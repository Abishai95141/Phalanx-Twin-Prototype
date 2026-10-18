# Settling experiment, round 2: model-in-the-loop behavioural fidelity (pre-registration)

**Written:** 2026-10-14, before any round-2 model was fitted, any round-2 synthetic data was generated, or any
round-2 holdout data was read beyond integrity checks. Any change after this commit goes in the amendment log
(§9) with a timestamp. Changes are allowed only before holdout synthesis starts, unless logged as a deviation
with results reported both ways.

## 1. Question

**When synthetic recorder data comes from a physics-structured dynamic engine model plus a revised
sensor/acquisition texture model, does it reproduce the real data's behavioural and causal structure as closely
as real data reproduces itself across tails, and ideally across seasons?**

- The model is driven by the aircraft's real inputs and fitted on calibration flights only.
- Real data is used only for the inputs and for calibration. All outputs must be generated.

**Why this round exists.** In round 1 the synthetic "truth" was the low-passed real signal, so slow behaviour,
lags and physical laws were inherited and could not fail. Two round-1 findings:
- The independent per-parameter residual model destroyed within-engine fast coupling (`analysis/correlation_check/`).
- The single-step quantiser missed the native step: double quantisation (Gate-0 smoke test).

Round 2 tests the architecture's real division of labour:
- the **physics/dynamic model carries coupling and causality**;
- the **texture layer carries only sensor/recorder effects**.

**Scope.** The engine channel group only: N1, N2, EGT and FF for each of the 4 engines, at 4 Hz.

## 2. Data, holdout and fallback

| Role | Data | Use |
|---|---|---|
| **Calibration** | Tail 687 archive 1, the round-1 `687-CAL` split (152 flights, `analysis/settling_experiment/results/splits.csv`) | The **only** data used to fit anything |
| **Holdout (primary)** | Tail 687 **archive 2** (`research_sources/datasets/dashlink_tail687/raw2/`), eligible flights under the same rule that built `analysis/dashlink_texture/results/eligible_flights.csv` | Evaluation only; untouched until the models are frozen (§6) |
| **Holdout (fallback)** | Tail 652 archive 8 (110 eligible flights, round-1 `652` split) | Used only under the fallback rule below |
| **Not used for anything in round 2** | Round-1 `687-TEST` flights, except as a real-vs-real baseline group in fallback mode | They were examined in round 1 |

**Fallback rule.**
- If archive 2 has not been downloaded, size-verified, SHA-256-recorded and extracted by **2026-10-15 10:00 IST**, the holdout becomes **Tail 652 archive 8**.
  - This turns the test into a cross-tail transfer test: fitted on 687, evaluated on 652.
  - Caveat, to be stated in the report: Tail 652 served as round-1's tail baseline, so its data has been seen in aggregate, although no round-2 model is fitted on it.
- If archive 2 becomes available later, the full analysis is also run on it. The report shows both, and the archive-2 result is primary.

**Sample.**
- If the holdout has more than 200 eligible flights, a fixed random sample of 200 is used (seed `20261015`), and the list is saved before any analysis.
- Every comparison uses equal numbers of flights per group.

## 3. Models (all fitted on 687-CAL only)

### M-A: proxy engine model (physics-structured grey box, one instance per engine position)

- **Inputs** (real, from the holdout flight): PLA_k, ALT, MACH and TAT. Inlet corrections θ and δ are computed from them with the standard-atmosphere relations.
- **Structure** (a fixed causal chain, with parameters fitted by output-error least squares):
  1. **Fuel control:** corrected fuel flow Wf/(δ√θ) = f(PLA, corrected flight condition), through asymmetric acceleration/deceleration rate-limited dynamics.
  2. **Core:** corrected N2 = g(corrected Wf), with a first-order lag. Accel and decel time constants are fitted separately.
  3. **Fan:** corrected N1 = h(corrected N2), with a lag.
  4. **EGT:** EGT/θ^a = k(corrected Wf, corrected N1), with a first-order thermal lag. The exponent a is fitted; the round-1 measurement was a ≈ 0.5–0.7.
- **Map forms.**
  - Steady maps f, g, h and k are monotone splines with at most 8 knots each.
  - No black-box ML: no neural networks and no unconstrained boosting (decision D4).
- **Unit offsets.** Per-engine offsets in the primary analysis are **drawn from the fleet prior**, as for an unseen Tejas tail. A secondary analysis uses the CAL-fitted offsets for each engine position.

### M-B: revised sensor/acquisition texture (fitted on CAL residuals *after* M-A)

- **Double quantiser.**
  - y = LSB_rec · round(LSB_nat · round(x / LSB_nat) / LSB_rec).
  - The native step LSB_nat comes from CAL-only residue-usage patterns (the round-1 `s12_native_step` diagnostic). Example: EGT ≈ 0.8 °C on the 0.5 °C recording lattice.
- **Sensor noise.** Small **independent** per-sensor noise, with an AR(1) form allowed. Variance is fitted on CAL steady segments after subtracting the M-A prediction.
- **Recorder effects.** Glitch words, validity gating and frame effects carry over unchanged from round 1. VRTG is not in scope.

### M-C: coupled discrepancy model (optional layer, evaluated as a separate arm)

- **Form:** a coupled multivariate residual over [FF, N2, N1, EGT] per engine. It is either one shared latent driver passed through channel-specific lagged transfer functions, or a VAR(p ≤ 8) with cross terms.
- **Fitting:** on CAL residuals after M-A and before M-B.
- **Purpose:** it represents real dynamics that M-A does not capture.

### Arms

| Arm | Layers | What it tests |
|---|---|---|
| **R2a** | M-A + M-B | How much coupling the physics structure carries on its own |
| **R2b** | M-A + M-C + M-B | Coupling with discrepancy correction |
| **R1-ref** | Round-1 FULL texture on low-passed real truth | Reference only, for comparison with round 1 |

## 4. Behavioural fidelity battery (primary evidence)

**Rules that apply to every test.**
- Each test compares groups with **the same estimator**, on airborne samples (all four N1 > 25 %).
- Bootstrap CIs resample flights (2,000 resamples).
- Distances are as defined in each row; a smaller distance is better.

| Test | Measures | Distance D |
|---|---|---|
| **B1 Cohesion** | Pearson correlation matrices of the 16 channels, slow band (low-pass 0.2 Hz) and fast band (residual), flight-median per pair. The 0.5 Hz split is reported as sensitivity. | Mean absolute difference over the 120 pairs; slow and fast bands reported separately, fast band primary |
| **B2 Lead–lag** | Per engine, lag (s) of peak cross-correlation of first differences for FF→N2, FF→N1, N2→N1, FF→EGT, N1→EGT (±10 s) | Mean absolute difference of flight-median lags (s) |
| **B3 Dynamic response** | (i) Welch coherence and \|transfer gain\| for PLA→FF, FF→N2, FF→N1, FF→EGT in bands 0.01–0.05, 0.05–0.2 and 0.2–1 Hz; (ii) median N1/FF/EGT time constants for detected throttle steps, accel and decel separately (round-1 `transients.py` detector) | Mean \|Δ log gain\| + mean \|Δ coherence\|; mean \|log τ ratio\| |
| **B4 Directional dependence** | Engine-1 VAR(8) on first differences of [FF, N2, N1, EGT] per airborne segment; Granger F-statistic matrix (4×4 off-diagonal), flight-median | Mean \|Δ log F\| over the 12 directed pairs |
| **B5 Physical laws** | (i) Relative RMS scatter of corrected fuel flow vs corrected N2 about a smooth fit; (ii) fitted EGT temperature exponent a | \|Δ scatter\| / scatter_real; \|Δ a\| |
| **B6 Regime behaviour** | Per flight phase (PH codes), each channel's median, IQR and fast-band σ | Mean \|Δ\| normalised by the real per-phase IQR |

**Not testable on DASHlink.** B7 (fault signatures) and B8 (BIT/event behaviour) need labelled faults and BIT,
which DASHlink lacks. They are deferred to the Tejas build: literature signature matrices, plus NGAFID, RflyMAD
and other proxies.

**Secondary: B9 downstream fitness.** Predict EGT 10 s ahead from the other channels with ridge regression and
gradient boosting. Report TSTR/TRTR R² ratios and the agreement of the two models' ranking (report only).

## 5. Bars and decision rules

**Real-vs-real bars.** Both are computed with the same estimators and equal flight counts.

| Bar | Primary mode (archive 2) | Fallback mode (Tail 652 holdout) |
|---|---|---|
| **D_tail**, "as close as one real tail is to another" | Holdout (687 archive 2) vs Tail 652 archive 8 | Holdout (652) vs round-1 687-TEST |
| **D_temp**, the stricter bar | Holdout early vs late, split at the median flight date | Same |

**Per-test verdict.** For each test B1–B6 and each arm, with D_sim = distance(synthetic holdout, real holdout),
paired by flight:

| Verdict | Condition |
|---|---|
| **PASS** | D_sim ≤ D_tail |
| **FAIL** | The one-sided 95 % bootstrap lower bound of (D_sim − D_tail) is above 0 |
| **INCONCLUSIVE** | Otherwise |
| **STRICT PASS** (reported alongside) | D_sim ≤ D_temp |

**Guards** (apply to both arms):

| Guard | Rule | Status |
|---|---|---|
| **G0 Trivial-cue audit** | Pipeline-only metadata subset (counts, length, dtype, NaN, float32 representability); the 95 % CI of the AUC must include 0.5 | Binding. The full-metadata AUC is reported as a diagnostic. |
| **G1 Quantiser fidelity** | Distance between the residue-usage histograms of synthetic and real | Diagnostic |
| **Label-leak audit** | — | Not applicable (no fault labels); mandatory in the Tejas fault build |

**Discriminator role.**
- The round-1 discriminator ladder (D2 LR/GB, D3 MiniRocket) runs on R2a and R2b for **diagnosis only**, with feature-family ablation. It produces **no verdict**.
- Ceiling effects in the AUC are irrelevant to the decision.

**Overall decision.** The decision is made on the better arm, and both arms are reported.

| Decision | Condition |
|---|---|
| **GO** | G0 passes; none of B1–B6 is FAIL; at least 4 of the 6 PASS |
| **GO WITH FIXES** | G0 passes; one or more FAILs; each FAIL is attributed to one module (M-A, M-B or M-C) using the arm contrast and the ablations, with a fix that does not change module interfaces or the data contract |
| **REWORK** | G0 fails after pipeline fixes, or a FAIL implicates the architecture premise. Examples: neither arm reproduces within-engine coupling or lead–lag order; or sensor-independent texture plus physics structure cannot reproduce B1 even with M-C. |

## 6. Freeze and hygiene

1. Fit M-A, M-B and M-C on CAL.
2. Save all parameters, then record their SHA-256 hashes in `results/frozen_models.json`.
3. **Commit to git before reading holdout data.** Until then only integrity checks are allowed on the holdout: size, hash, file count and date range.
4. Inputs taken from holdout flights are the real PLA_k, ALT, MACH, TAT and PH channels. Nothing in a holdout flight's outputs (N1, N2, EGT, FF) is used to generate its synthetic version.
5. Synthetic holdout files are written as MAT files through the same `dlio.load_flight` path as in round 1.

## 7. Compute and verification

- **Where it runs:** local `.venv-settling`, or Kaggle CPU kernels. Kaggle reproducibility was already verified in round 1 (agree = true; per-flight score differences ≤ 3e-13).
- **Sample batch first:** every new script or kernel runs on a 20-flight sample before the full run, and the check is logged.
- **Seeds:** root seed `20261015`; per-module `SeedSequence` streams keyed by (flight, engine, component).
- **Reproducibility files:** a README with exact commands, pinned requirements, and `results/manifest.json` with input hashes.

## 8. Deliverables

- `REPORT.md`, with the per-test verdict table first, then:
  - the arm contrast (R2a vs R2b vs R1-ref);
  - the battery figures;
  - the guard results;
  - the discriminator diagnostics;
  - attribution of every failure to a module;
  - threats to validity, including the fallback caveat if it applies, and the fact that DASHlink is an airliner;
  - the implications for the Tejas M07/M13 design.
- Scripts in `src/`, results in `results/`, figures in `figures/`.
- An amendment log (§9) and a `DEVIATIONS.md`.

## 9. Amendment log

Entries are allowed only before holdout synthesis starts. Each records date and time, the change, the reason,
and the round-1 evidence behind it.

- *(none at writing)*. Round-1 diagnostics still pending at writing: the interim verdict, the feature-family ablation, and the CAL native-step diagnostic. They may refine M-B's components, but only through this log.

All entries below were written before any round-2 model was fitted, before any round-2 synthetic data existed,
and before any holdout flight data was read (archive 2 has never been downloaded; Tail 652 archive 8 has not been
opened in round 2).

**A1. 2026-10-14 15:06 IST. Fallback holdout triggered now (user decision, relayed by the coordinator).**
- *Change.* The fallback rule of §2 is applied immediately instead of at 2026-10-15 10:00 IST. The primary
  holdout is **Tail 652 archive 8** (the 110 eligible round-1 `652` flights; read-only at
  `/Users/abishaikc/phalanx/data/raw/dashlink_tail652/extracted/`). The cross-tail caveat of §2 applies and is
  stated in the report.
- Tail 687 archive 2 becomes a **confirmatory** holdout, run with the identical frozen models if and when it is
  downloaded, size-verified, SHA-256-recorded and extracted. It no longer replaces the 652 result as primary.
- Bars are those of the prereg fallback mode (§5): D_tail = 652 holdout vs round-1 687-TEST; D_temp = 652 early vs
  late, split at the median flight date. Decision rules (§5), battery (§4), guards and sample rule (§2) unchanged.
- Phase B starts as soon as the freeze (§6) is committed.
- *Reason.* The user prioritised speed. NASA DASHlink has been unreachable since 13:39 IST
  (`research_sources/datasets/dashlink_tail687/raw2/fetch.log`, every retry "unreachable"). No holdout data has been
  read.

**A2. 2026-10-14 15:06 IST. M-B native steps fixed from the round-1 CAL native-step diagnostic.**
- *Change.* LSB_nat per channel family: N1 and N2 = 0.04 %RPM (1.28 recorder LSB of 0.03125; period 32 codes =
  25 native steps, 7 never-used codes per period); EGT = 0.8 °C (1.6 LSB of 0.5 °C; period 8 codes = 5 native
  steps, residues 1, 4, 7 never used). FF: no double quantisation is detectable (best native step 0.333 LSB has
  the same correlation as r ≈ 1), so FF uses the single recorder lattice (8 lb/h). The native-grid offset is
  refined on CAL only (finer grid than round 1's 0.02 LSB) so that the predicted never-used residues equal the
  observed ones.
- *Evidence.* `analysis/settling_experiment/results/native_step_cal.json` (687-CAL only): N1/N2 corr 0.51–0.59 at
  r = 1.28 vs 0.19–0.49 at r ≈ 1; EGT corr 0.92–0.96 at r = 1.6 vs 0.25 at r ≈ 1; 22 % (N1/N2) and 37.5 % (EGT)
  of codes in the dense range never used.

**A3. 2026-10-14 15:06 IST. Division of residual variance between M-B and M-C, from the round-1 coupling evidence.**
- *Change.* (i) M-B's "small independent per-sensor noise" is identified as the **idiosyncratic** part of the
  CAL steady-segment residual after M-A: the variance not explained by the other three channels of the same
  engine and the same channel on the other three engines (contemporaneous and ±2-sample lags), net of the
  quantiser's own variance. The full residual variance is not used, because the round-1 evidence shows that
  most fast-band residual variance is coupled dynamics, not sensor noise. (ii) M-C keeps per-engine dynamics
  over [FF, N2, N1, EGT] with cross terms; its innovations may be correlated across the four engines (one
  16×16 innovation covariance estimated on CAL), so that M-C does not dilute cross-engine coherence.
- *Evidence.* `analysis/correlation_check/README.md`: fast-band (f_c 0.2 Hz) within-engine N1–FF 0.65 real vs
  0.04 round-1 synthetic; N1–EGT 0.56 vs 0.05; N1–N2 0.43 vs 0.05; cross-engine N1_1–N1_2 0.80 real (reproduced
  by round 1's common-mode term, 0.78). Fast-band distance 0.32 synthetic vs 0.02–0.05 real-vs-real.

**A4. 2026-10-14 15:06 IST. M-B recorder effects for the engine channel group, from the round-1 mechanism check.**
- *Change.* All 16 in-scope channels are digital 4-Hz words. Because P4 was refuted (no stale or duplicate
  digital reads at clock slips), M-B applies **no** clock-slip missingness to them; Δ ≈ 910 ppm (CAL median
  910.5 ppm) is recorded for completeness only (it acts on VRTG, which is out of scope). M-B carries over round
  1's L5 recorder effects unchanged from `model_params_primary.json` `fixed`: validity gating below the lowest
  valid reading (N1 1.22–2.03 %, N2 0.031 %, FF 8 lb/h; EGT not gated), glitch words (CAL rate 0 for all 16
  channels) and airborne episodic freezes (CAL rates: EGT 0.016–0.098 /air-h, FF_1 0.19 /air-h, N1_1 0.01 /air-h).
- *Evidence.* `analysis/settling_experiment/results/mechanism_decisions.json` (P1 confirmed, P4 refuted, 687-CAL);
  `model_params_primary.json` `fixed.gate/glitch/freeze` (687-CAL).

**A5. 2026-10-14 15:06 IST. Quick-look development step (user request, relayed by the coordinator).**
- *Change.* Before the full Phase A, a simplified M-A (same causal chain and corrected parameters, fewer knots)
  is fitted on a fixed random sample of 30 687-CAL flights (seed 20261015) and used to generate 15–20 *other*
  CAL flights, with M-B (A2 native steps) and without M-C; only B1, B2 and B5 are computed. This is a
  development diagnostic on CAL data only, never a verdict, and changes no rule, bar or holdout.

**A6. 2026-10-14 15:31 IST. Sensor-dynamics stage between M-A truth and M-B (coordinator pointer after the quick look).**
- *Change.* A sensor-dynamics stage (part of the sensor/acquisition layer; it carries no engine physics) is added
  between the M-A engine truth and M-B:
  - **FF:** measured FF = first-order lag of true FF, τ_FFs fitted on CAL. No update-interval hold: round-1 CAL
    transients show no FF staircase (median fraction of identical consecutive samples during fast changes 0.0,
    p90 0.14; `analysis/dashlink_texture/results/transients_stale_summary.csv`). The FF and N2 stages are fitted
    jointly by output error, so that the truth Wf that drives N2 can lead the measured FF.
  - **EGT:** thermocouple lag τ_TC = τ_TC,ref · W_rel^−0.5 (AGARD scaling with gas mass flow),
    W_rel = (δ/√θ)·(N1c/90). τ_TC,ref is fitted on CAL jointly with M-A's gas-path thermal lag.
  - M-A's pre-registered chain, maps and lags are unchanged; true FF still leads N2 in the model.
- *Evidence.* Quick look (CAL only, `results/QUICK_LOOK.md`): in real CAL data N2 leads measured FF by 0.5 s,
  then N1, then EGT, while the open-loop chain forces FF to lead (B2 0.35 s vs 0.26 s for R1-ref). Round 1:
  measured FF time constant ≈ 1.3 s and EGT lags spools/FF by 0.75–1.25 s
  (`research_notes/.../empirical_dashlink_texture.md` Q6–Q7). Flowmeter dynamics
  (`research_notes/.../texture_and_fault_gap_closure.md` Q2): angular-momentum meters update every 300 ms; turbine
  meters respond in about 10 ms; the meter type is unresolved.
- Closed-loop speed governing is **not** added (it would mix attribution between engine and sensor physics).

**A7. 2026-10-14 15:31 IST. Unit variation placed where it physically lives (coordinator pointer after the quick look).**
- *Change.* The per-position "unit offsets" are re-parametrised (variant S) as:
  - component-health deltas: a fuel-efficiency delta e (demand × (1+e); the core sees Wc/(1+e), so the same
    N2 needs more fuel and EGT follows through the physics) and a fan/core match delta m (% on h);
  - sensor installation biases: b_N2 (% on measured N2) and b_EGT (°C on measured EGT).
  Each is sum-to-zero over the four positions and fitted on CAL. The fleet prior is the across-position SD of each,
  and an unseen tail draws (e, m, b_N2, b_EGT) from it. The physics then produces the output offsets.
  - The pre-registered additive output offsets (a_f, a_g, a_h, a_k) remain as variant P.
- *Evidence.* Quick look: the corrected FF-vs-N2 scatter was 0.093 synthetic vs 0.049 real (B5 D = 0.89), driven
  by prior-drawn N2 output offsets (SD ≈ 1.2 %) mapped through the steep Wf_c(N2c) curve at cruise. That is
  physically inconsistent, since the same N2 offset should move FF and EGT together.

**A8. 2026-10-14 15:31 IST. Reporting of A6–A7 "both ways".**
- Two model variants are fitted, frozen and evaluated with identical scripts:
  - **S** (A6 + A7): primary for the decision.
  - **P** (pre-registered structure; output offsets; no sensor stage): reported alongside every result.
- Arms R2a (M-A + M-B) and R2b (M-A + M-C + M-B) exist for both. Offsets: fleet prior (primary) and CAL-fitted
  (secondary), as pre-registered.
- The decision rules (§5) are applied to S (better of R2a/R2b); P is reported with the same rules for comparison.
- The fitting procedure for both variants fits the FF and N2 stages jointly (output error on FF and N2 together),
  then N1, then EGT. For P this is a fitting-procedure change only (the quick look fitted FF then N2 separately).
