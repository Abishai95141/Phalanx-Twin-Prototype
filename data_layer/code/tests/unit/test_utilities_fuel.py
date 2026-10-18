"""M09 fuel: transfer and mass conservation, mass properties, the F1A pick-up stall (true-quantity side of the
zoom-climb case; the gauge is M12's under AD-42), heat sink, and the exposing test of the 1-D free-surface
PROXY (A-W1.4-15).

Samples: transfer 120 s; artefact cases 10 s settle + 45 s manoeuvre each (stated per test).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import (
    G0,
    T_MAX_AB,
    T_MIL,
    WF_MAX_AB,
    WF_MIL,
    climb_profile,
    inputs,
    module,
    run,
)

from phalanx.core.module import ContractError
from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L

PS = load_m09_params()
RHO15 = PS.value("fuel_rho_15")
CAP = np.asarray(PS.value("tank_cap"))  # m^3


def _fuel(total: float) -> tuple[float, ...]:
    """Internal-only distribution after the transfer sequence: feed group (F1, F2 at the fill target) full
    first, then F1A, then the wings (TEST FIXTURE helper mirroring the ECFM order)."""
    cap = CAP * RHO15
    m = np.zeros(L.N_TANKS)
    rest = total
    for k, c in (
        (L.T_F1, cap[L.T_F1]),
        (L.T_F2, PS.value("fuel_fill_target") * cap[L.T_F2]),
        (L.T_F1A, cap[L.T_F1A]),
    ):
        m[k] = min(c, rest)
        rest -= m[k]
    m[L.T_WL] = m[L.T_WR] = rest / 2
    return tuple(m)


@pytest.mark.unit
def test_transfer_sequence_and_mass_conservation():
    """Full internal + all drop tanks, cruise burn 1 kg/s for 120 s: drop tanks transfer first (centreline,
    then the inboard pair evenly), wings and F1A stay full, F2 is held at its fill target, and the fuel mass
    balance closes exactly (A1 fuel): initial - final = burned (unmet = 0)."""
    cfg = UtilitiesConfig(drop_tanks=(True, True, True), soak_temp=288.15)
    m, st0 = module(cfg)
    m0 = st0["f"][L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS].copy()
    st, out = run(m, st0, inputs(120 * 240, wf=1.0))
    m1 = st["f"][L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS]
    burned = float(st["f"][L.F_FUEL_BURN])
    assert burned == pytest.approx(120.0, rel=1e-9) and float(st["f"][L.F_FUEL_UNMET]) == 0.0
    assert m0.sum() - m1.sum() == pytest.approx(burned, abs=1e-9)
    assert m1[L.T_DTC] < m0[L.T_DTC] - 100.0  # centreline drop tank feeds first
    assert m1[L.T_DTL] == m0[L.T_DTL] and m1[L.T_WL] == m0[L.T_WL] and m1[L.T_F1A] == m0[L.T_F1A]
    assert m1[L.T_F2] == pytest.approx(PS.value("fuel_fill_target") * CAP[L.T_F2] * RHO15, rel=0.01)
    assert np.allclose(out["fuel_mass"][-1], m1)
    # mass port tracks the fuel: dm = -burned
    assert out["mass"][0] - out["mass"][-1] == pytest.approx(
        burned - (m0.sum() - out["fuel_mass"][0].sum()), rel=1e-6
    )


@pytest.mark.unit
def test_inboard_drop_tanks_transfer_evenly_and_wings_after():
    cap = CAP * RHO15
    fuel = list(_fuel(2400.0))
    fuel[L.T_DTL] = fuel[L.T_DTR] = 50.0
    m, st = module(UtilitiesConfig(fuel=tuple(fuel), drop_tanks=(True, True, False)))
    st, _ = run(m, st, inputs(120 * 240, wf=1.2))  # 144 kg burned > 100 kg in the drop tanks
    f = st["f"][L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS]
    assert f[L.T_DTL] == pytest.approx(f[L.T_DTR], abs=1e-9)
    assert f[L.T_DTL] < 0.01 * cap[L.T_DTL] + 1e-6  # drained to residual
    assert f[L.T_WL] < fuel[L.T_WL] and f[L.T_WL] == pytest.approx(f[L.T_WR])  # wings follow, evenly


@pytest.mark.unit
def test_feed_tank_exhaustion_is_reported_as_unmet_demand():
    m, st = module(UtilitiesConfig(fuel=(5.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0)))
    st, _ = run(m, st, inputs(10 * 240, wf=2.0))
    assert float(st["f"][L.F_FUEL_UNMET]) > 0.0
    assert np.all(st["f"][L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS] >= 0.0)
    assert float(st["f"][L.F_FUEL_BURN]) + float(st["f"][L.F_FUEL_UNMET]) == pytest.approx(20.0, rel=1e-9)


@pytest.mark.unit
def test_mass_properties_reproduce_reference():
    """At the reference loading (OE + fuselage tanks holding m_ref - m_oe, 15 degC, no stores) the module
    reproduces the DIRECT-unnamed 9,000 kg inertia tensor exactly and puts the CG on the datum (A-W1.4-17)."""
    caps = CAP[[L.T_F1, L.T_F1A, L.T_F2]]
    m_ref_fuel = (PS.value("mp_m_ref") - PS.value("mp_m_oe")) * caps / caps.sum()
    fuel = np.zeros(L.N_TANKS)
    fuel[[L.T_F1, L.T_F1A, L.T_F2]] = m_ref_fuel
    m, st = module(UtilitiesConfig(fuel=tuple(fuel), soak_temp=288.15))
    out = m.initial_outputs(st)
    assert float(out["mass"]) == pytest.approx(9000.0, abs=1e-9)
    assert np.allclose(out["cg"], 0.0, atol=1e-12)
    j = out["inertia"]
    ref = np.array([[14087.9, -162.5, -2490.5], [-162.5, 66558.9, -32.5], [-2490.5, -32.5, 77875.2]])
    assert np.allclose(j, ref, atol=1e-6)


@pytest.mark.unit
def test_mass_properties_respond_to_fuel_and_stores():
    """Wing fuel raises Ixx (lateral arm); burning it lowers mass and Ixx; drop tanks lower the CG (z down)
    and move it toward the stations; the tensor stays symmetric positive definite."""
    m, st_full = module(UtilitiesConfig())
    full = m.initial_outputs(st_full)
    m2, st_dt = module(UtilitiesConfig(drop_tanks=(True, True, True)))
    dt = m2.initial_outputs(st_dt)
    m3, st_low = module(UtilitiesConfig(fuel=_fuel(1658.0)))
    low = m3.initial_outputs(st_low)
    assert float(dt["mass"]) > float(full["mass"]) > float(low["mass"])
    assert full["inertia"][0, 0] > low["inertia"][0, 0] + 1000.0
    assert dt["cg"][2] > full["cg"][2]  # z down: drop tanks hang below
    for j in (full["inertia"], dt["inertia"], low["inertia"]):
        assert np.allclose(j, j.T) and np.all(np.linalg.eigvalsh(j) > 0)
        ev = np.linalg.eigvalsh(j)
        assert ev[0] + ev[1] >= ev[2]  # triangle inequality of principal moments


@pytest.mark.unit
def test_fuel_config_guards():
    with pytest.raises(ContractError):
        module(UtilitiesConfig(fuel=(0.0,) * 7))
    with pytest.raises(ContractError):
        module(UtilitiesConfig(fuel=(0, 0, 0, 0, 0, 100.0, 0, 0)))  # drop tank not fitted
    with pytest.raises(ContractError):
        module(UtilitiesConfig(fuel=(1e4, 0, 0, 0, 0, 0, 0, 0)))  # over capacity


def _zoom(total: float, theta: float, thrust: float, wf: float, mod: int = 0, seconds: float = 45.0):
    """TEST FIXTURE manoeuvre after a 10 s level settle. Returns (F1A fuel moved out / fuel burned during the
    manoeuvre, true feed-group (F1 + F2) mass at the end, F1A mass at the end)."""
    m, st = module(UtilitiesConfig(fuel=_fuel(total), f1a_mod=mod))
    st, _ = run(m, st, inputs(2400, wf=WF_MIL, fspec=(0.25 * G0, 0.0, -G0)))
    f1a0 = float(st["f"][L.F_FUEL_M + L.T_F1A])
    burn0 = float(st["f"][L.F_FUEL_BURN])
    fs, tas = climb_profile(theta, thrust, seconds=seconds)
    st, _ = run(m, st, inputs(int(seconds * 240), wf=wf, fspec=fs, tas=tas))
    moved = f1a0 - float(st["f"][L.F_FUEL_M + L.T_F1A])
    burned = float(st["f"][L.F_FUEL_BURN]) - burn0
    return moved / burned, m.truth_view(st)["feed_mass"], float(st["f"][L.F_FUEL_M + L.T_F1A])


FEED_LOW = 600.0  # kg: ~30 min of feed-tank fuel at max-range cruise (MIL-F-17874B rule); test criterion only


@pytest.mark.unit
def test_f1a_pickup_stall_boundary():
    """True-quantity side of the zoom-climb case (ADA AR 2017-18/2018-19; the gauge and the warning are M12's,
    AD-42): in a > 40 deg max-AB zoom with < 1,200 kg, F1A's forward pick-up uncovers, F1A stops feeding F2
    (>= 250 kg stranded) and max-AB burn drains the true F1 + F2 contents below 600 kg within 45 s. With
    more fuel, at MIL power, in a shallow climb, in level max-AB acceleration, or after the F1A
    modification the feed group stays above 600 kg. Seven 55 s cases; the boundary is a curve in surface
    slope x F1A contents (A-W1.4-14), calibrated to the ADA test condition."""
    ratio, feed, f1a = _zoom(1150.0, 45.0, T_MAX_AB, WF_MAX_AB)
    assert ratio < 0.6 and f1a >= 250.0 and feed < FEED_LOW
    assert _zoom(1100.0, 40.0, T_MAX_AB, WF_MAX_AB)[1] < FEED_LOW
    for case in (
        (1300.0, 45.0, T_MAX_AB, WF_MAX_AB, 0),  # more fuel: the stall comes later
        (1150.0, 45.0, T_MIL, WF_MIL, 0),  # MIL: shallower surface, slow burn
        (1150.0, 30.0, T_MAX_AB, WF_MAX_AB, 0),  # shallow climb
        (1150.0, 0.0, T_MAX_AB, WF_MAX_AB, 0),  # level max-AB acceleration
        (1150.0, 45.0, T_MAX_AB, WF_MAX_AB, 1),  # post-modification
    ):
        assert _zoom(*case[:4], mod=case[4])[1] >= FEED_LOW, case
    # post-modification F1A keeps feeding at the full burn rate
    assert _zoom(1150.0, 45.0, T_MAX_AB, WF_MAX_AB, mod=1)[0] > 0.85


@pytest.mark.unit
def test_roll_plane_tilt_not_represented():
    """PROXY A-W1.4-15 exposing test: a sustained lateral specific force (sideslip / roll-plane tilt) changes
    nothing in the fuel model (slope, pick-up wetness, transfer), although a real wing-tank surface would
    tilt."""
    outs = []
    for fy in (0.0, 0.5 * G0):
        m, st = module(UtilitiesConfig(fuel=_fuel(2000.0)))
        st, _ = run(m, st, inputs(10 * 240, wf=1.0, fspec=(0.1 * G0, fy, -G0)))
        tv = m.truth_view(st)
        outs.append(
            (tv["fuel_slope"], tuple(tv["fuel_pickup_wetness"]), tuple(st["f"][L.F_FUEL_M : L.F_FUEL_M + 8]))
        )
    assert outs[0] == outs[1]


@pytest.mark.unit
def test_fuel_temperature_follows_recovery_temperature():
    """Tank fuel warms toward the recovery temperature (hot-day ground hold vs high-altitude cruise). n = 600
    s."""
    temps = []
    for alt, mach, ts in ((0.0, 0.0, 315.15), (11000.0, 0.85, None)):
        m, st = module(UtilitiesConfig(soak_temp=300.0))
        st, _ = run(m, st, inputs(600 * 240, alt=alt, mach=mach, t_s=ts, wf=0.3))
        temps.append(float(st["f"][L.F_FUEL_T]))
    assert temps[0] > 300.0 > temps[1]


@pytest.mark.unit
def test_fuel_inlet_temperature_carries_the_hydraulic_heat():
    """util.fuel_inlet_t = tank fuel temperature + hydraulic HX heat / (Wf cp): low fuel flow (idle) gives a
    hotter engine inlet than high flow for the same hydraulic duty (report §3 heat-sink edge); it never
    exceeds the hottest hydraulic fluid (epsilon-NTU bound). n = 60 s each."""
    res = {}
    for wf in (0.08, 2.0):
        m, st = module(UtilitiesConfig(soak_temp=300.0))
        st, out = run(m, st, inputs(60 * 240, wf=wf, demand=4e-4))
        res[wf] = (
            float(out["fuel_inlet_t"][-1, 0]),
            float(st["f"][L.F_FUEL_T]),
            float(out["hyd_t"][-1].max()),
        )
    lo, hi = res[0.08], res[2.0]
    assert lo[0] > hi[0] > hi[1]
    assert lo[1] < lo[0] <= lo[2]
