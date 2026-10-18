"""Rule tests for orders and the human gate (DEVELOPMENT.md §6): ids, consent, signatures, freeze, the log."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

PROTO = Path(__file__).resolve().parents[1]
REPO = PROTO.parent
sys.path.insert(0, str(PROTO / "ground"))

from interfaces import Authority, CandidateOrder  # noqa: E402
from lel import EventLog  # noqa: E402
from orders import IST, OrderDesk, order_id  # noqa: E402
from present import order_status  # noqa: E402

EPOCH = int(dt.datetime(2026, 6, 22, 8, tzinfo=IST).timestamp()) * 10**9


def cand(action: str, auth: Authority, issue: str = "TJ107-HYD-101", params: dict | None = None) -> CandidateOrder:
    return CandidateOrder(issue_id=issue, rule="P-DEC-01", row="r3", policy_version="P-DEC-01/1.4.0+jdm.3f9c0d7a",
                          action=action, parameters=params or {"code": "HYD-101"}, target_tail_no="TJ107", target_base="sulur",
                          authority=auth, mode="consent", evidence=(b"\x01" * 16,), rationale="test")


@pytest.fixture()
def desk(tmp_path: Path) -> OrderDesk:
    return OrderDesk(EventLog(tmp_path / "lel.sqlite"), EPOCH)


def test_order_ids_reproduce_the_film() -> None:
    d = json.loads((REPO / "video/data/decision_screens_asof_20260622.json").read_text())
    semver = {"P-DEC-01": "1.4.0", "P-ORG-02": "1.2.0", "P-SPR-01": "1.0.0"}
    for o in d["orders"]:
        oid, _ = order_id(o["rule"], semver[o["rule"]], EPOCH, o["tail"], o["action"], o["parameters"], o["evidence"])
        assert oid == o["order_id"]


def test_consent_unapproved_orders_are_not_issued(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    assert order_status(a) == "AWAITING_APPROVAL"
    out = desk.freeze()
    assert out == [] and a.state == "NOT_ISSUED"


def test_human_only_needs_a_named_signature(desk: OrderDesk) -> None:
    h = desk.propose(cand("CHANGE_MONITORING_CONFIG", Authority.HUMAN, params={"filter_codes_add": ["HYD-101"]}), "1.4.0")
    desk.approve(h.order_id, "SEO")
    assert h.needs_signature and not h.issuable and order_status(h) == "NEEDS_SIGNATURE"
    desk.sign(h.order_id, "ENGG-OFFICER")
    assert h.issuable and h.command()["issuer_kind"] == "HUMAN"
    assert [d.order_id for d in desk.freeze()] == [h.order_id]


def test_human_only_action_is_human_even_if_proposed_as_agent(desk: OrderDesk) -> None:
    h = desk.propose(cand("CHANGE_MONITORING_CONFIG", Authority.AGENT, params={"filter_codes_add": ["HYD-101"]}), "1.4.0")
    desk.approve(h.order_id, "SEO")
    assert h.needs_signature and not h.issuable


def test_frozen_board_refuses_changes(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    desk.freeze()
    with pytest.raises(PermissionError):
        desk.approve(a.order_id, "SEO")


def test_modify_creates_a_new_order(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    b = desk.modify(a.order_id, "SEO", {"code": "HYD-101", "position": "SYS1"})
    assert b.order_id != a.order_id and a.state == "REJECTED" and b.state == "PROPOSED"


def test_same_decision_same_id(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    b = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    assert a is b  # idempotent: a retry can never issue twice


def test_every_human_action_is_on_a_valid_chain(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    desk.approve(a.order_id, "SEO")
    desk.freeze()
    types = [e.type for e in desk.log.events()]
    assert types == ["ORDER_APPROVED", "BOARD_FROZEN"] and desk.log.verify()["ok"]


def test_snoozed_order_is_not_shown_ready(desk: OrderDesk) -> None:
    a = desk.propose(cand("TROUBLESHOOT", Authority.AGENT), "1.4.0")
    desk.snooze(a.order_id, "SEO", EPOCH + 86_400 * 10**9)
    assert order_status(a) == "SNOOZED" and desk.freeze() == []
