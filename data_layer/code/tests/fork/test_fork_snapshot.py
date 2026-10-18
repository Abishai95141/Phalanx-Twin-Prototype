"""A5/A7: snapshot -> restore -> continue is bitwise identical; identical order suffixes give identical
branches; the snapshot round-trips queues, inventories, in-transit spares, the shop pipeline and pending
events.

Sample: one 6-tail fleet; snapshots at day 40 (busy maintenance state); 30-day continuation (n = 1 per check:
the comparisons are exact).
"""

from __future__ import annotations

import numpy as np
import pytest
from test_fork_fixture_fleet import DAY, EPOCH, FixtureFleetBuilder

from phalanx.core.snapshot import SnapshotError, read_snapshot, snapshot
from phalanx.core.state import trees_equal
from phalanx.fork.kpi import compute_kpis
from phalanx.fork.service import BranchSpec, ForkService
from phalanx.fork.session import OpsSession
from phalanx.maintenance.docstate import decode_doc
from phalanx.maintenance.world import LOC_DEPOT, LOC_SHOP
from phalanx.orders.model import Order

ROOT = 0x5A5A
T_SNAP = 40 * DAY
HORIZON = 30 * DAY


def _parent():
    b = FixtureFleetBuilder(n_tails=6, horizon_days=80)
    s = OpsSession(b, ROOT)
    s.run_until(T_SNAP)
    return b, s


@pytest.mark.fork
def test_snapshot_restore_continue_is_bitwise_identical():
    b, s = _parent()
    snap = s.snapshot()
    restored = OpsSession.restore(b, snap)
    s.run_until(T_SNAP + HORIZON)
    restored.run_until(T_SNAP + HORIZON)
    assert restored.log.digest == s.log.digest
    assert snapshot(restored.system, restored.world) == snapshot(s.system, s.world)
    k1 = compute_kpis(s.log, b.m18_cfg, t0_utc=EPOCH + T_SNAP, t1_utc=EPOCH + T_SNAP + HORIZON, tails=b.tails)
    res = ForkService(b, b.m18_cfg).run(snap, BranchSpec("o"), HORIZON)
    assert res.kpis == k1 and res.record_digest == s.log.digest


@pytest.mark.fork
def test_identical_suffixes_give_identical_branches_and_different_suffixes_differ():
    b, s = _parent()
    snap = s.snapshot()
    fs = ForkService(b, b.m18_cfg)
    t = b.calendar.next_epoch(T_SNAP + DAY)
    suffix = [
        Order(
            "SFX-1",
            "H",
            "HUMAN",
            EPOCH + t,
            EPOCH + t,
            "GROUND",
            {"reason": "what-if"},
            target_tail_no=b.tails[0],
        )
    ]
    r1 = fs.run(snap, BranchSpec("a", orders=suffix), HORIZON)
    r2 = fs.run(snap, BranchSpec("a2", orders=suffix), HORIZON)
    r0 = fs.run(snap, BranchSpec("none"), HORIZON)
    assert r1.record_digest == r2.record_digest and r1.order_log_hash == r2.order_log_hash
    assert r1.record_digest != r0.record_digest and r1.kpis.mc < r0.kpis.mc


@pytest.mark.fork
def test_snapshot_round_trips_queues_inventories_transit_and_pending_events():
    b, s = _parent()
    # put spares in transit and orders in the queue at the snapshot instant
    s.submit(
        [
            Order(
                "TR-1",
                "H",
                "HUMAN",
                s.t_utc,
                s.t_utc,
                "REQUISITION_SPARES",
                {"part_no": "SYN-PN-RADAR", "quantity": 1},
                priority="MCM",
                target_base="SUL",
            )
        ]
    )
    s.run_until(T_SNAP + DAY)
    st = s.world.states["m18"]
    demands = decode_doc(st["doc_supply"])["demands"]
    assert demands, "open demands (in-transit wholesale spares) must exist at the snapshot"
    assert np.any(np.isin(st["ser_loc"], [LOC_SHOP, LOC_DEPOT])), "shop/depot pipeline must be non-empty"
    assert len(s.world.queue) > 0
    snap = s.snapshot()
    info = read_snapshot(snap.core)
    assert info.header["n_orders"] == len(s.world.order_log)
    r = OpsSession.restore(b, snap)
    for mid in s.system.order:
        assert trees_equal(r.world.states[mid], s.world.states[mid]), mid
    assert r.world.queue.get_state() == s.world.queue.get_state()
    assert r.world.order_log == s.world.order_log
    assert snapshot(r.system, r.world) == snapshot(s.system, s.world)  # same content bytes after a restore
    assert r.snapshot().parent == snap.id and r.snapshot().id != snap.id  # lineage is recorded
    bad = bytearray(snap.core)
    bad[-5] ^= 0xFF
    with pytest.raises(SnapshotError):
        read_snapshot(bytes(bad))
