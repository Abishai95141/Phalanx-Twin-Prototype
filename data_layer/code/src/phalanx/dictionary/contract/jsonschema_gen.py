"""Spec -> JSON-Schema (draft 2020-12) for the JSON-carried topics: manifests and orders (architecture §12
Formats).

A JSON document is one record. Every field is required (present); nullable fields may be ``null``. record_ids
are 32-character lower-case hex; ``json_object`` fields are JSON objects; times are integers (ns). The
consumer view omits restricted fields. :func:`table_to_json_docs` / :func:`json_docs_to_table` convert between
the Arrow and JSON forms of the same records, losslessly.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from .model import INTEGER_RANGES, FieldSpec, TypeSpec
from .validate import canonical_json_text

if TYPE_CHECKING:
    from .model import Contract

DRAFT = "https://json-schema.org/draft/2020-12/schema"
RECORD_ID_HEX_PATTERN = "^[0-9a-f]{32}$"


def _type_schema(contract: Contract, t: TypeSpec, f: FieldSpec | None) -> dict[str, Any]:
    if t.kind == "primitive":
        n = t.name
        if n == "string":
            s: dict[str, Any] = {"type": "string"}
            if f is not None and f.pattern:
                s["pattern"] = f.pattern
            return s
        if n == "bool":
            return {"type": "boolean"}
        if n == "float64":
            s = {"type": "number"}
            if f is not None and f.minimum is not None:
                s["minimum"] = f.minimum
            if f is not None and f.maximum is not None:
                s["maximum"] = f.maximum
            return s
        if n == "record_id":
            return {"type": "string", "pattern": RECORD_ID_HEX_PATTERN}
        if n == "json_object":
            return {"type": "object"}
        assert n is not None
        lo, hi = INTEGER_RANGES[n]
        s = {"type": "integer", "minimum": lo, "maximum": hi}
        if n == "time_ns" and f is not None:
            s["x-phalanx-time-unit"] = "ns"
            s["x-phalanx-time-scale"] = f.time_scale
        return s
    if t.kind == "enum":
        assert t.name is not None
        return {"type": "string", "enum": list(contract.enums[t.name].names)}
    if t.kind == "flags":
        assert t.name is not None
        width = contract.flag_sets[t.name].width
        return {"type": "integer", "minimum": 0, "maximum": 2**width - 1}
    if t.kind == "list":
        assert t.item is not None
        return {"type": "array", "items": _nullable(_type_schema(contract, t.item, None), t.item_nullable)}
    return _object_schema(contract, list(t.fields))


def _nullable(s: dict[str, Any], nullable: bool) -> dict[str, Any]:
    return {"anyOf": [s, {"type": "null"}]} if nullable else s


def _object_schema(contract: Contract, fields: list[FieldSpec]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for f in fields:
        s = _nullable(_type_schema(contract, f.type, f), f.nullable)
        s = {"description": f.description, **s}
        props[f.name] = s
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [f.name for f in fields],
        "properties": props,
    }


def json_schema(contract: Contract, topic: str, *, audience: str = "consumer") -> dict[str, Any]:
    """JSON-Schema for one record of ``topic``. ``audience='consumer'`` omits restricted fields."""
    spec = contract.topics[topic]
    if audience == "consumer" and spec.restricted:
        raise PermissionError(f"topic {topic} is restricted (truth); it has no consumer view")
    fields = [f for f in spec.fields if audience == "full" or not f.restricted]
    doc = {
        "$schema": DRAFT,
        "$id": f"urn:phalanx:contract:{contract.version}:{topic}:{audience}",
        "title": f"{topic} record (Phalanx contract {contract.version})",
        "description": spec.description,
        "x-phalanx-contract-hash": contract.hash,
    }
    doc.update(_object_schema(contract, fields))
    return doc


# ---- Arrow <-> JSON documents ------------------------------------------------------------------------------
def _to_json_value(t: TypeSpec, v: Any) -> Any:
    if v is None:
        return None
    if t.kind == "primitive" and t.name == "record_id":
        return bytes(v).hex()
    if t.kind == "primitive" and t.name == "json_object":
        return json.loads(v)
    if t.kind == "list":
        assert t.item is not None
        return [_to_json_value(t.item, x) for x in v]
    if t.kind == "struct":
        return {f.name: _to_json_value(f.type, v[f.name]) for f in t.fields}
    return v


def _from_json_value(t: TypeSpec, v: Any) -> Any:
    if v is None:
        return None
    if t.kind == "primitive" and t.name == "record_id":
        return bytes.fromhex(v)
    if t.kind == "primitive" and t.name == "json_object":
        return canonical_json_text(v)
    if t.kind == "list":
        assert t.item is not None
        return [_from_json_value(t.item, x) for x in v]
    if t.kind == "struct":
        return {f.name: _from_json_value(f.type, v[f.name]) for f in t.fields}
    return v


def table_to_json_docs(
    contract: Contract, topic: str, table: pa.Table, *, audience: str = "consumer"
) -> list[dict]:
    """Arrow records -> JSON-ready dicts (consumer view drops restricted fields)."""
    spec = contract.topics[topic]
    fields = [f for f in spec.fields if audience == "full" or not f.restricted]
    rows = table.select([f.name for f in fields]).to_pylist()
    return [{f.name: _to_json_value(f.type, r[f.name]) for f in fields} for r in rows]


def json_docs_to_table(
    contract: Contract, topic: str, docs: Iterable[dict], *, audience: str = "full"
) -> pa.Table:
    """JSON documents -> an Arrow table with the contract schema (``audience`` selects the schema)."""
    spec = contract.topics[topic]
    schema = contract.schemas[topic] if audience == "full" else contract.consumer_schema(topic)
    fields = [f for f in spec.fields if audience == "full" or not f.restricted]
    cols: dict[str, list[Any]] = {f.name: [] for f in fields}
    for d in docs:
        for f in fields:
            cols[f.name].append(_from_json_value(f.type, d[f.name]))
    return pa.Table.from_pydict(cols, schema=schema)


def dumps_doc(doc: dict) -> str:
    """Canonical JSON text of one document (sorted keys, compact)."""
    return canonical_json_text(doc)
