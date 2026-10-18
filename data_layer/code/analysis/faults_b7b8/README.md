# W2.5 results: fault behaviour (B7), event behaviour (B8), label-leak audit and G0

Scope per AD-55: B7/B8 in depth for the priority set; the label-leak audit and G0 on every catalogue mode.
Pre-registration: `PREREGISTRATION.md` (committed before any outcome data). Every departure from it is in
`DEVIATIONS.md` (D1-D7) with results both ways; pre-registered verdicts are never changed by a deviation.
Machine-readable outputs: `results/`. Code: `code/` (run with `python -I`, paths as arguments).
All results were generated on `wp/w2.5-faults` at or before ccca0b4, before main c663f1f (W2.2 phase B part 1)
was merged; after the merge the bench uses W2.2's real ENG.AB_LIT lane instead of its zero lane (AB is never
selected on the bench) and its smoke tests pass (`tests/integration/test_faults_bench_*.py`).

**Credibility ceiling:** NASA-STD-7009B Level 2 against proxy and transferred data. Nothing here is
validation against Tejas or IN20 fleet data. Several B7 checks compare an implemented law with the same
source its parameter was set from; those are consistency checks, marked as such, not independent validation.

## 1. Priority set (catalogue `validation: validated`, 11 modes)

| Mode | Why it is in the set | Evidence the checks use | Checks |
|---|---|---|---|
| FM.ENG.FOULING | Gas-path deterioration a fleet trends; the only released fighter signatures with directions (Muir matrix) | Muir et al. AGARD-CP-448 p7 (CF-18 F404 test cell) [TRANSFER]; Kurz & Brun (~1 % per roughness step) [TRANSFER] | B7-ENG-FOUL-SIG, -FOUL-RATE |
| FM.ENG.EROSION | As above | Muir [TRANSFER]; ProDiMES (HPC -5 % at 5,000 flights), C-MAPSS (HPT -2.6 % at 3,000 cycles) [TRANSFER] | B7-ENG-ERO-SIG, -ERO-RATE |
| FM.ENG.HPT_DETERIORATION | As above | Muir [TRANSFER]; N-CMAPSS post-onset trajectories [TRANSFER] | B7-ENG-HPT-SIG, -HPT-ONSET |
| FM.ENG.HPC_DAMAGE | The released fighter magnitude (C26) | Muir: at fixed N2, PS3/P1 +8 %, Wf +8-14 % for about -5 % HPC efficiency [TRANSFER] | B7-ENG-C26 |
| FM.ENG.BEARING_SPALL (+ healthy-wear debris) | Su-30MKI IAF malfunctions are dominated by bearing chips (report §9) [DIRECT, IAF] | Bennett 1996 QFDA (CF188) [TRANSFER]; NASA TM-2011-217117 [TRANSFER] | B7-OIL-C25, -SPALL |
| FM.ENG.OIL_CONDITION | Oil analysis is the released engine-condition route | JOAP SOAP slopes [TRANSFER] | B7-OIL-SOAP |
| FM.SNS.T5_HARNESS_BIAS | AD-26: a measurement bias is not a deterioration | F404 T5 harness bias (Merrington) [TRANSFER] | B7-SNS-BIAS |
| FM.HYD.PUMP_WEAR | The released utility trend curve | US 12,265,000 case-drain flow and temperature [TRANSFER] | B7-HYD-PUMP-SIG, -TIME |
| FM.ELEC.GEN_DIODE | Generator loss and backup transfer are standard-bounded | MIL-STD-704F; US 9,910,083; AIB F-16CM 92-3881 [TRANSFER] | B7-ELEC-GEN |
| FM.LG.BRAKE_WEAR | Brake and tyre wear drive Tejas availability (report §18) | Collins F-15C/D carbon brakes 1,400 landings [TRANSFER] | B7-LG-BRAKE |
| FM.LG.TYRE_WEAR | As above | F-16 tyres 4-12 landings [TRANSFER] | B7-LG-TYRE |

The other 72 modes carry `validation: unvalidated (AD-55): outside the W2.5 priority set; <reason>` in
`configs/tejas/faults/catalogue.yaml` (format `phalanx.fault_catalogue/2`; `FaultMode.validated`,
`catalogue.priority_set()`).

## 2. B7 fault behaviour

CI = two-sided 95 % t-interval over pairs unless stated. "Pre-reg" = the pre-registered run and verdict;
"post hoc" = the deviation run (DEVIATIONS.md), reported beside it.

### 2.1 Engine gas path on the ground-run bench (n = 5 pairs per fault; `results/b7_engine*.json`)

Muir cross-plots C1-C7 (C1 W1c-N1c, C2 N2c-N1c, C3 Fgc-N2c, C4 Wfm-N2c, C5 PS3/P1-N2c, C6 T56-P56/P1, C7
N2c-P56/P1; C1 and C3 from test-cell truth instruments). Shift = mean relative distance of the faulty
governed holds from the healthy line. Arrow cell PASS iff the CI excludes 0 on Muir's side; "-" cell PASS iff
|mean| < 1 % (AD-53). A cell needs all 5 pairs evaluable.

| Fault (state, magnitude) | Muir row | Pre-reg verdict | Post hoc D3 (own-input start): cells PASS, failing cells |
|---|---|---|---|
| F1 fan fouling (`foul_fan` 0.02) | fan | FAIL (4/5 pairs evaluable) | FAIL, 6/7: C2 +0.16 % [+0.13, +0.19] (Muir: down) |
| F2 HPC fouling (`foul_hpc` 0.02) | HPC | FAIL (2/5) | FAIL, 6/7: C4 +0.51 % [+0.39, +0.63] (Muir: down) |
| F3 HPC erosion (`ero_hpc` 0.05) | HPC | FAIL (0/5) | FAIL, not evaluable (4/5: pair 4 rolls back from its own trim); on 4 pairs the 6 arrow cells have Muir's sign, C1 -1.46 % (Muir: "-") |
| F4 HPT erosion (`ero_hpt` 0.026) | HPT | FAIL (0/5) | FAIL, 5/7: C5 -0.34 % [-0.47, -0.20] (Muir: up), C7 +0.00 % (Muir: down) |
| F5 LPT erosion (`ero_lpt` 0.008) | LPT | **PASS** 7/7 | **PASS** 7/7 |
| F6 HPT abnormal (`abn_hpt` 0.03) | HPT | FAIL (0/5) | FAIL, 5/7: C5 -0.34 % [-0.49, -0.19] (up), C7 -0.01 % (down) |
| F7 HPC damage (`extra_hpc_eta` -0.05), C26 | - | FAIL (1/5) | FAIL: PS3/P1 +2.37 % [+2.23, +2.51] vs [6, 10] %; Wfm +7.44 % [+7.09, +7.79] inside [6, 17.5] %; Fg +4.4 % |

Why the pre-registered run was mostly not evaluable (DEVIATIONS D3): the bench started each run from M08's
healthy no-load trim and stepped health, fault and M09's idle loads in at t = 0; the deteriorated engines
then rolled back below idle on M08's acceleration Wf/PS3 schedule and the minimum-fuel clamp. Steady ground
idle with M09's loads needs Wf/PS3 = 1.20-1.24 x M08's reference line for the healthy builds and up to
1.36 x for the B7 deteriorations, against an accel schedule of 1.4 x (`acc_k`, [ASSUMPTION], A-W1.3b-4).

IRP diagnostic (PLA 90, D3): the healthy engine is on the N1 governor with the nozzle T5 loop active; the
deteriorations open A8 (+5.8 % F4, +6.8 % F6, +8.1 % F7, +12.9 % F3) and lose 3.5-4.7 % thrust at held N1 and
T5: the F100 DEEC expectation (A8 opens, thrust falls), with N1 held by its governor.

Reading: only LPT erosion reproduces its Muir row. The failing cells are signs or magnitudes of M07's
deterioration response (fan fouling moves N2c-N1c the wrong way; HPC fouling raises fuel at given N2; HPT
deterioration lowers PS3/P1 at given N2 and leaves N2c-P56/P1 unchanged; HPC damage raises PS3/P1 a third as
much as Muir measured). They are M07 calibration targets for W2.3, not fixable in M10/M11.

### 2.2 Progression laws (usage mode, real M10; `results/b7_progression*.json`, `b7_spall.json`)

| Check | n | Result | Band (source) | Verdict |
|---|---|---|---|---|
| B7-ENG-ERO-RATE, HPC at 5,000 flights | 100 serials (pre-registered 200: D5) | Pre-reg 6.92 % (sd 0.91 %); post hoc D2 4.95 % (sd 0.65 %) | 5 % +/- 25 % (ProDiMES) | Pre-reg **FAIL**; D2 consistency check inside the band (base rate re-derived from the same source) |
| HPT at 3,000 cycles | 100 | 2.60 % (sd 0.40 %) | 2.6 % +/- 25 % (C-MAPSS) | PASS |
| Gamma/eta HPC | - | 1.8 | 1.8 (ProDiMES) | PASS (parameter) |
| B7-ENG-FOUL-RATE, 500 EOT h at dust 1 | 100 serials x 2 stages | 1.02 % (sd 0.21 %) | 1 % +/- 25 % (Kurz & Brun) | PASS; wash fraction structural (`test_health_protocol::test_mx_actions_wash_service_and_latent_forwarding`) |
| B7-ENG-HPT-ONSET | statistical test | `test_post_onset_trajectory_recovers_ncmapss_parameters` | N-CMAPSS | PASS |
| B7-OIL-C25 healthy debris | 999 healthy engines x 100 EOT h | mean 0.485 ug/h; 2 sigma 1.78 ug/h | Bennett's own 95 % CIs: mean [0.135, 0.814], 2 sigma [1.32, 2.32] | **PASS (C25 green, A5)** |
| B7-OIL-SOAP | golden | healthy slope in 0.02-0.07 ppm/h; spalling (L >= 2 mm) in 1-11 ppm/h | JOAP | PASS |
| B7-OIL-SPALL growth | 1 engine (deterministic law) | 0.087-0.318 mm/h for L in 0.8-3.4 mm | 0.08-0.34 mm/h (TM-2011-217117) | PASS (consistency: the rate constant was set from this range) |
| B7-OIL-SPALL debris | 1 | 20.0 mg/mm | 2-50 mg/mm | PASS |
| Spall initiation to critical (0.5 -> 8 mm) | 1 | 28 EOT h | open conflict "hours to tens of hours" vs 36-100 FH (App. A4) | reported |
| B7-HYD-PUMP-TIME | 200 pumps x 600 days | flat end median 133 d (q10-q90 87-184); limit median 288.5 d (241-341) | 152 d +/- 25 %; 350 d +/- 25 % (US 12,265,000) | PASS (consistency: incubation set from the same curve) |
| B7-LG-BRAKE | M10 40 wheels x 2,000 landings; M09 reference stop | 1,493 / 1,427 landings (4.6 % apart) | 1,400 +/- 25 %, within 10 % | PASS |
| Brake heat sink per stop | M09 | peak 439 K at wear 0.1, 501 K at wear 0.9 | higher when worn | PASS |
| B7-LG-TYRE | as brake | 8.04 / 8.01 landings | [4, 12], within 10 % | PASS |

Spall-law finding (proposed decision PD-W2.5-6, below): the source gives 0.08-0.34 mm/h as the spread of a
roughly linear propagation rate between bearings (notes: lognormal, median about 0.15 mm/h), with an
acceleration at the knee; M10 makes the rate proportional to length (dL/dt = 0.1 L, deterministic), mapping
the between-bearing range onto lengths 0.8-3.4 mm. The pre-registered check passes because it was written on
the same reading.

### 2.3 Sensor bias, hydraulics, generator (bench, n = 5 pairs; `results/b7_misc.json`)

| Check | Result | Verdict |
|---|---|---|
| B7-SNS-BIAS (i): recorded shift of ENG.T5.HARNESS_B at 60 deg | 30.00 K in every pair (injected 30 K; LSB 1 K); harness A 0.00 K | PASS |
| B7-SNS-BIAS (ii): engine truth at 60 deg | T5 0.00 K, N2 0.000 % | PASS |
| Diagnostic: M14 | ENG-036 recorded in the faulty runs only | - |
| Diagnostic at 90 deg (pre-reg start) | 2/5 healthy runs rolled back below idle (D3); on the other 3 pairs truth T5 -2.4 to -2.8 %, A8 +5.0 to +5.7 %, thrust -4.2 to -4.8 % at held N1 | - |
| Diagnostic at 90 deg (D3 start, kind `bias_d3`, 5 pairs; (i) and (ii) PASS again) | truth T5 -2.65 % [-2.87, -2.43], A8 +5.42 % [+4.94, +5.89], thrust -4.58 % [-4.97, -4.19], N1 held: the FADEC selects the higher (biased) T5 and opens the nozzle, so the true T5 falls, as expected | - |
| B7-HYD-PUMP-SIG: system-1 fluid temperature, last 30 s | +5.35 K [+5.34, +5.37]; system 2 -0.004 K | PASS |
| Diagnostic: system-1 pressure | -0.78 bar [-0.81, -0.75] | - |
| B7-ELEC-GEN: generator offline within one frame | 5/5 (0-3.3 ms) | PASS |
| B7-ELEC-GEN: essential DC back in 22-29 V within 50 ms | 5/5 (33.3 ms) | PASS |
| B7-ELEC-GEN: M14 records ELE-401 after the onset | 0/5 | **FAIL** (overall FAIL) |

ELE-401 (DEVIATIONS D4): it is an external code (the GCU declares it). In telemetry mode M14 tests internal
codes only and takes external codes from `monitor.bit_report`, which nothing sends for the generator; M11's
`monitor.lru_condition` therefore sets a test shift that nothing evaluates. Closing the ground run
(`gen_d4`, pair 0) does not change it. Request to the electrical system's owner below.

## 3. B8 event behaviour (usage-mode operations worlds; `results/b8.json`, `b8_um.json`, `b8_chain1.json`,
`b8_chain3.json`)

Sample: 8 one-tail worlds (TJ101-TJ108) x 180 days per regime, real M02/M18/M21/M10/M11 (stochastic)/M14.
Exposure: immature 615 sorties, 511.6 FH; mature 914 sorties, 732.5 FH (the immature tails fly fewer sorties:
more BIT work orders ground them). Truth matching as pre-registered. Rule for shares: the 95 % Wilson CI must
overlap the band.

| Check | Immature (pre-reg) | Mature (pre-reg) | Band | Verdict |
|---|---|---|---|---|
| B8-FA-RATE (false alarms per FH, Poisson 95 %) | 2.21 [2.09, 2.35] (1,132 alarms) | 0.0027 [0.0003, 0.0099] (2) | immature [1, 10]; mature <= 0.02 | PASS / PASS |
| B8-FA-SHARE | 1.000 [0.997, 1.000] | 1.0 [0.34, 1.0] (n = 2) | [0.86, 0.999]; [0.22, 0.53] | PASS / PASS (mature uninformative) |
| B8-PERSIST, 1 flight | 0.700 [0.663, 0.735] (627 episodes) | - | [0.67, 0.81] | PASS |
| B8-PERSIST, >= 3 flights | 0.145 [0.120, 0.175] | - | [0.10, 0.18] | PASS |
| B8-NFF (RTOK share of shop findings) | 1.000 [0.982, 1.000] (213) | 1/1 | [0.25, 0.63] | **FAIL** / PASS (n = 1) |
| B8-CND (troubleshot BIT/pilot jobs) | 0.731 [0.700, 0.761] (815) | 2/3 | [0.22, 0.54] | **FAIL** / PASS (n = 3) |
| B8-CHAIN2: non-grounding BIT job closed administratively after exactly 3 monitored flights | 107/107 at 3 flights; elapsed median 6.0 d (q10-q90 2.8-9.8 d) | 1/1 at 3 flights (2.0 d) | exactly 3 flights | PASS |
| B8-CHAIN3: exceedance from recorded data -> EXCEEDANCE_INSPECTION, NMC until inspected (`chain3.py`, n = 1) | ELE-702 from the recorded generator-fault ground run; inspection opened 0.34 h after download, closed after 1.93 h; tail NMCM_U throughout (reference world FMC); no sortie while open | | both hold | PASS |
| B8-CHAIN1: engine lube anomaly (`chain1.py`, n = 1 per configuration) | pre-registered M14 configuration: never detected (see below); usage mode (D7): ECM-702 at the next sortie, 2.6 h after onset; pilot-discovered ENG job 3.4 h after; engine removed and replaced, 56.2 h, NMCM_U | | anchor about 3 h, same day, with parts | reported: 19 x the anchor (M18 has no oil-pressure-transmitter position, so the engine goes) |

Why NFF and CND fail: the true-fault side of the worlds is almost empty. 47 fault instances in 1,244 FH, all
transient (AB no-light and blowout 5-10 s, hung and hot starts 20-30 s, pop stall 3 s, connector glitches,
one limit cycle) and none persistent; the persistent modes' onset rates ([ASSUMPTION], e.g. 3e-4 per LRU-hour)
give less than one expected instance in this exposure. With no true failures behind the removals every shop
finding is RTOK and most troubleshooting ends as could-not-duplicate. Real fleets have a large share of true
failures behind their removals (RTOK 25-63 %). Three mechanisms are involved, all in W2.5's modules:
1. **M14 configuration in the operations worlds (harness).** The worlds used M14's default telemetry
   configuration, as every W1/W2 operations world does: only the 33 internal codes are tests. The usage-mode
   detection stand-in (A-W1.5-26) sets the condition of a mode's first detection code; for the engine
   transients and the oil-pressure transmitter that code is external or CIR, so the stand-in was inert.
2. **M11 bug (fixed, c7ea09d).** The stand-in was never cleared with its instance, so wherever it is a test
   (usage mode) M14 kept declaring the code after the fault was gone (found by chain 1: 13 phantom ECM-702
   records and repeated engine removals before the fix). The pre-registered B8 run is unaffected (all its
   stand-ins were inert).
3. **M14 usage-sortie evaluation (open, PD-W2.5-7).** In usage mode a sortie's tests are evaluated when the
   summary arrives at landing, so a condition that set and cleared during the flight (every transient here)
   is never seen.

Post hoc D7 (`results/b8_um.json`, M14 in usage mode, after the M11 fix):

| Check | Immature (D7) | Mature (D7) | Verdict |
|---|---|---|---|
| FA rate per FH | 5.44 [5.23, 5.66] (543 sorties, 452 FH) | 0.011 [0.005, 0.022] (914 sorties, 732 FH) | PASS / FAIL (upper bound above 0.02) |
| FA share | 1.000 [0.998, 1.000] | 8/8 [0.68, 1.00] | PASS / FAIL |
| Persistence 1 flight; >= 3 flights | 0.754; 0.107 | - | PASS |
| NFF (RTOK) | 1.000 [0.984, 1.000] | 1/1 | FAIL / PASS (n = 1) |
| CND | 0.794 [0.770, 0.816] | 3/4 | FAIL / PASS (n = 4) |
| CHAIN2 | 73/73 at 3 flights | 6/6 | PASS |

Still no true detection: the 42 instances are all transients, lost by mechanism 3. With 104 tests instead
of 33 the false-alarm rates rise about 2.5 x (immature) and 4 x (mature): the regime calibration (made on
the internal tests) does not carry over to usage mode (PD-W2.5-8).

## 4. Label-leak audit and G0 (all 83 modes, 166 pairs; `results/leak/`)

Runs: per mode 2 pairs (healthy and faulty bench runs of one identity, 20 s, fault at 5 s or its M10 state
at t = 0). FM.ENG.LIFE_USAGE and FM.FUEL.GAUGING_ARTEFACT are not injectable (no label exists to leak).

| Audit | Result | Pre-registered verdict |
|---|---|---|
| (a) Paired pipeline invariance (deterministic) | 0 problems in 166 pairs | **PASS** |
| (b) Metadata-only (LR, GB; grouped CV; one-sided) | LR 0.526 [0.466, 0.589]; GB 0.551 [0.491, 0.616]; 166 pairs | **PASS** |
| (b) Texture-only (5 texture-visible modes excluded, AD-48.7) | LR 0.585 [0.521, 0.650]; GB 0.583 [0.518, 0.646]; 156 pairs | **FAIL** |
| (c) G0, binding pipeline-only subset (paired, one-sided) | LR 0.526 [0.505, 0.550]; GB 0.551 [0.522, 0.582]; 166 pairs | **FAIL** |
| NC1 texture (faulty ENG.T5 re-quantised to 1 degC) | texture AUC LR 0.947, GB 0.976 | caught |
| NC2 pipeline (faulty runs lose the last second of ENG.N2.A) | invariance 166/166; metadata and G0 AUC 1.0 | caught |
| NC3 noise path (one unaffected channel, other stream) | invariance 166/166 | caught |

Post-hoc diagnostics (DEVIATIONS D1): every separating feature difference is on a channel the fault's
physics reached (0 differences on channels with identical acquisition input, across texture, metadata and G0
features). Texture separation comes from the abrupt modes that change signal dynamics within 20 s (blade
loss, liberation, stalls, flameout, over-metering): abrupt modes LR 0.603 [0.529, 0.674] (112 pairs),
gradual degradation 0.577 [0.457, 0.696] (44 pairs, at chance). G0's separation is the float32
representability of affected channels (a function of the recorded value). On the structural pipeline facts
(sample counts, count over rate, dtype, NaN, run frames and seconds) healthy and faulty runs are identical in
166/166 pairs (AUC exactly 0.5). The STUB is removed: `phalanx.validation.guards.label_leak` implements the
audit (`paired_invariance`, `label_leak_audit`, `leak_features`, `texture_features`).

Reading: no non-physical cue was found; the texture-only and G0 rules as pre-registered are not
physics-blind for same-path healthy/faulty pairs. Proposed decision PD-W2.5-4 below.

## 5. Power-up BIT and preflight aborts

- `ops.power_up` {tail_no, sortie_id, engine_starts, cold_soak} is catalogued (producer M02, consumers M05,
  M11, M14; `planned: W2.1a`). M14 runs PBIT at power-up and CBIT from then on; `ops.takeoff` keeps that
  power-up (PROXY A-W2.1c-4 retired once M02 emits it). PBIT outcomes are identical whichever event powers
  the monitor up (keyed draws). Tests: `tests/integration/test_monitoring_power_up.py` (the strict
  tracked-exception test fails the day M02 emits the event).
- M11 draws the preflight start failures (JFS cold start, hung start, hot start) at `ops.power_up`
  (A-W2.5-2); a start failure goes to M02 as `ops.start_failure` before take-off and M02 ground-aborts.
  End to end in the operations world: `tests/integration/test_faults_preflight_abort.py` (n = 1, forced
  probability). Tracked gap (strict test): after a ground abort M02 closes nothing toward M11/M14.

## 6. Proposed decisions (for the coordinator; not applied)

- **PD-W2.5-4 (label-leak verdict rule for same-path pairs).** Evidence: §4 and D1. Proposal: for
  healthy/faulty pairs generated through one path, the binding label-leak verdict is (a) paired pipeline
  invariance plus G0 on the structural pipeline facts; the texture-only and float32-representability features
  are restricted to channels whose acquisition input is identical in the pair (unaffected channels), and on
  affected channels they are diagnostics. Alternatives: keep the pre-registered rules (they flag physics as
  leaks); drop the classifier audits (loses the check on unaffected channels). What would change it: a leak
  that only shows on affected channels (e.g. a fault-dependent pipeline branch on an affected channel), which
  this rule would miss; the invariance check catches it only if the acquisition input is unchanged.
- **PD-W2.5-5 (generator BIT declarer).** ELE-401/ELE-404 need a physical declarer in telemetry mode: either
  M09 emits `monitor.bit_report` on its GCU state transitions, or the dictionary declares ELE-401 from the
  recorded ELEC.GEN.OUT discrete (src `cir`, monitor high, engine-running gate). M14 unchanged either way.
- **PD-W2.5-6 (bearing spall growth law).** Replace dL/dt = r L (deterministic) by a per-bearing lognormal
  linear rate (median about 0.15 mm/h, 0.08-0.34 mm/h range) until the knee (about one rolling-element
  spacing), then acceleration [TRANSFER: NASA TM-2011-217117; research_notes
  texture_and_fault_gap_closure.md, propagation note and table row #22]. Re-tune the SOAP golden after.
  Would change with an IN20 bearing propagation source.
- **PD-W2.5-7 (M14 usage-mode sorties honour in-flight condition intervals).** M14 keeps the set and clear
  instants of conditions that arrive while the usage-mode sortie is not yet evaluated and applies them on the
  test grid of that sortie (piecewise test shift), so transients that clear before landing are detectable.
  Schema bump of M14; owner: W2.5 follow-up. Alternative: M10 forwards the sortie summary before the
  conditions (no: the summary is written at landing).
- **PD-W2.5-8 (operations-world M14 configuration and true-failure incidence).** Usage-mode worlds run M14 in
  usage mode (every code a test, A-W1.5-26) and the regime calibration is redone for 104 tests instead of 33;
  the persistent-failure onset rates of M11 get evidence for fighter LRU removal rates (mean flight hours
  between removals) before B8-NFF and B8-CND are re-run. Not tuned here: the B8 bands are the test, not a
  fitting target.

## 7. Requests to other owners

- **W2.1b / W2.3 (M07, M08):** (1) accel margin at ground idle: M08's accel Wf/PS3 schedule (1.4 x a
  reference line derived from the no-load nominal engine) leaves 3-20 % margin at idle once M09's idle loads
  (about 21 kW PTO, 0.5 kg/s bleed) and B7-level deterioration are present; after a small sag the engine
  rolls back to WF_MIN with T5 rising (healthy builds included: 2/5 B7-SNS-BIAS identities). Strict xfail:
  `tests/integration/test_faults_bench_trim.py`. (2) Muir-row mismatches of §2.1 (F1 C2, F2 C4, F4/F6 C5 and
  C7, C26 PS3/P1 +2.4 % vs +8 %) as W2.3 calibration targets. (3) M08 README: `bleed_schedule_bias` is now
  engine-targeted in the catalogue.
- **W2.1a (M02, M05, integration):** M02 emits `ops.power_up` with `engine_starts` and `cold_soak`; M02
  closes a ground-aborted sortie toward M11/M14; M05 consumes `ops.power_up`; the integrated aircraft feeds
  M14 with `monitor.observe` CIR chunks (the bench has none).
- **Electrical system owner (M09) or dictionary (M01):** PD-W2.5-5.
- **W2.6 (M18):** an electrical exceedance (ELE-702) is filed as a COND-STRUCT inspection with MAL-OG
  (`_exceedance_job` only distinguishes engine and structure); oil-pressure-transmitter position for chain
  1; per-tail router (the B8 worlds are one tail each).
