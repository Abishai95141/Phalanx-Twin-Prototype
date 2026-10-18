"""A4 event sourcing: replaying the order log of a live closed-loop session reproduces it bit for bit; orders
are idempotent on order_id at fleet scale.

Sample: one 5-tail fleet, 50 days, condition-based policy issuing orders at every daily epoch (n = 1 live
session and its replay; equality is exact, so one non-trivial session answers the question).
"""

from __future__ import annotations

import pytest
from test_fork_fixture_fleet import DAY, FixtureFleetBuilder

from phalanx.core.snapshot import snapshot
from phalanx.fork.service import BranchSpec, ForkService
from phalanx.fork.session import OpsSession
from phalanx.orders.policies import ConditionBasedPolicy
from phalanx.orders.replay import dump_order_log, load_order_log, order_log_hash, replay

ROOT = 0xC0FFEE


@pytest.mark.fork
def test_replay_of_the_order_log_reproduces_the_live_session_bitwise():
    b = FixtureFleetBuilder(n_tails=5, horizon_days=50)
    live = ForkService(b, b.m18_cfg).run(
        OpsSession(b, ROOT).snapshot(),
        BranchSpec("live", policy=ConditionBasedPolicy()),
        50 * DAY,
        keep_session=True,
    )
    log = live.session.world.order_log
    assert len(log) >= 3, "the policy must have issued orders"
    data = dump_order_log(log)
    events = load_order_log(data)
    assert order_log_hash(events) == order_log_hash(log) == live.order_log_hash
    rep = replay(OpsSession(b, ROOT), events, 50 * DAY)
    assert rep.log.digest == live.record_digest
    assert snapshot(rep.system, rep.world) == snapshot(live.session.system, live.session.world)
    # a different log is a different run (the comparison can fail)
    rep2 = replay(OpsSession(b, ROOT), events[:-1], 50 * DAY)
    assert rep2.log.digest != live.record_digest


@pytest.mark.fork
def test_resent_orders_are_no_ops_after_a_restore():
    b = FixtureFleetBuilder(n_tails=3, horizon_days=20)
    s = OpsSession(b, ROOT)
    s.run_until(2 * DAY)
    from phalanx.orders.model import Order

    o = Order(
        "RS-1", "H", "HUMAN", s.t_utc, s.t_utc, "INSPECT", {"type": "BORESCOPE"}, target_tail_no=b.tails[0]
    )
    assert [r.verdict for r in s.submit([o])] == ["ACCEPTED"]
    snap = s.snapshot()
    s2 = OpsSession.restore(b, snap)
    before = snapshot(s2.system, s2.world)
    assert [r.verdict for r in s2.submit([o])] == ["DUPLICATE"]  # idempotency memory travels with the world
    assert snapshot(s2.system, s2.world) == before
