"""Contract minor-version migration helpers (AD-41: additive change = minor bump; W2.2 contract 0.2.0).

A minor version of the ground-decoder contract may only **add**: new topics, new nullable fields appended
after the existing ones, new enum symbols after the existing ones, new quality flags on free bits. Everything
an earlier minor version defined keeps its name, position, type, nullability, enum symbols, flag bits, time
and partition fields and record-id components (component descriptions may be refined: 0.2.0 adds the rule
for identified recordings, which leaves every 0.1.0 id unchanged).

- :func:`additive_changes` checks that rule and returns the added fields per topic (it raises otherwise);
- :func:`project` turns a newer-minor table into an older version's table (drops the added fields),
  validated under the older contract: what a 0.1.0 consumer reads;
- :func:`upgrade` turns an older-minor table into the newer version (added fields as nulls), validated
  under the newer contract: how 0.1.0 data joins a 0.2.0 store.

Parquet files are bound to the exact contract hash they were written under (A-W0.4-19), so a store of one
version never silently reads another's files; these helpers are the explicit bridge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow as pa

if TYPE_CHECKING:
    from phalanx.dictionary.contract import Contract

__all__ = ["ContractMigrationError", "additive_changes", "project", "upgrade"]


class ContractMigrationError(ValueError):
    """The two contract versions are not related by an additive (minor) change."""


def _semver(v: str) -> tuple[int, int, int]:
    a, b, c = (int(x) for x in v.split("."))
    return a, b, c


def additive_changes(old: Contract, new: Contract) -> dict[str, tuple[str, ...]]:
    """Fields ``new`` adds to each topic of ``old`` (topics new in ``new`` map to all their fields).

    Raises ContractMigrationError unless ``new`` is a later minor version of the same major line that only
    adds.
    """
    errs: list[str] = []
    vo, vn = _semver(old.version), _semver(new.version)
    if old.name != new.name or vo[0] != vn[0] or vn <= vo:
        raise ContractMigrationError(f"{new.version} is not a later minor version of {old.version}")
    for name, eo in old.enums.items():
        en = new.enums.get(name)
        if en is None or en.names[: len(eo.names)] != eo.names:
            errs.append(f"enum {name}: symbols removed or reordered")
    for name, fo in old.flag_sets.items():
        fn = new.flag_sets.get(name)
        if fn is None or fn.width != fo.width:
            errs.append(f"flag set {name}: removed or resized")
            continue
        bits_n = {f.bit: f.name for f in fn.flags}
        if any(bits_n.get(f.bit) != f.name for f in fo.flags):
            errs.append(f"flag set {name}: a flag moved or was renamed")
    added: dict[str, tuple[str, ...]] = {}
    for topic, to in old.topics.items():
        tn = new.topics.get(topic)
        if tn is None:
            errs.append(f"topic {topic} removed")
            continue
        so, sn = old.schemas[topic], new.schemas[topic]
        if sn.names[: len(so.names)] != so.names:
            errs.append(f"{topic}: 0.x fields removed, renamed or reordered")
            continue
        for fo, fnw in zip(so, sn, strict=False):
            if not fo.type.equals(fnw.type) or fo.nullable != fnw.nullable:
                errs.append(f"{topic}.{fo.name}: type or nullability changed")
        extra = tuple(sn.names[len(so.names) :])
        for name in extra:
            if not sn.field(name).nullable:
                errs.append(f"{topic}.{name}: an added field must be nullable")
        if (to.event_time, to.ingest_time, to.partition_by, to.restricted) != (
            tn.event_time,
            tn.ingest_time,
            tn.partition_by,
            tn.restricted,
        ):
            errs.append(f"{topic}: event/ingest time, partitioning or restriction changed")
        if [(k.name, k.type, k.source) for k in to.record_id_key] != [
            (k.name, k.type, k.source) for k in tn.record_id_key
        ]:
            errs.append(f"{topic}: record_id components changed")
        if extra:
            added[topic] = extra
    for topic in new.topics:
        if topic not in old.topics:
            added[topic] = tuple(new.schemas[topic].names)
    if errs:
        raise ContractMigrationError("not an additive change:\n" + "\n".join(errs))
    return added


def project(table: pa.Table, new: Contract, old: Contract, topic: str) -> pa.Table:
    """A ``new``-version table of ``topic`` as the ``old`` version sees it (added fields dropped),
    validated under both versions."""
    additive_changes(old, new)
    new.validate(topic, table)
    schema = old.schemas[topic]
    out = pa.Table.from_arrays([table.column(n).combine_chunks() for n in schema.names], schema=schema)
    old.validate(topic, out)
    return out


def upgrade(table: pa.Table, old: Contract, new: Contract, topic: str) -> pa.Table:
    """An ``old``-version table of ``topic`` in the ``new`` version: added fields are null, validated."""
    added = set(additive_changes(old, new).get(topic, ()))
    old.validate(topic, table)
    schema = new.schemas[topic]
    n = table.num_rows
    arrays = [
        pa.nulls(n, schema.field(f).type) if f in added else table.column(f).combine_chunks()
        for f in schema.names
    ]
    out = pa.Table.from_arrays(arrays, schema=schema)
    new.validate(topic, out)
    return out
