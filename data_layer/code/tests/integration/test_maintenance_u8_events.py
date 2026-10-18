"""E1-MF (U8): the two catalogued cross-module events no test ever emitted, produced and consumed by the real
modules.

- `mx.monitoring` (M18 -> M14, AD-44): the real M18 executes a CHANGE_MONITORING_CONFIG order and emits it;
  the real M14 (in the same operations world, the M18 `monitoring` target) masks the code, so a condition it
  then declares is evaluated but not recorded (A-W1.5-42), while the order-free control records it.
- `m18.disruption` (M02 -> M18): the real M02 in operations mode sends its scenario's supply disruption at
  day 0; the real M18 stores it and applies the lead-time factor to a demand raised in the window, against
  the disruption-free control on the same seed.

Each test also checks the dispatched payload carries the catalogued keys (`configs/interfaces/w1_events.yaml`;
read with `read_payload`; AD-48.1 plain top-level keys).

Sample: operations worlds of one or two tails over 1-3 days; one order, one condition, one demand each.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.yamlio import load_yaml
from phalanx.environment.config import load_env_config
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.maintenance.config import load_m18_config
from phalanx.maintenance.docstate import decode_doc
from phalanx.maintenance.world import FleetSpec, OpsTargets
from phalanx.monitoring import (
    MonitoringConfig,
    MonitoringModule,
    contract_tables,
    load_code_table,
    load_monitoring_params,
    lru_condition_payload,
)
from phalanx.orders.model import Order
from phalanx.scenario.config import FleetScenario, load_fleet_scenario, load_scenario_params
from phalanx.scenario.module import EV_DAY, OpsLink, ScenarioModule

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
EVENTS = load_yaml(ROOT / "configs" / "interfaces" / "w1_events.yaml")["events"]
NS = 10**9
H = 3600 * NS
DAY = 24 * H
D = load_dictionary()


def _steps_to(s: OpsSession, t_kernel: int) -> int:
    return -((-t_kernel * 240) // NS) - s.world.k


def _run_traced(s: OpsSession, t_kernel: int) -> list[Event]:
    """Advance the session's world to ``t_kernel`` and return the events dispatched on the way."""
    s.world, trace = s.system.run(s.world, _steps_to(s, t_kernel))
    return [e for _, e in trace.dispatched]


# ---------------------------------------------------------------------------------------------- M18 -> M14
TAIL = "T01"
CODE = "AVI-203"
EPOCH = 1_790_035_200 * NS  # 2026-09-22 00:00 UTC (05:30 IST), as the M18 world tests


def _quiet_m18():
    cfg = load_m18_config()
    big = (10**9,) * cfg.n_servicing
    cfg = cfg.with_values(srv_interval_fh_s=big, srv_interval_s=big)
    no_life = {
        c.code: {"life_fh": 0.0, "life_landings": 0.0, "life_streams": 0.0, "life_years": 0.0}
        for c in cfg.catalogue.classes
    }
    return cfg.with_catalogue_values(no_life)


def _monitoring_world(with_order: bool):
    p = load_monitoring_params()
    codes = load_code_table(D, p)
    cfg = MonitoringConfig.from_dictionary(D, codes, ("IN20-0001",), tail_no=TAIL, regime="mature")
    b = OpsOnlyBuilder(
        FleetSpec((TAIL,), ("SUL",), (0,)),
        EPOCH,
        m18_cfg=_quiet_m18(),
        targets=OpsTargets(m21="m21", sink="sink", health=None, monitoring="mon"),
        extra=(lambda: MonitoringModule("mon", p, config=cfg, identity={"tail": TAIL}),),
    )
    s = OpsSession(b, 0x5EED)
    s.run_until(H)
    if with_order:
        s.submit(
            [
                Order(
                    "F1",
                    "TEST",
                    "HUMAN",
                    s.t_utc,
                    s.t_utc,
                    "CHANGE_MONITORING_CONFIG",
                    {"filter_codes_add": [CODE]},
                    target_tail_no=TAIL,
                )
            ]
        )
    dispatched = _run_traced(s, 2 * DAY)  # applied at the next decision epoch (08:00 IST)
    sid = f"{TAIL}-u8"
    t0 = 2 * DAY + H
    flight = [
        Event(t0, "monitor.sortie_start", "mon", {"sortie_id": sid}),
        Event(t0 + 60 * NS, "monitor.lru_condition", "mon", lru_condition_payload(CODE, 30.0)),
        Event(t0 + 3500 * NS, "monitor.landing", "mon", {}),
        Event(
            t0 + H + 1,
            "monitor.sortie_end",
            "mon",
            {"flight_time_s": np.array(3250.0), "landings": np.array(1.0), "ab_lights": np.array([0.0])},
        ),
    ]
    s.world = s.system.inject(s.world, flight)
    _run_traced(s, 3 * DAY)
    m = s.system.modules["mon"]
    st = s.world.states["mon"]
    tabs = contract_tables(
        m, st, dictionary=D, tail_no=TAIL, epoch_utc_ns=EPOCH, t_ingest_utc_ns=EPOCH + 4 * DAY
    )
    return m, st, dispatched, tabs


def test_m18_emits_mx_monitoring_and_m14_masks_the_code():
    m, st, dispatched, tabs = _monitoring_world(with_order=True)
    mx = [e for e in dispatched if e.kind == "mx.monitoring"]
    assert len(mx) == 1 and mx[0].target == "mon" and mx[0].source == "m18"
    d = read_payload(mx[0].payload)
    assert set(EVENTS["mx.monitoring"]["payload"]) <= set(d), d
    assert d["tail"] == TAIL and d["filter_codes_add"] == [CODE]
    assert int(st["x_mask"][m.config.codes.by_code[CODE].index]) == 1  # M14 handled it
    assert CODE not in tabs["events.bit_faults"].column("event_code").to_pylist()  # evaluated, not recorded
    _, _, dispatched0, tabs0 = _monitoring_world(with_order=False)  # control: no order, same seed
    assert not [e for e in dispatched0 if e.kind == "mx.monitoring"]
    assert CODE in tabs0["events.bit_faults"].column("event_code").to_pylist()


# ---------------------------------------------------------------------------------------------- M02 -> M18
START = dt.date(2026, 1, 5)
FACTOR = 4.0


def _fleet(disrupted: bool) -> FleetScenario:
    full = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
    sq = full.squadrons[0]
    small = type(sq)(sq.sid, sq.role, sq.base, sq.tails[:2], sq.engine_serials[:2])
    dis = (("TYRE", FACTOR, START, START + dt.timedelta(days=2)),) if disrupted else ()
    return FleetScenario("u8_disruption", START, 3, (small,), disruptions=dis)


class _Builder:
    """WorldBuilder: real M02 (operations mode) + real M18/M21/sink (as test_scenario_m18_ops.py)."""

    def __init__(self, fleet: FleetScenario) -> None:
        self.fleet = fleet
        self.ids = OpsIds()
        self.epoch_utc_ns = fleet.epoch_utc_ns
        tails = fleet.tails()
        targets = OpsTargets(m21=self.ids.m21, sink=self.ids.sink, scenario="m02", health=None)
        link = OpsLink(m18=self.ids.m18, health=None, kpi=self.ids.sink)
        params, env = load_scenario_params(), load_env_config()
        self._ops = OpsOnlyBuilder(
            FleetSpec(tails, ("SUL",), tuple(0 for _ in tails)),
            self.epoch_utc_ns,
            scenario="u8",
            targets=targets,
            ids=self.ids,
            extra=(lambda: ScenarioModule("m02", params, env, fleet=fleet, ops=link),),
        )
        self.calendar = self._ops.calendar
        self.dict_version, self.dict_hash = self._ops.dict_version, self._ops.dict_hash

    def build(self, root, *, ledger=None):
        return self._ops.build(root, ledger=ledger)

    def initial_events(self) -> list[Event]:
        return [*self._ops.initial_events(), Event(0, EV_DAY, "m02", {"day": 0}, source="session")]


def _supply_world(disrupted: bool):
    b = _Builder(_fleet(disrupted))
    s = OpsSession(b, 0x0D5)
    dispatched = _run_traced(s, H)
    t_ep = b.calendar.next_epoch(s.t + 1)
    s.run_until(t_ep)
    ep = b.epoch_utc_ns + t_ep
    order = Order(
        "Q1",
        "TEST",
        "HUMAN",
        ep,
        ep,
        "REQUISITION_SPARES",
        {"part_no": "SYN-PN-TYRE", "quantity": 1},
        priority="PHU",
        target_base="SUL",
    )
    s.submit([order])
    s.run_until(t_ep + 2 * H)
    sup = decode_doc(s.world.states["m18"]["doc_supply"])
    dem = [d for d in sup["demands"].values() if d.get("order_id") == "Q1"]
    return b, sup, dem, dispatched


def test_m02_emits_m18_disruption_and_m18_applies_it():
    b, sup, dem, dispatched = _supply_world(disrupted=True)
    ev = [e for e in dispatched if e.kind == "m18.disruption"]
    assert len(ev) == 1 and ev[0].target == "m18" and ev[0].source == "m02"
    d = read_payload(ev[0].payload)
    assert set(EVENTS["m18.disruption"]["payload"]) <= set(d), d
    t1 = (
        START + dt.timedelta(days=3) - dt.date(1970, 1, 1)
    ).days * DAY - b.epoch_utc_ns  # end-of-window, kernel
    assert d["cls"] == "TYRE" and d["factor"] == FACTOR and int(d["t1"]) == t1
    assert sup["disruptions"] == [{"cls": "TYRE", "factor": FACTOR, "t0": int(d["t0"]), "t1": t1}]  # stored
    _, sup0, dem0, dispatched0 = _supply_world(disrupted=False)  # control: same seed, no disruption
    assert not [e for e in dispatched0 if e.kind == "m18.disruption"] and sup0["disruptions"] == []
    assert len(dem) == len(dem0) == 1 and dem[0]["t_open"] == dem0[0]["t_open"]
    lead, lead0 = dem[0]["eta"] - dem[0]["t_open"], dem0[0]["eta"] - dem0[0]["t_open"]
    assert lead0 > 3600 * NS  # not on the 1 h floor, so the factor is visible
    # M18 quantises an ETA to whole seconds: the disrupted lead is FACTOR x the control, to (1 + FACTOR) s
    assert abs(lead - FACTOR * lead0) <= (1 + FACTOR) * NS, (lead, lead0)


def test_payload_check_uses_the_catalogue():
    """Negative control: the catalogued payload keys are non-empty, so a payload without them would fail."""
    assert EVENTS["mx.monitoring"]["payload"] == ["tail"]
    assert EVENTS["m18.disruption"]["payload"] == ["cls", "factor", "t0", "t1"]
    assert not {"cls", "factor", "t0", "t1"} <= set(
        read_payload(Event(0, "m18.disruption", "m18", plain_payload({"cls": "TYRE"})).payload)
    )
