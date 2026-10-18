# W2.4a: DASHlink proxy - MF1 reachability, identification and quick look

Work package W2.4a (brief `docs/build_briefs/W2.4a_proxy_quicklook.md`). **W2.4a-1** (below the W2.4a-2
sections): the MF1 joint reachability study and the A2 self-test of the identification machinery; nothing in it
fits real data. **W2.4a-2** (the staged plan after the MF1 decision, AD-52 D): identification on **687-CAL
only**, development on Tail 652 and 687-TEST, archive 2 never read.

- **Credibility ceiling:** NASA-STD-7009B Level 2 against proxy data. The proxy is a four-engine regional jet
  (AD-43), not the F404-IN20; only structure transfers to the Tejas.
- **Status:** development evidence. No gate verdict. W2.4a-2 stages 1-5 and 7 reported below; stage 6
  staged on Kaggle.

## W2.4a-2 stages 6-7: quick look (staged on Kaggle) and the W2.4b pre-registration draft

- **Stage 6 (A4, A5)** is staged as a private Kaggle run (`kaggle_pending_cmds.txt`; about 8 CPU-hours, over
  the local rule): B1-B6 against D_tail / D_temp on the round-2 development lists (`holdout_652_s20`: 20
  Tail-652 flights with 20 687-TEST partners, and the reverse), three arms with common random numbers for
  per-test attribution - the committed configuration (stage-4 pooled-fit bank), the median-fit bank, and no
  engine bank - next to the stored round-2 S_R2b D_sim on the same 652 flights. Per flight: MF1 statistics
  (B1 per phase class PH 4 / 5 / 6 / taxi, governed classes, spectral pairs) and the B2 lags split A/T vs
  manual (A5). Smoke-tested locally on one flight per set (`code/st6_quicklook.py ... 4 1`): the real
  records reproduce the round-2 post hoc split (FF->N2 -0.5 s with the A/T, 0.0 s manual).
- **Stage 7:** `W2.4b_PREREGISTRATION_DRAFT.md`, written before archive 2 was ever read; section 11 lists the
  decisions that must precede its freeze.

## W2.4a-2 stage 5: staged indirect identification of the dynamics (report)

**Result.** On 687-CAL A/T windows the real engine words are **much slower than the proxy's** at the
recorded level, and the identification puts most of it in the **word lags**: the EGT indication lag at W_ref
comes out at **4.33 s** (round-2 prior 0.81 s) and the FF meter lag at **1.53 s** (round-2 0.218 s). Both
agree with the DASHlink step responses in the research notes, and both **conflict with the round-2 MEASURED
values**. The autothrottle gains are 3-8 times the MF1 base. **Coordinator decision needed** on the two lags
(below). The identified values are written into the proxy configuration with the conflict in their evidence
tags, so that stages 4 (pass 2) and 6 use them; they are one revert away.

**Method** (`code/st5_segments.py`, `code/st5_ident.py`, `code/st5_plant_rerun.py`; `ident` machinery of W2.4a-1
A2):
- **Windows, from the inputs only** (`results/stage5/segments.json`): 4 A/T windows of 120 s (airborne, A/T
  engaged, N1 command >= 60 %, the largest |dN1C| with both increases and decreases; one per flight, MF1-D
  order) and 3 manual approach windows of 160 s (A/T off, PH 6-7, airborne). Each is screened with the
  empty-bank full chain: A/T windows 99.8 % governed; manual windows 94-96 % (accel/decel schedules during
  the lever moves).
- **Indirect output error**, transient-weighted (AD-34), the closed loop simulated from the external commands.
  Residuals per (window, engine, word) with the model's offset **and gain** removed, so the dynamic parameters
  fit timing and shape and the stage-1 steady slopes do not load them.
- **Staging.** The first run fitted the plant on the A/T windows with the MF1-base autothrottle and drove
  i_hp, tau_egt and tau_ff towards zero at a cost reduction of 1 %
  (`results/stage5/ident_run1_plant_first_killed.log`):
  the model N1 followed the N1 command 1-3 s later than the real engine, and the plant parameters were
  compensating for the A/T loop. Stage 0 (autothrottle gains) was therefore added in front:

| Stage | Windows / words | Parameters (start -> estimate) | Cost | Jacobian step check |
|---|---|---|---|---|
| 0 autothrottle | 4 A/T / N1, N2 | at_kp 0.3 -> **0.889**; at_ki 0.2 -> **0.416** 1/s; at_rate 0.1 -> **0.828** 1/s | -70 % | 0.000 |
| 1 governor | 3 manual / N1, N2, FF | gov_kp 2.0 -> 1.30; gov_ki 1.0 -> 1.14 1/s | -25 % | **4.1 / 0.54: fails** |
| 2 plant + word lags (committed governor) | 4 A/T / all four | i_lp x**1.215** (h_lp 0.6 -> 0.729 s); i_hp x**1.257** (h_hp 0.3 -> 0.377 s); tau_egt 0.81 -> **4.33** s; tau_ff 0.218 -> **1.53** s | -32 % | <= 0.0009 |

- **Governor gains not adopted.** The manual-window Jacobian is not step-consistent (A-W2.4a-20: the accel and
  decel schedules switch inside the approach windows), so the committed 2 / 1 1/s stay. Stage 2 was re-run
  with them (`results/stage5/ident_plant_gov2.json`); with stage 1's 1.30 / 1.14 it gave i_lp x1.164,
  i_hp x1.098, tau_egt 4.12 s, tau_ff 1.47 s: within 4-14 %.
- **The prior does not hold the EGT lag.** The round-2 range (0.55-1.18 s) as a Gaussian penalty, scaled by the
  residual SD of the free fit: 4.35 s free, 4.33 s with the prior. With about 30,000 residuals the data
  dominate any prior of that width, and the Gauss-Newton SEs (1-3 %) are too small (white-residual
  assumption); the two stage-2 runs differ by 5 % on tau_egt.
- Stage 0 is not fully converged (at_rate still moving after 6 iterations). All three A/T gains exceed the W1
  sweep ranges (0.5, 0.3 1/s and 0.5 1/s), which were widened.
- Sample: 4 A/T windows (8 min) and 3 manual windows (8 min) on 7 CAL flights; about 1 CPU-hour in total.

**Evidence on the two word lags (report, not resolved).**

| Source | EGT word | FF word |
|---|---|---|
| This stage (closed loop, A/T windows) | tau_ref 4.33 s (about 6 s at cruise airflow) | 1.53 s |
| DASHlink step responses, E381 flights (`research_notes/.../empirical_dashlink_texture.md` Q7, MEASURED) | first-order tau 3-6 s (5.0-5.8 s above FL150) against N1/N2 1.1-1.3 s | tau about 1.3 s, as slow as N2 (1.13 s) |
| Round 2 frozen M-A variant S (REPORT §3.2, MEASURED) | tau_TC,ref 0.81 s plus a gas-path tau_T at its 0.1 s bound; variant P: gas-path 1.54 s, no thermocouple stage | 0.218 s, with a fuel-control rate limit of 262 lb/h/s carrying the slowness |
| Meter / probe physics (`texture_and_fault_gap_closure.md` Q2) | - | angular-momentum meters update every 300 ms, turbine meters about 10 ms; meter type unresolved |

- **The round-2 values belong to a different model structure.** Its open-loop chain put the FF slowness in
  a fuel-control rate limit and split the EGT slowness between a gas-path lag and the probe. The proxy's fuel
  control is the closed-loop M08, which moves the fuel quickly, so the slowness that the words show has
  nowhere to go but the word lags (or the A/T and inertias, which stage 0/2 fit).
- **Recorded-level equivalence.** At the words, an indication lag, a gas-path heat-storage lag (stage 3) and
  slower fuel control are hard to tell apart; they differ for the spools (fuel control) and for the controller
  T5 lanes (gas path), which DASHlink does not record. This stage's fit prefers fast true fuel plus a slow FF
  word, because the spools respond as the model's fast fuel predicts (inertias only +22-26 %).
- **Gas-path heat-storage evidence (coordinator item):** released *structure* evidence exists - MAPSS keeps a
  hot-section metal-temperature state TMPC (NASA TM-2004-212968), Litt 1989's F100 piecewise-linear model has
  "slow-response" burner-exit and fan-turbine-inlet temperature states, GasTurb simulates heat soakage
  (`research_notes/.../f404_in20_engine_model.md` Q6, `modelling_methodology.md`). **No released heat-capacity
  value for the proxy engine (or the F404) was found**, so no M07 heat-storage state is proposed; the EGT lag
  stays in M12 as decided.

**Decision (coordinator, 2026-10-15): (a) for the quick look.** The EGT (tau_ref 4.33 s) and FF (1.53 s)
slowness stays as recorded-indication lags in M12 for the proxy, labelled **PROXY** (A-W2.4a-11) with the
conflict in the evidence: the round-2 MEASURED 0.81 / 0.218 s were fitted under the misspecified open-loop
model; the DASHlink step responses support the slower values. A 1.5 s first-order lag is not a plausible
fuel-flow transducer response, so the FF entry is described as the recorded FF indication / damping path, not
the meter physics. `tests/integration/test_proxy_word_lags.py` exposes the limitation: on a commanded fuel
step the true fuel flow reaches 63 % about 1.5 s before the recorded FF word (the round-2 0.218 s leaves
< 0.5 s), and the EGT word trails the true T5 by 3-10 s at cruise airflow. Option (b) (slowness in the fuel
control or a gas-path state) is evaluated only if the quick look's B2/B3/B4 show the signature it would fix
(spool responses to fuel too fast against real); with no released heat-capacity value there is no M07
gas-path state.

## W2.4a-2 stage 4: disturbance bank (report: pass 1, then pass 2 with the stage-5 dynamics)

**Structure committed** (AD-46 amended): `fan_face_flow_share` 0 - the fan_face channel is the LP shaft-torque
path (fan efficiency only); `k_eta_fan_face` 0.6 so the declared loading range covers the W2.4a-1 prototype.
`test_signs` follows (N1 and the airflow fall; the flow-share-1 contrast kept). A-W2.4a-10/-18 updated.

**Method: linear spectral synthesis** (`code/st4_tf.py`, `st4_base.py`, `st4_fit.py`).
- Per-channel closed-loop transfer matrices of the 4 words, per 0.0625-Hz sub-band, from single-channel per-unit
  OU injections into the full chain at three governed CAL points (climb, cruise, flight-idle descent: medians
  of the A/T-engaged CAL steady points), 1,500 s each.
- The empty-bank chain on 4 CAL flights (MF1-D order[:4]) gives the input-driven content plus texture on the
  governed in-flight segments (class GOVFLT), with the real record's spectra on the same segments.
- The bank's expected cross-spectrum (per channel: total SD, common share, correlation time; aircraft-common
  factors load every engine) is added and fitted to the statistics: within- and cross-engine fast-band
  correlations and SDs (time domain, as the class statistics) and, per spectral pair, phases and coherences in
  0.19-0.5 and 0.5-1 Hz, the equivalent delay and the band gain (MF1-D estimators): 50 statistics. An EGT-lag
  scale is a
  nuisance with the round-2 prior range.

**Findings (pass 1, the stage-3 configuration).**
1. **Fuel follows the spools only under weak governing.** With a spool-side driver (HP shaft load), the FF
   phase behind N2 at 0.19-0.5 Hz is +87..+91 deg (FF *leads*) at the committed Kp 2 / Ki 1, +2..+16 at Kp 1 /
   Ki 0.5 and -13..-21 (FF lags, as real -24) at Kp 0.5 / Ki 0.25 (`results/stage4/pass1/tf_phases.json`).
   **Both weaker settings limit-cycle at flight idle**: the empty-bank descent point carries an EGT/FF
   oscillation (fast-band EGT power 0.3-0.4 against 5e-4 at Kp 2). The committed gains are the weakest uniform
   governor that is stable at flight idle on this plant; a governing strength scheduled with power would be a
   structural M08 change (coordinator).
2. **The bank cannot fix the timing.** At the committed governor all 12 starts converge to the same optimum
   (rms 2.83 MF1 units against
   3.55 for the empty bank). What remains is dominated by the EGT and FF timing of the *input-driven* content,
   which the bank does not touch:

| Statistic (pooled GOVFLT, n = 4) | real | empty bank | fitted bank |
|---|---|---|---|
| N2->EGT phase 0.19-0.5 Hz [deg] | -94 | +28 | +10 |
| N1->EGT phase [deg] | -34 | +69 | +34 |
| N2->FF phase [deg] | -24 | +29 | +42 |
| FF->EGT phase [deg] | -68 | -8 | -43 |
| r N2-EGT / N1-FF | -0.04 / 0.74 | 0.84 / 0.35 | 0.71 / 0.31 |

   The EGT-lag nuisance sits at its prior bound (tau_ref 1.18 s) at every governor setting; freed to x10 it goes
   to 3.7 s (`st4_fit_wide_tc_diagnostic.json`). This is what sent stage 5 to the dynamics first.
3. Pass-1 bank (committed governor, not adopted): fuel SD 1.7 % (62 % common, tau at the 5 s bound),
   combustor 0.22 %, inlet 0.80 % and HP shaft load 0.46 % (both fully common), LP torque about 0.

**Pass 2 (with the stage-5 dynamics; adopted).** Same method with the stage-5 configuration (identified
autothrottle gains, inertias and word lags; committed governor; EGT lag held at its configured value,
`ST4_STC=fixed`). Empty bank: rms 2.94 (pass 1: 3.55) - stage 5 removed a fifth of the mismatch before any
disturbance. Two fits, both verified with the full chain on the same 4 flights (`results/stage4/verify/`):

| Statistic (median of 4 CAL flights; full chain) | real | empty bank | **pooled fit (adopted)** | median fit |
|---|---|---|---|---|
| B1 N1-N2 / N1-FF / N2-FF | 0.44 / 0.68 / 0.67 | 0.74 / 0.69 / 0.77 | **0.57 / 0.56 / 0.56** | 0.60 / 0.60 / 0.60 |
| B1 N1-EGT / N2-EGT | 0.56 / 0.07 | 0.58 / 0.80 | **0.43 / 0.64** | 0.45 / 0.67 |
| B1 cross-engine N1 / N2 / EGT | 0.80 / 0.79 / 0.66 | 0.89 / 0.89 / 0.81 | **0.65 / 0.78 / 0.56** | 0.58 / 0.68 / 0.48 |
| GOV fast-band SD N1 / N2 [%] | 0.11 / 0.09 | 0.07 / 0.06 | **0.14 / 0.15** | 0.11 / 0.11 |
| GOV fast-band SD EGT [degC] / FF [lb/h] | 0.39 / 3.7 | 0.30 / 2.7 | **0.46 / 4.7** | 0.38 / 3.8 |
| GOV N2->N1 phase 0.19-0.5 / 0.5-1 Hz [deg] | -64 / -94 | -34 / -27 | **-33 / -30** | -32 / -25 |
| GOV N1->EGT phase 0.19-0.5 Hz [deg] | -28 | +33 | **+33** | +36 |
| GOV N2->FF / FF->EGT tau_eq [s] | +0.10 / 0.48 | -0.11 / 0.11 | **-0.11 / 0.22** | -0.13 / 0.31 |
| B2 FF->N2 / N2->N1 / FF->EGT [s] | -0.50 / +0.50 / +0.75 | 0 / 0 / 0 | **0 / +0.25 / 0** | 0 / +0.13 / 0 |
| MF1 joint distance, governed set (battery set) | | 1.84 (1.63) | **1.56 (1.72)** | 1.61 (1.77) |

- **Pooled fit (adopted)**: per channel SD / common share / tau - fuel metering 0.57 % / 1 % / 2.6 s; combustor
  1.21 % / 70 % / 1.6 s; inlet recovery 1.36 % / 54 % / 0.29 s; HP shaft load 1.35 % / 91 % / 0.05 s (lower
  bound); LP shaft torque about 0. The common combustor and inlet loadings sit at their declared maximum (1 %).
  Written to `configs/proxy_dashlink/params/M03/` (`code/st4_adopt.py`; factors 101-110; the W1 bleed/PTO
  placeholders went with their factors). The median-aggregated fit matches the amplitudes but drops the
  cross-engine correlations further; it is kept as a result (`st4_fit_median.json`).
- **What the bank achieves:** amplitudes of the right order (pass 1's W1 bank was 4-5 times too large), lower
  within-engine N1-N2 (0.74 -> 0.57) and N2-EGT (0.80 -> 0.64), cross-engine N2 kept. Best on the governed
  set; on the battery set the empty bank is closer (it is lower on phase).
- **What it cannot do (the open structural gap):** the timing. In the real fast band the words follow N2 -> FF
  (-26 deg) -> N1 (-62 deg) -> EGT (-100 deg); EGT trails N1 by about 0.3 s, almost like a delay (-31 / -60
  deg at 0.3 / 0.75 Hz; a single lag cannot exceed -90 deg against its input). In the model
  (`tf_phases_pass2.json`, climb / cruise) EGT leads N1 for every driver (+12 fuel, +11 combustor, +71 LP
  torque, +77..+81 HP shaft load) except inlet recovery (-30 deg in cruise, near anti-phase in climb); with
  the 1.53 s FF lag the FF word now trails N2 for the fuel-metering and LP-torque drivers (-6..-17 deg) but
  still leads it for combustor, inlet and shaft load (+20..+52 deg). The bank only re-weights these responses,
  and the fit, balancing all statistics, settles on combustor, inlet and shaft load. The LP-torque path is not
  used by the fit. Stage 5's long EGT and FF lags fit the slow step responses but not this fast-band order;
  the synthesis even prefers a shorter EGT lag for the bank part (EGT-lag nuisance at its lower bound when
  free, `st4_fit_stc_free.json`).
- **Reading for the coordinator.** The remaining B1/B2 gap is the fast-band ordering of FF and T5 relative to
  the spools, a structure item, not a parameter one: either the real fuel flow follows the spools (weakly
  governed metering; weaker uniform governing limit-cycles at flight idle, pass 1), or the EGT/FF words carry
  a two-time-scale response (fast part following N1 with about 0.3 s delay, slow part with the 4-6 s step time
  constant), or a combination. Each is a proposed M08 / M12 structure change (decision register), not
  something stage 4 can fit.

Sample: 4 CAL flights (MF1-D order[:4], the stage-2/3 identities); transfers at 3 points x 6 runs x 1,500 s;
fits about 2-7 CPU-min; verification 12 flight runs (about 45 CPU-min).

## W2.4a-2 stage 1: steady identification of the plant levels (report)

**Result.** The W2.4a-1 plant's off-design levels (A-W2.4a-19) are removed. On 10 CAL flights the fit did not
use (MF1-D order[20:30], 12,368 quasi-steady points), against the W2.4a-1 generic plant:

| Regime (verification set) | Fuel, model / real - 1 | N1 error [%] | EGT error [K] |
|---|---|---|---|
| ground idle (3,308 points) | -0.12 -> **+0.04** | +2.4 -> **-1.3** | +152 -> **-26** |
| take-off roll (44; EGT not settled) | -0.22 -> **-0.03** | +3.0 -> **-4.4** | (-58 -> -18) |
| flight idle (1,010) | -0.38 -> **-0.01** | +27.3 -> **+0.3** | +22 -> **+11** |
| part-power descents (438) | -0.45 -> **+0.02** | +9.8 -> **+0.4** (median +5.8) | -104 -> **-2** |
| climb/cruise below 15,000 ft (1,379) | -0.21 -> **-0.01** | +4.6 -> **-1.5** | -67 -> **-4** |
| climb/cruise above 15,000 ft (6,189) | -0.16 -> **-0.02** | +4.1 -> **+1.5** | -73 -> **-4** |

Point-weighted means (`results/stage1/st_relations.md` has the g, h and EGT relations by corrected-speed band,
for the fit and verification sets, before and after). The fit set gives the same picture (no over-fitting
visible). In the replay the fuel no longer sits on the minimum clamp in descents: governed share of the
airborne samples 98 % (W2.4a-1: 75 %).

**What was identified** (`results/stage1/st_fits.json`, evidence lines in `configs/proxy_dashlink/params`):

- **Off-design map modifiers** (A-W2.4a-21, PROXY): each `1 + a (1 - Nc/Nc_des)^k` below design corrected
  speed, 1 at and above it, so the design anchors are untouched. Fan flow (a 1.05, k 1.83), fan speed line (the
  map read at a modified speed; a 0.70, k 1.0), fan efficiency (a 0.97, k 4.0), HPC flow (a 0.78, k 1.08), HPC
  speed line (a 0.54, k 1.09). Reading: the proxy's low-pressure-ratio fan and core compressor have flatter
  flow-speed characteristics than the scaled multistage generic maps. The energy balance at ground idle
  demands it: the real engine burns more fuel and runs about 130 K cooler than the W2.4a-1 plant, so its core
  passes more air.
- **Customer bleed from the record** (A-W2.4a-22): DASHlink records the bleed-valve (BLV), pack (PACK) and
  anti-ice (EAI, WAI, TAI) states. `phalanx.proxy.bleed` turns them into a bleed flow per engine:
  - per running pack 1.31 kg/s in flight and 0.33 kg/s on the ground, shared by the open valves;
  - engine anti-ice 0.24 kg/s;
  - wing and tail anti-ice 1.06 kg/s.

  Bit k is engine k + 1. For EAI this is [MEASURED]: 25 of 25 single-bit switch-ons coincide with that
  engine's start (`results/stage1/st_bits.json`).
- **Tested, set neutral:** HPC efficiency modifier, a Reynolds-number term (the TP-1034 method), and a constant
  power off-take. The identified effects were negligible (0.0015, 0.0125 and 0.4 kW).

**Method and n.**
- **Sample:** quasi-steady 10-s blocks per engine (`code/st_points.py`; thresholds stated before any model
  comparison). The fit set is 12 CAL flights: MF1-D order[:10], plus the first 2 flights from order[40:] with
  wing or tail anti-ice on in flight, selected on the discretes only. That gives 13,215 points (47 take-off
  rolls) in 537 bins. This is the minimal set that covers every bleed state; the verification set is above.
- **Model evaluation:** the M07 steady state at the recorded condition, bleed and N2. Bounded least squares on
  fuel (2 %), N1 (1 %) and EGT (8 K) residuals per bin (`code/st_ident.py`).
- **Penalties:** stall-margin floors (fan 5 % in flight, HPC 5 %) and efficiency ceilings. A modified map must
  stay inside its stall lines and below physical efficiencies.
- **Structures compared:** seven (st_fits.json `candidate_structures`). The two without floors or ceilings
  broke them (fan margin -2.2 %, fan efficiency 1.26).
- **Excluded shape:** exponents below 1 put a kink at design speed, and the SLS operating line did not
  converge.
- **The 5 % in-flight fan floor:** with 0 % it was 2-15 surges per engine per CAL flight in the replay. With
  the floor, the highest-lever trim and the -2 % trigger (limit 3), there were none on the smoke flight.
- **CPU:** about 3 CPU-h over all fits, 10-80 CPU-min each on 4 workers.

**Limits (reported, not hidden).**
1. **The model's N1-N2 relation depends on flight Mach; the real one does not.** At the take-off roll N1 is
   4 % low, in cruise 1.5-2 % high, and at SLS 3-7 % below the MEASURED h between 84 and 96 % N2c. The
   modifiers act through corrected speed only. The candidate fix is a fan speed-line slope (back-pressure
   sensitivity) modifier or a high-bypass fan map.
2. **The in-flight pack draw (1.31 kg/s) is confounded with altitude.** Bleed is on whenever airborne except
   the take-off, and the value is large for a 2-pack regional jet, so it also absorbs altitude effects the plant
   lacks. There is no pack-flow evidence in the base. The ground value (0.33) is set by the taxi-in contrast.
3. **The ground-idle fan operating point sits on the scaled map's stall line**, in its similarity extrapolation
   below the lowest speed line. A 3 % ground floor was not attainable. Two changes follow:
   - the replay trims at the highest lever (`proxy.system.trim_engine`), because the start transient had
     surged two engines 9-10 times;
   - the PROXY surge trigger moves from -1 % to -2 %, the end of its declared range (A-W2.4a-9). Ground-idle
     margins of -1.0 to -1.1 % still fired 6-12 events per engine. Flight margins stay at 3 % or more, so the
     trigger hides nothing in flight, and the record has no surges.

   On the smoke flight: 0 surges.
4. **The EGT is 26 K low at ground idle**, and part-power descent N1 is high (median +6 %).

**Also changed in stage 1.**
- **Demand reference:** the M08 PLA demand is evaluated at the ground reference, M 0 (A-W2.4a-14). Ground
  idle N2c is now 49.6 % against about 50 % recorded; it was about 61 %.
- **Derived settings regenerated:**
  - the M08 ratio-unit tables (`code/st_schedules.py`);
  - the thermocouple reference airflow, 88.09 -> 112.37 kg/s (the M07 airflow at N1c 90 % SLS);
  - SimFlight now records surge counts.
- **Tests:** `tests/integration/test_proxy_steady.py` (CAL steady relations, with the generic plant as the
  negative control) and `tests/unit/test_proxy_bleed.py`.

**Coordinator items.**
- **(i) M08 demand:** add the measured flight-condition terms (cM, cD, cT of the round-2 f map). This is an M08
  change. The PLA-only demand is wrong by cM M (about +60 lb/h) on in-flight manual segments.
- **(ii) Pack draw:** decide whether the in-flight pack draw should be bounded by an external pack-flow value.

**Next: stage 2.** The smoke flight on the identified plant already shows T5 leading N1 on governed segments
(N1->EGT phase +84 deg base, +38 deg bank19, against -19 deg real). Stage 2 measures it at n = 4.

## W2.4a-2 stage 3: gas-path thermal-lag prototype (report; **coordinator decision needed**)

**Prototype** (A-W2.4a-23, behind a flag, **not adopted**):
- **Structure:** a heat-storage node between the LPT exit and the T5 station (exhaust duct, struts, probe
  rakes), with `dX/dt = (T5 - X) / tau`. The station sees `T5 - kappa (T5 - X)`: a first-order lag at
  kappa = 1, a lag-lead below.
- **Steady state:** unity, so the stage-1 levels are untouched.
- **No effect on the cycle:** the storage is downstream of the LPT. N1, N2 and FF are identical with and
  without it (tested).
- **Implementation:** it uses the separate-flow topology's unused mixer-volume state slot, so there is no
  layout change and no edit to shared files. tau = 0 is the default and leaves the kernel bitwise unchanged.
- **Who sees it:** the probes and the controller T5 lanes.
- **Runs:** on the identified plant with the demand pre-map; governed segments; 0 surges in all 22 runs.

**Result** (`results/stage3/`): **with the fuel-dominated driver mix of bank19, a 2-3 s pure lag reproduces
the EGT timing and amplitude; with the W1 bank of base it does not.**

| MF1-D order[:4] (n = 4) | real | bank19 | bank19 + lag 2 s | bank19 + lag 3 s |
|---|---|---|---|---|
| EGT phase vs N1, 0.19-0.5 Hz, governed [deg] | -32 | +38 | **-36** | **-40** |
| same, battery rule [deg] | -30 | +39 | -35 | -39 |
| N1-EGT (governed / battery) | 0.55 / 0.56 | 0.63 / 0.61 | 0.57 / 0.58 | 0.49 / 0.50 |
| N2-EGT (governed / battery) | 0.05 / 0.07 | 0.92 / 0.91 | 0.27 / 0.31 | 0.19 / 0.23 |
| cross-engine EGT (governed) | 0.58 | 0.74 | 0.63 | 0.51 |
| EGT fast-band SD, governed in flight [degC] | 0.39 | 1.94 | 0.53 | **0.40** |
| B2 FF->EGT lag [s] | +0.75 | 0.00 | **+0.75** | **+0.75** |
| FF->EGT tau_eq (phase slope) [s] | 0.40 | 0.04 | 0.15 | 0.13 |

On n = 2 (MF1-D order[:2], 16 runs, `st3`):

| Configuration | EGT phase vs N1 | EGT SD [degC] |
|---|---|---|
| bank19, lag 1 s | -22 deg | 0.84 |
| bank19, lag 2 s, kappa 0.6 (lag-lead) | +20 deg | 0.88 |
| base, lag 2 s | +12 deg | 0.40 |
| base, lag 4 s | +5 deg | 0.29 |

For base, FF->EGT tau_eq is 0.41-0.48 s against 0.41 real. Base's T5 leads by +143 deg at truth level: the W1
bank is spool-side, which pushes T5 towards anti-phase, so no lag brings EGT behind N1 there.

**Reading for the decision.**
1. **The lag is necessary, not sufficient.** It fixes the EGT phase, the EGT amplitude, the B2 lag and N1-EGT,
   but only together with a driver mix in which the fuel follows the spools.
   - With base's W1 bank it cannot work.
   - Even with bank19, FF still leads N2 (N2->FF -0.03 s against +0.13). The FF->EGT phase slope (0.13-0.15 s
     against 0.40) and N2-EGT (0.19-0.27 against 0.05) stay off, because bank19 drives the fuel directly.
   - The driver composition is stage 4 (common spool-side factors), and both have to be judged together.
2. **The magnitude is large for a pure gas-path lag.** A 2-3 s first-order lag on top of the 0.81 s
   thermocouple, with kappa = 1, means the station temperature fully follows a 2-3 s storage node. The
   evidence base has no hot-section or exhaust heat-capacity data for the proxy to support it. A lag-lead with
   a realistic absorbed share (kappa 0.6) does not do it (+20 deg).
3. **Alternative reading: measurement-side lag.** The round-2 MEASURED 0.81 s was identified against static
   maps without the plant's own fast T5 dynamics, so it may understate the effective EGT-indication lag. At
   the recorded level a sensor lag and this station lag are indistinguishable. They differ only for the
   controller T5 lanes, which DASHlink does not record.

**Decision requested (AD-52 item 3):**
- **(a) Adopt the gas-path lag** (tau about 2-3 s, kappa 1) as an M07 structure for the proxy; for the Tejas,
  through the coordinator.
- **(b) Treat it as an EGT-indication lag in M12** and re-identify the thermocouple law with the plant's
  dynamics in the loop (stage 5).
- **(c) Keep it as a flagged prototype** and decide after stage 4 (spool-side common bank), whose driver
  composition changes how much lag is needed.

My recommendation is **(c) then (b)**:
- the lag works only with the right drivers;
- its size has no gas-path evidence;
- the stage-5 transient identification can estimate the lag jointly with the plant.

**Work is stopped here pending the decision.** Stages 4-7 have not started.

## W2.4a-2 stage 2: joint reachability on the identified plant (report)

**Answer: T5 still leads the spools.** On governed segments of 4 CAL flights, the EGT phase relative to N1
(0.19-0.5 Hz) is far from real:

| Configuration | Truth T5 vs N1 | Recorded EGT vs N1 | FF->EGT tau_eq |
|---|---|---|---|
| base | +143 deg | +83 deg | 0.09 s |
| bank19 | +103 deg | +39 deg | 0.04 s |
| bank19 + LP torque (AD-46 amended path) | +113 deg | +50 deg | 0.04 s |
| real | | -34 deg | 0.41 s |

The real EGT lags N1 (MF1-D -27 to -42 deg). AD-52 item 3 therefore applies, and **stage 3 (the gas-path
thermal-lag prototype) follows**.

**Sample.**
- MF1-D order[:4], the W2.4a-1 design flights with the same run identities (common random numbers). n = 4 is
  the W2.4a-1 sample whose medians agreed with 20 flights within 0.06 in correlation and 5 deg in phase.
- 3 configurations x 4 flights; 12 runs, about 40 CPU-min.
- The identified plant of stage 1, before the demand pre-map. The governed segments run under the A/T, so the
  pre-map does not enter them.

`results/stage2/mf1_tables.md` has every statistic (sweeps `st2` and `st2x`); `results/stage2/st2_summary.json`
has the medians, surge counts and limiter shares.

| Statistic (median) | real | W2.4a-1 base | stage-2 base | bank19 | bank19 + LP torque |
|---|---|---|---|---|---|
| B1 N1-N2 / N1-FF / N2-FF / N1-EGT | 0.44 / 0.68 / 0.67 / 0.56 | 0.31 / 0.23 / 0.41 / 0.15 | 0.54 / 0.23 / 0.39 / 0.40 | 0.70 / 0.37 / 0.75 / 0.62 | 0.57 / 0.29 / 0.75 / 0.48 |
| B1 N2-EGT | 0.07 | 0.47 | 0.56 | 0.91 | 0.91 |
| B1 cross-engine N1 / N2 / EGT | 0.80 / 0.79 / 0.66 | 0.66 / 0.40 / 0.68 | 0.50 / 0.39 / 0.60 | 0.77 / 0.75 / 0.77 | 0.69 / 0.75 / 0.76 |
| GOV N2->N1 phase 0.19-0.5 / 0.5-1 Hz [deg] | -53 / -92 | | -56 / -62 | -39 / -31 | -50 / -33 |
| GOV N2->N1 coherence | 0.67 | | 0.34 | 0.89 | 0.55 |
| GOV N2->FF tau_eq [s] | +0.14 | | -0.15 | -0.03 | -0.04 |
| GOV fast-band SD EGT [degC] / FF [lb/h] | 0.38 / 3.6 | | 1.43 / 9.7 | 1.95 / 16.5 | 1.97 / 16.6 |
| taxi share of the airborne samples | 0.135 | | 0.033 | 0.033 | 0.032 |

Reading:
- **Stage 1 moved base towards the targets.** N1-N2 rose from 0.31 to 0.54 and N1-EGT from 0.15 to 0.40. The
  governed share rose from 75 % to 95 %.
- **The timing order is still wrong.** FF leads N2 and T5 leads N1, and the fast-band amplitudes are 4-5 times
  too large: the W1 placeholder bank, stage 4.
- **Taxi share: 3 % against 13 %.** Ground-idle N1 is now about 1 % below the record, at 24 %. The airborne rule
  (all N1 > 25 %) therefore drops the synthetic taxi samples, which changes the battery-rule composition
  (caveat b). B1 on PH 4-6 and on governed segments is unaffected.

**Small re-sweep: which driver puts T5 where.** One disturbance channel at a time, the others off, on
MF1-D order[:2] (12 runs, about 35 CPU-min). Governed segments; phase of T5/EGT relative to N1 at 0.19-0.5 Hz:

| Driver alone | Truth T5 vs N1 | Recorded EGT vs N1 | GOV N1-EGT | GOV N2-EGT | FF->N1 tau_eq [s] |
|---|---|---|---|---|---|
| fuel metering | +98 deg | +34 deg | 0.59 | 0.87 | 0.01 |
| combustor efficiency (x3) | +101 deg | +37 deg | 0.56 | 0.85 | -0.20 |
| fan face / LP (x3, flow share 1) | +149 deg | +86 deg | 0.21 | 0.92 | 0.84 |
| HP shaft load | -173 deg | +124 deg (wrapped) | 0.04 | 0.27 | 0.49 |
| inlet recovery (x3) | -144 deg | +163 deg (wrapped) | 0.19 | 0.70 | 0.06 |
| base, thermocouple tau 1.75 s | +144 deg | +69 deg | 0.33 | 0.41 | 0.38 |
| real (same flights) | | -29 deg | 0.45 | 0.05 | +0.16 |

**Mechanism.**
- **The T5-vs-N1 phase depends on the disturbance type.** W2.1b found the same on the Tejas loop: under shaft
  load, truth T5 lags N1 by 112-117 deg.
- **Fuel-side drivers make T5 lead N1 by about 100 deg at truth level.** At constant speed T5 follows the fuel
  at once, and the spools' later rise in airflow pulls it back, so T5 leads the fuel.
- **Spool-side drivers put T5 near anti-phase with N1** (correlation 0.04-0.19).
- **What the real data requires:**
  - N2 first, FF following it (+0.16 s), N1 after FF (+0.18 s);
  - EGT after FF by the thermocouple lag alone (FF->EGT 0.41-0.56 s, about the 0.81 s probe at 0.3 Hz).

  That means truth T5 roughly in phase with FF and slightly ahead of N1, which no single driver reproduces.
- **The thermocouple lag alone is not enough:** 1.75 s moves base only from +83 to +69 deg.

**Other stage-2 findings.**
- **No surges:** 0 in all 24 runs.
- **Limiter shares** on the 4 flights (base): governor 91-98 %, minimum-fuel clamp 0.7-7.5 %, accel schedule
  0.4-1.4 %, N1 limiter <= 0.05 %, decel <= 0.03 %.
  - The **minimum-fuel clamp** binds in high-altitude idle descents. M08's A/T demand floor is the table's
    idle, now the ground idle (49.6 % N2c), so the A/T can ask for less than the real flight idle. CAL steady
    in-flight fuel never falls below 296 lb/h, against the 253 lb/h clamp. The fix is an A/T floor at the
    pre-mapped idle-stop demand, an M08 change: coordinator item.
- **W2.1b limiter hand-off: not adopted for the proxy.** Limiters other than the governor and the
  minimum-fuel clamp hold the fuel for at most 1.4 % of a CAL flight (accel schedule; N1 limiter <= 0.05 %).
  The proxy keeps the W1.3b law (neutral W2.1b parameters). This is revisited in stage 5 if the A/T-step
  transients show hand-off bumps.
- **Pack-flow bound (stage-1 item ii):** no released pack-flow value for the proxy type was found. A web search
  located ATSB BAe 146 investigation pages describing the pack feed (engines 1-2 to pack 1, engines 3-4 to
  pack 2; APU bleed for the packs during take-off, landing and on the ground). The pages could not be fetched
  for verification, so they are not used as evidence. The identified value stays, with the altitude confound
  recorded (A-W2.4a-22).

# W2.4a-1: MF1 joint reachability study and A2 identification self-test

## Answer (MF1 reachability, development evidence for the coordinator's decision)

**The joint fast-band target is not reachable by the un-identified proxy chain inside the declared ranges.**
Over 36 one-at-a-time and 32 jointly varied configurations (4 flights each; the 20-flight base and targets
below), every *single* B1 fast correlation can be met by some configuration, but no configuration meets the
timing structure at the same time:

- **What is reachable.** The N2->N1 phase on governed segments (base -43 / -67 deg against real -46 / -72 deg
  at H_LP 0.6 s); the within-engine and cross-engine B1 values one at a time (achievable region contains the
  real medians for N1-N2, N2-FF, N2-EGT, all cross-engine pairs, N2->N1 coherence and gain). The best joint
  point (`bank19`, verified on the 20 target flights) reaches B1 N1-N2 0.51 / N1-FF 0.43 / N2-FF 0.71 /
  N1-EGT 0.52 (real 0.43 / 0.69 / 0.63 / 0.56) and cross-engine N1 0.79 (real 0.82); its N1-N2 match is a
  flight-phase composition result (0.70 on PH 4-6 against 0.37, 0.25 on taxi against 0.48).
- **How it gets there, and why that is the wrong mechanism.** Every configuration that brings the FF and EGT
  pairs up does it by making **fuel** an aircraft-common driver (`bank19`: common fuel-metering SD 1.6 %): FF
  and EGT then *lead* the spools (governed segments, n = 20: N2->FF tau_eq -0.04 s against +0.11, FF->EGT
  0.04 s against 0.54, EGT leads N1 by 22 deg against a 42 deg lag; FF fast-band amplitude 10.3 lb/h against
  4.0; N2-EGT 0.86 against 0.07). Real data has the opposite order (MF1-D): N2 first, FF 0.16 s later, N1
  0.18 s after FF, EGT 0.25 s after N1.
- **What is not reachable at all** (outside the achievable region of every one-at-a-time, joint-design and
  prototype configuration, 77 in all): EGT lagging N1 (the EGT phase relative to N1 is at least +15 deg on the
  battery rule, with the 1.75 s thermocouple sensitivity, and at least -15 deg on governed segments, at one
  joint-design point, against -30 / -45 deg); FF->EGT tau_eq on the battery rule (max 0.24 s against 0.54 s;
  on governed segments one point reaches 0.46 s against 0.47 s, with EGT still leading N1); the EGT
  fast-band amplitude (min 0.65 degC against 0.42); N1-FF on every sample set (max 0.47 on the battery rule,
  0.49 on governed segments, 0.56 on PH 4-6, against 0.68 / 0.65 / 0.62); and the B2 lags FF->N2 -0.50 s,
  FF->N1 0.00 s, FF->EGT +0.75 s. The 20-flight verification of the two best joint points confirms each of
  these.
- **Mechanism attribution** (OAT and regression, below). The LP rotor (H_LP) sets the N2->N1 phase as the
  coordinator's framing expected: the fan lag is reachable and is the primary mechanism for low N1-N2. The
  failure is on the **gas-path side**: in every configuration the model's T5 responds to fuel and combustion
  ahead of the spools (truth-level T5 leads N1 by 120 deg in base), so EGT cannot lag N1; shaft-load
  (spool-side) disturbances, which give the right FF order, drive T5 *against* the spools (EGT phase +130 to
  +160 deg). The fan-face path (AD-46) only lowers N1-FF (the E1 failure mode) and does not help.
- **Plant caveat (A-W2.4a-19).** The un-identified plant runs about 40 % low on part-power fuel, 100-140 K low
  on EGT and ram-drives the LP spool at flight idle, so in descents the fuel sits on its minimum clamp (24-25 %
  of airborne samples; excluded by the governed masks). These level errors change the local gains that set
  the fast-band timing (for example the T5 response to fuel at constant speed), so the unreachable items above
  are **conditional on the W2.4a-2 steady identification**.

## Prototypes behind flags and sensitivities (around `bank19`, n = 4; not adopted)

| Variant | N1-N2 | N1-FF | N1-EGT | N2-EGT | N2->N1 phase [deg] | coherence | N1->EGT phase [deg] | EGT SD [degC] |
|---|---|---|---|---|---|---|---|---|
| real (same flights, governed) | 0.43 | 0.64 | 0.59 | 0.11 | -44 / -71 | 0.68 | -44 | 0.42 |
| `bank19` | 0.52 | 0.44 | 0.53 | 0.86 | -28 / -32 | 0.89 | +21 | 1.45 |
| + word-slot skew N1 0.15 s (PROTOTYPE) | 0.32 | 0.17 | 0.39 | 0.86 | **-45 / -67** | 0.89 | +38 | 1.45 |
| + thermocouple tau 1.2 s (sensitivity; MEASURED 0.81 s) | 0.52 | 0.44 | 0.56 | 0.84 | -28 / -32 | 0.89 | +13 | 1.05 |
| + thermocouple tau 1.75 s (Tejas assumption) | 0.52 | 0.44 | 0.56 | 0.80 | -28 / -32 | 0.89 | +6 | 0.76 |
| + fan_face 1 % SD, AD-46 (flow + efficiency) | 0.36 | 0.23 | 0.46 | 0.85 | -47 / -43 | 0.44 | +33 | 1.49 |
| + fan_face 1 % SD, efficiency only, k_eta 0.2 (PROTOTYPE) | 0.52 | 0.44 | 0.53 | 0.86 | -28 / -32 | 0.89 | +21 | 1.45 |
| + gov_kp 1.0 (bottom of the Kp window) | 0.56 | 0.48 | 0.56 | 0.87 | -28 / -32 | 0.91 | +20 | 1.54 |
| + LP shaft torque: fan_face efficiency-only, k_eta 0.6, fan SD 2 % (PROTOTYPE, about 1.2 % torque SD) | **0.43** | **0.41** | 0.46 | 0.86 | -34 / -33 | 0.53 | +29 | 1.46 |

- The **skew** reproduces the real N2->N1 phase pattern in both bands on top of a fuel-driven mix, at the cost of
  the N1 correlations: it is a candidate explanation of the high-band phase, not of the correlations.
- A **longer thermocouple lag** moves EGT towards lagging N1 (+21 -> +6 deg at 1.75 s) and brings the EGT
  amplitude down, but even the Tejas value does not reach the real -44 deg, and the proxy's lag is MEASURED
  (0.81 s, round 2). The EGT problem is upstream of the sensor: T5's fast response in the plant.
- The **AD-46 fan_face path** at a size that matters reproduces the E1 failure mode (N1-FF 0.44 -> 0.23,
  coherence 0.89 -> 0.44) and only moves the low-band phase. Its efficiency-only variant (the second LP path)
  does nothing at k_eta 0.2, but at a meaningful size (an LP shaft-torque disturbance of about 1.2 % SD) it
  **lowers N1-N2 to the real 0.43 while keeping N1-FF (0.44 -> 0.41)**: the LP-specific input MF1-D sizes at
  about a quarter of N1's fast-band power is better represented as LP torque than as the AD-46 flow-capacity
  path. It does not touch the EGT problem.

## Coordinator caveats (MF1-D)

- **(a) Word-slot skew.** M13's DASHlink texture samples every ACMS word at the same instant: it does **not**
  model per-channel sample-time offsets within the frame (`acquisition.config`: `slot_phase_ns` only places
  analog slip windows). A pure delay of the N1 word (PROTOTYPE `word_delay_s`) adds about -11 deg (0.19-0.5
  Hz) and -22 deg (0.5-1 Hz) of N2->N1 phase and +0.1 s of tau_eq per 0.1 s, lowers r(N1,N2) by about 0.08 and
  r(N1,FF) by about 0.12 per 0.1 s, and leaves the coherence unchanged. So the 0.15 s pure-delay part of the real
  phase could be skew: with 0.15 s of skew the LP lag needed for the 0.19-0.5 Hz phase is smaller (H_LP about
  0.4 s), and the 0.5-1 Hz phase (-90 to -97 deg, which a first-order LP lag cannot reach: it saturates near
  -60 to -76 deg) becomes reachable. Skew cannot be separated from a fan pure delay with these data.
- **(b) Taxi composition.** All runs are whole flights (taxi-out to taxi-in). The airborne rule admits 12.5 %
  taxi samples in the real records and 16 % in the synthetic ones (the synthetic ground idle runs at about 35 %
  N1 against 26 % recorded, because the PLA-only demand omits the MEASURED Mach term of the fuel-control law:
  A-W2.4a-19). B1 is also reported on PH 4-6 (FLT) and on the paired governed segments (GOV). For base the
  conclusions are the same on all three. For the fuel-driven frontier point they are not: `bank19`'s
  battery-rule N1-N2 (0.51 against 0.43) is 0.70 on PH 4-6 (real 0.37) and 0.25 on taxi (real 0.48), so the
  battery rule's taxi share hides an in-flight N1-N2 that is too high (verification, below).
- **(c) Phase diagnostics.** N2->N1, N1->EGT, N2->EGT, N2->FF, FF->N1 and FF->EGT phase, gain, coherence and
  tau_eq per band are reported next to the battery for every configuration (`results/mf1_tables.md`).

## Reading against MF1-D

MF1-D's phase-dominance finding holds on the model side: with the LP rotor at H_LP 0.6-0.85 s the model's
low N1-N2 is mainly phase (base: 1 - r_lag = 0.43 of the 0.69 loss, a phase share of 0.62 against the real
0.91; the rest is the model's low coherence), and the fan_face path is not needed for it. MF1-D's second
point (aircraft-common driving beyond the lever) is partly reachable: common factors raise the cross-engine
correlations to the real 0.8, but the common driver that reproduces the real *order* (N2 first, fuel
following) is a spool-side one, and in this plant spool-side drivers put EGT against the spools. MF1-D's item
4 (EGT must follow N1 closely) is the unreachable part.

## Joint design (32 configurations x 4 flights) and verification

Latin hypercube over the disturbance bank (per engine channel: SD log-uniform from 1/200 of the declared
maximum to the maximum, common share 0-1, correlation time 0.1-3 s), H_LP 0.3-1.2 s, k_eta_fan_face 0-0.6,
gov_kp 1-4, A/T kp/ki, and the N1 word-skew prototype 0-0.2 s (`code/configs.py: bank`, keyed design stream).
Full tables: `results/mf1_tables.md` (achievable region, Pareto fronts on four objective groups, regression
attribution).

- **Pareto fronts.** On the governed objective set the front holds 15 of the 32 configurations; the lowest
  joint distances are 1.95 (`bank19`), 2.01 (`bank27`) and 2.06 (`bank28`) scale units, against 3.0 for base
  on the same 4 flights (`results/base_on_design_flights.json`; 1 unit = 0.1 in correlation, 20 deg in phase,
  x1.35 in amplitude). Every front point trades the within-engine correlations against the phase group: the
  points with high FF/EGT correlations are fuel-driven (wrong order), the points with the right FF order are
  spool-driven (EGT against the spools).
- **Regression attribution** (R^2 0.69-0.94): the N1->EGT phase moves +39 deg per SD of shaft-load SD and -31
  deg per SD of fuel-metering SD, +15 deg per SD of H_LP; the N2->N1 phase -14 deg (low band) per SD of H_LP,
  -26 deg (high band) per SD of skew; coherence +0.11 per SD of shaft-load SD; cross-engine N2 -0.13 per SD of
  shaft-load SD (+0.09 per SD of its common share); N1-FF -0.14 per SD of fan-face SD.
- **Verification on the 20 target flights** (`bank19`, `bank27` and base; MF1-D order[:20], the identities
  of the targets; sweep `verify` in `results/mf1_tables.md`). The ranking holds: joint distance on governed
  segments 1.99 (`bank19`), 2.20 (`bank27`), 3.28 (base); on the battery rule 2.01 / 2.58 / 3.05. `bank19`'s
  within-engine correlations move by at most 0.06 and its phases by at most 5 deg from the 4-flight values.
  The cross-engine N1 does not hold: on governed segments 0.82 -> 0.74 for `bank19` (real 0.84,
  flight-bootstrap CI [0.77, 0.86]) and 0.68 -> 0.54 for `bank27`, so the 4-flight design overstates the
  cross-engine agreement of the fuel-driven points.
- **Every unreachable item stays unreachable at n = 20** (`bank19` / `bank27` / real, governed segments):
  N1->EGT phase +22 / +14 / -42 deg; FF->EGT tau_eq 0.04 / 0.06 / 0.54 s; N2->FF tau_eq -0.04 / -0.05 /
  +0.11 s; N2-EGT 0.86 / 0.77 / 0.07; N1-FF 0.46 / 0.36 / 0.68; EGT fast-band SD 1.41 / 0.80 / 0.41 degC;
  and on the battery rule B2 FF->N2, FF->N1, N2->N1, FF->EGT 0.00, +0.25, +0.25, 0.00 s / all +0.25 s /
  -0.50, 0.00, +0.50, +0.75 s. The N2->N1 phase on governed segments is further from real at both points
  (-28 / -32 and -12 / -19 deg) than at base (-43 / -67 deg against -46 / -72): the fuel-common driver moves
  N1 and N2 together.
- **Flight-phase composition at the frontier (caveat b).** On PH 4-6 `bank19` has N1-N2 0.70, N1-FF 0.51,
  N2-FF 0.75, N1-EGT 0.65 (real 0.37 / 0.57 / 0.68 / 0.52; n = 20). In the joint design the 6 of 32
  configurations that match N1-N2 on PH 4-6 (within 0.06) have N1-FF at most 0.48 and N1-EGT at most 0.19
  there (real 0.62 / 0.54 on the same 4 flights): no configuration meets the in-flight N1-N2 and the FF/EGT
  pairs together.

## Proposed decisions and items for the coordinator (not adopted here)

| Id | Proposal | Evidence | What would change it |
|---|---|---|---|
| P-W24a-1 | AD-52 item 1 holds: the LP rotor (fan lag) is the primary mechanism for low fast-band N1-N2 and is reachable (governed-segment phase -43/-67 deg against -46/-72 deg at H_LP 0.6 s). Keep word-slot skew of the N1 word open as a recorder candidate for the 0.15 s pure-delay part (it reproduces the 0.5-1 Hz phase, which a first-order LP lag cannot) | OAT, bank regression, proto | A recorder timing measurement; W2.4a-2 transient identification of H_LP |
| P-W24a-2 | The secondary LP-specific input should be an **LP shaft-torque path** (efficiency-only `fan_face`, or a sixth engine channel), sized to MF1-D's N1-specific residual and about half aircraft-common, **not** AD-46's flow-capacity path (which reproduces the E1 failure: N1-FF collapses) | proto `bank19+lptorque` vs `+fan0.01+share1.0` | W2.4a-2 identification of the residual on CAL |
| P-W24a-3 | The joint target fails on the **gas-path side**: the plant's T5 leads the spools in every configuration, so EGT cannot lag N1. First remove the plant level errors (A-W2.4a-19: part-power fuel/EGT, ram-driven LP spool, flight-idle demand) in W2.4a-2 steady identification; if T5 still leads, prototype a gas-path thermal lag (hot-section / probe-boss heat capacity) in M07 as a structural candidate | bank region (N1->EGT phase min -15 deg vs -45), proto TC-lag sensitivity | The EGT phase after steady identification |
| P-W24a-4 | The disturbance bank's W1 placeholder composition (fuel-metering and combustor-efficiency dominated, per-unit shaft load) gives the wrong order (FF and T5 lead the spools). The real fast band is spool-driven and mostly aircraft-common; W2.4a-2 should identify the bank with common spool-side factors, jointly with P-W24a-3 | base vs bank, MF1-D | W2.4a-2 PSD/coherence identification |
| P-W24a-5 | Identification staging for W2.4a-2: plant and sensor dynamics on A/T segments, governor gains on manual lever segments (taxi, final approach); the six-parameter joint fit on A/T data is ill-conditioned | A2 run 1, ladder, split | |
| P-W24a-6 | M12 sources should accept complex truth rows (comparisons on the real part in `interp_table`, `total_pressure`, the `_tau` flux floor; bitwise unchanged for real rows) so AD-22's complex step passes the closed loop | A-W2.4a-20 | Owner of M12 |
| P-W24a-7 | Multi-engine CIR: contract v0 has no unit identity for engine instances; `acquisition.record.to_cir` refuses them for now | U3 | Contract change (coordinator) |

## The proxy chain the study runs

`phalanx.proxy` (W2.4a-1): recorded inputs drive replay producers (scenario phase, environment with the M03
disturbance bank, pilot lever and A/T state, airframe flight condition, utility/health constants: U4), M08
governs four `separate_fixed` M07 engines (AD-43) with the A/T outer loop, M12 measures them (per-engine
lanes: U3), and M13 delivers the FADEC lanes in the loop and records the four DASHlink words per engine with
the DASHlink texture (double quantiser on the native grid with the MEASURED offsets, recorder lattice,
idiosyncratic noise, gates, freezes) on the ACMS clock. The closed loop runs in one compiled block
(`proxy.loop.ProxyLoopGroup`, bitwise equal to the module System). A whole CAL flight (about 80 min, 1.2 M
truth steps) takes about 2 min on one core.

Every run is a whole recorded flight with all engines running (`proxy.inputs.running_window`): taxi-out,
take-off, climb, cruise, descent, approach, taxi-in, so the battery's airborne rule admits the same kinds of
samples as in the real record (MF1-D D2).

## Statistics

`code/mf1stats.py` computes, for the real record and for the synthetic record of the same window, with the
same estimators:
- **B1** fast-band correlations (`phalanx.validation.battery.stats.b1_stats`): within-engine pairs and
  cross-engine pairs (engine 1 and engine means);
- **B2** lead-lag (`b2_stats`);
- **classes** (MF1-D): FLT (PH 4-6), CLB, CRZ, DES, TAXI, AT_FLT, and the paired **GOV** classes (samples at
  which every synthetic engine's fuel is on the N2 governor; the same mask is applied to the real record);
- **spectral** (MF1-D `spectral.py`, unchanged): N2->N1, FF->N1, N2->FF, N1->EGT, N2->EGT, FF->EGT phase,
  gain and coherence per band, tau_eq, r_lag, coherent fraction;
- **fast-band amplitude** (SD of the fast-band signal per family);
- three levels for synthetic records: truth (M07 at the sample instants), sensor (M12 output) and recorded
  (M13 words), which separates the M12 sensor dynamics from the M13 texture.

## Targets, base configuration and texture shifts (n = 20 flights)

`results/mf1_tables.md` (first table) has every statistic. Real = 687-CAL engine-1 medians over the 20 MF1-D
flights (flight-bootstrap 95 % CI), on the same whole-flight windows as the synthetic runs. **Estimator check:**
on these flights the study's pipeline reproduces MF1-D's published values (B1 N1-N2 0.43 [0.38, 0.47];
N2->N1 phase -57 deg / -97 deg, coherence 0.74, tau_eq 0.33 s; N1->EGT phase -27 deg, tau_eq 0.24 s; FF->EGT
0.54 s). N1-FF 0.69, N2-FF 0.63 and N1-EGT 0.56 differ from MF1-D's whole-file values by at most 0.03 (the
windows exclude engine start and shut-down).

| Statistic (fast band) | Real | Base recorded | Base sensor | Base truth |
|---|---|---|---|---|
| B1 N1-N2 / N1-FF / N2-FF / N1-EGT | 0.43 / 0.69 / 0.63 / 0.56 | 0.31 / 0.15 / 0.35 / 0.12 | 0.32 / 0.16 / 0.38 / 0.13 | 0.32 / -0.04 / 0.20 / -0.12 |
| B1 N2-EGT | 0.07 | 0.40 | 0.41 | -0.16 |
| B1 cross-engine N1 / N2 / EGT | 0.82 / 0.78 / 0.65 | 0.52 / 0.33 / 0.60 | 0.54 / 0.34 / 0.63 | 0.54 / 0.34 / 0.59 |
| N2->N1 phase 0.19-0.5 / 0.5-1 Hz [deg] | -57 / -97 | -50 / -65 | -50 / -63 | -50 / -63 |
| N2->N1 gain / coherence (0.19-0.5 Hz) | 1.04 / 0.74 | 0.65 / 0.29 | 0.65 / 0.30 | 0.65 / 0.30 |
| N1->EGT phase 0.19-0.5 Hz [deg] | -27 | +63 | +62 | +123 |
| tau_eq N2->FF / FF->N1 / FF->EGT [s] | +0.16 / +0.18 / +0.54 | -0.11 / +0.04 / +0.06 | -0.12 / +0.04 / +0.05 | -0.23 / +0.18 / +0.09 |
| B2 FF->N2 / FF->N1 / N2->N1 / FF->EGT [s] | -0.50 / 0.00 / +0.50 / +0.75 | +0.25 / +0.50 / +0.50 / +0.25 | | |
| Governed in-flight fast-band SD N1 / N2 [%], EGT [degC], FF [lb/h] | 0.12 / 0.10 / 0.41 / 4.0 | 0.08 / 0.08 / 0.97 / 5.1 | 0.08 / 0.08 / 0.94 / 4.6 | 0.08 / 0.08 / 2.68 / 5.9 |

**Governed segments** (GOV: samples at which every synthetic engine's fuel is on the N2 governor, 75 % of the
airborne samples in both records; the rest is mostly descent on the minimum-fuel clamp, A-W2.4a-19):

| Statistic | Real | Base recorded |
|---|---|---|
| N1-N2 / N1-FF / N2-FF / N1-EGT / N2-EGT | 0.47 / 0.68 / 0.61 / 0.59 / 0.07 | 0.37 / 0.17 / 0.37 / 0.12 / 0.34 |
| cross-engine N1 / N2 / EGT | 0.84 / 0.78 / 0.65 | 0.45 / 0.28 / 0.53 |
| N2->N1 phase 0.19-0.5 / 0.5-1 Hz [deg]; gain; coherence | -46 / -72; 1.14; 0.61 | -43 / -67; 0.64; 0.44 |
| N1->EGT phase [deg]; tau_eq N2->FF [s] | -42; +0.11 | +86; -0.34 |

Reading:
- **On governed segments the base N2->N1 phase is already close to the real one** (-43 deg / -67 deg against
  -46 deg / -72 deg) with the committed H_LP 0.6 s. The gap is the coherence and the gain: N1 carries
  independent motion and N2 carries motion that does not reach N1.
- **The FF and EGT pairs are wrong in sign of timing**, not only in size: at truth level FF *leads* N2
  (tau_eq -0.23 s, real +0.16 s: FF follows N2) and T5 leads N1 by 123 deg (real EGT lags N1). The committed
  bank's fuel-metering and combustor-efficiency factors (W1 placeholders) drive fuel and gas temperature
  directly, ahead of the spools; the real fast band is spool-driven, with fuel following N2 (ratio-unit
  metering) and EGT following fuel through the thermocouple. The model's truth-level EGT fast band is 6.5x the
  real recorded amplitude.
- **Texture shifts.** M12 sensor dynamics move the FF pairs up by 0.16-0.20 (the 0.218 s meter lag aligns FF
  with the spools) and the EGT pairs by 0.25 (the 0.81 s thermocouple lag), and divide the EGT amplitude by
  2.8. The M13 DASHlink texture lowers the correlations by only 0.01-0.04 (MF1-D: 0.04-0.12 on the FF/EGT pairs
  in real data, because the real FF/EGT fast bands are smaller relative to the 8 lb/h and 0.5 degC lattices)
  and leaves N1-N2 unchanged, as in the data.

## One-at-a-time attribution (36 configurations, n = 4 flights)

Changes from base (recorded level, B1 on the battery rule); full table `results/mf1_tables.md`.

| Mechanism (declared range) | What it moves |
|---|---|
| LP rotor H_LP 0.2 -> 2.0 s (A-W2.4a-6) | **The N2->N1 phase**: -19 / -52 / -69 / -77 deg (0.19-0.5 Hz) for 0.2 / 0.6 / 1.2 / 2.0 s, and r(N1,N2) 0.44 -> 0.11. The 0.5-1 Hz phase saturates near -60 to -76 deg (a first-order LP lag), short of the real -97 deg |
| Word-slot skew on N1 (PROTOTYPE) | Pure delay: per +0.1 s, about -11 deg (0.19-0.5 Hz), -22 deg (0.5-1 Hz), +0.1 s tau_eq, -0.08 r(N1,N2), -0.12 r(N1,FF); coherence unchanged |
| Fuel-metering factors x0 / x3 | x3 raises every positive pair (N1-FF 0.39, N1-EGT 0.38, N1-N2 0.45) by making fuel the common driver, with the wrong order (FF and EGT lead); x0 puts FF behind N2 (tau_eq +0.05 s) |
| Shaft-load factors x0 / x3 | x0: N2-FF 0.65, cross-engine N2 0.72 (the per-unit shaft load is what decorrelates the engines' N2); x3: coherence 0.57 (the only knob that raises it), N1-N2 0.53, but N1-EGT -0.17 and cross-engine N2 0.07 |
| Per-unit factors x0 (common only) | Cross-engine N1/N2/EGT 0.95 / 0.87 / 0.87 (too high), N2-FF 0.64, N2-EGT 0.73 |
| Fan-face loading x3 | The E1 failure mode: N1-FF -0.08, N1-N2 0.15, cross-engine N1 0.34 |
| k_eta_fan_face 0 -> 0.6 | Negligible at the committed fan loading (0.002 common / 0.004 per unit) |
| Governor Kp 1 -> 4, Ki 0.3 -> 3, PS3 tau 0 -> 0.2 s | +-0.05 to +-0.1 on the correlations; Kp up lowers N1-FF and N2-FF |
| A/T gains (0.1/0.05/0.05 -> 0.5/0.3/0.2) | Slow A/T removes the common N1 command response: cross-engine N1 0.66 -> 0.28 |

No single knob moves the coherence to the real 0.74 or brings the FF/EGT pairs above 0.4 with the right
timing; the joint design below tests combinations.

## A2: identification self-test (synthetic proxy flights only)

Machinery: `src/phalanx/proxy/ident.py` (deterministic closed-loop model = the proxy chain's kernels without
lane texture and disturbances; transient-weighted output error; prediction error with an AR innovations
model; direct method; residual spectra; difference Jacobians, a reported deviation from AD-22, A-W2.4a-20).
Ground truth: six parameters moved off nominal (H_LP x1.4, H_HP x0.8, gov_kp x1.3, gov_ki x0.7, tau_egt
0.81 -> 1.10 s, tau_ff 0.218 -> 0.30 s). Data: the full textured chain on a 120 s synthetic cruise with five
A/T steps (`code/a2_selftest.py`, criteria stated in its docstring before running).

**Run 1** (`results/a2_selftest.json`; committed bank at full scale; criteria stated before running): **FAIL**.

| Parameter | OE (indirect) / truth | GN SE / truth | Direct method / truth |
|---|---|---|---|
| i_lp (H_LP) | 1.06 | 0.02 | 0.36 |
| i_hp (H_HP) | 0.94 | 0.05 | 0.07 |
| gov_kp | 0.56 | 0.07 | n/a |
| gov_ki | 1.59 | 0.20 | n/a |
| tau_egt | 1.17 | 0.03 | 0.38 |
| tau_ff | 1.24 | 0.06 | n/a |

- The OE recovers the rotor inertias within 6 % but not the governor gains or the sensor time constants. The
  cost falls only from 125,500 to 104,000: the committed placeholder bank's disturbance response dominates the
  residual, and the Gauss-Newton SEs (white-residual assumption) understate the error by several times.
- The **direct method** (plant driven by the measured fuel flow) is grossly biased (inertias x0.36 and x0.07,
  EGT tau x0.38). This is the closed-loop bias of round-2 REPORT §8 H-c 2: W2.4a-2 must use the indirect
  method.
- The residual-coherence controls failed because the self-test's estimator used 2 Welch segments of 256 samples
  on 480 samples, which biases the coherence of independent signals to about 0.5 (committed 0.53, unit-only
  0.54). `ident.residual_spectra` now refuses fewer than 8 segments.

**Follow-ups added after run 1** (each with criteria stated before running; deviations from the plan):

1. **Coherence controls with the corrected estimator** (`results/a2_coherence.json`; 14 segments of 64):
   per-unit-only bank N2 residual coherence **0.085 (< 0.2: pass)**; committed bank 0.07; aircraft-common-only
   bank **0.44 (> 0.8: fail)**. The estimator separates the two banks (0.44 against 0.085; EGT 0.58 against
   0.07; FF 0.61 against 0.09), but at the committed common loadings the common response is of the order of
   the per-engine texture noise, so the registered 0.8 threshold was not a property of the estimator alone.
2. **Signal-to-disturbance ladder, six parameters** (`results/a2_ladder.json`): **fail** at both rungs.
   Estimate / truth for (i_lp, i_hp, gov_kp, gov_ki, tau_egt, tau_ff): texture only 0.96, 0.86, 0.77, 0.69,
   0.93, 0.89; bank x0.25 0.99, 0.91, 0.74, 0.89, 1.00, 0.99; bank x0.25 with the AR(2) innovations model
   0.98, 0.85, 0.75, 0.86, 0.94, 0.93. On the texture-only data the fit reaches a *lower* cost than the truth
   (2,746 against 2,886): the identification model omits the M13 lane texture inside the loop, and the
   governor gains are the weakest directions (Jacobian condition 22; the gain columns have the smallest
   norms), so a small model mismatch moves them by 25-30 %.
3. **Identifiability split** (`results/a2_subset.json`): with the governor gains held, the plant and sensor
   parameters are recovered **within 5 % at texture only** (i_lp 1.004, i_hp 0.96, tau_egt 0.975, tau_ff
   0.971) **and within 10 % with a quarter of the committed bank** (1.026, 0.997, 1.038, 1.051): **pass**.
   With the plant held, the **governor gains are recovered on a manual lever-step flight** (A/T off, five lever
   steps of 3-6 deg): gov_kp 1.021 / gov_ki 0.942 at texture only, 0.952 / 1.043 with a quarter of the bank.

**A2 reading:** the machinery (model, weighting, difference Jacobians, LM, PEM option, residual spectra) is
correct where the problem is well posed: the inertias and sensor lags are recovered from A/T steps, the
governor gains from lever steps, and the indirect method is unbiased where the direct method is grossly biased.
A joint six-parameter fit on A/T-step data alone is ill-conditioned (the A/T outer loop hides the inner
governor) and absorbs the identification model's missing lane texture into the gains. For W2.4a-2: identify
the gains on manual lever segments (on CAL these are taxi and final approach, MF1-D D1) and the plant on A/T
segments, staged, and consider the lane quantiser in the identification model. A2 ("recovers known
parameters on a synthetic proxy flight") is **met per parameter group under the right excitation, and not met
for the joint six-parameter fit on one A/T flight** (registered run 1 and the ladder failed).

## Sample sizes (RULES.md rule 1)

| Stage | n | Justification |
|---|---|---|
| Smoke | 1 flight, base | format, ranges, run time (2 min per 80-min flight on one core) |
| Targets + base | 20 flights (MF1-D order[:20]) | the MF1-D n rule (bootstrap CI half-width <= 0.05 on the medians), so the targets have MF1-D's precision; the estimator check against MF1-D's published values uses the same flights |
| One-at-a-time attribution | 4 flights x 36 configurations | the smallest flight set whose medians separate the mechanism effects (attribution, not a test); the same 4 flights and identities for every configuration (common random numbers) |
| Joint design (bank) | 4 flights x 32 configurations | a 32-point Latin hypercube over 21 dimensions (reduced from 48 for machine load) locates the achievable region and its Pareto front |
| Prototypes | 4 flights x 9 configurations | the design flights, so each variant is compared with `bank19` under common random numbers |
| Verification | 20 flights x 2 configurations (`bank19`, `bank27`) | the targets' flights and n, so the two best joint points are compared with the real medians at the targets' precision (base is the n = 20 base run) |
| A2 self-test | one 120 s synthetic flight per ladder rung | the smallest window with accel and decel steps for every identified parameter |

## Data hygiene

- **Flights:** Tail 687 archive-1 **CAL** only (`analysis/settling_experiment/results/splits.csv`). The flight
  sample is a prefix of the MF1-D fixed order (`analysis/mf1_lp_structure/results/flight_order.json`, drawn
  with `phalanx.core.rng` from file names before any data was read), so the targets are on the flights MF1-D
  characterised.
- **Inputs only drive the chain:** PLA x4, pressure altitude, Mach, TAT, PH, ATEN and N1C
  (`phalanx.proxy.inputs`). Real engine outputs are read only to compute the targets with the same
  estimators.
- **Guards:** every path passes `phalanx.proxy.guard.check_path` (A3) and `code/common.py: guarded` (CAL only,
  no Tail 652). The reserved archive is never named outside `src/phalanx/proxy/guard.py` (static test).
- **Untrusted files:** MAT files are parsed by `scipy.io.loadmat` through the M20 adapter; Python runs with
  `-I`; paths are arguments.

## Commands

From the worktree root, `PY=<main repo>/.venv-build/bin/python`, `M=<.../dashlink_tail687/raw/mat>`:

```bash
R=runs/proxy_quicklook
$PY -I analysis/proxy_quicklook/code/sweep.py $M base 20 $R/v2 10     # targets + base, n = 20
$PY -I analysis/proxy_quicklook/code/sweep.py $M oat 4 $R/n4 10       # one-at-a-time, n = 4
$PY -I analysis/proxy_quicklook/code/sweep.py $M bank 4 $R/v2 10      # joint design, n = 4
$PY -I analysis/proxy_quicklook/code/sweep.py $M proto 4 $R/v2 10     # prototypes (results/proto_base.json)
$PY -I analysis/proxy_quicklook/code/sweep.py $M verify 20 $R/v2 10   # verification (results/verify_configs.json)
$PY -I analysis/proxy_quicklook/code/aggregate.py $R/agg_v2base.json $R/v2/base.jsonl
$PY -I analysis/proxy_quicklook/code/aggregate.py $R/oat.json $R/n4/oat.jsonl        # likewise bank, proto
$PY -I analysis/proxy_quicklook/code/aggregate.py $R/verify.json $R/v2/base.jsonl $R/v2/verify.jsonl
$PY -I analysis/proxy_quicklook/code/report.py analysis/proxy_quicklook/results $R/agg_v2base.json \
    $R/oat.json $R/bank.json $R/proto.json $R/verify.json
$PY -I analysis/proxy_quicklook/code/a2_selftest.py analysis/proxy_quicklook/results/a2_selftest.json
```

Run rows go to the git-ignored `runs/proxy_quicklook/`; aggregated results are committed in `results/`. The
one-at-a-time sweep ran before `simulate_flight` recorded the per-sample fuel regulator, so it has no governed
(GOV) statistics; every other sweep has them.

W2.4a-2 stage 1 (`S=runs/proxy_quicklook/st`; `F` = the round-2 frozen `ma_readable.json`):

```bash
$PY -I analysis/proxy_quicklook/code/st_points.py $M 0 10 $S/points_F.json 2    # fit set (12 CAL flights)
$PY -I analysis/proxy_quicklook/code/st_points.py $M 20 10 $S/points_V.json     # verification set
$PY -I analysis/proxy_quicklook/code/st_bits.py $M 0 10 $S/bits.json            # EAI bit -> engine
ST_MAX_NFEV=15 $PY -I analysis/proxy_quicklook/code/st_ident.py fit $S/points_F.json $S/fit.json 4 \
    <free list> <start.json>
$PY -I analysis/proxy_quicklook/code/st_ident.py assess $S/points_V.json <fit.json|none> $S/V.json 4
$PY -I analysis/proxy_quicklook/code/st_adopt.py <adopt.json> <result path> configs/proxy_dashlink/params
$PY -I analysis/proxy_quicklook/code/st_schedules.py $F configs/proxy_dashlink/params/M08  # M08, TC w_ref
$PY -I analysis/proxy_quicklook/code/st_report.py <out.md> <label=assess.json> ...
```

W2.4a-2 stages 4-6 (`T=runs/proxy_quicklook/st4b`, `P=/Users/.../dashlink_tail652/extracted`):

```bash
# stage 5 (run first in pass 2): windows from the inputs, staged identification, plant re-run
$PY -I analysis/proxy_quicklook/code/st5_segments.py $M runs/proxy_quicklook/st5/segments.json 12
ST4_AT=mf1base $PY -I analysis/proxy_quicklook/code/st5_ident.py $M <segments.json> <ident.json> 5 6
$PY -I analysis/proxy_quicklook/code/st5_plant_rerun.py $M <ident.json> <ident_plant_gov2.json> 6 6
# stage 4: transfers, empty-bank base, synthesis fit, verification, adoption
$PY -I analysis/proxy_quicklook/code/st4_tf.py $T/tf_g2.npz 1500 2:1    # pass 1: ST4_AT=mf1base, grid 2:1,1:0.5,0.5:0.25
$PY -I analysis/proxy_quicklook/code/st4_base.py $M $T/base4.npz 4 4 2:1
ST4_STC=fixed $PY -I analysis/proxy_quicklook/code/st4_fit.py $T/base4.npz <pooled.json> $T/tf_g2.npz
ST4_STC=fixed ST4_AGG=median $PY -I analysis/proxy_quicklook/code/st4_fit.py $T/base4.npz <median.json> $T/tf_g2.npz
$PY -I analysis/proxy_quicklook/code/sweep.py $M st4v 4 $T/verify 4
$PY -I analysis/proxy_quicklook/code/st4_adopt.py analysis/proxy_quicklook/results/stage4/st4_fit_pooled.json kp2ki1
# stage 6 (Kaggle: kaggle_stage.py + kaggle_pending_cmds.txt; smoke locally with limit 1)
$PY -I analysis/proxy_quicklook/code/st6_quicklook.py $M $P analysis/proxy_quicklook/results/stage6_spec.json <out> 4 [1]
$PY -I analysis/proxy_quicklook/code/kaggle_stage.py quicklook $M $P analysis/proxy_quicklook/results/stage6_spec.json \
    runs/proxy_quicklook/kaggle/st6 phalanx-w24a2-quicklook
```
