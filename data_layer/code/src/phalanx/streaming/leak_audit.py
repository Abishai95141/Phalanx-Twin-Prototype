"""Audit a consumer tree for restricted data (invariant I5; coordinator requirement R1c).

A consumer tree must contain no restricted topic, no restricted field and no restricted value, in any form a
downstream reader could reach: directory or file names, Arrow or Parquet schemas (at any nesting level), file
key-value metadata (including the base64-encoded Arrow schema), raw file bytes, and decoded column values
(compression hides raw bytes, so values are checked after decoding).

What is checked:

- **Restricted names**, derived from the contract: the restricted topics, and every field name that occurs
  only in restricted data (restricted fields of consumer topics, their nested members, and the fields of
  restricted topics that no consumer schema uses). Matched exactly against schema field names; the
  restricted topic names and the names of restricted fields of consumer topics are also searched in metadata.
- **Secret values**, supplied by the caller (seeds, truth values, truth instants, stream-table key paths ...):
  searched in raw bytes (strings and bytes), in metadata, and in every decoded value of every column (strings
  by containment; integers, floats and bytes by equality). Integer secrets are matched in every integer column
  (int64 times, uint counters and words); to avoid false positives on small counts and flags they must have a
  magnitude of at least ``INT_SECRET_MIN_MAGNITUDE`` (ns times and seeds are far above it), else a
  ``ValueError`` is raised rather than silently not checking them.

Use it before handing a consumer tree to a downstream team; the leak test runs it on every write path.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from phalanx.dictionary.contract import Contract
from phalanx.dictionary.contract.model import FieldSpec


def _names(fields: Iterable[FieldSpec]) -> set[str]:
    out: set[str] = set()
    for f in fields:
        out.add(f.name)
        t = f.type
        while t.kind == "list" and t.item is not None:
            t = t.item
        if t.kind == "struct":
            out |= _names(t.fields)
    return out


def restricted_names(contract: Contract) -> tuple[set[str], set[str]]:
    """(names never allowed as a consumer field, names never allowed anywhere in consumer metadata)."""
    consumer_names: set[str] = set()
    restricted: set[str] = set()
    strong: set[str] = set()
    for name, spec in contract.topics.items():
        if spec.restricted:
            restricted |= _names(spec.fields)
            strong.add(name)
        else:
            consumer_names |= _names(f for f in spec.fields if not f.restricted)
            r = _names(f for f in spec.fields if f.restricted)
            restricted |= r
            strong |= r
    only_restricted = restricted - consumer_names
    return only_restricted, strong - consumer_names


def _arrow_field_names(t: pa.DataType, prefix: str = "") -> list[str]:
    out = []
    if pa.types.is_list(t) or pa.types.is_large_list(t):
        out += _arrow_field_names(t.value_type, prefix)
    elif pa.types.is_struct(t):
        for i in range(t.num_fields):
            f = t.field(i)
            out.append(f.name)
            out += _arrow_field_names(f.type, prefix)
    elif pa.types.is_map(t):
        out += _arrow_field_names(t.key_type) + _arrow_field_names(t.item_type)
    return out


def _walk_values(v: Any, out: list[Any]) -> None:
    if isinstance(v, dict):
        for x in v.values():
            _walk_values(x, out)
    elif isinstance(v, list | tuple):
        for x in v:
            _walk_values(x, out)
    elif v is not None:
        out.append(v)


INT_SECRET_MIN_MAGNITUDE = 10**6


def audit_consumer_tree(
    root: str | Path, contract: Contract, *, secrets: Iterable[str | int | float | bytes] = ()
) -> list[str]:
    """Return every finding (empty list = clean). ``secrets`` are restricted values to search for.

    Raises:
        ValueError: an integer secret below ``INT_SECRET_MIN_MAGNITUDE`` in magnitude (it would match ordinary
            counts and flags), or a secret of an unsupported type.
    """
    root = Path(root)
    secrets = list(secrets)
    str_secrets = [s for s in secrets if isinstance(s, str)]
    byte_secrets = [s for s in secrets if isinstance(s, bytes)] + [s.encode("utf-8") for s in str_secrets]
    int_secrets = {int(s) for s in secrets if isinstance(s, int | np.integer) and not isinstance(s, bool)}
    float_secrets = {float(s) for s in secrets if isinstance(s, float | np.floating)}
    small = sorted(s for s in int_secrets if abs(s) < INT_SECRET_MIN_MAGNITUDE)
    if small:
        raise ValueError(
            f"integer secrets below {INT_SECRET_MIN_MAGNITUDE} would match ordinary counts: {small[:5]}"
        )
    other = [s for s in secrets if not isinstance(s, str | bytes | int | float | np.integer | np.floating)]
    if other or any(isinstance(s, bool) for s in secrets):
        raise ValueError(f"unsupported secret types: {sorted({type(s).__name__ for s in secrets})}")
    field_names, strong_names = restricted_names(contract)
    restricted_topics = {n for n, s in contract.topics.items() if s.restricted}
    findings: list[str] = []
    if not root.exists():
        return findings
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        for part in rel.parts:
            if part in restricted_topics or any(n in part for n in strong_names):
                findings.append(f"{rel}: path names restricted data ({part})")
        if path.is_dir():
            continue
        raw = path.read_bytes()
        for s in byte_secrets:
            if s in raw:
                findings.append(f"{rel}: raw bytes contain a secret value")
        if path.suffix != ".parquet":
            findings.append(f"{rel}: unexpected non-Parquet file in the consumer tree")
            continue
        pf = pq.ParquetFile(path)
        arrow_schema = pf.schema_arrow
        names = list(arrow_schema.names)
        for f in arrow_schema:
            names += _arrow_field_names(f.type)
        names += [pf.schema.column(i).path for i in range(len(pf.schema))]
        names += [p for n in list(names) for p in n.split(".")]
        for n in sorted(set(names) & field_names):
            findings.append(f"{rel}: schema has restricted field {n!r}")
        md = dict(pf.metadata.metadata or {})
        md_text = []
        for k, v in md.items():
            if k == b"ARROW:schema":
                v = base64.b64decode(v)
            md_text.append(k + b"\x00" + v)
        for f in arrow_schema:
            for k, v in (f.metadata or {}).items():
                md_text.append(k + b"\x00" + v)
        blob = b"\x01".join(md_text)
        topic = (arrow_schema.metadata or {}).get(b"phalanx.topic", b"").decode()
        if topic in restricted_topics:
            findings.append(f"{rel}: file belongs to restricted topic {topic}")
        for n in sorted(strong_names | restricted_topics):
            if n.encode() in blob:
                findings.append(f"{rel}: metadata mentions restricted name {n!r}")
        for s in byte_secrets:
            if s in blob:
                findings.append(f"{rel}: metadata contains a secret value")
        table = pf.read()
        for name in table.column_names:
            values: list[Any] = []
            _walk_values(table.column(name).to_pylist(), values)
            hit_str = sum(1 for v in values if isinstance(v, str) and any(s in v for s in str_secrets))
            hit_int = sum(1 for v in values if type(v) is int and v in int_secrets)
            hit_float = sum(1 for v in values if isinstance(v, float) and v in float_secrets)
            hit_bytes = sum(1 for v in values if isinstance(v, bytes) and v in byte_secrets)
            if hit_str or hit_int or hit_float or hit_bytes:
                findings.append(
                    f"{rel}: column {name!r} decoded values contain secrets "
                    f"(strings {hit_str}, ints {hit_int}, floats {hit_float}, bytes {hit_bytes})"
                )
    return findings
