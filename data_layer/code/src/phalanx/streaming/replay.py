"""Replay streamer with per-sortie watermarks, and the information-discipline hook ``as_of`` (M19; I5;
A-W0.4-18).

Delivery model. Data reach the ground as bursts: one download of one sortie (or one batch of ground records)
at one ``t_ingest``. A global wall-clock watermark is wrong when sorties arrive hours late, so watermarks are
per sortie (report §13; Flink event-time semantics).

Emission order (deterministic):

1. bursts in order of (t_ingest, tail_no, sortie_id) (null sorts first);
2. within a burst, topics in contract rank order;
3. within a (burst, topic), rows in (event time, record_id) order;
4. after a sortie burst, ``Watermark(tail, sortie, t_ingest, event_time)`` where event_time is the maximum
   event time delivered for that sortie so far: every record of the sortie with an event time at or before it
   that this replay will deliver has been delivered, except records that arrive in a later burst
   (re-downloads), which are counted in ``ReplayBatch.late_rows``.

Idempotency: a record_id already delivered (by an earlier burst or earlier in the same burst) is dropped; with
``verify=True`` the dropped copy must equal the delivered one (except ingest time and DUPLICATE_DOWNLOAD).

Information discipline: ``until=t`` stops before any burst with t_ingest > t; :meth:`ObservationView.as_of`
returns only records with t_ingest <= t (deduplicated). Both read only the consumer tree by default
(least privilege, R1); ``audience="validation"`` joins the restricted part from the restricted tree.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .dedup import dedup_by_record_id
from .parquet_store import CONSUMER, NULL_PARTITION, ParquetStore, canonical_order


@dataclass(frozen=True)
class ReplayBatch:
    """Records of one topic from one delivery burst, in (event time, record_id) order."""

    topic: str
    t_ingest: int
    tail_no: str | None
    sortie_id: str | None
    table: pa.Table
    late_rows: int  # rows whose event time is <= the sortie's previous watermark (re-download fill)


@dataclass(frozen=True)
class Watermark:
    """Per-sortie event-time watermark after a delivery burst."""

    tail_no: str
    sortie_id: str
    t_ingest: int
    event_time: int


def _check_audience(store: ParquetStore, topic: str, audience: str) -> None:
    spec = store.contract.topics[topic]
    if audience not in ("consumer", "validation"):
        raise ValueError("audience must be 'consumer' or 'validation'")
    if audience == "consumer" and spec.restricted:
        raise PermissionError(f"topic {topic} is restricted (truth); consumers cannot read it")


def _partition_of(store: ParquetStore, topic: str, path: Path) -> tuple[str | None, str | None]:
    parts = dict(p.split("=", 1) for p in path.relative_to(store.root / topic).parts[:-1])

    def val(k: str) -> str | None:
        v = parts.get(k)
        return None if v is None or v == NULL_PARTITION else v

    return val("tail_no"), val("sortie_id")


class ReplayStreamer:
    """Deterministic replay of stored topics as delivery bursts with per-sortie watermarks.

    Args:
        store: the Parquet store to replay.
        topics: topics to replay (default: every topic with an ingest time visible to ``audience``).
        audience: ``"consumer"`` (default; consumer tree only, restricted topics refused) or ``"validation"``
            (restricted fields joined from the restricted tree by record_id).
        tail_no, date_from, date_to: optional selection (tail filter applies to tail-partitioned topics).
        until: stop before the first burst with t_ingest > until (information discipline).
        verify: check that dropped duplicates equal the delivered record.
    """

    def __init__(
        self,
        store: ParquetStore,
        topics: Sequence[str] | None = None,
        *,
        audience: str = "consumer",
        tail_no: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        until: int | None = None,
        verify: bool = True,
    ):
        c = store.contract
        if topics is None:
            topics = [
                t
                for t in c.topic_names
                if c.topics[t].ingest_time is not None
                and not (audience == "consumer" and c.topics[t].restricted)
            ]
        for t in topics:
            _check_audience(store, t, audience)
            if c.topics[t].ingest_time is None:
                raise ValueError(f"topic {t} has no ingest time and cannot be streamed")
        self.store = store
        self.topics = sorted(topics, key=lambda t: c.topics[t].rank)
        self.audience = audience
        self.tail_no = tail_no
        self.date_from, self.date_to = date_from, date_to
        self.until = until
        self.verify = verify

    def _index(self) -> tuple[list[tuple], dict]:
        c = self.store.contract
        bursts: dict[tuple, list[tuple[str, Path]]] = defaultdict(list)
        for topic in self.topics:
            spec = c.topics[topic]
            parts = (
                {"tail_no": self.tail_no}
                if self.tail_no is not None and "tail_no" in spec.partition_by
                else {}
            )
            for path in self.store.files(
                topic, date_from=self.date_from, date_to=self.date_to, partitions=parts
            ):
                tail, sortie = _partition_of(self.store, topic, path)
                assert spec.ingest_time is not None
                ingest = pq.read_table(path, columns=[spec.ingest_time]).column(0).to_numpy()
                for t in np.unique(ingest).tolist():
                    bursts[(int(t), tail or "", sortie or "", tail, sortie)].append((topic, path))
        keys = sorted(bursts, key=lambda k: k[:3])
        return keys, bursts

    def __iter__(self) -> Iterator[ReplayBatch | Watermark]:
        c = self.store.contract
        keys, bursts = self._index()
        file_uses: Counter[Path] = Counter(p for k in keys for _, p in bursts[k])
        part_uses: Counter[tuple] = Counter()
        for k in keys:
            for topic in {t for t, _ in bursts[k]}:
                part_uses[(topic, k[3], k[4])] += 1
        cache: dict[Path, pa.Table] = {}
        history: dict[tuple, list[pa.Table]] = defaultdict(list)
        marks: dict[tuple[str, str], int] = {}
        for key in keys:
            t_ingest, _, _, tail, sortie = key
            if self.until is not None and t_ingest > self.until:
                break
            prev_mark = marks.get((tail, sortie)) if sortie is not None and tail is not None else None
            burst_max: int | None = None
            by_topic: dict[str, list[Path]] = defaultdict(list)
            for topic, path in bursts[key]:
                by_topic[topic].append(path)
            for topic in sorted(by_topic, key=lambda t: c.topics[t].rank):
                spec = c.topics[topic]
                assert spec.ingest_time is not None
                pieces = []
                for path in by_topic[topic]:
                    if path not in cache:
                        cache[path] = self.store.read_file(topic, path, tree=CONSUMER)
                    tab = cache[path]
                    pieces.append(
                        tab.filter(pc.equal(tab.column(spec.ingest_time), pa.scalar(t_ingest, pa.int64())))
                    )
                    file_uses[path] -= 1
                    if file_uses[path] == 0:
                        del cache[path]
                rows = pa.concat_tables(pieces)
                rows, _ = dedup_by_record_id(c, topic, rows, verify=self.verify)
                pk = (topic, tail, sortie)
                prior = history.get(pk)
                if prior:
                    seen = pa.concat_tables(prior)
                    dup = pc.is_in(
                        rows.column("record_id"), value_set=seen.column("record_id").combine_chunks()
                    )
                    if self.verify and pc.any(dup).as_py():
                        dedup_by_record_id(c, topic, pa.concat_tables([seen, rows.filter(dup)]), verify=True)
                    rows = rows.filter(pc.invert(dup))
                part_uses[pk] -= 1
                if part_uses[pk] > 0:
                    history[pk].append(rows)
                else:
                    history.pop(pk, None)
                rows = canonical_order(c, topic, rows).combine_chunks()
                et = rows.column(spec.event_time)
                late = 0
                if prev_mark is not None and rows.num_rows:
                    late = int(pc.sum(pc.less_equal(et, pa.scalar(prev_mark, pa.int64()))).as_py() or 0)
                if rows.num_rows:
                    m = int(pc.max(et).as_py())
                    burst_max = m if burst_max is None else max(burst_max, m)
                    out = rows if self.audience == "consumer" else self.store.attach_restricted(topic, rows)
                    yield ReplayBatch(topic, t_ingest, tail, sortie, out, late)
            if sortie is not None and tail is not None and burst_max is not None:
                mark = burst_max if prev_mark is None else max(prev_mark, burst_max)
                marks[(tail, sortie)] = mark
                yield Watermark(tail, sortie, t_ingest, mark)


class ObservationView:
    """The decision-maker's information set (I5): contract records with t_ingest <= t, deduplicated, read
    from the consumer tree only (no restricted topics or fields). This is the hook the orders interface (M21)
    uses. ``audience="validation"`` (explicit) also joins the restricted part."""

    def __init__(self, store: ParquetStore, *, audience: str = "consumer"):
        if audience not in ("consumer", "validation"):
            raise ValueError("audience must be 'consumer' or 'validation'")
        self.store = store
        self.audience = audience

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
        """Records of ``topic`` ingested at or before ``t`` (earliest ingest kept), in canonical order."""
        c = self.store.contract
        spec = c.topics[topic]
        _check_audience(self.store, topic, self.audience)
        if spec.ingest_time is None:
            raise PermissionError(f"topic {topic} has no ingest time; it is not observable")
        parts: dict[str, str | None] = {}
        if tail_no is not None and "tail_no" in spec.partition_by:
            parts["tail_no"] = tail_no
        if sortie_id is not None and "sortie_id" in spec.partition_by:
            parts["sortie_id"] = sortie_id
        pieces = []
        files = self.store.files(topic, date_from=date_from, date_to=date_to, partitions=parts, tree=CONSUMER)
        for path in files:
            tab = self.store.read_file(topic, path, tree=CONSUMER)
            pieces.append(
                tab.filter(pc.less_equal(tab.column(spec.ingest_time), pa.scalar(int(t), pa.int64())))
            )
        table = pa.concat_tables(pieces) if pieces else self.store.tree_schema(topic, CONSUMER).empty_table()
        for name, v in (("tail_no", tail_no), ("sortie_id", sortie_id)):
            if v is not None and name in table.schema.names:
                table = table.filter(pc.equal(table.column(name), pa.scalar(v)))
        table, _ = dedup_by_record_id(c, topic, table)
        table = canonical_order(c, topic, table).combine_chunks()
        return table if self.audience == "consumer" else self.store.attach_restricted(topic, table)

    def ingested(self, t: int, record_ids: Sequence[bytes]) -> np.ndarray:
        """For each record_id, whether a consumer-visible record with that id was ingested at or before ``t``
        (the M21 evidence check: an order citing un-ingested evidence is rejected)."""
        c = self.store.contract
        want = pa.array(list(record_ids), pa.binary(16))
        found = np.zeros(len(want), dtype=bool)
        for topic in c.topic_names:
            spec = c.topics[topic]
            if spec.ingest_time is None or spec.restricted:
                continue
            for path in self.store.files(topic, tree=CONSUMER):
                tab = pq.read_table(path, columns=["record_id", spec.ingest_time])
                ok = tab.filter(pc.less_equal(tab.column(1), pa.scalar(int(t), pa.int64())))
                found |= pc.is_in(want, value_set=ok.column(0).combine_chunks()).to_numpy(
                    zero_copy_only=False
                )
        return found
