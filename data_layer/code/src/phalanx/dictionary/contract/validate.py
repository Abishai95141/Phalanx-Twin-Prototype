"""Batch validation against the generated contract schema (W0.4 acceptance A7).

Arrow does not enforce field nullability on data (a non-nullable field can hold nulls), and it knows nothing
about enum tables, reserved flag bits, NaN, patterns or cross-field invariants. ``validate_table`` checks all
of them, so every batch that crosses the contract boundary (fast path, full path, storage) is held to the
spec.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.compute as pc

from .model import FieldSpec, TypeSpec

if TYPE_CHECKING:
    from .model import Contract

_MAX_ERRORS = 50


class ContractViolation(ValueError):
    """A batch does not conform to the contract. ``errors`` lists every violation found."""

    def __init__(self, topic: str, errors: list[str]):
        self.topic = topic
        self.errors = tuple(errors)
        shown = "\n  - ".join(errors[:_MAX_ERRORS])
        more = f"\n  ... and {len(errors) - _MAX_ERRORS} more" if len(errors) > _MAX_ERRORS else ""
        super().__init__(f"{topic}: {len(errors)} contract violation(s):\n  - {shown}{more}")


def _check_schema(expected: pa.Schema, got: pa.Schema, errors: list[str]) -> None:
    if expected.names != got.names:
        missing = [n for n in expected.names if n not in got.names]
        extra = [n for n in got.names if n not in expected.names]
        errors.append(f"field names/order differ: missing={missing} extra={extra} got_order={got.names}")
        return
    for e, g in zip(expected, got, strict=True):
        if not e.type.equals(g.type):
            errors.append(f"{e.name}: type {g.type} != contract type {e.type}")
        if e.nullable != g.nullable:
            errors.append(f"{e.name}: nullable={g.nullable} but contract says nullable={e.nullable}")


def _any(arr: pa.Array | pa.ChunkedArray) -> bool:
    v = pc.any(arr).as_py()
    return bool(v)


def _check_values(
    contract: Contract, f: FieldSpec, arr: pa.ChunkedArray | pa.Array, path: str, errors: list[str]
) -> None:
    if not f.nullable and arr.null_count:
        errors.append(f"{path}: {arr.null_count} null(s) in a non-nullable field")
    t: TypeSpec = f.type
    if len(arr) == arr.null_count:
        return
    if t.kind == "primitive":
        name = t.name
        if name == "float64":
            bad = pc.invert(pc.is_finite(arr))
            if _any(bad):
                errors.append(f"{path}: {pc.sum(bad).as_py()} NaN/inf value(s); the contract carries no NaN")
        if name == "time_ns":
            lo = pc.min(arr).as_py()
            if lo is not None and lo < 0:
                errors.append(f"{path}: negative time {lo} (all contract times are >= 0)")
        if f.minimum is not None or f.maximum is not None:
            mm = pc.min_max(arr).as_py()
            if f.minimum is not None and mm["min"] is not None and mm["min"] < f.minimum:
                errors.append(f"{path}: value {mm['min']} below minimum {f.minimum}")
            if f.maximum is not None and mm["max"] is not None and mm["max"] > f.maximum:
                errors.append(f"{path}: value {mm['max']} above maximum {f.maximum}")
        if f.pattern is not None:
            ok = pc.match_substring_regex(arr, f.pattern)
            nbad = int(pc.sum(pc.invert(ok)).as_py() or 0)
            if nbad:
                sample = pc.filter(arr, pc.invert(ok)).slice(0, 3).to_pylist()
                errors.append(f"{path}: {nbad} value(s) do not match {f.pattern} (e.g. {sample})")
        if name == "json_object":
            for i, s in enumerate(arr.to_pylist()):
                if s is None:
                    continue
                try:
                    obj = json.loads(s)
                except ValueError:
                    errors.append(f"{path}[{i}]: not valid JSON")
                    continue
                if not isinstance(obj, dict):
                    errors.append(f"{path}[{i}]: JSON value is not an object")
                elif s != canonical_json_text(obj):
                    errors.append(f"{path}[{i}]: JSON text is not in canonical form")
    elif t.kind == "enum":
        assert t.name is not None
        symbols = pa.array(contract.enums[t.name].names, pa.string())
        present = pc.drop_null(arr)
        ok = pc.is_in(present, value_set=symbols)
        bad = pc.filter(present, pc.invert(ok))
        if len(bad):
            errors.append(f"{path}: values {sorted(set(bad.to_pylist()))[:5]} not in enum {t.name}")
    elif t.kind == "flags":
        assert t.name is not None
        reserved = contract.flag_sets[t.name].reserved_mask
        hit = pc.bit_wise_and(arr, pa.scalar(reserved, arr.type))
        if _any(pc.not_equal(hit, pa.scalar(0, arr.type))):
            errors.append(f"{path}: reserved {t.name} bits set (reserved mask 0x{reserved:08x})")
    elif t.kind == "list":
        assert t.item is not None
        values = pc.list_flatten(arr)
        item = FieldSpec(
            name=f"{f.name}[]",
            type=t.item,
            nullable=t.item_nullable,
            description="list item",
            basis="ARCH §12",
        )
        _check_values(contract, item, values, f"{path}[]", errors)
    elif t.kind == "struct":
        chunks = arr.chunks if isinstance(arr, pa.ChunkedArray) else [arr]
        for sub in t.fields:
            parts = []
            for ch in chunks:
                valid = ch.filter(ch.is_valid())
                parts.append(valid.field(sub.name))
            _check_values(
                contract, sub, pa.chunked_array(parts, type=parts[0].type), f"{path}.{sub.name}", errors
            )


def canonical_json_text(obj: object) -> str:
    """Canonical JSON text (sorted keys, compact separators, no NaN) used for json_object fields."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def validate_table(
    contract: Contract,
    topic: str,
    table: pa.Table,
    *,
    require_unique_record_ids: bool = True,
    audience: str = "full",
) -> None:
    """Validate ``table`` as a batch of ``topic`` records; raise :class:`ContractViolation` on any violation.

    Checks: exact field names, order, types and nullability flags; nulls in non-nullable fields (top level and
    nested); enum membership; reserved flag bits; NaN/inf; non-negative times; patterns; numeric ranges;
    canonical JSON objects; the topic's row invariants (``checks``); record_id uniqueness within the batch.

    Args:
        audience: ``"full"`` (producer side, restricted fields present) or ``"consumer"`` (restricted fields
            absent).
    """
    if topic not in contract.topics:
        raise KeyError(f"unknown topic {topic!r}")
    spec = contract.topics[topic]
    expected = contract.schemas[topic] if audience == "full" else contract.consumer_schema(topic)
    errors: list[str] = []
    _check_schema(expected, table.schema, errors)
    if errors:
        raise ContractViolation(topic, errors)
    fields = [f for f in spec.fields if audience == "full" or not f.restricted]
    for f in fields:
        _check_values(contract, f, table.column(f.name), f.name, errors)
    present = set(table.schema.names)
    for c in spec.checks:
        if c.check == "order":
            left, right, op = c.get("left"), c.get("right"), c.get("op")
            if left not in present or right not in present:
                continue
            a, b = table.column(left), table.column(right)
            bad = pc.less(a, b) if op == ">=" else pc.less_equal(a, b)
            n = int(pc.sum(bad).as_py() or 0)
            if n:
                errors.append(f"check {left} {op} {right}: violated by {n} row(s)")
        elif c.check == "required_if":
            fld, when, eq = c.get("field"), c.get("when_field"), c.get("equals")
            cond = pc.and_(pc.equal(table.column(when), pa.scalar(eq)), pc.is_null(table.column(fld)))
            n = int(pc.sum(cond).as_py() or 0)
            if n:
                errors.append(f"check {fld} required when {when} == {eq}: missing in {n} row(s)")
    if require_unique_record_ids and table.num_rows:
        distinct = pc.count_distinct(table.column("record_id")).as_py()
        if distinct != table.num_rows:
            errors.append(f"record_id: {table.num_rows - distinct} duplicate(s) within the batch")
    if errors:
        raise ContractViolation(topic, errors)
