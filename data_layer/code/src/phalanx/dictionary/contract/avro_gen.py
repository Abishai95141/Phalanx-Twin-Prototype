"""Arrow/spec -> Avro schema for the v1.x Kafka adapter (AD-13). Generator, structural check and inverse only;
there is no Kafka here.

Mapping (A-W0.4-20): int8/int16/int32/uint8/uint16 -> int; int64/uint32/flags/time_ns -> long; float64 ->
double; bool -> boolean; string/json_object/enum-as-string -> string or Avro enum; record_id -> fixed(16)
``RecordId``; list -> array; struct -> record; nullable -> ["null", T] with default null. Time fields carry
``phalanx.time_unit = "ns"`` because Avro 1.11.1 has no nanosecond logical type (report §13; AD-35).

No Avro library is pinned in the build environment, so :func:`check_avro_schema` validates schemas against the
Avro 1.11 specification rules structurally, and :func:`avro_to_arrow` inverts the mapping so the round trip
Arrow -> Avro -> Arrow can be checked field by field. A binary round trip runs when ``fastavro`` is installed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pyarrow as pa

from .arrow import LIST_ITEM_NAME
from .model import FieldSpec, TypeSpec

if TYPE_CHECKING:
    from .model import Contract

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PRIMITIVES = {"null", "boolean", "int", "long", "float", "double", "bytes", "string"}

_AVRO_PRIMITIVE = {
    "string": "string",
    "bool": "boolean",
    "int8": "int",
    "int16": "int",
    "int32": "int",
    "uint8": "int",
    "uint16": "int",
    "int64": "long",
    "uint32": "long",
    "float64": "double",
    "time_ns": "long",
    "json_object": "string",
}


def namespace(contract: Contract) -> str:
    return f"phalanx.contract.v{contract.version.split('.')[0]}"


def record_name(topic: str) -> str:
    return topic.replace(".", "_")


class _Ctx:
    def __init__(self, contract: Contract):
        self.contract = contract
        self.ns = namespace(contract)
        self.defined: set[str] = set()

    def named(self, name: str, build: Any) -> Any:
        full = f"{self.ns}.{name}"
        if full in self.defined:
            return full
        self.defined.add(full)
        return build()


def _avro_type(ctx: _Ctx, t: TypeSpec, path: str) -> Any:
    if t.kind == "primitive":
        if t.name == "record_id":
            return ctx.named("RecordId", lambda: {"type": "fixed", "name": "RecordId", "size": 16})
        assert t.name is not None
        return _AVRO_PRIMITIVE[t.name]
    if t.kind == "enum":
        assert t.name is not None
        e = ctx.contract.enums[t.name]
        return ctx.named(
            e.name, lambda: {"type": "enum", "name": e.name, "doc": e.description, "symbols": list(e.names)}
        )
    if t.kind == "flags":
        return "long"
    if t.kind == "list":
        assert t.item is not None
        item = _avro_type(ctx, t.item, f"{path}_item")
        return {"type": "array", "items": ["null", item] if t.item_nullable else item}
    name = path
    return ctx.named(
        name,
        lambda: {
            "type": "record",
            "name": name,
            "fields": [_avro_field(ctx, f, f"{path}_{f.name}") for f in t.fields],
        },
    )


def _avro_field(ctx: _Ctx, f: FieldSpec, path: str) -> dict[str, Any]:
    t = _avro_type(ctx, f.type, path)
    out: dict[str, Any] = {"name": f.name, "type": ["null", t] if f.nullable else t, "doc": f.description}
    if f.nullable:
        out["default"] = None
    out["phalanx.basis"] = f.basis
    out["phalanx.restricted"] = f.restricted
    if f.units is not None:
        out["phalanx.units"] = f.units
    if f.type.kind == "primitive" and f.type.name == "time_ns":
        out["phalanx.time_unit"] = "ns"
        out["phalanx.time_scale"] = f.time_scale
    if f.type.kind == "flags":
        out["phalanx.flags"] = f.type.name
    if f.type.kind == "primitive" and f.type.name == "json_object":
        out["phalanx.format"] = "json_object"
    return out


def avro_schema(contract: Contract, topic: str) -> dict[str, Any]:
    """Avro record schema (JSON-ready dict) for ``topic``, generated from the contract (full view)."""
    spec = contract.topics[topic]
    ctx = _Ctx(contract)
    rec = record_name(topic)
    return {
        "type": "record",
        "name": rec,
        "namespace": ctx.ns,
        "doc": spec.description,
        "fields": [_avro_field(ctx, f, f"{rec}_{f.name}") for f in spec.fields],
        "phalanx.contract_version": contract.version,
        "phalanx.contract_hash": contract.hash,
        "phalanx.topic": topic,
        "phalanx.restricted": spec.restricted,
    }


# ---- structural validation (Avro 1.11 specification rules) -------------------------------------------------
def check_avro_schema(schema: Any) -> list[str]:
    """Return a list of violations of the Avro 1.11 schema rules (empty list = structurally valid).

    Checked: primitive and named types; name and namespace syntax; named types defined once and referenced
    only after definition; record field names unique; enum symbols valid and unique; fixed size positive;
    unions non-empty, not directly nested, without duplicate unnamed branches; a field default only on a union
    whose first branch is ``"null"`` with default ``null`` (the only defaults the generator emits).
    """
    errors: list[str] = []
    defined: dict[str, str] = {}

    def fullname(name: str, ns: str | None) -> str:
        return name if "." in name or not ns else f"{ns}.{name}"

    def check_name(name: Any, where: str) -> bool:
        if not isinstance(name, str) or not all(_NAME.match(p) for p in name.split(".")):
            errors.append(f"{where}: invalid name {name!r}")
            return False
        return True

    def walk(t: Any, ns: str | None, where: str) -> str:
        """Returns a branch key for union duplicate detection."""
        if isinstance(t, str):
            if t in _PRIMITIVES:
                return t
            full = fullname(t, ns)
            if full not in defined:
                errors.append(f"{where}: reference to undefined type {t!r}")
            return full
        if isinstance(t, list):
            if not t:
                errors.append(f"{where}: empty union")
            keys = []
            for i, b in enumerate(t):
                if isinstance(b, list):
                    errors.append(f"{where}: union directly contains a union")
                keys.append(walk(b, ns, f"{where}|{i}"))
            if len(set(keys)) != len(keys):
                errors.append(f"{where}: union has duplicate branches {keys}")
            return "union"
        if not isinstance(t, dict) or "type" not in t:
            errors.append(f"{where}: not a schema: {t!r}")
            return "?"
        kind = t["type"]
        if kind in ("record", "enum", "fixed"):
            name = t.get("name")
            if not check_name(name, where):
                return "?"
            ns2 = t.get("namespace", ns)
            if ns2 is not None and not all(_NAME.match(p) for p in ns2.split(".")):
                errors.append(f"{where}: invalid namespace {ns2!r}")
            full = fullname(name, ns2)
            if full in defined:
                errors.append(f"{where}: named type {full} defined twice")
            defined[full] = kind
            if kind == "record":
                fields = t.get("fields")
                if not isinstance(fields, list):
                    errors.append(f"{where}: record without fields list")
                    return full
                names = [f.get("name") for f in fields]
                if len(set(names)) != len(names):
                    errors.append(f"{where}: duplicate field names")
                for f in fields:
                    fw = f"{where}.{f.get('name')}"
                    check_name(f.get("name"), fw)
                    if "type" not in f:
                        errors.append(f"{fw}: field without type")
                        continue
                    walk(f["type"], ns2, fw)
                    if "default" in f:
                        ft = f["type"]
                        if not (isinstance(ft, list) and ft and ft[0] == "null" and f["default"] is None):
                            errors.append(f"{fw}: default must be null on a ['null', ...] union")
            elif kind == "enum":
                syms = t.get("symbols")
                if not isinstance(syms, list) or not syms:
                    errors.append(f"{where}: enum without symbols")
                else:
                    for s in syms:
                        if not isinstance(s, str) or not _NAME.match(s):
                            errors.append(f"{where}: invalid enum symbol {s!r}")
                    if len(set(syms)) != len(syms):
                        errors.append(f"{where}: duplicate enum symbols")
            else:
                size = t.get("size")
                if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                    errors.append(f"{where}: fixed size must be a positive int")
            return full
        if kind == "array":
            walk(t.get("items"), ns, f"{where}[]")
            return "array"
        if kind == "map":
            walk(t.get("values"), ns, f"{where}{{}}")
            return "map"
        if kind in _PRIMITIVES:
            return kind
        errors.append(f"{where}: unknown type {kind!r}")
        return "?"

    if not isinstance(schema, dict) or schema.get("type") != "record":
        errors.append("top level must be a record")
    walk(schema, None, "$")
    return errors


# ---- inverse mapping for the structural round trip ---------------------------------------------------------
def avro_to_arrow(schema: dict[str, Any]) -> pa.Schema:
    """Map an Avro record schema back to Arrow (int -> int32, long -> int64, fixed(n) -> fixed_size_binary(n),
    enum -> string, array -> list<element>, record -> struct, ['null', T] -> nullable T)."""
    named: dict[str, Any] = {}
    ns0 = schema.get("namespace")

    def full(name: str, ns: str | None) -> str:
        return name if "." in name or not ns else f"{ns}.{name}"

    def conv(t: Any, ns: str | None) -> tuple[pa.DataType, bool]:
        if isinstance(t, list):
            nullable = "null" in t
            rest = [b for b in t if b != "null"]
            assert len(rest) == 1, f"only ['null', T] unions are generated, got {t}"
            dt, _ = conv(rest[0], ns)
            return dt, nullable
        if isinstance(t, str):
            prim = {
                "int": pa.int32(),
                "long": pa.int64(),
                "double": pa.float64(),
                "float": pa.float32(),
                "boolean": pa.bool_(),
                "string": pa.string(),
                "bytes": pa.binary(),
            }
            if t in prim:
                return prim[t], False
            return conv(named[full(t, ns)], ns)
        kind = t["type"]
        if kind == "record":
            ns2 = t.get("namespace", ns)
            named[full(t["name"], ns2)] = t
            fields = []
            for f in t["fields"]:
                dt, nl = conv(f["type"], ns2)
                fields.append(pa.field(f["name"], dt, nullable=nl))
            return pa.struct(fields), False
        if kind == "enum":
            named[full(t["name"], t.get("namespace", ns))] = t
            return pa.string(), False
        if kind == "fixed":
            named[full(t["name"], t.get("namespace", ns))] = t
            return pa.binary(t["size"]), False
        if kind == "array":
            dt, nl = conv(t["items"], ns)
            return pa.list_(pa.field(LIST_ITEM_NAME, dt, nullable=nl)), False
        raise ValueError(f"unsupported Avro type {kind}")

    st, _ = conv(schema, ns0)
    return pa.schema([st.field(i) for i in range(st.num_fields)])


def arrow_type_via_avro(t: pa.DataType) -> pa.DataType:
    """The Arrow type a contract type becomes after Arrow -> Avro -> Arrow (the documented lossy
    widenings)."""
    if pa.types.is_list(t):
        v = t.value_field
        return pa.list_(pa.field(LIST_ITEM_NAME, arrow_type_via_avro(v.type), nullable=v.nullable))
    if pa.types.is_struct(t):
        return pa.struct(
            [
                pa.field(t.field(i).name, arrow_type_via_avro(t.field(i).type), nullable=t.field(i).nullable)
                for i in range(t.num_fields)
            ]
        )
    if t in (pa.int8(), pa.int16(), pa.int32(), pa.uint8(), pa.uint16()):
        return pa.int32()
    if t in (pa.int64(), pa.uint32()):
        return pa.int64()
    return t
