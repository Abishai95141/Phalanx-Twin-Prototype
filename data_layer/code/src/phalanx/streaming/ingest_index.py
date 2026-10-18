"""Indexed evidence lookup for the orders interface (M19 productionisation for M21; I5).

``ObservationView.ingested`` (W0.4) scans every consumer file on every call. The orders gateway (M21) calls it
for every order, so W1.8 adds an index (W0.4 README "Known limitations": "index it in W1.8"). The index maps
each consumer-visible ``record_id`` to the earliest ``t_ingest`` at which any copy of it reached the ground;
the evidence check is then a binary search.

Semantics are identical to :meth:`ObservationView.ingested` (tested in
``tests/property/test_orders_no_lookahead_property.py``):

- only consumer-visible topics with an ingest time contribute (restricted topics never do);
- a record counts as ingested at ``t`` if any copy has ``t_ingest <= t`` (re-downloads only add later copies).

The W0.4 class is not modified: :class:`IndexedObservationView` subclasses it and overrides ``ingested`` only.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .dedup import record_id_words
from .parquet_store import CONSUMER, ParquetStore
from .replay import ObservationView

KEY_DTYPE = np.dtype([("w0", "<u8"), ("w1", "<u8")])
_NEVER = np.iinfo(np.int64).max


def _keys(record_ids: pa.Array | pa.ChunkedArray) -> np.ndarray:
    w = record_id_words(record_ids)
    k = np.empty(w.shape[0], dtype=KEY_DTYPE)
    k["w0"] = w[:, 0]
    k["w1"] = w[:, 1]
    return k


def _keys_from_bytes(ids: Sequence[bytes]) -> np.ndarray:
    for r in ids:
        if not isinstance(r, bytes | bytearray) or len(r) != 16:
            raise ValueError("record_ids must be 16-byte values")
    return _keys(pa.array([bytes(r) for r in ids], pa.binary(16)))


class IngestIndex:
    """record_id -> earliest t_ingest over consumer-visible records (append-only, deterministic).

    Appends are buffered and merged lazily into one sorted structured array (keys ``(w0, w1)`` = the record_id
    as two big-endian uint64 words, plus the minimum ingest time per key): 24 bytes per distinct record.
    """

    def __init__(self) -> None:
        self._keys = np.empty(0, dtype=KEY_DTYPE)
        self._t = np.empty(0, dtype=np.int64)
        self._pending: list[tuple[np.ndarray, np.ndarray]] = []

    def __len__(self) -> int:
        self._merge()
        return int(self._keys.size)

    def add(self, record_ids: pa.Array | pa.ChunkedArray, t_ingest: np.ndarray | pa.Array) -> None:
        """Add records (``record_ids`` fixed_size_binary(16), ``t_ingest`` int64 of equal length)."""
        k = _keys(record_ids)
        t = np.asarray(
            t_ingest.to_numpy(zero_copy_only=False)
            if isinstance(t_ingest, pa.Array | pa.ChunkedArray)
            else t_ingest,
            dtype=np.int64,
        )
        if t.shape != k.shape:
            raise ValueError("record_ids and t_ingest differ in length")
        if k.size:
            self._pending.append((k, t))

    def add_table(self, table: pa.Table, ingest_time: str) -> None:
        self.add(table.column("record_id"), table.column(ingest_time).to_numpy())

    def _merge(self) -> None:
        if not self._pending:
            return
        keys = np.concatenate([self._keys, *(k for k, _ in self._pending)])
        ts = np.concatenate([self._t, *(t for _, t in self._pending)])
        self._pending = []
        order = np.lexsort((ts, keys["w1"], keys["w0"]))  # by key, then by time (earliest first)
        keys, ts = keys[order], ts[order]
        first = np.ones(keys.size, dtype=bool)
        if keys.size > 1:
            first[1:] = (keys["w0"][1:] != keys["w0"][:-1]) | (keys["w1"][1:] != keys["w1"][:-1])
        self._keys, self._t = keys[first], ts[first]

    def earliest(self, record_ids: Sequence[bytes]) -> np.ndarray:
        """Earliest ingest time per record_id (int64 max if never ingested)."""
        self._merge()
        q = _keys_from_bytes(record_ids)
        out = np.full(q.size, _NEVER, dtype=np.int64)
        if q.size == 0 or self._keys.size == 0:
            return out
        pos = np.searchsorted(self._keys, q)
        ok = pos < self._keys.size
        hit = np.zeros(q.size, dtype=bool)
        hit[ok] = self._keys[pos[ok]] == q[ok]
        out[hit] = self._t[pos[hit]]
        return out

    def ingested(self, t: int, record_ids: Sequence[bytes]) -> np.ndarray:
        """Whether each record_id was ingested at or before ``t`` (boolean array)."""
        return self.earliest(record_ids) <= int(t)


class IndexedObservationView(ObservationView):
    """:class:`ObservationView` with an indexed ``ingested`` (same semantics, no full scan per call).

    The index is built from the consumer tree and refreshed incrementally: files are content-addressed and
    never rewritten (A-W0.4-17), so only files not seen before are read on a refresh.
    """

    def __init__(self, store: ParquetStore, *, audience: str = "consumer"):
        super().__init__(store, audience=audience)
        self._index = IngestIndex()
        self._seen: set[Path] = set()

    def _topics(self) -> Iterable[tuple[str, str]]:
        c = self.store.contract
        for topic in c.topic_names:
            spec = c.topics[topic]
            if spec.ingest_time is None or spec.restricted:
                continue
            yield topic, spec.ingest_time

    def refresh(self) -> int:
        """Index files written since the last refresh; returns the number of new files."""
        n = 0
        for topic, ingest in self._topics():
            for path in self.store.files(topic, tree=CONSUMER):
                if path in self._seen:
                    continue
                tab = pq.read_table(path, columns=["record_id", ingest])
                self._index.add(tab.column(0), tab.column(1).to_numpy())
                self._seen.add(path)
                n += 1
        return n

    def ingested(self, t: int, record_ids: Sequence[bytes]) -> np.ndarray:
        self.refresh()
        return self._index.ingested(t, record_ids)
