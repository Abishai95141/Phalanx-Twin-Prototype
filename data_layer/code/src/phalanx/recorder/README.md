# M16 Recorder writer and download simulator (W1.7)

**Purpose.** Write one IRIG 106 Chapter 10 recording per sortie (a *surrogate* recorder format, AD-24) from
M15 bus traffic, and simulate its post-flight download to the ground. Architecture §6 M16, §8, §12; AD-24, AD-25,
AD-38.

## Interfaces

```python
from phalanx.recorder.writer import STREAMS, RecorderConfig, RecordingEvent, write_recording, Recording
from phalanx.recorder.download import DownloadConfig, simulate_download, Delivery
from phalanx.recorder.full_path import run_full_path, full_path_truth_labels, FullPathResult
from phalanx.recorder import ch10  # packet encoders: setup, time, 1553, 429, PCM, events, index, analog...

res = run_full_path(cir_batch, ident=ident, rng=rng, t_start=..., t_end=...)  # M15 -> M16 -> download -> M17
res.recording.data  # .c10 bytes;  res.deliveries -> Delivery(t_ingest, bytes, attempt, complete)
res.decoded[k].samples  # contract param.samples, provenance full_path
labels = full_path_truth_labels(res.recording, cir_batch)  # RESTRICTED labels.truth (TRUTH_SAMPLE)
```

`STREAMS` (AD-37): `recorder.rtc_offset` (scenario, serial), `recorder.rtc_start`, `recorder.lock_loss`,
`recorder.download` (scenario, tail, sortie).

## The recording

- **Setup record first**: the M01 dictionary TMATS with the dictionary's recorder setup, verbatim
  (`writer.setup_record` = `generate_tmats(recording=True, extra_events=...)`; recorder events from
  `Dictionary.recording_events()`, index interval from `Dictionary.recorder_setup()`; rule R-REC-SETUP,
  A-W0.3-44). Dictionary 0.1.2 migration (W2.2): the W1.7 overlay of `R-1\EV\*` / `R-1\IDX\*` (A-W1.7-12) is
  gone; the recording bytes are unchanged (`tests/integration/test_w22_datapath_migrations.py`). FTI PCM words
  no producer populated in the recording (all frame rows without CIR data) are spare slots: they stay in the PCM
  frame as zero words but the setup record does not describe them (`writer.unpopulated_pcm_words`,
  `generate_tmats(pcm_unpopulated=...)`), so the ground emits no zero-fill records (W2.2, AD-54; A-W2.2-14).
- **First dynamic packet is a time packet**; IRIG-B time packets at every time-source second (month/year
  format, so the year is carried); during a lock-loss holdover the TCG free-runs on the recorder crystal
  (SRC internal) and relocks at the next true second (`timesource.py`).
- **Data packets** per channel (channel IDs from the TMATS R group): 1553 F1 (TTB 01, IPDH with block status,
  GAP1, length), ARINC-429 F0 (ID words with gap times), PCM F1 (unpacked, IPH per minor frame); each packet
  ≤ 100 ms of data, committed when its timer expires; 32-bit data checksums (as in the public sample).
- **Recording events** (F2): REC_START, TIME_LOCK_LOST/REGAINED and caller events (e.g. M14 BIT events);
  **node/root index** (F3) covering every time and event packet; root index last.
- **8-bit sequence numbers wrap**; the cumulative count (AD-38) is what the decoder and the truth table use.
- **RTC**: 10 MHz on the recorder crystal (offset per unit), arbitrary start count; exact integer arithmetic.

## Download

Per sortie: first delivery `max(10 min, LN(2 h, 0.8))` after the sortie; 3 % interrupted first transfers (a
prefix, then a retry); 5 % repeat downloads (A-W1.7-10). Re-delivered records keep their `record_id`.

## Assumptions (tagged; `docs/assumptions.md` W1.7) and PROXY

A-W1.7-8 (RTC crystal), -9 (time source, lock loss), -10 (download), -13 (monitor latency); the recorder
events and index are the dictionary's (A-W0.3-44, replacing A-W1.7-12 in W2.2). **Recording identity
(contract 0.2.0, A-W0.4-22):** `write_recording` / `run_full_path(..., recording_id=..., sink=...)` label a
recording; the deliveries carry the label and the decoder fills `recording_id` / `sink` and qualifies the
record-id channel component (the file bytes do not change). The default (both None) is the W1.7 single capture,
whose records keep their 0.1.0 ids. **PROXY A-W1.7-11: one recording for all sinks** (contract side resolved by
0.2.0; the per-sink writer still needs per-sink setup records from M01) — the CDR, ECMS log, HUMS DAU and OAC maintenance
log are not yet separate recordings with their own subsets, rates and clocks (AD-25); exposed by
`tests/integration/test_recorder_writer.py::test_proxy_single_recording_has_no_sink_subsets`. Parameters:
`configs/tejas/params/M16.yaml`.

## Validation criteria

| Criterion | Tests |
|---|---|
| A3 packets parse in pyChapter10 and the independent M17 reader (all types; golden BCD time) | `tests/unit/test_recorder_ch10.py` |
| A3 whole-file agreement of the two parsers; file-order rules; ≤ 100 ms packets; seq wrap; index coverage | `tests/integration/test_recorder_writer.py` |
| A3 conformance vs the public KC-135 sample (header layout, TTB, checksum conventions) | `tests/integration/test_recorder_sample_c10.py` (data) |
| RTC exactness (property), time packets, holdover drift, lock-loss Poisson rate | `tests/unit/test_recorder_timesource.py` |
| Setup record = dictionary recording TMATS; only EV/IDX lines differ from the plain TMATS; round-trips | `tests/unit/test_recorder_setup.py` |
| Dictionary 0.1.2 migration leaves the recording bytes unchanged (golden from before W2.2) | `tests/integration/test_w22_datapath_migrations.py` |
| Download outcomes, determinism, delay distribution | `tests/unit/test_recorder_download.py` |
| A8 identical `.c10` bytes and decoded Parquet (in process and in a fresh process) | `tests/integration/test_decoder_full_path.py` |

## Known limitations

- **pyChapter10 1.1.19 deviates from the IRIG 106-15 text** for four fields this writer emits per the standard:
  the recording-event entry word, the PCM CSDW lock-status/indicator bits, the 1553 CSDW time-tag bits and the
  root-index offset read. The tests pin both behaviours; irig106lib is not installed to arbitrate.
- Analog F1 and discrete F1 writers/readers exist and are tested, but the dictionary declares no recorder-direct
  analog or discrete channel, so recordings contain none.
- No CDR loop overwrite (a lost file *start* would shift cumulative packet counts and record ids; only prefix
  truncation is simulated).
- File size ≈ 2.4 MB per sortie-minute for all buses; full chain ≈ 3.3 CPU-s per sortie-minute (fixture CIR).
