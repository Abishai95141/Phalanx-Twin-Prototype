"""Idempotency on ``record_id`` (architecture §12 delivery semantics, M17/M19 acceptance).

A re-download delivers the same records again (same record_id, later t_ingest, possibly the DUPLICATE_DOWNLOAD
flag). Idempotent ingest keeps exactly one copy: the earliest-ingested one (ties: first in input order). With
``verify=True`` every dropped duplicate is checked to be the same record (all fields equal except the ingest
time and the DUPLICATE_DOWNLOAD bit); a mismatch means a record_id collision or a non-deterministic producer
and raises :class:`RecordIdConflict` instead of silently keeping one version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

if TYPE_CHECKING:
    from phalanx.dictionary.contract import Contract


class RecordIdConflict(ValueError):
    """Two records share a record_id but differ in content."""


def record_id_words(col: pa.ChunkedArray | pa.Array) -> np.ndarray:
    """(n, 2) big-endian uint64 view of a fixed_size_binary(16) column (for sorting and grouping)."""
    arr = col.combine_chunks() if isinstance(col, pa.ChunkedArray) else col
    if not arr.type.equals(pa.binary(16)):
        raise TypeError(f"record_id column must be fixed_size_binary(16), got {arr.type}")
    buf = arr.buffers()[1]
    raw = np.frombuffer(buf, dtype=np.uint8, count=16 * len(arr), offset=16 * arr.offset)
    return raw.view(">u8").reshape(-1, 2).astype(np.uint64)


def _equal_with_nulls(a: pa.Array, b: pa.Array) -> np.ndarray:
    t = a.type
    if pa.types.is_list(t) or pa.types.is_struct(t):
        return np.array([x == y for x, y in zip(a.to_pylist(), b.to_pylist(), strict=True)], dtype=bool)
    both_null = pc.and_(pc.is_null(a), pc.is_null(b))
    eq = pc.fill_null(pc.or_(both_null, pc.fill_null(pc.equal(a, b), False)), False)
    return eq.to_numpy(zero_copy_only=False)


def dedup_by_record_id(
    contract: Contract, topic: str, table: pa.Table, *, verify: bool = True
) -> tuple[pa.Table, int]:
    """Drop duplicate record_ids, keeping the earliest-ingested copy; rows keep their input order.

    Returns:
        (deduplicated table, number of rows dropped).
    """
    n = table.num_rows
    if n < 2:
        return table, 0
    spec = contract.topics[topic]
    words = record_id_words(table.column("record_id"))
    ingest = (
        table.column(spec.ingest_time).to_numpy()
        if spec.ingest_time is not None
        else np.zeros(n, dtype=np.int64)
    )
    order = np.lexsort((np.arange(n), ingest, words[:, 1], words[:, 0]))
    w = words[order]
    new_run = np.r_[True, np.any(w[1:] != w[:-1], axis=1)]
    if new_run.all():
        return table, 0
    run_id = np.cumsum(new_run) - 1
    run_first = order[new_run]
    dup_rows = order[~new_run]
    keep_of_dup = run_first[run_id[~new_run]]
    if verify:
        dup_bit = contract.quality_flags.mask("DUPLICATE_DOWNLOAD")
        for name in table.schema.names:
            if name == spec.ingest_time:
                continue
            col = table.column(name)
            a = col.take(pa.array(dup_rows))
            b = col.take(pa.array(keep_of_dup))
            if isinstance(a, pa.ChunkedArray):
                a, b = a.combine_chunks(), b.combine_chunks()
            if name == "quality_flags":
                m = pa.scalar(~dup_bit & 0xFFFFFFFF, pa.uint32())
                a, b = pc.bit_wise_and(a, m), pc.bit_wise_and(b, m)
            eq = _equal_with_nulls(a, b)
            if not eq.all():
                i = int(np.flatnonzero(~eq)[0])
                rid = bytes(table.column("record_id")[int(dup_rows[i])].as_py()).hex()
                raise RecordIdConflict(
                    f"{topic}: record_id {rid} appears with different {name!r} values; "
                    "record_ids must identify identical records"
                )
    keep = np.sort(run_first)
    return table.take(pa.array(keep)), int(n - len(keep))
