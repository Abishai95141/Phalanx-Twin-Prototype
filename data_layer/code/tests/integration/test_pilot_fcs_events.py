"""AD-47 (A-W1.1-47): M04 toe brakes (``pilot.brake_cmd``), spin recognition -> ``fcs.spin_mode``,
FCS caution -> ``fcs.reset``; M02 sortie preparation -> ``af.ground_elevation`` (M06) and
``fcs.pbit_start`` (M05). The real M05 and M06 accept the events. Sample: one sortie plan (with a
run-up), single ticks per phase for the brake law, 2.5 s windows for spin entry and recovery; one seed."""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import numpy as np
import pytest

from phalanx.airframe.analysis import Condition, make_ic, reference_mass_properties, trim
from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.module import Airframe
from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import TRUTH_DT_S, TRUTH_HZ
from phalanx.environment.config import load_env_config
from phalanx.fcs.module import Fcs, FcsIC
from phalanx.pilot import kernel as K
from phalanx.pilot.module import EV_FCS_CAUTION, EV_MONITOR, PilotModule, load_pilot_config
from phalanx.scenario import phases as PH
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.module import EV_SORTIE_START, PLAN_EVENT, ScenarioModule
from phalanx.scenario.plan import S_PHASE
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
CFG = load_pilot_config()
P = CFG.vector
NS = 10**9
T0 = 100 * NS


def _plan():
    keys = RngService(21, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario="ad47"))
    pl = Planner(PARAMS, ENV, FLEET, keys)
    slots, _ = pl.plan_day(FLEET.start + dt.timedelta(days=2))
    plans = (pl.build_sortie(s) for s in slots)
    return next(p for p in plans if PH.RUNUP in p.seg_i[:, S_PHASE])


def _pilot(plan):
    m = PilotModule("pilot", CFG, fcs="fcs", utilities="util")
    m.bind(RngService(3, StreamRegistry(m.streams)).scope(KeyPath.of(scenario="ad47", tail="T", sortie=1)))
    st = m.init(m.params, m.keys)
    st, out = m.on_event(st, Event(T0, PLAN_EVENT, "pilot", plan.to_payload(T0), source="m02"), T0)
    return m, st, out


def _inputs(n, *, gs=0.0, vd=0.0, r=0.0, alt=500.0):
    return {
        "alt": np.full(n, alt),
        "tas": np.full(n, math.hypot(gs, vd)),
        "mach": np.full(n, math.hypot(gs, vd) / 340.0),
        "vel_ned": np.tile([gs, 0.0, vd], (n, 1)),
        "quat": np.tile([1.0, 0.0, 0.0, 0.0], (n, 1)),
        "omega_body": np.tile([0.0, 0.0, r], (n, 1)),
        "nz": np.ones(n),
        "wow": np.ones((n, 3), dtype=np.int64),
        "n2": np.full((n, 1), 1000.0),
    }


def _ticks(t0, n):
    return t0 + (np.arange(n, dtype=np.int64) * NS) // TRUTH_HZ


def _seg_mid(plan, phase):
    ph = plan.seg_i[:, S_PHASE]
    j = int(np.flatnonzero(ph == phase)[0])
    ends = np.append(plan.t_off_ns[1:], plan.t_end_off_ns)
    return T0 + (int(plan.t_off_ns[j]) + int(ends[j])) // 2 // (NS // TRUTH_HZ) * (NS // TRUTH_HZ)


@pytest.mark.integration
def test_toe_brake_law_by_phase():
    plan = _plan()
    m, st, _ = _pilot(plan)
    v_taxi, k, cap, v_on = P[K.P_VTAXI], P[K.P_KWB], P[K.P_WBLAND], P[K.P_VBON]
    cases = [
        (T0 - 10 * NS, 0.0, 1.0),  # parked before the plan
        (_seg_mid(plan, PH.ENGINE_START), 0.0, 1.0),
        (_seg_mid(plan, PH.RUNUP), 0.0, 1.0),  # run-up against the brakes
        (_seg_mid(plan, PH.TAKEOFF), 40.0, 0.0),
    ]
    for t, gs, want in cases:
        st, out = m.step_block(st, _inputs(1, gs=gs), np.array([t], np.int64), TRUTH_DT_S)
        assert out["brake_cmd"].shape == (1, 2) and np.all(out["brake_cmd"][0] == want), (t, gs)
    m2, st2, _ = _pilot(plan)
    t_taxi = _seg_mid(plan, PH.TAXI_OUT)
    _, out = m2.step_block(st2, _inputs(1, gs=v_taxi + 2.0), np.array([t_taxi], np.int64), TRUTH_DT_S)
    assert out["brake_cmd"][0, 0] == pytest.approx(k * 2.0)
    t_l = _seg_mid(plan, PH.LANDING)
    for gs, want in ((v_on + 5.0, 0.0), (v_taxi + 1.0, k * 1.0), (v_taxi + 30.0, cap)):
        m3, st3, _ = _pilot(plan)
        _, out = m3.step_block(st3, _inputs(1, gs=gs), np.array([t_l], np.int64), TRUTH_DT_S)
        assert out["brake_cmd"][0, 1] == pytest.approx(min(want, cap)), gs
    assert m.initial_outputs(st)["brake_cmd"].tolist() == [1.0, 1.0]


@pytest.mark.integration
def test_spin_recognition_selects_and_deselects_the_mode():
    plan = _plan()
    m, st, out = _pilot(plan)
    mon = [e for e in out if e.kind == EV_MONITOR]
    assert len(mon) == 1 and mon[0].t_ns == T0
    t = _seg_mid(plan, PH.TRANSIT) if PH.TRANSIT in plan.seg_i[:, S_PHASE] else _seg_mid(plan, PH.MISSION)
    n = round(2.5 * TRUTH_HZ)
    a = math.radians(60.0)  # inside the DIRECT spin-mode range 57-85 deg
    st, _ = m.step_block(
        st, _inputs(n, gs=30.0 * math.cos(a), vd=30.0 * math.sin(a), r=1.2), _ticks(t, n), TRUTH_DT_S
    )
    assert int(st["i"][K.I_SPIN]) == 1
    t1 = t + n * NS // TRUTH_HZ
    st, ev = m.on_event(st, Event(t1, EV_MONITOR, "pilot"), t1)
    sm = [e for e in ev if e.kind == "fcs.spin_mode"]
    assert len(sm) == 1 and bool(np.asarray(sm[0].payload["on"])) and sm[0].target == "fcs"
    assert [e.t_ns for e in ev if e.kind == EV_MONITOR] == [t1 + NS]  # re-armed
    st, ev = m.on_event(st, Event(t1 + NS, EV_MONITOR, "pilot"), t1 + NS)
    assert not [e for e in ev if e.kind == "fcs.spin_mode"]  # no repeat while the flag is unchanged
    t2 = t1 + 2 * NS
    st, _ = m.step_block(st, _inputs(n, gs=150.0, vd=5.0, r=0.0), _ticks(t2, n), TRUTH_DT_S)
    assert int(st["i"][K.I_SPIN]) == 0
    t3 = t2 + n * NS // TRUTH_HZ
    _, ev = m.on_event(st, Event(t3, EV_MONITOR, "pilot"), t3)
    off = [e for e in ev if e.kind == "fcs.spin_mode"]
    assert len(off) == 1 and not bool(np.asarray(off[0].payload["on"]))


@pytest.mark.integration
def test_fcs_caution_reset_and_real_m05_m06_accept_the_events():
    plan = _plan()
    m, st, _ = _pilot(plan)
    _, ev = m.on_event(st, Event(T0, EV_FCS_CAUTION, "pilot"), T0)
    assert [(e.kind, e.t_ns) for e in ev] == [("fcs.reset", T0 + round(CFG.reset_reaction_s * 1e9))]
    # M02 sortie preparation events (sortie mode)
    m02 = ScenarioModule("m02", PARAMS, ENV, plan=plan, fcs="fcs", airframe="af", t_kernel0_ns=T0)
    m02.bind(RngService(1, StreamRegistry(m02.streams)).scope(KeyPath.of(scenario="ad47")))
    s02 = m02.init(m02.params, m02.keys)
    (boot,) = m02.initial_events()
    assert boot.kind == EV_SORTIE_START
    _, prep = m02.on_event(s02, boot, T0)
    kinds = {e.kind: e for e in prep if e.target in ("fcs", "af")}
    assert set(kinds) == {"fcs.pbit_start", "af.ground_elevation"}
    assert float(np.asarray(kinds["af.ground_elevation"].payload["h"])) == plan.field_elev_m
    # the real M05 (on the ground): PBIT, spin mode on/off, reset
    fcs = Fcs.from_registry("fcs", FcsIC(surf=np.zeros(13), alpha=0.0, mach=0.0, hp=0.0, on_ground=True))
    s5 = fcs.init(fcs.params, None)
    for e in (
        kinds["fcs.pbit_start"],
        Event(T0, "fcs.spin_mode", "fcs", {"tail": plan.tail, "on": True}),
        Event(T0, "fcs.spin_mode", "fcs", {"tail": plan.tail, "on": False}),
        ev[0],
    ):
        s5, _ = fcs.on_event(s5, e, T0)
    # the real M06: ground elevation sets the local ground height (af.hag reference)
    ps = airframe_param_set()
    cfg = build_config(ps, 1)
    m0, cg0, j0 = reference_mass_properties(ps)
    cond = Condition(3000.0, 0.5, m0, cg0, j0)
    ic = make_ic(cfg, cond, trim(cfg, cond, guess=(0.05, 0.0, 3e4)), h_ground=0.0)
    af = Airframe.from_registry("af", ic)
    s6 = af.init(af.params, None)
    s6, _ = af.on_event(s6, kinds["af.ground_elevation"], T0)
    io = af.initial_outputs(s6)
    assert io["hag"] == pytest.approx(io["alt"] - plan.field_elev_m, abs=1e-9)
