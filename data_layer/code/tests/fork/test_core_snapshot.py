"""W0.2 A3: snapshot at k -> restore (fresh objects) -> continue to N == uninterrupted run, bitwise.

Sample: toy system with loop, monitor and events, N = 2,400 steps; k in {0, 1, 239, 1201, 2399, 2400} plus
a step where an event is pending in the queue. Each k is checked for three mode pairs (before/after).
"""

from __future__ import annotations

import pytest

from phalanx.core.snapshot import SnapshotError, read_snapshot, restore, snapshot, snapshot_id
from phalanx.core.toy import build_toy_system, default_params, set_stiffness_order

N = 2400
CFG = {"controlled": True, "monitored": True, "fused": True}


def _reference():
    s = build_toy_system(**CFG)
    w, tr = s.run(s.start(), N, mode="step", record=s.output_ports())
    return s, w, tr


@pytest.fixture(scope="module")
def reference():
    return _reference()


def _pending_k(tr):
    """A boundary at which an emitted event is waiting in the queue (dispatched at that step)."""
    return next(k for k, e in tr.dispatched if e.kind == "exceedance" and k > 1)


@pytest.mark.fork
@pytest.mark.parametrize("k", [0, 1, 239, 1201, 2399, 2400, "pending"])
@pytest.mark.parametrize("modes", [("block", "block"), ("step", "block"), ("block", "step")])
def test_snapshot_restore_continue_is_bitwise_identical(reference, k, modes):
    s_ref, w_ref, tr_ref = reference
    if k == "pending":
        k = _pending_k(tr_ref)
    s1 = build_toy_system(**CFG)
    w1, tr1 = s1.run(s1.start(), k, mode=modes[0], record=s1.output_ports())
    snap = snapshot(s1, w1)
    if k == _pending_k(tr_ref):
        assert len(read_snapshot(snap).queue) > 0 and len(w1.queue) == 1  # an event really is pending
    s2 = build_toy_system(**CFG)  # fresh modules, fresh RNG service, fresh memo caches
    w2 = restore(s2, snap)
    assert snapshot(s2, w2) == snap  # restore -> snapshot is the identity on bytes
    w3, tr2 = s2.run(w2, N - k, mode=modes[1], record=s2.output_ports())
    assert snapshot(s2, w3) == snapshot(s_ref, w_ref)
    assert tr1.concat(tr2).digest() == tr_ref.digest()


@pytest.mark.fork
def test_snapshot_is_self_describing_versioned_and_tamper_evident(reference):
    s_ref, w_ref, _ = reference
    snap = snapshot(s_ref, w_ref, parent="root")
    info = read_snapshot(snap)
    h = info.header
    assert h["format"] == 1 and h["k"] == N and h["parent"] == "root"
    assert [m["id"] for m in h["modules"]] == ["ctrl", "truth", "sensor", "monitor", "counter"]
    assert h["rng"]["bit_generator"] == "Philox" and h["config_hash"] == s_ref.config_hash
    assert info.id == snapshot_id(snap) and len(info.id) == 64
    # flip one byte inside the truth module's state blob
    blob = info.module_states["truth"]
    pos = snap.index(blob) + len(blob) - 3
    bad = snap[:pos] + bytes([snap[pos] ^ 1]) + snap[pos + 1 :]
    with pytest.raises(SnapshotError, match="digest"):
        read_snapshot(bad)
    assert snapshot_id(bad) != info.id


@pytest.mark.fork
def test_strict_restore_refuses_a_different_world(reference):
    s_ref, w_ref, _ = reference
    snap = snapshot(s_ref, w_ref)
    with pytest.raises(SnapshotError, match="RNG identity"):
        restore(build_toy_system(root=0x1234, **CFG), snap)
    ps = default_params()
    ps["truth"] = ps["truth"].replace(damping=0.7)
    changed = build_toy_system(params=ps, **CFG)
    with pytest.raises(SnapshotError, match="config hash"):
        restore(changed, snap)
    w = restore(changed, snap, strict=False)  # an explicit parameter-change fork is possible
    assert w.k == N
    with pytest.raises(SnapshotError, match="module order"):
        restore(build_toy_system(controlled=True, fused=True), snap, strict=False)


@pytest.mark.fork
def test_order_log_travels_with_the_snapshot():
    s = build_toy_system(**CFG)
    w, _ = s.run(s.start(), 100)
    w = s.inject(w, [set_stiffness_order(w.t_ns, 45.0)])
    snap = snapshot(s, w)
    w2 = restore(build_toy_system(**CFG), snap)
    assert w2.order_log == w.order_log and read_snapshot(snap).header["n_orders"] == 1
    assert w2.queue.get_state() == w.queue.get_state()


@pytest.mark.fork
def test_negative_control_held_outputs_are_part_of_the_world(reference):
    """Dropping the held port values on restore breaks continuation (so the A3 test can fail).

    ``ctrl.u`` is a held output, not part of the controller's state; at a non-tick boundary (k % 3 != 0)
    truth needs it on the very next step.
    """
    s_ref, w_ref, _ = reference
    k = 1201
    s1 = build_toy_system(**CFG)
    w1, _ = s1.run(s1.start(), k)
    s2 = build_toy_system(**CFG)
    w2 = restore(s2, snapshot(s1, w1))
    w2.held["ctrl.u"] = s2.modules["ctrl"].initial_outputs(w2.states["ctrl"])["u"]
    w3, _ = s2.run(w2, N - k)
    assert snapshot(s2, w3) != snapshot(s_ref, w_ref)
