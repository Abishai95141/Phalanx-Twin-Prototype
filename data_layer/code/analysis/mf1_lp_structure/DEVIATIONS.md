# MF1-D deviations from PREREGISTRATION.md (commit 62f8f8f)

Each entry: date, what changed, why, and how results are reported both ways. All entries below were written at
the verification stage (5 flights, `results/verify/log_verify.md`), before scaling.

## D1. In-flight classes added; pooled estimator for in-flight manual control (2026-10-15, verification)

**Finding that triggered it (V2).** The B1 airborne rule (all four N1 > 25 %) admits taxi samples at ground idle,
because ground-idle N1 sits at 25–26 % (round-2 REPORT §6 item 4 noted the threshold effect). On the 5
verification flights, PH 2 (taxi) is 7–21 % of the ALL class, and the pre-registered **MAN class (ATEN = 0) is
80–90 % taxi** (PH 2), with the rest in final approach (PH 6) and rollout (PH 7). In-flight manual throttle exists
only in short final-approach runs (224–1,316 samples per flight). So the pre-registered AT vs MAN contrast is
mostly "in flight under A/T" vs "taxi", which confounds A/T engagement with ground operation. That does not answer
question (d) (A/T common-mode driving vs disturbance-driven motion in flight).

**Change.**
- Four classes are added (`code/extract.py`): FLT = airborne rule ∧ PH ∈ {4, 5, 6}; TAXI = airborne rule ∧ PH = 2;
  AT_FLT = FLT ∧ ATEN = 1; MAN_FLT = FLT ∧ ATEN = 0. They use the pre-registered estimators and per-flight
  inclusion rule (≥ 600 samples, K ≥ 6).
- Because in-flight manual runs are short, MAN_FLT rarely meets K ≥ 6 per flight. For the in-flight A/T contrast
  the **pooled-spectrum estimator** (pre-registered as a sensitivity, §5) is used as the primary estimator, over
  every segment the flights contribute (K ≥ 1), with the flight bootstrap. The contrast is also reported within
  approach only (AT_DES vs MAN_DES, pooled), because in-flight manual is almost all in PH 6.
- Spectra are therefore cached for any class with K ≥ 1; per-flight statistics still require the pre-registered
  inclusion rule, so nothing pre-registered changes.
- Coverage: the split-coverage rule (§7.3, ≥ 15 contributing flights) is applied to MAN_FLT as "≥ 15 flights
  contributing at least one MAN_FLT segment"; the prefix is extended in steps of 10 if needed.

**Both ways.** The pre-registered AT/MAN classes are reported unchanged, next to FLT/TAXI/AT_FLT/MAN_FLT.

## D2. V4 (spectral reconstruction) fails in 2 of 12 cells; cause is sample coverage (2026-10-15, verification)

**Result.** Median over the 5 flights of |r_spec − r_B1| is ≤ 0.03 in 10 of 12 (engine, pair) cells; it is 0.055
for engine-1 N2–EGT and 0.035 for engine-2 N1–N2 (`results/verify/log_verify.md`, V4 table).

**Investigation.** The time-domain r on exactly the samples covered by the Welch segments (r_seg) differs from
r_spec by a median ≤ 0.021 in every cell, so Hann weighting is not the cause. All airborne-rule samples outside
the Welch segments are PH 2 taxi samples in short runs at the 25 % N1 threshold (30–1,378 samples per flight,
0.2–9 % of ALL). A few hundred high-variance taxi samples can move r_B1 by up to 0.10–0.13 in single flights
(e.g. engine-2 N1–N2 0.431 with them, 0.331 without, flight 687200107202208).

**At the final n (20 flights).** The median |r_spec − r_B1| is 0.014–0.044 per (engine, pair) cell; 3 of 12 cells
exceed 0.03 (engine-1 N2–FF 0.044, engine-1 N2–EGT 0.041, engine-2 N2–EGT 0.037). The primary pair N1–N2 is
0.024–0.025 on both engines (`results/tables.md` §9).

**Handling (as pre-registered for this case, §6).** The decomposition is interpreted relative to r_spec. r_B1 and
r_seg are reported alongside, and the FLT class (in-flight phases only) shows the result without taxi. The verdict
text states the discrepancy.

**Implication for the build (finding, not a deviation).** B1's fast-band targets (N1–N2 0.47 on 652, 0.44 on CAL)
pool in-flight samples with taxi samples that pass the 25 % N1 rule. A proxy-mode comparison is only fair if the
synthetic flights reproduce that composition (taxi segments at ground idle near the threshold), which the round-2
running-state PROXY did not (round-2 REPORT §6 item 4).

## D3. Texture-first decomposition added as a sensitivity (2026-10-15, after the first full run at n_split)

**Finding that triggered it.** In the low-power classes (climb, cruise) the pre-registered texture term L_tex
(ordering A, §4.3) and the pre-registered truth-level r disagree. Example, cruise N1–EGT (engine 1): texture
de-attenuation raises r from 0.07 to 0.15, but the ordering-A texture share is only 0.05 of 1 − r. The reason is
structural, not numerical: ordering A computes the coherence-1 ceiling r_lag on the *observed* amplitude spectra,
which already contain the texture power, so texture lowers r through the weights w_b (that part is booked as
"dynamic"), and its coherence effect is multiplied by cos φ_b, which is negative in the high sub-bands where white
texture lives. Ordering A therefore under-states texture when texture is a large part of the fast-band power.

**Change.** A texture-first split is reported next to ordering A (`spectral.texture_first_decomposition`,
self-tested: 19/19 PASS): independent texture adds power but no cross-power, so it is removed first and exactly
(r_truth − r), and the truth-level loss 1 − r_truth is then split into dynamic (1 − r_lag*) and beyond-texture
(r_lag* − r_truth) parts on the texture-free spectra. Shares are fractions of the observed 1 − r. The verdict is
also evaluated with these shares (label "TF") under T_q, T_lo and T_hi.

**Both ways.** The pre-registered ordering A remains the primary verdict cell. For the primary cell (ALL, N1–N2)
texture is 1–2 % of the fast-band power, so the two splits agree to within 0.02 there; they differ materially only
in the climb and cruise classes and for pairs involving FF or EGT, where the TF numbers are the ones to use.

## D4. V3 at the final n: one of 12 cells misses its tolerance by 0.004 (2026-10-15, final stage)

**Result.** At n_final = 20 the engine-1 N1–FF median r_B1 is 0.672 [0.62, 0.70] against the published 51-flight
fold-0 median 0.628: difference +0.044, tolerance max(0.03, CI half-width) = 0.041. The other 11 cells pass
(`results/tables.md` §9).

**Investigation.** The estimator is not in question: r_B1 is the battery's own `b1_stats` and equals this
pipeline's time-domain r to < 1e-12 on every flight (V3, verification stage). The published value lies inside the
bootstrap CI of the 20-flight median (the CI is asymmetric, so the half-width rule is slightly stricter than the
CI). At n_split = 30 the same median is 0.65 [0.62, 0.70] (difference +0.02, within tolerance). The difference is
sampling between two partly overlapping CAL subsets, not a pipeline effect. No action beyond reporting; the
pre-registered tolerance is kept as written and the cell is reported as a marginal miss.
