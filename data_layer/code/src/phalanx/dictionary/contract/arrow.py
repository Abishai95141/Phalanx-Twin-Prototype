"""Spec -> ``pyarrow.Schema`` generation (AD-13: Arrow schemas are the single schema source).

Mapping (A-W0.4-9, AD-35):

=============  ==========================================  ======================================
spec type      Arrow type                                  field metadata
=============  ==========================================  ======================================
string         string                                      pattern (if any)
bool           bool
intN / uintN   intN / uintN                                minimum / maximum (if any)
float64        float64 (NaN forbidden by validation)       units, minimum / maximum
time_ns        int64                                       time_unit=ns, time_scale
record_id      fixed_size_binary(16)                       format=record_id
json_object    string (canonical JSON text)                format=json_object
enum:E         string                                      enum=E, enum_symbols=[...]
flags:F        uint32                                      flags=F, flag_bits={name: bit}
list           list<element: T> (Parquet-compliant name)
struct         struct<...>
=============  ==========================================  ======================================

Every field also carries ``phalanx.description``, ``phalanx.basis`` and ``phalanx.restricted``. Schema
metadata carries the contract name, version and hash, the topic, its event and ingest time fields and its
partitioning.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

import pyarrow as pa

from .model import FieldSpec, TypeSpec

if TYPE_CHECKING:
    from .model import Contract

META = "phalanx."

_PRIMITIVE_ARROW: Mapping[str, pa.DataType] = {
    "string": pa.string(),
    "bool": pa.bool_(),
    "int8": pa.int8(),
    "int16": pa.int16(),
    "int32": pa.int32(),
    "int64": pa.int64(),
    "uint8": pa.uint8(),
    "uint16": pa.uint16(),
    "uint32": pa.uint32(),
    "float64": pa.float64(),
    "time_ns": pa.int64(),
    "record_id": pa.binary(16),
    "json_object": pa.string(),
}

#: Width of the flags carrier type. All flag sets are carried as uint32 so a set can grow without a type
#: change.
FLAGS_ARROW = pa.uint32()
LIST_ITEM_NAME = "element"


def arrow_type(contract: Contract, t: TypeSpec) -> pa.DataType:
    if t.kind == "primitive":
        assert t.name is not None
        return _PRIMITIVE_ARROW[t.name]
    if t.kind == "enum":
        return pa.string()
    if t.kind == "flags":
        return FLAGS_ARROW
    if t.kind == "list":
        assert t.item is not None
        item = pa.field(LIST_ITEM_NAME, arrow_type(contract, t.item), nullable=t.item_nullable)
        return pa.list_(item)
    return pa.struct([arrow_field(contract, f) for f in t.fields])


def field_metadata(contract: Contract, f: FieldSpec) -> dict[str, str]:
    md: dict[str, str] = {
        META + "description": f.description,
        META + "basis": f.basis,
        META + "restricted": "true" if f.restricted else "false",
    }
    t = f.type
    if f.units is not None:
        md[META + "units"] = f.units
    if f.minimum is not None:
        md[META + "minimum"] = repr(f.minimum)
    if f.maximum is not None:
        md[META + "maximum"] = repr(f.maximum)
    if f.pattern is not None:
        md[META + "pattern"] = f.pattern
    if t.kind == "primitive" and t.name == "time_ns":
        md[META + "time_unit"] = "ns"
        assert f.time_scale is not None
        md[META + "time_scale"] = f.time_scale
    if t.kind == "primitive" and t.name in ("record_id", "json_object"):
        md[META + "format"] = t.name
    if t.kind == "enum":
        assert t.name is not None
        md[META + "enum"] = t.name
        md[META + "enum_symbols"] = json.dumps(list(contract.enums[t.name].names), separators=(",", ":"))
    if t.kind == "flags":
        assert t.name is not None
        fs = contract.flag_sets[t.name]
        md[META + "flags"] = t.name
        md[META + "flag_bits"] = json.dumps({x.name: x.bit for x in fs.flags}, separators=(",", ":"))
    return md


def arrow_field(contract: Contract, f: FieldSpec) -> pa.Field:
    return pa.field(
        f.name, arrow_type(contract, f.type), nullable=f.nullable, metadata=field_metadata(contract, f)
    )


def restricted_part_keys(contract: Contract, topic: str) -> tuple[str, ...]:
    """Non-restricted fields copied into a topic's restricted part so it can be partitioned, ordered,
    de-duplicated and joined back by record_id: record_id, the partition fields, event and ingest time."""
    spec = contract.topics[topic]
    keys = {"record_id", *spec.partition_by, spec.event_time}
    if spec.ingest_time is not None:
        keys.add(spec.ingest_time)
    return tuple(f.name for f in spec.fields if f.name in keys)


def topic_schema(contract: Contract, topic: str, *, audience: str = "full") -> pa.Schema:
    """Schema of ``topic`` for an audience.

    ``full``: every field (producers, validation). ``consumer``: restricted fields removed (the only schema
    ever written to the consumer tree). ``restricted_part``: the restricted fields of a consumer-visible
    topic plus the join keys (:func:`restricted_part_keys`); written only to the restricted tree.
    """
    spec = contract.topics[topic]
    if audience == "full":
        fields = list(spec.fields)
    elif audience == "consumer":
        fields = [f for f in spec.fields if not f.restricted]
    elif audience == "restricted_part":
        keys = set(restricted_part_keys(contract, topic))
        fields = [f for f in spec.fields if f.restricted or f.name in keys]
    else:
        raise ValueError(f"unknown audience {audience!r}")
    md = {
        META + "contract": contract.name,
        META + "contract_version": contract.version,
        META + "contract_hash": contract.hash,
        META + "topic": spec.name,
        META + "topic_restricted": "true" if spec.restricted else "false",
        META + "event_time": spec.event_time,
        META + "ingest_time": spec.ingest_time or "",
        META + "partition_by": json.dumps(list(spec.partition_by), separators=(",", ":")),
        META + "record_id_key": json.dumps([c.name for c in spec.record_id_key], separators=(",", ":")),
        META + "audience": audience,
    }
    return pa.schema([arrow_field(contract, f) for f in fields], metadata=md)


def build_schemas(contract: Contract) -> dict[str, pa.Schema]:
    return {name: topic_schema(contract, name) for name in contract.topic_names}


def consumer_schema(contract: Contract, topic: str) -> pa.Schema:
    """The downstream view of ``topic``: restricted fields dropped; restricted topics refused (I5)."""
    if contract.topics[topic].restricted:
        raise PermissionError(f"topic {topic} is restricted (truth); it has no consumer view")
    return topic_schema(contract, topic, audience="consumer")


def render_arrow_type(t: pa.DataType) -> str:
    """Stable textual rendering of an Arrow type (independent of pyarrow's repr choices for nesting)."""

    def child(f: pa.Field) -> str:
        return f"{f.name}: {render_arrow_type(f.type)}{'' if f.nullable else ' not null'}"

    if pa.types.is_list(t):
        return f"list<{child(t.value_field)}>"
    if pa.types.is_struct(t):
        return f"struct<{', '.join(child(t.field(i)) for i in range(t.num_fields))}>"
    return str(t)


def _render_field(f: pa.Field) -> list[object]:
    md = sorted((k.decode(), v.decode()) for k, v in (f.metadata or {}).items())
    children: list[object] = []
    t = f.type
    if pa.types.is_list(t):
        children = [_render_field(t.value_field)]
    elif pa.types.is_struct(t):
        children = [_render_field(t.field(i)) for i in range(t.num_fields)]
    return [f.name, render_arrow_type(t), f.nullable, md, children]


def schema_fingerprint(schemas: Mapping[str, pa.Schema]) -> str:
    """blake2b-256 over a canonical rendering of the schemas (names, types, nullability, all metadata)."""
    from .loader import blake2b_hex, canonical_json

    doc = []
    for topic, s in schemas.items():
        md = sorted((k.decode(), v.decode()) for k, v in (s.metadata or {}).items())
        doc.append([topic, [_render_field(f) for f in s], md])
    return blake2b_hex(canonical_json(doc))
