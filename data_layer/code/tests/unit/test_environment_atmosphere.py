"""M03 atmosphere (W1.1 A1): USSA-1976 reproduction, anchored and design-day profiles, moist air.

Reference values: USSA-1976 (NASA-TM-X-74335). The layer-base pressures P_b (7 significant figures, the
standard's layer table) are reproduced to 1e-6 relative; the sea-level state (T, p, rho, a) and the layer-base
temperatures are checked at their printed precision. The full Table I (5 significant figures, geometric
altitude) is not in the evidence base (research_sources has no copy), so it is not used as a golden
reference: a W1.1 data request. No sample: deterministic."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.environment.atmosphere import (
    PR_P,
    anchored_offset_profile,
    build_profile,
    design_day_profile,
    geometric_altitude,
    geopotential_altitude,
    moist_state,
    profile_tp,
    ussa76_profile,
)
from phalanx.environment.config import load_env_config

CFG = load_env_config()
C = CFG.constants
CV = C.vector()
DRY = np.array([610.94, 17.625, 243.04])

# USSA-1976 layer-base pressures (Pa) at H_b = 0, 11, 20, 32, 47, 51, 71 km' (7 significant figures)
P_B = [101325.0, 22632.06, 5474.889, 868.0187, 110.9063, 66.93887, 3.956420]

# USSA-1976 sea-level state as printed: T (K), p (Pa), rho (kg/m^3), a (m/s)
SEA_LEVEL = ("288.150", "1.01325e5", "1.2250", "340.29")
# layer-base temperatures (K) at H_b = 0, 11, 20, 32, 47, 51, 71, 84.852 km'
T_B = ("288.150", "216.650", "216.650", "228.650", "270.650", "270.650", "214.650", "186.946")


def _half_ulp(printed: str) -> float:
    """Half a unit in the last printed digit of a table value (its printing precision)."""
    mant, _, exp = printed.lower().partition("e")
    decimals = len(mant.split(".")[1]) if "." in mant else 0
    return 0.5 * 10.0 ** (-decimals + (int(exp) if exp else 0))


def _matches(value: float, printed: str) -> bool:
    return abs(value - float(printed)) <= _half_ulp(printed) * (1 + 1e-9)


@pytest.mark.golden
def test_ussa76_layer_base_pressures_to_1e_minus_6():
    prof, _n = ussa76_profile(CFG.layers, C)
    for j, pb in enumerate(P_B):
        assert abs(prof[PR_P, j] / pb - 1.0) <= 1e-6, (j, prof[PR_P, j], pb)


@pytest.mark.golden
def test_ussa76_sea_level_state_and_layer_temperatures_at_print_precision():
    prof, n = ussa76_profile(CFG.layers, C)
    t, p, rho, a, q, _, _ = moist_state(prof, n, 0.0, CV, DRY)
    assert q < 1e-9
    for v, ref in zip((t, p, rho, a), SEA_LEVEL, strict=True):
        assert _matches(v, ref), (v, ref)
    for j, ref in enumerate(T_B):
        assert _matches(prof[1, j], ref), (j, prof[1, j], ref)
    # negative control: a 1 % temperature error is outside print precision
    assert not _matches(288.150 * 1.01, "288.150")


@pytest.mark.unit
def test_negative_control_wrong_constant_breaks_table():
    """A 0.1 % error in the molecular weight must be caught by the 1e-6 layer-base check."""
    from dataclasses import replace

    bad = replace(C, m0=C.m0 * 1.001)
    prof, _ = ussa76_profile(CFG.layers, bad)
    assert max(abs(prof[PR_P, j] / pb - 1.0) for j, pb in enumerate(P_B)) > 1e-4


@pytest.mark.unit
def test_geopotential_roundtrip_and_values():
    for z in (0.0, 1000.0, 11019.13, 86000.0):
        h = geopotential_altitude.py_func(z, C.r0)
        assert geometric_altitude.py_func(h, C.r0) == pytest.approx(z, rel=1e-12, abs=1e-9)
    # USSA-1976: Z = 86 km corresponds to H = 84.852 km'
    assert geopotential_altitude.py_func(86000.0, C.r0) == pytest.approx(84852.0, abs=0.5)


@pytest.mark.unit
def test_anchor_reproduces_station_conditions_and_is_hydrostatic():
    """Bikaner May afternoon (IMD 974.3 hPa, 40.7 C at 224 m): the profile returns the anchor exactly and
    satisfies dp/dH = -p g0 M0 / (R* T) (finite difference)."""
    hs = geopotential_altitude.py_func(224.0, C.r0)
    prof, n = anchored_offset_profile(
        CFG.layers,
        C,
        h_station=hs,
        p_station=97430.0,
        t_station=313.85,
        e_station=1330.0,
        vapour_scale_height=2000.0,
    )
    t, p = profile_tp(prof, n, hs, CV)
    assert t == pytest.approx(313.85, abs=1e-9) and p == pytest.approx(97430.0, rel=1e-12)
    for h in (100.0, 3000.0, 10500.0, 15000.0):
        dh = 0.01
        _, p1 = profile_tp(prof, n, h - dh, CV)
        t0, p0 = profile_tp(prof, n, h, CV)
        _, p2 = profile_tp(prof, n, h + dh, CV)
        dpdh = (p2 - p1) / (2 * dh)
        assert dpdh == pytest.approx(-p0 * C.g0 * C.m0 / (C.r_star * t0), rel=1e-6), h
    # the temperature offset from ISA is constant with altitude
    std, ns = ussa76_profile(CFG.layers, C)
    d = [profile_tp(prof, n, h, CV)[0] - profile_tp(std, ns, h, CV)[0] for h in (0.0, 5000.0, 15000.0)]
    assert np.ptp(d) < 1e-9


@pytest.mark.unit
def test_moist_air_is_lighter_and_dry_limit_is_ussa():
    std, ns = ussa76_profile(CFG.layers, C)
    t, p, rho_dry, a_dry, _q, _, _ = moist_state(std, ns, 0.0, CV, DRY)
    hum, nh = build_profile(
        std[0, :ns], std[1, :ns], C, p_anchor=101325.0, h_anchor=0.0, lne_nodes=np.full(ns, math.log(1000.0))
    )
    t2, p2, rho_wet, a_wet, q2, _, _ = moist_state(hum, nh, 0.0, CV, DRY)
    assert t2 == t and p2 == p
    eps = C.m_water / C.m0
    assert q2 == pytest.approx(eps * 1000.0 / (p - (1 - eps) * 1000.0), rel=1e-12)
    assert rho_wet < rho_dry and a_wet > a_dry
    assert rho_wet == pytest.approx(rho_dry / (1 + (1 / eps - 1) * q2), rel=1e-12)


@pytest.mark.unit
def test_vapour_capped_at_saturation():
    std, ns = ussa76_profile(CFG.layers, C)
    wet, nw = build_profile(
        std[0, :ns], std[1, :ns], C, p_anchor=101325.0, h_anchor=0.0, lne_nodes=np.full(ns, math.log(1e5))
    )
    t, p, _, _, q, _, _ = moist_state(wet, nw, 9000.0, CV, DRY)
    tc = t - 273.15
    es = 610.94 * math.exp(17.625 * tc / (tc + 243.04))
    eps = C.m_water / C.m0
    assert q == pytest.approx(eps * es / (p - (1 - eps) * es), rel=1e-12)


@pytest.mark.unit
def test_design_day_table_altitude_is_pressure_altitude():
    """JSSG-2007A Fig. 5 note 4 convention: at every table node the pressure is the USSA pressure at the
    table altitude and the temperature is the table value; between nodes the profile is hydrostatic
    (a synthetic hot table; the MIL-HDBK-310 tables themselves are data-pending, A-W1.1-15)."""
    hp = np.array([0.0, 5000.0, 11000.0, 20000.0])
    t = np.array([322.15, 290.0, 230.0, 220.0])
    prof, n = design_day_profile(hp, t, CFG.layers, C)
    std, ns = ussa76_profile(CFG.layers, C)
    for k in range(n):
        tt, p = profile_tp(prof, n, prof[0, k], CV)
        assert p == pytest.approx(profile_tp(std, ns, hp[k], CV)[1], rel=1e-12)
        assert tt == pytest.approx(t[k], abs=1e-9)
    # a hot day is taller than ISA: the 11 km pressure level lies above 11 km geopotential
    assert prof[0, 2] > 11000.0
    for x in np.linspace(prof[0, 0], prof[0, n - 1], 41):
        dh = 0.01
        t0, p0 = profile_tp(prof, n, x, CV)
        dpdh = (profile_tp(prof, n, x + dh, CV)[1] - profile_tp(prof, n, x - dh, CV)[1]) / (2 * dh)
        assert dpdh == pytest.approx(-p0 * C.g0 * C.m0 / (C.r_star * t0), rel=1e-5)


@pytest.mark.property
@settings(max_examples=40, deadline=None)
@given(
    dt=st.floats(-40.0, 40.0),
    hs=st.floats(0.0, 3500.0),
    p_rel=st.floats(0.97, 1.03),
)
def test_pressure_decreases_and_temperature_is_offset_isa(dt, hs, p_rel):
    std, ns = ussa76_profile(CFG.layers, C)
    t_isa, p_isa = profile_tp(std, ns, hs, CV)
    prof, n = anchored_offset_profile(
        CFG.layers,
        C,
        h_station=hs,
        p_station=p_isa * p_rel,
        t_station=t_isa + dt,
        e_station=500.0,
        vapour_scale_height=2000.0,
    )
    hs_grid = np.linspace(-500.0, 30000.0, 60)
    ps = np.array([profile_tp(prof, n, x, CV)[1] for x in hs_grid])
    assert np.all(np.diff(ps) < 0) and np.all(ps > 0)
    for x in (hs, 12000.0):
        assert profile_tp(prof, n, x, CV)[0] - profile_tp(std, ns, x, CV)[0] == pytest.approx(dt, abs=1e-9)
