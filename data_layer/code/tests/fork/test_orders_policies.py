"""Reference policies (architecture §11.2) act as their configuration says, through the orders channel only.

A-W1.8-22 exposing tests. Sample: one fixture run per policy: 6 tails x 120 days for the scheduled policy,
with intervals shortened to 20 / 45 FH so every tail gets several orders; 3 tails x 40 days with raised BIT
and exceedance rates for the condition-based policy. Every issued order is checked; the scheduled test needs
at least 10 consecutive-order intervals.
"""

from __future__ import annotations

import copy
import itertools
from collections import defaultdict
from dataclasses import replace

import pytest
from test_fork_fixture_fleet import DAY, FixtureFleetBuilder, FixtureParams

from phalanx.fork.service import BranchSpec, ForkService
from phalanx.fork.session import OpsSession
from phalanx.orders.policies import ConditionBasedPolicy, ScheduledPolicy, load_policy_config


def _status(s):
    st = {}
    for r in s.records("orders.status"):
        st[r["order_id"]] = r["status"]
    return st


@pytest.mark.fork
def test_scheduled_policy_issues_washes_and_borescopes_at_its_flight_hour_intervals():
    cfg = copy.deepcopy(load_policy_config("scheduled"))
    cfg["rules"]["engine_wash"]["every_fh"] = 20.0
    cfg["rules"]["borescope"]["every_fh"] = 45.0
    b = FixtureFleetBuilder(n_tails=6, horizon_days=120)
    res = ForkService(b, b.m18_cfg).run(
        OpsSession(b, 0x5C4ED).snapshot(),
        BranchSpec("sched", policy=ScheduledPolicy(config=cfg)),
        120 * DAY,
        keep_session=True,
    )
    s = res.session
    cmds = s.records("orders.commands")
    st = _status(s)
    assert cmds and all(st[c["order_id"]] == "COMPLETED" for c in cmds), "every preventive order is executed"
    sorties = defaultdict(list)
    for r in s.records("maint.records"):
        if r["record_type"] == "SORTIE":
            sorties[r["tail_no"]].append((int(r["t_ingest"]), float(r["flight_hours"])))
    n_checked = 0
    for action, itype, every in (("WASH_SERVICE", "WASH", 20.0), ("INSPECT", "BORESCOPE", 45.0)):
        for tail in b.tails:
            issued = sorted(
                int(c["t_issued"]) for c in cmds if c["action"] == action and c["target_tail_no"] == tail
            )
            total = sum(fh for _, fh in sorties[tail])
            # one order per `every` flight hours (the last interval may be incomplete or still pending)
            assert int(total // every) - 1 <= len(issued) <= int(total // every), (
                action,
                tail,
                total,
                issued,
            )
            for t0, t1 in itertools.pairwise(issued):
                flown = sum(fh for t, fh in sorties[tail] if t0 < t <= t1)
                assert flown >= every - 1e-9, (action, tail, flown)
                n_checked += 1
            done = [
                r
                for r in s.records("maint.records")
                if r["record_type"] == "INSPECTION"
                and r["tail_no"] == tail
                and r["inspection_type"] == itype
                and r["status"] == "CLOSED"
            ]
            assert len(done) == len(issued)
    assert n_checked >= 10, n_checked


@pytest.mark.fork
def test_condition_based_policy_acts_on_ingested_evidence_at_its_thresholds():
    p = replace(FixtureParams(), fa_per_fh=1.0, fa_codes=("NAV-310",), p_exceed_per_sortie=0.15)
    b = FixtureFleetBuilder(n_tails=3, horizon_days=40, p=p)
    pol = ConditionBasedPolicy()
    rules = pol.config["rules"]
    res = ForkService(b, b.m18_cfg).run(
        OpsSession(b, 0xCB4).snapshot(), BranchSpec("cbm", policy=pol), 40 * DAY, keep_session=True
    )
    s = res.session
    events = {r["record_id"]: r for t in ("events.bit_faults", "events.exceedances") for r in s.records(t)}
    cmds = [c for c in s.records("orders.commands") if c["issuer_id"] == "PLANNER-CBM"]
    st = _status(s)
    ts = [c for c in cmds if c["action"] == "TROUBLESHOOT"]
    bs = [c for c in cmds if c["action"] == "INSPECT"]
    assert ts and bs, (len(ts), len(bs))
    for c in ts + bs:
        rule = "bit_recurrence" if c["action"] == "TROUBLESHOOT" else "exceedance_borescope"
        window = int(float(rules[rule]["window_days"]) * 86_400) * 1_000_000_000
        ev = [events[rid] for rid in c["evidence"]]
        assert len(ev) >= int(rules[rule]["min_events"])
        assert all(e["tail_no"] == c["target_tail_no"] for e in ev)
        assert all(e["t_ingest"] <= c["t_issued"] and e["t_occurrence"] >= c["t_issued"] - window for e in ev)
        if rule == "bit_recurrence":
            assert {e["event_code"] for e in ev} == {c["parameters"]["code"]}
        assert st[c["order_id"]] in ("COMPLETED", "REJECTED")
    # a troubleshoot order ends the deferral: the monitored job is worked and closed
    closed_after = [
        r
        for r in s.records("maint.records")
        if r["record_type"] == "DEFECT_WO"
        and r["status"] == "CLOSED"
        and r["action_taken_code"] in ("AT-RR", "AT-CND")
        and "NAV-310" in (r["discrepancy_text"] or "")
    ]
    assert closed_after
