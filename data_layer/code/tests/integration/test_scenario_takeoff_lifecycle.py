"""AD-48.2 (W2.1c): the sortie lifecycle reaches M10 / M11 / M14 through catalogued events.

M02 emits ``ops.takeoff`` at the actual take-off (sortie mode: the plan's first airborne segment; operations
mode: the committed sortie's take-off, never for a ground-aborted one) and ``ops.sortie_done`` at engine
cut-off. They replace the internal telemetry-mode hooks (``faults.sortie_start`` / ``faults.sortie_end``,
``monitor.sortie_start`` / ``monitor.sortie_end``):

- M11 starts the sortie at take-off with onsets over the planned airborne window and the plan's drivers -
  **bitwise the same state** as the W1 hook with the same window and drivers - and ends it at sortie-done;
- M14 powers up at take-off when no power-up hook ran (PROXY A-W2.1c-4), and at sortie-done writes the final
  LUIs and the OAC counters it has a source for (no false zeros), then powers down;
- M10 holds the airborne sortie open from take-off to its usage summary; maintenance on the aircraft while
  airborne, a summary of another sortie, or a second take-off are protocol errors.

Negative controls: a double start of M11 (hook + ops.takeoff), M14 sortie-done without a start, the M10
guards. Sample: one planned sortie (sortie mode, one seed); the operations-mode ground abort uses 1 squadron
of 2 tails over 1 flying day.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, ParamSet
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.core.state import Field, StateSchema
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.environment.config import load_env_config
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.health.usage import summary_payload, usage_from_summary
from phalanx.maintenance.world import FleetSpec, OpsTargets
from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params
from phalanx.monitoring.module import KIND_COUNTER
from phalanx.scenario.config import FleetScenario, load_fleet_scenario, load_scenario_params
from phalanx.scenario.generator import Planner, airborne_window_ns
from phalanx.scenario.module import EV_DAY, TAKEOFF_KEYS, OpsLink, ScenarioModule
from phalanx.scenario.streams import STREAMS

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
CAT = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]
PARAMS = load_scenario_params()
ENV = load_env_config()
FLEET = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
D = load_dictionary()
NS = 10**9
T0 = 5 * NS


def _plan():
    rng = RngService(0x5C, StreamRegistry(STREAMS))
    pl = Planner(PARAMS, ENV, FLEET, rng.scope(KeyPath.of(scenario="w21c")))
    slots, _ = pl.plan_day(dt.date(2026, 1, 6))
    return pl.build_sortie(slots[0])


PLAN = _plan()
TAIL = PLAN.tail
SERIAL = PLAN.engine_serials[0]


def _m10():
    cfg = HealthConfig((SERIAL,), sensor_bias_channels(D), "m11", monitor_target="m14", tail_no=TAIL)
    return HealthModule("m10", load_health_params(), config=cfg, identity={"tail": TAIL})


def _m11(stochastic=True):
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"health": "m10", "monitoring": "m14"},
        (SERIAL,),
        sensor_bias_channels(D),
        realise_physics_edges=False,  # telemetry mode
        stochastic=stochastic,
        tail_no=TAIL,
    )
    return FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": TAIL})


def _m14():
    p = load_monitoring_params()
    cfg = MonitoringConfig.from_dictionary(D, load_code_table(D, p), (SERIAL,), regime="mature", tail_no=TAIL)
    return MonitoringModule("m14", p, config=cfg, identity={"tail": TAIL})


def _world():
    scen = ScenarioModule(
        "m02",
        PARAMS,
        ENV,
        plan=PLAN,
        t_kernel0_ns=T0,
        takeoff_targets=("m10", "m11", "m14"),
        done_targets=("m11", "m14"),
    )
    s = System(
        [scen, _m10(), _m11(), _m14()],
        [],
        rng=RngService(0x21C, StreamRegistry()),
        identity=KeyPath.of(scenario="w21c"),
    )
    return s, s.inject(s.start(), scen.initial_events())


def _run_to(s, w, t):
    k = -((-t * 240) // NS)
    return s.run(w, k - w.k)


OFF_TO, OFF_LDG = airborne_window_ns(PLAN)
T_TO, T_LDG, T_END = T0 + OFF_TO, T0 + OFF_LDG, T0 + int(PLAN.t_end_off_ns)


def _telemetry_summary(t):
    """The harness's telemetry-mode usage summary (the plan's usage stands in for the truth-derived one)."""
    doc = {
        "sortie_id": PLAN.sortie_id,
        "tail_no": TAIL,
        "flight_hours": PLAN.summary.flight_s / 3600.0,
        "engine_cycles": PLAN.summary.tac,
        "engine_starts": PLAN.summary.starts,
        "landings": PLAN.summary.landings,
        "time_at_temp_s": PLAN.summary.irp_s,
        "max_nz": 3.0,
        "ab_time_s": PLAN.summary.ab_s,
        "dust_index": 0.0,
        "salt_index": 0.0,
    }
    u = usage_from_summary(doc, load_health_params(), 1)
    return Event(t, "usage.sortie_summary", "m10", plain_payload(summary_payload(u, TAIL)), source="harness")


@pytest.fixture(scope="module")
def flown():
    s, w = _world()
    w, tr_to = _run_to(s, w, T_TO + NS // 100)
    at_to = {k: w.states[k] for k in ("m10", "m11", "m14")}
    w = s.inject(w, [_telemetry_summary(T_END + 1)])
    w, tr_end = _run_to(s, w, T_END + 2 * NS)
    events = [e for _, e in tr_to.dispatched] + [e for _, e in tr_end.dispatched]
    return s, w, at_to, events


def test_takeoff_and_sortie_done_reach_their_catalogued_consumers(flown):
    _, _, _, events = flown
    to = [e for e in events if e.kind == "ops.takeoff"]
    assert sorted(e.target for e in to) == ["m10", "m11", "m14"]
    assert all(e.t_ns == T_TO for e in to) and T0 < T_TO < T_LDG < T_END
    d = read_payload(to[0].payload)
    assert set(CAT["ops.takeoff"]["payload"]) == set(TAKEOFF_KEYS) <= set(d)
    assert d["sortie_id"] == PLAN.sortie_id and d["t_landing"] - d["t_takeoff"] == OFF_LDG - OFF_TO
    assert d["ab_lights"] == PLAN.summary.ab_lights and d["engine_starts"] == PLAN.summary.starts
    done = [e for e in events if e.kind == "ops.sortie_done"]
    assert sorted(e.target for e in done) == ["m11", "m14"] and all(e.t_ns == T_END for e in done)
    assert set(CAT["ops.sortie_done"]["payload"]) <= set(read_payload(done[0].payload))


def test_m11_starts_at_takeoff_exactly_as_the_w1_hook_and_ends_at_sortie_done(flown):
    """The ops.takeoff path gives the bitwise-same M11 state as faults.sortie_start with the same window and
    drivers; the flight hours of ops.sortie_done advance the latent clocks."""
    _, w, at_to, _ = flown
    st = at_to["m11"]
    assert int(st["sortie_open"]) == 1 and str(st["sortie_id"]) == PLAN.sortie_id
    hook = System([_m11()], [], rng=RngService(0x21C, StreamRegistry()), identity=KeyPath.of(scenario="w21c"))
    win = (OFF_LDG - OFF_TO) / 1e9
    pay = {
        "sortie_id": PLAN.sortie_id,
        "duration_s": win,
        "window_s": win,
        "ab_lights": float(PLAN.summary.ab_lights),
        "starts": float(PLAN.summary.starts),
        "landings": float(PLAN.summary.landings),
        "dust": _dust(),
    }
    hw = hook.inject(hook.start(), [Event(T_TO, "faults.sortie_start", "m11", pay)])
    hw, _ = _run_to(hook, hw, T_TO + NS // 100)
    for k in st:
        assert np.array_equal(np.asarray(hw.states["m11"][k]), np.asarray(st[k])), k
    end = w.states["m11"]
    assert int(end["sortie_open"]) == 0
    assert float(end["fh_s"]) == pytest.approx(PLAN.summary.flight_s, abs=1e-6)


def _dust() -> float:
    from phalanx.scenario.generator import exposure

    exp_h, dust = exposure(PARAMS, PLAN)
    return exp_h * dust


def test_m14_powers_up_at_takeoff_and_writes_sourced_counters_at_sortie_done(flown):
    _, w, at_to, _ = flown
    assert int(at_to["m14"]["clock"][2]) == 1 and str(at_to["m14"]["sortie_id"]) == PLAN.sortie_id
    st = w.states["m14"]
    assert int(st["clock"][2]) == 0  # powered down at engine cut-off
    from phalanx.monitoring.module import _CI

    sel = (st["o_kind"] == KIND_COUNTER) & (st["o_t"] >= T_END)  # at the dispatch frame of sortie-done
    codes = {int(c) for c in st["o_code"][sel]}
    assert _CI["USAGE.FLIGHT_HOURS"] in codes and _CI["USAGE.LANDINGS"] in codes
    fh = float(st["o_incr"][sel & (st["o_code"] == _CI["USAGE.FLIGHT_HOURS"])][0])
    assert fh == pytest.approx(PLAN.summary.flight_s / 3600.0)
    for absent in ("USAGE.AB_LIGHTS", "USAGE.JFS_STARTS.ATTEMPTS", "USAGE.BRAKE_APPLICATIONS.COUNT"):
        assert _CI[absent] not in codes, absent  # no source in ops.sortie_done: no false zero


def test_m10_holds_the_airborne_sortie_until_its_summary(flown):
    _, w, at_to, _ = flown
    assert str(at_to["m10"]["sortie_open"]) == PLAN.sortie_id
    assert str(w.states["m10"]["sortie_open"]) == ""
    assert int(w.states["m10"]["clock"][0]) == 1  # the sortie advanced the health state once


# ------------------------------------------------------------------------------------------ negative controls
def test_m11_double_start_is_refused():
    """faults.sortie_start (M10's usage-mode forwarding) and ops.takeoff for one sortie: a wiring error."""
    s = System([_m11()], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="x"))
    to = {k: 0 for k in TAKEOFF_KEYS} | {
        "sortie_id": "S1",
        "tail_no": TAIL,
        "t_takeoff": NS,
        "t_landing": 9 * NS,
    }
    evs = [
        Event(NS, "faults.sortie_start", "m11", {"sortie_id": "S1", "duration_s": 8.0}),
        Event(NS, "ops.takeoff", "m11", plain_payload(to), source="m02"),
    ]
    with pytest.raises(ContractError, match="one path"):
        _run_to(s, s.inject(s.start(), evs), 2 * NS)


def test_m10_airborne_guards():
    s = System([_m10()], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="x"))
    to = {k: 0 for k in TAKEOFF_KEYS} | {
        "sortie_id": "S1",
        "tail_no": TAIL,
        "t_takeoff": NS,
        "t_landing": 9 * NS,
    }
    w = s.inject(s.start(), [Event(NS, "ops.takeoff", "m10", plain_payload(to), source="m02")])
    w, _ = _run_to(s, w, 2 * NS)
    inst = Event(
        3 * NS, "cfg.install", "m10", plain_payload({"tail": TAIL, "pos": "ENG", "serial": "X", "cls": "ENG"})
    )
    with pytest.raises(ContractError, match="airborne"):
        _run_to(s, s.inject(w, [inst]), 4 * NS)
    other = Event(3 * NS, "ops.takeoff", "m10", plain_payload(to | {"sortie_id": "S2"}), source="m02")
    with pytest.raises(ContractError, match="while sortie"):
        _run_to(s, s.inject(w, [other]), 4 * NS)
    other_tail = Event(3 * NS, "ops.takeoff", "m10", plain_payload(to | {"tail_no": "XX"}), source="m02")
    w2, _ = _run_to(s, s.inject(w, [other_tail]), 4 * NS)  # another tail's take-off is not ours
    assert str(w2.states["m10"]["sortie_open"]) == "S1"


def test_m14_sortie_done_without_a_start_is_refused():
    s = System([_m14()], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="x"))
    done = {k: 0 for k in CAT["ops.sortie_done"]["payload"]} | {"sortie_id": "S1", "tail_no": TAIL}
    ev = Event(NS, "ops.sortie_done", "m14", plain_payload(done), source="m02")
    with pytest.raises(ContractError, match="never started"):
        _run_to(s, s.inject(s.start(), [ev]), 2 * NS)


# ------------------------------------------------------------------------------- operations-mode ground abort
class Recorder(ModuleBase):
    """TEST FIXTURE (stand-in consumer of ops.takeoff): counts the take-offs it receives."""

    version = "0"
    rate = None
    state_schema = StateSchema("fixture.takeoffs", 1, (Field("ids", "<U48", (None,)),))

    def __init__(self, id="rec"):
        super().__init__(id, ParamSet("fixture", {}))

    def init(self, params, keys):
        return {"ids": np.zeros(0, "<U48")}

    def initial_outputs(self, state):
        return {}

    def on_event(self, state, event, t):
        sid = read_payload(event.payload)["sortie_id"]
        return {"ids": np.append(state["ids"], np.array(sid, "<U48"))}, []


def _ops_world():
    sq = FLEET.squadrons[0]
    small = type(sq)(sq.sid, sq.role, sq.base, sq.tails[:2], sq.engine_serials[:2])
    fleet = FleetScenario("w21c_to", dt.date(2026, 1, 6), 1, (small,))
    ids = OpsIds()
    link = OpsLink(m18=ids.m18, health=None, kpi=ids.sink)
    b = OpsOnlyBuilder(
        FleetSpec(fleet.tails(), ("SUL",), (0, 0)),
        fleet.epoch_utc_ns,
        scenario="w21c-to",
        targets=OpsTargets(m21=ids.m21, sink=ids.sink, scenario="m02"),
        ids=ids,
        extra=(
            lambda: ScenarioModule("m02", PARAMS, ENV, fleet=fleet, ops=link, takeoff_targets=("rec",)),
            Recorder,
        ),
    )

    class B:
        epoch_utc_ns, calendar, dict_version, dict_hash = (
            b.epoch_utc_ns,
            b.calendar,
            b.dict_version,
            b.dict_hash,
        )
        scenario = "w21c-to"

        def build(self, root, *, ledger=None):
            return b.build(root, ledger=ledger)

        def initial_events(self):
            return [*b.initial_events(), Event(0, EV_DAY, "m02", {"day": 0}, source="session")]

    B.ids = ids
    return B()


def _launches(events):
    return [(e.t_ns, read_payload(e.payload)) for e in events if e.kind == "ops.launch"]


def test_operations_mode_takeoff_and_no_takeoff_after_a_ground_abort():
    """Every flown sortie of the day gets one ops.takeoff at its take-off; a tail grounded between launch and
    take-off is ground-aborted and its sortie never takes off."""
    b = _ops_world()
    s = OpsSession(b, 0x0D5)
    s.world, tr = s.system.run(s.world, 240 * 86_400)
    events = [e for _, e in tr.dispatched]
    to = [read_payload(e.payload) for e in events if e.kind == "ops.takeoff"]
    done = [read_payload(e.payload) for e in events if e.kind == "ops.sortie_done"]
    assert to and sorted(d["sortie_id"] for d in to) == sorted(d["sortie_id"] for d in done)
    assert all(d["t_takeoff"] < d["t_landing"] for d in to)
    # rerun, grounding the first launched tail one second after its launch (before its take-off)
    t_l, first = _launches(events)[0]
    tko = next(d for d in to if d["sortie_id"] == first["sortie_id"])
    assert tko["t_takeoff"] > t_l + NS
    s2 = OpsSession(b, 0x0D5)
    s2.world = s2.system.inject(
        s2.world, [Event(t_l + NS, "order.tail_status", "m02", {"tail": first["tail_no"], "available": 0})]
    )
    s2.world, tr2 = s2.system.run(s2.world, 240 * 86_400)
    ev2 = [e for _, e in tr2.dispatched]
    aborted = [read_payload(e.payload)["sortie_id"] for e in ev2 if e.kind == "ops.ground_abort"]
    to2 = [read_payload(e.payload)["sortie_id"] for e in ev2 if e.kind == "ops.takeoff"]
    assert aborted == [first["sortie_id"]] and first["sortie_id"] not in to2
