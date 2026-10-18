"""W0.2 A9 (property tier): pop order == sort by (t, priority, insertion); snapshot round trip at any cut.

n = 300 generated push/pop programs (hypothesis, derandomized); times and priorities are drawn from small
ranges so ties are frequent.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.events import Event, EventQueue

ops = st.lists(
    st.one_of(st.tuples(st.just("push"), st.integers(0, 5), st.integers(-1, 1)), st.just(("pop",))),
    max_size=60,
)


@pytest.mark.property
@settings(max_examples=300, derandomize=True, deadline=None)
@given(program=ops, cut=st.integers(0, 60))
def test_order_is_total_and_survives_round_trip(program, cut):
    q = EventQueue()
    model: list[tuple[int, int, int]] = []  # (t, prio, insertion index)
    popped, ins = [], 0
    for i, op in enumerate(program):
        if i == cut:
            q = EventQueue.from_state(q.get_state())  # snapshot/restore in the middle of the program
        if op[0] == "push":
            q.push(Event(op[1], "e", "m", {"i": ins}, priority=op[2]))
            model.append((op[1], op[2], ins))
            ins += 1
        elif model:
            model.sort()
            want = model.pop(0)
            got = q.pop()
            popped.append(got)
            assert (got.t_ns, got.priority, int(got.payload["i"])) == want
            assert got.seq == want[2]
    assert len(q) == len(model)
