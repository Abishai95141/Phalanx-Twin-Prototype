"""M04 -> M09 utility events (AD-44 catalogue; A-W1.1-46): scheduled from the sortie plan, timed on the
plan's segments, and accepted by the real M09 (JFS cranks then coasts on abort, chute deployed then
jettisoned, stores released, extinguisher fired). Sample: one ground-attack sortie (dive passes), one
non-attack sortie, one ground run; one root seed."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.environment.config import load_env_config
from phalanx.pilot.kernel import I_STARTED
from phalanx.pilot.module import EV_FIRE_WARNING, EV_START_CHECK, PilotModule, load_pilot_config
from phalanx.scenario import phases as PH
from phalanx.scenario.config import GROUND_ATTACK, P_DIVE, load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Overrides, Planner
from phalanx.scenario.module import PLAN_EVENT
from phalanx.scenario.plan import S_PHASE, S_PRIM
from phalanx.scenario.streams import STREAMS
from phalanx.utilities import UtilitiesConfig, load_m09_params
from phalanx.utilities import layout as UL
from phalanx.utilities.jfs import JFS_COAST, JFS_CRANK
from phalanx.utilities.module import Utilities

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
CFG = load_pilot_config()
T0 = 1_000 * 10**9


def _plans():
    keys = RngService(9, StreamRegistry(STREAMS)).scope(KeyPath.of(scenario="m04util"))
    pl = Planner(PARAMS, ENV, FLEET, keys)
    d = FLEET.start + dt.timedelta(days=1)
    slots, runs = pl.plan_day(d)
    attack = pl.build_sortie(slots[0], Overrides(mission={slots[0].key: GROUND_ATTACK}))
    other = next(p for p in (pl.build_sortie(s) for s in slots[1:]) if p.mission_type != GROUND_ATTACK)
    return attack, other, pl.build_ground_run(runs[0])


def _pilot():
    m = PilotModule("pilot", CFG, utilities="util")
    m.bind(RngService(3, StreamRegistry(m.streams)).scope(KeyPath.of(scenario="m04util", tail="T", sortie=1)))
    return m, m.init(m.params, m.keys)


def _load(plan):
    m, st = _pilot()
    ev = Event(T0, PLAN_EVENT, "pilot", plan.to_payload(T0), source="m02")
    st, out = m.on_event(st, ev, T0)
    return m, st, out


@pytest.mark.integration
def test_events_follow_the_plan_segments():
    attack, other, run = _plans()
    for plan in (attack, other, run):
        _, _, out = _load(plan)
        ph = plan.seg_i[:, S_PHASE]
        offs = np.asarray(plan.t_off_ns)
        ends = np.append(offs[1:], plan.t_end_off_ns)
        kinds = [e.kind for e in out]
        j_st = int(np.flatnonzero(ph == PH.ENGINE_START)[0])
        start = next(e for e in out if e.kind == "util.jfs_start")
        check = next(e for e in out if e.kind == EV_START_CHECK)
        assert start.t_ns == T0 + offs[j_st] and check.t_ns == T0 + ends[j_st] and check.target == "pilot"
        assert all(str(np.asarray(e.payload["tail"])) == plan.tail for e in out if e.target == "util")
        if plan.chute:
            dep = next(e for e in out if e.kind == "util.chute_deploy")
            jet = next(e for e in out if e.kind == "util.chute_jettison")
            j_l = int(np.flatnonzero(ph == PH.LANDING)[-1])
            j_t = int(np.flatnonzero(ph == PH.TAXI_IN)[0])
            assert dep.t_ns == T0 + offs[j_l] < jet.t_ns == T0 + offs[j_t]
            assert not bool(np.asarray(dep.payload["emergency"]))
        else:
            assert "util.chute_deploy" not in kinds
        dives = np.flatnonzero(plan.seg_i[:, S_PRIM] == P_DIVE)
        rel = [e for e in out if e.kind == "util.store_release"]
        if plan.mission_type == GROUND_ATTACK:
            assert dives.size and len(rel) == min(dives.size, len(CFG.release_stations))
            assert [int(np.asarray(e.payload["station"])) for e in rel] == list(
                CFG.release_stations[: len(rel)]
            )
            assert [e.t_ns for e in rel] == [T0 + int(ends[j]) for j in dives[: len(rel)]]
        else:
            assert not rel
    assert attack.chute and not run.chute  # flights stream the chute (A-W1.1-35); ground runs never land


@pytest.mark.integration
def test_start_check_and_fire_warning():
    attack, _, _ = _plans()
    m, st, out = _load(attack)
    check = next(e for e in out if e.kind == EV_START_CHECK)
    _, hung = m.on_event(st, check, check.t_ns)  # the kernel never saw N2 reach light-off
    assert [e.kind for e in hung] == ["util.jfs_abort"]
    ok = dict(st)
    ok["i"] = np.array(st["i"], copy=True)
    ok["i"][I_STARTED] = 1
    assert m.on_event(ok, check, check.t_ns)[1] == []
    t = T0 + 600 * 10**9
    _, fire = m.on_event(st, Event(t, EV_FIRE_WARNING, "pilot", {}, source="m14"), t)
    assert [(e.kind, e.t_ns) for e in fire] == [
        ("util.fire_extinguish", t + round(CFG.fire_reaction_s * 1e9))
    ]


@pytest.mark.integration
def test_real_m09_accepts_the_events():
    attack, _, _ = _plans()
    m, st, out = _load(attack)
    check = next(e for e in out if e.kind == EV_START_CHECK)
    out = [e for e in out if e.target == "util"] + m.on_event(st, check, check.t_ns)[1]
    out.append(m.on_event(st, Event(T0, EV_FIRE_WARNING, "pilot", {}, source="m14"), T0)[1][0])
    ps = load_m09_params()
    stores = (0.0, 0.0, 113.0, 113.0, 113.0)
    m09 = Utilities("util", ps, config=UtilitiesConfig(stores=stores, engine_running=False))
    m09.bind(
        RngService(4, StreamRegistry(m09.streams)).scope(KeyPath.of(scenario="m04util", tail="T", sortie=1))
    )
    s9 = m09.init(ps, m09.keys)
    modes = []
    for e in sorted(out, key=lambda e: e.t_ns):
        s9, _ = m09.on_event(s9, e, e.t_ns)
        modes.append((e.kind, int(s9["i"][UL.I_JFS_MODE])))
    assert ("util.jfs_start", JFS_CRANK) in modes and ("util.jfs_abort", JFS_COAST) in modes
    assert int(s9["i"][UL.I_CHUTE]) == 2 and int(s9["i"][UL.I_CHUTE_N]) == 1  # deployed, then jettisoned
    released = [s for s in range(UL.N_STORE) if s9["f"][UL.F_STORE_M + s] == 0.0 and stores[s] > 0]
    n_rel = sum(e.kind == "util.store_release" for e in out)
    assert len(released) == n_rel > 0
    assert int(s9["i"][UL.I_EXT_CHARGED]) == 0  # the extinguisher bottle was fired
