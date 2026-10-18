# M19 Streaming and storage (W0.4: Parquet store, replay streamer, information discipline)

**Purpose.** Persist and serve the contract (architecture §6 M19, AD-13): file-backed and deterministic in v1;
a Kafka adapter (Avro generated from the same Arrow schemas) is v1.x.

## Interfaces

```python
from phalanx.streaming import (
    ParquetStore,
    ReplayStreamer,
    ObservationView,
    ReplayBatch,
    Watermark,
    audit_consumer_tree,
)

store = ParquetStore.at(base, contract)  # producer side: <base>/consumer and <base>/restricted
consumer = ParquetStore(base / "consumer", contract)  # what a downstream team gets: no restricted root at all

store.write("param.samples", table, date="2026-10-14")  # validate, split, partition, canonical order, write
store.read("param.samples", tail_no="T001", sortie_id="S1", date_from=..., date_to=..., t_from=..., t_to=...)
store.read("sortie.manifest", audience="validation")  # explicit: joins the restricted part by record_id

for item in ReplayStreamer(store, until=t_now):  # audience="consumer" by default
    ...  # ReplayBatch(topic, t_ingest, tail_no, sortie_id, table, late_rows) or Watermark(tail, sortie, t_ingest, event_time)

view = ObservationView(store)  # the M21 information set (I5), consumer tree only
view.as_of(t, "events.bit_faults")  # only t_ingest <= t, deduplicated, no restricted data
view.ingested(t, record_ids)  # evidence check for orders

audit_consumer_tree(
    base / "consumer", contract, secrets=[...]
)  # [] = no restricted data in the consumer tree
```

**Restricted data is physically separated (I5; coordinator requirement R1).** Two sibling trees, neither inside
the other:

- the **consumer tree** holds consumer-visible topics written with the *consumer schema*: no restricted column,
  value or metadata. It can be handed to a downstream team as is; any Parquet reader (pandas, duckdb) sees
  nothing restricted;
- the **restricted tree** holds restricted topics (`labels.truth`) and the *restricted part* of consumer topics
  with restricted fields (`sortie.manifest`: `root_seed`, `rng_stream_table` plus the join keys record_id,
  partition fields, event and ingest time).

Every read defaults to `audience="consumer"` (least privilege). `audience="validation"` must be requested; it
joins the restricted part by record_id (rows without one get nulls; restricted fields of consumer topics are
nullable by a loader rule). A store without a restricted root refuses restricted writes (unless every restricted
value is null) and validation reads.

**Layout.** `<tree>/<topic>/date=YYYY-MM-DD/<partition field>=<value>/part-<min ingest>-<digest>.parquet`
(`__null__` for a null partition value). Per-sortie topics partition by `tail_no/sortie_id`; `maint.records` by
`tail_no`; orders by date only.

**Determinism.** Validation, exact tree schema, rows sorted by (event time, record_id), fixed writer options
(zstd 3, 131,072-row groups, format 2.6, stored schema, no page index or checksums), file name from the content
digest. Same records → same bytes and the same file (idempotent write). The only version-dependent bytes are the
pinned writer's `created_by`.

**Replay semantics** (A-W0.4-18). Bursts in (t_ingest, tail, sortie) order; topics in contract rank order; rows in
(event time, record_id) order; a per-sortie `Watermark` after each sortie burst (max event time delivered so far);
duplicates (re-downloads) dropped by record_id, keeping the earliest ingest, with content verification
(`RecordIdConflict` on mismatch); `late_rows` counts rows at or before the previous watermark.

## Assumptions

A-W0.4-17 (storage options and layout, two trees), A-W0.4-18 (replay semantics), A-W0.4-19 (non-negative times;
foreign contract files rejected). Rows in `docs/assumptions.md`.

## Validation criteria

| Criterion | Tests |
|---|---|
| A3 lossless round trip (validation read = input; consumer read = consumer projection); identical bytes across writes, row orders and a fresh interpreter | `tests/unit/test_streaming_parquet.py` |
| A5 event-time order, per-sortie watermarks, replay = files bitwise, duplicates suppressed | `tests/unit/test_streaming_replay.py` |
| A6 `as_of(t)` never returns t_ingest > t, and withholds nothing ingested (property) | `tests/property/test_streaming_as_of.py` |
| R1 leak test on all 10 topics (names, metadata, raw bytes, decoded values) with a positive control and 4 planted-leak negative controls; least-privilege defaults; consumer reads never touch the restricted tree | `tests/unit/test_streaming_restricted.py` |
| Toy end-to-end CIR → fast path → Parquet → replay, bitwise stable incl. subprocess | `tests/integration/test_streaming_toy_e2e.py` |

## Known limitations

- Replay and `as_of` read whole files; fleet-scale replay keeps only the partitions that will receive a later
  burst in memory, but `ingested()` scans every file (fine for W0; index it in W1.8).
- The leak audit checks the names the contract marks restricted and the secret values the caller supplies; it
  cannot know an unregistered secret. Run it with the run's seeds and a sample of truth values before release.
- No live transport (Kafka) yet; transport timing never feeds back into the simulation (AD-16) by construction.
- Watermarks are replay-time facts about delivered data; a live consumer cannot know that no later re-download
  will come (re-downloads surface as `late_rows`).
