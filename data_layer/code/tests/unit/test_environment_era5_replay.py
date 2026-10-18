"""M03 ERA5 replay adapter (synthetic fixture, no download) and the proxy-mode replay module."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.core.module import ContractError
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import NS_PER_S, TRUTH_DT_S, TRUTH_HZ
from phalanx.environment.atmosphere import geometric_altitude, moist_state, profile_tp, ussa76_profile
from phalanx.environment.config import load_env_config
from phalanx.environment.era5 import Era5Column, MetarOverride, pressure_residual, profile_at, vapour_pressure
from phalanx.environment.module import EnvironmentModule, EnvironmentReplay

CFG = load_env_config()
C = CFG.constants
CV = C.vector()
LEVELS_HPA = np.array([1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100.0])


def _fixture(dt_k=(5.0, 9.0)):
    """TEST FIXTURE: ERA5-like columns from ISA + dT at two analysis times 1 h apart, dry above 6 km."""
    p = LEVELS_HPA * 100
    rows = {"z": [], "t": [], "q": [], "u": [], "v": []}
    for d in dt_k:
        prof, n = ussa76_profile(CFG.layers, C, dt_k=d)
        hs = []
        for pk in p:  # invert p(H) by bisection on the hydrostatic profile
            lo, hi = -2000.0, 40000.0
            for _ in range(100):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if profile_tp(prof, n, mid, CV)[1] > pk else (lo, mid)
            hs.append(0.5 * (lo + hi))
        hs = np.array(hs)
        t = np.array([profile_tp(prof, n, h, CV)[0] for h in hs])
        rows["z"].append(hs * C.g0)
        rows["t"].append(t)
        rows["q"].append(np.where(hs < 6000, 0.01 * np.exp(-hs / 2000), 1e-6))
        rows["u"].append(np.linspace(2, 30, p.size))
        rows["v"].append(np.linspace(-1, 5, p.size))
    return Era5Column(
        np.array([0.0, 3600.0]),
        p,
        np.array(rows["z"]),
        np.array(rows["t"]),
        np.array(rows["q"]),
        np.array(rows["u"]),
        np.array(rows["v"]),
    )


@pytest.mark.unit
def test_era5_adapter_reproduces_levels_and_interpolates_in_time():
    col = _fixture()
    for t_s in (0.0, 1800.0, 3600.0):
        prof, n = profile_at(col, t_s, C, CFG.magnus)
        h = ((1 - t_s / 3600) * col.geopotential[0] + t_s / 3600 * col.geopotential[1]) / C.g0
        for k in range(h.size):
            assert profile_tp(prof, n, h[k], CV)[0] == pytest.approx(
                (1 - t_s / 3600) * col.temperature_k[0, k] + t_s / 3600 * col.temperature_k[1, k], abs=1e-9
            )
    # hydrostatic residual against the level pressures stays small (dry fixture -> pure interpolation error)
    assert np.max(np.abs(pressure_residual(col, 1800.0, C, CFG.magnus))) < 2e-3
    # winds: u east, v north
    prof, n = profile_at(col, 0.0, C, CFG.magnus)
    _, _, _, _, _, wn, we = moist_state(
        prof, n, geometric_altitude(float(col.geopotential[0, 5] / C.g0), C.r0), CV, CFG.magnus
    )
    assert we == pytest.approx(col.u_mps[0, 5], rel=1e-6) and wn == pytest.approx(col.v_mps[0, 5], rel=1e-6)
    e = vapour_pressure(np.array([0.01]), np.array([1e5]), C)
    eps = C.m_water / C.m0
    assert eps * e[0] / (1e5 - (1 - eps) * e[0]) == pytest.approx(0.01, rel=1e-12)


@pytest.mark.unit
def test_metar_override_sets_the_surface_node():
    col = _fixture()
    met = MetarOverride(229.0, 97000.0, 315.0, 290.0, 6.0, math.pi / 2)
    prof, n = profile_at(col, 600.0, C, CFG.magnus, metar=met)
    t, p, _, _, _q, wn, we = moist_state(prof, n, 229.0, CV, CFG.magnus)
    assert t == pytest.approx(315.0, abs=1e-6) and p == pytest.approx(97000.0, rel=1e-9)
    assert we == pytest.approx(-6.0, abs=1e-9) and abs(wn) < 1e-9  # wind from the east blows west
    with pytest.raises(ValueError):
        Era5Column(
            np.array([0.0]),
            LEVELS_HPA,
            np.zeros((1, 3)),
            np.zeros((1, 3)),
            np.zeros((1, 3)),
            np.zeros((1, 3)),
            np.zeros((1, 3)),
        )


@pytest.mark.unit
def test_profile_mode_module_uses_era5_winds_aloft():
    col = _fixture()
    prof = profile_at(col, 0.0, C, CFG.magnus)
    env = EnvironmentModule("env", CFG, profile=prof, profile_wind=True, cat_c_codes=())
    rng = RngService(1, StreamRegistry(env.streams))
    env.bind(rng.scope(KeyPath.of(scenario="e5", tail="T", sortie="S")))
    st = env.init(env.params, env.keys)
    h5 = geometric_altitude(float(col.geopotential[0, 9] / C.g0), C.r0)
    _, out = env.step_block(
        st,
        {"alt": np.array([h5]), "hag": np.array([h5]), "tas": np.array([200.0]), "phase": np.array([5])},
        np.array([0]),
        TRUTH_DT_S,
    )
    assert out["wind_ned"][0, 1] == pytest.approx(col.u_mps[0, 9], rel=1e-9)


@pytest.mark.unit
def test_replay_module_reproduces_recorded_flight_condition():
    """A-W1.1-14: ISA pressure at the recorded pressure altitude; SAT from TAT with unit recovery."""
    alt = np.array([0.0, 3000.0, 10000.0])
    mach = np.array([0.2, 0.6, 0.8])
    tat = np.array([300.0, 290.0, 250.0])
    env = EnvironmentReplay("env", CFG, pressure_alt_m=alt, mach=mach, tat_k=tat, rate_hz=1.0, n_engines=2)
    rng = RngService(2, StreamRegistry(env.streams))
    env.bind(rng.scope(KeyPath.of(scenario="rp", tail="T", sortie="S")))
    st = env.init(env.params, env.keys)
    t = (np.arange(3 * TRUTH_HZ, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
    st, out = env.step_block(st, {}, t, TRUTH_DT_S)
    std, ns = ussa76_profile(CFG.layers, C)
    for k in range(3):
        row = k * TRUTH_HZ + 10
        from phalanx.environment.atmosphere import geopotential_altitude

        assert out["p_s"][row] == pytest.approx(
            profile_tp(std, ns, geopotential_altitude(alt[k], C.r0), CV)[1], rel=1e-12
        )
        assert out["t_s"][row] == pytest.approx(tat[k] / (1 + 0.2 * mach[k] ** 2), rel=1e-12)
    assert out["w_engine"].shape == (3 * TRUTH_HZ, 2, 5) and np.std(out["w_engine"]) > 0
    assert np.all(out["turb_vel_body"] == 0) and np.all(out["wind_ned"] == 0)
    with pytest.raises(ContractError):
        EnvironmentReplay("env", CFG, pressure_alt_m=alt, mach=mach[:2], tat_k=tat, rate_hz=1.0)


@pytest.mark.unit
def test_replay_module_four_engine_proxy_topology():
    """AD-43 proxy (n_engines = 4): one engine-specific stream per serial; engines differ, shapes follow e.
    Sample: 2 s of 240 Hz ticks (smoke; the 4-engine PSD/coherence check is the statistical A3 case)."""
    alt, mach, tat = np.array([3000.0, 3000.0]), np.array([0.5, 0.5]), np.array([280.0, 280.0])
    serials = [f"E{k}" for k in range(4)]
    env = EnvironmentReplay(
        "env", CFG, pressure_alt_m=alt, mach=mach, tat_k=tat, rate_hz=1.0, n_engines=4, engine_serials=serials
    )
    rng = RngService(3, StreamRegistry(env.streams))
    env.bind(rng.scope(KeyPath.of(scenario="rp4", tail="T", sortie="S")))
    st = env.init(env.params, env.keys)
    t = (np.arange(2 * TRUTH_HZ, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
    st, out = env.step_block(st, {}, t, TRUTH_DT_S)
    w = out["w_engine"]
    assert w.shape == (2 * TRUTH_HZ, 4, 5) and out["w_bleed_pto"].shape == (2 * TRUTH_HZ, 4)
    assert np.all(np.isfinite(w))
    for a in range(4):
        for b in range(a + 1, 4):
            assert not np.array_equal(w[:, a, :], w[:, b, :]), (a, b)  # engine-specific components present
