"""W0.2 A5 / I8 (property tier): a stream's draws never depend on other streams or on access order.

n = 200 generated scenarios (hypothesis, derandomized): random identity values, random sets of extra
streams declared and consumed (in random order and amounts) before and between reads of a target stream.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate

ROOT = 0xA5A5_0000_1111_2222_3333_4444_5555_6666
ident = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._:+\-]{0,8}", fullmatch=True)
comp = st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)

TARGET = StreamDecl("target", "noise", ("scenario", "tail", "sortie"), Variate.NORMAL, 32)


@pytest.mark.property
@settings(max_examples=200, derandomize=True, deadline=None)
@given(
    tail=ident,
    sortie=st.integers(0, 10**6),
    extra=st.lists(st.tuples(comp, st.integers(0, 300)), max_size=6, unique_by=lambda x: x[0]),
    start=st.integers(0, 500),
    count=st.integers(0, 200),
)
def test_adding_streams_or_consumers_never_perturbs_existing_draws(tail, sortie, extra, start, count):
    path = KeyPath.of(scenario="S", tail=tail, sortie=sortie, subsystem="target", component="noise")
    ref = RngService(ROOT, StreamRegistry([TARGET])).draws(path, start, count)

    reg = StreamRegistry([TARGET])
    for name, _ in extra:  # new streams declared after the fact
        reg.declare(StreamDecl("extra", name, ("scenario", "tail"), Variate.UNIFORM, 16))
    rng = RngService(ROOT, reg)
    for name, n in extra:  # other consumers draw first, in arbitrary amounts
        rng.draws(KeyPath.of(scenario="S", tail=tail, subsystem="extra", component=name), 0, n)
    s = rng.stream(path)
    tail_part = s.draws(start + count // 2, count - count // 2)  # read the second half first
    for name, n in reversed(extra):  # interleaved consumption
        rng.draws(KeyPath.of(scenario="S", tail=tail, subsystem="extra", component=name), n, 7)
    head_part = s.draws(start, count // 2)
    assert np.array_equal(np.concatenate([head_part, tail_part]), ref)
