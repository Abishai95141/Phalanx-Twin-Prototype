"""W0.4 A8: Avro schemas generated from the contract; structural validity; Arrow -> Avro -> Arrow round trip.

Structural checks run the Avro 1.11 schema rules and the inverse mapping field by field; the binary round trip
encodes and decodes EXAMPLE records of every topic with the pinned ``fastavro`` (a hard dependency since main
70e7844, so the test fails rather than skips if it is missing).
"""

from __future__ import annotations

import io

import pyarrow as pa
import pytest

from phalanx.dictionary.contract import load_contract
from phalanx.dictionary.contract.avro_gen import arrow_type_via_avro, avro_to_arrow, check_avro_schema
from phalanx.dictionary.contract.examples import example_records

C = load_contract("v0")


@pytest.mark.unit
@pytest.mark.parametrize("topic", C.topic_names)
def test_a8_avro_schema_structurally_valid(topic):
    s = C.avro_schema(topic)
    assert check_avro_schema(s) == []
    assert s["namespace"] == "phalanx.contract.v0"
    assert s["phalanx.contract_hash"] == C.hash


@pytest.mark.unit
@pytest.mark.parametrize("topic", C.topic_names)
def test_a8_arrow_avro_arrow_roundtrip(topic):
    back = avro_to_arrow(C.avro_schema(topic))
    expected = C.schemas[topic]
    assert back.names == expected.names
    for e, b in zip(expected, back, strict=True):
        assert b.nullable == e.nullable, e.name
        assert b.type.equals(arrow_type_via_avro(e.type)), (e.name, b.type, e.type)


@pytest.mark.unit
def test_a8_avro_mapping_details():
    s = C.avro_schema("param.samples")
    f = {x["name"]: x for x in s["fields"]}
    assert f["record_id"]["type"] == {"type": "fixed", "name": "RecordId", "size": 16}
    assert f["t_sample"]["type"] == "long" and f["t_sample"]["phalanx.time_unit"] == "ns"
    assert f["t_bus"]["type"] == ["null", "long"] and f["t_bus"]["default"] is None
    assert f["validity"]["type"]["type"] == "enum"
    assert f["validity"]["type"]["symbols"] == list(C.enums["Validity"].names)
    assert f["quality_flags"]["type"] == "long"  # uint32 does not fit Avro int
    # a named type used twice is defined once and then referenced by full name
    m = {x["name"]: x for x in C.avro_schema("maint.records")["fields"]}
    assert m["record_id"]["type"] == {"type": "fixed", "name": "RecordId", "size": 16}
    assert m["evidence_record_ids"]["type"] == {"type": "array", "items": "phalanx.contract.v0.RecordId"}


BAD_AVRO = {
    "bad name": {"type": "record", "name": "1bad", "fields": []},
    "duplicate field": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": "int"}, {"name": "a", "type": "int"}],
    },
    "undefined reference": {"type": "record", "name": "r", "fields": [{"name": "a", "type": "Nope"}]},
    "nested union": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": ["null", ["int", "long"]]}],
    },
    "duplicate union branch": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": ["int", "int"]}],
    },
    "default not matching first branch": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": ["int", "null"], "default": None}],
    },
    "named type twice": {
        "type": "record",
        "name": "r",
        "fields": [
            {"name": "a", "type": {"type": "fixed", "name": "F", "size": 2}},
            {"name": "b", "type": {"type": "fixed", "name": "F", "size": 2}},
        ],
    },
    "bad enum symbol": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": {"type": "enum", "name": "E", "symbols": ["a-b"]}}],
    },
    "zero fixed size": {
        "type": "record",
        "name": "r",
        "fields": [{"name": "a", "type": {"type": "fixed", "name": "F", "size": 0}}],
    },
}


@pytest.mark.unit
@pytest.mark.parametrize("case", sorted(BAD_AVRO))
def test_a8_structural_check_catches_violations(case):
    assert check_avro_schema(BAD_AVRO[case]), case


@pytest.mark.unit
@pytest.mark.parametrize("topic", C.topic_names)
def test_a8_binary_roundtrip_through_avro(topic):
    """Arrow records -> Avro binary (object container) -> Arrow, lossless, for every topic (n = 4 rows each,
    alternating null / value in every nullable field, so both union branches are exercised)."""
    import fastavro

    table = example_records(C, topic, 4)
    schema = fastavro.parse_schema(C.avro_schema(topic))
    buf = io.BytesIO()
    fastavro.writer(buf, schema, table.to_pylist())
    buf.seek(0)
    rows = list(fastavro.reader(buf))
    back = pa.Table.from_pylist(rows, schema=C.schemas[topic])
    assert back.equals(table, check_metadata=True)
    C.validate(topic, back)
    # the schema fastavro reads back from the container is the generated one
    buf.seek(0)
    assert fastavro.reader(buf).writer_schema["name"] == f"phalanx.contract.v0.{topic.replace('.', '_')}"
