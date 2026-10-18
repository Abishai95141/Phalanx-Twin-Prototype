# W2.5 deviations from PREREGISTRATION.md

Each entry: date, what differs from the pre-registration, why, and the results both ways. Pre-registered
verdicts are never changed by a deviation; post-hoc analyses are labelled as diagnostics.

## D1 (2026-10-15): post-hoc diagnostics of the label-leak audit and G0 (no verdict change)

**Pre-registered results (verdicts stand):** paired pipeline invariance PASS (0 problems in 166 pairs);
metadata-only audit PASS; texture-only audit **FAIL** (logistic AUC 0.585, 95 % CI [0.521, 0.650]; boosting
0.583 [0.518, 0.646]; 156 pairs); G0 on the binding pipeline-only subset **FAIL** (logistic 0.526 [0.505,
0.550]; boosting 0.551 [0.522, 0.582]; 166 pairs). All three negative controls were caught (NC1 texture AUC
0.95-0.98; NC2 metadata and G0 AUC 1.0 and invariance 166/166; NC3 invariance 166/166).

**Why diagnostics were added:** a FAIL of a classifier audit says that something separates the runs, not
what. Two questions had to be answered before the result can be acted on: does the separation come from a
non-physical generation-path difference (a leak), or from the fault's physics reaching features that are not
physics-blind?

**Diagnostics (post hoc, `code/leak_diagnose.py`, `code/leak_posthoc.py`; results `results/leak/`):**
1. Feature differences on channels whose acquisition input was identical in the pair (the fault's physics did
   not reach them): **0** for the texture, metadata and G0 features over all pairs. Every separating feature
   difference is on a channel whose acquisition input the fault changed (e.g. ENG.PS3.A acf1_d2: 65 differing
   pairs, all with ENG.PS3.A affected).
2. The texture separation is carried by the abrupt engine faults whose physics changes the signal dynamics in
   the 20 s run (blade loss, fan-blade liberation, quick-fill and pop stall, flameout, fuel over-metering):
   kurtosis and colour of the first and second differences of PS3 and N1. Stratified: gradual degradation
   modes 0.577 [0.457, 0.696] (44 pairs, at chance), abrupt modes 0.603 [0.529, 0.674] (112 pairs, FAIL).
3. G0's separation is the float32 representability of affected channels (ENG.P5, ELEC.DCBUS.V.MAIN, ENG.CVG):
   a function of the recorded values, so a physical level change moves it. On the structural pipeline facts
   (sample counts, count over rate, dtype, NaN, run frames and seconds) the healthy and faulty runs are
   identical in 166/166 pairs (AUC exactly 0.5).

**Reading:** no non-physical cue was found; the pre-registered texture-only and G0 rules are not physics-blind
for same-path healthy/faulty pairs (they were designed for synthetic-vs-real files, where float32 storage and
texture are pipeline properties). This is a design limitation of the pre-registered rule, reported as such;
the proposed decision is in the README (PD-W2.5-4) and needs the coordinator's approval before any verdict
rule changes.

## D2 (2026-10-15): HPC and fan erosion base rates corrected to their source; erosion check rerun

**Pre-registered result (verdict stands):** B7-ENG-ERO-RATE **FAIL**: mean HPC efficiency loss at 5,000
flights 6.92 % (sd 0.91 %, 100 serials: see D5) against ProDiMES 5 % +/- 25 % (`results/b7_progression.json`). HPT at
3,000 cycles 2.60 % (PASS against C-MAPSS 2.6 %); fouling at 500 EOT h 1.02 % (PASS).

**Why:** the W1.5 base rate `erosion_rate_hpc` = 1e-5 per flight was set as 5 % / 5,000 flights, but M10 also
applies `hpc_accel_factor` (2) after 3,000 flights (the ProDiMES acceleration the same source shows), so the
two together give 3,000 x 1e-5 + 2,000 x 2e-5 = 7 %. This is a derivation error against the cited source, not
a new fit: the corrected base rate is the one that reproduces the same source with the acceleration the model
already carries, 5 % / (3,000 + 2 x 2,000) = 7.142857e-6 per flight. The fan rate was set as half the HPC rate
in W1.5 and keeps that ratio (3.571429e-6). Parameter text and evidence in `configs/tejas/params/M10.yaml`.

**Rerun (post hoc, same 100 serials and seeds, `code/progression.py <out> erosion` ->
`results/b7_progression_d2.json`):** HPC efficiency loss at 5,000 flights 4.95 % (sd 0.65 %; inside
[3.75 %, 6.25 %]); at 3,000 flights 2.09 %; HPT unchanged (2.60 % at 3,000, 4.36 % at 5,000); fouling unchanged
(1.02 %). Because the base rate is now derived from the same ProDiMES figure the check uses, the rerun is a
consistency check of the implemented law against its source, not independent validation; the pre-registered
FAIL is what the build delivered before the correction.

**Tests:** `tests/unit/test_health_module.py`, `test_health_wear_debris.py`,
`tests/property/test_health_bias_property.py`, `tests/statistical/test_health_statistical.py`: 21 passed.

## D3 (2026-10-15): bench start condition; B7-ENG rerun with each run trimmed at its own initial inputs

**Pre-registered result (verdicts stand, `results/b7_engine.json`):** F5 (LPT erosion) PASS 7/7 cells; F1, F2,
F3, F4, F6 FAIL; F7 (C26) FAIL. Most cells were not evaluable: the deteriorated engines rolled back below
ground idle (N2 66.6 % -> 26-40 %) before the first hold, so fewer than 3 faulty points fell inside the healthy
range. Evaluable pairs per cell: F1 4/5, F2 2/5, F3 0/5, F4 0/5, F6 0/5, F7 1/5, F5 5/5. The analysis code first
computed means and CIs over the evaluable pairs only; it now records `n_evaluable` and, as pre-registered
(n = 5), a cell with fewer than 5 evaluable pairs is not evaluable (FAIL). No verdict changed by that fix.

**Why:** the pre-registration says "M10 state set at t = 0, i.e. an engine degraded before the run". The bench
did not start such an engine: it started every run from M08's healthy no-load trim (`TrimCondition(t_s)`:
health 0, PTO 0, bleed 0) and stepped the run's M10 build deltas, the fault, and M09's idle loads (PTO about
21 kW, bleed about 0.5 kg/s) in at t = 0. The step is a transient the pre-registration did not intend. Traces
(`code/bench.py` runs of F6 pair 0 and of the healthy B7-SNS-BIAS pair 2): N2 sags about 3 %, M08's
acceleration Wf/PS3 schedule (`acc_k` 1.4 x the reference line M08 derived from the no-load nominal engine)
takes control, and the engine decelerates on it to the minimum-fuel clamp (WF_MIN) with T5 rising. Steady ground
idle needs Wf/PS3 = 1.20-1.24 x that line for the healthy builds with M09's loads and 1.24-1.36 x with the B7
deteriorations (`trim.operating_point` at each run's own inputs; HPC erosion 5 % on pair 4: 1.361), so the
accel schedule leaves 3-20 % margin at idle and none once N2 has sagged. This is reported to the engine/FADEC
owners (README, requests); the bench cannot fix M08.

**Change (post hoc):** `bench.run_bench(..., trim_at_start=True)`: a 0.5 s first pass of the same bench gives
the run's own engine inputs (M03 field and process inputs, M09 bleed, PTO and fuel-inlet temperature, M10
`health.engine` including the fault set at t = 0), and the run starts trimmed there (`bench.initial_condition`).
Healthy and faulty runs use the same rule (one generation path). Exposing tests:
`tests/integration/test_faults_bench_trim.py` (the D3 start holds an HPT-deteriorated engine at idle; the
pre-registered start's rollback kept as a strict xfail for the owners).

**Rerun (`code/b7_engine.py run|analyse OUT --d3` -> `results/b7_engine_d3.json`, same 5 identities):**
- F1 fan fouling: 6/7 cells PASS; C2 (N2c vs N1c) +0.16 % [+0.13, +0.19] where Muir has "down": FAIL.
- F2 HPC fouling: 6/7 PASS; C4 (Wfm vs N2c) +0.51 % [+0.39, +0.63] where Muir has "down": FAIL.
- F3 HPC erosion: not evaluable (4/5 pairs): pair 4 rolls back even from its own trim (its idle needs 1.361 x
  the line; process disturbances take the remaining 3 %). On the 4 evaluable pairs the six arrow cells have
  Muir's sign; C1 (W1c vs N1c, Muir "-") is -1.46 %, outside AD-53's 1 %.
- F4 HPT erosion and F6 HPT abnormal: 5/7 PASS; C5 (PS3/P1 vs N2c) -0.34 % where Muir has "up", and C7 (N2c vs
  P56/P1) 0.00 % where Muir has "down": FAIL.
- F5 LPT erosion: 7/7 PASS (as pre-registered).
- F7 HPC damage (C26): PS3/P1 +2.37 % [+2.23, +2.51] against [6 %, 10 %]: FAIL; Wfm +7.44 % [+7.09, +7.79]
  inside [6 %, 17.5 %]; Fg +4.4 %.
- IRP diagnostic: the healthy engine is on the N1 governor with the nozzle T5 loop active (code 18); the
  deteriorations open A8 (+5.8 % F4, +6.8 % F6, +8.1 % F7, +12.9 % F3) and lose 3.5-4.7 % thrust at held N1 and
  T5: the F100 DEEC expectation for an active nozzle T5 loop (A8 opens, thrust falls), with N1 held by its
  governor rather than lowered.
No priority engine mode passes its pre-registered row after D3 except LPT erosion; every remaining failure is
a sign or magnitude of M07's deterioration response (W2.3 calibration) or M08's accel margin (W2.1b/W2.3).

## D4 (2026-10-15): B7-ELEC-GEN M14 criterion diagnosed (no verdict change)

**Pre-registered result (verdict stands, `results/b7_misc.json`, kind `gen`):** **FAIL**. In 5/5 runs the
generator goes offline within one frame (0-3.3 ms after the onset) and the essential DC bus is back inside
22-29 V after 33.3 ms (MIL-STD-704F <= 50 ms): PASS; M14 records no ELE-401 after the onset in any run: FAIL.

**Diagnosis (post hoc):** two candidate causes were separated. (a) M14 is event-driven and evaluates its CBIT
tests only up to the next event it receives; the bench sent none after the onset. The diagnostic kind
`gen_d4` closes the ground run with its shut-down (`bench.shutdown_event`, `ops.sortie_done` to M14 at
19.99 s) on pair 0 (a deterministic wiring question: n = 1): still no ELE-401. (b) ELE-401 is a
`src: external` code (the GCU declares it); in telemetry mode M14 tests only `src: internal` codes and takes
external codes from `monitor.bit_report`, which no module sends for the generator (M09 publishes the GCU's
off-line discrete ELEC.GEN.OUT as a recorded channel but emits no BIT report). M11's `monitor.lru_condition`
for ELE-401 therefore sets a test shift nothing evaluates. Cause (b) holds. The fix belongs to the electrical
system's owner or the dictionary (README, requests): M09 reporting ELE-401/ELE-404 on its GCU state, or
ELE-401 declared from the recorded ELEC.GEN.OUT discrete. M14 is not changed here (it would put a label on
the record path that no physical declarer produces).

## D5 (2026-10-15): progression sample size

The pre-registration says 200 serials for B7-ENG-ERO-RATE and B7-ENG-FOUL-RATE; `code/progression.py` ran
100 engine serials (fouling: 100 serials x 2 stages = 200 values). The verdicts do not hinge on n: the
standard error of the HPC mean is 0.09 % at 6.92 % (pre-registered run) and 0.065 % at 4.95 % (D2), against a
+/-1.25 % band. Reported as run; not rerun with 200.

## D6 (2026-10-15): B7-OIL-SPALL measurement fix

`code/progression.py <out> spall` (pre-registered check, first run): the seed (`health.fault eng:spall_len`
= M10's initiation size) landed inside the first 1-h sortie, so that sortie's length change included the
seeded 0.5 mm, which by design sheds no debris; its debris per mm (1.90 mg/mm) was a measurement artefact.
The seed now lands before the first sortie; the reported numbers are from that run
(`results/b7_spall.json`).

## D7 (2026-10-15): B8 M14 configuration, the M11 stand-in clear, and chain 1

**Pre-registered result (verdicts stand, `results/b8.json`):** immature FA rate 2.21 [2.09, 2.35] per FH PASS;
mature <= 0.0099 per FH PASS; FA share PASS in both (mature n = 2); persistence 1 flight 0.700 and >= 3 flights
0.145 PASS; NFF (RTOK) 1.000 [0.982, 1.000] FAIL; CND 0.731 [0.700, 0.761] FAIL (mature NFF and CND pass on
n = 1 and n = 3); CHAIN2 PASS (107/107 at exactly 3 flights). CHAIN1, pre-registered configuration: the
injected oil-pressure-transmitter fault was never detected in 28 days.

**Why the true-fault side is empty:** 47 fault instances in 1,244 FH, all transient, none persistent (see
README §3). Two of the three mechanisms are in W2.5's modules and one in the harness:
(1) the worlds' M14 ran its default telemetry configuration (only internal codes are tests), so the usage-mode
detection stand-in (A-W1.5-26), which sets the condition of a mode's first detection code, was inert when that
code is external or CIR (all engine transients; ECM-702 for chain 1). (2) M11 never cleared the stand-in when
its instance cleared: with M14 in usage mode, chain 1 recorded the true ECM-702 at the next sortie and then 13
phantom ECM-702 records and four more engine removals after the instance had ended. Fixed in M11 (`_clear`
clears the stand-in; unit test `test_usage_detection_stand_in_clears_with_its_instance`; commit c7ea09d). The
pre-registered B8 run is unaffected by the fix (all its stand-ins were inert). (3) M14 evaluates a usage-mode
sortie's tests when the summary arrives at landing, so a condition that set and cleared in flight is never
seen (open; proposed decision PD-W2.5-7).

**Post hoc runs:** `fleet.OneTailWorld(m14_usage_mode=True)` (M14 `usage_mode`: every code a test, as
A-W1.5-26 describes usage mode), same roots and worlds, after the M11 fix.
- Chain 1 (`results/b8_chain1.json`, `usage_mode_d7`): ECM-702 at the next sortie, 2.6 h after the onset; a
  pilot-discovered ENG work order 3.4 h after; the engine is removed and replaced (M18 has no
  oil-pressure-transmitter position), 56.2 h, tail NMCM_U; the instance ends with the removal and no phantom
  record follows. Against the anchor (about 3 h, same day, with parts): 19 x longer, the known limitation.
- B8 (`results/b8_um.json`): immature (543 sorties, 452 FH) FA rate 5.44 [5.23, 5.66] per FH PASS, FA share 1.000 [0.998, 1.000] PASS, persistence 1 flight 0.754 and >= 3 flights 0.107 PASS, NFF 1.000 [0.984, 1.000] FAIL, CND 0.794 [0.770, 0.816] FAIL; mature (914 sorties, 732 FH) FA rate 0.011 [0.005, 0.022] per FH FAIL (upper bound above 0.02), FA share 8/8 [0.68, 1.00] FAIL; CHAIN2 PASS (79/79 at 3 flights). Still no true detection: the 42 instances are all transients, lost by mechanism 3; with 104 tests instead of 33 the false-alarm rates rise about 2.5 x (immature) and 4 x (mature), so the regime calibration (made on internal tests) does not carry over to usage mode (PD-W2.5-8).
