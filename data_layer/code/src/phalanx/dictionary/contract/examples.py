"""EXAMPLE records for every contract topic, generated from the spec (documentation and interface tests).

EXAMPLE DATA: these rows satisfy the contract's types, nullability, enums, patterns, ranges and row
invariants, but they carry no physical meaning. They are never simulation output and must never be used as
such. Generation is spec-driven and deterministic, so a new field is covered automatically.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from .model import FieldSpec, TypeSpec

if TYPE_CHECKING:
    from .model import Contract

EXAMPLE_EPOCH_NS = 1_791_000_000 * 10**9  # 2026-10-03T03:20:00Z, an arbitrary instant on the sim UTC calendar

# Candidate string templates, tried in order against a field's pattern ({i} = row index).
_STRING_CANDIDATES = (
    "X{i}",
    "A{i}",
    "RT05/SA12/W{i:02d}",
    "L203/SDI{j}",
    "0123456789abcdef" * 2,
    "0123456789abcdef" * 4,
)


def _example_string(f: FieldSpec | None, i: int) -> str:
    if f is None or f.pattern is None:
        return f"example-{i}"
    for tpl in _STRING_CANDIDATES:
        s = tpl.format(i=i, j=i % 4)
        if re.match(f.pattern, s):
            return s
    raise ValueError(f"no example string matches {f.pattern}")


def _example_value(c: Contract, t: TypeSpec, f: FieldSpec | None, i: int) -> Any:
    if t.kind == "enum":
        assert t.name is not None
        return c.enums[t.name].names[0]
    if t.kind == "flags":
        return 0
    if t.kind == "list":
        assert t.item is not None
        return [_example_value(c, t.item, None, i)] if i % 2 == 0 else []
    if t.kind == "struct":
        return {sub.name: _example_value(c, sub.type, sub, i) for sub in t.fields}
    n = t.name
    if n == "string":
        return _example_string(f, i)
    if n == "bool":
        return i % 2 == 0
    if n == "float64":
        lo = f.minimum if f is not None else None
        hi = f.maximum if f is not None else None
        if lo is not None and hi is not None:
            return (lo + hi) / 2
        return (lo or 0.0) + 1.5 + i
    if n == "time_ns":
        if f is not None and f.time_scale == "recorder_rtc":
            return 100 * (i + 1)
        return EXAMPLE_EPOCH_NS + i * 10**9
    if n == "record_id":
        return bytes([i % 256]) * 16
    if n == "json_object":
        return "{}"
    return i  # integers


def example_records(contract: Contract, topic: str, n: int = 3) -> pa.Table:
    """``n`` valid EXAMPLE records of ``topic`` (nullable fields alternate value / null by row)."""
    from phalanx.ground.rid import record_ids  # local import: ground depends on the contract

    spec = contract.topics[topic]
    cols: dict[str, list[Any]] = {f.name: [] for f in spec.fields}
    for i in range(n):
        for f in spec.fields:
            if f.name == "record_id":
                cols[f.name].append(None)  # filled below
            elif f.nullable and i % 2 == 1:
                cols[f.name].append(None)
            else:
                cols[f.name].append(_example_value(contract, f.type, f, i))
    # required_if checks: make the conditional field present
    for ch in spec.checks:
        if ch.check == "required_if":
            fld, when, eq = ch.get("field"), ch.get("when_field"), ch.get("equals")
            for i in range(n):
                if cols[when][i] == eq and cols[fld][i] is None:
                    cols[fld][i] = _example_value(contract, spec.field(fld).type, spec.field(fld), i)
    comps: dict[str, Any] = {}
    for k in spec.record_id_key:
        if k.source == "column":
            comps[k.name] = pa.array(cols[k.name], pa.binary(16) if k.type == "rid" else None)
        else:
            comps[k.name] = "example" if k.type == "str" else pa.array(list(range(n)), pa.uint64())
    cols["record_id"] = record_ids(contract, topic, comps, n).to_pylist()
    table = pa.Table.from_pydict(cols, schema=contract.schemas[topic])
    contract.validate(topic, table)
    return table
