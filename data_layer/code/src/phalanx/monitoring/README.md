# `phalanx.monitoring`: M14 monitoring, BIT, ECMS usage counters and CWS (W1.5)

M14 turns observations into the records a real fleet downloads:

- BIT fault records (`events.bit_faults`);
- limit exceedances (`events.exceedances`);
- CWS cautions and voice warnings (`events.cautions`);
- ECMS/OAC usage counters (`usage.counters`).

It also supplies the CWS words to the recorder (AD-42). M14 never reads truth. Its inputs are recorded values
(CIR, engineering units), controller fault reports and physical LRU conditions from M11. So false alarms,
missed detections, persistence and bursts emerge from the same path for healthy and faulty runs (I6).

Binding sources: architecture §6 M14, §9.4, §12, AD-19, AD-38, AD-41 (frozen contract v0), AD-42;
`W1_interfaces.md` §4; W1.5 brief. Evidence: report §9 (BIT model, regimes), `research_notes/.../
addendum_engine_F404_F414_monitoring*` (LUIs, ECMS), RADC-TR-81-220 (m-of-n, persistence) [TRANSFER].

## Interfaces

```python
from phalanx.monitoring import MonitoringModule, MonitoringConfig, load_code_table, load_monitoring_params
from phalanx.monitoring import contract_tables, cir_chunk_payload, bit_report_payload, cws_words_at
from phalanx.monitoring import ports  # PREFIX "monitor", RECORDED = {port: CWS channel}

codes = load_code_table(d, load_monitoring_params())
cfg = MonitoringConfig.from_dictionary(d, codes, ("IN20-0001",), regime="immature")  # or usage_mode=True
m14 = MonitoringModule("monitoring", load_monitoring_params(), config=cfg)  # event-only
tables = contract_tables(m14, state, dictionary=d, tail_no="KH2011", epoch_utc_ns=..., t_ingest_utc_ns=...)
```

Events handled:

| Event | Payload | Purpose |
|---|---|---|
| `monitor.sortie_start` | `sortie_id` | PBIT pass of every test; per-flight offsets |
| `monitor.observe` | `cir_chunk_payload(...)` (`ch`, `t`, `v`, `validity`; truth columns dropped) | limit monitors, LUIs, Nz counters, take-off trigger (chunk invariant) |
| `monitor.bit_report` | `bit_report_payload(code, lane, persistence, cleared)` | controller (M08/M05/M09) declarations and clears |
| `monitor.lru_condition` | `lru_condition_payload(code, magnitude, covered, ...)` | M11 physical LRU condition: shifts the code's test statistic |
| `monitor.landing`, `monitor.sortie_end` | `sortie_end_payload(...)` | LUI writes (twice per flight), OAC counters, TAC cross-check |
| `monitor.usage_summary` | `SortieUsage` payload | usage-mode counters |
| `monitor.sw_load`, `monitor.lru_replace`, `monitor.ibit` | | software-load burst; new unit offsets; ground IBIT/MBIT |
| `monitor.ack` | `n` | drain the first n outbox records after download |
| `monitor.usage_sortie` | `SortieUsage` payload + `t_start`, `t_end` | a whole usage-mode sortie forwarded by M10: PBIT at `t_start`, tests over the flight, LUIs/OAC counters at `t_end` |
| `fadec.fault` / `fadec.caution` (AD-44, M08) | `engine`, `code`, `set`, `sensor`, `lane`, `description`, `t_frame_ns`, `frame` | the FADEC's code is a dictionary `bit_codes` code (AD-48.5; M08 emits the unified table since W2.1b, so the W1 legacy-map setting is removed), declared or cleared at the frame instant. The FADEC's T5/N1/N2 limit cautions (`src: cir`, ENG-701..703) are not re-recorded. A code that is not an external FADEC code is an error. |
| `mx.action` (AD-44, M18) | `tail`, `pos`, `action`, `serial`, `sw_config_id` | `SWLOAD` starts the software-load burst; `RR` of an LRU position redraws that LRU's test offsets |
| `mx.monitoring` (AD-44, M18) | `tail`, `filter_codes_add` / `filter_codes_remove` | masked codes are still evaluated but not recorded (A-W1.5-42) |
| out: `pilot.fire_warning` / `pilot.fcs_caution` (AD-49, to `pilot_target` = M04) | `tail`, `code` | when a CWS record opens for the engine-fire warning (FIR group) or an FCS pilot-fault-list caution, at the record time (no earlier than the event that raised it: M14 is event-driven) |
| `ops.power_up` (W2.5, catalogued; M02 emission planned for W2.1a) | `tail_no`, `sortie_id` | power-up at engine start: PBIT (one pass of every testable code) and CBIT from then on, taxi included; a repeated power-up of the powered sortie is a no-op, another sortie's is an error |
| `ops.takeoff` (AD-48.2, M02) | `sortie_id`, `tail_no` | the sortie's identity; keeps an `ops.power_up` power-up (it must be the same sortie); powers up (PBIT) at take-off only when nothing powered the monitor up (PROXY A-W2.1c-4, retired once M02 emits `ops.power_up`; tracked by `tests/integration/test_monitoring_power_up.py::test_m02_power_up_emission_is_still_pending`) |
| `ops.sortie_done` (AD-48.2, M02) | `flight_hours`, `landings`, `engine_starts`, `chute_streamed` | shut-down: final LUIs, OAC counters with a source (tech-log quantities, PROXY A-W2.1c-4; no false zeros), power down, download; a sortie never started raises |

Outputs:

- **Outbox:** records with kernel times in the state. `contract_tables` converts them to the four contract v0
  topics and validates every batch with `load_contract("v0").validate`. Restricted labels never appear there.
  Event snapshot pointers are carried: every `events.bit_faults` / `events.exceedances` / `events.cautions`
  row of an exceedance or an ECMS- or FADEC-sourced code has `snapshot_t_start` / `snapshot_t_end` = its
  occurrence time - `snapshot_pre_s` (5 s) / + `snapshot_post_s` (25 s), in simulated UTC; other rows carry
  nulls. They point into the continuous record: the samples of the window are the `param.samples` rows in
  it (M14 keeps no separate snapshot buffer). Not carried: the ECMS take-off record (`takeoff_record_s`, 8 s
  from the PLA >= IRP trigger with weight on wheels, A-W1.5-40) has no topic and no pointer row; only
  `takeoff_records()` exposes it.
- **`obs.event` to M18 (AD-44, `obs_target`):** after each sortie M14 schedules a download at shut-down +
  `download_delay` (1,800 s, whole seconds, A-W1.5-42). It sends every `events.*` row it has not yet sent as
  `{topic, row}` (plain keys, AD-48.1; `row` as JSON text), with `t_ingest` = the download time.
- **Held ports (AD-42 `RECORDED`):** `cws_legend_a`, `cws_legend_b`, `cws_master`, `cws_voice_aoa`,
  `cws_voice_canopy`, `cws_voice_low_alt` and `cws_voice_uc`. Each is the int bitfield word of the
  dictionary channel `CWS.*` (`cws.build_cws_map`). The held value changes when M14 handles an event. With CIR
  delivered in chunks, `cws_words_at(module, state, t_ns)` gives the exact edge times from the caution
  records; call it before `monitor.ack`.

## Model

- **Internal BIT test** (`logic.bit_test_kernel`): the statistic is unit offset + flight offset + LRU condition
  + AR(1) heavy-tailed mixture noise. It is evaluated at `test_rate` per hour against threshold k with m-of-n
  non-overlapping windows (RADC Table 5-8). Declarations latch; n_clear consecutive passes clear them. Two
  regimes are calibrated by simulation (`calibrate.py`): immature k = 3.0, 3-of-4; mature k = 5.0, 4-of-5.
  Gas-path EHM statistics use a baseline-corrected unit offset. A software load lowers k by Δk, decaying
  over 10 sorties. Sympathetic codes are drawn from the `cascade` stream. A PBIT failure latches the test until
  CBIT passes.
- **Limit monitors** (`logic.limit_kernel`): persistence in samples, clear count, hysteresis, running peak and
  gates (engine running, airborne). Limits come from dictionary limit kinds or M14 SI parameters converted
  to EU.
- **ECMS LUIs:** the M10 kernels on recorded N2/PS3/T5/PLA, written at landing and at shutdown. TAC is
  cross-checked (validity NO_COMPUTED_DATA on a data gap, FAILURE_WARNING outside 0.4–15 TAC/FH).
  Nz level-crossing counters and OAC counters are computed from the same data.
- **Code table** (AD-48.5, dictionary 0.1.2, SYNTHETIC): the dictionary's single `bit_codes` table
  (`Dictionary.bit_codes()` / `bit_code(c)`: index, description, severity, list, mechanism, LRU, lane, source,
  legend, voice channel, monitor channel/limit/sense/gate, groups) joined with M14's behaviour rows
  (`configs/tejas/params/M14/codes.yaml`, format `phalanx.m14_codes/2`: technology and CND propensity,
  displayed, suspect LRUs, threshold regime, sympathetic codes, monitor persistence/clear). 104 codes (33
  internal, 50 external, 21 CIR monitors), 30 legends and 4 voice warnings; one behaviour row per dictionary
  code (checked on load). ENG-509/510 (M08's AB lockout and blowout, formerly folded into ENG-503) take
  ENG-503's behaviour.

Streams (subsystem `monitoring`):

- `test_noise`/`test_tail`, `pbit_noise`/`pbit_tail` per (tail, sortie, code);
- `ground_noise`/`ground_tail` per (tail, job, code);
- `flight_offset` per sortie;
- `unit_offset` per LRU serial;
- `cascade` per sortie.

## Assumptions and PROXY items

A-W1.5-30 … A-W1.5-42 in `docs/assumptions.md`:

- the test-statistic form;
- regime calibration;
- LUI gates;
- exceedance persistence;
- Nz levels;
- LUI write instants;
- the synthetic code table;
- caution thresholds (restricted F404 bands are not used);
- the software-load burst;
- the snapshot window;
- the take-off record;
- CWS word logic;
- download delay and code masking (A-W1.5-42).

**PROXY (A-W1.5-44):** `contract_out` sets `t_utc` to the event time (a perfect time source). W1.7 built no
event path; W2.2's M14 `events.*` full-path route (M16 records, M17 decodes with the recorder time base)
replaces it.

## Validation (acceptance → tests)

| Criterion | Tests |
|---|---|
| A5 persistence and latch logic, m-of-n arithmetic (RADC 5-8), coloured noise | `tests/unit/test_monitoring_logic.py` |
| A5 LUI counting on synthetic cycles | `tests/unit/test_health_usage.py`, `tests/unit/test_monitoring_module.py::test_luis_written_twice_per_flight` |
| A5 event rates per regime (n and exact CI stated); false alarms persisting ≥ 3 flights in 10–18 %; burst ≈ ×10 | `tests/statistical/test_monitoring_regimes.py` |
| A6 every batch validates against contract v0; restricted labels never reach consumer topics | `tests/unit/test_monitoring_module.py::test_event_tables_validate_and_stay_consumer_safe` |
| Code table vs dictionary formats | `tests/unit/test_monitoring_codes.py` |
| AD-42 CWS words, RECORDED conformance, exact edges, ack safety, PBIT latch | `tests/integration/test_monitoring_cws.py` |
| FADEC events into BIT and caution records; translation table targets | `tests/unit/test_monitoring_fadec.py` |
| AD-44 declarations; `obs.event` rows become an M18 defect job; masked codes | `tests/integration/test_event_protocol.py`, `tests/integration/test_health_faults_m18_m12_protocol.py` |
| A7 determinism, snapshot round trip including latches and persistence counters, CRN | `tests/fork/test_health_faults_monitoring_fork.py` |

## Known limitations

- Contract v0 carries the event snapshot pointers (`snapshot_t_start` / `snapshot_t_end` on `events.*` rows
  of exceedances and ECMS / FADEC codes) but nothing for the ECMS take-off record: no topic, no pointer row
  (A-W1.5-40, exposed by `takeoff_records()`). Carrying it needs a contract minor version (an
  `events.*` record kind or a take-off pointer pair).
- The BIT noise form duplicates M13's texture form (AR(1) + heavy-tail mixture). W2.1 should share one
  implementation.
- Module-level rate CIs are optimistic: unit offsets make counts overdispersed. The bands are wide enough
  that this does not decide a verdict.
- The pilot's master-caution reset is not modelled (A-W1.5-41).
- Open cautions from a previous flight stay open in the outbox after power-down. Their `t_cleared` stays null.
- M08's FADEC codes and M14's table are two SYNTHETIC vocabularies joined by a provisional translation
  table. Some ids coincide with different meanings (for example ENG-501: flameout in M08, stall in M14). One
  FADEC code table in the dictionary would remove the table (coordinator).
- M14 is not in `test_interface_conformance.py`'s module list. `test_monitoring_cws.py` applies the same
  `recorded_problems` check to M14.
