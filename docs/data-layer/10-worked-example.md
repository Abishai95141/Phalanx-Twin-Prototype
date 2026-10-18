# 10 · Worked example: one sortie through the contract

Source: kit `examples/` (FORMAT EXAMPLES — hand-set inputs, **values are not physics**). Verified independently:
all 11 Parquet + 3 JSON files match the published consumer schemas (incl. metadata), every `record_id`
(106/106) recomputes from the documented rule, and every Parquet file re-writes byte-identically with the
documented writer options. Identities: tail `TJ101`, base `SUL`, sortie `TJ101-20261010T0902`, engine
`ENG-000001`; run epoch 2026-10-10T00:00Z.

## Timeline (UTC)

| Time | What happens | Topic(s) |
|---|---|---|
| 10-10 00:00 | Initial configuration: 19 `COMPONENT_LIFE` INSTALL v0 (18 LRU triplets + engine `ENG-000001`, 587.84 h, 1,469.61 cycles), `TECH_LOG` v0 SERVICEABLE/FMC, first `AVAILABILITY_STATE` (FMC) | maint.records |
| 09:00:00 | Engine start (`t_start`) | sortie.manifest |
| 09:02:30 | Take-off (`sortie_id` encodes 0902) | sortie.manifest, SORTIE `t_open` |
| 09:04:56.8 – 09:05:10.9 | **T5 over-temperature** `ENG-701`: peak 831.6 °C vs `ENG.T5:steady_max` 830, persistence 18, CAUTION/PFL, suspects ENGINE 0.7, T5_HARNESS_A/B 0.15; CWS legend `CWS-L08` displayed, cleared 09:05:10.9 | events.exceedances, events.cautions (same `event_id`) |
| 09:06:40.000 | **CBIT `ENG-001` "N1 sensor lane A fail"**, ADVISORY/MFL, latched, `detection_far_per_fh` 6.06e-4, suspects FADEC 0.2, N1_PICKUP_A 0.8; snapshot window 09:06:35 → 09:07:05 | events.bit_faults |
| 09:06:40 ± | Samples inside the snapshot window: fast path ENG.N2 A/B/V + ENG.T5 at 60 Hz; full path ENG.N1.V/N2.V/T5/WFM at 25 Hz and ENG.OIL_P at 12.5 Hz (`BUS_INVALID`, value 0 — RT answered without data) | param.samples (store/ and full_path/) |
| 09:27:30 | Landing | manifest, SORTIE `t_close` |
| 09:28:20 | ECMS LUI write #1 (`update_seq` 0) | usage.counters |
| 09:30:00 | Shutdown (`t_end`); LUI write #2 + OAC counters (+ one 1/240 s kernel step) | usage.counters |
| **10:00:00** | **Download**: every per-sortie topic + SORTIE row get `t_ingest` 10:00 | all per-sortie topics |
| 10:19:48 | M18 reviews the downloaded BIT event (+0.33 h): `DEFECT_WO` `SUL-26283-0001` v0 OPEN → v1 DEFERRED (`AT-DEF`), `evidence_record_ids` = the BIT event's `record_id`; text "HMS/BIT CODE ENG-001 SET ON DOWNLOAD. ENGINE FADEC (DUAL CHANNEL) SUSPECT."; TECH_LOG v1 "DEFERRED: SUL-26283-0001" (still FMC) | maint.records |
| 12:54:02.88 | Separate Ch10 download → full-path samples ingested (different `t_ingest` from the events!) | param.samples (full_path/) |
| **10-11 02:30 (08:00 IST epoch)** | Two orders: `EXAMPLE:20261011:001` HUMAN TROUBLESHOOT `{"code":"ENG-001"}`, evidence = DEFECT_WO v1 → ACCEPTED; `EXAMPLE:20261011:002` AGENT INSPECT `{"type":"BORESCOPE"}`, evidence = a non-existent id → **REJECTED** "evidence not ingested by t_issued: 0000…" | orders.commands, orders.status |
| 02:30 | Order 001 QUEUED → IN_WORK; defect v2 OPEN (REPEAT/RECURRING) → v3 IN_WORK; TECH_LOG v2 PMCM; availability bin PMCM | maint.records, orders.status |
| 06:39:51 | Defect v4 CLOSED: `MAL-NDF` / `AT-CND` "TROUBLESHOT … COULD NOT DUPLICATE. NO DEFECT FOUND. OPS CHK GOOD.", 12.49 man-hours; TECH_LOG v3 FMC; order COMPLETED with `result_record_ids` = defect v2, v3, v4 | maint.records, orders.status |
| 06:45 | Next 15-min bin boundary: availability FMC | maint.records |

This one example already shows the full chain the PS describes: **health monitoring → download latency →
technical record → decision (order) → maintenance action → availability state**, and an NFF/CND outcome.

## Linkage observed

```text
events.bit_faults.record_id ──► maint.records(DEFECT_WO).evidence_record_ids
maint.records(DEFECT_WO v1).record_id ──► orders.commands.evidence
orders.commands.order_id ──► orders.status.order_id ──► result_record_ids ──► maint.records (v2..v4)
maint.records.order_id = orders.commands.order_id
events.exceedances.event_id == events.cautions.event_id   (same occurrence)
sortie.manifest.lru_serials (part_no, serial_no, maker) == COMPONENT_LIFE triplets
usage.counters (FLIGHT_HOURS, LANDINGS, GROUND_STARTS, TAC) == SORTIE row (flight_hours, landings, engine_starts, engine_cycles)
```

## Identifier formats seen (not specified by the contract — treat as opaque, but useful for debugging)

| Identifier | Example | Pattern |
|---|---|---|
| `sortie_id` | `TJ101-20261010T0902` | `<tail>-<UTC YYYYMMDD>T<HHMM take-off>` |
| `event_id` | `TJ101:TJ101-20261010T0902:ENG-001:0` | `<tail>:<sortie>:<code>:<occurrence index>` |
| `job_no` | `SUL-26283-0001` | `<base>-<YYDDD>-<seq>` |
| AVAILABILITY_STATE `record_key` | `AV-TJ101-1791590400` | `AV-<tail>-<bin start epoch s>` |
| TECH_LOG `record_key` | `TL-TJ101` | `TL-<tail>` |
| COMPONENT_LIFE `record_key` | the serial | |
| serials / part numbers / makers | `FADEC-000001`, `SYN-PN-FADEC`, `SYN-MKR-*` | synthetic |
| `crew_id` | `PLT-sqa-01` | pseudonymous |
| `limit_id` | `ENG.T5:steady_max` | `<channel>:<limit kind>` |

Maintenance code strings seen: when-discovered `WD-HMS`, system `ENG`, malfunction `MAL-BIT` / `MAL-NDF`,
type-maint `TM-UNS`, action `AT-DEF` / `AT-CND`. `sw_config_id` `SW-BASE`; mission `GH`.

## Gotchas the example exposes

1. **Events and samples of the same sortie have different `t_ingest`** (10:00 vs 12:54) — filter per topic.
2. `orders.status` files are sorted by (event time, `record_id`), **not lifecycle** — sort by
   (`order_id`, `status_seq`) yourself.
3. `BUS_INVALID` rows carry `quality_flags = 0` and `value_eu = 0.0` — rely on `validity`, not on flags alone.
4. Fast-path vs full-path rows for the same signal coexist in one partition with different `record_id`s —
   choose one path per analysis.
5. Full-path `t_record` steps are 39,999,900 ns, not 40 ms (clock drift is real in the data).
6. `usage.counters.param_id` is the measurand (e.g. `STRUCT.NZ_COUNTERS.L3`), units include `hour` and `MJ`.
7. `confirmed_status` stays `UNCONFIRMED` on events forever; the confirmation (here: CND/NFF) lives only in
   `maint.records`.
8. JSON-Schema files don't enforce "reason required when REJECTED"; contract validation does.
9. `TECH_LOG` rows also carry `availability_state` (instantaneous state), not only AVAILABILITY_STATE bins.

## Verified storage facts

- File name `part-<20-digit min t_ingest ns>-<32-hex>.parquet`; the hex is `blake2b(file_bytes,
  digest_size=16)` (unkeyed). One file = one write batch (may span several ingest times).
- Writer: `pq.write_table(t, compression="zstd", compression_level=3, row_group_size=131072, version="2.6",
  write_page_index=False, write_page_checksum=False, store_schema=True)`; pyarrow 26.0.0; rows sorted by
  (event time, `record_id`) but `sorting_columns` not declared.
- Schema metadata keys: `phalanx.contract`, `phalanx.contract_version`, `phalanx.contract_hash`,
  `phalanx.topic`, `phalanx.topic_restricted`, `phalanx.event_time`, `phalanx.ingest_time`,
  `phalanx.partition_by` (non-date fields), `phalanx.record_id_key`, `phalanx.audience` (`consumer`).
  Field metadata: `phalanx.description`, `.basis`, `.restricted`, `.format`, `.pattern`, `.time_unit` (`ns`),
  `.time_scale`, `.enum` + `.enum_symbols`, `.flags` + `.flag_bits`, `.units`, `.minimum`.
- Which time drives the `date=` partition (event vs ingest) is undocumented (identical in the examples).
- `record_id` recipe verified: `blake2b(enc_str(topic) + components, digest_size=16, person=b"phalanx.rid.v0")`
  with `S`/`N`/`U`/`I`/`R`-tagged components. For orders this is the typed encoding — *not* plain
  `blake2b(order_id)` despite the field description.
- Library versions recorded in the manifest: numba 0.68.0, numpy 2.5.4, pyarrow 26.0.0, scipy 1.18.1.
- Avro: only producer-view `.avsc` exists (restricted field names appear in `sortie.manifest.avsc`); times are
  plain `long` with `phalanx.time_unit` attributes (no logical type).
