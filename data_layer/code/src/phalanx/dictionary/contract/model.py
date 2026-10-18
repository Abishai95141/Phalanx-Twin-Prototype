"""Typed, immutable model of the contract spec (architecture §12).

The YAML spec under ``spec/v<major>/`` is parsed by :mod:`.loader` into these frozen dataclasses. Everything
downstream (Arrow, JSON-Schema, Avro, Markdown, validation, record_id) is generated from this model, so the
spec stays the single source (AD-13, AD-14).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pyarrow as pa

#: Scalar spec types. ``time_ns`` is int64 nanoseconds (AD-35); ``record_id`` is a 16-byte blake2b digest;
#: ``json_object`` is a JSON object carried as canonical JSON text in Arrow.
PRIMITIVE_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "bool",
        "int8",
        "int16",
        "int32",
        "int64",
        "uint8",
        "uint16",
        "uint32",
        "float64",
        "time_ns",
        "record_id",
        "json_object",
    }
)

INTEGER_RANGES: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "int8": (-(2**7), 2**7 - 1),
        "int16": (-(2**15), 2**15 - 1),
        "int32": (-(2**31), 2**31 - 1),
        "int64": (-(2**63), 2**63 - 1),
        "uint8": (0, 2**8 - 1),
        "uint16": (0, 2**16 - 1),
        "uint32": (0, 2**32 - 1),
        "time_ns": (0, 2**63 - 1),
    }
)

TIME_SCALES: frozenset[str] = frozenset({"sim_utc", "recorder_rtc", "duration"})
RECORD_ID_COMPONENT_TYPES: frozenset[str] = frozenset({"str", "rid", "u64", "i64"})
#: Component types grouped into the per-stream hasher prefix (they precede the integer components).
RECORD_ID_PREFIX_TYPES: frozenset[str] = frozenset({"str", "rid"})


@dataclass(frozen=True)
class EnumSymbol:
    name: str
    description: str


@dataclass(frozen=True)
class EnumDef:
    """A closed set of string symbols (carried as UTF-8 strings, A-W0.4-9)."""

    name: str
    description: str
    basis: str
    symbols: tuple[EnumSymbol, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.symbols)


@dataclass(frozen=True)
class FlagDef:
    bit: int
    name: str
    scope: str
    description: str


@dataclass(frozen=True)
class FlagSet:
    """A bit set with stable bit positions (A-W0.4-8)."""

    name: str
    description: str
    basis: str
    width: int
    flags: tuple[FlagDef, ...]

    def bit(self, name: str) -> int:
        for f in self.flags:
            if f.name == name:
                return f.bit
        raise KeyError(f"{self.name} has no flag {name!r}")

    def mask(self, *names: str) -> int:
        """Bit mask with the named flags set."""
        m = 0
        for n in names:
            m |= 1 << self.bit(n)
        return m

    @property
    def defined_mask(self) -> int:
        return self.mask(*(f.name for f in self.flags))

    @property
    def reserved_mask(self) -> int:
        return ((1 << self.width) - 1) & ~self.defined_mask

    def scope_mask(self, *scopes: str) -> int:
        """Mask of every flag whose producing-stage scope is in ``scopes``."""
        return self.mask(*(f.name for f in self.flags if f.scope in scopes))

    def names_of(self, value: int) -> tuple[str, ...]:
        return tuple(f.name for f in self.flags if value >> f.bit & 1)


@dataclass(frozen=True)
class TypeSpec:
    """A spec type: a primitive, an enum or flag-set reference, a list or a struct."""

    kind: str  # "primitive" | "enum" | "flags" | "list" | "struct"
    name: str | None = None  # primitive name, enum name or flag-set name
    item: TypeSpec | None = None  # list item type
    item_nullable: bool = False
    fields: tuple[FieldSpec, ...] = ()  # struct fields

    def render(self) -> str:
        """Human-readable type string (used in the summary and the schema fingerprint)."""
        if self.kind == "primitive":
            assert self.name is not None
            return self.name
        if self.kind in ("enum", "flags"):
            return f"{self.kind}:{self.name}"
        if self.kind == "list":
            assert self.item is not None
            return f"list<{self.item.render()}{'' if self.item_nullable else ' not null'}>"
        inner = ", ".join(
            f"{f.name}: {f.type.render()}{'' if f.nullable else ' not null'}" for f in self.fields
        )
        return f"struct<{inner}>"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: TypeSpec
    nullable: bool
    description: str
    basis: str
    units: str | None = None
    time_scale: str | None = None
    restricted: bool = False
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class RecordIdComponent:
    name: str
    type: str  # "str" | "rid" | "u64" | "i64"
    source: str  # "column" (a contract field) | "path" (supplied by the producing path)
    description: str = ""


@dataclass(frozen=True)
class CheckSpec:
    """A row-level invariant. ``order``: left op right where both non-null. ``required_if``: field non-null
    when when_field == equals."""

    check: str
    params: tuple[tuple[str, Any], ...]

    def get(self, key: str) -> Any:
        return dict(self.params)[key]


@dataclass(frozen=True)
class TopicSpec:
    name: str
    rank: int
    description: str
    basis: str
    restricted: bool
    event_time: str
    ingest_time: str | None
    partition_by: tuple[str, ...]
    json_schema: bool
    record_id_key: tuple[RecordIdComponent, ...]
    checks: tuple[CheckSpec, ...]
    fields: tuple[FieldSpec, ...]

    def field(self, name: str) -> FieldSpec:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(f"topic {self.name} has no field {name!r}")

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)


@dataclass(frozen=True)
class AssumptionRef:
    id: str
    statement: str


@dataclass(frozen=True)
class Contract:
    """A loaded, validated contract version. Immutable; obtain one with :func:`load_contract`.

    Attributes:
        version: contract semantic version (e.g. ``"0.1.0"``).
        hash: blake2b-256 hex of the canonical JSON of the expanded spec (the contract identity).
        schema_hash: blake2b-256 hex of the canonical rendering of the generated Arrow schemas (detects
            generator drift for an unchanged spec).
        schemas: ``topic -> pyarrow.Schema`` (full schema, restricted fields included).
        topics, enums, flag_sets: the parsed spec.
    """

    name: str
    version: str
    status: str
    description: str
    hash: str
    schema_hash: str
    canonical_spec: bytes
    spec_dir: str
    time: Mapping[str, Any]
    record_id_rules: Mapping[str, Any]
    nan_policy: str
    restriction_policy: str
    enums: Mapping[str, EnumDef]
    flag_sets: Mapping[str, FlagSet]
    topics: Mapping[str, TopicSpec]
    assumptions: tuple[AssumptionRef, ...]
    schemas: Mapping[str, pa.Schema] = field(repr=False)

    # ---- convenience accessors -----------------------------------------------------------------------------
    @property
    def topic_names(self) -> tuple[str, ...]:
        """Topics in rank order (the deterministic tie-breaker between topics)."""
        return tuple(sorted(self.topics, key=lambda t: self.topics[t].rank))

    @property
    def quality_flags(self) -> FlagSet:
        return self.flag_sets["QualityFlags"]

    @property
    def validity(self) -> EnumDef:
        return self.enums["Validity"]

    def consumer_schema(self, topic: str) -> pa.Schema:
        """Schema of ``topic`` as a downstream consumer sees it: restricted fields removed (invariant I5).

        Raises:
            PermissionError: if the whole topic is restricted.
        """
        from .arrow import consumer_schema

        return consumer_schema(self, topic)

    def restricted_fields(self, topic: str) -> tuple[str, ...]:
        """Names of the restricted fields of ``topic`` (every field, if the topic itself is restricted)."""
        spec = self.topics[topic]
        return tuple(f.name for f in spec.fields if spec.restricted or f.restricted)

    def restricted_part_schema(self, topic: str) -> pa.Schema:
        """Schema of the restricted part of a consumer-visible topic with restricted fields: the restricted
        fields plus the join keys. Written only under the restricted root (I5, R1)."""
        from .arrow import topic_schema

        spec = self.topics[topic]
        if spec.restricted or not any(f.restricted for f in spec.fields):
            raise ValueError(f"topic {topic} has no restricted part")
        return topic_schema(self, topic, audience="restricted_part")

    def validate(self, topic: str, table: pa.Table, *, require_unique_record_ids: bool = True) -> None:
        """Validate ``table`` against the generated schema and every spec invariant.

        Raises:
            ContractViolation: listing every violation found.
        """
        from .validate import validate_table

        validate_table(self, topic, table, require_unique_record_ids=require_unique_record_ids)

    def json_schema(self, topic: str, *, audience: str = "consumer") -> dict[str, Any]:
        from .jsonschema_gen import json_schema

        return json_schema(self, topic, audience=audience)

    def avro_schema(self, topic: str) -> dict[str, Any]:
        from .avro_gen import avro_schema

        return avro_schema(self, topic)
