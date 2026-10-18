"""W1.1 A4 for M04: remnant draws are indexed by the absolute tick, so a branch that receives a different plan
at
the fork (a re-plan order) shares every remnant draw with the unchanged branch (CRN audit, I8), while its
trajectory differs; identical suffixes give identical branches.

Sample: the short sortie of tests/integration/test_pilot_module.py from take-off; parent 6,000 ticks, suffix
6,000 ticks (the remnant stream is consumed 18,000 times in the suffix).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import DrawLedger, crn_audit
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import truth_step_time_ns
from phalanx.pilot.module import PLAN_EVENT
from phalanx.scenario import phases as PH
from phalanx.scenario.plan import S_ALT, S_HDG

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from test_pilot_module import build, short_plan

K, N = 6000, 12000


def _rebuild(plan, ledger):
    return build(plan, start_phase=PH.TAKEOFF, ledger=ledger)


@pytest.fixture(scope="module")
def setup():
    plan = short_plan()
    s = _rebuild(plan, None)
    w, _ = s.run(s.start(), K)
    return plan, snapshot(s, w), s.t0_plan


def _branch(plan, snap, events=(), ledger=None):
    s = _rebuild(plan, ledger)
    w = restore(s, snap)
    if events:
        w = s.inject(w, list(events))
    w, tr = s.run(w, N - K, record=["pilot.stick_pitch", "pilot.stick_roll", "af.alt"])
    return s, w, tr


@pytest.mark.fork
def test_replan_order_shares_the_remnant_draws(setup):
    plan, snap, t0 = setup
    seg_f = np.array(plan.seg_f, copy=True)
    seg_f[:, S_ALT] += 2000.0  # a re-plan: everything 2 km higher and a quarter turn to the right
    seg_f[:, S_HDG] = (seg_f[:, S_HDG] + np.pi / 2) % (2 * np.pi)
    other = dataclasses.replace(plan, seg_f=seg_f)
    ev = Event(truth_step_time_ns(K), PLAN_EVENT, "pilot", other.to_payload(t_kernel0_ns=t0))
    la, lb = DrawLedger(), DrawLedger()
    _, _wa, ta = _branch(plan, snap, (), la)
    _, _wb, tb = _branch(plan, snap, (ev,), lb)
    assert not np.array_equal(
        ta.ports["pilot.stick_roll"], tb.ports["pilot.stick_roll"]
    )  # the order had an effect
    rep = crn_audit(la, lb)
    assert not rep.values_differ and not rep.consumption_differs
    remnant = [p for p in rep.identical if "component=s:remnant" in p]
    assert remnant  # the per-tick remnant stream is shared bitwise
    assert all("component=s:aar" in p for p in rep.only_in_b)  # re-plan re-reads the AAR closures (same keys)


@pytest.mark.fork
def test_identical_suffixes_give_identical_branches(setup):
    plan, snap, _ = setup
    sa, wa, _ = _branch(plan, snap)
    sb, wb, _ = _branch(plan, snap)
    assert snapshot(sa, wa) == snapshot(sb, wb)
