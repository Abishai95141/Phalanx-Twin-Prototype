# MF1-D: What makes real fast-band N1–N2 low? (CAL-only diagnostic)

**Context.** Real fast-band (>0.2 Hz) correlations from Tail 652:

| Pair | Correlation |
|---|---|
| N1–N2 | **0.47** |
| N1–FF | 0.65 |
| N2–FF | 0.67 |
| N1–EGT | 0.56 |

Real B2 lags: FF→N2 −0.50 s, N2→N1 +0.50 s, FF→N1 0.00 s (`docs/behavioural_targets.md`).

AD-46 assumed that the low N1–N2 value needs an **LP-specific independent disturbance** (`fan_face`). E1 found
that, under the adopted control law (AD-50), every `fan_face` mix that lowers N1–N2 also drives N1–FF negative,
and N1–EGT came out ≈ 0. The joint target was not reached (`docs/build_gates/E1_verifier_report.md` §8).

Before choosing a mechanism, establish **from real data** what the low zero-lag correlation consists of. A low
zero-lag correlation can come from four sources:
- **(a) phase:** coherent but lagged motion (the fan follows the core by about 0.5 s; in the fast band that is a
  large phase angle);
- **(b) independent variance:** LP-specific or core-specific input, giving coherence < 1;
- **(c) texture:** quantisation and recorder lattice noise, which is independent per channel;
- **(d) common-mode driving:** A/T or PLA activity versus disturbance-driven motion.

Each source points to a different model mechanism. This diagnostic is the non-parametric half of round-2 H-c
(REPORT §8, items 1 and 3).

**Owned path:** `analysis/mf1_lp_structure/` only:
- `PREREGISTRATION.md`;
- `code/`;
- `results/`;
- `README.md`;
- `DEVIATIONS.md` if needed.

Do not edit `src/`, `configs/`, `tests/` or `docs/`.

**Read:**
- `RULES.md`;
- `docs/build_briefs/_common.md`;
- `docs/behavioural_targets.md`;
- `analysis/settling_experiment_round2/`: PREREGISTRATION, REPORT §3/§8, the loaders and `src/`;
- `src/phalanx/validation/`: the battery band definitions, `FlightRecord`, the `dashlink.py` adapter;
- AD-31, AD-46, AD-50 in `docs/architecture.md`;
- the report and notes on fan/core coupling and quantisation (grep `N1`, `fan lag`, `quantis`, `native step`).

## Data hygiene (binding)

- **Only Tail 687 archive-1 CAL flights.** The split is in `analysis/settling_experiment/results/splits.csv`, and
  the MAT files are under the main checkout's `research_sources/datasets/dashlink_tail687/raw/mat/` (read-only;
  use the absolute path).
- **Never read, list or load `research_sources/datasets/dashlink_tail687/raw2/`.** Add a guard that refuses any
  path containing `raw2`.
- Do not read Tail 652 or 687-TEST. Their published medians in `docs/behavioural_targets.md` are for comparison
  only.
- **Pre-register.** Commit `PREREGISTRATION.md` on your branch **before reading any flight data**. It holds:
  - the statistics;
  - the band and segment rules, matching B1/B2 so the numbers are comparable;
  - n and its justification;
  - the sample → verify → scale plan;
  - the interpretation rules below, made precise.

## Statistics (per flight, within engine; engine 1, with engine 2 as a replicate)

**Pairs:** N1–N2, N1–FF, N2–FF, N1–EGT, N2–EGT, FF–EGT.

1. **Zero-lag fast-band correlation**, with the exact B1 estimator. It must reproduce the B1 CAL-scale numbers;
   that is the sanity check.
2. **Band-averaged magnitude-squared coherence and phase** (Welch; state the window and dof):
   - the equivalent delay from the phase slope, to compare with the B2 lags;
   - the **coherent-variance fraction** of each channel.
3. **Decompose 1 − r into a phase loss and a coherence loss.** Compare the observed r with the "lag-only ceiling":
   the r obtained if the coherence were 1 at the observed cross-spectral phase and gain.
4. **Partial coherence:**
   - N1–N2 given FF;
   - N1–FF given N2;
   - the multiple coherence of N1 on {N2, FF}.

   These show whether N1 carries input the core does not see.
5. **Texture floor.** For each channel, the fast-band variance against the variance of independent quantisation
   noise: native step and recorder lattice, Δ²/12, using `native_step_cal.json` and the round-2 double-quantiser
   results. Report the r ceiling that texture alone implies.
6. **Splits:**
   - A/T engaged vs manual (round-2 post-hoc segmenting);
   - by phase: climb, cruise, descent;
   - cross-engine coherence of the N1-specific residual, to tell an aircraft-common source from an
     engine-specific one.

## Interpretation rules (make them precise in the pre-registration)

- **Phase-dominated.** The N1–N2 coherent fraction is high and the phase loss explains most of 1 − r. Then the
  low N1–N2 is mostly **dynamic** (fan lag, spool dynamics), and the model mechanism priority is the LP spool
  dynamics and loop. An independent `fan_face` input is then secondary.
- **Coherence-dominated, beyond the texture floor.** Independent LP-specific variance is needed (AD-46). Report
  whether that variance is aircraft-common or engine-specific across engines.
- **Texture-dominated.** Texture handles it (M13). Then the truth-level target is higher than 0.47; state that
  truth-level target.
- **Mixed outcomes.** Report the shares with CIs.
- **Also report** what makes N1–EGT +0.56 and N1–FF +0.65 under each split. This tells W2.4a-1 whether A/T
  common-mode driving carries the joint structure.

## Sample

1. **Verify on 5 CAL flights:** formats, segments, the B1 sanity check, and a plot of each spectrum.
2. **Scale** to the minimal n giving a bootstrap 95 % CI half-width ≤ 0.05 on the median coherent fraction and
   on the median phase-loss share for N1–N2. Write the n rule down before scaling.
3. Use the full CAL set only if that rule demands it.

Every result file states n.

## Report (final message)

- A table per pair: r, coherent fraction, phase/coherence loss shares, equivalent delay, texture-implied ceiling,
  with CIs and n; split by A/T vs manual and by phase.
- The verdict per the pre-registered rules, plus a mechanism recommendation for MF1. **State its evidence tag
  and limits;** the coordinator decides.
- Commits on your branch with clean `git status`. Do not push or merge.
