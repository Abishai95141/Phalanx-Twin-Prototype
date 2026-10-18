"""Property tests for the M01 building blocks: canonical JSON, BNR scaling, 1553 allocation, inventory text
checks.

Hypothesis runs derandomised (fixed example sequence); example counts are stated per test.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from phalanx.dictionary.icd import (
    BUS_GROUP_ORDER,
    Mil1553Item,
    allocate_arinc429,
    allocate_mil1553,
    bnr_lsb,
    fits_word,
    select_word,
)
from phalanx.dictionary.textcheck import contains_number
from phalanx.dictionary.yamlio import canonical_json_bytes, dump_yaml, load_yaml_text

pytestmark = pytest.mark.property

json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(-(10**9), 10**9)
    | st.floats(allow_nan=False, allow_infinity=False, width=64)
    | st.text(max_size=8)
)
json_values = st.recursive(
    json_scalars,
    lambda kids: st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=6), kids, max_size=4),
    max_leaves=20,
)


@settings(max_examples=200, derandomize=True, deadline=None)
@given(json_values)
def test_canonical_json_is_order_independent_and_stable(value):
    def shuffle(v):
        if isinstance(v, dict):
            return {k: shuffle(v[k]) for k in reversed(list(v))}
        if isinstance(v, list):
            return [shuffle(x) for x in v]
        return v

    a = canonical_json_bytes(value)
    assert a == canonical_json_bytes(shuffle(value))
    assert a.isascii()


@settings(max_examples=100, derandomize=True, deadline=None)
@given(json_values)
@example({"\x85": None, "a\u2028b": "c\u2029\x00"})  # NEL and Unicode line breaks (regression)
def test_yaml_round_trip_preserves_values(value):
    """The deterministic dumper and the strict loader agree (what the seeder writes is what the compiler
    reads)."""
    doc = {"root": value}
    assert canonical_json_bytes(load_yaml_text(dump_yaml(doc))) == canonical_json_bytes(doc)


ranges = st.tuples(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
    st.floats(min_value=1e-3, max_value=1e6, allow_nan=False),
).map(lambda t: (t[0], t[0] + t[1]))


@settings(max_examples=300, derandomize=True, deadline=None)
@given(ranges, st.sampled_from([12, 16, 19, 32]))
@example((-1.0, 0.0), 12)  # W0.5-found regression: the negative side holds 2**(n-1) counts, not 2**(n-1)-1
@example((-2048.0, 100.0), 12)
def test_bnr_lsb_fits_and_is_minimal(rng, bits):
    lo, hi = rng
    lsb = bnr_lsb(lo, hi, bits)
    enc = "bnr" if lo < 0 else "ubnr"
    assert math.log2(lsb) == int(math.log2(lsb))  # power of two
    assert fits_word(lo, hi, lsb, enc, bits)
    assert not fits_word(lo, hi, lsb / 2, enc, bits)  # the next finer power of two does not fit


@settings(max_examples=200, derandomize=True, deadline=None)
@given(ranges, st.floats(min_value=1e-4, max_value=10.0))
def test_select_word_always_fits(rng, lsb):
    lo, hi = rng
    try:
        enc, bits = select_word(lo, hi, lsb, transport="mil1553")
    except ValueError:
        assert not fits_word(lo, hi, lsb, "bnr", 32)
        return
    assert fits_word(lo, hi, lsb, enc, bits)
    assert bits in (16, 32)


items_strategy = st.lists(
    st.tuples(
        st.sampled_from(["B1", "B2"]),
        st.integers(1, 3),
        st.sampled_from(["T", "R"]),
        st.sampled_from(BUS_GROUP_ORDER),
        st.integers(1, 2),
    ),
    min_size=1,
    max_size=120,
)


@settings(max_examples=150, derandomize=True, deadline=None)
@given(items_strategy)
def test_mil1553_allocation_never_collides(specs):
    items = [Mil1553Item(f"C{i:04d}", b, rt, tr, g, w) for i, (b, rt, tr, g, w) in enumerate(specs)]
    alloc = allocate_mil1553(items)
    assert set(alloc) == {it.channel_id for it in items}
    used: dict[tuple, str] = {}
    group_of: dict[tuple, str] = {}
    by_id = {it.channel_id: it for it in items}
    for cid, a in alloc.items():
        it = by_id[cid]
        key = (it.bus, it.rt, it.tr, a["sa"])
        assert group_of.setdefault(key, it.group) == it.group  # one rate group per message
        assert 1 <= a["sa"] <= 30 and a["word"] + a["words"] - 1 <= a["message_words"] <= 32
        assert a["validity_word"] < a["word"]
        for w in range(a["word"], a["word"] + a["words"]):
            assert (*key, w) not in used
            used[(*key, w)] = cid
        vk = ("v", *key, a["validity_word"], a["validity_bit"])
        assert vk not in used
        used[vk] = cid
    assert allocate_mil1553(list(reversed(items))) == alloc  # independent of input order


@settings(max_examples=100, derandomize=True, deadline=None)
@given(st.lists(st.tuples(st.sampled_from(["L1", "L2"]), st.sampled_from(["AV25", "AV12.5"])), max_size=150))
def test_arinc429_labels_unique(specs):
    labels = allocate_arinc429([(f"C{i}", link, g) for i, (link, g) in enumerate(specs)])
    seen = set()
    for cid, a in labels.items():
        link = specs[int(cid[1:])][0]
        assert (link, a["label"], a["sdi"]) not in seen and 0 <= a["label"] <= 0o377
        seen.add((link, a["label"], a["sdi"]))


@settings(max_examples=200, derandomize=True, deadline=None)
@given(st.integers(0, 10**6), st.integers(0, 3))
def test_contains_number_finds_written_numbers(n, decimals):
    value = n / 10**decimals
    text = f"range 0-{value:,.{decimals}f} units"
    assert contains_number(text, value)
    assert not contains_number(text, value + 0.5 + 1)
