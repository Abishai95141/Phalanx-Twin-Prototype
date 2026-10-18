"""Arrow IPC variant of the data layer's ParquetStore, for platforms where Parquet is unreliable.

On IBM Z (s390x, big-endian) pyarrow's Parquet reader/writer fails on nullable and nested columns (a Parquet
round trip of a list<binary(16)> column with nulls raises "Decoded values 0 does not match expected 2"), while
Arrow IPC is Arrow's native format and handles byte order. ``IpcStore`` keeps everything else of
``ParquetStore`` — validation, consumer/restricted split, partition layout, canonical row order, exact schema
with the contract metadata (incl. ``phalanx.contract_hash``) — and only swaps the file encoding:
``part-<min_ingest:020d>-<blake2b digest>.arrow``, zstd-compressed IPC file format. Nothing in the data layer
is modified; this subclass lives in our runner.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

from datalayer import ParquetStore

FORMAT = os.environ.get("PHX_STORE_FORMAT", "arrow")  # "arrow" (default everywhere) or "parquet"


def ipc_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    opts = pa.ipc.IpcWriteOptions(compression="zstd")
    with pa.ipc.new_file(sink, table.schema, options=opts) as w:
        w.write_table(table)
    return sink.getvalue().to_pybytes()


class IpcStore(ParquetStore):
    def _write_file(self, base: Path, topic: str, rel: str, part: pa.Table) -> Path:  # type: ignore[override]
        spec = self.contract.topics[topic]
        data = ipc_bytes(part)
        digest = hashlib.blake2b(data, digest_size=16).hexdigest()
        t_min = int(pc.min(part.column(spec.ingest_time or spec.event_time)).as_py())
        d = base / topic / rel
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"part-{t_min:020d}-{digest}.arrow"
        if path.exists():
            if path.read_bytes() != data:
                raise OSError(f"{path} exists with different bytes")
            return path
        tmp = d / f".tmp-{digest}"
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return path


def store_class() -> type[ParquetStore]:
    return IpcStore if FORMAT == "arrow" else ParquetStore
