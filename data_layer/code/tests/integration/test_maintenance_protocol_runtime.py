"""AD-44 / AD-48.1 at run time: what the real operations modules actually dispatch follows the catalogue.

A declaration check (``tests/integration/test_event_protocol.py``) cannot see an emitted payload: E1's mutant
m06b (M18 ``mx.action`` key ``tail`` -> ``tail_no``) survived it. This test runs one real operations world -
M02 (operations mode), M18, M21 and the record sink, and the health trio M10 / M11 / M14 of one tail - with
orders, a supply disruption and scripted faults, and checks **every dispatched event of a catalogued kind**:

- it is not in the retired ``{"doc": ...}`` encoding (AD-48.1) and decodes with ``read_payload``;
- its plain top-level keys cover the catalogued payload keys;
- its source is the catalogued producer and its target a catalogued consumer.

It also requires that the world exercises every catalogued kind these modules produce, so it cannot pass
vacuously. Negative controls: the m06b mutant on the real M18 (key renamed at emission), a planted
doc-encoded event, a wrong producer and a wrong consumer are each reported; uncatalogued (internal) kinds are
free (AD-44).

This is a test-side check of real traffic; the production runtime validator is W2.1a's
``phalanx.integration.validate`` (deliverable 3), built to the same catalogue.

Sample (stated before running): one squadron of 2 tails at Sulur, 4 days from Monday 2026-01-05 (4 flying
days), one root seed; 6 orders at the first decision epoch, 2 scripted faults on the monitored tail.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.environment.config import load_env_config
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels
from phalanx.health.protocol import RETIRED_DOC_KEY, PayloadError, plain_payload, read_payload
from phalanx.maintenance.world import FleetSpec, MaintenanceWorld, OpsTargets
from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params
from phalanx.orders.model import Order
from phalanx.scenario.config import FleetScenario, load_fleet_scenario, load_scenario_params
from phalanx.scenario.module import EV_DAY, OpsLink, ScenarioModule

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
CAT = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]
D = load_dictionary()
NS = 10**9
H = 3600 * NS
DAY = 24 * H
START = dt.date(2026, 1, 5)  # a Monday
N_DAYS = 4
SEED = 0x0D5
IDS = OpsIds()
#: module instance id -> module id (M-number) of this world
MODULE_OF = {
    "m02": "M02",
    IDS.m18: "M18",
    IDS.m21: "M21",
    IDS.sink: "M21",
    "m10": "M10",
    "m11": "M11",
    "m14": "M14",
}
#: catalogued kinds this world must exercise (every kind its producers emit in operations / usage mode)
REQUIRED = frozenset(
    {
        # M02
        "ops.offer_request",
        "ops.launch",
        "ops.sortie_done",
        "usage.sortie_summary",
        "m18.disruption",
        "ops.takeoff",  # AD-48.2 (to M10 here: it holds the airborne sortie open until the summary)
        "kpi.plan",  # AD-49 (the daily flying task to the M21 RecordSink)
        # M18
        "ops.offer",
        "ops.launch_denied",
        "ops.assign",
        "ops.restrict",
        "cfg.install",
        "cfg.remove",
        "mx.action",
        "mx.monitoring",
        "order.progress",
        # M21
        "order.exec",
        # M11
        "truth.fault",
        "truth.fault_clear",
        "truth.incident",
        "ops.start_failure",  # AD-49 (the scripted JFS cold start falls between sorties: M02 counts it late)
        # M14
        "obs.event",
    }
)


def protocol_violations(events, module_of=MODULE_OF, catalogue=CAT) -> list[str]:
    """Every catalogued-kind event: plain keys (no retired doc wrapper), catalogued keys present, catalogued
    producer and consumer. Internal (uncatalogued) kinds are free (AD-44)."""
    out: list[str] = []
    for ev in events:
        spec = catalogue.get(ev.kind)
        if spec is None:
            continue
        where = f"{ev.kind} {ev.source}->{ev.target} @{ev.t_ns}"
        prod, cons = module_of.get(ev.source), module_of.get(ev.target)
        if prod != spec["producer"]:
            out.append(f"{where}: producer {prod or ev.source!r} is not the catalogued {spec['producer']}")
        if cons not in spec["consumers"]:
            out.append(f"{where}: consumer {cons or ev.target!r} not in the catalogued {spec['consumers']}")
        if RETIRED_DOC_KEY in ev.payload:
            out.append(f"{where}: retired {{'doc': ...}} encoding (AD-48.1)")
            continue
        try:
            d = read_payload(ev.payload)
        except (PayloadError, ValueError) as x:
            out.append(f"{where}: payload does not decode ({x})")
            continue
        missing = set(spec["payload"]) - set(d)
        if missing:
            out.append(f"{where}: payload lacks {sorted(missing)}")
    return out


# ---------------------------------------------------------------------------------------------- the world
def _fleet() -> FleetScenario:
    full = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
    sq = full.squadrons[0]
    small = type(sq)(sq.sid, sq.role, sq.base, sq.tails[:2], sq.engine_serials[:2])
    dis = (("TYRE", 2.0, START, START + dt.timedelta(days=2)),)
    return FleetScenario("w21c_runtime", START, N_DAYS, (small,), disruptions=dis)


FLEET = _fleet()
TAIL, OTHER = FLEET.tails()
SERIAL = FLEET.squadrons[0].engine_serials[0]
EPOCH = FLEET.epoch_utc_ns


def _m10():
    cfg = HealthConfig((SERIAL,), sensor_bias_channels(D), "m11", monitor_target="m14", tail_no=TAIL)
    return HealthModule("m10", load_health_params(), config=cfg, identity={"tail": TAIL})


def _m11():
    cfg = FaultConfig(
        load_catalogue(),
        load_graph(),
        {"health": "m10", "monitoring": "m14", "maintenance": IDS.m18, "ops": "m02"},
        (SERIAL,),
        sensor_bias_channels(D),
        realise_physics_edges=True,
        stochastic=False,
        tail_no=TAIL,
    )
    return FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": TAIL})


def _m14():
    p = load_monitoring_params()
    cfg = MonitoringConfig.from_dictionary(
        D,
        load_code_table(D, p),
        (SERIAL,),
        regime="mature",
        tail_no=TAIL,
        epoch_utc_ns=EPOCH,
        obs_target=IDS.m18,
    )
    return MonitoringModule("m14", p, config=cfg, identity={"tail": TAIL})


class RuntimeWorld:
    """WorldBuilder: real M02 (operations mode) + M18/M21/sink + the real M10/M11/M14 of ``TAIL``."""

    def __init__(self, fleet_spec: FleetSpec | None = None) -> None:
        self.ids = IDS
        self.epoch_utc_ns = EPOCH
        targets = OpsTargets(m21=IDS.m21, sink=IDS.sink, scenario="m02", health="m10", monitoring="m14")
        link = OpsLink(m18=IDS.m18, health="m10", kpi=IDS.sink)
        params, env = load_scenario_params(), load_env_config()
        self._ops = OpsOnlyBuilder(
            fleet_spec or FleetSpec.from_scenario(FLEET, bases={"sulur": "SUL"}),  # the scenario's serials
            EPOCH,
            scenario="w21c-rt",
            targets=targets,
            ids=IDS,
            extra=(
                lambda: ScenarioModule("m02", params, env, fleet=FLEET, ops=link, takeoff_targets=("m10",)),
                _m10,
                _m11,
                _m14,
            ),
        )
        self.calendar = self._ops.calendar
        self.dict_version, self.dict_hash = self._ops.dict_version, self._ops.dict_hash

    def build(self, root, *, ledger=None):
        return self._ops.build(root, ledger=ledger)

    def initial_events(self) -> list[Event]:
        return [*self._ops.initial_events(), Event(0, EV_DAY, "m02", {"day": 0}, source="session")]


def _orders(ep: int) -> list[Order]:
    d2 = (START + dt.timedelta(days=2)).isoformat()

    def o(oid, action, params, tail=TAIL):
        return Order(oid, "TEST", "HUMAN", ep, ep, action, params, target_tail_no=tail)

    return [
        o("A-1", "ASSIGN_SORTIE", {"date": d2, "sorties": 1}, tail=OTHER),  # -> ops.assign
        o("R-1", "RESTRICT_USAGE", {"limit": "AB"}, tail=OTHER),  # -> ops.restrict
        o("M-1", "CHANGE_MONITORING_CONFIG", {"filter_codes_add": ["ADC-401"]}),  # -> mx.monitoring
        o("W-1", "WASH_SERVICE", {"type": "ENGINE_WASH"}),  # -> mx.action
        o("X-1", "REMOVE_REPLACE", {"position": "ADC"}),  # -> cfg.remove / cfg.install
        o("G-1", "GROUND", {"reason": "TEST"}, tail=OTHER),  # -> ops.launch_denied for its launches
    ]


def _faults(t: int) -> list[Event]:
    """Scripted faults on the monitored tail: an FCS channel dropout (truth.fault, then truth.fault_clear
    after 5 s), a JFS cold-start failure (truth.incident start_failure) and an avionics LRU failure (a
    persistent covered internal-BIT condition: M14 records it on the next sortie and downloads it to M18 as
    obs.event)."""
    return [
        Event(t, "faults.inject", "m11", {"mode": "FM.FCS.CHANNEL_DROPOUT", "covered": True}, source="test"),
        Event(t + 60 * NS, "faults.inject", "m11", {"mode": "FM.SPS.JFS_COLD_START_FAIL"}, source="test"),
        Event(t + 2 * 60 * NS, "faults.inject", "m11", {"mode": "FM.AV.LRU_FAILURE", "covered": True}),
    ]


def run_world(
    *, mutate=None, fleet_spec: FleetSpec | None = None, session: list | None = None
) -> list[Event]:
    """Dispatched events of the world over N_DAYS (``mutate``: a context manager applied while running;
    ``fleet_spec``: M18's fleet, default the scenario's; ``session``: receives the session when given)."""
    b = RuntimeWorld(fleet_spec)
    s = OpsSession(b, SEED)
    if session is not None:
        session.append(s)
    out: list[Event] = []
    t_ep = b.calendar.next_epoch(1 * NS)
    s.world, tr = s.system.run(s.world, _steps(s, t_ep))
    out += [e for _, e in tr.dispatched]
    res = s.submit(_orders(b.epoch_utc_ns + t_ep))
    assert all(r.verdict == "ACCEPTED" for r in res), res
    s.world = s.system.inject(s.world, _faults(t_ep + 2 * H))
    s.world, tr = s.system.run(s.world, _steps(s, N_DAYS * DAY))
    out += [e for _, e in tr.dispatched]
    return out


def _steps(s: OpsSession, t_kernel: int) -> int:
    return -((-t_kernel * 240) // NS) - s.world.k


@pytest.fixture(scope="module")
def dispatched():
    return run_world()


def test_every_catalogued_event_follows_the_catalogue(dispatched):
    seen = {e.kind for e in dispatched if e.kind in CAT}
    assert REQUIRED <= seen, f"world did not exercise {sorted(REQUIRED - seen)}"
    bad = protocol_violations(dispatched)
    assert not bad, "\n".join(bad[:40])
    n = sum(1 for e in dispatched if e.kind in CAT)
    assert n > 100, n  # the check ran over real traffic


def test_m06b_mutant_is_caught(monkeypatch, dispatched):
    """E1 mutant m06b: M18 emits ``mx.action`` with ``tail`` renamed ``tail_no``; it survived E1's
    ``make check`` because M10 fell back to ``tail_no``. Now it is killed twice:

    1. at the consumer: M10 reads the catalogued key only (AD-48.1), so the mutated world raises at the first
       ``mx.action`` it receives;
    2. by the run-time check: every real ``mx.action`` of the unmutated world, re-keyed the same way, is
       reported as lacking ``tail``."""
    orig = MaintenanceWorld._emit

    def mutant(self, ctx, kind, target, doc, **kw):
        if kind == "mx.action" and "tail" in doc:
            doc = {("tail_no" if k == "tail" else k): v for k, v in doc.items()}
        return orig(self, ctx, kind, target, doc, **kw)

    with monkeypatch.context() as mp:
        mp.setattr(MaintenanceWorld, "_emit", mutant)
        with pytest.raises(ContractError, match=r"mx\.action payload lacks its catalogued key 'tail'"):
            run_world()
    real = [e for e in dispatched if e.kind == "mx.action"]
    assert real
    mutated = []
    for e in real:
        d = read_payload(e.payload)
        d["tail_no"] = d.pop("tail")
        mutated.append(Event(e.t_ns, e.kind, e.target, plain_payload(d), source=e.source))
    bad = protocol_violations(mutated)
    assert len(bad) == len(real) and all("lacks ['tail']" in m for m in bad), bad[:5]


def test_negative_controls_on_planted_events():
    """A doc-encoded event, a wrong producer and a wrong consumer are each reported; an internal kind is free;
    a well-formed event passes."""
    good = Event(
        0, "cfg.remove", "m10", plain_payload({"tail": TAIL, "pos": "ENG", "serial": "S1"}), source="m18"
    )
    assert protocol_violations([good]) == []
    doc = Event(0, "cfg.remove", "m10", {"doc": '{"tail":"T","pos":"ENG","serial":"S1"}'}, source="m18")
    assert any("retired" in m for m in protocol_violations([doc]))
    wrong_src = Event(0, "cfg.remove", "m10", good.payload, source="m02")
    assert any("producer" in m for m in protocol_violations([wrong_src]))
    wrong_dst = Event(0, "cfg.remove", "m14", good.payload, source="m18")
    assert any("consumer" in m for m in protocol_violations([wrong_dst]))
    short = Event(0, "cfg.remove", "m10", plain_payload({"tail": TAIL, "pos": "ENG"}), source="m18")
    assert any("lacks ['serial']" in m for m in protocol_violations([short]))
    internal = Event(0, "m18.review", "m18", {"doc": "{}"}, source="m18")
    assert protocol_violations([internal]) == []
