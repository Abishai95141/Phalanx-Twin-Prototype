# W2.5 pre-registration: B7 fault behaviour, B8 event behaviour, label-leak audit and G0

Committed before any outcome data of these experiments is generated (RULES.md rule 4). Smoke runs made
before this commit checked wiring and run time only (bench: 0.5 s per simulated second warm; one-tail
operations world: 7 s per 30 days); no statistic named below was computed. Deviations go to
`DEVIATIONS.md` with date, reason and results both ways.

Scope (AD-55 item 3): B7/B8 in depth for the priority set; the label-leak audit and G0 on **every**
catalogue mode. Credibility ceiling: NASA-STD-7009B Level 2 against proxy and transferred data; nothing here
is validation against Tejas or IN20 fleet data.

## 1. Priority set (catalogue `validation: validated`)

| Group | Modes | Why (maintenance relevance, evidence available) |
|---|---|---|
| Engine performance | FM.ENG.FOULING, FM.ENG.EROSION, FM.ENG.HPT_DETERIORATION, FM.ENG.HPC_DAMAGE | The gas-path deterioration a fleet trends; the only released fighter signatures with directions and magnitudes (Muir matrix, C26) |
| Oil and bearing | FM.ENG.BEARING_SPALL (+ healthy-wear debris), FM.ENG.OIL_CONDITION | Su-30MKI IAF malfunctions are dominated by bearing chips (report §9); QFDA and SOAP statistics are released (Bennett 1996, JOAP) |
| Sensor bias | FM.SNS.T5_HARNESS_BIAS | AD-26: bias is separate from deterioration; the F404 T5 harness bias is the released case (Merrington) |
| Hydraulics | FM.HYD.PUMP_WEAR | Pump case-drain trend is the released utility monitoring curve (US 12,265,000) |
| Electrical | FM.ELEC.GEN_DIODE | Generator loss and backup transfer are MIL-STD-704F-bounded and AIB-documented |
| Brakes and tyres | FM.LG.BRAKE_WEAR, FM.LG.TYRE_WEAR | Brake/tyre wear drives Tejas availability (report §18); lives per landing are released (F-15, F-16) |

Every other mode is `unvalidated (AD-55)` with its reason in the catalogue.

## 2. Generation paths

1. **Ground-run bench** (`code/bench.py`): real M07, M08, M09, M10, M11 (scripted faults, telemetry mode),
   M12, M13 (lanes and the recording entry point) and M14; boundaries: published replay producers (phase
   GROUND_RUN, ISA sea level 288.15 K / 101,325 Pa, PLA programme), a chocked stationary airframe, a static
   FCS, a zero AB-lit lane (the bench never selects AB). Faults enter only as events to their state owners.
   A healthy and a faulty run of a pair share the identity `(scenario, tail, sortie)`: every exogenous draw
   (process disturbances, sensor noise, build deltas) is common (CRN).
2. **Usage-mode M10 fleets** (`code/progression.py`): the real M10 advanced by `health.sortie` events.
3. **M09 landing drive** (`code/landing.py`): the real M09 kernel driven through a reference landing roll.
4. **One-tail operations worlds** (`code/fleet.py`): real M02 (operations mode), M18, M21, sink, M10, M11
   (stochastic), M14; one tail per world (M18 addresses one health module id; the per-tail router is W2.6's).

## 3. B7 fault behaviour

Common pass rule notation: CI = two-sided 95 % t-interval of the mean over pairs (df = n - 1).

### B7-ENG-*-SIG and B7-ENG-C26 (bench, telemetry)

- **Programme:** settle 12 s at PLA 18 deg, then holds of 15 s at 31, 45, 60, 70, 80, 84 deg (governed, below
  IRP 87 deg), then 15 s at 90 deg (IRP regime). Duration 117 s. Steady value per hold = mean of the recorded
  samples in its last 7 s.
- **Faults** (M10 state set at t = 0 through `health.fault`, i.e. an engine degraded before the run):
  F1 fan fouling `eng:foul_fan` 0.02; F2 HPC fouling `eng:foul_hpc` 0.02; F3 HPC erosion `eng:ero_hpc` 0.05;
  F4 HPT erosion `eng:ero_hpt` 0.026; F5 LPT erosion `eng:ero_lpt` 0.008; F6 HPT abnormal `eng:abn_hpt` 0.03;
  F7 HPC damage `eng:extra_hpc_eta` -0.05 (efficiency only: Muir's "about -5 % HPC efficiency equivalent").
  Magnitudes: fouling at Kurz & Brun's ~1 % per roughness step (M10 drift gives 2 % at ~1,000 EOT h);
  erosion at ProDiMES 5,000 flights (HPC) and C-MAPSS 3,000 cycles (HPT, LPT); HPT abnormal mid-range.
- **Cross-plots** (Muir Fig. 15, inlet-corrected, recorded channels): theta1 = recorded T1 (mean of
  ENG.T1.V) / 288.15 K, delta1 = test-cell barometer (bench ambient) / 101,325 Pa. C2 N2c vs N1c (ENG.N2.V,
  ENG.N1.V); C4 Wfm/(delta1 sqrt theta1) vs N2c (ENG.WFM); C5 PS3/P1 vs N2c (ENG.PS3.V); C6 T56/theta1 vs
  P56/P1 (ENG.T5, ENG.P5); C7 N2c vs P56/P1. Test-cell-only columns from truth instruments (reported, not
  recorded aircraft channels): C1 W1c vs N1c (eng.w2), C3 Fgc vs N2c (eng.thrust).
- **Shift** per pair and cross-plot: from the six governed holds, interpolate the healthy line at each faulty
  abscissa inside the healthy range; shift = mean relative difference (faulty - healthy) / healthy. Fewer
  than 3 faulty points inside the range: the cell is not evaluable (counts as FAIL).
- **n = 5 pairs** (minimum for a t-CI with df 4; the paired design removes the common variance).
- **Sign rule (Muir Fig. 15 rows; F1 fan row; F2, F3 HPC row; F4, F6 HPT row; F5 LPT row):** an arrow cell
  PASSes iff the CI excludes 0 on the predicted side; a "-" cell PASSes iff |mean| < 1 % (AD-53 b). A row
  PASSes iff all its cells PASS. Validated modes: FOULING (F1, F2), EROSION (F3, F4, F5), HPT_DETERIORATION
  (F6).
- **C26 magnitude (F7):** Muir measured at fixed N2: PS3/P1 +8 %, Wf +8-14 % (NRC model +9.6 %, +9.6 %; Fg
  +6.0 %). PASS iff the mean C5 shift is in [6 %, 10 %] and the mean C4 shift in [6 %, 17.5 %] (the source's
  values or range widened by 25 %, architecture §14.2).
- **IRP regime diagnostic (no verdict on the mode status):** at PLA 90, report the change of A8 (truth),
  N1, T5 and thrust; expectation [TRANSFER: F100 DEEC, report §3]: when the healthy run's nozzle T5 loop is
  active, deterioration (F3, F4, F6) opens A8 and lowers N1/thrust; otherwise T5 rises at held N1.

### B7-SNS-BIAS (bench)

FM.SNS.T5_HARNESS_BIAS through `faults.inject` at t = 0, severity 0.5, covered (bias = 0.12 x 0.5 x span of
ENG.T5.HARNESS_B). Programme: 12 s at 18 deg, 40 s at 60 deg, 30 s at 90 deg. n = 5 pairs.
- (i) PASS iff the mean recorded shift of ENG.T5.HARNESS_B over the last 20 s at 60 deg equals the injected
  bias within max(1 recorded LSB, 2 % of the bias) and ENG.T5.HARNESS_A's mean shift is within 1 LSB.
- (ii) PASS iff the engine truth is unchanged at 60 deg (governed N2, no T5 control): |mean shift| of truth
  T5 < 0.5 K and of truth N2 < 0.05 % (the bias is a measurement, not a deterioration: AD-26).
- Diagnostic: M08 lane-compare state/code; at 90 deg the change of A8, N1 and truth T5 (expectation: the
  FADEC selects the safer, higher T5 and opens the nozzle, so truth T5 falls).

### B7-HYD-PUMP-SIG (bench) and B7-HYD-PUMP-TIME (usage mode)

- SIG: `util:hyd1_pump_wear` = 1.0 (the wear limit) at t = 0; 180 s at PLA 31 deg, static FCS. n = 5 pairs.
  PASS iff the system-1 fluid temperature (recorded HYD.SYS1.T, mean of the last 30 s) is higher in the worn
  run with CI excluding 0 [US 12,265,000: case-drain flow and temperature rise with pump wear]; system 2 is
  unchanged (|mean| < 0.1 K). Diagnostic: HYD.SYS1.P mean.
- TIME: 200 pump serials, daily sorties for 600 days. PASS iff the median end of the flat period is within
  25 % of 5 months (152 d) and the median time to the limit within 25 % of 11.5 months (350 d). Note: the
  incubation parameter is set from the same curve; this checks the implemented law, not an independent fact.

### B7-ELEC-GEN (bench)

FM.ELEC.GEN_DIODE through `faults.inject` (severity 1, covered) at t = 10 s + 0.37 k s (k = 0..4) of a 20 s
run at 31 deg. n = 5. PASS iff, in every run: the generator goes offline (truth `util.gen_online` 1 -> 0)
within one frame of the onset; the essential DC bus (truth) is back inside 22-29 V within 50 ms
(MIL-STD-704F transfer interruption); M14 records ELE-401 after the onset.

### B7-LG-BRAKE and B7-LG-TYRE (M10 usage mode and M09 landing drive)

- M10 surrogate: life = 1 / (mean wear per reference landing) over 2,000 landings of 20 serials. M09: wear
  accrued in one reference landing roll (3.96 MJ per wheel) -> life.
- PASS (brake) iff both lives are within 25 % of 1,400 landings (Collins F-15C/D) and within 10 % of each
  other; PASS (tyre) iff both lives are in [4, 12] landings (F-16) and within 10 % of each other.
- Per-stop heat-sink temperature (M09, TFG (c) #33): PASS iff the peak brake temperature after the reference
  stop is higher at wear 0.9 than at wear 0.1.

### B7-OIL-* and engine progression (usage mode)

- B7-OIL-C25 = golden `test_c25_healthy_oil_debris_wear_rate` (fleet mean and 2 sigma inside Bennett's CIs).
- B7-OIL-SOAP = golden SOAP slopes: healthy 0.02-0.07 ppm/h; spalling 1-11 ppm/h (JOAP).
- B7-OIL-SPALL: spall growth rate in 0.08-0.34 mm/h for L in 0.8-3.4 mm; debris per mm in 2-50 mg; time from
  initiation to the critical length reported against the open conflict "hours vs 36-100 FH" (App. A4).
- B7-ENG-ERO-RATE: 200 serials, 5,000 flights at S = 1 (commercial reference): PASS iff mean HPC efficiency
  loss within 25 % of ProDiMES -5 % and Gamma/eta = 1.8; HPT at 3,000 cycles within 25 % of C-MAPSS -2.6 %.
- B7-ENG-FOUL-RATE: 200 serials, 500 EOT h at dust 1: mean fouling within 25 % of 1 %; a wash removes the
  fraction rho of it (structural).
- B7-ENG-HPT-ONSET = statistical `test_post_onset_trajectory_recovers_ncmapss_parameters`.

## 4. B8 event behaviour (one-tail operations worlds, usage mode)

- **Sample:** 8 worlds (tails TJ101-TJ108) x 180 days per regime (immature, mature), one root seed per regime.
  Expected per regime about 130 sorties per world (from the 30-day smoke rate), i.e. about 1,000 sorties and
  750 FH: a 95 % Poisson upper bound of 0.02 / FH needs at most 3 events in that exposure and resolves the
  immature band [1, 10] / FH.
- **Truth matching:** a BIT record is a true detection iff an active M11 instance at its time lists its code
  (catalogue detection codes or a cascade node's code); otherwise it is a false alarm.
- B8-FA-RATE: immature: Poisson 95 % CI of false alarms per FH inside [1, 10]; mature: upper bound <= 0.02.
- B8-FA-SHARE (share of BIT indications that are false): immature in [0.86, 0.999] (F/A-18E/F 86 %; F-35
  14:1-1,079:1); mature in [0.22, 0.53] (RADC Cat II 22-53 %; F/A-18E/F 33.5 %). PASS iff the 95 % Wilson CI
  overlaps the band; FAIL iff it lies outside.
- B8-PERSIST (immature): share of false-alarm episodes lasting >= 3 flights in [0.10, 0.18], 1 flight in
  [0.67, 0.81] (RADC); same CI-overlap rule.
- B8-NFF: RTOK share of shop findings of removed units in [0.25, 0.63] (F-14 RTOK 25 %; NFF by technology
  29.5-63 %); CI-overlap rule (both regimes pooled, reported per regime).
- B8-CND: CND share of troubleshot BIT/pilot work orders in [0.22, 0.54] (F-14 CND 31 %; F-16 CND+RTOK 54 %;
  RADC Cat II 22-53 %); CI-overlap rule.
- B8-CHAIN2 (BIT false alarm): every non-grounding BIT work order without recurrence is closed
  administratively after exactly 3 monitored flights (NAMP / F-35 HRC workflow); the elapsed-time
  distribution is reported (no external anchor).
- B8-CHAIN3 (exceedance -> conditional inspection): an M14 exceedance from recorded data (bench CIR fed to
  M14) downloaded to M18 opens an EXCEEDANCE_INSPECTION and the aircraft is not mission-capable until it is
  inspected; PASS iff both hold; the inspection duration is reported.
- B8-CHAIN1 (engine lube anomaly) is reported as measured with its known limitation (M18 has no
  oil-pressure-transmitter position; the anchor is ~3 h same-day with parts).

## 5. Label-leak audit and G0 (binding, all modes)

- **Runs:** for every catalogue mode m and k in {0, 1}: a healthy and a faulty bench run, identity
  `(LEAK, L<index><k>, <m>-<k>)`. Programme: 5 s at 18 deg, then 15 s at 60 deg (20 s). Faults: injectable
  modes through `faults.inject` at t = 5 s (covered, default severity draw); M10-process modes as their M10
  state set at t = 0 (map in `code/leak_campaign.py`, magnitudes at about half of the state's limit or at
  the B7 magnitudes); FM.SNS.GENERIC as a drift on ENG.PS3.A; FM.FUEL.GAUGING_ARTEFACT is not injectable (it
  emerges from the operating condition: no label exists to leak) and is reported as such. Modes whose target
  module is absent from the bench (M05, M06) still run: their M11/M14 traces are audited.
- **(a) Paired pipeline invariance (deterministic, every mode and pair):** for every recorded channel whose
  acquisition input (M12 output frames, or the M08 computed value) is bitwise identical in the two runs, the
  recorded value, validity, flags and sample instants must be bitwise identical; the per-channel sample
  counts and the run metadata must be identical for every channel. Any difference is a non-physical leak:
  FAIL.
- **(b) Classifier audits** (`label_leak_audit`, W0.5 core: L2 logistic regression and gradient boosting,
  grouped 5x3 CV, groups = pair, 2,000 stratified bootstrap resamples, seed 25): texture-only and
  metadata-only features (`leak_features`; per channel: log10 LSB, lattice adherence, zero-step fraction,
  first-difference MAD in LSB, kurtosis of first differences, lag-1 ACF of second differences, fraction at the
  series minimum / sample count, count over rate, float32 representability, plus run frames). Rule (AD-40,
  one-sided): FAIL iff, for either classifier, the 95 % CI lower bound of the AUC is above 0.5. Texture-only
  excludes the modes whose physical effect is texture (AD-48.7: sensor modes stuck, intermittent, spikes,
  open, short, probe open/short, slow); metadata-only covers every mode. n = 2 pairs x 82 modes.
- **(c) G0** (`g0_audit`, binding pipeline-only subset, paired, one-sided): healthy vs faulty, all modes.
- **Negative controls** (each must be caught): NC1 texture: the faulty runs' ENG.T5 re-quantised to 1.0 degC
  (a different lattice) -> texture audit FAILs; NC2 pipeline: the faulty runs lose the last second of
  ENG.N2.A -> invariance (a), metadata audit and G0 FAIL; NC3 noise path: one unaffected channel of the faulty
  runs recorded with a different noise stream -> invariance (a) FAILs.
- **Compute:** 328 runs x 20 s at about 0.5 s per simulated second, about 55 CPU-minutes, run in 3 processes.

## 6. Reporting

`README.md` gets the B7 and B8 tables (n, estimate, CI, band, PASS/FAIL), the audit results with the
negative controls, and the per-mode list. `results/` holds the machine-readable outputs (JSON/CSV).
