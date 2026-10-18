# Round 2: deviations, clarifications and pipeline fixes

Every departure from `PREREGISTRATION.md` (commit f6aa660) is listed here with the date, the reason and, where
possible, the result with and without it. Structural model changes are amendments in §9 of the pre-registration
(A1–A8), not deviations; they are only cross-referenced here. "Clarification" fills in a detail the
pre-registration left open. All dates are 2026-10-14. Unless stated otherwise, each item was fixed before the
freeze and before any holdout flight data was read.

## A. Data and scope

**A1. Holdout.** Amendment A1 applies: Tail 652 archive 8 is the primary holdout from now on; Tail 687 archive 2 is
confirmatory. No holdout data were read in Phase A. The only Tail 652 action was a directory listing of
`/Users/abishaikc/phalanx/data/raw/dashlink_tail652/` (names only). The 687 archive-2 fetch log
(integrity metadata) was read.

**A2. 687-TEST is not used in Phase A.** The CAL-only development battery needs a real-vs-real reference. 687-TEST
(the D_tail partner in fallback mode) and 652 (now the holdout) are both excluded, so the development reference is
**CAL early vs late** (median date split, equal n). It is a D_temp analogue and is never a bar.

## B. M-A (proxy engine model)

**B1. "One instance per engine position".** (Clarification.)
- Each of the four instances is driven by its own PLA_k and shares the engine-*type* steady maps and dynamics.
- Each instance carries its own unit parameters, sum-to-zero over the four positions, so the type maps describe
  the average engine.
- Reason: the primary analysis must represent an *unseen* tail (type model plus fleet-prior unit variation). With
  only four positions, separate per-position maps could not be split into type and unit parts.

**B2. Corrections.** (Clarification.)
- θ = (TAT + 273.15)/288.15.
- δ = δ_s(ALT)·(1 + 0.2 M²)^3.5: ISA static pressure ratio with full isentropic ram recovery.
- TAT (1 Hz) is linearly interpolated to the 4-Hz grid.
- MACH = 0 is the channel's sentinel: isolated zeros with a 2-s neighbourhood median above 0.15 are interpolated;
  ground zeros are kept.
- PT (measured total pressure) is **not** used, because the pre-registered inputs are PLA_k, ALT, MACH and TAT.

**B3. Engine running state (PROXY).** (Smallest change for an impossibility.)
- From inputs alone, an engine that is shut down at idle PLA cannot be told apart from a running one. Synthesis
  therefore treats an engine as running when PH ∈ {2..7}; this is a PROXY.
- Outside running segments each channel holds its CAL engine-off reading. The state is initialised at the steady
  map value when a segment starts. Start and shutdown transients are not modelled.
- Fitting on CAL uses the output-based mask N2 > 40 % and PH ∈ {2..7}; outputs may be used on CAL.
- Effect on the battery: the airborne rule (all four N1 > 25 %) excludes start transients. However, ground-idle
  N1 (25–26 % on 687) sits at the 25 % threshold, so which taxi samples enter the mask depends on the synthetic idle
  level. Listed as a threat to validity.

**B4. Fitting procedure.** (Clarification, A8.)
- Staged output-error least squares: the FF and N2 stages jointly (on measured FF and N2), then N1, then EGT, each
  driven by the simulated upstream signals.
- The loss uses every 7th running sample and drops the first 60 s of each running segment, where the state is
  initialised at the steady value.
- Solver: scipy `least_squares` (trf, lsmr, `x_scale='jac'`) with a forward-difference Jacobian evaluated in
  threads; at most 100 function evaluations per stage. A stage that stops at the cap is reported (status 0).
- Steady maps: monotone PCHIP, K = 8 knots at fixed positions.
  - Fuel-flow axis: log-spaced between the 0.5 and 99.5 percentiles.
  - Other axes: the mean of quantile and evenly spaced positions.
- Bounds: increments ≥ 0 and capped; τ ∈ [0.1, 30] s; health delta e ∈ [−0.3, 0.3]. Parameters at bounds are
  listed in `ma_readable.json` (`at_bound`).
- **Convergence and warm start** (coordinator request; 16:44 IST, before the final fits).
  - Convergence: scipy trf `ftol` 1e-6 (relative cost change), `xtol`/`gtol` 1e-8. Status, converged flag, initial
    and final cost and wall time are stored per stage (`ma.json` → `info`).
  - The CV and sample fits used a 100-evaluation cap. Several of their FF+N2 stages stopped at the cap (status 0,
    *not converged*) and are labelled so; they are development fits only.
  - The frozen all-CAL fits were warm-started and capped at 300 evaluations:
    - S from the S fold-0 solution, maps re-projected onto the all-CAL knots;
    - P from the frozen S (maps and dynamics; output offsets start at 0).
  - **Every stage of both frozen variants converged** (status 2): S FF+N2 135 evaluations / 1,233 s, N1 5, EGT 12;
    P FF+N2 9, N1 4, EGT 45.
  - Cost driver: finite-difference Jacobians, about 34 simulations of 9–14 M samples per iteration
    (coordinator insights E10). A memory-bound concurrency failure is logged in `log_sample_batches.md` #12.
- **Uncertainty.** Every parameter is logged with (i) a naive Jacobian SE inflated by the residual-AR(1) factor
  (1+ρ)/(1−ρ) and (ii) the grouped-jackknife SE over the CV folds (`results/cv_fit_quality_*.json`).

**B5. Cross-validation: 3 folds, not 5.** (Clarification; minimal sufficient sample, project rule 1.)
- The brief says "e.g., 5-fold". Three flight-grouped folds (51/51/50 held-out flights; 101–102 training flights)
  give an out-of-fold prediction for every one of the 152 CAL flights with three fits instead of five.
- One output-error fit of a fold takes about 20 min on 10 cores.
- CV is run for the decision variant S. Variant P gets fold 0 only, for the S-vs-P development contrast on the same
  held-out flights, plus the 20-flight sample batch.

**B6. Pipeline fix: corrected vs physical fuel flow (quick look v1).** The FF stage compared the simulated
*corrected* fuel flow with the measured *physical* FF. Found by the out-of-sample check (FF bias −405 lb/h) and
fixed before any reported number (`results/log_sample_batches.md` #5).

**B7. Compiled kernels.** The simulation runs in fused numba kernels. They are bit-identical to the numpy reference
implementations kept in `ma_model.py` (`_ref_sim_*`), and the numba PCHIP agrees with scipy's to < 1e-11
(`src/t01_selftest.py`; output in `results/log_selftest.txt`).

## C. M-B, M-C

**C1. M-B noise variance (A3).** The idiosyncratic residual variance in CAL steady cruise falls below the quantiser
variance for EGT, FF and most N2 channels. Their sensor-noise σ is therefore 0 (floor), and N1 σ is 0.01–0.03 %.
This is the measured result of the pre-registered estimator, not a choice.

**C2. M-C band and noise budget.** (Clarification.)
- M-C is fitted on M-A residuals band-limited above 0.01 Hz, so slow (< 0.01 Hz) M-A error is not regenerated.
- Quantiser and M-B noise variances are removed from the innovation diagonal (projected to PSD), because M-B
  generates them.
- VAR order by BIC (p ≤ 8). The state resets at each running-segment start, with a 200-sample warm-up.

## D. Battery, guards, diagnostics (all fixed before the freeze)

**D1. Multi-part tests.** B3 has parts (i) spectral and (ii) time constants; B5 has parts (i) scatter and (ii) EGT
exponent. A test is PASS iff every part passes, FAIL iff any part fails, otherwise INCONCLUSIVE. B1's verdict uses
the fast band (pre-registered "primary"); the slow band and the 0.5-Hz split are reported.

**D2. Estimator details.** (Clarification.)
- **B2:** first differences over the concatenated airborne samples, exactly as `corr_check.py`.
- **B3 (i):** longest airborne run ≥ 10 min, Welch nperseg 512, H1 gain, natural-log gain differences.
- **B3 (ii):** round-1 detector and FOPDT fit, R² > 0.9, |ΔPLA| ≥ 5°, airborne rule at the step; group τ is the
  median over the pooled steps (≥ 3 steps per cell).
- **B4:** per flight, one pooled VAR(8) regression over airborne segments ≥ 120 s; F statistic for dropping the
  cause's 8 lags; log F.
- **B5:** pooled least-squares moments per group (cubic for scatter; quadratic and exponent grid 0–1.2 step 0.01
  for a).
- **B6:** the airborne rule is applied in every phase; phases with < 40 samples in a flight are missing.
- **B9:** target EGT_1 10 s ahead; features N1/N2/FF of all four engines at t and their 5-s differences; 1-Hz
  airborne rows; 50/50 flight split; ridge and HistGradientBoosting with fixed hyper-parameters.
- **G1:** total-variation distance between pooled residue-usage histograms (mod 32 for N1/N2; mod 8 for EGT and
  FF) on airborne samples.

**D3. Distance normalisation.** B5 (i) and B6 are normalised by the real holdout (D_sim, D_tail) or by the early half
(D_temp).

**D4. Joint bootstrap.** Bootstrap draws are shared by flight list, so D_sim and D_tail use the same holdout
resample, and the one-sided bound is taken on D_sim − D_tail.

**D5. Discriminator diagnostics.** (Minimal sufficient sample.)
- D2 LR/GB on 64-s windows and whole segments (texture families), D3 MiniRocket on 64-s residual windows, and
  feature-family ablation (drop-one and only-one) for the strongest D2 window classifier.
- Omitted: 300-s windows and permutation tests. The discriminators are diagnostic only and produce no verdict.

**D6. G0.** Round-1 Gate-0 features and `s07_gate0.evaluate` (pipeline-only subset binding; full metadata
diagnostic). VRTG fields enter the feature vector; VRTG is the real array in every synthetic file (out of scope).

**D7. Holdout input checks (report only).** Before synthesis, the runner records each holdout flight's airborne
MACH-zero fraction, TAT/ALT ranges and PLA ranges (`input_checks.json`). It flags MACH zeros > 5 %, PLA range < 5°
or ALT max < 5,000 ft. No flight is excluded; flags are reported. All 152 CAL flights pass (no dead MACH channel;
checked on CAL only).

**D8. Archive 2 (confirmatory) sample size.**
- The pre-registered sample of ≤ 200 eligible flights (seed 20261015) is drawn and saved before any analysis
  (`list_sample200.txt`).
- Every comparison must use equal flight counts (§2), and the D_tail partner (Tail 652) has 110 eligible flights. So
  D_sim, D_tail and D_temp use one seeded subsample of 110 from the saved 200.
- Archive 2 became available at 16:55 IST (coordinator's fetch log: 837,334,163 bytes; SHA-256 df7bdda1…6fcc;
  602 MAT files, Sep–Dec 2001). Only its integrity metadata were read before the freeze.

## E. Records

**E1. Quick-look provenance.** `results/QUICK_LOOK.md` was produced by an earlier code state: staged FF-then-N2
fit, scipy PCHIP, output offsets (variant P), K = 5. Re-running `src/q01_quick_look.py` with the current code
gives variant P with the joint FF+N2 stage, so its numbers differ.

**E2. Timestamps.** Times first written by hand in `QUICK_LOOK.md` and `log_sample_batches.md` were corrected to
the system clock and file modification times.

## F. Filled in after the runs

**F1. Archive-2 confirmatory run deferred and reserved. Coordinator decision 18:02 IST, user-confirmed.**
- The primary holdout (Tail 652, 110 flights) gave the pre-registered decision **REWORK**: 0/6 PASS for every arm
  of both variants.
- The coordinator paused the archive-2 run before any of its flight data was read. Reason: confirming frozen models
  that had already failed would add little and would spend the only pristine holdout.
- The user confirmed:
  - archive 2 stays **unread**, reserved as the holdout for the build's proxy-mode acceptance gate (M07/M08 plus
    the new process-disturbance layer);
  - **Option B:** no round 3; the rework goes into the build.
- **What was accessed of archive 2:**
  - `raw2/fetch.log` (text);
  - the SHA-256 of `Tail_687_2.zip`, recomputed at the freeze (bytes hashed; no MAT file opened or parsed);
  - an existence check of `raw2/mat/` (`os.path.isdir`; the directory was not listed).
- No archive-2 eligibility scan, sample list, synthesis or statistic was produced.
- This departs from amendment A1 ("run when available") and from the prereg's §2 "If archive 2 becomes available
  later, the full analysis is also run on it". No result is reported for archive 2.

**F2. CV scope at completion.**
- S: folds 0, 1 and 2 were fitted (cold start, 100-evaluation cap). Each FF+N2 stage stopped at the cap (status 0,
  **not converged**); N1 and EGT converged. Out-of-fold numbers are therefore conservative development
  diagnostics.
- P fold 0 was not fitted: it was stopped in the memory incident and not re-run after the user's "finish what is in
  flight" instruction. The S-vs-P contrast is reported from the sample batch and the 652 holdout.

**F3. Post-hoc diagnostic (not pre-registered).** Autothrottle-engaged vs manual FF→N2 lead–lag on CAL real data
(`src/q02_at_leadlag.py`, coordinator request): reported in REPORT §5 as post hoc and phase-confounded, with no
verdict.
