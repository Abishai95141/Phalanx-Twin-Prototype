"""W1.1 A4 for M02: identical suffixes give identical branches; a divergent order (grounding one aircraft of
squadron A at the fork) leaves every other exogenous draw untouched (CRN, I8): squadron B's plans are
bitwise identical, and every squadron-A slot flown by the same tail in both branches is identical.

Sample: the two-squadron fleet, fork at day 2 + 37 frames, 4-day suffix (~150 plans per branch).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from phalanx.core.events import Event
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamRegistry, crn_audit
from phalanx.core.scheduler import System
from phalanx.core.snapshot import restore, snapshot
from phalanx.scenario.module import ScenarioModule

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from test_scenario_module import DAY_K, ENV, FLEET, PARAMS, PlanSink

K = 2 * DAY_K + 37
END = 6 * DAY_K


def build(ledger=None):
    fleet = FLEET.__class__(FLEET.name, FLEET.start, 6, FLEET.squadrons, FLEET.surge)
    scen = ScenarioModule("scen", PARAMS, ENV, fleet=fleet, plan_targets=("sink",))
    s = System(
        [scen, PlanSink()],
        [],
        rng=RngService(0xF0, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="crn"),
    )
    return s, scen


@pytest.fixture(scope="module")
def parent():
    s, scen = build()
    w = s.inject(s.start(), scen.initial_events())
    w, _ = s.run(w, K)
    return snapshot(s, w), len(w.states["sink"]["keys"])


def _branch(snap, orders=(), ledger=None):
    s, _ = build(ledger)
    w = restore(s, snap)
    if orders:
        w = s.inject(w, list(orders))
    w, _ = s.run(w, END - K)
    return s, w


def _records(w, n0):
    sk = w.states["sink"]
    return {
        k: (t, d)
        for k, t, d in list(
            zip(sk["keys"].tolist(), sk["tails"].tolist(), sk["digest"].tolist(), strict=True)
        )[n0:]
    }


@pytest.mark.fork
def test_identical_suffixes_give_identical_branches(parent):
    snap, _ = parent
    sa, wa = _branch(snap)
    sb, wb = _branch(snap)
    assert snapshot(sa, wa) == snapshot(sb, wb)


@pytest.mark.fork
def test_grounding_order_shares_every_other_exogenous_draw(parent):
    snap, n0 = parent
    from phalanx.core.time import truth_step_time_ns

    order = Event(truth_step_time_ns(K), "order.tail_status", "scen", {"tail": "TJ105", "available": 0})
    la, lb = DrawLedger(), DrawLedger()
    _, wa = _branch(snap, (), la)
    _, wb = _branch(snap, (order,), lb)
    ra, rb = _records(wa, n0), _records(wb, n0)
    assert ra != rb  # the order had an effect
    assert all(t != "TJ105" for t, _ in rb.values())
    sqb_a = {k: v for k, v in ra.items() if k.startswith("sqb")}
    sqb_b = {k: v for k, v in rb.items() if k.startswith("sqb")}
    assert sqb_a == sqb_b and len(sqb_a) > 20  # the other squadron is untouched
    same_tail = [k for k in ra if k in rb and ra[k][0] == rb[k][0]]
    assert len(same_tail) > 10 and all(ra[k] == rb[k] for k in same_tail)
    rep = crn_audit(la, lb)
    assert not rep.values_differ
    # consumption differs only on squadron-A slots or squadron-A tails (the decision's footprint)
    for path in rep.diverged():
        assert ("sortie=s:sqa" in path) or ("tail=s:TJ1" in path), path
