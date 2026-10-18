"""M02 kernel module (A7 for M02, plus the order effects API used by W1.8): sortie mode drives the held phase
port at the plan's segment boundaries and hands the plan to its consumers; fleet (usage) mode reproduces the
pure Planner exactly through the event loop; orders take effect at the next planning action; snapshot round
trip mid-scenario.

Sample: one sortie (sortie mode); 7 days of the two-squadron fleet (~250 plans) in usage mode.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import latest_truth_step
from phalanx.environment.config import load_env_config
from phalanx.scenario import phases as P
from phalanx.scenario.config import load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner
from phalanx.scenario.module import PLAN_EVENT, ScenarioModule
from phalanx.scenario.plan import SortiePlan
from phalanx.scenario.streams import STREAMS

ROOT = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
NS = 10**9
DAY_K = 86400 * 240


class PlanSink(ModuleBase):
    """TEST FIXTURE (consumer stand-in for M04/M18): records every received sortie plan."""

    version = "0"
    rate = None
    state_schema = StateSchema(
        "fixture.sink",
        1,
        (
            Field("keys", "<U48", (None,)),
            Field("tails", "<U24", (None,)),
            Field("digest", "<U32", (None,)),
            Field("ab_lights", "<i8", (None,)),
            Field("t0", "<i8", (None,)),
        ),
    )

    def __init__(self, id="sink"):
        super().__init__(id, ParamSet("fixture", {}))

    def init(self, params, keys):
        return {
            "keys": np.zeros(0, "<U48"),
            "tails": np.zeros(0, "<U24"),
            "digest": np.zeros(0, "<U32"),
            "ab_lights": np.zeros(0, np.int64),
            "t0": np.zeros(0, np.int64),
        }

    def initial_outputs(self, state):
        return {}

    @staticmethod
    def digest(plan: SortiePlan) -> str:
        h = hashlib.blake2b(digest_size=16)
        for a in (plan.t_off_ns, plan.seg_f, plan.seg_i, plan.summary.vector()):
            h.update(np.ascontiguousarray(a).tobytes())
        return h.hexdigest()

    def on_event(self, state, event, t):
        assert event.kind == PLAN_EVENT
        plan, t0 = SortiePlan.from_payload(event.payload)
        return {
            "keys": np.append(state["keys"], plan.rng_key).astype("<U48"),
            "tails": np.append(state["tails"], plan.tail).astype("<U24"),
            "digest": np.append(state["digest"], self.digest(plan)).astype("<U32"),
            "ab_lights": np.append(state["ab_lights"], plan.summary.ab_lights),
            "t0": np.append(state["t0"], t0),
        }, []


def fleet_system(days=7, root=0x5C, orders=()):
    fleet = FLEET.__class__(FLEET.name, FLEET.start, days, FLEET.squadrons, FLEET.surge)
    scen = ScenarioModule("scen", PARAMS, ENV, fleet=fleet, plan_targets=("sink",), focus_tail="TJ201")
    s = System(
        [scen, PlanSink()], [], rng=RngService(root, StreamRegistry()), identity=KeyPath.of(scenario="w11")
    )
    w = s.inject(
        s.start(), [*orders, *scen.initial_events()]
    )  # orders queued before the first planning epoch
    return s, scen, w


@pytest.mark.integration
def test_sortie_mode_drives_phase_and_hands_off_the_plan():
    rng = RngService(0x5C, StreamRegistry(STREAMS))
    pl = Planner(PARAMS, ENV, FLEET, rng.scope(KeyPath.of(scenario="w11")))
    slots, _ = pl.plan_day(dt.date(2026, 1, 6))
    plan = pl.build_sortie(slots[0])
    t0 = 5 * NS
    scen = ScenarioModule("scen", PARAMS, ENV, plan=plan, plan_targets=("sink",), t_kernel0_ns=t0)
    s = System(
        [scen, PlanSink()], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="w11")
    )
    w = s.inject(s.start(), scen.initial_events())
    assert int(w.held["scen.epoch_utc_ns"]) == plan.t_start_utc_ns - t0  # AD-38: contract time = epoch + t
    dmap = P.dictionary_map()
    for j in range(plan.n_segments):
        k = latest_truth_step(t0 + int(plan.t_off_ns[j])) + 2
        w, _ = s.run(w, k - w.k)
        assert int(w.held["scen.phase"]) == dmap[int(plan.seg_i[j, 0])], j
    w, _ = s.run(w, latest_truth_step(t0 + plan.t_end_off_ns) + 2 - w.k)
    assert int(w.held["scen.phase"]) == dmap[P.POSTFLIGHT]
    sink = w.states["sink"]
    assert list(sink["keys"]) == [plan.rng_key] and int(sink["t0"][0]) == t0
    assert str(sink["digest"][0]) == PlanSink.digest(plan)


@pytest.mark.integration
def test_fleet_mode_equals_the_pure_planner():
    s, scen, w = fleet_system()
    w, _ = s.run(w, 8 * DAY_K)
    got = sorted(zip(w.states["sink"]["keys"].tolist(), w.states["sink"]["digest"].tolist(), strict=True))
    rng = RngService(0x5C, StreamRegistry(STREAMS))
    pl = Planner(PARAMS, ENV, scen.fleet, rng.scope(KeyPath.of(scenario="w11")))
    want = sorted((p.rng_key, PlanSink.digest(p)) for p in pl.plans_between(FLEET.start, 7))
    assert got == want and len(got) > 100
    assert int(w.held["scen.epoch_utc_ns"]) == FLEET.epoch_utc_ns


@pytest.mark.integration
def test_orders_take_effect_at_the_next_planning_action():
    orders = [
        Event(0, "order.tail_status", "scen", {"tail": "TJ101", "available": 0}),
        Event(0, "order.usage_restriction", "scen", {"tail": "*", "no_ab": 1, "g_limit": 6.0}),
        Event(0, "order.programme_change", "scen", {"squadron": "sqb", "rate_scale": 0.0}),
    ]
    s, scen, w = fleet_system(days=4, orders=orders)
    w, _ = s.run(w, 5 * DAY_K)
    sink = w.states["sink"]
    flights = [
        t for k, t in zip(sink["keys"].tolist(), sink["tails"].tolist(), strict=True) if "-gr-" not in k
    ]
    runs = [t for k, t in zip(sink["keys"].tolist(), sink["tails"].tolist(), strict=True) if "-gr-" in k]
    assert "TJ101" not in flights + runs  # grounded: neither flights nor ground runs
    assert not any(t.startswith("TJ2") for t in flights)  # programme change: squadron B does not fly
    assert any(t.startswith("TJ2") for t in runs)  # ... but its maintenance ground runs continue
    assert len(set(flights)) > 5 and int(np.sum(sink["ab_lights"])) == 0  # no-AB restriction
    st = w.states["scen"]
    assert int(st["unavail"][list(scen.tails).index("TJ101")]) == 1


@pytest.mark.fork
def test_snapshot_round_trip_mid_scenario():
    s, _, w = fleet_system(days=5)
    w_ref, _ = s.run(w, 5 * DAY_K)
    s1, _, w1 = fleet_system(days=5)
    w1, _ = s1.run(w1, 2 * DAY_K + 37)
    s2, _, _ = fleet_system(days=5)
    w2 = restore(s2, snapshot(s1, w1))
    w2, _ = s2.run(w2, 5 * DAY_K - w2.k)
    assert snapshot(s2, w2) == snapshot(s, w_ref)


@pytest.mark.unit
def test_mode_guard():
    with pytest.raises(ContractError):
        ScenarioModule("scen", PARAMS, ENV)
