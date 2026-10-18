"""W0.2 A2 (codec part): canonical, versioned, pickle-free state encoding; schema validation.

Deterministic hand-built trees (n = a handful per case); the generated-tree property lives in
tests/property/test_core_state_property.py.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from phalanx.core.state import (
    Field,
    StateError,
    StateSchema,
    decode_tree,
    encode_tree,
    freeze,
    tree_digest,
    trees_equal,
)


def _tree():
    nan_payload = np.frombuffer(np.uint64(0x7FF8_0000_DEAD_BEEF).tobytes(), dtype="<f8")[0]
    return {
        "x": np.array(-0.0),
        "v": np.array([1.5, np.inf, -np.inf, nan_payload]),
        "k": np.array(2**62, dtype=np.int64),
        "flags": np.array([True, False]),
        "name": np.array(["ab", "c"]),
        "raw": np.array([2**64 - 1], dtype=np.uint64),
        "empty": np.zeros((0, 3)),
    }


@pytest.mark.unit
def test_round_trip_is_bitwise_including_nan_payloads_and_negative_zero():
    t = _tree()
    b = encode_tree(t, kind="module_state", name="s", version=3)
    d = decode_tree(b, kind="module_state")
    assert (d.name, d.version) == ("s", 3)
    assert trees_equal(d.tree, t)
    assert np.signbit(d.tree["x"])
    assert d.tree["v"][3:].tobytes() == t["v"][3:].tobytes()  # NaN payload bits preserved
    assert encode_tree(d.tree, kind="module_state", name="s", version=3) == b
    d.tree["v"][0] = 7.0  # decoded arrays are writable copies, not views of the bytes
    assert decode_tree(b).tree["v"][0] == 1.5


@pytest.mark.unit
def test_bytes_independent_of_insertion_order_and_byte_order():
    t = _tree()
    rev = dict(reversed(list(t.items())))
    be = {
        k: (v.astype(v.dtype.newbyteorder(">")) if v.dtype.byteorder not in "|" else v) for k, v in t.items()
    }
    kw = {"kind": "k", "name": "n", "version": 1}
    assert encode_tree(t, **kw) == encode_tree(rev, **kw) == encode_tree(be, **kw)
    assert tree_digest(t) == tree_digest(rev)


@pytest.mark.unit
def test_header_is_canonical_json_and_tampering_is_rejected():
    b = encode_tree({"a": np.arange(3)}, kind="k", name="n", version=1)
    hlen = int.from_bytes(b[5:9], "little")
    header = json.loads(b[9 : 9 + hlen])
    assert header["fields"][0][:3] == ["a", "<i8", [3]]
    with pytest.raises(StateError):
        decode_tree(b"XXXX" + b[4:])
    with pytest.raises(StateError):
        decode_tree(b + b"\x00")  # trailing payload
    spaced = json.dumps(header).encode()  # same content, non-canonical whitespace
    with pytest.raises(StateError):
        decode_tree(b[:5] + len(spaced).to_bytes(4, "little") + spaced + b[9 + hlen :])
    with pytest.raises(StateError):
        decode_tree(b, kind="other_kind")


@pytest.mark.unit
def test_object_and_structured_dtypes_are_rejected():
    with pytest.raises(StateError):
        encode_tree({"o": np.array([object()])}, kind="k", name="n", version=1)
    with pytest.raises(StateError):
        encode_tree({"s": np.zeros(2, dtype=[("a", "<f8")])}, kind="k", name="n", version=1)
    with pytest.raises(StateError):
        encode_tree({"bad key": np.zeros(1)}, kind="k", name="n", version=1)


@pytest.mark.unit
def test_schema_validation_catches_each_mismatch():
    s = StateSchema("s", 1, (Field("x", "<f8"), Field("buf", "<f8", (None, 2)), Field("n", "<i8")))
    ok = s.make(x=1.0, buf=np.zeros((5, 2)), n=3)
    s.validate(ok)
    assert s.names == ("buf", "n", "x")
    bad = [
        ({**ok, "extra": np.zeros(1)}, "undeclared"),
        ({k: v for k, v in ok.items() if k != "n"}, "missing"),
        ({**ok, "x": np.array(1.0, np.float32)}, "dtype"),
        ({**ok, "buf": np.zeros((5, 3))}, "shape"),
        ({**ok, "x": 1.0}, "not an array"),
    ]
    for tree, word in bad:
        with pytest.raises(StateError, match=word):
            s.validate(tree)
    with pytest.raises(StateError):
        StateSchema("s", 1, (Field("x", "<f8"), Field("x", "<i8")))
    with pytest.raises(StateError):
        Field("Bad", "<f8")


@pytest.mark.unit
def test_freeze_makes_in_place_mutation_fail():
    t = freeze({"x": np.zeros(3)})
    with pytest.raises(ValueError):
        t["x"][0] = 1.0
