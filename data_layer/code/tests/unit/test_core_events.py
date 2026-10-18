"""W0.2 A9: deterministic event ordering under ties; the queue round-trips through its state bytes.

Hand-built cases (n <= 10 events each); generated sequences: tests/property/test_core_events_property.py.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event, EventError, EventQueue, event_log_digest
from phalanx.core.state import StateError


def _ev(t, kind="tick", prio=0, **payload):
    return Event(t, kind, "mod", payload, priority=prio)


@pytest.mark.unit
def test_ties_resolve_by_priority_then_insertion_order():
    q = EventQueue()
    q.push(_ev(10, "a"))
    q.push(_ev(5, "b", prio=2))
    q.push(_ev(5, "c", prio=1))
    q.push(_ev(5, "d", prio=1))
    q.push(_ev(10, "e", prio=-1))
    q.push(_ev(10, "f"))
    assert [q.pop().kind for _ in range(6)] == ["c", "d", "b", "e", "a", "f"]


@pytest.mark.unit
def test_pop_due_respects_time():
    q = EventQueue()
    q.push(_ev(100))
    q.push(_ev(200))
    assert q.pop_due(99) is None
    assert q.pop_due(100).t_ns == 100
    assert q.next_time() == 200 and len(q) == 1


@pytest.mark.unit
def test_state_round_trip_preserves_pending_order_and_sequence():
    q = EventQueue()
    for t, k, p in [(30, "x", 0), (10, "y", 0), (30, "z", 0), (10, "w", 1), (20, "v", 0)]:
        q.push(_ev(t, k, p, value=float(t) / 3, n=t, label=k, arr=np.arange(3) * t))
    q.pop()  # one already consumed: next_seq (5) must survive, not be re-derived from the pending events
    b = q.get_state()
    r = EventQueue.from_state(b)
    assert r.get_state() == b and r.next_seq == 5
    assert [e.key for e in r.pending()] == [e.key for e in q.pending()]
    a1, a2 = q.push(_ev(10, "new")), r.push(_ev(10, "new"))
    assert a1 == a2 and a1.seq == 5
    out_q = [q.pop() for _ in range(len(q))]
    out_r = [r.pop() for _ in range(len(r))]
    assert out_q == out_r
    assert [e.kind for e in out_q] == ["new", "w", "v", "x", "z"]  # (10,0,5) < (10,1,3) < (20,..) < (30,..)
    assert out_q[1].payload["arr"].tolist() == [0, 10, 20]
    with pytest.raises(StateError):
        EventQueue.from_state(b"XXXX" + b[4:])


@pytest.mark.unit
def test_event_validation_and_payload_normalisation():
    e = Event(5, "set_stiffness", "truth", {"value": 1.5, "n": 3, "on": True, "who": "ab"})
    assert e.payload["value"].dtype == np.float64 and e.payload["n"].dtype == np.int64
    assert e.payload["on"].dtype == np.bool_ and str(e.payload["who"]) == "ab"
    with pytest.raises(ValueError):
        e.payload["value"][...] = 2.0  # payloads are immutable
    for bad in (
        lambda: Event(-1, "k", "m"),
        lambda: Event(1, "Bad Kind", "m"),
        lambda: Event(1, "k", "has space"),
        lambda: Event(1.0, "k", "m"),
        lambda: Event(1, "k", "m", {"o": np.array([object()])}),
    ):
        with pytest.raises(EventError):
            bad()
    assert Event.decode(e.encode()) == e
    assert event_log_digest([e]) != event_log_digest([e, e])
