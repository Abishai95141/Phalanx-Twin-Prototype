"""M09 snapshot/restore and fork CRN (A5 snapshot round-trip; architecture §11.2, I8).

Sample: the scripted TEST FIXTURE system (tests/unit/test_utilities_support.py); snapshots at k = 1, 239, 1201
(mid JFS start, mid transfer interruption), suffix to k = 2,400 (10 s).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from test_utilities_support import utility_system

from phalanx.core.events import Event
from phalanx.core.rng import DrawLedger, crn_audit
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import truth_step_time_ns
from phalanx.utilities import layout as L

N = 2400


def _orders():
    return [
        Event(truth_step_time_ns(1000), "util.fault", "util", {"mode": "gen_fail"}),
        Event(truth_step_time_ns(1100), "util.jfs_start", "util", {}),
        Event(truth_step_time_ns(1195), "util.fault", "util", {"mode": "gen_restore"}),
    ]


@pytest.mark.fork
@pytest.mark.parametrize("k", [1, 239, 1201])
def test_snapshot_restore_continues_bitwise(k):
    ref = utility_system()
    w = ref.inject(ref.start(), _orders())
    w_ref, _ = ref.run(w, N)
    a = utility_system()
    wa, _ = a.run(a.inject(a.start(), _orders()), k)
    snap = snapshot(a, wa)
    b = utility_system()
    wb, _ = b.run(restore(b, snap), N - k)
    assert snapshot(b, wb) == snapshot(ref, w_ref)
    if k == 1201:  # the snapshot really caught the JFS mid start and the restored generator transfer
        st = wa.states["util"]
        assert int(st["i"][L.I_JFS_MODE]) != 0 and int(st["i"][L.I_JFS_ATTEMPT]) == 1


@pytest.mark.fork
def test_held_util_outputs_restore_exactly():
    """Held util.* outputs are part of the world snapshot (AD-36: consumers on delayed edges read them after a
    restore); every one comes back bitwise."""
    a = utility_system()
    wa, _ = a.run(a.start(), 500)
    wr = restore(utility_system(), snapshot(a, wa))
    for name, v in wa.held.items():
        if name.startswith("util."):
            assert np.array_equal(wr.held[name], v), name


def _branch(snap, extra, ledger):
    s = utility_system(ledger=ledger)
    w = restore(s, snap)
    w = s.inject(w, [Event(truth_step_time_ns(1300), "util.jfs_start", "util", {}), *extra])
    w2, tr = s.run(w, N - 1200, record=["util.jfs_state", "util.bus_v"])
    return w2, tr


@pytest.mark.fork
def test_fork_branches_share_the_exogenous_ignition_draws():
    """CRN (I8): two branches from one snapshot, one with an extra order (generator fault), consume the JFS
    ignition stream at the same indices with identical values; their trajectories differ."""
    s = utility_system()
    w, _ = s.run(s.start(), 1200)
    snap = snapshot(s, w)
    la, lc = DrawLedger(), DrawLedger()
    _, ta = _branch(snap, [], la)
    _, tc = _branch(snap, [Event(truth_step_time_ns(1250), "util.fault", "util", {"mode": "gen_fail"})], lc)
    assert not np.array_equal(ta.ports["util.bus_v"], tc.ports["util.bus_v"])
    rep = crn_audit(la, lc)
    assert rep.ok, rep
    assert any("jfs_ignition" in p for p in rep.identical)
