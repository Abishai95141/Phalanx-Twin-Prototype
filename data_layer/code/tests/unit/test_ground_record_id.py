"""W0.4 A4: record_id is deterministic, injective in its encoding, and pinned by golden values."""

from __future__ import annotations

import hashlib
import struct

import numpy as np
import pyarrow as pa
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.ground.rid import (
    RID_PERSON,
    encode_key,
    from_hex,
    record_id,
    record_ids,
    to_hex,
)

C = load_contract("v0")

SAMPLE_KEY = {
    "provenance": "direct",
    "tail_no": "T001",
    "sortie_id": "T001-20261014T0530Z",
    "channel_id": "direct:FADEC:A",
    "param_id": "ENG.N2",
    "seq": 41,
    "msg_index": 0,
}

# Golden record_ids. A change here changes every stored id: it is a breaking contract change.
GOLDEN = {
    "param.samples": "e81e56fad42b7c1c901411e2adb58750",
    "orders.commands": "760bd52de692b5a6353c70df6784dc3f",
    "orders.status": "c5d1aa84fc50703d45e353b8c0872f71",
    "labels.truth": "92fdbdf961463513dbcc60779cc0405e",
}
GOLDEN_INPUTS = {
    "param.samples": SAMPLE_KEY,
    "orders.commands": {"order_id": "ORD-0001"},
    "orders.status": {"order_id": "ORD-0001", "status_seq": 2},
    "labels.truth": {
        "label_kind": "TRUTH_SAMPLE",
        "subject_id": "ENG.N2",
        "tail_no": "T001",
        "sortie_id": None,
        "serial_no": None,
        "related_record_id": bytes(range(16)),
        "t_true": -5,
    },
}


@pytest.mark.unit
@pytest.mark.golden
@pytest.mark.parametrize("topic", sorted(GOLDEN))
def test_a4_golden_record_ids(topic):
    assert to_hex(record_id(C, topic, GOLDEN_INPUTS[topic])) == GOLDEN[topic]


@pytest.mark.unit
def test_a4_definition_matches_spec_text():
    """The id is blake2b-128, person 'phalanx.rid.v0', over the documented byte encoding."""
    rid = record_id(C, "param.samples", SAMPLE_KEY)
    s = lambda x: b"S" + struct.pack("<I", len(x.encode())) + x.encode()  # noqa: E731
    data = (
        s("param.samples")
        + s("direct")
        + s("T001")
        + s("T001-20261014T0530Z")
        + s("direct:FADEC:A")
        + s("ENG.N2")
        + b"U"
        + struct.pack("<Q", 41)
        + b"U"
        + struct.pack("<Q", 0)
    )
    assert rid == hashlib.blake2b(data, digest_size=16, person=b"phalanx.rid.v0").digest()
    assert RID_PERSON == C.record_id_rules["person"].encode()
    assert C.record_id_rules["digest_bytes"] == 16


@pytest.mark.unit
@pytest.mark.parametrize(
    ("a", "b"),
    [
        ([("str", "ab"), ("str", "c")], [("str", "a"), ("str", "bc")]),  # boundary shift
        ([("str", None)], [("str", "")]),  # null vs empty
        ([("u64", 1)], [("i64", 1)]),  # same number, different type
        ([("str", "1")], [("u64", 1)]),
        ([("rid", bytes(16))], [("rid", None)]),
        ([("str", "x"), ("u64", 0)], [("str", "x"), ("u64", 0), ("u64", 0)]),  # arity
    ],
)
def test_a4_encoding_distinguishes_near_misses(a, b):
    assert encode_key("t", a) != encode_key("t", b)
    assert encode_key("t", a) != encode_key("u", a)  # topic is part of the identity


@pytest.mark.unit
@pytest.mark.parametrize("topic", sorted(GOLDEN))
def test_a4_vectorised_equals_scalar(topic):
    base = GOLDEN_INPUTS[topic]
    key = C.topics[topic].record_id_key
    n = 7
    cols, rows = {}, [dict(base) for _ in range(n)]
    for i, r in enumerate(rows):
        for k in key:
            if k.type == "str" and r[k.name] is not None:
                r[k.name] = f"{r[k.name]}-{i % 3}"
            elif k.type in ("u64", "i64"):
                r[k.name] = int(r[k.name]) + i
    for k in key:
        vals = [r[k.name] for r in rows]
        if k.type == "str":
            cols[k.name] = pa.array(vals, pa.string())
        elif k.type == "rid":
            cols[k.name] = pa.array(vals, pa.binary(16))
        else:
            cols[k.name] = np.array(vals, dtype=np.int64)
    vec = record_ids(C, topic, cols, n).to_pylist()
    assert vec == [record_id(C, topic, r) for r in rows]


@pytest.mark.unit
def test_a4_scalar_broadcast_and_errors():
    n = 3
    vec = record_ids(C, "param.samples", {**SAMPLE_KEY, "seq": np.arange(n)}, n).to_pylist()
    assert vec == [record_id(C, "param.samples", {**SAMPLE_KEY, "seq": i}) for i in range(n)]
    with pytest.raises(KeyError):
        record_id(C, "param.samples", {k: v for k, v in SAMPLE_KEY.items() if k != "seq"})
    with pytest.raises(ValueError):
        record_id(C, "param.samples", {**SAMPLE_KEY, "seq": -1})
    with pytest.raises(ValueError):
        record_ids(C, "param.samples", {**SAMPLE_KEY, "seq": np.array([0, -1, 2])}, 3)
    with pytest.raises(ValueError):
        record_ids(C, "param.samples", {**SAMPLE_KEY, "seq": np.array([0, 1])}, 3)
    with pytest.raises(ValueError):
        record_id(C, "labels.truth", {**GOLDEN_INPUTS["labels.truth"], "related_record_id": b"short"})
    assert record_ids(C, "param.samples", SAMPLE_KEY, 0).to_pylist() == []


@pytest.mark.unit
def test_a4_hex_helpers():
    rid = record_id(C, "orders.commands", {"order_id": "X"})
    assert from_hex(to_hex(rid)) == rid and len(to_hex(rid)) == 32
    for bad in (to_hex(rid).upper(), to_hex(rid)[:-2], "zz" * 16):
        with pytest.raises(ValueError):
            from_hex(bad)
