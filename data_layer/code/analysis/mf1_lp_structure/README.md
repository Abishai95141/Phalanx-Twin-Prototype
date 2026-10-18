# MF1-D: what makes real fast-band N1–N2 low? (CAL-only diagnostic)

Work package MF1-D (brief `docs/build_briefs/MF1_lp_structure_diagnostic.md`). This is the non-parametric half of
round-2 H-c (REPORT §8, items 1 and 3). It fits no model and tunes nothing. It uses only Tail 687 archive-1 CAL
flights. Archive 2, Tail 652 and 687-TEST were never read.

- **Pre-registration:** `PREREGISTRATION.md`, committed before any flight data was read (commit 62f8f8f, 05:17 IST).
- **Deviations:** `DEVIATIONS.md` D1–D4.
- **Results:** `results/tables.md` (all tables), `results/summary.json` (machine-readable medians and CIs),
  `results/perflight_primary.csv` (per-flight values, engines 1–2).
- **Credibility ceiling:** NASA-STD-7009B Level 2 against proxy data. The proxy is a four-engine airliner with a
  hydromechanical/TMS-era control, not the F404-IN20.

## Answer in one paragraph

Real fast-band N1–N2 (≈ 0.43) is low **mainly because of phase**. Within the fast band, N1 lags N2 by about
55° over 0.19–0.5 Hz, where 82–84 % of the fast-band power sits (median), and by about 96° over 0.5–1 Hz. The
equivalent delay is 0.33 s; the best phase description is a 0.15 s delay plus a 0.38 s first-order lag. Even at
perfect coherence, that phase limits the zero-lag correlation to r_lag = 0.49 (median over flights). Coherence is moderate (CF ≈ 0.69 of N1's fast-band
power is coherent with N2). Texture is negligible for this pair: 1–2 % of the fast-band power under the
quantisation floor, 7–8 % under the empirical high-frequency floor.

The pre-registered verdict is **MIXED**, because the "coherent fraction ≥ 0.70" condition misses narrowly
(0.69 [0.67, 0.72]). The shares are:
- dynamic (phase) share of 1 − r: 0.92 [0.88, 0.93];
- beyond-texture independent variance: 0.09 [0.08, 0.12]; 0.18 [0.16, 0.22] in the Shapley split;
- texture: ≈ 0.

The dynamic share is the largest component on engine 2, under every texture floor and decomposition order, and
in every flight-phase class.

## Data, hygiene and commands

- **Flights.** 687-CAL (152 flights, `analysis/settling_experiment/results/splits.csv`). A fixed order
  (`results/flight_order.json`, `phalanx.core.rng`, scenario `mf1-diag`) was written from file names only, before
  any data was read; samples are prefixes of it.
- **Guard.** MAT files are read read-only through `phalanx.validation.dashlink` (its own `raw2` guard is active).
  `code/common.py: guard_path` refuses:
  - any path containing `raw2`;
  - any MAT directory containing `raw2` or `652`;
  - any file outside the declared directory;
  - any non-CAL file.

  It is self-tested.
- **Cache.** A per-flight cache of derived spectra (no raw samples) lives in the git-ignored `runs/mf1/cache`.
- **Commands** (from this folder; `M=/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat`,
  `C=<worktree>/runs/mf1/cache`, `PY=<main repo>/.venv-build/bin/python`):

```bash
$PY -I code/select_flights.py results/flight_order.json   # fixed order (names only)
$PY -I code/selftest.py results/log_selftest.txt          # 19 synthetic-signal checks, no data
$PY -I code/run.py verify $M $C                           # 5-flight verification (V1-V6)
$PY -I code/run.py nrule  $M $C                           # pre-registered n rule + split coverage
$PY -I code/final.py $C                                   # statistics, verdicts, pooled spectra, figures
$PY -I code/report.py                                     # results/tables.md
```

**Reproducibility.** A clean re-run from an empty cache reproduced `summary.json`, `tables.md`,
`perflight_primary.csv` and `n_rule_log.md` byte for byte. The runtime is about 5 minutes on a laptop.

## Sample sizes (RULES.md rule 1)

| Stage | n | Justification |
|---|---|---|
| Verification | 5 (`order[:5]`) | Pre-registered smoke stage: formats, segments, B1 sanity, spectra (`results/verify/log_verify.md`) |
| Primary (n_final) | **20** | Pre-registered n rule: bootstrap 95 % CI half-width ≤ 0.05 on the medians of CF_N1, CF_N2 and s_dyn (engine 1, ALL). At n = 20 (the rule's floor) the half-widths are 0.027, 0.029 and 0.024 (`results/n_rule_log.md`) |
| Splits (n_split) | **30** | Pre-registered coverage rule: ≥ 15 contributing flights per split class. MAN reached 18 only at n = 30; the other classes had 19–30. In-flight manual segments came from 23 flights (D1) |

The full CAL set was not needed.

## Results (engine 1; medians over flights with flight-bootstrap 95 % CIs; full tables in `results/tables.md`)

### Per pair, class ALL (n = 20)

| Pair | r_B1 | r_lag ceiling | CF cause / effect | s_dyn (A) | s_tex (TF) | s_beyond (TF) | τ_eq (s) | B2 (s) | texture-only ceiling | truth-level r |
|---|---|---|---|---|---|---|---|---|---|---|
| N1–N2 (N2→N1) | 0.43 [0.38, 0.47] | 0.49 [0.40, 0.53] | 0.70 / 0.69 | 0.92 [0.88, 0.93] | 0.01 | 0.09 [0.08, 0.13] | 0.33 | 0.50 | 0.99 | 0.43 (0.46 with T_hf) |
| N1–FF (FF→N1) | 0.67 [0.62, 0.70] | 0.86 [0.84, 0.88] | 0.59 / 0.64 | 0.45 [0.41, 0.51] | 0.23 [0.20, 0.26] | 0.38 [0.34, 0.45] | 0.18 | 0.00 | 0.89 | 0.77 [0.73, 0.79] |
| N2–FF (FF→N2) | 0.60 [0.56, 0.63] | 0.76 [0.73, 0.81] | 0.62 / 0.67 | 0.62 [0.57, 0.72] | 0.19 [0.13, 0.28] | 0.30 [0.26, 0.35] | −0.16 | −0.50 | 0.89 | 0.72 [0.67, 0.76] |
| N1–EGT (N1→EGT) | 0.57 [0.53, 0.62] | 0.75 [0.73, 0.77] | 0.49 / 0.47 | 0.58 [0.54, 0.64] | 0.14 [0.11, 0.15] | 0.43 [0.38, 0.48] | 0.25 | 0.25 | 0.89 | 0.61 [0.58, 0.66] |
| N2–EGT (N2→EGT) | 0.08 [0.01, 0.11] | 0.02 [−0.05, 0.06] | 0.69 / 0.65 | 1.02 | 0.00 | 0.00 | 0.66 | n/a | 0.89 | 0.05 |
| FF–EGT (FF→EGT) | 0.32 [0.29, 0.37] | 0.37 [0.30, 0.40] | 0.51 / 0.54 | 0.94 [0.91, 0.98] | 0.09 | 0.10 | 0.53 | 0.75 | 0.80 | 0.39 [0.35, 0.42] |

Engine 2 replicates the N1–N2 row (0.42, s_dyn 0.91, CF 0.69, τ_eq 0.32 s) and the structure of the other rows.
N2–FF is higher on engine 2 (0.71 vs 0.60), as in the published fold-0 medians (0.695 vs 0.577). The B1 sanity check
reproduces the published 51-flight CAL fold-0 medians in 11 of 12 cells; engine-1 N1–FF misses its tolerance by
0.004 (D4).

### N1–N2 by class (n = 30)

| Class | r (class B1) | CF_N1 | s_dyn (A) | s_beyond (A) | τ_eq (s) | Verdict (A, T_q) |
|---|---|---|---|---|---|---|
| AT (A/T engaged) | 0.35 | 0.64 | 0.95 | 0.06 | 0.30 | MIXED |
| MAN (not engaged; 80–90 % taxi, D1) | 0.53 | 0.80 | 0.92 | 0.09 | 0.27 | **PHASE-DOMINATED** |
| FLT (PH 4–6) | 0.37 | 0.61 | 0.88 | 0.12 | 0.33 | MIXED |
| AT_FLT | 0.25 | 0.46 | 0.91 | 0.10 | 0.32 | MIXED |
| CLB (climb) | 0.29 | 0.39 | 0.86 | 0.13 | 0.20 | MIXED |
| CRZ (cruise) | 0.20 | 0.47 | 0.87 | 0.10 | 0.23 | MIXED (texture material in the TF split: 0.31) |
| DES (descent/approach) | 0.41 | 0.72 | 0.91 | 0.09 | 0.33 | **PHASE-DOMINATED** |
| TAXI | 0.48 | 0.72 | 0.94 | 0.06 | 0.32 | **PHASE-DOMINATED** (n = 13) |

The dynamic share is 0.86–0.95 in every class. The coherence is high where the fast-band power comes from lever
or regime activity (descent/approach, taxi) and low in climb and cruise. In cruise, quantisation is 22–38 % of the
fast-band power (texture-first split, texture share 0.31).

### Independent N1 input (partial and multiple coherence)

- **Partial coherence.** N1–N2 given FF is 0.28 [0.25, 0.33]: N1 and N2 share some coherent motion that measured
  FF does not carry. N1–FF given N2 is 0.24.
- **N1 unexplained beyond texture.** 24 % [20, 27] of N1's fast-band power is not explained by its own N2 and FF.
  The figure is 33 % [27, 39] in flight and 41 % [36, 45] in A/T flight.
- **N2 unexplained beyond texture.** For N2 given (N1, FF) the figures are 18–23 %.
- **Difference N1 − N2.**
  - ALL: +0.05 [−0.01, 0.10] (undetermined).
  - In flight (FLT): +0.09 [0.04, 0.14], and +0.04 [0.04, 0.07] under the high texture floor.
  - AT_FLT: +0.09 [0.07, 0.15].

  So in flight N1 carries modestly more independent input than N2.
- **Cross-engine share of the N1-specific residual.** The common share |γ| with the partner engine is
  0.48 [0.40, 0.52], or 0.53 after texture correction. About half is aircraft-common and half engine-specific;
  by the pre-registered rule this is "mixed". The residual is 9–10× its quantisation texture (≈ 2× the empirical
  HF floor), so it is not texture.

### What carries N1–FF (+0.67) and N1–EGT (+0.57)

- **Phase structure (the dominant factor for every pair).**
  - N2 leads measured FF (τ_eq −0.16 s; B2 −0.5 s).
  - FF leads N1 (0.18 s).
  - N1 leads EGT (0.25 s).
  - N2→EGT is 0.66 s, about −88° over 0.19–0.5 Hz. So N2–EGT ≈ 0 although their coherence is 0.65–0.74.

  N1–EGT is positive because EGT follows N1 closely in time.
- **Lever (PLA) path.** The lever carries a minority of each correlation:
  - ALL: 0.16–0.29;
  - A/T engaged: N1–FF 0.29 [0.21, 0.34], N1–EGT 0.20 [0.07, 0.25];
  - A/T in flight: 0.05–0.13.

  The pre-registered joint-structure rule therefore gives **"partial"**: A/T lever motion does not carry the joint
  structure.
- **Partner-engine path.** Components coherent with the partner engine's N1 carry most of each N1 correlation:
  - ALL: 0.78–0.89;
  - A/T engaged: 0.66–0.87 (N1–FF 0.73, N1–EGT 0.66);
  - A/T in flight: 0.44–0.76.

  The fast-band joint structure is carried by **aircraft-common motion that is mostly not visible in the
  recorded lever angle**.
- **Texture.** It matters for the FF and EGT pairs. FF texture (8 lb/h lattice) is 17–20 % of FF fast-band power,
  and EGT texture is 16–20 %. Truth-level targets are therefore higher than the B1 values: N1–FF 0.77, N2–FF 0.72,
  N1–EGT 0.61.
- **In-flight control mode** (pooled spectra, D1; in-flight manual is almost all final approach).

  | Pair | Manual r | A/T r | Manual CF_N1 | A/T CF_N1 | Paired difference in r (A/T − manual) |
  |---|---|---|---|---|---|
  | N1–N2 | 0.53 | 0.28 | 0.80 | 0.50 | −0.25 [−0.37, −0.16] |
  | N1–FF | 0.78 | 0.52 | – | – | – |
  | N1–EGT | 0.70 | 0.43 | – | – | – |

  The phase-matched approach-only contrast agrees: N1–N2 manual 0.53 vs A/T 0.36. The dynamic share stays ≈ 0.9
  in both modes. Large manual lever moves drive the engine coherently, while the A/T-engaged fast band carries more
  independent variance.

  One flight flown manually throughout had low N1–N2 coherence (CF 0.26). The contrast therefore reflects lever
  activity, not the control mode as such.

## Verdict (pre-registered rules, PREREGISTRATION.md §8)

**MIXED: phase-dominant, with a small independent component and negligible texture.**

| Rule | Value | Met? |
|---|---|---|
| CI lower bound of s_dyn > 0.5 | 0.88 | yes |
| median CF_N1 ≥ 0.70 | 0.69 [0.67, 0.72] | **no, by 0.01** |
| s_beyond CI lower bound > 0.5 | 0.08 | no |
| s_tex CI lower bound > 0.5 | 0.00 | no |

**Components.**
- Dynamic: **material**.
- Texture: **negligible** (CI upper bound < 0.10 in every variant).
- Beyond-texture independent variance: "neither" in ordering A and in the texture-first split (0.09 [0.08, 0.13]);
  **material** in the Shapley split (0.18 [0.16, 0.22]).

**Robustness.**

| Label | Result |
|---|---|
| Replicated | yes; engine 2 is MIXED with the same shares |
| Texture-robust | yes; MIXED under T_q, T_lo, T_hi, T_hf and T_qi |
| Ordering-robust | yes; MIXED under A, Shapley and texture-first |
| Class-stable | no: AT, FLT, CLB, CRZ are MIXED (CF 0.39–0.64); MAN, DES, TAXI are PHASE-DOMINATED (CF 0.72–0.80). s_dyn ≥ 0.86 in every class |

The decomposition uses the spectral r. On individual flights r_B1 differs by up to 0.10–0.13, because of taxi
samples at the 25 % N1 threshold (D2). Over flights, the median absolute difference is 0.014–0.044 per
pair (0.024 for N1–N2); it exceeds the pre-registered 0.03 in 3 of 12 cells (N2–FF and N2–EGT), never for
N1–N2.

## Mechanism recommendation for MF1 (proposal; the coordinator decides)

Evidence tag: **[MEASURED: Tail 687 CAL, proxy airliner, n = 20/30 flights]**; for the Tejas,
**[TRANSFER: structure only]**.

1. **Priority 1: LP-spool dynamics and phase (M07 fan and LP-turbine response, with the M08 loop).**
   - Low fast-band N1–N2 is a phase effect in real data. The model must make N1 lag N2 by about 55° over
     0.19–0.5 Hz and about 96° over 0.5–1 Hz.
   - The N2→N1 gain should be ≈ 0.97–1.11 %/% over 0.16–0.54 Hz, falling to 0.49 at 0.79 Hz (median over
     flights).
   - Coherence should be ≈ 0.74 over 0.19–0.5 Hz.

   With that phase and the observed spectra, r(N1,N2) cannot exceed r_lag ≈ 0.49 at any coherence, so no large
   independent LP input is needed to reach 0.43–0.47.
   This is also the route that keeps N1–FF positive: FF→N1 is a small positive lag of 0.18 s, with N1–FF truth-level
   r 0.77. That avoids the E1 failure mode (a `fan_face` mix strong enough to lower N1–N2 drives N1–FF negative).
   Identify the fan and LP lag on transients (AD-34), and add a fast-band phase check, which B3 (i) lacks.
2. **Priority 2: a modest LP-specific disturbance (AD-46 `fan_face`), as a secondary mechanism.**
   - Size it so that roughly 20–25 % of N1 fast-band power (33–41 % in flight) is not explained by the own engine's
     N2 and FF.
   - About half of it should be common across engines (aircraft-common inlet or atmospheric component) and half
     engine-specific.

   Its cost to N1–N2 in real data is only 0.09–0.18 of 1 − r. It must not be the main lever on r(N1,N2).
3. **Common-mode driving.** The fast-band joint structure (N1–FF, N1–EGT, N1–N2) is mostly aircraft-common
   (partner-engine path 0.66–0.89; 0.44–0.76 in A/T flight), and the recorded lever carries only 0.05–0.29 of it.
   - For W2.4a-1, the A/T lever loop alone is not sufficient: an aircraft-common driver that is not the lever is
     needed. Candidates are inlet and atmospheric disturbance, or a command path that bypasses the lever angle;
     the data cannot tell which.
   - Lever activity raises coherence (manual approach segments).
4. **EGT.** N1–EGT +0.57 needs EGT to follow N1 closely: lag 0.25 s, about 27° over 0.19–0.5 Hz, with coherence
   about 0.55. N2→EGT is 0.66–0.81 s.
   - The E1 result of N1–EGT ≈ 0 indicates a wrong EGT phase relative to N1.
   - EGT also carries the largest independent share (s_beyond 0.43 of its loss with N1).
5. **Texture.** For N1–N2, M13 texture plays no role (truth-level target ≈ observed: 0.43, or 0.46 with T_hf). For
   the FF and EGT pairs the truth-level targets are higher (above), and M13 lowers them to the B1 values.

**Limits.**
- One proxy tail (airliner, hydromechanical/TMS-era control, four high-bypass engines), Mar–Sep 2001,
  20/30 of 152 CAL flights.
- Linear coherence measures. Within-class regime variation can appear as coherence loss.
- The 0.15 s pure-delay part of the N2→N1 phase cannot be told apart from recorder word-slot skew, which is
  unknown for these words (research notes Q8).
- The magnitudes (phase angles, lags, fractions) are airliner values. The F404-IN20 is a low-bypass, afterburning,
  FADEC-governed single engine, so only the structure transfers:
  - the phase-dominated low N1–N2;
  - modest independent LP input;
  - aircraft-common driving, which on a single engine is the inlet or atmosphere.

## Proposed decisions (for the decision register; not adopted here)

| Id | Proposal | Alternatives | What would change it |
|---|---|---|---|
| P-MF1-1 | MF1 resolves AD-46 under AD-50 by making LP spool dynamics (the fan phase lag) the primary mechanism for low fast-band N1–N2. `fan_face` stays as a secondary input sized to ≈ 20–25 % of N1 fast-band power, half common across units | Keep `fan_face` as the primary lever (E1 showed it breaks N1–FF); add a second LP path (LP-shaft torque) | W2.4a-1 reachability showing that the measured phase cannot be reached with M07/M08 structure; archive-2 results |
| P-MF1-2 | Add a fast-band phase acceptance check for N2→N1, N1→EGT and N2→EGT (sub-band phase and coherence, 0.19–1 Hz) to the W2.4a quick look. Today B3 (i) checks only coherence and gain, and only for PLA→FF and FF→* pairs | Rely on B1 and B2 only | Coordinator judgement on battery scope (a battery change needs a new pre-registration) |
| P-MF1-3 | Proxy-mode B1 comparisons must reproduce the taxi composition admitted by the 25 % N1 airborne rule (7–21 % of samples), or B1 is reported on PH 4–6 in addition | Ignore (adds up to ±0.1 per-flight noise in B1) | A battery revision |
| P-MF1-4 | Truth-level (pre-texture) targets for M07: N1–FF ≈ 0.77, N2–FF ≈ 0.72, N1–EGT ≈ 0.61, N1–N2 ≈ 0.43–0.46 (fast band, CAL proxy) | Use B1 values as truth targets | A different texture model in M13 |

## Files

| Path | Content |
|---|---|
| `code/common.py` | Constants, data guard, `phalanx.core.rng` streams |
| `code/select_flights.py` | Fixed flight order (file names only) |
| `code/spectral.py` | Welch estimator, sub-bands, pair decomposition, partial/multiple coherence, residual cross-coherence, texture power, texture-first split (D3) |
| `code/selftest.py` | 19 synthetic-signal checks (`results/log_selftest.txt`) |
| `code/extract.py` | Per-flight extraction to the git-ignored cache (guarded data access) |
| `code/analyse.py` | Per-flight statistics, bootstrap, pooled estimator |
| `code/run.py` | Verification and n-rule stages |
| `code/final.py` | Final statistics, verdicts, pooled spectra, figures |
| `code/report.py` | `results/tables.md` |
| `code/svgplot.py` | Dependency-free SVG plots (no plotting library in `.venv-build`) |
| `results/verify/` | V1–V6 log and per-flight spectra plots (5 flights) |
| `results/figures/` | Median coherence, phase, gain and power share per class |
| `results/n_rule_log.md`, `n_rule.json` | The n-rule trace |
| `results/summary.json` | Medians and CIs (compact: m = median, l/h = CI, n = flights; pooled v/l/h) |
| `results/perflight_primary.csv` | Per-flight values (engines 1–2, main classes) |

**Other observation.** A narrow coherent line near 1.6 Hz, with a weaker one near 1.2 Hz, appears in N1, N2, FF
and EGT. Median MSC is 0.67 for N2→N1 (`results/figures/median_spectra_ALL.svg`). It is coherent, so it is not
texture. The 1.5–1.75 Hz sub-bands hold about 2 % (1–5 %) of the N1 and N2 fast-band power. The origin
(aliased periodic component or recorder artefact) is unknown.
