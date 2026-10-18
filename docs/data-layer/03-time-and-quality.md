# 03 · Time model, information discipline and data quality

References: kit `README.md` §4, §6, §7; `reference/architecture.md` §7–8, AD-05/06/35/42/45;
`contract/contract.md` "Conventions"; modules M13, M15, M16, M17, M19.

## Time

- **Every time field is `int64` nanoseconds.** Scale `sim_utc` = POSIX ns since 1970-01-01Z (no leap seconds).
  Contract time = scenario epoch + kernel time; truth step k sits exactly at `E + (k·10⁹)//240`.
- Exception: `t_record` uses `recorder_rtc` (Ch10 10 MHz RTC × 100 ns) with a **per-recording arbitrary origin**
  — never compare `t_record` across recordings or with other times.
- Local time for operations is **IST (UTC+05:30)**; decision epoch is daily 08:00 IST by default.

### The six sample timestamps

| Field | Meaning | Fast path | Full path |
|---|---|---|---|
| `t_true` | Physics time | never in contract (CIR/labels only) | never |
| `t_sample` | When the LRU acquired the value, on its **drifting oscillator** — the event time | CIR instant | decoder's *estimate* from ICD latencies (error ≤ T_update/2) |
| `t_bus` | When it appeared on the bus | null | reconstructed sim-UTC of the tagged bit |
| `t_record` | Recorder RTC | null | IPTS × 100 ns |
| `t_utc` | Aircraft GPS/IRIG time source | `= t_sample` (PROXY) | raw; `TIME_SOURCE_INTERNAL` flag on lock loss |
| `t_ingest` | Arrival at the ground (per-sortie download burst) | caller-supplied download instant | M16 delivery instant |

Event/record times: `events.*` → `t_occurrence` (declared on board); `usage.counters` → `t_update`;
`sortie.manifest` → `t_start`; `maint.records` → `t_event` (instant this version refers to) with `t_open`,
`t_close`; orders → `t_issued`/`t_status` (event time = availability time).

### Clocks are not aligned (by design)

- Truth runs at 240 Hz. Each LRU samples on its own oscillator with a fractional offset Δ (e.g. FADEC 60 Hz
  +50 ppm; recorder-vs-source Δ ≈ 910 ppm measured on real DASHlink data).
- Rates that do not divide 240 Hz are **clock domains**: 1553 avionics groups AV50/25/12.5/6.25, FADEC 50–67 Hz
  (nominal 60), CDR 16/8/4/1 Hz, ECMS 10/1 Hz, HUMS 1 Hz, vibration HF 2.5–10 kHz → features.
- Consequences: channels from different LRUs are **not on a common time grid**; resample explicitly (the
  validation harness uses "latest sample at or before each grid instant, sentinels kept"). Digital bus words show
  **duplicates and skips** from bus-controller schedule mismatch; analog paths show periodic **slip-window
  sentinels** every 1/(f·Δ) seconds. **There is no independent random dropout process.**

## Information discipline (invariant I5) — the most important rule

> A consumer sees a record only once `t_ingest ≤ t_now`. A decision at time t may use only records with
> `t_ingest ≤ t`. An order citing evidence not ingested by `t_issued` is **rejected**.

Latency chain you must model, not ignore:

| Data | When it becomes visible |
|---|---|
| Ch10 recording (`param.samples`, full path) | First delivery `max(10 min, LN(2 h, 0.8))` after the sortie; 3 % of first transfers interrupted (prefix then retry); 5 % of sorties re-downloaded |
| `events.*`, `usage.counters` (M14) | shutdown + `download_delay` = **1,800 s** (sweep 600–7,200 s) |
| `maint.records` SORTIE row | 0.5 h after `ops.sortie_done` |
| Defect opened from a downloaded event | event `t_ingest` + 0.33 h (HMS review) |
| `maint.records` generally | `t_ingest` includes reconciliation lag (defect injection can add up to 14-day lag) |

At the snapshot, a sortie's events and its full-path samples can carry **different `t_ingest`** values (separate
download models) — visible in `examples/`. Always filter each topic by its own `t_ingest`.

**Backtesting rule for us:** every feature, label join and model evaluation must be computed "as of" a decision
time using `t_ingest`, never event time. Using `t_sample`/`t_event` alone leaks the future (look-ahead), and the
orders gateway will reject such evidence anyway.

## Validity (per sample / counter)

| Value | Meaning | Source |
|---|---|---|
| `NORMAL` | valid | |
| `NO_COMPUTED_DATA` | source cannot compute (ARINC NCD); M13 gating sets it with `GATED` | 429 SSM / acquisition |
| `FUNCTIONAL_TEST` | produced under test | 429 SSM |
| `FAILURE_WARNING` | source declares failure (reserved for 429 FW; also TAC out of 0.4–15/FH) | 429 SSM / counter check |
| `BUS_INVALID` | 1553 validity bit / RT status flag / block-status or parity error | 1553 |

An RT that answers but has no data for an item marks it invalid → decodes as `BUS_INVALID` (example: `ENG.OIL_P`
in `examples/full_path/`, which carries `value_eu = 0.0` and `quality_flags = 0` — so **filter on `validity`,
not on flags alone**). A not-simulated channel currently has **no records** on the fast path; on the full
path an RT with no data at all doesn't answer (no records). How the contract will mark not-simulated channels is
**not yet specified**.

## Quality flags (`uint32`; bits 11–31 reserved, must be zero → mask `0xFFFFF800`)

| Bit | Mask | Flag | Scope | Meaning |
|---|---|---|---|---|
| 0 | `0x001` | `SENTINEL` | acquisition | value is a sentinel word (bottom-of-scale in analog slip window), not a measurement |
| 1 | `0x002` | `GATED` | acquisition | gated by acquisition validity logic |
| 2 | `0x004` | `HELD_STALE` | acquisition | held from an earlier sample |
| 3 | `0x008` | `DUPLICATE_POLL` | bus | same producer update read twice by asynchronous poll (full path: inferred, precision ≥ 0.95 / recall ≥ 0.9) |
| 4 | `0x010` | `SUBSTITUTED` | acquisition | synthesised by FADEC/signal validator (model substitution) |
| 5 | `0x020` | `VOTED_OUT` | acquisition | lane voted out by redundancy management |
| 6 | `0x040` | `OUT_OF_RANGE` | acquisition | outside dictionary range or saturated — **kept and flagged, not clipped** |
| 7 | `0x080` | `CLOCK_SUSPECT` | recorder | clock jump / drift beyond tolerance |
| 8 | `0x100` | `TIME_SOURCE_INTERNAL` | recorder | GPS/IRIG lock lost |
| 9 | `0x200` | `DUPLICATE_DOWNLOAD` | ground | first delivered by a repeat download |
| 10 | `0x400` | `DECODER_INTERPOLATED` | ground | decoder interpolated a value/time (holdover) |

**Unflagged artefacts exist on purpose:** M13 episodic freeze and glitch words (top of scale) carry no flag.
Robust feature extraction must handle them (e.g. run-length checks for freezes, top-of-scale spike filters).

## Missing data, NaN and sentinels

- **No NaN or ∞ in any float field, ever.** Missing = null, and only in nullable fields.
- Sentinels are carried as their decoded value + `SENTINEL` flag — **drop or mask them before statistics**,
  they look like real (extreme-low) values.
- Real recorder data behave the same way (DASHlink: 186 params, zero NaN in 121k records).

## Quantisation and noise ("texture")

- Values are quantised twice: native sensor/LRU step, then recorder lattice (`native_step`, `recorder_lsb` in
  the dictionary; where native resolution is unknown, native step = LSB). Values are lattice-valued — e.g. EGT
  never uses some residues mod 8 on real data.
- Idiosyncratic noise is AR(1) with a heavy-tail mixture, capped at the measured real-flight level ("noise
  ceiling"): N1 lanes 0.61 native steps, N2 0.16, T5 and WFM 0, others ≈ 0.144 steps; computed words 0.
- **All cross-channel coupling (correlations, lead/lag, regime dependence) comes from closed-loop physics**, not
  from noise. So multivariate residual/physics-based features are meaningful by construction.

## Duplicates, late data and idempotency

- Ingest is idempotent by `record_id`: keep the earliest `t_ingest`, verify identical content on repeats
  (the reference store raises `RecordIdConflict` on mismatch).
- Re-downloads re-deliver the same `record_id`s; records first delivered by a repeat download carry
  `DUPLICATE_DOWNLOAD`.
- Decoding is causal: a partial download decodes its records exactly like the complete one.
- Replay watermarks are per sortie (max event time delivered so far); a live consumer can't know no later
  re-download will come — late rows surface as `late_rows`.

## Consumer checklist for this layer

1. Dedupe on `record_id` (earliest `t_ingest`).
2. Filter every topic by `t_ingest ≤ decision time`.
3. Never compare `t_record` across recordings; prefer `t_sample` for physics alignment, `t_ingest` for availability.
4. Mask `SENTINEL`, treat `validity != NORMAL` as missing, keep `OUT_OF_RANGE` as a signal (could be a fault).
5. Resample per clock domain deliberately; don't assume synchronous channels.
6. Assert `quality_flags & 0xFFFFF800 == 0` and the file's contract hash on load.
