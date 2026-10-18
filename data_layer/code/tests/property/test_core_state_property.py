"""W0.2 A2 (property tier): encode/decode round-trips bitwise for generated flat trees.

n = 300 generated trees (hypothesis, derandomized): random names, dtypes (bool, ints, uints, floats incl.
NaN/inf/-0, complex, bytes, unicode) and shapes up to 3-D.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from phalanx.core.state import decode_tree, encode_tree, tree_digest, trees_equal

DTYPES = st.sampled_from(
    ["|b1", "<i1", "<i4", "<i8", "|u1", "<u2", "<u8", "<f4", "<f8", "<c16", "|S4", "<U3"]
)
names = st.from_regex(r"[a-z_][a-z0-9_]{0,10}", fullmatch=True)


@st.composite
def trees(draw):
    keys = draw(st.lists(names, min_size=0, max_size=6, unique=True))
    out = {}
    for k in keys:
        dt = np.dtype(draw(DTYPES))
        shape = draw(hnp.array_shapes(min_dims=0, max_dims=3, min_side=0, max_side=4))
        out[k] = draw(hnp.arrays(dt, shape))
    return out


@pytest.mark.property
@settings(max_examples=300, derandomize=True, deadline=None)
@given(t=trees(), version=st.integers(0, 2**31))
def test_round_trip_bitwise(t, version):
    b = encode_tree(t, kind="module_state", name="prop", version=version)
    d = decode_tree(b, kind="module_state")
    assert d.version == version
    assert trees_equal(d.tree, t)
    assert encode_tree(d.tree, kind="module_state", name="prop", version=version) == b
    assert tree_digest(d.tree) == tree_digest(t)
