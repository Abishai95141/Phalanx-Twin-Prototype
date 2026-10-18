"""A2: every coupling-map sign in report §3 that M09 implements holds (edges as data:
configs/tejas/params/M09/coupling_signs.csv). Each edge has a probe that runs M09 at a low and a high value of
the driver (everything else equal, TEST FIXTURE inputs) and returns (driven_lo, driven_hi, tolerance).

Samples: 2-60 s of truth per probe side (stated in each probe); JFS probes run one start each.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_utilities_support import (
    G0,
    N2_100,
    event,
    ground_inputs,
    inputs,
    isa,
    module,
    run,
    start_protocol,
)

from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as L
from phalanx.utilities.coupling import load_coupling_table
from phalanx.utilities.electrical import battery_r
from phalanx.utilities.hydraulics import precharge
from phalanx.utilities.params import param_vector

PS = load_m09_params()
P = param_vector(PS)
Q = PS.value("hyd_q_rated")
BAR = 1e5
TABLE = load_coupling_table()


def _last(out, port, idx=(-1, 0)):
    return float(out[port][idx])


def _hyd(n2f, demand, seconds=4.0, soak=300.0, health=None, wf=0.6):
    m, st = module(UtilitiesConfig(soak_temp=soak))
    st, out = run(m, st, inputs(int(seconds * 240), n2f=n2f, demand=demand, health=health, wf=wf))
    return m, st, out


def p_r3_1a():
    return (_last(_hyd(0.70, 0.8 * Q)[2], "hyd_p"), _last(_hyd(1.0, 0.8 * Q)[2], "hyd_p"), 1 * BAR)


def p_r3_1b():
    lo = _hyd(0.50, 0.0)[2]["gen_online"][-1]
    hi = _hyd(0.70, 0.0)[2]["gen_online"][-1]
    return float(lo), float(hi), 0.5


def p_r3_1c():
    return (_last(_hyd(0.75, 1e-4)[2], "pto_power"), _last(_hyd(1.0, 1e-4)[2], "pto_power"), 100.0)


def p_r3_2a():
    """90 % N2 (Q_max = 0.9 q_rated): demand 0.85 Q_max (held) vs 1.15 Q_max (above Q_max: sags)."""
    return (
        _last(_hyd(0.9, 0.85 * 0.9 * Q)[2], "hyd_p"),
        _last(_hyd(0.9, 1.15 * 0.9 * Q)[2], "hyd_p"),
        5 * BAR,
    )


def p_r3_2b():
    lo, hi = _last(_hyd(0.95, 0.0)[2], "hyd_p"), _last(_hyd(0.95, 0.5 * Q)[2], "hyd_p")
    return lo, hi, PS.value("hyd_dp_band") + 2 * PS.value("hyd_filter_dp")


def p_r3_2c():
    return (
        _last(_hyd(0.65, 0.9 * Q)[2], "hyd_dp_avail"),
        _last(_hyd(0.95, 0.9 * Q)[2], "hyd_dp_avail"),
        5 * BAR,
    )


def _swash(soak):
    m, st, _ = _hyd(0.95, 0.0, seconds=2.0, soak=soak)
    return m.truth_view(st)["hyd_swash"][0]


def p_r3_3a():
    return _swash(270.0), _swash(370.0), 1e-4


def p_r3_3b():
    return (
        _last(_hyd(0.9, 0.97 * 0.9 * Q, soak=270.0, seconds=2.0)[2], "hyd_dp_avail"),
        _last(_hyd(0.9, 0.97 * 0.9 * Q, soak=380.0, seconds=2.0)[2], "hyd_dp_avail"),
        0.5 * BAR,
    )


def p_r3_4():
    """N2 spool-down 70 % -> 30 % in 20 s: generator online before (hi N2) vs after (lo N2)."""
    n = 30 * 240
    n2f = np.clip(0.7 - 0.02 * np.arange(n) / 240, 0.3, None)
    _, _, out = _hyd(n2f, 0.0, seconds=30.0)
    return float(out["gen_online"][-1]), float(out["gen_online"][0]), 0.5


def _jfs_time(**kw):
    return start_protocol(variant=2, n_starts=1, **kw).times[0]


def p_r3_5a():
    return (_jfs_time(t_amb=258.15, alt=3260.0, soc=0.2), _jfs_time(t_amb=258.15, alt=3260.0, soc=0.9), 0.05)


def p_r3_5b():
    return (
        _jfs_time(t_amb=248.15, alt=3260.0, soc=0.85),
        _jfs_time(t_amb=268.15, alt=3260.0, soc=0.85),
        0.05,
    )


def p_r3_5c():
    return (
        _jfs_time(t_amb=isa(0.0)[0], alt=0.0, soc=1.0),
        _jfs_time(t_amb=isa(4000.0)[0], alt=4000.0, soc=1.0),
        0.05,
    )


def _bleed(p3, w_bp=0.0):
    m, st = module(UtilitiesConfig())
    st, out = run(m, st, inputs(3 * 240, p3=p3, t3=460.0, w_bp=w_bp, alt=3000.0))
    return _last(out, "bleed_extract")


def p_r3_6():
    return _bleed(2.0e5), _bleed(2.8e5), 1e-4


def p_r3_7():
    return _bleed(6.0e5, 0.0), _bleed(6.0e5, 0.05), 1e-5


def _slope(fx, fz):
    m, st = module(UtilitiesConfig())
    st, _ = run(m, st, inputs(10 * 240, fspec=(fx, 0.0, fz)))
    return m.truth_view(st)["fuel_slope"]


def p_r3_8a():
    return _slope(0.1 * G0, -G0), _slope(0.6 * G0, -G0), 1e-3


def p_r3_8b():
    return _slope(0.4 * G0, -G0), _slope(0.4 * G0, -3.0 * G0), 1e-3


def p_r3_8c():
    """1,150 kg internal fuel, max AB: a 10 deg climb (speed builds, surface flattens) vs a 45 deg zoom; 45 s
    each after a 10 s settle (TEST FIXTURE point-mass manoeuvre, as in the F1A stall test). Driven: true F1
    + F2."""
    from test_utilities_support import T_MAX_AB, WF_MAX_AB, WF_MIL, climb_profile

    cap = np.asarray(PS.value("tank_cap")) * PS.value("fuel_rho_15")
    fuel = np.zeros(L.N_TANKS)
    fuel[L.T_F1] = cap[L.T_F1]
    fuel[L.T_F2] = 0.98 * cap[L.T_F2]
    fuel[L.T_F1A] = 1150.0 - fuel[L.T_F1] - fuel[L.T_F2]
    res = []
    for theta in (10.0, 45.0):
        m, st = module(UtilitiesConfig(fuel=tuple(fuel), f1a_mod=0))
        st, _ = run(m, st, inputs(2400, wf=WF_MIL, fspec=(0.25 * G0, 0.0, -G0)))
        fs, tas = climb_profile(theta, T_MAX_AB, seconds=45.0)
        st, _ = run(m, st, inputs(45 * 240, wf=WF_MAX_AB, fspec=fs, tas=tas))
        res.append(m.truth_view(st)["feed_mass"])
    return res[0], res[1], 20.0


def p_r3_9a():
    """Low vs high engine fuel flow through the hydraulic heat exchanger (60 s at 30 % Q demand)."""
    lo = _last(_hyd(0.95, 0.3 * Q, seconds=60.0, wf=0.1)[2], "hyd_t")
    hi = _last(_hyd(0.95, 0.3 * Q, seconds=60.0, wf=3.0)[2], "hyd_t")
    return lo, hi, 0.01


def p_r3_9c():
    vals = []
    for wf in (0.1, 2.0):
        m, st = module(UtilitiesConfig(soak_temp=300.0))
        st, out = run(m, st, inputs(30 * 240, wf=wf, demand=3e-4))
        vals.append(float(out["fuel_inlet_t"][-1, 0]))
    return vals[0], vals[1], 0.01


def _fuel_t(t_s):
    m, st = module(UtilitiesConfig(soak_temp=290.0))
    st, _ = run(m, st, inputs(300 * 240, alt=0.0, t_s=t_s, mach=0.0, tas=0.0, wow=(1, 1, 1), wf=0.1))
    return float(st["f"][L.F_FUEL_T])


def p_r3_9b():
    return _fuel_t(280.0), _fuel_t(315.0), 1e-3


def _brake(pw):
    m, st = module(UtilitiesConfig())
    st, out = run(
        m, st, inputs(20 * 240, wow=(1, 1, 1), tas=50.0, wheel=(176.0, 176.0), pbrk=(pw, pw), alt=0.0)
    )
    return out


def p_r3_10a():
    return _last(_brake(1e5), "brake_t"), _last(_brake(4e5), "brake_t"), 1.0


def p_r3_10b():
    return _last(_brake(1e5), "brake_wear"), _last(_brake(4e5), "brake_wear"), 1e-9


def _touchdown(fuel_kg):
    cap = np.asarray(PS.value("tank_cap")) * PS.value("fuel_rho_15")
    fuel = np.minimum(cap * fuel_kg / cap[:5].sum(), cap)
    fuel[5:] = 0.0
    m, st = module(UtilitiesConfig(fuel=tuple(fuel)))
    st, _ = run(m, st, inputs(2, wow=(0, 0, 0), tas=75.0))
    st, out = run(m, st, inputs(2, wow=(1, 1, 1), tas=75.0, wheel=(264.0, 264.0)))
    return out


def p_r3_10c():
    return _last(_touchdown(500.0), "tyre_wear"), _last(_touchdown(2400.0), "tyre_wear"), 1e-6


def p_r3_11():
    m, st = module(UtilitiesConfig())
    lo = _last(run(m, st, inputs(240, wow=(1, 1, 1), tas=0.0))[1], "pto_power")
    hi = _last(run(m, st, inputs(240, wow=(0, 0, 0), tas=0.0))[1], "pto_power")
    return lo, hi, 100.0


def p_r3_12a():
    return float(precharge(P, 0.0, 253.15, 101325.0)), float(precharge(P, 0.0, 303.15, 101325.0)), 1.0


def p_r3_12b():
    return _swash(250.0), _swash(300.0), 1e-5


def p_r3_12c():
    return float(battery_r(P, 0.03, 253.15)), float(battery_r(P, 0.03, 303.15)), 1e-6


def p_r3_13a():
    h = np.zeros(L.N_HEALTH)
    h[L.H_FILTER] = 0.8
    return _last(_hyd(0.95, 0.6 * Q)[2], "hyd_p"), _last(_hyd(0.95, 0.6 * Q, health=h)[2], "hyd_p"), 0.5 * BAR


def _phx(foul):
    h = np.zeros(L.N_HEALTH)
    h[L.H_HX_FOUL] = foul
    m, st = module(UtilitiesConfig())
    st, out = run(m, st, inputs(20 * 240, p3=6.0e5, t3=700.0, health=h))
    return float(out["ecs_t"][-1, L.E_PHX])


def p_r3_13b():
    return _phx(0.0), _phx(0.8), 1.0


def p_n4():
    lo = _hyd(0.9, 1.1 * Q)[2]
    hi = _hyd(0.9, 0.2 * Q)[2]
    assert np.allclose(hi["hyd_dp_avail"] + PS.value("hyd_p_ret"), hi["hyd_p"])
    return _last(lo, "hyd_dp_avail"), _last(hi, "hyd_dp_avail"), 1 * BAR


def p_n9():
    m, st = module(UtilitiesConfig(engine_running=False))
    _, out0 = m.step_block(st, ground_inputs(0.1 * N2_100, 288.15, 101325.0), np.array([0]), 1 / 240)
    st, _ = m.on_event(st, event("util.jfs_start"), 0)
    p_eng = []
    for k in range(20 * 240):
        st, out = m.step_block(st, ground_inputs(0.1 * N2_100, 288.15, 101325.0), np.array([k]), 1 / 240)
        if int(st["i"][L.I_JFS_MODE]) == 3:
            p_eng.append(float(out["pto_power"][0, 0]))
    return float(out0["pto_power"][0, 0]), min(p_eng), 100.0


def p_n13():
    m, st = module(UtilitiesConfig())
    lo = _last(run(m, st, inputs(240, p3=0.99 * 70108.0, t3=290.0, alt=3000.0))[1], "bleed_extract")
    hi = _last(run(m, st, inputs(240, p3=1.01 * 70108.0, t3=290.0, alt=3000.0))[1], "bleed_extract")
    return lo, hi, 0.5 * PS.value("ecs_m_aux")


def p_n14():
    vals = []
    for wow in ((1, 1, 1), (0, 0, 0)):
        m, st = module(UtilitiesConfig())
        st, out = run(m, st, inputs(120 * 240, wow=wow, tas=0.0, p3=4e5, t3=600.0))
        vals.append(float(out["ecs_t"][-1, L.E_AV]))
    return vals[0], vals[1], 0.1


def p_n15():
    vals = []
    for wf in (0.2, 2.0):
        m, st = module(UtilitiesConfig())
        st, out = run(m, st, inputs(30 * 240, wf=wf))
        vals.append(float(out["mass"][-1]))
    return vals[0], vals[1], 1.0


def p_n23():
    """Same braked stop with the brake system pressurised (95 % N2) vs depressurised (engine off): pressure
    available to the brakes."""
    vals = []
    for n2f in (0.0, 0.95):
        m, st = module(UtilitiesConfig(engine_running=n2f > 0))
        st, out = run(
            m,
            st,
            inputs(480, n2f=n2f, wow=(1, 1, 1), tas=40.0, alt=0.0, pbrk=(6e5, 6e5), wheel=(140.0, 140.0)),
        )
        vals.append(float(out["brake_p"][-1, 0]))
    return vals[0], vals[1], 1e5


PROBES = {
    "R3-1a": p_r3_1a, "R3-1b": p_r3_1b, "R3-1c": p_r3_1c,
    "R3-2a": p_r3_2a, "R3-2b": p_r3_2b, "R3-2c": p_r3_2c,
    "R3-3a": p_r3_3a, "R3-3b": p_r3_3b, "R3-4": p_r3_4,
    "R3-5a": p_r3_5a, "R3-5b": p_r3_5b, "R3-5c": p_r3_5c,
    "R3-6": p_r3_6, "R3-7": p_r3_7,
    "R3-8a": p_r3_8a, "R3-8b": p_r3_8b, "R3-8c": p_r3_8c,
    "R3-9a": p_r3_9a, "R3-9b": p_r3_9b, "R3-9c": p_r3_9c,
    "R3-10a": p_r3_10a, "R3-10b": p_r3_10b, "R3-10c": p_r3_10c,
    "R3-11": p_r3_11,
    "R3-12a": p_r3_12a, "R3-12b": p_r3_12b, "R3-12c": p_r3_12c,
    "R3-13a": p_r3_13a, "R3-13b": p_r3_13b,
    "N4": p_n4, "N9": p_n9, "N13": p_n13, "N14": p_n14, "N15": p_n15, "N23": p_n23,
}  # fmt: skip


@pytest.mark.integration
def test_every_table_edge_has_a_probe_and_every_report_row_is_covered():
    ids = {e.edge_id for e in TABLE}
    assert ids == set(PROBES), (sorted(ids - set(PROBES)), sorted(set(PROBES) - ids))
    rows = {e.source.split(" ")[2] for e in TABLE if e.source.startswith("R§3 row")}
    assert rows == {str(n) for n in range(1, 14)}  # all 13 rows of the report §3 coupling table


def check_sign(sign: str, lo: float, hi: float, tol: float) -> bool:
    if sign == "+":
        return hi > lo + tol
    if sign == "-":
        return hi < lo - tol
    return abs(hi - lo) <= tol


@pytest.mark.integration
def test_sign_checker_rejects_wrong_signs():
    """Negative control: the checker fails a reversed or flat response."""
    assert (
        check_sign("+", 1.0, 2.0, 0.1)
        and not check_sign("+", 2.0, 1.0, 0.1)
        and not check_sign("+", 1.0, 1.05, 0.1)
    )
    assert check_sign("-", 2.0, 1.0, 0.1) and not check_sign("-", 1.0, 2.0, 0.1)
    assert check_sign("0", 1.0, 1.05, 0.1) and not check_sign("0", 1.0, 1.5, 0.1)


@pytest.mark.integration
@pytest.mark.parametrize("edge", TABLE, ids=[e.edge_id for e in TABLE])
def test_coupling_sign(edge):
    lo, hi, tol = PROBES[edge.edge_id]()
    assert check_sign(edge.sign, lo, hi, tol), f"{edge.edge_id} {edge.driver} -> {edge.driven}: {lo} -> {hi}"
