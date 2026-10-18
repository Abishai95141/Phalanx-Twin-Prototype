"""Load, validate and hash a contract spec version (deliverable 1-2 of W0.4).

The spec is YAML (``spec/v<major>/contract.yaml`` plus ``topics/*.yaml``). Loading is strict: unknown keys,
duplicate YAML keys, missing nullability, unknown types, dangling references and unregistered assumptions are
all errors, because a silently wrong contract is worse than none.

Identity: ``Contract.hash`` is blake2b-256 over the canonical JSON (sorted keys, compact separators, UTF-8) of
the *normalised* spec model, so comments, whitespace, key order and explicit-vs-default values do not change
it, while any semantic edit (a field, a type, a description, a symbol) does.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from .model import (
    PRIMITIVE_TYPES,
    RECORD_ID_COMPONENT_TYPES,
    RECORD_ID_PREFIX_TYPES,
    TIME_SCALES,
    AssumptionRef,
    CheckSpec,
    Contract,
    EnumDef,
    EnumSymbol,
    FieldSpec,
    FlagDef,
    FlagSet,
    RecordIdComponent,
    TopicSpec,
    TypeSpec,
)

SPEC_ROOT = Path(__file__).resolve().parent / "spec"

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_ENUM_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")  # Avro name rule
_FIELD_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_TOPIC_NAME = re.compile(r"^[a-z]+(\.[a-z_]+)+$")
_ASSUMPTION_ID = re.compile(r"^A-W0\.4-\d+$")
_ASSUMPTION_REF = re.compile(r"ASSUMPTION: (A-W0\.4-\d+)")
_BASIS = re.compile(r"(ARCH |TRANSFER: |ASSUMPTION: A-W0\.4-\d+|MEASURED: |DIRECT)")
_FLAG_SCOPES = frozenset({"acquisition", "bus", "recorder", "ground"})
_NUMERIC = frozenset({"int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "float64"})
_UNSIGNED_INT = frozenset({"uint8", "uint16", "uint32"})

_TOP_KEYS = {
    "contract",
    "version",
    "status",
    "description",
    "time",
    "record_id",
    "nan_policy",
    "restriction_policy",
    "enums",
    "flag_sets",
    "field_sets",
    "topics",
    "assumptions",
}
_TOPIC_KEYS = {
    "name",
    "description",
    "basis",
    "restricted",
    "event_time",
    "ingest_time",
    "partition_by",
    "json_schema",
    "record_id_key",
    "checks",
    "fields",
}
_FIELD_KEYS = {
    "name",
    "type",
    "nullable",
    "description",
    "basis",
    "units",
    "time_scale",
    "restricted",
    "pattern",
    "minimum",
    "maximum",
}


class ContractSpecError(ValueError):
    """The spec itself is malformed (not a data violation)."""


class ContractNotFound(LookupError):
    """No spec directory matches the requested version."""


# ---- strict YAML -------------------------------------------------------------------------------------------
class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys (PyYAML silently keeps the last one)."""


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ContractSpecError(f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_StrictLoader)


# ---- helpers -----------------------------------------------------------------------------------------------
def _req(d: dict[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise ContractSpecError(f"{where}: missing required key {key!r}")
    return d[key]


def _nonempty_str(v: Any, where: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ContractSpecError(f"{where}: expected a non-empty string, got {v!r}")
    return v.strip()


def _check_keys(d: Any, allowed: set[str], where: str) -> None:
    if not isinstance(d, dict):
        raise ContractSpecError(f"{where}: expected a mapping, got {type(d).__name__}")
    extra = set(d) - allowed
    if extra:
        raise ContractSpecError(f"{where}: unknown keys {sorted(extra)}")


def _basis(v: Any, where: str) -> str:
    s = _nonempty_str(v, where)
    if not _BASIS.search(s):
        raise ContractSpecError(
            f"{where}: basis {s!r} carries no evidence tag (ARCH/TRANSFER/ASSUMPTION/...)"
        )
    return s


# ---- enums and flags ---------------------------------------------------------------------------------------
def _parse_enums(raw: Any) -> dict[str, EnumDef]:
    if not isinstance(raw, dict) or not raw:
        raise ContractSpecError("enums: expected a non-empty mapping")
    out: dict[str, EnumDef] = {}
    for name, body in raw.items():
        where = f"enums.{name}"
        if not isinstance(name, str) or not _ENUM_NAME.match(name):
            raise ContractSpecError(f"{where}: invalid enum name")
        _check_keys(body, {"basis", "description", "symbols"}, where)
        syms_raw = _req(body, "symbols", where)
        if not isinstance(syms_raw, list) or not syms_raw:
            raise ContractSpecError(f"{where}: symbols must be a non-empty list")
        symbols = []
        for i, s in enumerate(syms_raw):
            _check_keys(s, {"name", "description"}, f"{where}.symbols[{i}]")
            sname = _req(s, "name", f"{where}.symbols[{i}]")
            if not isinstance(sname, str) or not _SYMBOL.match(sname):
                raise ContractSpecError(f"{where}.symbols[{i}]: invalid symbol {sname!r}")
            symbols.append(EnumSymbol(sname, _nonempty_str(_req(s, "description", where), where)))
        names = [s.name for s in symbols]
        if len(set(names)) != len(names):
            raise ContractSpecError(f"{where}: duplicate symbols")
        out[name] = EnumDef(
            name=name,
            description=_nonempty_str(_req(body, "description", where), where),
            basis=_basis(_req(body, "basis", where), where),
            symbols=tuple(symbols),
        )
    return out


def _parse_flag_sets(raw: Any) -> dict[str, FlagSet]:
    if not isinstance(raw, dict) or not raw:
        raise ContractSpecError("flag_sets: expected a non-empty mapping")
    out: dict[str, FlagSet] = {}
    for name, body in raw.items():
        where = f"flag_sets.{name}"
        if not isinstance(name, str) or not _ENUM_NAME.match(name):
            raise ContractSpecError(f"{where}: invalid flag-set name")
        _check_keys(body, {"basis", "description", "width", "flags"}, where)
        width = _req(body, "width", where)
        if width not in (8, 16, 32):
            raise ContractSpecError(f"{where}: width must be 8, 16 or 32")
        flags = []
        for i, f in enumerate(_req(body, "flags", where)):
            fw = f"{where}.flags[{i}]"
            _check_keys(f, {"bit", "name", "scope", "description"}, fw)
            bit, fname, scope = _req(f, "bit", fw), _req(f, "name", fw), _req(f, "scope", fw)
            if not isinstance(bit, int) or isinstance(bit, bool) or not 0 <= bit < width:
                raise ContractSpecError(f"{fw}: bit must be an int in [0, {width})")
            if not isinstance(fname, str) or not _SYMBOL.match(fname):
                raise ContractSpecError(f"{fw}: invalid flag name {fname!r}")
            if scope not in _FLAG_SCOPES:
                raise ContractSpecError(f"{fw}: scope must be one of {sorted(_FLAG_SCOPES)}")
            flags.append(FlagDef(bit, fname, scope, _nonempty_str(_req(f, "description", fw), fw)))
        if len({f.bit for f in flags}) != len(flags) or len({f.name for f in flags}) != len(flags):
            raise ContractSpecError(f"{where}: duplicate flag bits or names")
        out[name] = FlagSet(
            name=name,
            description=_nonempty_str(_req(body, "description", where), where),
            basis=_basis(_req(body, "basis", where), where),
            width=width,
            flags=tuple(sorted(flags, key=lambda x: x.bit)),
        )
    return out


# ---- fields ------------------------------------------------------------------------------------------------
def _parse_type(raw: Any, where: str, enums: dict[str, EnumDef], flag_sets: dict[str, FlagSet]) -> TypeSpec:
    if isinstance(raw, str):
        if raw in PRIMITIVE_TYPES:
            return TypeSpec("primitive", raw)
        if raw.startswith("enum:"):
            name = raw[len("enum:") :]
            if name not in enums:
                raise ContractSpecError(f"{where}: unknown enum {name!r}")
            return TypeSpec("enum", name)
        if raw.startswith("flags:"):
            name = raw[len("flags:") :]
            if name not in flag_sets:
                raise ContractSpecError(f"{where}: unknown flag set {name!r}")
            return TypeSpec("flags", name)
        raise ContractSpecError(f"{where}: unknown type {raw!r}")
    if isinstance(raw, dict) and "list" in raw:
        _check_keys(raw, {"list", "item_nullable"}, where)
        item_nullable = _req(raw, "item_nullable", where)
        if not isinstance(item_nullable, bool):
            raise ContractSpecError(f"{where}: item_nullable must be true or false")
        return TypeSpec(
            "list",
            item=_parse_type(raw["list"], f"{where}.list", enums, flag_sets),
            item_nullable=item_nullable,
        )
    if isinstance(raw, dict) and "struct" in raw:
        _check_keys(raw, {"struct"}, where)
        fields = tuple(
            _parse_field(f, f"{where}.struct[{i}]", enums, flag_sets) for i, f in enumerate(raw["struct"])
        )
        _unique_names([f.name for f in fields], where)
        return TypeSpec("struct", fields=fields)
    raise ContractSpecError(f"{where}: cannot parse type {raw!r}")


def _parse_field(raw: Any, where: str, enums: dict[str, EnumDef], flag_sets: dict[str, FlagSet]) -> FieldSpec:
    _check_keys(raw, _FIELD_KEYS, where)
    name = _req(raw, "name", where)
    if not isinstance(name, str) or not _FIELD_NAME.match(name):
        raise ContractSpecError(f"{where}: invalid field name {name!r}")
    where = f"{where}({name})"
    nullable = _req(raw, "nullable", where)
    if not isinstance(nullable, bool):
        raise ContractSpecError(f"{where}: nullable must be explicitly true or false")
    t = _parse_type(_req(raw, "type", where), where, enums, flag_sets)
    prim = t.name if t.kind == "primitive" else None
    time_scale = raw.get("time_scale")
    if prim == "time_ns":
        if time_scale not in TIME_SCALES:
            raise ContractSpecError(f"{where}: time_ns needs time_scale in {sorted(TIME_SCALES)}")
    elif time_scale is not None:
        raise ContractSpecError(f"{where}: time_scale is only valid on time_ns fields")
    units = raw.get("units")
    if units is not None and prim not in _NUMERIC:
        raise ContractSpecError(f"{where}: units only on numeric fields")
    pattern = raw.get("pattern")
    if pattern is not None:
        if prim != "string":
            raise ContractSpecError(f"{where}: pattern only on string fields")
        if not (pattern.startswith("^") and pattern.endswith("$")):
            raise ContractSpecError(f"{where}: pattern must be anchored with ^...$")
        re.compile(pattern)
    lo, hi = raw.get("minimum"), raw.get("maximum")
    for b in (lo, hi):
        if b is not None and (prim not in _NUMERIC or isinstance(b, bool) or not isinstance(b, int | float)):
            raise ContractSpecError(f"{where}: minimum/maximum only numeric, on numeric fields")
    restricted = raw.get("restricted", False)
    if not isinstance(restricted, bool):
        raise ContractSpecError(f"{where}: restricted must be a bool")
    return FieldSpec(
        name=name,
        type=t,
        nullable=nullable,
        description=_nonempty_str(_req(raw, "description", where), where),
        basis=_basis(_req(raw, "basis", where), where),
        units=units,
        time_scale=time_scale,
        restricted=restricted,
        pattern=pattern,
        minimum=float(lo) if lo is not None else None,
        maximum=float(hi) if hi is not None else None,
    )


def _unique_names(names: list[str], where: str) -> None:
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ContractSpecError(f"{where}: duplicate field names {dup}")


def _expand_fields(raw_fields: Any, field_sets: dict[str, list[Any]], where: str) -> list[Any]:
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ContractSpecError(f"{where}: fields must be a non-empty list")
    out: list[Any] = []
    for i, f in enumerate(raw_fields):
        if isinstance(f, dict) and set(f) == {"include"}:
            if f["include"] not in field_sets:
                raise ContractSpecError(f"{where}.fields[{i}]: unknown field set {f['include']!r}")
            out.extend(field_sets[f["include"]])
        else:
            out.append(f)
    return out


# ---- topics ------------------------------------------------------------------------------------------------
def _scalar_kind(f: FieldSpec) -> str | None:
    return f.type.name if f.type.kind == "primitive" else f.type.kind


def _parse_topic(
    raw: Any,
    rank: int,
    where: str,
    enums: dict[str, EnumDef],
    flag_sets: dict[str, FlagSet],
    field_sets: dict[str, list[Any]],
) -> TopicSpec:
    _check_keys(raw, _TOPIC_KEYS, where)
    name = _req(raw, "name", where)
    if not isinstance(name, str) or not _TOPIC_NAME.match(name):
        raise ContractSpecError(f"{where}: invalid topic name {name!r}")
    where = f"topic {name}"
    raw_fields = _expand_fields(_req(raw, "fields", where), field_sets, where)
    fields = tuple(
        _parse_field(f, f"{where}.fields[{i}]", enums, flag_sets) for i, f in enumerate(raw_fields)
    )
    _unique_names([f.name for f in fields], where)
    by_name = {f.name: f for f in fields}

    def time_field(key: str, allow_null: bool) -> str | None:
        v = _req(raw, key, where)
        if v is None and allow_null:
            return None
        f = by_name.get(v)
        if f is None or _scalar_kind(f) != "time_ns" or f.nullable:
            raise ContractSpecError(f"{where}: {key} must name a non-null time_ns field, got {v!r}")
        return v

    event_time = time_field("event_time", allow_null=False)
    ingest_time = time_field("ingest_time", allow_null=True)
    assert event_time is not None
    partition_by = tuple(_req(raw, "partition_by", where) or ())
    for p in partition_by:
        if p not in by_name or _scalar_kind(by_name[p]) != "string":
            raise ContractSpecError(f"{where}: partition field {p!r} must be a string field")

    rid: list[RecordIdComponent] = []
    for i, c in enumerate(_req(raw, "record_id_key", where)):
        cw = f"{where}.record_id_key[{i}]"
        _check_keys(c, {"name", "type", "source", "description"}, cw)
        comp = RecordIdComponent(
            name=_req(c, "name", cw),
            type=_req(c, "type", cw),
            source=_req(c, "source", cw),
            description=c.get("description", "") or "",
        )
        if comp.type not in RECORD_ID_COMPONENT_TYPES:
            raise ContractSpecError(f"{cw}: type must be one of {sorted(RECORD_ID_COMPONENT_TYPES)}")
        if comp.source == "column":
            f = by_name.get(comp.name)
            if f is None:
                raise ContractSpecError(f"{cw}: column component {comp.name!r} is not a field of the topic")
            k = _scalar_kind(f)
            ok = (
                (comp.type == "str" and k in ("string", "enum"))
                or (comp.type == "rid" and k == "record_id")
                or (comp.type == "u64" and k in _UNSIGNED_INT)
                or (comp.type == "i64" and k in ("int64", "time_ns"))
            )
            if not ok:
                raise ContractSpecError(f"{cw}: component type {comp.type} does not match field type {k}")
        elif comp.source == "path":
            if comp.name in by_name:
                raise ContractSpecError(f"{cw}: path component {comp.name!r} collides with a field name")
            if not comp.description:
                raise ContractSpecError(f"{cw}: path component needs a description of each path's rule")
        else:
            raise ContractSpecError(f"{cw}: source must be 'column' or 'path'")
        rid.append(comp)
    if not rid:
        raise ContractSpecError(f"{where}: record_id_key must not be empty")
    kinds = [c.type in RECORD_ID_PREFIX_TYPES for c in rid]
    if kinds != sorted(kinds, reverse=True):
        raise ContractSpecError(f"{where}: record_id_key must list str/rid components before integer ones")

    checks: list[CheckSpec] = []
    for i, c in enumerate(raw.get("checks") or []):
        cw = f"{where}.checks[{i}]"
        kind = _req(c, "check", cw)
        if kind == "order":
            _check_keys(c, {"check", "left", "op", "right"}, cw)
            for side in ("left", "right"):
                f = by_name.get(c[side])
                if f is None or _scalar_kind(f) not in _NUMERIC | {"time_ns"}:
                    raise ContractSpecError(f"{cw}: {side} must name a numeric or time field")
            if c["op"] not in (">=", ">"):
                raise ContractSpecError(f"{cw}: op must be '>=' or '>'")
        elif kind == "required_if":
            _check_keys(c, {"check", "field", "when_field", "equals"}, cw)
            for key in ("field", "when_field"):
                if c[key] not in by_name:
                    raise ContractSpecError(f"{cw}: {key} {c[key]!r} is not a field")
        else:
            raise ContractSpecError(f"{cw}: unknown check {kind!r}")
        checks.append(CheckSpec(kind, tuple(sorted((k, v) for k, v in c.items() if k != "check"))))

    restricted = _req(raw, "restricted", where)
    json_schema = _req(raw, "json_schema", where)
    if not isinstance(restricted, bool) or not isinstance(json_schema, bool):
        raise ContractSpecError(f"{where}: restricted and json_schema must be booleans")
    if "record_id" not in by_name or _scalar_kind(by_name["record_id"]) != "record_id":
        raise ContractSpecError(f"{where}: every topic needs a record_id field of type record_id")
    # restricted fields of a consumer-visible topic live in a separate restricted part (R1): the consumer
    # record must be complete without them, and they must never be identity, time or partition keys
    keys = {
        "record_id",
        event_time,
        ingest_time,
        *partition_by,
        *(c.name for c in rid if c.source == "column"),
    }
    for f in fields:
        if f.restricted and not restricted:
            if not f.nullable:
                raise ContractSpecError(f"{where}: restricted field {f.name} must be nullable")
            if f.name in keys:
                raise ContractSpecError(f"{where}: restricted field {f.name} cannot be a key or time field")
    return TopicSpec(
        name=name,
        rank=rank,
        description=_nonempty_str(_req(raw, "description", where), where),
        basis=_basis(_req(raw, "basis", where), where),
        restricted=restricted,
        event_time=event_time,
        ingest_time=ingest_time,
        partition_by=partition_by,
        json_schema=json_schema,
        record_id_key=tuple(rid),
        checks=tuple(checks),
        fields=fields,
    )


# ---- canonical form and hash -------------------------------------------------------------------------------
def canonical_json(obj: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, compact separators, UTF-8, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )


def blake2b_hex(data: bytes, digest_size: int = 32) -> str:
    return hashlib.blake2b(data, digest_size=digest_size).hexdigest()


def _canonical_spec(
    head: dict[str, Any],
    enums: dict[str, EnumDef],
    flag_sets: dict[str, FlagSet],
    topics: list[TopicSpec],
    assumptions: list[AssumptionRef],
) -> bytes:
    doc = dict(head)
    doc["enums"] = {k: dataclasses.asdict(v) for k, v in sorted(enums.items())}
    doc["flag_sets"] = {k: dataclasses.asdict(v) for k, v in sorted(flag_sets.items())}
    doc["topics"] = [dataclasses.asdict(t) for t in topics]
    doc["assumptions"] = [dataclasses.asdict(a) for a in assumptions]
    return canonical_json(doc)


# ---- public ------------------------------------------------------------------------------------------------
def load_spec_dir(spec_dir: str | Path) -> Contract:
    """Load and validate the spec in ``spec_dir`` (no caching; use :func:`load_contract` normally)."""
    from .arrow import build_schemas, schema_fingerprint

    spec_dir = Path(spec_dir).resolve()
    root = _read_yaml(spec_dir / "contract.yaml")
    _check_keys(root, _TOP_KEYS, "contract.yaml")
    version = _req(root, "version", "contract.yaml")
    if not isinstance(version, str) or not _SEMVER.match(version):
        raise ContractSpecError(f"contract.yaml: version {version!r} is not semver MAJOR.MINOR.PATCH")
    enums = _parse_enums(_req(root, "enums", "contract.yaml"))
    flag_sets = _parse_flag_sets(_req(root, "flag_sets", "contract.yaml"))
    field_sets = _req(root, "field_sets", "contract.yaml") or {}
    if not isinstance(field_sets, dict):
        raise ContractSpecError("contract.yaml: field_sets must be a mapping")

    assumptions: list[AssumptionRef] = []
    for i, a in enumerate(_req(root, "assumptions", "contract.yaml") or []):
        _check_keys(a, {"id", "statement"}, f"assumptions[{i}]")
        aid = _req(a, "id", f"assumptions[{i}]")
        if not isinstance(aid, str) or not _ASSUMPTION_ID.match(aid):
            raise ContractSpecError(f"assumptions[{i}]: invalid id {aid!r}")
        assumptions.append(AssumptionRef(aid, _nonempty_str(_req(a, "statement", aid), aid)))
    ids = [a.id for a in assumptions]
    if len(set(ids)) != len(ids):
        raise ContractSpecError("assumptions: duplicate ids")

    topic_files = _req(root, "topics", "contract.yaml")
    topics: list[TopicSpec] = []
    for rank, rel in enumerate(topic_files):
        path = (spec_dir / rel).resolve()
        if spec_dir not in path.parents:
            raise ContractSpecError(f"topic file {rel!r} escapes the spec directory")
        topics.append(_parse_topic(_read_yaml(path), rank, rel, enums, flag_sets, field_sets))
    names = [t.name for t in topics]
    if len(set(names)) != len(names):
        raise ContractSpecError("duplicate topic names")

    head_keys = ("contract", "version", "status", "description", "time", "record_id")
    head = {k: _req(root, k, "contract.yaml") for k in (*head_keys, "nan_policy", "restriction_policy")}
    for k in ("contract", "status", "description", "nan_policy", "restriction_policy"):
        _nonempty_str(head[k], f"contract.yaml.{k}")
    canonical = _canonical_spec(head, enums, flag_sets, topics, assumptions)

    # every ASSUMPTION reference in the spec must be registered in the assumptions list
    referenced = set(_ASSUMPTION_REF.findall(canonical.decode("utf-8")))
    missing = sorted(referenced - set(ids))
    if missing:
        raise ContractSpecError(f"basis strings cite unregistered assumptions: {missing}")

    digest = blake2b_hex(canonical)
    topic_map = {t.name: t for t in topics}
    partial = Contract(
        name=head["contract"],
        version=version,
        status=head["status"],
        description=head["description"],
        hash=digest,
        schema_hash="",
        canonical_spec=canonical,
        spec_dir=str(spec_dir),
        time=MappingProxyType(dict(head["time"])),
        record_id_rules=MappingProxyType(dict(head["record_id"])),
        nan_policy=head["nan_policy"],
        restriction_policy=head["restriction_policy"],
        enums=MappingProxyType(enums),
        flag_sets=MappingProxyType(flag_sets),
        topics=MappingProxyType(topic_map),
        assumptions=tuple(assumptions),
        schemas=MappingProxyType({}),
    )
    schemas = build_schemas(partial)
    return dataclasses.replace(
        partial, schemas=MappingProxyType(schemas), schema_hash=schema_fingerprint(schemas)
    )


def available_versions() -> dict[str, str]:
    """Map of spec directory name (``v0``) to the semantic version it contains."""
    out: dict[str, str] = {}
    for d in sorted(SPEC_ROOT.iterdir()):
        f = d / "contract.yaml"
        if d.is_dir() and f.is_file():
            out[d.name] = str(_read_yaml(f)["version"])
    return out


@lru_cache(maxsize=8)
def _load_builtin(dirname: str) -> Contract:
    return load_spec_dir(SPEC_ROOT / dirname)


def load_contract(version: str = "v0", *, spec_dir: str | Path | None = None) -> Contract:
    """Load a contract version.

    Args:
        version: a spec line (``"v0"``) or an exact semantic version (``"0.1.0"``) that must match the
            ``version`` declared by one of the built-in spec directories.
        spec_dir: load an explicit spec directory instead (tools and tests); ``version`` is then ignored.

    Returns:
        The immutable :class:`Contract` with ``.schemas[topic]``, ``.version``, ``.hash``, enum and flag
        tables.

    Raises:
        ContractNotFound: no built-in spec matches ``version``.
        ContractSpecError: the spec is malformed.
    """
    if spec_dir is not None:
        return load_spec_dir(spec_dir)
    versions = available_versions()
    if version in versions:
        return _load_builtin(version)
    for dirname, semver in versions.items():
        if semver == version:
            return _load_builtin(dirname)
    raise ContractNotFound(f"no contract spec for {version!r}; available: {versions}")
