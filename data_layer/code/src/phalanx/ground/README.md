# M17 Ground decoder → canonical contract (W0.4 part: CIR, record_id, fast path)

**Purpose.** Turn what the observation layer produces (the CIR) into contract records. W0.4 builds the CIR
definition, the deterministic `record_id`, and the fast path. The full-path decoder (Ch10 → contract) is W1.7 and
must emit the identical schema (AD-12).

## Interfaces

```python
from phalanx.ground import (
    CIR_SCHEMA,
    CirBatch,
    validate_cir,
    assign_sample_index,  # cir.py
    record_id,
    record_ids,
    to_hex,
    from_hex,
    encode_key,  # rid.py
    FastPathConfig,
    cir_to_param_samples,
    cir_to_truth_labels,  # fast_path.py
)

batch = CirBatch(tail_no, sortie_id, cir_table)  # columnar, one (tail, sortie)
cfg = FastPathConfig.from_dictionary(load_dictionary(), engine_serial="E404-0001")  # production config
batch = cir_from_streams(contract, tail_no, sortie_id, [StreamSamples(...), ...])  # M13 helper
truth = truth_at_samples(t_sample, truth_240hz, epoch_ns=epoch, k0=k_first)  # truth at the LRU ticks
samples = cir_to_param_samples(batch, cfg, t_ingest=download_ns)  # validated param.samples table
labels = cir_to_truth_labels(batch, cfg)  # RESTRICTED labels.truth table
rid = record_id(contract, "orders.commands", {"order_id": "ORD-1"})  # 16 bytes
```

**CIR** (`cir.py`, version 0.1.0): an Arrow table, one row per acquired sample: `param_id`, `source_lru`,
`lane`, `sample_index` (per-stream acquisition index within the sortie), `t_true`, `t_sample` (int64 ns, sim UTC),
`value` (dictionary EU), `truth_value` (RESTRICTED), `validity`, `quality_flags` (acquisition scope only),
`rng_key_path` (the `phalanx.core.rng.KeyPath.canonical()` text of the sample's noise stream, AD-37; build it with
`key_path_text(KeyPath.of(...))`, read it back with `parse_key_path`). Validation enforces types, nullability,
patterns, enum and flag scope, no NaN, `t_true ≤ t_sample`, a strictly increasing `t_sample` per stream, and that
every `rng_key_path` round-trips exactly through `KeyPath`.

**Overlap with `phalanx.core` (W0.2).** `core.canonical` also provides canonical JSON and personalised blake2b
digests. W0.4 keeps its own (built before W0.2 merged): `record_id` uses person `phalanx.rid.v0` (16-byte digest,
typed length-prefixed encoding); the contract hash is blake2b-256 of canonical JSON with `ensure_ascii=False`
(the spec contains `§`) and no person string. Aligning them on `core.canonical` (e.g. person `phx.rid.v1`,
`phx.contract.v1`) is a coordinator decision: it would change the golden record_ids and the contract hash.

**record_id** (`rid.py`): `blake2b(digest_size=16, person=b"phalanx.rid.v0")` over
`enc_str(topic) || enc(component)...` with `S`/`R`/`N`/`U`/`I`-tagged, length-prefixed components in the
topic's `record_id_key` order. The scalar function is the reference; `record_ids` is the vectorised path
(identical, about 0.7 µs per record: the per-stream string prefix is hashed once and its state copied per row).

**Fast-path rules** (A-W0.4-3/4/5): `channel_id = "direct:<source_lru>:<lane or empty>"`, `seq = sample_index`,
`msg_index = 0`; `t_bus`, `t_record`, `raw_counts`, `bus`, `rt_sa_word`, `label_sdi` are null; `t_utc = t_sample`
(**PROXY**: perfect time source); `t_ingest` supplied by the caller (≥ every `t_sample`); truth goes only to
`labels.truth`.

**Dictionary binding.** `FastPathConfig.from_dictionary(d, engine_serial=...)` carries the dictionary's
channel set `(param_id, source_lru, lane)` (from `Dictionary.contract_location`) and each channel's range.
A CIR stream that is not a dictionary channel (unknown lane, wrong LRU, unknown measurand) rejects the batch;
a value outside the channel range is kept and flagged `OUT_OF_RANGE` (decoder-side quality flag; saturation
is M13's job). A string `engine_serial` applies to every measurand of the `engine` and `engine_usage`
subsystems (LUIs and TAC included). A hand-built `FastPathConfig` (no `channels`) checks units only; it is
for interface tests.

**One channel set on both paths (AD-54, coordinator decision W2.2).** The consumer-visible `param.samples`
channel set is identical on the fast and full paths: `from_dictionary(..., fti_fitted=False)` keeps only
channels with a full-path transport (`RECORDED_TRANSPORTS`: 1553 data, status and mode-code words,
ARINC-429; plus `fti_pcm` when the FTI system is fitted, as `run_full_path(fti_fitted=...)`). LRU-internal
lanes (transport `internal`, the ADC-DFCC RS-422 links) are accepted as dictionary channels but stay in the
CIR and internal diagnostics; their truth labels are not emitted. Test:
`tests/integration/test_w22_fast_full_channel_sets.py` (equal sets for one sortie, negative control, transport
rule = M15 bus ICD). Tracked: with FTI fitted the full path also emits zero-fill records for FTI PCM words no
producer populates (phase B).

**Building CIR from M13 outputs.** `cir_from_streams` takes one `StreamSamples` per stream with explicit
per-stream counts (no NaN padding; missing truth is a `truth_present` mask, stored as null). `t_true`
defaults to `t_sample` (A-W0.4-21): truth interpolated at the LRU tick (`truth_at_samples`) is the truth at
that instant, and sensor lag is measurement error. Give an earlier `t_true` only when the model reports the
physics instant its value refers to.

**Contract 0.2.0 (W2.2, additive; A-W0.4-22).** `param.samples` carries `recording_id` and `sink` (AD-25
per-sink recordings). The fast path sets both null. On the full path the record-id `channel_id` component is
`rid.full_path_channel_id(ch10_channel, recording_id)`: `<recording_id>:<channel ID>` for an identified
recording, the bare 0.1.0 channel ID otherwise; `rid.check_recording_identity` enforces "both null or both set"
and the key-safe patterns. `migrate.py` checks additivity between versions and projects/upgrades tables
(`project(t_020, c020, c010, topic)` is what a 0.1.0 consumer reads); see
`src/phalanx/dictionary/contract/MIGRATION.md`.

**Channel coverage (W2.2, U6; A-W2.2-11).** `coverage.load_coverage()` reads
`configs/tejas/coverage/channel_coverage.yaml`: every dictionary channel's owner class (`m12_sensor`,
`recorded`, `topic`, `not_simulated`), the producing module and port, the acquisition gap of a produced channel
the recording path cannot record yet, and the named gaps (owner, work package, plan). A `not_simulated` channel
never appears in `param.samples` (contract state `absent`); `ChannelCoverage.in_param_samples` says whether a
channel reaches `param.samples` today.

## Assumptions (tagged; rows in `docs/assumptions.md`)

- A-W0.4-2 record_id definition; A-W0.4-3 fast-path id components; A-W0.4-4 **PROXY** fast-path time and null
  rules; A-W0.4-5 caller-supplied ingest time; A-W0.4-6 CIR in dictionary EU (M13 converts SI → EU);
  A-W0.4-22 recording identity (contract 0.2.0).

## Validation criteria

| Criterion | Tests |
|---|---|
| A4 record_id deterministic, golden, collision-free on a designed corpus, vectorised = scalar | `tests/unit/test_ground_record_id.py`, `tests/property/test_ground_record_id_props.py` |
| A7 fast-path output is the contract schema and validates; malformed input rejected | `tests/unit/test_ground_fast_path.py` |
| CIR rules each bite (negative tests) | `tests/unit/test_ground_cir.py` |
| Contract 0.2.0 is additive; 0.1.0 consumers pass (projection = 0.1.0 output, same record ids); recordings never collide | `tests/unit/test_w22_contract_020.py`, `tests/integration/test_w22_contract_020_full_path.py` |
| U6: 464/464 channels classified and the plan agrees with the code (producers, acquisition, topics, NM cross-references, named gaps) | `tests/integration/test_w22_channel_coverage.py` |

## Known limitations

- The fast path has no bus, recorder or download model, by design (PROXY A-W0.4-4); W1.7 replaces it.
- `FastPathConfig.units` / `engine_serial` are plain maps until the M01 API (W0.3) is wired in (W0.X).
- `examples.py` holds EXAMPLE CIR batches (deterministic ramps) for interface tests only; never simulation output.
- `assign_sample_index` is valid only on whole-sortie tables; block producers must carry their tick index.
