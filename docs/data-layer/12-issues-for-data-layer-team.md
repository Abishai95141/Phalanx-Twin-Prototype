# 12 · Issues for the data-layer team (preview v0.9)

From the Phalanx-Solution team (downstream PdM + fleet availability), for triage by the Phalanx
data-layer team.

- **Dataset:** preview v0.9 (`data/v0.9/`), contract `phalanx.ground_decoder_contract` 0.2.0 (`a4396f1d…`),
  dictionary tejas 0.1.3 (`9428d30f…`), data generated at `6d4dc52`; code references are to the bundled snapshot
  `code/` (`fda9f98`). Paths are relative to the preview bundle root.
- **How we checked:** every number below was re-measured on 2026-10-16 with pyarrow reads
  (`ds.dataset(path, format="parquet", partitioning=None)`) of the consumer trees (`fleet/`, `telemetry/`),
  `_runs/` and `MANIFEST.json`. **`_restricted_labels/` was never opened.** Statements marked *by code reading*
  were not executed.
- **Severity is for our build:** **blocking** = a planned capability cannot be built or demonstrated;
  **degrading** = we work around it but lose scope or accuracy, or carry a leak risk; **cosmetic** = docs or
  hygiene. **Ask:** Fix / Document / Answer. `D`-numbers are our decisions in
  [`../architecture/13-decision-register.md`](../architecture/13-decision-register.md).
- We know v0.9 is a preview with behaviour not yet validated. Items already listed in the v0.9 README's known
  issues are included only where we need an answer or a date.

## If you only do five things

1. **Answer D3:** how a separate repo should submit orders and run forks (library pin or service). It sets our
   deployment shape.
2. **Fix or document A1 + A3:** ids collide across the 8 fleet worlds, and null-`tail_no` rows from all worlds
   share one partition. The README currently tells consumers to dedupe on `record_id`.
3. **Fix D1 + D2:** fork defaults and `OpsSession.records()` hand out true hidden state unless the caller opts out.
4. **Answer B1:** when CONFIRMED shop findings (W2.5b) arrive. Our failure/removal models need them.
5. **Answer C2 / C3 / B3:** whether lane, vibration/chip/oil-level and `MX.*` inspection data will reach consumer
   topics, and when.

## Triage table

| # | Issue | Severity | Ask | Our decisions |
|---|---|---|---|---|
| A1 | `maint.records` `record_id`s collide across fleet worlds (3,388 surplus rows) | degrading | Fix + Document + Answer | D03, D02, D15, D16 |
| A2 | Same `order_id` on two tails; `orders.status` has no tail column | degrading | Fix + Answer | D22, D02 |
| A3 | Null `tail_no` on 91/91 SHOP_FINDING and 564/614 SUPPLY_DEMAND rows; AOG demands lose their tail on close | degrading | Fix or Document | D03, D08, D10, D16 |
| A4 | MANIFEST row counts don't reconcile with on-disk `maint.records` (10,086 vs 10,085) | degrading | Answer + Fix | D01 |
| B1 | 0 CONFIRMED shop findings (91/91 RTOK) | **blocking** | Answer | D08, D10, D18 |
| B2 | No MODIFICATION / CANNIBALISATION / EXCEEDANCE_INSPECTION; `sw_config_id` only `SW-BASE` | degrading | Answer | D26, D15, D16 |
| B3 | `MX.*` inspection measurements have no contract transport | **blocking** (phase B) | Answer | D11 |
| B4 | Defect narratives say "FIRE-CONTROL RADAR" for AHRS / SMS / MC codes | degrading | Fix | D04, D06 |
| B5 | 35 of 42 event suspect ids are not removable part classes | degrading | Document | D04, D08 |
| B6 | Pilot-reported defects have no evidence links; TJ108's engine removal cites a caution that doesn't exist | degrading | Fix or Document | D06, D08 |
| C1 | `ENG.T5` clamped at its 371 °C floor in 33 % of samples, unflagged; `ENG.OIL_T` ceiling flagged inconsistently | degrading | Fix or Document | D07, D11 |
| C2 | No A/B lanes in consumer `param.samples` (all 108 lane channels are INTERNAL-only) | **blocking** (D09) | Answer | D09 |
| C3 | No vibration, chip-detector or oil-level channels in telemetry | **blocking** (phase B) | Answer | D11 |
| C4 | `detection_far_per_fh` is one value per regime, not per code | cosmetic | Document | D06, D08 |
| D1 | `BranchSpec.mode` defaults to `oracle`; `what_if()` silently maps it to `ensemble` (true state) | degrading (leak risk) | Fix | D18 |
| D2 | `OpsSession.records()` returns truth rows; README shows it as the normal read | degrading (leak risk) | Fix | D18, D05 |
| D3 | Orders and forks are callable only in-process | **blocking** (decision) | Answer | D18, D21 |
| D4 | Belief forks cover one hidden state; reference posterior renews only on CONFIRMED findings | degrading | Answer | D18 |
| D5 | `ConditionBasedPolicy` matches BIT codes by substring in noisy text | cosmetic | Fix | D25 |
| E1 | Planned flight hours (`kpi.plan`) not in the contract, though MANIFEST publishes `flying_task` | degrading | Fix or Document | D15, D12 |
| E2 | Grounding (U/S) linkage exists only as `TECH_LOG.limitations_text` | cosmetic | Document | D20, D21 |
| E3 | Sortie completion/abort is not in the contract; telemetry tree has no `usage.counters` | degrading | Document + Answer | D01, D07 |
| E4 | `COMPONENT_LIFE` has no installed-position field | degrading | Answer | D04 |

---

## A · Identity and dedup

### A1 · `maint.records` record_ids collide across the 8 fleet worlds — degrading

- **Observed.** `data/v0.9/fleet/maint.records`: 10,085 rows, 6,697 distinct `record_id` → **3,388 surplus rows**;
  1,341 ids occur more than once, 77 of them on all 8 tails. Rows whose id is shared with another world:
  DEFECT_WO 3,232, COMPONENT_LIFE 822, SUPPLY_DEMAND 474, INSPECTION 153, SHOP_FINDING 48.
  - Cause: the `record_id_key` is (`record_type`, `record_key`, `record_version`), with no world or tail
    component. Each world restarts the same job, demand and serial counters.
  - Examples: the COMPONENT_LIFE install of `ADC-000001` exists on all 8 tails, and DEFECT_WO job
    `sulur-26006-0001` on 7 of them. There are 361 distinct job numbers globally against 1,003 (`tail_no`,
    `job_no`) pairs, and 77 of the 89 serial numbers appear on more than one tail.
  - Keyed by (`tail_no`, `record_id`), every non-null-tail row is unique. The 320 remaining repeats all sit in
    the null-tail partition (A3).
- **Why it bites.** `code/docs/previews/v0.9_README.md:184-185` says `record_id` is unique per topic and tells
  consumers to deduplicate on it, which drops a third of the records. *By code reading*,
  `ParquetStore.read(dedup=True)` would instead raise `RecordIdConflict` (`code/src/phalanx/streaming/dedup.py:89`),
  because colliding rows differ at least in `tail_no`.
- **Repro.**
  ```python
  import pyarrow.dataset as ds, pyarrow.compute as pc
  t = ds.dataset("data/v0.9/fleet/maint.records", format="parquet", partitioning=None).to_table(columns=["record_id", "tail_no"])
  t.num_rows, pc.count_distinct(t["record_id"]).as_py()      # (10085, 6697)
  t.group_by(["tail_no", "record_id"]).aggregate([]).num_rows  # 9765 (the 320 left are null-tail rows)
  ```
- **Impact.** D03: scoped identity (`tail_no` as world id) is our temporary workaround. D02: as-of store keys.
  D15/D16: fleet-level planning, spares pooling and cannibalisation need a shared world.
- **Ask.**
  - **Document** it in the v0.9 README now: one paragraph plus the scoped key.
  - **Fix** future per-tail previews by namespacing job, demand, serial and order counters per world (e.g.
    `sulur-TJ101-26006-0001`). Ids then become globally unique with no contract change.
  - **Answer:** when does the W2.6 shared-world fleet land?

### A2 · Order ids collide; `orders.status` cannot be attributed to a tail — degrading

- **Observed.**
  - `fleet/orders.commands` has 7 rows and 6 ids. `scheduled:20260507T023000:001` was issued to both TJ101 and
    TJ102 (both `PLANNER-SCHED` `WASH_SERVICE`).
  - `fleet/orders.status` has 28 rows and 24 ids. That order's 8 status rows share 4 `record_id`s. Its two
    COMPLETED rows share `record_id` `cb386700…` but carry different `t_status` (`1778132338…` vs
    `1778141370…`), so any dedupe keeps only one tail's completion.
  - `orders.status` has no tail column; only `result_record_ids` lead back to a tail.
- **Impact.** D22: our own order ids are content-addressed and include tail and evidence hash. In a multi-tail
  run every epoch would hit this. Also D02.
- **Ask.**
  - **Fix** the scheduled policy's ids to include the tail (e.g. `scheduled:<tail>:<t>:<seq>`), and state that
    `order_id` must be fleet-unique.
  - **Answer:** the contract says re-sending an `order_id` is a no-op. In a shared world, will the gateway
    silently drop a second tail's order that reuses an id, or reject it with a reason?

### A3 · Null `tail_no` on SHOP_FINDING and SUPPLY_DEMAND in one shared partition — degrading

- **Observed.** All 91 SHOP_FINDING rows and 564 of 614 SUPPLY_DEMAND rows have `tail_no` null. They sit in 443
  files under `fleet/maint.records/date=*/tail_no=__null__/`. The contract allows null for base-level records
  (`code/docs/contract/contract/v0/contract.md:579`, "e.g. stock"), but three things go wrong:
  - **No world key.** The 8 worlds write into the same null partition with colliding ids. 140 SUPPLY_DEMAND and
    15 SHOP_FINDING `record_id`s appear with **different content**. For example, `D-sulur-26007-0001` v0 appears
    8 times with different `t_event`/`t_open`, and `SF-FADEC-000001-1` appears 5 times with different `job_no`,
    `item_hours` and `t_event`. No column says which world a row belongs to.
  - **AOG demands lose their tail on close.** All 41 AOG v0 (OPEN) rows carry `tail_no`, but 21 of the 30 v1
    (CLOSED) rows have it null. For example, `D-sulur-26008-0001` is TJ107 at v0 and null at v1, so the latest
    version of a tail's AOG demand cannot be attributed to it.
  - **MCM demands are unlinkable.** The 543 MCM demands have no `job_no`, no `serial_no` and empty
    `evidence_record_ids`. The null-tail parts are tyres 531, chutes 22, HYDP 10 and JFS 1.
- **Our workaround.**
  - SHOP_FINDING → world by matching (`job_no`, `serial_no`) to a COMPONENT_LIFE REMOVE. 88 of 91 resolve to
    exactly one tail; 3 resolve to none (`SF-HYDP-000001-5`, `SF-FADEC-000002-2`, `SF-HYDP-000010-2`).
  - Closed AOG versions → tail via (`demand_no`, `job_no`) to their OPEN v0. 20 of 21 resolve; 1 is ambiguous.
- **Impact.** D03; D08 and D10, whose outcome labels come from shop findings; D16 and D12, which need demand
  rates per tail.
- **Ask.**
  - **Fix:** carry `tail_no` on every version of a tail-originated record (AOG close, shop finding on an item
    removed from a tail), and give base-level demands a per-world namespace in per-tail previews.
  - **Or document:** the SHOP_FINDING ↔ REMOVE linkage rule, and that MCM demands are base-stock replenishment
    with no tail by design.

### A4 · MANIFEST row counts don't reconcile with the consumer tree — degrading

- **Observed.** `MANIFEST.json` `runs.fleet[*].rows["maint.records"]` sum to **10,086** (so does the README
  per-tail table), but the consumer tree holds **10,085**. Every other fleet topic reconciles exactly.
- **Likely cause (*by code reading*).** `ParquetStore._write_file`
  (`code/src/phalanx/streaming/parquet_store.py:246`) treats an existing content-addressed file with identical
  bytes as already written. A byte-identical one-row file written by two worlds into the shared
  `tail_no=__null__` partition would therefore be stored once. We have not identified the row.
- **Impact.** D01: our G0 release gate checks row counts against the manifest, so this release quarantines.
  Doc 03 R7: reproducible dataset identity.
- **Ask.** **Answer** which row is missing. **Fix:** it should fall out of the A1/A3 namespacing; otherwise
  record per-tree written counts in MANIFEST.

## B · Missing or limited record types and record content

### B1 · Zero CONFIRMED shop findings — blocking

- **Observed.**
  - `shop_finding` over all of `maint.records`: RTOK 91, CONFIRMED 0, BCM 0. By part: HYDP 36, BCU 17, FADEC 12,
    JFS 12, ADC 10, DFCC 3, ENG-F404 1.
  - Every event is UNCONFIRMED, which is expected per the contract.
  - README known issue 5 ties this to W2.5b (few persistent faults).
  - The reference `SurvivalPosterior` renews a serial only on a CONFIRMED finding
    (`code/src/phalanx/fork/belief.py` docstring), so in v0.9 no renewal is ever observed.
- **Impact.** Blocks learned detection parameters (D08, revisit at ≥ 50 CONFIRMED), cause-specific removal
  hazards (D10) and any failure/RUL model trained on confirmed failures. It also weakens belief forks (D18).
- **Ask.** **Answer:** the W2.5b date. A preview where a handful of persistent faults end in CONFIRMED findings
  (ideally ≥ 50 across the fleet) would unblock us.

### B2 · No MODIFICATION / CANNIBALISATION / EXCEEDANCE_INSPECTION records; one software config — degrading

- **Observed.**
  - Record types present: DEFECT_WO 3,902, TECH_LOG 2,260, AVAILABILITY_STATE 1,340, COMPONENT_LIFE 915,
    SORTIE 643, SUPPLY_DEMAND 614, INSPECTION 320, SHOP_FINDING 91.
  - Three enum values never occur (`code/docs/contract/contract/v0/arrow/maint.records.consumer.schema.txt:24`).
  - `sw_config_id` is `SW-BASE` on 2,903 rows and null on 7,182.
  - `fleet/` has no `events.exceedances`, so nothing can trigger an exceedance inspection.
- **Impact.** D26: software loads and mods as change-points cannot be exercised. Cannibalisation (D15/D16, AOG
  desk) is not demonstrable, and neither is the exceedance → conditional-inspection loop.
- **Ask.** **Answer:** which wave produces these. Could the next preview script one software load and one mod
  campaign on one or two tails?

### B3 · `MX.*` ground-inspection measurements have no contract transport — blocking (phase B)

- **Observed.**
  - Dictionary 0.1.3 defines 9 `MX.*` channels: `MX.SOAP.FE`, `MX.OIL_SERVICING.ENGINE|AMAGB|JFS`,
    `MX.BORESCOPE`, `MX.BRAKE_WEAR`, `MX.TYRE_P.MAIN|NOSE` and `MX.ACCUM_PRECHARGE`. All have transport
    `maint_record` and sink `MAINT_RECORD` only.
  - `maint.records` has no measurement column (no `param_id` / `value_eu` / `units`).
  - v0.9 INSPECTION types are SRV-L1 229, WASH 21, SRV-L2-MINOR 15, SRV-L2-MAJOR 14, ROH 2 and null 39. There
    are no borescope, SOAP or oil-servicing records.
- **Impact.** D11: oil-consumption, SOAP-Fe and borescope trends are the core engine-prognostics story.
- **Ask.** **Answer:** the intended transport (additive nullable columns in a 0.3.0? a separate topic?) and
  when.

### B4 · Defect narratives name the fire-control radar for AHRS, SMS and MC codes — degrading

- **Observed.** DEFECT_WO `discrepancy_text` reads "HMS/BIT CODE … FIRE-CONTROL RADAR (LRU SET) SUSPECT." for
  codes whose dictionary LRU is not the radar:

  | Code | Dictionary LRU / description | DEFECT_WO rows citing it | …that name the radar | Jobs (per world) |
  |---|---|---|---|---|
  | AVI-204 | AHRS / "AHRS LRU BIT fail" | 219 | all 219 | 41 |
  | AVI-202 | SMS / "SMS LRU BIT fail" | 74 | all 74 | 16 |
  | AVI-301 | MC / "1553 bus fault" | 73 | all 73 | 15 |
  | AVI-205 | MC / "Mission computer LRU BIT fail" | 5 | all 5 | 1 |

  The word "RADAR" is spelled exactly in 213 / 71 / 68 / 5 of these rows; the rest carry injected typos
  ("RDAR", "RAADR"). The events agree with the dictionary: all 92
  `fleet/events.bit_faults` AVI-204 rows have `source_lru` AHRS and `suspect_lrus` [AHRS 0.9]. None of these
  jobs removed anything (0 AT-RR, no COMPONENT_LIFE REMOVE), so the error is text-only.
- **Likely cause.** The M18 catalogue has 16 removable classes and none for AHRS, SMS or MC. The narrative
  falls back to `RADAR` (`code/configs/tejas/params/M18/catalogue.yaml:351`, `ambiguity: AVIONICS`).
- **Similar collapses.** ELE-405 (TRU fault) → "MAIN AC GENERATOR"; SPS-001 (AMAGB oil low) → "JET FUEL STARTER";
  HYD-001 (filter ΔP) → "ENGINE-DRIVEN HYDRAULIC PUMP"; LGB-501 (gear unsafe) → "BRAKE CONTROL / ANTI-SKID UNIT".
- **Impact.** D04: we resolve codes from coded fields only, so our registry is safe. But text analytics, the
  assistant's citations and anyone reading the CMMS view see the wrong LRU (D06).
- **Ask.** **Fix:** generate the narrative LRU from the code's dictionary LRU, or from the delivered
  `suspect_lrus`, not from the catalogue fallback.

### B5 · Event suspect ids do not map to removable part classes — degrading

- **Observed.** Events (fleet + telemetry) use **42** distinct `suspect_lrus[].lru` ids, while COMPONENT_LIFE has
  **16** part classes (`SYN-PN-*`). 35 suspect ids are not class names.
  - Some are naming variants: `HYD_PUMP` vs `SYN-PN-HYDP`, `ENGINE` vs `SYN-PN-ENG-F404`, `BRAKE_CONTROL` vs
    `SYN-PN-BCU`.
  - Others have no removable class at all: `AHRS`, `SMS`, `MC`, `MUX_BUS`, `TRU`, `PS3_TRANSDUCER`,
    `T5_HARNESS_A`/`_B` (`T5_HARNESS_A` alone appears 166 times).
- **Impact.** D04: our crosswalk is hand-built and flagged. D08: the D-matrix item set needs to know what
  maintenance can actually remove.
- **Ask.** **Document** an official suspect-id → removable class (`part_no`) table, with "not removable / not
  modelled" marked, in the dictionary or contract docs.

### B6 · Pilot-reported defects carry no evidence; TJ108's engine removal cites a caution that isn't there — degrading

- **Observed.** All 7 `WD-AIR` DEFECT_WO jobs (counted per world) have empty `evidence_record_ids`.
  - TJ108 job `sulur-26013-0003` (opened day 8.1) reads "…OIL PRESS FLUCTUATES / EGT HIGH IN FLT. CAUTION ON.
    PLS CHK."
  - Engine `IN20-TJ108` was removed on day 9.5 (AT-RR) and replaced by `IN20-000001`. Its shop finding
    `SF-IN20-TJ108-1` is RTOK.
  - TJ108 has **no** `events.bit_faults` or `events.cautions` rows between day 6 and day 9.6.
  - The 6 TJ104 NAV jobs do have AVI-205 cautions within ±1 day, but they are not linked.
- **Impact.** D06/D08: evidence-linked defect intelligence and outcome learning. The fleet's only engine removal
  has no observable precursor.
- **Ask.** **Fix:** emit the caution the write-up claims, and link `evidence_record_ids` when a matching event
  exists. **Or document** that pilot reports are generated independently of events.

## C · Telemetry channels and flags

### C1 · `ENG.T5` clamped at its range floor with no flag — degrading

- **Observed.** `telemetry/param.samples`, `ENG.T5`: 1,344,350 rows. **443,838 (33.0 %) are exactly 371.0 °C**,
  the dictionary range floor (`range` [371, 871]), and 443,832 of them have `quality_flags = 0` and `validity`
  NORMAL. Only 6 carry `OUT_OF_RANGE`.
  - Per sortie, 23–66 % of samples sit at the floor.
  - On TJ212 (the one completed sortie), every sample with N2 < 70.5 % is at the floor. The 133,140 floor
    samples have median N2 66.6 %. This is a below-range value clamped, not a reading.
- **Related.** The `ENG.OIL_T` value 179.962 °C (top code below the 180 °C range max) occurs in 513,765 rows
  (38.2 %). 474,964 of those carry `OUT_OF_RANGE` and 38,801 do not: same value, inconsistent flag.
- **Repro.**
  ```python
  s = ds.dataset("data/v0.9/telemetry/param.samples", format="parquet", partitioning=None)
  x = s.to_table(columns=["value_eu", "quality_flags"], filter=ds.field("param_id") == "ENG.T5")
  floor = x.filter(pc.equal(x["value_eu"], 371.0))
  x.num_rows, floor.num_rows, pc.sum(pc.equal(floor["quality_flags"], 0)).as_py()  # (1344350, 443838, 443832)
  ```
- **Impact.** D07: an EGT-margin or residual baseline would learn a flat line at low power, and our L0 masks have
  to guess (D11 too).
- **Ask.** **Fix:** set `OUT_OF_RANGE` consistently on clamped/saturated samples (the contract's bit-6 meaning),
  or widen the `ENG.T5` range to cover ground idle. **Or document** both as deliberate unflagged artefacts;
  we treat them that way today.

### C2 · No redundancy lanes in consumer `param.samples` — blocking (D09)

- **Observed.**
  - The 123 consumer `param_id`s from 6 LRUs have `lane` V (28) or null (95); there is no A/B anywhere.
    `FCS.CH.STATUS.A|B` and `CWS.LEGEND.A|B` are status words with null `lane`.
  - Dictionary 0.1.3 defines **108 `role: lane` channels** (e.g. `ENG.N1.A|B`), and **every one has INTERNAL as
    its only sink**, so lanes cannot reach any recorder by design.
  - `ENG.T5.HARNESS_A|B` are routed to ECMS_HUMS/MPDRU in the dictionary but are absent from the data.
  - Fleet BIT events do carry `lane` (A 199, B 21).
- **Impact.** D09: lane-disagreement sensor validation is impossible, so our sensor-vs-component layer runs
  without its strongest check.
- **Ask.** **Answer:** will any lane pairs reach ECMS_HUMS / MPDRU / FTI? One engine pair (N1/N2 or the T5
  harnesses) and one FCS pair in a single preview sortie would unblock D09.

### C3 · No vibration, chip-detector or oil-level channels — blocking (phase B)

- **Observed.** `ENG.VIB.OVERALL`, `ENG.CHIP` and `ENG.OIL_LEVEL` exist in dictionary 0.1.3 with
  CDR/COCKPIT/ECMS_HUMS/MPDRU sinks (FADEC RT5 on AV-MUX-2), but none appears in `telemetry/param.samples`.
  - The engine README lists the vibration source as a PROXY (`code/src/phalanx/engine/README.md:112`,
    A-W1.3a-14).
  - Bearing spall drives debris and oil-Fe states in M10 (`code/src/phalanx/health/README.md:75`). That state
    leaves M10 only through four held ports and the restricted labels (`health/README.md:6`), so no consumer
    channel carries it in v0.9.
- **Impact.** D11: bearing and lube prognostics, the canonical engine PdM story.
- **Ask.** **Answer:** which of these will carry fault-driven signal, and in which wave.

### C4 · `detection_far_per_fh` is one value per regime — cosmetic

- **Observed.**
  - All 1,021 fleet BIT faults (27 codes) and all 304 fleet cautions carry **6.0606e-4 /FH**.
  - All 159 telemetry exceedances and 153 of 167 telemetry cautions carry **6.7e-4 /FH**.
  - `code/src/phalanx/monitoring/contract_out.py:74-75,168`: `far_bit = spec_far_aircraft × 3600 / n_tests`, the
    aircraft spec spread evenly over every test; `far_ehm` applies to exceedance/EHM.
- **Impact.** Small. We learn real false-alarm rates from outcomes (D06/D08), but a per-code nominal prior would
  help the leak term.
- **Ask.** **Document** the even split in the contract field description. **Fix** per mechanism or per code if
  the dictionary is ever given those values.

## D · Fork / orders API safety and the cross-repo interface

### D1 · Fork defaults hand out the true hidden state — degrading (silent leak risk)

- **Observed.**
  - `code/src/phalanx/fork/service.py:60`: `BranchSpec.mode = "oracle"`.
  - `service.py:213`: `what_if()` silently remaps `oracle` → `ensemble`, which is "the true state with a
    different exogenous future" (`service.py:9`).
  - The `fork/README.md` example passes `mode="oracle"`.
  - A caller who never sets `mode` gets truth-informed KPIs with no warning.
- **Impact.** D18: we force belief mode and keep oracle/ensemble offline-only. Any demo built on the defaults
  overstates what a system under test could know.
- **Ask.** **Fix:** require `mode` (no default) or default to `belief`, and gate `oracle`/`ensemble` behind an
  explicit evaluation flag. `what_if()` should reject `oracle`, not remap it.

### D2 · `OpsSession.records()` returns truth rows — degrading (silent leak risk)

- **Observed.** `code/src/phalanx/fork/session.py:229-231`: `records(topic)` returns "Truth rows of topic emitted
  so far (restricted: KPIs and validation only)". These rows come before defect injection; the consumer view is
  `session.obs.as_of(...)`. Yet `code/src/phalanx/fork/README.md:14` shows
  `s.records("maint.records")  # list of contract rows …` as the normal read.
- **Impact.** D18, D05: our wrapper forbids it. A new team member following the README would train on truth.
- **Ask.** **Fix:** rename it (e.g. `truth_records()`) or move it behind an evaluation handle, and show
  `s.obs.as_of(t, topic)` in the README.

### D3 · Orders and forks are callable only in-process — blocking (decision)

- **Observed.**
  - There is no HTTP/gRPC/IPC code under `code/src/phalanx`, and `pyproject.toml` defines no `[project.scripts]`
    entry points. The README integration is `from phalanx.fork import OpsSession, ForkService`.
  - Pins: `requires-python >=3.12,<3.14` and `numpy>=2.1` (a floor only); `uv.lock` pins numpy 2.5.4.
  - The bitwise-replay claims (`orders/README.md:72`, `fork/README.md:17`) hold for that lock.
- **Impact.** D18 (fork worker) and D21 (daily MAPE-K epoch loop) need a stable way for a separate repo to
  submit orders, run forks and read `as_of` views.
- **Ask.** **Answer:** the supported route:
  - (a) import `phalanx` as a pinned library: which tag or commit, and is a wheel published?
  - (b) a thin service you own (submit orders, run a fork, stream `as_of`).
  - Either way: which platforms and NumPy versions keep bitwise determinism?

### D4 · Belief forks implement one hidden state — degrading

- **Observed.**
  - `BeliefTarget` is implemented by `health/module.py:789-802` (engine bearing-spall initiation, Weibull) and by
    the W1 fixture in `maintenance/world.py` (known faults only).
  - `fork/belief.py` says W2.6 asks M10/M11 to implement it.
  - The reference posterior renews only on CONFIRMED findings, and there are none (B1).
- **Impact.** D18: in-loop belief forks are a PROXY in our demo, and we say so.
- **Ask.** **Answer:** which modules gain `BeliefTarget` in W2.6, and when. **Document** how a downstream
  posterior should express per-serial state for them.

### D5 · `ConditionBasedPolicy` matches BIT codes by substring in free text — cosmetic

- **Observed.**
  - `code/src/phalanx/orders/policies.py:321`: `code in (j["discrepancy_text"] or "")`. Grounding jobs come from
    parsing tech-log text (`_us_jobs`, `policies.py:81`).
  - The text is noisy by design: 84 of 2,825 DEFECT_WO BIT write-ups (3.0 %) cite no valid dictionary code
    (e.g. `VAI-203`, `HDY-101`, `ACD-002`).
  - In v0.9's final state none of the 10 open DEFERRED/AT-DEF jobs is affected.
- **Impact.** D25: it is the rule baseline our G1 gate must beat, so its misses inflate our measured gain.
- **Ask.** **Fix:** match on structured links (`evidence_record_ids` → `event_code`) instead of text.

## E · Contract gaps

### E1 · Planned flight hours are not in the contract — degrading

- **Observed.**
  - The scenario emits `kpi.plan` (`t_utc`, `date`, `planned_sorties`, `planned_fh`) to the record sink
    (`code/src/phalanx/scenario/ports.py:84`).
  - M22 computes `flying_task = flown / planned` from it (`code/src/phalanx/fork/kpi.py:109`), and `MANIFEST.json`
    publishes `flying_task` per tail (TJ101 0.373 … TJ108 0.299).
  - No consumer topic carries planned sorties or FH.
- **Impact.** D15: the flight-and-maintenance planner has to take demand from user input. D12: the usage model
  loses its target. We cannot reproduce your flying-task KPI from the contract.
- **Ask.** **Fix:** expose `kpi.plan` as a consumer topic or record type in the next additive contract minor.
  **Or document** the generating rule (scenario parameters) so we can rebuild it.

### E2 · Grounding (U/S) linkage exists only in `TECH_LOG.limitations_text` — cosmetic

- **Observed.**
  - Which open jobs make a tail unserviceable is recorded only as text, e.g.
    `U/S: sulur-26093-0001 sulur-26093-0002; DEFERRED: …`.
  - All 2,260 TECH_LOG rows parse cleanly: 1,950 follow the `U/S: …; DEFERRED: …` grammar and 310 are
    `SERVICEABLE`.
  - DEFECT_WO has no grounding field (`priority` and `limitations_text` are always null; `type_maint_code` is
    only TM-UNS/TM-SCH).
- **Impact.** D20/D21: our airworthiness invariants (no RELEASE with an open grounding defect) depend on that
  grammar staying stable and free of injected noise.
- **Ask.** **Document** the grammar as a stable format, or say if it will change. A structured flag on DEFECT_WO
  in a later minor would be better.

### E3 · Sortie completion is not in the contract; the telemetry tree has no `usage.counters` — degrading

- **Observed.**
  - 5 of 6 telemetry sorties end in a simulator `ground_impact` (`_runs/telemetry/*.json` `abort.kind`, e.g.
    TJ201 at 1,293 s in DESCENT). Only TJ212 completed (6,173.7 s).
  - `sortie.manifest` has no completion field, and `t_landing` is set for TJ115 (it touched down, then impacted
    on the next circuit), so the contract alone cannot tell a crash from a landing.
  - `telemetry/` has no `usage.counters` topic.
- **Impact.** D01: our G0 gate has to read `_runs/` to tag aborted sorties. D07: no model should learn "crash"
  from a simulator artefact.
- **Ask.** **Document** `_runs/*.json` as an official consumer-side artefact with a stable schema, or drop
  aborted sorties from consumer trees. **Answer:** when do telemetry runs emit `usage.counters`?

### E4 · `COMPONENT_LIFE` has no installed-position field — degrading

- **Observed.** `maint.records` has no position or slot column, yet several classes are installed more than
  once per tail (TJ101 at day 0: TYRE ×2, BRAKE ×2, HYDP ×2). The M18 catalogue holds positions internally
  (`positions: [...]`).
- **Impact.** D04: positions are inferred and flagged in our registry, so per-position health on the 3D twin is
  a guess.
- **Ask.** **Answer:** can position go into `record_key` or a nullable `position` column in a later minor?
