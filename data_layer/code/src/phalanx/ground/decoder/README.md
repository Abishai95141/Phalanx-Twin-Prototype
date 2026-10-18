# M17 Ground decoder, full path (W1.7)

**Purpose.** Turn a delivered Ch10 recording into contract `param.samples` with `provenance = full_path`, in the
**identical** schema as the fast path (AD-12; A5). Independent of M15/M16 code: it reads only the recording (its
own TMATS) and the M01 dictionary, so it decodes a real Ch10 file the same way. Architecture §6 M17, §8, §12;
AD-38.

## Interfaces

```python
from phalanx.ground.decoder import DecoderConfig, decode_recording, read_file, setup_from_tmats, TimeBase

res = decode_recording(
    delivery_bytes,
    dictionary=d,
    tail_no=...,
    sortie_id=...,
    t_ingest=...,
    attempt=0,
    engine_serial=...,
    config=DecoderConfig.from_params(),
)
res.samples  # validated param.samples;  res.events (recording events);  res.report (packets, errors)
```

`reader.py` is a minimal independent Ch10 reader written from IRIG 106-15 §10.6 (irig106lib is not installed):
headers and checksums, resync on bad sync/header, truncation; time F1, 1553 F1 (compiled message walk),
ARINC-429 F0, PCM F1 (unpacked), events F2, analog F1, discrete F1.

## Rules

- **Dictionary binding**: the TMATS must name the decoder's dictionary version and round-trip its layout
  (`setup.py`), else `DecoderError` (the BEA wrong-frame-layout failure mode). The one admitted difference: FTI
  PCM words the recording leaves undescribed are spare frame slots (no records; W2.2, A-W2.2-14); any other
  missing or moved measurand is a mismatch.
- **record_id** (AD-38): (full_path, tail, sortie, Ch10 channel ID, param_id, cumulative packet count, message /
  word / frame index). The cumulative count is unwrapped from the 8-bit sequence, so a lost or corrupt packet
  never moves later ids.
- **Times** (the W1.7 answer to the open `t_sample` question, A-W1.7-14): `t_record` = IPTS; `t_utc` = the
  aircraft time source's time of the tag; `t_bus` = best reconstructed sim-UTC of the Ch10-defined bit;
  `t_sample` = `t_bus` minus the nominal acquisition-to-tag latency built from the ICD (D_tag + L_proc +
  T_update/2 [+ L_relay + T_acq/2]). `latency_model="none"` gives `t_sample = t_bus`.
- **Causal decoding**: every decoded field depends only on packets at or before the record, so a partial
  download and the complete one decode shared records identically (idempotent ingest verifies equality).
- **Validity**: 1553 validity bit → dictionary code table `mil1553_validity_bit`; RT status SUBSYSTEM/TERMINAL
  flag or a block-status error → BUS_INVALID; BUSY/MESSAGE_ERROR → no data records; ARINC SSM via `ssm_bnr` /
  `ssm_dis`; parity error → BUS_INVALID.
- **Quality flags**: OUT_OF_RANGE (dictionary range, as on the fast path), DUPLICATE_POLL (A-W1.7-15),
  SENTINEL (A-W1.7-16), TIME_SOURCE_INTERNAL / DECODER_INTERPOLATED / CLOCK_SUSPECT (A-W1.7-17),
  DUPLICATE_DOWNLOAD (attempt > 0).

Parameters (declared nominal values; never the simulator's): `configs/tejas/params/M17.yaml`.

## Validation criteria

| Criterion | Tests |
|---|---|
| A4 decoded values = CIR (exact on the lattice), validity mapping, times within the clock model | `tests/integration/test_decoder_full_path.py` |
| A5 identical schema on fast and full paths (cross-path) | same file, `test_a5_*` |
| A6 re-download: no duplicates through ParquetStore / ReplayStreamer; prefix decodes like the full file | same file, `test_a6_*`, `test_partial_download_*` |
| A7 real public Ch10 sample decodes (bus level); param decode refuses a foreign layout | `tests/integration/test_recorder_sample_c10.py` (data) |
| A8 deterministic decoded Parquet (in process, fresh process) | `test_a8_*` |
| t_sample estimate bounded and centred; DUPLICATE_POLL precision ≥ 0.95, recall ≥ 0.9 vs M15 truth | `test_t_sample_*`, `test_duplicate_poll_*` |
| Time base: crystal removal, holdover, suspect cases, causality | `tests/unit/test_decoder_timebase.py` |
| Reader robustness: corruption, loss, truncation, garbage; cumulative sequence (property) | `tests/unit/test_decoder_reader.py` |
| Sentinel rule, config, dictionary binding | `tests/unit/test_decoder_quality.py` |

## Known limitations

- Acquisition-scope flags with no bus representation (GATED, HELD_STALE, SUBSTITUTED, VOTED_OUT) cannot be
  recovered from the recording; GATED/invalid 1553 data appear as a set validity bit, decoded as
  **BUS_INVALID** (AD-45, dictionary 0.1.2 `mil1553_validity_bit`; FAILURE_WARNING is reserved for the ARINC-429
  SSM failure-warning code). Code and test: `decode.py` validity mapping,
  `tests/integration/test_decoder_full_path.py` (1553 validity → BUS_INVALID).
- DUPLICATE_POLL and SENTINEL are inferences (no freshness word or sentinel code in the synthetic ICD).
- Recording events are decoded to (event id, number, count, times); full `events.*` records are not built here.
- A real recording of another platform decodes at bus level only (no param mapping without its dictionary).
