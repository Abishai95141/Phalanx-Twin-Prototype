"""File-backed, deterministic Parquet storage of contract topics (M19 v1; AD-13; A-W0.4-17), with restricted
data physically separated from the consumer tree (invariant I5; coordinator requirement R1).

Two trees, never nested in each other::

    <consumer root>/<topic>/date=YYYY-MM-DD/<field>=<value>/.../part-<min_ingest:020d>-<digest>.parquet
    <restricted root>/<topic>/date=YYYY-MM-DD/<field>=<value>/.../part-<min_ingest:020d>-<digest>.parquet

- **Consumer tree**: only consumer-visible topics, written with the *consumer schema* (restricted fields
  removed). It never contains a restricted column, a restricted value or restricted metadata, so it can be
  handed to a downstream team as is (pandas, duckdb or any Parquet reader see nothing restricted).
- **Restricted tree**: whole restricted topics (``labels.truth``) and the *restricted part* of consumer topics
  that have restricted fields (``sortie.manifest``: ``root_seed``, ``rng_stream_table``), i.e. the restricted
  fields plus the join keys (record_id, partition fields, event and ingest time). The validation audience
  joins the two by ``record_id``.
- A store opened without a restricted root can still write consumer data; writing restricted data then raises
  ``PermissionError`` (unless every restricted value is null), and validation reads are refused.
- Every read defaults to ``audience="consumer"`` (least privilege); ``"validation"`` must be asked for.

Partitioning: ``date`` is the UTC calendar date, given by the caller (e.g. the sortie's take-off date) or
derived per row from the event time; then the topic's ``partition_by`` fields; a null value is ``__null__``.

Determinism: every write validates the full batch, splits it, attaches the exact schema of each tree, sorts
rows by (event time, record_id) and writes with fixed options (zstd 3, fixed row-group and page sizes, format
2.6, Arrow schema stored, no page index or checksums). pyarrow writes no timestamps; the only
version-dependent bytes are the footer's ``created_by``. The file name carries the minimum ingest time and the
blake2b digest of the bytes, so writing the same records twice is a no-op.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from phalanx.dictionary.contract import Contract, load_contract

from .dedup import dedup_by_record_id

PARQUET_WRITE_OPTIONS: Mapping[str, Any] = MappingProxyType(
    {
        "compression": "zstd",
        "compression_level": 3,
        "use_dictionary": True,
        "write_statistics": True,
        "version": "2.6",
        "data_page_version": "1.0",
        "data_page_size": 1 << 20,
        "use_compliant_nested_type": True,
        "store_schema": True,
        "write_page_index": False,
        "write_page_checksum": False,
    }
)
ROW_GROUP_SIZE = 131_072
NULL_PARTITION = "__null__"
DATE_KEY = "date"
CONSUMER = "consumer"
RESTRICTED = "restricted"
AUDIENCES = ("consumer", "validation")
_NS_PER_DAY = 86_400 * 10**9
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EPOCH = _dt.date(1970, 1, 1)


class StoreError(RuntimeError):
    """Storage-level inconsistency (wrong contract, bad partition value, corrupt layout)."""


def utc_date(t_ns: int) -> str:
    """UTC calendar date (YYYY-MM-DD) of a sim-UTC ns timestamp (pure integer arithmetic)."""
    return (_EPOCH + _dt.timedelta(days=int(t_ns) // _NS_PER_DAY)).isoformat()


def canonical_order(contract: Contract, topic: str, table: pa.Table) -> pa.Table:
    """Rows sorted by (event time, record_id): the canonical, input-order-independent row order."""
    et = contract.topics[topic].event_time
    return table.sort_by([(et, "ascending"), ("record_id", "ascending")])


def parquet_bytes(table: pa.Table) -> bytes:
    """Serialise with the fixed deterministic options."""
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, row_group_size=ROW_GROUP_SIZE, **PARQUET_WRITE_OPTIONS)
    return sink.getvalue().to_pybytes()


def _partition_value(v: str | None, field: str) -> str:
    if v is None:
        return NULL_PARTITION
    if not _SAFE_VALUE.match(v):
        raise StoreError(f"partition value {v!r} of {field} is not filesystem-safe ({_SAFE_VALUE.pattern})")
    return v


def _with_schema(table: pa.Table, schema: pa.Schema) -> pa.Table:
    return pa.Table.from_arrays([table.column(n) for n in schema.names], schema=schema)


def project_consumer(contract: Contract, topic: str, table: pa.Table) -> pa.Table:
    """Drop restricted fields and attach the consumer schema (I5)."""
    return _with_schema(table, contract.consumer_schema(topic))


def _check_audience(audience: str) -> None:
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}, got {audience!r}")


class ParquetStore:
    """Contract-aware Parquet store with a consumer tree (``root``) and an optional restricted tree.

    Args:
        root: the consumer tree (the only directory a downstream consumer is given).
        contract: the contract (default: built-in v0).
        restricted_root: the restricted tree; must not be inside ``root`` (or contain it).
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        contract: Contract | None = None,
        *,
        restricted_root: str | os.PathLike[str] | None = None,
    ):
        self.root = Path(root)
        self.contract = contract or load_contract("v0")
        self.restricted_root = Path(restricted_root) if restricted_root is not None else None
        if self.restricted_root is not None:
            a, b = self.root.resolve(), self.restricted_root.resolve()
            if a == b or a in b.parents or b in a.parents:
                raise StoreError("the restricted root must be outside the consumer root (and vice versa)")

    @classmethod
    def at(cls, base: str | os.PathLike[str], contract: Contract | None = None) -> ParquetStore:
        """Producer-side store with sibling trees ``<base>/consumer`` and ``<base>/restricted``."""
        base = Path(base)
        return cls(base / CONSUMER, contract, restricted_root=base / RESTRICTED)

    # ---- trees and schemas ---------------------------------------------------------------------------------
    def _tree_root(self, tree: str) -> Path:
        if tree == CONSUMER:
            return self.root
        if tree == RESTRICTED:
            if self.restricted_root is None:
                raise PermissionError("this store has no restricted root (consumer-only access)")
            return self.restricted_root
        raise ValueError(f"unknown tree {tree!r}")

    def tree_schema(self, topic: str, tree: str) -> pa.Schema:
        """The exact schema of ``topic`` files in ``tree``."""
        c = self.contract
        spec = c.topics[topic]
        if tree == CONSUMER:
            return c.consumer_schema(topic)  # raises PermissionError for restricted topics
        if spec.restricted:
            return c.schemas[topic]
        return c.restricted_part_schema(topic)

    def _has_restricted_part(self, topic: str) -> bool:
        spec = self.contract.topics[topic]
        return not spec.restricted and any(f.restricted for f in spec.fields)

    # ---- write ---------------------------------------------------------------------------------------------
    def write(self, topic: str, table: pa.Table, *, date: str | None = None) -> list[Path]:
        """Validate the full batch, split it into its consumer and restricted parts, and write each part to
        its own tree (partitioned, canonically ordered). Returns the files written (sorted).

        Args:
            date: UTC date partition for every row (e.g. the sortie date). If None, each row goes to the
                date of its event time.
        """
        c = self.contract
        spec = c.topics[topic]
        c.validate(topic, table)
        table = _with_schema(table, c.schemas[topic])
        if table.num_rows == 0:
            return []
        if date is not None and not _DATE.match(date):
            raise StoreError(f"date {date!r} is not YYYY-MM-DD")
        if spec.restricted:
            return self._write_tree(topic, table, RESTRICTED, date)
        written = self._write_tree(
            topic, _with_schema(table, self.tree_schema(topic, CONSUMER)), CONSUMER, date
        )
        if self._has_restricted_part(topic):
            part = _with_schema(table, self.tree_schema(topic, RESTRICTED))
            if self.restricted_root is None:
                if any(part.column(n).null_count < part.num_rows for n in c.restricted_fields(topic)):
                    raise PermissionError(
                        f"{topic}: batch has restricted values but this store has no restricted root"
                    )
            else:
                written += self._write_tree(topic, part, RESTRICTED, date)
        return sorted(written)

    def _write_tree(self, topic: str, table: pa.Table, tree: str, date: str | None) -> list[Path]:
        spec = self.contract.topics[topic]
        base = self._tree_root(tree)
        n = table.num_rows
        if date is None:
            days = table.column(spec.event_time).to_numpy() // _NS_PER_DAY
            uniq = np.unique(days)
            date_vals = [utc_date(int(d) * _NS_PER_DAY) for d in uniq]
            date_code = np.searchsorted(uniq, days)
        else:
            date_vals, date_code = [date], np.zeros(n, dtype=np.int64)
        key_codes = [date_code.astype(np.int64)]
        key_vals: list[list[str]] = [date_vals]
        for p in spec.partition_by:
            enc = pc.dictionary_encode(table.column(p).combine_chunks(), null_encoding="encode")
            key_vals.append([_partition_value(v, p) for v in enc.dictionary.to_pylist()])
            key_codes.append(enc.indices.to_numpy(zero_copy_only=False).astype(np.int64))
        groups, inverse = np.unique(np.stack(key_codes, axis=1), axis=0, return_inverse=True)
        inverse = np.asarray(inverse).reshape(-1)
        jobs = []
        for g, codes in enumerate(groups):
            parts = [f"{DATE_KEY}={key_vals[0][codes[0]]}"]
            parts += [f"{p}={key_vals[i + 1][codes[i + 1]]}" for i, p in enumerate(spec.partition_by)]
            jobs.append(("/".join(parts), g))
        written = []
        for rel, g in sorted(jobs):
            part = canonical_order(self.contract, topic, table.take(pa.array(np.flatnonzero(inverse == g))))
            written.append(self._write_file(base, topic, rel, part))
        return written

    def _write_file(self, base: Path, topic: str, rel: str, part: pa.Table) -> Path:
        spec = self.contract.topics[topic]
        data = parquet_bytes(part)
        digest = hashlib.blake2b(data, digest_size=16).hexdigest()
        t_min = int(pc.min(part.column(spec.ingest_time or spec.event_time)).as_py())
        d = base / topic / rel
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"part-{t_min:020d}-{digest}.parquet"
        if path.exists():
            if path.read_bytes() != data:  # name embeds the digest, so this means corruption
                raise StoreError(f"{path} exists with different bytes")
            return path
        tmp = d / f".tmp-{digest}"
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return path

    # ---- read ----------------------------------------------------------------------------------------------
    def files(
        self,
        topic: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        partitions: Mapping[str, str | None] | None = None,
        tree: str = CONSUMER,
    ) -> list[Path]:
        """Data files of ``topic`` in ``tree`` (sorted), filtered by date range (inclusive) and partitions."""
        spec = self.contract.topics[topic]
        partitions = dict(partitions or {})
        bad = set(partitions) - set(spec.partition_by)
        if bad:
            raise ValueError(f"{topic}: {sorted(bad)} are not partition fields {spec.partition_by}")
        base = self._tree_root(tree) / topic
        if not base.is_dir():
            return []
        out = []
        for path in sorted(base.rglob("part-*.parquet")):
            parts = path.relative_to(base).parts[:-1]
            kv = dict(p.split("=", 1) for p in parts)
            if list(kv) != [DATE_KEY, *spec.partition_by]:
                raise StoreError(f"unexpected partition layout {parts} for {topic}")
            if date_from is not None and kv[DATE_KEY] < date_from:
                continue
            if date_to is not None and kv[DATE_KEY] > date_to:
                continue
            if any(kv[f] != (NULL_PARTITION if v is None else v) for f, v in partitions.items()):
                continue
            out.append(path)
        return out

    def read_file(self, topic: str, path: Path, *, tree: str = CONSUMER) -> pa.Table:
        """Read one file and check it was written under this exact contract and tree schema."""
        t = pq.read_table(path)
        md = t.schema.metadata or {}
        if md.get(b"phalanx.contract_hash") != self.contract.hash.encode():
            raise StoreError(f"{path}: written under a different contract (hash mismatch)")
        if not t.schema.equals(self.tree_schema(topic, tree), check_metadata=True):
            raise StoreError(f"{path}: schema differs from the {tree} schema of {topic}")
        return t

    def attach_restricted(self, topic: str, table: pa.Table) -> pa.Table:
        """Validation audience: join the restricted part onto consumer rows by record_id -> full schema.

        Rows without a restricted part get nulls in the restricted fields (they are nullable by spec rule).
        """
        c = self.contract
        full = c.schemas[topic]
        if not self._has_restricted_part(topic):
            return _with_schema(table, full)
        spec = c.topics[topic]
        combos: set[tuple[str | None, ...]] = set()
        if table.num_rows:
            cols = [table.column(p).to_pylist() for p in spec.partition_by]
            combos = set(zip(*cols, strict=True)) if cols else {()}
        pieces = []
        for combo in sorted(combos, key=lambda x: tuple("" if v is None else v for v in x)):
            parts = dict(zip(spec.partition_by, combo, strict=True))
            pieces += [
                self.read_file(topic, p, tree=RESTRICTED)
                for p in self.files(topic, partitions=parts, tree=RESTRICTED)
            ]
        rschema = self.tree_schema(topic, RESTRICTED)
        rp = pa.concat_tables(pieces) if pieces else rschema.empty_table()
        rp, _ = dedup_by_record_id(c, topic, rp)
        index = {rid: i for i, rid in enumerate(rp.column("record_id").to_pylist())}
        take = pa.array([index.get(r) for r in table.column("record_id").to_pylist()], pa.int64())
        restricted = set(c.restricted_fields(topic))
        arrays = [
            rp.column(f.name).take(take) if f.name in restricted else table.column(f.name) for f in full
        ]
        return pa.Table.from_arrays(arrays, schema=full)

    def read(
        self,
        topic: str,
        *,
        tail_no: str | None = None,
        sortie_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        t_from: int | None = None,
        t_to: int | None = None,
        dedup: bool = True,
        audience: str = "consumer",
    ) -> pa.Table:
        """Read ``topic`` by tail, sortie, date range and event-time window ``[t_from, t_to)``.

        ``audience="consumer"`` (default) reads only the consumer tree and refuses restricted topics.
        ``audience="validation"`` returns the full schema: restricted topics from the restricted tree, other
        topics with their restricted part joined by record_id. Duplicates (re-downloads) are removed by
        record_id, keeping the earliest ingest; rows are in canonical (event time, record_id) order.
        """
        _check_audience(audience)
        c = self.contract
        spec = c.topics[topic]
        if spec.restricted and audience == "consumer":
            raise PermissionError(f"topic {topic} is restricted (truth); consumers cannot read it")
        tree = RESTRICTED if spec.restricted else CONSUMER
        parts: dict[str, str | None] = {}
        if tail_no is not None:
            parts["tail_no"] = tail_no
        if sortie_id is not None:
            parts["sortie_id"] = sortie_id
        files = self.files(topic, date_from=date_from, date_to=date_to, partitions=parts, tree=tree)
        if files:
            table = pa.concat_tables([self.read_file(topic, f, tree=tree) for f in files])
        else:
            table = self.tree_schema(topic, tree).empty_table()
        et = table.column(spec.event_time)
        mask = None
        if t_from is not None:
            mask = pc.greater_equal(et, pa.scalar(t_from, pa.int64()))
        if t_to is not None:
            m2 = pc.less(et, pa.scalar(t_to, pa.int64()))
            mask = m2 if mask is None else pc.and_(mask, m2)
        if mask is not None:
            table = table.filter(mask)
        if dedup:
            table, _ = dedup_by_record_id(c, topic, table)
        table = canonical_order(c, topic, table).combine_chunks()
        if audience == "validation" and not spec.restricted:
            table = self.attach_restricted(topic, table)
        return table
