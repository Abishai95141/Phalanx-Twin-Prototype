# 11 · Preview dataset v0.9 — what we actually have to build on

Source: `/Users/abishaikc/Downloads/phalanx_data_layer_preview/` (README, `code/docs/previews/v0.9_README.md`,
`code/docs/contract/contract/MIGRATION.md`, `data/v0.9/MANIFEST.json`) plus our own profiling of the consumer
trees on 2026-10-15 (scripts kept in the session scratchpad). **PREVIEW: behaviour not yet validated** — use it
to build readers, pipelines, UI and model plumbing, not to draw conclusions about Tejas/F404 behaviour.

## Versions (changed since the context kit)

| Item | Kit snapshot (docs 01–10) | Preview v0.9 |
|---|---|---|
| Contract | 0.1.0, hash `18d7627b…` | **0.2.0** (frozen, AD-56), hash `a4396f1d5482ce78…`, schema hash `e8313f48…` |
| Dictionary | tejas 0.1.2 (`a8b02cab…`) | **tejas 0.1.3** (`9428d30f578f0318…`) — same 464 channels / 104 codes; 15 channels changed (FADEC lane native steps now the 14-bit converter step, T1, RADALT, AB_LIT) |
| Data-layer code | n/a | snapshot `fda9f98`; data generated at `6d4dc52` (main `0476ed9` + two pre-merge fix branches) |

**Contract 0.1.0 → 0.2.0 is additive:** `param.samples` gains two nullable trailing fields, `recording_id`
(unique within tail + sortie) and `sink` (CDR / ECMS_HUMS / MPDRU / FTI), both null on the fast path and for a
single unattributed bus-monitor capture. With `recording_id` set, the full-path `record_id`'s channel component
becomes `<recording_id>:<Ch10 channel ID>`. Nothing else changed. **Parquet files embed the exact contract hash,
so a 0.1.0 reader refuses 0.2.0 files** — read by column name and pin 0.2.0 (the data layer ships
`phalanx.ground.migrate.project/upgrade` bridges).

## What is in `data/v0.9/`

| Tree | Content | Size |
|---|---|---|
| `telemetry/` | 6 fast-path sorties (`provenance = direct`): `param.samples`, `events.*`, `sortie.manifest` | 162.9 M sample rows, 78 files, ≈ 3.2 GB (≈ 0.15 MB per flown second) |
| `telemetry_full_path/` + `ch10/` | first 600 s of TJ201-20260106T0300 via bus → Ch10 → download → decoder; the 17 MB IRIG 106 Ch10 file | 3.17 M samples |
| `fleet/` | usage-mode operations worlds, **8 tails (TJ101–TJ108) × 180 days** from 2026-01-05, policy `scheduled/1.0.0`, BIT regime immature | see below |
| `_restricted_labels/` | truth for evaluation only (fleet: DEFECT labels for injected data defects; full path: TRUTH_SAMPLE) — **never read by the solution** | |
| `_runs/` | per-run outcome JSON (completed / aborted + reason) | |
| `MANIFEST.json` | sha256 of every file, validation (leak audit: 0 findings), run outcomes, seeds | |

### Telemetry (profiled)

- Sorties: TJ109 INST_NAV, TJ115 GH, TJ201 AIR_TEST, TJ204 NAV_TRANSIT, **TJ212 GROUND_ATTACK (the only completed
  sortie, 6,174 s)**, TJ213 ACM_INTERCEPT. **5 of 6 end in `ground_impact`** during descent/pattern (a known
  low-energy guidance issue); data up to the abort is kept; the abort is recorded only in `_runs/` and MANIFEST
  (`sortie.manifest` shows `t_end` early and null `t_landing`).
- **123 consumer-visible `param_id`s from 6 acquiring LRUs** (ADC, BHEEM_EU, CWS, DFCC, ECFM_C, FADEC). Rates on
  the fast path are acquisition rates: hydraulic pressures 200 Hz; DFCC/ADC 80 Hz (65 channels); FADEC engine
  channels 60 Hz (N1, N2, T5, PS3, P5, T1, WFM, CVG, FVG, OIL_P, OIL_T, FUEL_INLET_T, AB_LIT, FADEC_STATUS);
  utilities/fuel 40 Hz; CWS words, FADEC discretes/fault codes 12.5 Hz; ECS/hydraulic temps/DC buses 10 Hz.
- **Only `V` (voted) lanes or simplex channels** appear — no A/B lane channels, so lane-disagreement sensor
  validation is not possible on this preview. **No vibration (`ENG.VIB.*`), chip detector or oil level
  channels.**
- Validity: all `NORMAL` except 12 `NO_COMPUTED_DATA`. Quality flags: `OUT_OF_RANGE` 5.55 M rows, `SENTINEL`
  0.93 M, both 15 k, `GATED` 12 — sentinels and out-of-range values are common enough to matter.
- Telemetry events: 19 BIT, 159 exceedances (83 × `ENG-701` T5 over-temperature, 64 hydraulic low, structural
  over-g), 167 cautions. The frequent T5 exceedances reflect the uncalibrated engine — do not read them as
  physics.
- `sortie.manifest`: `base` null, `lru_serials` empty, `sw_config_id` SW-BASE, engine serial `IN20-<tail>`.
  **No `usage.counters` in the telemetry tree** (a known lifecycle bug).
- `t_ingest` is hours after the recorder stop (e.g. TJ212: ≈ 18.6 h after `t_end`).

### Fleet (profiled)

| Topic | Rows | Highlights |
|---|---|---|
| `maint.records` | 10,085 | DEFECT_WO 3,902 rows / 361 jobs; TECH_LOG 2,260; AVAILABILITY_STATE 1,340; COMPONENT_LIFE 915 (529 INSTALL / 386 REMOVE); SORTIE 643 (542.6 FH; GH, BFM, FORMATION, INST_NAV, GROUND_ATTACK); SUPPLY_DEMAND 614 (MCM 543, AOG 71; mostly tyres, chutes, hydraulic pumps); INSPECTION 320 (SRV-L1 229, WASH 21, L2 minor/major, ROH 2); **SHOP_FINDING 91 — all `RTOK`**. No CANNIBALISATION, MODIFICATION or EXCEEDANCE_INSPECTION rows |
| `events.bit_faults` | 1,021 | top codes ENG-201 (199), HYD-101 (138), AVI-201/203/204 (117/104/92), HYD-001, AVI-202, LGB-501, ELE-405; ADVISORY 717 / CAUTION 271 / WARNING 33; CBIT 786 / PBIT 235 |
| `events.cautions` | 304 | HYD-101 138, LGB-501 33, ENG-401 29, SPS-501 28 …; all displayed |
| `events.exceedances` | 0 | none occur in usage mode |
| `usage.counters` | 21,219 | 33 counters (8 LUIs, Nz L1–L8, USAGE.*), sources OAC / ECMS / GROUND; all NORMAL |
| `orders.commands` / `.status` | 7 / 28 | all AGENT `WASH_SERVICE ENGINE_WASH` from the scheduled policy, each ACCEPTED → QUEUED → IN_WORK → COMPLETED |
| `sortie.manifest` | none | not produced in usage mode; SORTIE records carry the sortie identity |

- DEFECT_WO: when-discovered `WD-HMS` 2,909 / `WD-SCH` 958 / `WD-AIR` 35; malfunction `MAL-BIT` 2,344, `MAL-HT`
  956, `MAL-NDF` 398; actions `AT-DEF` 1,041, `AT-CND` 398, `AT-RR` 390; system codes LGB 1,120, ENG 680, AVI
  672, HYD 654. 295 of 361 jobs link `evidence_record_ids` to events. Free text has injected typos
  ("ENIGNE", "SUSPET", "(280 BA)R") and task refs like `PHX-TASK-HYDP`, `PHX-FIM-HYD`.
- Availability transitions: FMC 600, NMCM_S 252, NMCM_U 238, PMCM 213, NMCS 36, NMCD 1. Per-tail MC 0.375–0.816
  (uncalibrated; TJ108 stops flying after ≈ day 90).
- **Few persistent true faults** — events are dominated by false alarms and transients (the B8 NFF/CND
  behaviour is still failing). 91 RTOK and **zero CONFIRMED shop findings**.

## Critical consumer finding: identifiers collide across the 8 fleet worlds

Each tail is simulated as **its own world** (the M18 per-tail router is pending W2.6). The worlds reuse the same
serial numbers, job numbers and order ids, so `record_id`s collide when the eight trees are read together:

| Topic | Rows | Unique `record_id` | Duplicates |
|---|---|---|---|
| `maint.records` | 10,085 | 6,697 | **3,388** (e.g. `COMPONENT_LIFE` `ADC-000001` exists on all 8 tails; job `sulur-26006-0001` on several) |
| `orders.commands` | 7 | 6 | 1 (`scheduled:20260507T023000:001` issued on TJ101 and TJ102) |
| `orders.status` | 28 | 24 | 4 |
| events, usage.counters | — | — | 0 |

**Consequence:** naive "dedupe by `record_id`" (rule 4 in `RULES.md`) would silently drop a third of the
maintenance records. Until the shared-world fleet arrives:
- Treat each tail's world as a namespace: identity = (`tail_no`, `record_id`) for fleet topics; for orders use
  (`target_tail_no`, `order_id`). Counted per world there are **1,003 defect jobs** (not the 361 a global
  count suggests).
- **Exception — SHOP_FINDING rows have `tail_no` null** (they sit under `tail_no=__null__`), so their world
  cannot be read from the row or the path; tie each one to its world by matching `job_no` + `serial_no` + time
  against that world's REMOVE record (job numbers alone also collide).
- Treat serials as world-scoped: `ADC-000001` on TJ101 and on TJ102 are different physical units in the
  preview. Key the serial lineage on (`tail_no`, `serial_no`) for now, and switch to the global serial when the
  data layer ships a shared world.
- The preview has no shared spares pool, manpower or cannibalisation across tails — fleet-level spares and
  cannibalisation optimisation cannot be demonstrated on it yet.
- Report this to the data-layer team (it also affects their own `ParquetStore.read` dedup).

## Other format details observed

- `job_no` format is `sulur-<YYDDD>-<seq>` (lower-case base id), not `SUL-…` as in the kit examples.
- Engine serial formats differ by tree: telemetry `IN20-<tail>`, fleet `ENG-00000n` (world-scoped).
- `sortie_id=__null__` partitions hold records with no sortie (power-up records before the sortie opens,
  ground events).
- Reading: `pyarrow.dataset.dataset(path, format="parquet", partitioning=None)` gives exactly the contract
  schema (partition columns are also stored in the files). List-of-`record_id` columns
  (`evidence_record_ids`, `evidence`, `result_record_ids`) must be cast to `list<binary>` before converting to
  pandas.

## What this means for the build

| Capability | Demonstrable on v0.9 now | Needs later calibrated data |
|---|---|---|
| Ingestion, contract/hash gates, as-of store, dedup, lineage | yes (incl. the collision handling) | — |
| Fleet availability board, SCIR timelines, KPIs (MC/FMC/NMCM/NMCS) | yes (uncalibrated values) | calibrated priors |
| BIT false-alarm / NFF analytics, recurring-code triage, evidence-linked defects | **yes — the preview is dominated by exactly this** | — |
| Usage/life tracking from counters (LUIs, TAC, Nz), servicing due-dates | yes | — |
| Telemetry views, snapshot windows around events, baselining of engine parameters | yes (one completed sortie; treat physics as unvalidated) | validated fan–core/EGT dynamics |
| Fault-signature diagnosis, sensor-vs-component isolation via lanes | no (no A/B lanes, B7 sign mismatches, few true faults) | yes |
| Failure/RUL models trained on confirmed failures | no (0 CONFIRMED findings) | yes |
| Fleet-level spares and cannibalisation optimisation | no (per-tail worlds) | shared-world fleet (W2.6) |
| What-if forks | via the data-layer code (`code/src/phalanx/fork`) in-process | — |
