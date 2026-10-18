# Settling experiment — pre-registration

**Question.** Can a residual-texture model learned from a proxy aircraft make synthetic recorder data
as hard to tell from real data as one real tail is from another? If not, the premise "learn texture
from the proxy" needs rework before any Tejas module depends on it.

**Status.** Written 2026-10-14, before any synthetic data were generated or any classifier was run.
Any deviation from this plan must be logged in `DEVIATIONS.md` with the date, the reason, and the
result both with and without the deviation.

---

## 1. Data and splits

| Set | Source | Use |
|---|---|---|
| **687-CAL** | Tail 687, archive 1 (`research_sources/datasets/dashlink_tail687/raw/mat/`), eligible flights from `analysis/dashlink_texture/results/eligible_flights.csv`; random 40 % | Fitting texture parameters **only** |
| **687-TEST** | The remaining 60 % of eligible Tail 687 flights | The real class; the synthetic versions of these flights |
| **652** | Tail 652, archive 8 (`~/phalanx/data/raw/dashlink_tail652/extracted/`, **read-only**), with the same eligibility rules | The real-vs-real tail baseline |

- The split is made with a fixed seed (`20261014`) and saved to `results/splits.csv` before anything else runs.
- The `_1` duplicate files are excluded.
- Tail 652's file dates span 2003–2010, against 2001 for Tail 687. Comparisons are therefore stratified by flight regime and TAT bin, and the season mix is reported.
- Where enough 652 flights exist, a month-matched subset is also reported.

**Channel group:** N1_1–4, N2_1–4, EGT_1–4, FF_1–4 (4 Hz, digital) and VRTG (8 Hz, analog).

## 2. Truth extraction and arms

Sentinels are identified with the existing `common.load_sentinels` / `clean` rules and linearly
interpolated before filtering. The truth is a zero-phase, 4th-order Butterworth low-pass of that cleaned signal.

| Cutoff f_c | Engine channels | VRTG | |
|---|---|---|---|
| **Primary** | 0.2 Hz | 0.5 Hz | |
| Sensitivity | 0.05 Hz and 0.5 Hz | 0.2 Hz and 1.0 Hz | Reported in full, but not used for the verdict |

- **Arm T1 (texture only).** Each channel's synthetic signal is Texture(lowpass(real channel)) for the same 687-TEST flight.
- **Arm T2 (texture + unit structure, engine channels only).** truth_common = lowpass(4-engine mean) per channel family. Each synthetic engine k = truth_common + b_k + Texture_k.
  - b_k is drawn from the fitted **fleet prior** of per-engine offsets and their flight-to-flight dynamics. It is not set to Tail 687's own offsets.

Synthetic flights are written as **MAT files**. Each is built by copying the real file and replacing only the channel-group arrays, cast to that file's original dtype. Real and synthetic data then pass through the identical `dlio.load_flight` path.

## 3. Texture model and ablation ladder

All parameters are fitted on **687-CAL only**, with the same truth extraction (residual = real − lowpass(real)).

| Level | Adds | Notes |
|---|---|---|
| L0 | iid Gaussian residual, σ matched per channel and regime; no quantisation | Straw man ("ideal + Gaussian noise") |
| L1 | Recording lattice: y = LSB·round(x/LSB), no artificial dither | |
| L2 | Coloured component (AR(1) / Gauss–Markov per channel) | |
| L3 | Regime-dependent variance multipliers | |
| L4 | Heavy-tail mixture | |
| L5 | Glitch words, validity gating, deadband / episodic freeze | |
| **L6 = FULL (T1)** | **Missingness from clock-domain slip** | Corrected model (see §5): the recorder samples each source on a clock that is offset Δ from the source's update clock. Reads that fall in a collision window of width w around a source update return the sentinel with probability p. Δ, w and p are fitted per acquisition path. Digital channels get stale or duplicate reads at slip points if, and only if, mechanism check P4 confirms them. |
| L6′ | L5 + the **old** independent periodic Gilbert–Elliott missingness | Comparator for the correction |
| **L7 = FULL (T2)** | L6 + per-engine bias and drift drawn from the fleet prior | |

## 4. Discriminators and features

- **Grouping.** All evaluation uses flights as the independent unit.
  - GroupKFold (k = 5, repeated 3×), with the real and synthetic versions of a flight kept in the same fold.
  - Window scores are averaged to a **flight score**, and AUC is computed at flight level.
  - 95 % CIs come from a flight-level bootstrap (2,000 resamples). Permutation tests shuffle labels at flight level (1,000 permutations).
- **Windows.** Regime-stratified windows (ground, take-off roll, climb, cruise, descent, approach) of 64 s and 300 s, plus whole-segment features. At most 4 windows per flight per regime. Equal numbers of flights per class in every comparison.
- **Gate 0 — trivial-cue audit.** A metadata-only classifier must be at chance before any other result counts. Its features: per-channel sample counts, record length, dtype, NaN presence, fraction of values on the lattice, histogram of value/LSB fractional parts, float bit-pattern statistics, sentinel counts, first and last samples. Pass means the 95 % CI of the AUC includes 0.5. If it fails, fix the **pipeline**, not the texture model, log the fix in `DEVIATIONS.md`, and re-run.
- **Discriminator ladder** (each applied to every comparison):
  - **D1:** per-channel two-sample tests (KS and Anderson–Darling) on residuals and on LSB-lattice histograms.
  - **D2:** texture features with regularised logistic regression and gradient boosting. Features:
    - σ/LSB and toggle rate;
    - fraction held, and run lengths of held values;
    - ACF at lags 1–20;
    - normalised band powers;
    - kurtosis, skew and 4σ exceedance;
    - sentinel count, spacing and periodicity;
    - cross-engine residual correlations;
    - regime variance ratios.
    catch22 is added if it installs cleanly.
  - **D3:** a MiniRocket/ROCKET-type classifier on residual windows. A variant on raw z-normalised windows is reported as a secondary result.
- **Feature families for ablation:** quantisation/lattice, noise level, spectral/ACF, tails, missingness/timing, cross-channel, levels.
  - **Primary verdicts use texture families only, never levels.** Levels are inherited in T1 and would trivially separate the tails.

## 5. Mechanism check: bursts as clock-domain slip

The predictions below are recorded before testing. Each is reported as confirmed, refuted or untestable.

- **P1.** The burst period at rate f equals 1/(f·Δ), with a single Δ across rates. The prior estimate is ≈910 ppm, against 917.6 ppm from the clock word (median over 590 flights).
- **P2.** The per-flight burst period tracks the per-flight clock-word slope (Spearman ρ > 0, p < 0.05), if Δ varies across flights.
- **P3.** Burst onsets at different rates on the same acquisition path are phase-related, e.g. 4 Hz bursts coincide with every second 8 Hz burst.
- **P4.** Digital channels show stale/duplicate or skipped samples at the same beat period. Tested on held-sample statistics during transients.
- **P5.** The collision window w = burst duration × Δ is roughly constant in absolute time across rates.

## 6. Decision rules

The verdict is given separately for each family: engine (T1 and T2) and VRTG (T1). AUC_x is the maximum over D2–D3 of the flight-level AUC on texture families.

- **Power check.** The L0 straw man must be detectable: AUC_L0 lower 95 % bound > 0.6. If it is not, the verdict is **INCONCLUSIVE (no power)**.
- **Primary (the user's criterion).** Compare AUC_sim (FULL) with AUC_tail (687-TEST vs 652, identical pipeline, matched regimes, equal flight counts).
  - **PASS** if AUC_sim ≤ AUC_tail.
  - **FAIL** if the one-sided 95 % bootstrap lower bound of (AUC_sim − AUC_tail) > 0.
  - **INCONCLUSIVE** otherwise.
- **Secondary (stricter).** Compare the same quantities against a within-tail temporal baseline (687-TEST Mar–May vs Jul–Sep).
- **Diagnosis (whatever the verdict).**
  - Run the ablation ladder L0 → FULL.
  - Report the feature-family ablation for the strongest discriminator.
  - Compare L6 with L6′.
  - Map each significant family to the texture component responsible.

## 7. Reproducibility

- Pinned `requirements.txt`; NumPy `SeedSequence` streams keyed by (flight, channel, component).
- The root seed is `20261014`.
- Every script is run with `-I` and data paths passed as arguments.
- `README.md` gives exact commands. SHA-256 hashes of the input archives are recorded in `results/manifest.json`.
