"""Policies: the decision tables (zen-engine), invariants, authority, order ids and the issue state machine.
No fleet data needed except where noted.

    python -m pytest proto/tests/test_triage_policies.py -q
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import pytest
import yaml

PROTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTO / "ground"))

from interfaces import NS, Authority, CandidateOrder, IssuedOrder, IssueState
from policies import (
    authority_of,
    check,
    epoch_of,
    human_only,
    issue_violations,
    order_id,
    policies,
    prefs,
)
from policies.engine import Prefs
from triage import IssueMachine, next_state

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
T = int(dt.datetime(2026, 6, 22, 6, 0, tzinfo=IST).timestamp()) * NS


def test_policy_versions_are_the_films():
    v = policies().version
    assert v["P-DEC-01"] == "P-DEC-01/1.4.0+jdm.c9b849a8e719"
    assert v["P-DEC-02"] == "P-DEC-02/0.3.0+jdm.a132344b5074"
    assert v["P-ORG-01"] == "P-ORG-01/2.1.0+jdm.7b053c8fed23"
    assert v["P-ORG-02"] == "P-ORG-02/1.2.0+jdm.c15c996682fc"
    assert v["P-ORG-03"] == "P-ORG-03/1.1.0+jdm.ae65c498a5af"
    assert v["P-SPR-01"].startswith("P-SPR-01/1.0.0+jdm.")


def test_film_files_unchanged():
    film = PROTO.parent / "video" / "data" / "policies"
    if not film.is_dir():
        pytest.skip("film policies not present")
    for n in ("P-DEC-01", "P-DEC-02", "P-ORG-01", "P-ORG-02", "P-ORG-03"):
        assert (film / f"{n}.jdm.json").read_bytes() == policies().raw[n]


@pytest.mark.parametrize("inp,row", [
    ({"severity": "WARNING", "job": {"status": "OPEN"}, "occ_10d": 2, "consec_flights": 1, "corroborated": False, "code": {"nofault_rate": 0.4}}, "r1"),
    ({"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": 3, "consec_flights": 1, "corroborated": True, "code": {"nofault_rate": 0.9}}, "r2"),
    ({"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": 1, "consec_flights": 3, "corroborated": False, "code": {"nofault_rate": 0.9}}, "r3"),
    ({"severity": "ADVISORY", "job": {"status": "DEFERRED"}, "occ_10d": 2, "consec_flights": 1, "corroborated": False, "code": {"nofault_rate": 0.59}}, "r4"),
    ({"severity": "ADVISORY", "job": {"status": "DEFERRED"}, "occ_10d": 2, "consec_flights": 2, "corroborated": False, "code": {"nofault_rate": 0.6}}, "r5"),
    ({"severity": "ADVISORY", "job": {"status": "CLOSED"}, "occ_10d": 0, "consec_flights": 0, "corroborated": False, "code": {"nofault_rate": 0.9}}, "r6"),
])
def test_p_dec_01_golden_cases(inp, row):
    e = policies().evaluate("P-DEC-01", inp)
    assert e.row == row and len(e.trace_hash) == 64


def test_tj107_input_and_counterfactual():
    tj107 = {"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": 6, "consec_flights": 34, "corroborated": False,
             "code": {"nofault_rate": 0.7094}}
    e = policies().evaluate("P-DEC-01", tj107)
    assert (e.row, e.rec) == ("r3", {"action": "TROUBLESHOOT", "band": "P2", "rationale_id": "PERSIST_3_FLIGHTS"})
    assert policies().evaluate("P-DEC-01", tj107 | {"consec_flights": 2}).rec["action"] == "MONITOR"  # film counterfactual


def test_other_tables():
    p = policies()
    assert p.evaluate("P-ORG-02", {"donor": {"nmc": False}, "job": {"awp_days": 80}, "policy": {"awp_min_days": 7}}).rec["action"] == "EXPEDITE_SPARES"
    assert p.evaluate("P-ORG-02", {"donor": {"nmc": True}, "job": {"awp_days": 80}, "policy": {"awp_min_days": 7}}).rec["action"] == "CANNIBALISE"
    assert p.evaluate("P-ORG-03", {"request": {"defer_servicing": True, "extension_pct": 25}}).output["rec"]["status"] == "BLOCKED_L1"
    assert p.evaluate("P-ORG-01", {"defect": {"grounding": False}, "severity": "WARNING"}).output["limit"]["deferrable"] is False
    assert p.evaluate("P-SPR-01", {"life": {"left": 1, "days_to_limit": 1.15}, "lead": {"median_d": 6.6}}).rec["action"] == "REQUISITION_SPARES"
    assert p.evaluate("P-SPR-01", {"life": {"left": 5, "days_to_limit": 20}, "lead": {"median_d": 6.6}}).rec["action"] == "NONE"


def test_determinism_lint():
    assert policies().lint() == []


def test_authority_matches_data_layer():
    mine = yaml.safe_load((PROTO / "ground" / "policies" / "authority.yaml").read_text())
    dl = Path(os.environ.get("PHX_DATALAYER_CODE", "/Users/abishaikc/Downloads/phalanx_data_layer_preview/code"))
    src = dl / "configs" / "policies" / "authority.yaml"
    if not src.exists():
        pytest.skip("data-layer authority matrix not present")
    assert mine == yaml.safe_load(src.read_text())
    for a in ("CHANGE_MONITORING_CONFIG", "LOAD_SOFTWARE", "EMBODY_MODIFICATION", "DEFER_SERVICING"):
        assert human_only(a) and authority_of(a) == Authority.HUMAN
    for a in ("TROUBLESHOOT", "EXPEDITE_SPARES", "REQUISITION_SPARES", "INSPECT"):
        assert authority_of(a) == Authority.AGENT


def _c(action="TROUBLESHOOT", auth=Authority.AGENT, ev=(b"\x01" * 16,), params=None, tail="TJ107"):
    return CandidateOrder(issue_id=f"{tail}-X", rule="P-DEC-01", row="r3", policy_version="v", action=action,
                          parameters=params or {"code": "HYD-101"}, target_tail_no=tail, target_base=None,
                          authority=auth, mode="consent", evidence=tuple(ev), rationale="r")


def test_invariants():
    ing = {("TJ107", "01" * 16): T - 1, ("TJ107", "02" * 16): T + 1}
    look = lambda tail, e: ing.get((tail, bytes(e).hex()))
    kept, rej = check([
        _c(),                                                     # ok
        _c(),                                                     # duplicate (tail, action, target)
        _c("CHANGE_MONITORING_CONFIG", Authority.AGENT, params={"filter_codes_add": ["HYD-101"]}),  # HUMAN-only
        _c("GROUND", params={}),                                  # no automatic grounding
        _c(ev=(b"\x02" * 16,), params={"code": "X"}),             # evidence ingested after t
        _c(ev=(b"\x03" * 16,), params={"code": "Y"}),             # evidence not in the store
        _c(ev=(), params={"code": "Z"}),                          # no evidence
        _c("DEFER_SERVICING", Authority.HUMAN, params={"extension_fraction": 0.25}),  # over the 20 % cap
    ], T, look)
    assert len(kept) == 1
    whys = [w for _, w in rej]
    assert "open order already exists" in whys[0] and "HUMAN-only" in whys[1] and "no automatic grounding" in whys[2]
    assert "ingested after" in whys[3] and "not in the store" in whys[4] and "no evidence" in whys[5] and "above 20%" in whys[6]
    human = _c("CHANGE_MONITORING_CONFIG", Authority.HUMAN, params={"filter_codes_add": ["HYD-101"]})
    assert issue_violations(IssuedOrder("x", human, T, approved_by="SEO", signed_by=None))
    assert not issue_violations(IssuedOrder("x", human, T, approved_by=None, signed_by="SEO"))
    assert issue_violations(IssuedOrder("x", _c(), T, approved_by=None, signed_by=None))  # consent: not approved


def test_order_id_recipe():
    ev = ["1723553b2db663fe4eaa564c5884b2f6"]
    a = order_id("P-DEC-01", "1.4.0", epoch_of(T), "TJ103", "TROUBLESHOOT", {"code": "LGB-501"}, ev)
    assert a.startswith("phx:P-DEC-01:1.4.0:20260622T0800:TJ103:TROUBLESHOOT:") and len(a.split(":")[-1]) == 16
    assert a == order_id("P-DEC-01", "1.4.0", epoch_of(T), "TJ103", "TROUBLESHOOT", {"code": "LGB-501"}, list(reversed(ev)))
    assert epoch_of(T) == int(dt.datetime(2026, 6, 22, 8, 0, tzinfo=IST).timestamp()) * NS
    assert epoch_of(T + 3 * 3600 * NS) == epoch_of(T) + 86400 * NS  # decided after 08:00 → next morning


def test_state_machine():
    assert next_state(None, decision=True, has_order=True, suppressed=False) == IssueState.PROPOSED
    assert next_state(None, decision=True, has_order=False, suppressed=False) == IssueState.TRIAGED
    assert next_state(None, decision=False, has_order=False, suppressed=False) == IssueState.MONITORING
    assert next_state(None, decision=True, has_order=True, suppressed=True) == IssueState.SUPPRESSED_BY_DESIGN
    assert next_state(IssueState.CLOSED, decision=True, has_order=True, suppressed=False) == IssueState.PROPOSED  # reopened
    assert next_state(IssueState.APPROVED, decision=True, has_order=True, suppressed=False) == IssueState.APPROVED
    m = IssueMachine()
    for ev in ("triage", "propose", "approve", "order", "start_work", "resolve", "close", "reopen", "triage"):
        m.send(ev)
    assert m.current_state_value == "TRIAGED"


def test_prefs_bounded(tmp_path):
    p = prefs()
    assert isinstance(p, Prefs) and p["budget"] == 10 and p["recurrence_min"] == 2 and p["cannibalisation_enabled"] is False
    bad = tmp_path / "prefs.yaml"
    bad.write_text("budget: {value: 50, bounds: [3, 20]}\n")
    with pytest.raises(ValueError):
        prefs.__wrapped__(bad)


def test_gate_g4_from_hazard_findings():
    """S3's hazard findings open gate G4 only above the threshold and only on a safety-critical class."""
    from interfaces import Belief, Finding, Source, Tier
    from triage import EFFECTS, risk_facts

    def hz(serial, v):
        return Finding("phx.hazard", Tier.PRED, "TJ107", serial,
                       (Belief("removal_risk_30d", v, v, v, 12, "phx.hazard", "1", Source.TRAIN),), (), "r.")

    from types import SimpleNamespace

    got = risk_facts(SimpleNamespace(t=T), [hz("HYDP-000010", 0.3), hz("HYDP-000002", 0.05), hz("TYRE-000017", 0.9),
                            hz("BCU-000001", None)], prefs())
    assert [(f.issue_id, f.gate) for f in got] == [("TJ107-RISK-HYDP-000010", "G4")]
    assert "HYDP" in EFFECTS["safety_critical_classes"]
