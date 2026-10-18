"""M21 order record, per-action parameter schemas, authority rules and the gateway (A4, A1 negative tests)."""

from __future__ import annotations

import pytest

from phalanx.core.snapshot import snapshot
from phalanx.fork.builder import OpsOnlyBuilder
from phalanx.fork.session import OpsSession
from phalanx.maintenance.records import ORDERS_COMMANDS, contract_v0, rows_to_table
from phalanx.maintenance.world import FleetSpec
from phalanx.orders.model import ACTION_SCHEMAS, Order, check_parameters, order_from_row, order_row
from phalanx.orders.rules import TechLogFacts, airworthiness, load_authority

NS = 1_000_000_000
H = 3600 * NS
EPOCH = 1_790_035_200 * NS

VALID = {
    "INSPECT": {"type": "BORESCOPE"},
    "TROUBLESHOOT": {"code": "HYD-120"},
    "REMOVE_REPLACE": {"position": "HYDP1"},
    "WASH_SERVICE": {"type": "ENGINE_WASH"},
    "DEFER": {"job_no": "SUL-26265-0001", "limits": "NO AB", "expiry_hours": 24},
    "CANNIBALISE": {"job_no": "SUL-26265-0001", "donor_tail_no": "T02"},
    "REQUISITION_SPARES": {"part_no": "SYN-PN-TYRE", "quantity": 2},
    "EXPEDITE_SPARES": {"demand_no": "D-SUL-26265-0001"},
    "TRANSFER_STOCK": {"part_no": "SYN-PN-TYRE", "quantity": 1, "from_base": "SUL", "to_base": "NAL"},
    "GROUND": {"reason": "fleet check"},
    "RELEASE": {},
    "BRING_FORWARD_SERVICING": {"servicing": "SRV-L1"},
    "DEFER_SERVICING": {"servicing": "SRV-L1", "extend_days": 2},
    "ASSIGN_SORTIE": {"date": "2026-09-23", "sorties": 2},
    "RESTRICT_USAGE": {"limit": "AB"},
    "EMBODY_MODIFICATION": {"mod_id": "MOD-1"},
    "LOAD_SOFTWARE": {"sw_config_id": "SW-2"},
    "CHANGE_MONITORING_CONFIG": {"filter_codes_add": ["NAV-310"]},
}


def mk(action, params, **kw):
    base = dict(
        order_id="O-1",
        issuer_id="AGENT-1",
        issuer_kind="AGENT",
        t_issued=EPOCH,
        t_effective=EPOCH,
        action=action,
        parameters=params,
        target_tail_no="T01",
    )
    base.update(kw)
    return Order(**base)


@pytest.mark.unit
def test_every_action_of_the_contract_vocabulary_has_a_schema():
    c = contract_v0()
    assert set(ACTION_SCHEMAS) == set(c.enums["OrderAction"].names) == set(VALID)


@pytest.mark.unit
@pytest.mark.parametrize("action", sorted(VALID))
def test_valid_parameters_pass_and_rows_validate(action):
    o = mk(action, VALID[action], target_base="SUL" if action == "REQUISITION_SPARES" else None)
    assert check_parameters(o) == []
    row = order_row(o, contract_v0(), dict_version=None, dict_hash=None)
    rows_to_table(contract_v0(), ORDERS_COMMANDS, [row])
    assert order_from_row(row) == o


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action", "params", "kw", "fragment"),
    [
        ("INSPECT", {"type": "XRAY"}, {}, "parameters"),
        ("DEFER", {"job_no": "J", "limits": "x"}, {}, "expiry_hours"),
        ("REMOVE_REPLACE", {"position": "HYDP1", "colour": "red"}, {}, "Additional properties"),
        ("REQUISITION_SPARES", {"part_no": "P", "quantity": 1}, {}, "target_base"),
        ("GROUND", {"reason": "x"}, {"target_tail_no": None}, "target"),
        ("TROUBLESHOOT", {}, {}, "parameters"),
        ("INSPECT", {"type": "NDT"}, {"t_effective": EPOCH - NS}, "t_effective"),
    ],
)
def test_invalid_orders_are_rejected_with_a_reason(action, params, kw, fragment):
    errs = check_parameters(mk(action, params, **kw))
    assert errs and any(fragment in e for e in errs), errs


@pytest.mark.unit
def test_authority_matrix_and_airworthiness_rules():
    a = load_authority()
    assert not a.allowed("DEFER_SERVICING", "AGENT") and a.allowed("DEFER_SERVICING", "HUMAN")
    assert a.allowed("CANNIBALISE", "AGENT") and a.allowed("INSPECT", "HUMAN")
    assert a.max_extension_fraction("DEFER_SERVICING") == 0.2
    down = TechLogFacts("T01", False, ("SUL-1",), False)
    up = TechLogFacts("T01", True, (), False)
    assert "SUL-1" in airworthiness("RELEASE", down, {})
    assert airworthiness("RELEASE", up, {}) is None
    assert airworthiness("ASSIGN_SORTIE", down, {}) and airworthiness("ASSIGN_SORTIE", up, {}) is None


def _session():
    b = OpsOnlyBuilder(FleetSpec(("T01", "T02"), ("SUL",), (0, 0)), EPOCH)
    s = OpsSession(b, 11)
    s.run_until(H)
    return s


@pytest.mark.unit
def test_gateway_authority_time_and_contract_checks():
    s = _session()
    now = s.t_utc
    res = s.submit(
        [
            Order(
                "A-1",
                "AGENT-1",
                "AGENT",
                now,
                now,
                "DEFER_SERVICING",
                {"servicing": "SRV-L1", "extend_days": 1},
                target_tail_no="T01",
            ),
            Order(
                "A-2",
                "AGENT-1",
                "AGENT",
                now + NS,
                now + NS,
                "INSPECT",
                {"type": "NDT"},
                target_tail_no="T01",
            ),
            Order(
                "bad id with spaces",
                "AGENT-1",
                "AGENT",
                now,
                now,
                "INSPECT",
                {"type": "NDT"},
                target_tail_no="T01",
            ),
            Order(
                "A-3", "AGENT-1", "AGENT", now, now + 30 * H, "INSPECT", {"type": "NDT"}, target_tail_no="T01"
            ),
        ]
    )
    v = {r.order_id: r for r in res}
    assert v["A-1"].verdict == "REJECTED" and "authority" in v["A-1"].reason
    assert v["A-2"].verdict == "REJECTED" and "session time" in v["A-2"].reason
    assert v["bad id with spaces"].verdict == "INVALID"
    assert v["A-3"].verdict == "ACCEPTED"
    # applied at the first 08:00 IST epoch at or after t_effective (05:30 IST + 1 h + 30 h -> day 2 08:00)
    assert v["A-3"].t_apply == s.builder.calendar.next_epoch(31 * H)
    s.run_until(2 * H)
    cmds = {r["order_id"] for r in s.records("orders.commands")}
    assert cmds == {"A-1", "A-2", "A-3"}  # the INVALID order never entered the world
    rej = [r for r in s.records("orders.status") if r["status"] == "REJECTED"]
    assert {r["order_id"] for r in rej} == {"A-1", "A-2"} and all(r["reason"] for r in rej)


@pytest.mark.unit
def test_resending_an_order_id_changes_nothing():
    s = _session()
    o = Order("DUP-1", "H", "HUMAN", s.t_utc, s.t_utc, "INSPECT", {"type": "NDT"}, target_tail_no="T01")
    s.submit([o])
    before = snapshot(s.system, s.world)
    res = s.submit(
        [o, Order("DUP-1", "H", "HUMAN", s.t_utc, s.t_utc, "GROUND", {"reason": "x"}, target_tail_no="T02")]
    )
    assert [r.verdict for r in res] == ["DUPLICATE", "DUPLICATE"]
    assert snapshot(s.system, s.world) == before  # world, queue and order log untouched
