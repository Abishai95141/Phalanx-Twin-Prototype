"""W0.2 A2 (I2): get_state . set_state round-trips exactly for every toy module (and the event queue).

n = 150 generated states per module (hypothesis, derandomized; floats include NaN/inf/-0 and extremes),
plus 40 states reached by actually running the system for a random number of steps (0-600).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from phalanx.core.events import EventQueue
from phalanx.core.state import trees_equal
from phalanx.core.toy import build_toy_system

SYSTEM = build_toy_system(controlled=True, monitored=True, fused=True, sampled=True)
MODULES = [SYSTEM.modules[m] for m in SYSTEM.order]


@st.composite
def state_for(draw, module):
    tree = {}
    for f in module.state_schema.fields:
        shape = tuple(draw(st.integers(0, 4)) if s is None else s for s in f.shape)
        tree[f.name] = draw(hnp.arrays(np.dtype(f.dtype), shape))
    return tree


@pytest.mark.property
@pytest.mark.parametrize("module", MODULES, ids=[m.id for m in MODULES])
def test_generated_states_round_trip(module):
    @settings(max_examples=150, derandomize=True, deadline=None)
    @given(state=state_for(module))
    def check(state):
        b = module.get_state(state)
        back = module.set_state(b)
        assert trees_equal(back, state)
        assert module.get_state(back) == b

    check()


@pytest.mark.property
@settings(max_examples=40, derandomize=True, deadline=None)
@given(n=st.integers(0, 600))
def test_states_reached_by_running_round_trip(n):
    s = build_toy_system(controlled=True, monitored=True, fused=True, sampled=True)
    w, _ = s.run(s.start(), n)
    for mid in s.order:
        m = s.modules[mid]
        b = m.get_state(w.states[mid])
        assert trees_equal(m.set_state(b), w.states[mid])
    q = w.queue.get_state()
    assert EventQueue.from_state(q).get_state() == q
