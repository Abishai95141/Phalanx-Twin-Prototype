"""The 22 Jun decision board against the film (DEVELOPMENT.md §5.1): the seven decisions and their bands, the
candidate orders and their ids, the P4 group, issue states, and the shapes the loop and the API read.

Differences from the film are listed in ``proto/ground/triage/golden-22jun.md`` with their reasons; they are
asserted here as computed, not tuned away.

    python -m pytest proto/tests/test_triage_golden.py -q
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

PROTO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROTO / "ground"))

import triage
from interfaces import NS, Authority, Issue, IssueState
from policies import candidate_order_id, check, policies
from store import Store
from twin import Twin

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
T = int(dt.datetime(2026, 6, 22, 6, 0, tzinfo=IST).timestamp()) * NS

FILM = {"TJ103-LGB-501": "P1", "TJ106-LGB-501": "P1", "TJ107-HYD-101": "P2", "TJ108-AOG-CHUTE": "P2",
        "TJ105-SPS-501": "P3", "TJ105-TYRE": "P3", "P4-ADVISORY": "P4"}
EXTRA = {"TJ102-HYD-001": "P2", "TJ102-HYD-101": "P3"}  # golden-22jun.md §Board
FILM_ORDERS = {
    "phx:P-DEC-01:1.4.0:20260622T0800:TJ103:TROUBLESHOOT:54d7fe500658cf7d",
    "phx:P-DEC-01:1.4.0:20260622T0800:TJ106:TROUBLESHOOT:98e5d97f15d4d9c7",
    "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:TROUBLESHOOT:748653aa6bcf4544",
    "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:CHANGE_MONITORING_CONFIG:6c744e071d8445f0",
    "phx:P-ORG-02:1.2.0:20260622T0800:TJ108:EXPEDITE_SPARES:c98851c5b4a8256b",
    "phx:P-SPR-01:1.0.0:20260622T0800:TJ105:REQUISITION_SPARES:b786353ebcdad872",
    "phx:P-DEC-01:1.4.0:20260622T0800:TJ105:TROUBLESHOOT:e9403bb76d4e79da",
}
FILM_GROUP = {"TJ102-ENG-201", "TJ103-AVI-201", "TJ103-AVI-203", "TJ103-ENG-201", "TJ104-ADC-002", "TJ104-ELE-405",
              "TJ104-ENG-201", "TJ105-AVI-201", "TJ105-AVI-203", "TJ106-AVI-201", "TJ106-AVI-204", "TJ106-ENG-201",
              "TJ107-AVI-203"}


@pytest.fixture(scope="module")
def world():
    store = Store.for_preview()
    twin = Twin(store)
    return store, twin, triage.evaluate(store, twin, T)


def test_board_bands(world):
    _, _, b = world
    got = {i.issue_id: i.band for i in b.issues}
    assert {k: got.get(k) for k in FILM} == FILM  # the film's seven decisions, same bands
    assert got == FILM | EXTRA  # plus the two written down in golden-22jun.md
    assert [i.band for i in b.issues] == sorted(i.band for i in b.issues)  # ranked P1 first
    assert b.funnel["alert_rows"] == 1192 and b.funnel["issues"] == 326 and b.funnel["open"] == 33
    assert (b.funnel["decisions"], b.funnel["monitoring"], b.flood) == (9, 13, False)


def test_bases(world):
    _, _, b = world
    i = {x.issue_id: x for x in b.issues}
    assert i["TJ103-LGB-501"].basis == i["TJ106-LGB-501"].basis == "Gate G1 · WARNING recurs ≤ 10 d"
    assert i["TJ107-HYD-101"].basis == "P-DEC-01 r3 · policy floor · D8 nuisance review"  # C3 × U1 → P3, floor → P2
    assert (i["TJ107-HYD-101"].consequence, i["TJ107-HYD-101"].urgency) == (3, 1)
    assert i["TJ108-AOG-CHUTE"].basis == "AP lookup · C3 × U3"
    assert i["TJ105-SPS-501"].basis == "AP lookup · C3 × U1"
    assert i["TJ105-TYRE"].basis == "AP lookup · C2 × U3"
    assert i["P4-ADVISORY"].basis.startswith("P-DEC-01 r5")
    assert [x.confidence for x in (i["TJ103-LGB-501"], i["TJ107-HYD-101"], i["TJ105-SPS-501"], i["P4-ADVISORY"])] == ["med", "high", "med", "high"]


def test_orders(world):
    _, _, b = world
    ids = {candidate_order_id(c, T): c for c in b.orders}
    assert FILM_ORDERS <= set(ids)  # every film order id reproduced exactly
    assert not b.rejected
    for oid, c in ids.items():
        assert c.mode == "consent"
        assert c.authority == (Authority.HUMAN if c.action == "CHANGE_MONITORING_CONFIG" else Authority.AGENT), oid
        assert c.policy_version == policies().version[c.rule]
        assert c.action != "GROUND"
    extra = {oid.split(":")[4] + ":" + c.action + ":" + c.issue_id for oid, c in ids.items() if oid not in FILM_ORDERS}
    assert extra == {"TJ102:TROUBLESHOOT:TJ102-HYD-001", "TJ102:CHANGE_MONITORING_CONFIG:TJ102-HYD-001",
                     "TJ102:TROUBLESHOOT:TJ102-HYD-101"}


def test_order_evidence_ingested(world):
    store, twin, b = world
    from engines.common import context

    ing = context(store, twin, T).ingest_of_rid
    kept, rejected = check(b.orders, T, lambda tail, e: ing.get((tail, bytes(e).hex())))
    assert len(kept) == len(b.orders) and not rejected
    early = T - 4 * 86400 * NS  # the same candidates decided four days earlier cite records not yet ingested
    _, rej = check(b.orders, early, lambda tail, e: ing.get((tail, bytes(e).hex())))
    assert rej and all("ingested after" in why for _, why in rej)


def test_group(world):
    _, _, b = world
    g = b.facts["P4-ADVISORY"]
    assert FILM_GROUP <= set(g.members) and set(g.members) - FILM_GROUP == {"TJ107-AVI-202"}
    assert g.p_true[0] < 0.005 and g.p_n >= 380


def test_states(world):
    _, _, b = world
    for i in b.issues:
        want = IssueState.TRIAGED if i.issue_id == "P4-ADVISORY" else IssueState.PROPOSED
        assert i.state == want, i.issue_id
    assert all(m.state == IssueState.MONITORING and m.band is None for m in b.monitoring)
    assert {m.issue_id for m in b.monitoring} >= {"TJ103-ADC-501", "TJ105-FUE-401", "TJ107-ENG-101", "TJ107-SPS-001"}


def test_board_texts(world):
    _, _, b = world
    t = {i.issue_id: (i.title, i.findings[0].reason) for i in b.issues}
    assert t["TJ103-LGB-501"] == ("Gear unsafe warning", "The same warning twice in four days · 15 Jun and 19 Jun")
    assert t["TJ108-AOG-CHUTE"] == ("Waiting for a brake chute", "Grounded 80 days · oldest open AOG demand")
    assert t["TJ105-SPS-501"] == ("JFS start fail", "Four times in ten days")
    assert t["TJ105-TYRE"][0] == "Tyre at 7 of 8 landings"
    assert t["P4-ADVISORY"] == ("Fourteen advisory issues, grouped", "Almost always closed as could-not-duplicate · 6 tails")


def test_findings_on_issues(world):
    _, _, b = world
    for i in b.issues:
        assert isinstance(i, Issue) and i.findings and i.findings[0].engine == "triage"
    tj107 = next(i for i in b.issues if i.issue_id == "TJ107-HYD-101")
    engines = [f.engine for f in tj107.findings]
    assert engines[:2] == ["triage", "episodes"] and {"cnd", "isolation", "similar"} <= set(engines)
    assert (tj107.title, tj107.findings[0].reason) == ("Hydraulic alarm that never clears",
                                                       "34 flights in a row · 30 pump removals found nothing")


def test_build_board_for_the_loop(world):
    store, twin, _ = world
    issues, cands, fun = triage.build_board(store, twin, T)
    assert len(issues) == 9 and len(cands) == 10
    assert all(sem == policies().semver[c.rule] for c, sem in cands)
    assert (fun["alert_rows"], fun["issues"], fun["open"], fun["days"]) == (1192, 326, 33, 168)
    assert triage.run(store, twin, T) == issues


def test_issue_detail_shape(world):
    store, twin, _ = world
    for iid in [*FILM, *EXTRA]:
        d = triage.issue_detail(store, twin, T, iid)
        assert {"id", "tail", "code", "band", "title", "standing", "reco", "facts", "evidence", "rule", "whynot", "donothing"} <= set(d)
        assert {"state", "why", "forecast"} <= set(d["facts"]) and d["reco"]["headline"]
        assert all(r["before_snapshot"] for r in d["evidence"]["rows"])
    d = triage.issue_detail(store, twin, T, "TJ107-HYD-101")
    assert d["reco"]["headline"] == "Stop removing the pump. Troubleshoot the indication path."
    assert d["facts"]["forecast"]["ci"] == "0.986 [0.93, 1.00] · 33 of 33 pumps RTOK"
    assert d["title"] == "TJ107 · hydraulic alarm HYD-101" and d["state"] == "PROPOSED"
    assert d["facts"]["why"]["text"] == "No HYD-101 job in the fleet confirmed a fault. All 33 pumps sent to the shop came back RTOK."
    assert d["facts"]["state"]["text"].startswith("Ten different pumps in that position since 05 Jan")
    assert (d["facts"]["state"]["big"], d["facts"]["state"]["unit"]) == ("30", "pump removals")
    assert d["evidence"]["order_id"] == "phx:P-DEC-01:1.4.0:20260622T0800:TJ107:TROUBLESHOOT:748653aa6bcf4544"
    assert triage.issue_detail(store, twin, T, "NOPE") is None


def test_workbench_tj107(world):
    store, twin, _ = world
    w = triage.workbench(store, twin, T, "TJ107-HYD-101")
    assert w["manual"] == "PHX-FIM-HYD" and len(w["sorties"]) == 61 and sum(x[1] for x in w["sorties"]) == 59
    assert [s["id"] for s in w["suspects"]] == ["IND", "AMAGB", "HYD_PUMP"]
    assert [round(s["p"], 2) for s in w["suspects"]] == [0.56, 0.44, 0.0]
    t1 = w["tests"][0]
    assert (t1["name"], t1["man_h"], t1["robust"]) == ("Indication-path isolation", 7.3, "best in 19 of 24")
    assert [x["value"] for x in w["tests"]] == [1.0, 0.91, 0.0]  # film: 1, 0.91, 0
    assert w["strip"]["note"].endswith("10 serials")  # film: ten pump serials through system 1
    assert len(w["removals"]) == 30  # one removal definition on every screen (golden-22jun.md §4)
    assert triage.workbench(store, twin, T, "TJ108-AOG-CHUTE") is None


def test_day2_tyres_past_the_limit_are_not_gated():
    """23 Jun on the go/no-go run (22 Jun history + one stepped day): tyres 1–2 landings past their 8-landing limit
    with no change on record yet are P3, not gate G3 — the station's own hard-time changes in the fleet history go up
    to 4 landings past the limit (95th percentile of 246 changes)."""
    run = PROTO / "runs" / "gonogo"
    if not (run / "fleet").is_dir():
        pytest.skip("go/no-go run not present")
    from engines import life
    from engines.common import context

    store = Store.for_run(run)
    twin = Twin(store)
    t2 = T + 86400 * NS
    assert life.station_overrun(context(store, twin, t2), "SYN-PN-TYRE") == (4, 246)
    b = triage.evaluate(store, twin, t2)
    tyres = {i.issue_id: i for i in b.issues if i.issue_id.endswith("-TYRE")}
    assert tyres and all(i.band == "P3" and not i.basis.startswith("Gate") for i in tyres.values())
    assert {k: twin.tyre_landings(t2, k.split("-")[0]) for k in tyres} == {
        k: int(b.facts[k].life_used) for k in tyres}  # the same count as the twin's fleet row
    assert tyres["TJ104-TYRE"].findings[0].reason == "2 landings past the limit · the station's own changes go up to 4 past it"
