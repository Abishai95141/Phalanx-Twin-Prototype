"""W0.4 A7 (contract side): batches validate against the generated schema; malformed batches are rejected.

Each negative case breaks exactly one rule of a valid batch and must raise ContractViolation naming it. The
positive controls show that valid batches of every topic pass, so the negatives are not passing vacuously.
"""

from __future__ import annotations

import pyarrow as pa
import pyarrow.compute as pc
import pytest

from phalanx.dictionary.contract import ContractViolation, load_contract
from phalanx.dictionary.contract.examples import example_records

C = load_contract("v0")


def _set(
    table: pa.Table, name: str, values: list, typ: pa.DataType | None = None, nullable: bool | None = None
):
    i = table.schema.get_field_index(name)
    f = table.schema.field(i)
    f = pa.field(
        f.name, typ or f.type, nullable=f.nullable if nullable is None else nullable, metadata=f.metadata
    )
    return table.set_column(i, f, pa.array(values, type=f.type))


@pytest.mark.unit
@pytest.mark.parametrize("topic", C.topic_names)
def test_a7_valid_examples_of_every_topic_pass(topic):
    t = example_records(C, topic, 4)
    C.validate(topic, t)  # positive control
    assert t.schema.equals(C.schemas[topic], check_metadata=True)


def _ps() -> pa.Table:
    return example_records(C, "param.samples", 4)


NEGATIVE = {
    "missing column": (lambda t: t.drop_columns(["units"]), "missing=['units']"),
    "extra column": (lambda t: t.append_column("extra", pa.array([1] * t.num_rows)), "extra=['extra']"),
    "reordered columns": (
        lambda t: t.select([t.schema.names[1], t.schema.names[0], *t.schema.names[2:]]),
        "order",
    ),
    "wrong type": (
        lambda t: _set(t, "t_sample", [float(v) for v in t.column("t_sample").to_pylist()], pa.float64()),
        "t_sample: type double",
    ),
    "nullability flag differs": (
        lambda t: _set(t, "units", t.column("units").to_pylist(), nullable=True),
        "nullable",
    ),
    "null in non-nullable": (lambda t: _set(t, "units", [None, "%", "%", "%"]), "units: 1 null(s)"),
    "enum value outside table": (
        lambda t: _set(t, "validity", ["NORMAL", "OK", "NORMAL", "NORMAL"]),
        "not in enum Validity",
    ),
    "reserved flag bit": (
        lambda t: _set(t, "quality_flags", [0, 1 << 20, 0, 0]),
        "reserved QualityFlags bits",
    ),
    "NaN value": (lambda t: _set(t, "value_eu", [1.0, float("nan"), 1.0, 1.0]), "NaN/inf"),
    "infinite value": (lambda t: _set(t, "value_eu", [1.0, float("inf"), 1.0, 1.0]), "NaN/inf"),
    "negative time": (
        lambda t: _set(t, "t_sample", [-5, *t.column("t_sample").to_pylist()[1:]]),
        "negative time",
    ),
    "pattern violation": (
        lambda t: _set(t, "rt_sa_word", ["RT40/SA01/W01", None, "RT05/SA12/W02", None]),
        "rt_sa_word: 1 value(s) do not match",
    ),
    "unsafe tail_no": (lambda t: _set(t, "tail_no", ["T/1", "X1", "X2", "X3"]), "tail_no: 1 value(s)"),
    "ingest before sample": (
        lambda t: _set(t, "t_ingest", [v - 1 for v in t.column("t_sample").to_pylist()]),
        "check t_ingest >= t_sample: violated by 4",
    ),
    "bus before sample": (
        lambda t: _set(t, "t_bus", [v - 1 for v in t.column("t_sample").to_pylist()]),
        "check t_bus >= t_sample",
    ),
    "duplicate record_id": (
        lambda t: _set(t, "record_id", [t.column("record_id")[0].as_py()] * t.num_rows),
        "record_id: 3 duplicate(s)",
    ),
}


@pytest.mark.unit
@pytest.mark.parametrize("case", sorted(NEGATIVE))
def test_a7_malformed_param_samples_rejected(case):
    mutate, expect = NEGATIVE[case]
    bad = mutate(_ps())
    with pytest.raises(ContractViolation) as ei:
        C.validate("param.samples", bad)
    assert any(expect in e for e in ei.value.errors), ei.value.errors


@pytest.mark.unit
def test_a7_nested_violations_rejected():
    t = example_records(C, "events.bit_faults", 2)  # row 0 has one suspect LRU
    i = t.schema.get_field_index("suspect_lrus")
    f = t.schema.field(i)
    bad = t.set_column(i, f, pa.array([[{"lru": "FADEC", "isolation_confidence": 1.5}], []], f.type))
    with pytest.raises(ContractViolation, match=r"above maximum 1\.0"):
        C.validate("events.bit_faults", bad)
    bad = t.set_column(i, f, pa.array([[{"lru": None, "isolation_confidence": 0.5}], []], f.type))
    with pytest.raises(ContractViolation, match=r"suspect_lrus\[\]\.lru: 1 null"):
        C.validate("events.bit_faults", bad)
    bad = t.set_column(i, f, pa.array([[None], []], f.type))
    with pytest.raises(ContractViolation, match=r"suspect_lrus\[\]: 1 null"):
        C.validate("events.bit_faults", bad)


@pytest.mark.unit
def test_a7_conditional_and_json_rules():
    t = example_records(C, "orders.status", 2)
    st = t.set_column(
        t.schema.get_field_index("status"), t.schema.field("status"), pa.array(["REJECTED", "ACCEPTED"])
    )
    st = st.set_column(
        st.schema.get_field_index("reason"), st.schema.field("reason"), pa.array([None, None], pa.string())
    )
    with pytest.raises(ContractViolation, match="reason required when status == REJECTED"):
        C.validate("orders.status", st)
    ok = st.set_column(
        st.schema.get_field_index("reason"), st.schema.field("reason"), pa.array(["no stock", None])
    )
    C.validate("orders.status", ok)

    o = example_records(C, "orders.commands", 2)
    j = o.schema.get_field_index("parameters")
    for text, msg in (
        ('{"b": 1, "a": 2}', "not in canonical form"),
        ("[1]", "not an object"),
        ("{", "not valid JSON"),
    ):
        bad = o.set_column(j, o.schema.field(j), pa.array([text, "{}"]))
        with pytest.raises(ContractViolation, match=msg):
            C.validate("orders.commands", bad)


@pytest.mark.unit
def test_a7_consumer_audience_requires_consumer_schema():
    from phalanx.dictionary.contract import validate_table

    full = example_records(C, "sortie.manifest", 2)
    cs = C.consumer_schema("sortie.manifest")
    consumer = pa.Table.from_arrays([full.column(n) for n in cs.names], schema=cs)
    validate_table(C, "sortie.manifest", consumer, audience="consumer")
    with pytest.raises(ContractViolation, match="extra"):
        validate_table(C, "sortie.manifest", full, audience="consumer")
    assert "root_seed" not in consumer.schema.names
    assert pc.all(pc.equal(consumer.column("tail_no"), full.column("tail_no"))).as_py()
