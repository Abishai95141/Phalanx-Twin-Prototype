"""M09 hydraulics and AMAGB/PTO behaviour (architecture §6 M09; report §3; note KQ2).

Each test drives the M09 module through TEST FIXTURE inputs (tests/unit/test_utilities_support.py).
Samples: 2-60 s of 240 Hz truth per case (stated per test); steady values are taken after >= 5 time constants.
"""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import N2_100, inputs, module, run

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L

PS = load_m09_params()
Q_RATED = PS.value("hyd_q_rated")  # m^3/s
P_NOM = PS.value("hyd_p_nom")
BAR = 1e5


def _steady(n2f=0.95, demand=0.0, seconds=4.0, health=None, config=None, params=None, wf=0.6):
    m, st = module(config or UtilitiesConfig(soak_temp=300.0), params)
    st, out = run(m, st, inputs(int(seconds * 240), n2f=n2f, demand=demand, health=health, wf=wf))
    return m, st, out


@pytest.mark.unit
def test_nominal_pressure_holds_at_280_bar_with_low_demand():
    """n = 4 s: the compensated pump holds the system within its droop band of 280 bar (DIRECT)."""
    _, _, out = _steady(demand=0.1 * Q_RATED)
    p = out["hyd_p"][-240:]
    assert np.all(p <= P_NOM) and np.all(p > P_NOM - PS.value("hyd_dp_band"))
    assert np.array_equal(out["hyd_dp_avail"][-1], out["hyd_p"][-1] - PS.value("hyd_p_ret"))


@pytest.mark.unit
def test_qmax_scales_with_n2():
    """Demand 0.75 q_rated: met at 100 % N2, not at 65 % N2 (Q_max = q_rated * N2 ratio). n = 4 s each."""
    _, _, hi = _steady(n2f=1.0, demand=0.75 * Q_RATED)
    _, _, lo = _steady(n2f=0.65, demand=0.75 * Q_RATED)
    assert hi["hyd_p"][-1, 0] > 0.9 * P_NOM
    assert lo["hyd_p"][-1, 0] < 0.5 * P_NOM


@pytest.mark.unit
def test_pressure_sags_only_when_demand_exceeds_qmax():
    """95 % N2: demand below Q_max minus leakage stays in the droop band; above Q_max it sags (report §3)."""
    q_max = 0.95 * Q_RATED
    held = [_steady(n2f=0.95, demand=x * q_max)[2]["hyd_p"][-1, 0] for x in (0.0, 0.4, 0.8)]
    sag = _steady(n2f=0.95, demand=1.15 * q_max)[2]["hyd_p"][-1, 0]
    band = PS.value("hyd_dp_band") + 3 * PS.value("hyd_filter_dp")
    assert all(p > P_NOM - band for p in held)
    assert held[0] > held[1] > held[2]  # droop: more flow, slightly lower pressure
    assert sag < 0.5 * P_NOM


@pytest.mark.unit
def test_leakage_rises_with_temperature():
    """Warm fluid: lower viscosity -> more internal leakage -> the pump strokes further at zero demand
    (report §3 edge 'hydraulic temperature -> leakage, pump volumetric efficiency'). n = 2 s per case."""
    swash = {}
    for t in (250.0, 330.0, 380.0):
        m, st, _ = _steady(seconds=2.0, config=UtilitiesConfig(soak_temp=t))
        swash[t] = m.truth_view(st)["hyd_swash"][0]
    assert swash[250.0] < swash[330.0] < swash[380.0]


def _volume_drift(nsub):
    h = np.zeros(L.N_HEALTH)
    h[L.H_EXT_LEAK] = 0.01
    m, st0 = module(UtilitiesConfig(soak_temp=300.0), PS.replace(hyd_nsub=nsub))
    inv0 = m.truth_view(st0, h, p_amb=70108.0)["hyd_volume_invariant"]
    n = 60 * 240
    k = np.arange(n)
    demand = 0.9 * Q_RATED * ((k // 240) % 4 == 0)
    st, _ = run(m, st0, inputs(n, demand=demand, health=h, alt=3000.0))
    tv = m.truth_view(st, h, p_amb=70108.0)
    return np.abs(np.array(tv["hyd_volume_invariant"]) - np.array(inv0)), tv, st


@pytest.mark.unit
def test_fluid_volume_balance_closes():
    """A1 (fluid): reservoir + accumulator fluid + compression + lost overboard - thermal expansion is
    invariant up to the explicit-Euler error of the accumulator compliance. n = 60 s of 0.9 Q_rated demand
    bursts (1 s in 4 s) with an external leak on system 1 (fluid warms ~18 K). Stated tolerance: 5 mL of a 15
    L system (0.03 %); the error is first order in the sub-step (it shrinks when the sub-steps double)."""
    drift8, tv, st = _volume_drift(8)
    drift16, _, _ = _volume_drift(16)
    assert np.all(drift8 < 5e-6)
    assert np.all(drift16 < 0.75 * drift8)
    lost = float(st["f"][L.F_HYD_VEXT])
    assert lost > 1e-5  # the external leak drained fluid ...
    assert tv["hyd_level"][0] < tv["hyd_level"][1]  # ... and the leaking system's reservoir level is lower


@pytest.mark.unit
def test_precharge_loss_deepens_transient_dip():
    """A step demand of 0.9 Q_max for 0.5 s: with 90 % precharge loss the accumulator no longer buffers,
    so the pressure dip is deeper. n = 3 s per case."""
    dips = []
    for loss in (0.0, 0.9):
        h = np.zeros(L.N_HEALTH)
        h[L.H_PRECHARGE] = loss
        k = np.arange(3 * 240)
        demand = 0.9 * 0.95 * Q_RATED * ((k >= 240) & (k < 360))
        _, _, out = _steady(seconds=3.0, demand=demand, health=h)
        dips.append(out["hyd_p"][:, 0].min())
    assert dips[1] < dips[0] - 2 * BAR


@pytest.mark.unit
def test_cold_soak_lowers_accumulator_precharge():
    from phalanx.utilities.hydraulics import precharge
    from phalanx.utilities.params import param_vector

    p = param_vector(PS)
    assert (
        precharge(p, 0.0, 253.15, 101325.0)
        < precharge(p, 0.0, 288.15, 101325.0)
        < precharge(p, 0.0, 313.15, 101325.0)
    )


@pytest.mark.unit
def test_relief_valve_caps_overpressure():
    """Compensator drifted +20 % (cut-off 336 bar) at zero demand: the relief valve holds the system between
    its cracking and full-flow pressures. n = 4 s."""
    h = np.zeros(L.N_HEALTH)
    h[L.H_COMP_DRIFT] = 0.2
    _, _, out = _steady(health=h)
    p = out["hyd_p"][-1, 0]
    assert PS.value("hyd_relief_crack") * P_NOM < p < PS.value("hyd_relief_full") * P_NOM


@pytest.mark.unit
def test_filter_loading_lowers_pressure_under_flow():
    """Pressure filter at 90 % loading: higher dP at the pump outlet; the compensator senses the pump outlet,
    so the delivered system pressure is lower under flow and unchanged without flow. n = 4 s per case."""
    h = np.zeros(L.N_HEALTH)
    h[L.H_FILTER] = 0.9
    clean = _steady(demand=0.6 * Q_RATED)[2]["hyd_p"][-1, 0]
    loaded = _steady(demand=0.6 * Q_RATED, health=h)[2]["hyd_p"][-1, 0]
    assert loaded < clean - 1 * BAR
    clean0 = _steady(demand=0.0)[2]["hyd_p"][-1, 0]
    loaded0 = _steady(demand=0.0, health=h)[2]["hyd_p"][-1, 0]
    assert abs(loaded0 - clean0) < abs(loaded - clean)


@pytest.mark.unit
def test_substep_convergence():
    """A-W1.4-11: 8 vs 16 sub-steps give the same steady pressure within 0.05 bar and the same burst response
    within 1 bar. n = 3 s with a demand burst."""
    k = np.arange(3 * 240)
    demand = 0.7 * Q_RATED * ((k >= 240) & (k < 300))
    a = _steady(seconds=3.0, demand=demand)[2]["hyd_p"][:, 0]
    b = _steady(seconds=3.0, demand=demand, params=PS.replace(hyd_nsub=16))[2]["hyd_p"][:, 0]
    assert abs(a[-1] - b[-1]) < 0.05 * BAR
    assert np.max(np.abs(a - b)) < 1.0 * BAR


@pytest.mark.unit
def test_pto_power_within_ptoshaft_rating():
    """At 100 % N2 with both pumps at full flow and airborne electrical loads, the summed accessory load stays
    under the PTO normal rating 118 N m x 16,810 rpm (~208 kW, DIRECT ceiling, note KQ1). n = 3 s."""
    _, _, out = _steady(n2f=1.0, demand=1.0 * Q_RATED, seconds=3.0)
    ceiling = PS.value("pto_torque_normal") * PS.value("pto_rated_speed")
    p = out["pto_power"][-1, 0]
    assert 0.3 * ceiling < p < ceiling
    assert p / (N2_100 * PS.value("pto_ratio")) < PS.value("pto_torque_normal")


@pytest.mark.unit
def test_reservoir_level_port_and_amagb_speed_channel():
    """util.hyd_res_level is the reservoir fluid volume over its 9.5 L capacity and falls with an external
    leak; the recorded SPS.AMAGB.SPEED (utility EU) is N2 times the PTO ratio. n = 30 s."""
    h = np.zeros(L.N_HEALTH)
    h[L.H_EXT_LEAK + 1] = 0.02
    _m, st, out = _steady(seconds=30.0, health=h)
    lvl = out["hyd_res_level"]
    assert lvl[-1, 1] < lvl[0, 1] and abs(lvl[-1, 0] - lvl[0, 0]) < abs(lvl[-1, 1] - lvl[0, 1])
    assert lvl[-1, 0] == pytest.approx(float(st["f"][L.F_HYD_VRES]) / PS.value("hyd_res_v"))
    assert out["amagb_speed"][-1] == pytest.approx(0.95 * N2_100 * PS.value("pto_ratio"))
