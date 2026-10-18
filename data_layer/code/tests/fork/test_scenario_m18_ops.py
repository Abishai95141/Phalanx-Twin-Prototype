"""M02 (real) against M18 (real) through the AD-44 operations protocol, usage mode with event jump.

The world: the real ScenarioModule in operations mode, the real MaintenanceWorld (M18), OrdersModule (M21) and
record sink from ``phalanx.fork.builder.OpsOnlyBuilder``, plus a TEST FIXTURE stand-in for M10 that stores
the ``usage.sortie_summary`` documents it receives (no health model). It shows the protocol end to end: the
day's flying task (``kpi.plan``), offers, launches, flights and SORTIE records, and the M18 -> M02 order paths
(GROUND removes a tail from the next offer; RESTRICT_USAGE AB removes afterburner from that tail's sorties;
ASSIGN_SORTIE with 0 sorties removes a tail from a date's programme).

Sample (smoke/integration ladder, stated before running): one squadron of 6 tails at Sulur, 5 days from Monday
2026-01-05 (5 flying days, ~45 sorties), one root seed; one run with orders and one without.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, ParamSet
from phalanx.core.state import Field, State, StateSchema
from phalanx.environment.config import load_env_config
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import read_payload
from phalanx.maintenance.world import FleetSpec, OpsTargets
from phalanx.orders.model import Order
from phalanx.scenario.config import FleetScenario, load_fleet_scenario, load_scenario_params
from phalanx.scenario.module import EV_DAY, OpsLink, ScenarioModule, read_doc

ROOT_DIR = Path(__file__).resolve().parents[2]
PARAMS = load_scenario_params()
ENV = load_env_config()
NS = 10**9
DAY = 86400 * NS
SEED = 0x0D5
N_DAYS = 5
FULL = load_fleet_scenario(ROOT_DIR / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
SQ = FULL.squadrons[0]
SMALL = FleetScenario(
    "m02_m18_smoke",
    dt.date(2026, 1, 5),
    N_DAYS,
    (type(SQ)(SQ.sid, SQ.role, SQ.base, SQ.tails[:6], SQ.engine_serials[:6]),),
)
DOC = StateSchema("fixture.usage_sink", 1, (Field("doc", "|u1", (None,)),))


class UsageSink(ModuleBase):
    """TEST FIXTURE (stand-in for M10): stores every ``usage.sortie_summary`` document it receives."""

    version = "0"
    rate = None
    state_schema = DOC

    def __init__(self, id: str = "m10") -> None:
        super().__init__(id, ParamSet("fixture.usage_sink", {}))

    def init(self, params, keys) -> State:
        return {"doc": np.frombuffer(b"[]", dtype=np.uint8).copy()}

    def initial_outputs(self, state):
        return {}

    def on_event(self, state, event, t):
        if event.kind != "usage.sortie_summary":
            return super().on_event(state, event, t)
        rows = json.loads(np.asarray(state["doc"]).tobytes().decode())
        rows.append(read_payload(event.payload))
        return {"doc": np.frombuffer(json.dumps(rows, sort_keys=True).encode(), dtype=np.uint8).copy()}, []


@dataclass
class ScenarioOpsBuilder:
    """WorldBuilder: real M02 (operations mode) + real M18/M21/sink + the usage-sink fixture."""

    fleet: FleetScenario = SMALL
    scenario: str = "m02m18"
    ids: OpsIds = field(default_factory=OpsIds)

    def __post_init__(self) -> None:
        self.epoch_utc_ns = self.fleet.epoch_utc_ns
        tails = self.fleet.tails()
        self.tails = tails
        spec = FleetSpec(tails, ("SUL",), tuple(0 for _ in tails))
        targets = OpsTargets(m21=self.ids.m21, sink=self.ids.sink, scenario="m02", health=None)
        link = OpsLink(m18=self.ids.m18, health="m10", kpi=self.ids.sink)
        self._ops = OpsOnlyBuilder(
            spec,
            self.epoch_utc_ns,
            scenario=self.scenario,
            targets=targets,
            ids=self.ids,
            extra=(
                lambda: ScenarioModule("m02", PARAMS, ENV, fleet=self.fleet, ops=link),
                lambda: UsageSink("m10"),
            ),
        )
        self.calendar = self._ops.calendar
        self.dict_version, self.dict_hash = self._ops.dict_version, self._ops.dict_hash

    def build(self, root, *, ledger=None):
        return self._ops.build(root, ledger=ledger)

    def initial_events(self) -> list[Event]:
        return [*self._ops.initial_events(), Event(0, EV_DAY, "m02", {"day": 0}, source="session")]


def _usage(s: OpsSession) -> list[dict]:
    return json.loads(np.asarray(s.world.states["m10"]["doc"]).tobytes().decode())


def _sorties(s: OpsSession) -> list[dict]:
    return [r for r in s.records("maint.records") if r["record_type"] == "SORTIE"]


def _local_date(b: ScenarioOpsBuilder, t_utc_ns: int) -> str:
    return dt.datetime.fromtimestamp(t_utc_ns / NS, tz=dt.UTC).date().isoformat()


@pytest.fixture(scope="module")
def baseline():
    b = ScenarioOpsBuilder()
    s = OpsSession(b, SEED)
    s.run_until(N_DAYS * DAY)
    return b, s


@pytest.mark.fork
def test_sorties_are_offered_launched_flown_and_recorded(baseline):
    b, s = baseline
    doc = read_doc(s.world.states["m02"])
    n = doc["n"]
    assert n["offers"] == N_DAYS  # Monday-Friday: one offer per flying day
    assert n["launched"] > 20, n
    assert n["flown"] + n["denied"] + len(doc["pending"]) == n["launched"]
    assert doc["pending"] == {}  # every committed sortie ended inside the window
    recs = _sorties(s)
    assert len(recs) == n["flown"]  # M18 wrote one SORTIE record per flown sortie (0.5 h after landing)
    usage = {u["sortie_id"]: u for u in _usage(s) if not u["ground_run"]}
    assert set(usage) == {r["sortie_id"] for r in recs}
    for r in recs:
        u = usage[r["sortie_id"]]
        assert r["tail_no"] == u["tail_no"] in b.tails
        assert r["flight_hours"] == pytest.approx(u["flight_hours"], abs=1.0 / 3600)
        assert r["engine_cycles"] == pytest.approx(u["engine_cycles"])  # TAC
        assert r["t_close"] > r["t_open"]
        assert 0.25 <= r["flight_hours"] <= 2.5
    kpi = s.records("kpi.plan")
    assert len(kpi) == N_DAYS and all(k["planned_fh"] > 0 for k in kpi)
    flown_fh = sum(r["flight_hours"] for r in recs)
    task_fh = sum(k["planned_fh"] for k in kpi)
    assert 0.3 < flown_fh / task_fh <= 1.0 + 1e-9, (flown_fh, task_fh)


@pytest.mark.fork
def test_usage_summary_carries_the_catalogued_drivers(baseline):
    from phalanx.scenario.ports import EVENTS_OUT

    _, s = baseline
    rows = _usage(s)
    assert rows and any(r["ground_run"] for r in rows)
    need = set(EVENTS_OUT["usage.sortie_summary"])
    for r in rows:
        assert need <= set(r)
        assert r["dust_index"] >= 0 and r["salt_index"] == 0.0  # Sulur is inland (A-W1.1-34)
        assert r["time_at_temp_s"] >= r["ab_time_s"] >= 0
        assert r["max_nz"] >= 1.0
    flights = [r for r in rows if not r["ground_run"]]
    assert all(r["chute_streamed"] == 1 for r in flights)  # one full-stop landing each (A-W1.1-35)


@pytest.mark.fork
def test_m18_orders_reach_the_programme(baseline):
    """GROUND -> the tail leaves the next offers; RESTRICT_USAGE AB -> no AB on its later sorties;
    ASSIGN_SORTIE 0 -> no sorties for the tail on that date. Compared with the order-free baseline run."""
    b = ScenarioOpsBuilder()
    s = OpsSession(b, SEED)
    t_ep = b.calendar.next_epoch(1 * NS)
    s.run_until(t_ep)
    ep = b.epoch_utc_ns + t_ep
    g_tail, r_tail, a_tail = b.tails[0], b.tails[1], b.tails[2]
    d_assign = "2026-01-08"
    res = s.submit(
        [
            Order("G-1", "H", "HUMAN", ep, ep, "GROUND", {"reason": "test"}, target_tail_no=g_tail),
            Order("R-1", "H", "HUMAN", ep, ep, "RESTRICT_USAGE", {"limit": "AB"}, target_tail_no=r_tail),
            Order(
                "A-1",
                "H",
                "HUMAN",
                ep,
                ep,
                "ASSIGN_SORTIE",
                {"date": d_assign, "sorties": 0},
                target_tail_no=a_tail,
            ),
        ]
    )
    assert all(r.verdict == "ACCEPTED" for r in res), res
    s.run_until(N_DAYS * DAY)
    t_exec = b.epoch_utc_ns + t_ep
    recs = _sorties(s)
    later = [r for r in recs if r["t_open"] > t_exec + DAY]
    assert later and not [r for r in later if r["tail_no"] == g_tail]  # grounded: never offered again
    assert not [r for r in recs if r["tail_no"] == a_tail and _local_date(b, r["t_open"]) == d_assign]
    usage = [u for u in _usage(s) if u["tail_no"] == r_tail and not u["ground_run"]]
    after = [u for u in usage if u["t_end"] > t_ep + DAY]
    assert after and all(u["ab_time_s"] == 0.0 for u in after)
    # the baseline (no orders) flies the assigned tail on that date and uses AB on the restricted tail
    _, base = baseline
    r0 = _sorties(base)
    assert [r for r in r0 if r["tail_no"] == a_tail and _local_date(b, r["t_open"]) == d_assign]
    u0 = [
        u for u in _usage(base) if u["tail_no"] == r_tail and not u["ground_run"] and u["t_end"] > t_ep + DAY
    ]
    assert any(u["ab_time_s"] > 0 for u in u0)


@pytest.mark.fork
def test_snapshot_mid_day_restores_bitwise(baseline):
    """Snapshot at 04:00 UTC on day 2 (wave-1 sorties in flight, launches pending), restore, continue: the M02
    state and the SORTIE records equal the uninterrupted run's."""
    _, full = baseline
    b = ScenarioOpsBuilder()
    s = OpsSession(b, SEED)
    s.run_until(2 * DAY + 4 * 3600 * NS)
    assert read_doc(s.world.states["m02"])["pending"], "the snapshot must hold sorties in flight"
    r = OpsSession.restore(ScenarioOpsBuilder(), s.snapshot())
    r.run_until(N_DAYS * DAY)
    for k, v in full.world.states["m02"].items():
        assert np.array_equal(np.asarray(r.world.states["m02"][k]), np.asarray(v)), k
    assert _sorties(r) == _sorties(full)
