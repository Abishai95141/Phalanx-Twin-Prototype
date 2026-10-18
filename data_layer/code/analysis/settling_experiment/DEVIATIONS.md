# Deviations, clarifications and pipeline fixes

Every departure from `PREREGISTRATION.md` is listed here with the date, the reason, and where possible the
result with and without it. "Clarification" entries fill in details the pre-registration left open. They were
fixed before any synthetic 687-TEST data existed and before any classifier was run, unless stated otherwise.
All dates are 2026-10-14.

## A. Environment

**A1. A separate interpreter environment `.venv-settling`.** (Clarification.)
- aeon 1.6.0, which provides MiniRocket, needs numba 0.63.1. That numba needs numpy ≤ 2.3, but the existing `.venv` pins numpy 2.5.4.
- So the experiment runs in `/Users/abishaikc/Phalanx/.venv-settling`:
  - CPython 3.14.6, the same interpreter;
  - numpy 2.3.5, scipy 1.17.1, scikit-learn 1.9.1, aeon 1.6.0, pycatch22 0.5.0 and matplotlib 3.11.2;
  - full pins in `requirements.txt`.
- The existing `.venv` is untouched. `dlio.py` and `common.py` are imported unchanged; their SHA-256 hashes are in `results/manifest.json`.
- `scipy.io.loadmat` round-trips every file bit for bit, checked on 5 files per variant (see C1).

## B. Mechanism check (section 5)

**B1. Estimator bug fixed after the first run.** (Pipeline fix, not a change of rule.)
- v1 pooled all channels of one rate group into a single Rayleigh phasor sum, with a single phase.
- The first run showed that the channels in one group have distinct but fixed phases. LATG and LONG differ by 0.2 of a 4-Hz beat cycle; these are their word slots.
- Pooling them made the folded loss profiles multi-peaked, so the boxcar window fits were meaningless. v1 gave 8/4/2/1-Hz window widths of 19.5/71/178/415 ms.
- v2 fixes this:
  - Δ comes from the *incoherent* sum of per-channel Rayleigh powers;
  - phase, profile and window are estimated per channel.
- Effect of the fix on the decisions:
  - **P4 is unchanged:** refuted in v1 (CAL test (i) p = 0.17) and in v2 (p = 0.06).
  - The v1 P5 verdict ("refuted", w ratio 21) was an artefact. v2 gives a ratio of 1.14 ("confirmed").
  - P1 under v1: the 1-Hz group's Δ was biased by the mixed phases (median difference −2.02 ppm against the ±2-ppm rule).
- The v1 summary is kept as `results/mechanism_summary_v1_pooled_phase.json`. The v1 code is not in the repository.

**B2. How P1–P3 were made testable, and the literal reading.** (Clarification; the second half is post hoc.)
- The pre-registration states P1–P5 as sentences. Before the first run, the decision rules in the docstring of `src/s03_mechanism.py` turned them into numerical tests ("verdict"):
  - P1: tolerance of ±2 ppm;
  - P2: split-half reliability gate ≥ 0.3 for "Δ varies across flights";
  - P3: coincidence within 0.1 period;
  - P5: max/min ≤ 1.5.
- Those rules are reported as the official verdicts.
- After the first run it became clear that two of them are *stricter* than the pre-registered sentence. Both are therefore reported, labelled as post hoc, under "verdict_text":
  - P3 reads "phase-related, e.g. coincide". The data show tight phase locking (R ≥ 0.98) at a fixed, non-zero offset for most channels.
  - P2 reads "ρ > 0, p < 0.05, if Δ varies". The correlation is significant in all three data sets, but the reliability gate classifies the result as untestable.
- Neither reading changes the model decision. The only mechanism result that feeds the model is P4.

**B3. ACMT excluded from the 1-Hz group.** (Clarification.)
- ACMT ("ACMS timing used") is a timing word, not an analog channel.
- Its "dropouts" have a different burst structure: interval percentiles 25/68/207 s and no 1,099-sample periodicity.

## C. Synthetic data pipeline

**C1. Float32 representability.** (Pipeline, before Gate 0.)
- Every value in the real files is exactly representable in float32. The probe found 100 % in all group channels of all inspected files.
- So float64 synthetic channels are rounded through float32 before writing. This is part of "cast to that file's original dtype": the recorded values are float32 values stored in float64 containers.
- This is also applied at L0, which has no lattice.
- Integer containers (FF, uint16) are written with `rint` and clipped to the dtype range. Negative fuel flow cannot be stored, so at L0–L4 noise below zero is clipped to 0. This is a property of the container, not of the model.

**C2. The VRTG lattice.** (Clarification.)
- The VRTG values are `float32(code)·float32(0.002289) + float32(−3.375)`, computed in float32. Code 0 is the −3.375 g sentinel.
- This was fitted on CAL and reproduces all 478 distinct CAL values bit for bit.
- The param_table "LSB" (0.002288818359375) is the minimum float spacing, not the scale.

**C3. Gate-0 fix 1: low-pass edge padding.** (Pipeline fix after Gate 0 v1.)
- Gate 0 v1 (`results/gate0_v1.json`) separated FULL from real partly on first and last samples, most strongly at f_c = 0.05 Hz.
- Cause: `sosfiltfilt` was padding with its default (about 15 samples). That leaves a start-up transient at the record edges. On CAL, |x[0] − truth[0]| had a p90 of 8.1 LSB at 0.05 Hz and 0.01 LSB at 0.2 Hz.
- Fix: odd padding of 3·rate/f_c samples. The p90 falls to 0.003 LSB.
- The same pipeline applies to real and synthetic data. The model was refitted on CAL with the fixed pipeline. Parameters changed by < 1 % (`fit_report_v1_*.json` vs `fit_report_*.json`). All synthetic files and features were regenerated.
- The v1 features are kept in `research_sources/settling_synthetic/features_v1/` for the with/without comparison in §F.

**C4. Gate-0 fix 2: numerical tolerance of the L5 gating rule.** (Implementation bug after Gate 0 v1.)
- The CAL gating threshold for N1_1 equals its engine-off reading exactly (1.78125 %).
- The low-pass of a constant 1.78125 returns 1.78125 − 1e-16. The `truth < g` test therefore zeroed the engine-off N1 of every synthetic L5+ file.
- Gate 0 v1 caught this: synthetic first sample 0 against real 1.78125 in 229 of 229 flights.
- The rule as specified, "below the lowest valid reading", is now implemented as truth < g − ½ step.
- Lower levels (L0–L4) are unaffected.

## D. Texture model (section 3); all fixed on CAL before TEST synthesis

**D1. L2 includes the common-mode split.** (Clarification.)
- The pre-registration names L2 "coloured component (AR(1)/Gauss–Markov per channel)", which is component 2 of the notes.
- Component 2 includes "for multi-unit platforms, split the variance into common-mode and independent parts". L2 therefore has:
  - a family common-mode AR(1), shared by the four engines;
  - independent per-engine AR(1) parts.
- Cross-*parameter* coupling within an engine (component 12) is **not** in the ladder and was not added.

**D2. Coloured texture restricted to the residual band.** (Design decision, made on CAL calibration evidence.)
- In the first CAL calibration, the AR(1) coefficient that best matched the residual lag-1 ACF went to the 0.995 bound. Most of that AR variance then lay below f_c, so the model added slow wander of up to 1 % N1 to the truth.
- The AR(1) series is therefore passed through the same zero-phase (1 − low-pass) filter that defines the residual. φ is capped at 0.98.
- Even so, the AR(1) shape cannot reach the measured residual lag-1 ACF; φ stays at the cap for every engine channel. This is a limitation of the pre-registered model form and is reported as a finding (REPORT §7):
  - N1 0.45 against 0.62;
  - EGT 0.42 against 0.53;
  - FF 0.38 against 0.52.

**D3. Parameters calibrated by simulation.** (Clarification.)
- σ per (channel, regime), common-mode scales, φ and tail mixtures are calibrated by the method of simulated moments on 50 CAL flights.
- Each round generates synthetic data, measures it with the identical pipeline, and updates the parameters.
- The targets come from all 152 CAL flights. Per-level calibration logs are in `results/fit_report_<fc>.json`.

**D4. L3 interpretation.** (Clarification.)
- L0 already has σ per (channel, regime). L3 therefore adds the *within-regime* multipliers of component 3:
  - power-setting bins of the engine's own N1 truth, or CAS bins for VRTG;
  - a log-normal intensity multiplier per regime segment. Its spread is the covariance of half-segment log-SDs on CAL, which is unbiased for the true spread.

**D5. L5 gating.** (Clarification.)
- y = 0 when the truth is below the channel's lowest valid reading on CAL: the 5th percentile across flights of the per-flight minimum non-zero value. This applies to N1, N2 and FF.
- EGT is not gated, because its engine-off reading is ambient temperature, not zero.

**D6. L6 uses (Δ, w, p) only.** (As pre-registered.)
- The boxcar fit also estimates a background loss p_out = 1.0e-3. The pre-registered L6 has no background term, so p_out is set to 0 and the ~3 % of events outside the window are not modelled.
- L6′ keeps its own "good-state" loss, p_good = 2.3e-5, as in the old model.

**D7. T2 when engines are not running.** (Smallest change that keeps the intent.)
- truth_common is the weighted mean of the engines that are running. The weight ramps from N2 30 % to N2 45 %.
- An engine that is shut down (single-engine taxi, start) keeps its own truth.
- Otherwise T2 would show all four engines running whenever any one was, which is an operational difference, not texture.

**D8. VRTG is not run in T2.** T2 changes only the engine channels, so the VRTG arrays in T2 files are identical to T1 at the same level.

## E. Discriminators (section 4)

**E1. Take-off roll has no 64-s or 300-s windows.** (Impossible as written.)
- The take-off roll (PH 3 on the ground) lasts 25–30 s.
- It is therefore represented only by whole-segment features. The minimum segment is 20 s.

**E2. How the regimes are defined.** (Clarification.) Everything is taken from channels outside the group, so the real and synthetic versions of a flight get identical windows.

| Regime | Definition |
|---|---|
| ground | WOW = 0 and PH ∈ {1, 2} |
| take-off roll | WOW = 0 and PH = 3 |
| climb | airborne and PH = 4 |
| cruise | airborne and PH = 5 |
| descent | airborne, PH = 6 and ≥ 3,000 ft above the landing field (median ALT after the last touchdown) |
| approach | airborne, PH = 6 and < 3,000 ft above the landing field |

**E3. Whole-segment features.**
- These use the longest run of each regime. Each flight gets one row: segment features concatenated over the six regimes, plus the regime variance ratios.
- These rows cannot be TAT-matched. The 64-s and 300-s window classifiers are matched on regime × 10 °C TAT bin.

**E4. Equal flight counts after matching.**
- Flights with no matched 64-s window are dropped. The larger class is then randomly reduced to the size of the smaller.
- n per class:

| Comparison | n per class |
|---|---|
| sim vs real | 229 |
| tail | ≤ 110 |
| July subset | ≤ 46 |
| temporal | ≤ 43 |

**E5. MiniRocket is fitted once per comparison on all windows.**
- This step is unsupervised and does not use the labels.
- The ridge classifier is fitted only on the training folds.
- This saves 15 MiniRocket fits per comparison.

**E6. Hyper-parameters fixed in advance.**
- LR: C = 0.1.
- GB: 200 iterations, learning rate 0.05, 15 leaves, 30 % of features per split.
- Ridge: α by exact leave-one-out on the training fold.
- Nothing was tuned.

**E7. Gate 0 scope.** (Clarification.)
- Gate 0 binds the simulation comparisons.
- It is reported for every level. Lattice (L0) and validity-gating (L0–L4) cues are by design part of the ladder, not pipeline artefacts. The binding test is FULL (L6 T1, L7 = T2-L6) and L6′.
- For the real-vs-real tail baseline, the metadata AUC is reported as information only. Record lengths, first and last samples and sentinel counts are genuine differences between tails, not pipeline artefacts.

**E8. Fewer permutations where 1,000 was not affordable.** See section F, filled in after the runs.

## F. Filled in after the runs

(see below)

## G. Stopped early (2026-10-14 ~14:55 IST)

The user and coordinator stopped round 1 before the FULL sim-vs-real comparisons finished. The pre-registered §6 verdict is **not issued**.

- **Reason:** the primary rule is non-informative (the tail baseline is at AUC ceiling), and validation pivoted to the behavioural battery (round-2 prereg, commit f6aa660).
- **Dropped:** FULL comparisons, family ablations, ladder L1–L5 and L6′, f_c sensitivity, the July subset, Kaggle shards a–d and f–h. shard_e output is unused.
- **Record:** `CLOSEOUT.md` lists the completed results and the lessons.
