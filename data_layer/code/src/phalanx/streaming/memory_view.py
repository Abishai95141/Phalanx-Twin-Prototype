"""In-memory observation source with the exact ``ObservationView`` semantics (M19 for M21/M22; I5).

Usage-mode sessions and forks (M22) need the decision-maker's information set many times per simulated day.
Writing each epoch's records to Parquet and reading them back is correct but slow. :class:`MemoryObservations`
holds the same consumer-view records in memory and answers ``as_of`` / ``ingested`` with the semantics of
:class:`~phalanx.streaming.replay.ObservationView` (equivalence is tested against a ``ParquetStore``):

- only consumer-visible topics are accepted; restricted fields are dropped (consumer projection) and
  restricted topics are refused, so truth can never enter (I5);
- ``as_of(t, topic)`` returns records with ``t_ingest <= t``, de-duplicated by record_id (earliest ingest
  kept), in canonical (event time, record_id) order;
- the ``date_from`` / ``date_to`` filter uses the UTC date of the record's event time (the ParquetStore
  default partition when no explicit date is given);
- ``ingested(t, ids)`` is the indexed evidence check.

A branch (M22 fork) shares its parent's record pieces (immutable Arrow tables) and appends its own:
:meth:`fork` is copy-on-write.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from phalanx.dictionary.contract import Contract, load_contract

from .dedup import dedup_by_record_id
from .ingest_index import IngestIndex
from .parquet_store import canonical_order, project_consumer, utc_date

_NS_PER_DAY = 86_400 * 1_000_000_000


class MemoryObservations:
    """Consumer-view records held in memory; same ``as_of`` / ``ingested`` contract as ObservationView."""

    def __init__(self, contract: Contract | None = None):
        self.contract = contract or load_contract("v0")
        self._pieces: dict[str, list[pa.Table]] = {}
        self._index = IngestIndex()
        self._index_pieces: list[tuple[pa.Array, np.ndarray]] = []

    # ---- producer side -------------------------------------------------------------------------------------
    def append(self, topic: str, table: pa.Table) -> None:
        """Validate a full-schema batch, project it to the consumer view and add it."""
        spec = self.contract.topics[topic]
        if spec.restricted:
            raise PermissionError(f"topic {topic} is restricted (truth); it cannot enter the observation set")
        if spec.ingest_time is None:
            raise PermissionError(f"topic {topic} has no ingest time; it is not observable")
        self.contract.validate(topic, table)
        if table.num_rows == 0:
            return
        cons = project_consumer(self.contract, topic, table).combine_chunks()
        self._pieces.setdefault(topic, []).append(cons)
        rid = cons.column("record_id").combine_chunks()
        t = cons.column(spec.ingest_time).to_numpy()
        self._index.add(rid, t)
        self._index_pieces.append((rid, t))

    def fork(self) -> MemoryObservations:
        """Copy-on-write child: shares the (immutable) pieces recorded so far."""
        child = MemoryObservations(self.contract)
        child._pieces = {k: list(v) for k, v in self._pieces.items()}
        for rid, t in self._index_pieces:
            child._index.add(rid, t)
        child._index_pieces = list(self._index_pieces)
        return child

    def n_rows(self, topic: str) -> int:
        return sum(p.num_rows for p in self._pieces.get(topic, []))

    # ---- consumer side -------------------------------------------------------------------------------------
    def as_of(
        self,
        t: int,
        topic: str,
        *,
        tail_no: str | None = None,
        sortie_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> pa.Table:
        c = self.contract
        spec = c.topics[topic]
        if spec.restricted:
            raise PermissionError(f"topic {topic} is restricted (truth); consumers cannot read it")
        if spec.ingest_time is None:
            raise PermissionError(f"topic {topic} has no ingest time; it is not observable")
        pieces = self._pieces.get(topic, [])
        schema = c.consumer_schema(topic)
        table = pa.concat_tables(pieces) if pieces else schema.empty_table()
        table = table.filter(pc.less_equal(table.column(spec.ingest_time), pa.scalar(int(t), pa.int64())))
        for name, v in (("tail_no", tail_no), ("sortie_id", sortie_id)):
            if v is not None and name in table.schema.names:
                table = table.filter(pc.equal(table.column(name), pa.scalar(v)))
        if (date_from is not None or date_to is not None) and table.num_rows:
            days = table.column(spec.event_time).to_numpy() // _NS_PER_DAY
            dates = np.array([utc_date(int(d) * _NS_PER_DAY) for d in days])
            keep = np.ones(table.num_rows, dtype=bool)
            if date_from is not None:
                keep &= dates >= date_from
            if date_to is not None:
                keep &= dates <= date_to
            table = table.filter(pa.array(keep))
        table, _ = dedup_by_record_id(c, topic, table)
        return canonical_order(c, topic, table).combine_chunks()

    def ingested(self, t: int, record_ids: Sequence[bytes]) -> np.ndarray:
        return self._index.ingested(t, record_ids)
