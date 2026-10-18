# MF1-D pre-registration: what makes real fast-band N1–N2 low? (CAL-only diagnostic)

**Written:** 2026-10-15 05:15 IST on branch `wp/mf1-diag` (from main 43831ed), **before any flight data was read**.
The commit that adds this file is the record. Only derived summaries already in the repository were read
beforehand (round-2 REPORT/JSON summaries, `native_step_cal.json`, frozen `mb.json`, `param_table.csv`, the split
file). Brief: `docs/build_briefs/MF1_lp_structure_diagnostic.md`.

Any change after this commit goes in `DEVIATIONS.md` with the date, the reason and results both ways.

## 1. Question

Real fast-band (> 0.2 Hz) zero-lag correlation of N1 and N2 within an engine is low (Tail 652: 0.47; 687-TEST:
0.43; 687-CAL fold 0: 0.44), while N1–FF (0.63–0.65) and N1–EGT (0.56–0.57) are higher, and N2–EGT is ≈ 0.04–0.08
on CAL. AD-46 assumed the low N1–N2 needs an LP-specific independent disturbance (`fan_face`). E1 found that under
the adopted control law (AD-50) every `fan_face` mix that lowers N1–N2 drives N1–FF negative
(`docs/build_gates/E1_verifier_report.md` §8).

**What does the low zero-lag N1–N2 correlation consist of, in real data?** Four candidate sources, each pointing
to a different model mechanism:

| Source | Signature in the estimators below | Model mechanism it points to |
|---|---|---|
| (a) phase | coherence high, phase large (the fan follows the core by ≈ 0.5 s; at 0.3 Hz that is 54°) | LP spool dynamics, fan lag, loop (M07/M08) |
| (b) independent variance | coherence < 1 beyond what texture explains | LP- or core-specific process input (AD-46 / AD-32) |
| (c) texture | coherence < 1, explained by independent quantisation / recorder noise | M13 (texture); the truth-level target is then higher than 0.47 |
| (d) common-mode driving | the correlation structure depends on A/T engagement or lever (PLA) activity | A/T outer loop (proxy), M04/M08 command activity |

This is the non-parametric half of round-2 H-c (REPORT §8, items 1 and 3). It fits nothing and tunes nothing.

## 2. Data and hygiene

- **Only Tail 687 archive-1 CAL flights**: set `687-CAL` (152 flights) of
  `analysis/settling_experiment/results/splits.csv`. MAT files are read read-only from the absolute directory
  passed as an argument (`/Users/abishaikc/Phalanx/research_sources/datasets/dashlink_tail687/raw/mat/`).
- **Guard** (`code/common.py: guard_path`, self-tested): refuses any path string containing `raw2` (Tail 687
  archive 2 is reserved for the AD-33 gate), any MAT directory string containing `raw2` or `652`, any file not
  directly inside the declared directory, and any file name not in the 687-CAL set. The phalanx loader's own
  `raw2` guard stays active (`allow_reserved` is never passed).
- **Not read:** archive 2, Tail 652, 687-TEST, round-2 synthetic outputs. Published 652/687-TEST medians in
  `docs/behavioural_targets.md` are for comparison only.
- **Loader:** `phalanx.validation.dashlink.load_record` (round-2 4-Hz alignment) for N1, N2, EGT, FF and PLA of
  engines 1–4 and PH (1 Hz held to 4 Hz); `phalanx.validation.dashlink.load_mat` for ATEN (A/T engage status,
  1 Hz), held to the 4-Hz grid exactly as round-2 `q02_at_leadlag.py` (`index = floor(t · rate)`). Files are only
  parsed with `scipy.io.loadmat`; nothing in them is executed. Python runs with `-I`.
- **Flight order** (fixed before any data is read): `results/flight_order.json`, a permutation of the sorted
  687-CAL list from `phalanx.core.rng` (root 20261015, stream `validation.flight_sample`, scenario `mf1-diag`,
  index 0). Every sample is a **prefix** of this order (nested), so scaling never re-draws flights. The first five
  (verification) are `687200107202208`, `687200105031623`, `687200108150546`, `687200107181544`, `687200107210730`.

## 3. Masks, band and segments (matching B1/B2)

- **Airborne rule:** all four N1 > 25 % (B1; `phalanx.validation.battery.stats.airborne_mask`).
- **Fast band:** x_fast = x − lowpass(x), Butterworth order 4, zero-phase (`sosfiltfilt`), f_c 0.2 Hz, applied to
  the whole record before masking (`phalanx.validation.battery.filters.lowpass`, the B1 filter). The fast operator
  is real and zero-phase, so it changes no cross-spectral phase.
- **Classes** (each intersected with the airborne mask):

| Class | Mask | Role |
|---|---|---|
| ALL | airborne | primary |
| AT / MAN | ATEN = 1 / ATEN = 0 | split (d) |
| CLB / CRZ / DES | PH = 4 (climb) / 5 (cruise) / 6 ("Approach": descent and approach in this ACMS logic) | split by phase |
| AT×phase, MAN×phase | intersections | descriptive only |

- **Time-domain r (statistic 1):** Pearson correlation of the fast-band samples in the class. For ALL it is exactly
  B1's `b1_stats` (the ported round-2 estimator, golden-tested in W0.5); for other classes the same computation on
  the class samples.
- **Welch (statistic 2 onwards)**, `code/spectral.py`: 512-sample segments (128 s, bin 0.0078125 Hz), periodic
  Hann, hop 256 (50 %), linear detrend per segment, one-sided density, segments placed only inside contiguous runs
  of the class mask; periodograms of all segments of a flight (and class) are averaged. The 256 non-DC bins are
  summed in blocks of 8 into 32 sub-bands of 0.0625 Hz (sub-band b covers bins 8b+1…8b+8). Cross-spectrum
  convention G_ij = E[conj(X_i) X_j] (scipy), so the equivalent delay τ = −dφ/dω is **positive when the second
  channel lags** (B2's sign).
- **Degrees of freedom:** per sub-band ν ≈ 8.34 K for K segments (Welch Hann 50 %: 2K/1.0556; 8-bin Hann average
  ≈ 4.40 independent bins). Coherence bias ≈ (1 − C)²/(ν/2) (Carter): ≤ 0.003 at K = 80; ≤ 0.04 at K = 6.
- **Inclusion per flight:** ALL needs ≥ 600 airborne samples (B1 rule) and K ≥ 8; any other class needs ≥ 600 class
  samples and K ≥ 6. A flight without the class is absent from that class (n stated per statistic).
- **B2 lags:** `phalanx.validation.battery.stats.b2_stats` (ALL); the same `_lag` estimator on class samples for
  classes (descriptive comparison with τ_eq).

## 4. Statistics (per flight, per class, per engine: engine 1 primary, engine 2 replicate, 3–4 descriptive)

**Pairs**, oriented cause → effect as in B2: N2→N1, FF→N1, FF→N2, N1→EGT, N2→EGT, FF→EGT. Sub-band powers P
(32 × p × p) and texture powers T (32 × p) as in §5. With w_b = √(P_ii,b P_jj,b)/√(ΣP_ii ΣP_jj), coherence C_b and
phase φ_b:

1. **Zero-lag fast-band correlation:** r_B1 (time domain, §3) and its spectral reconstruction
   r = Σ Re P_ij / √(ΣP_ii ΣP_jj) (Parseval), the reference for the decomposition.
2. **Coherence and phase.**
   - Band-averaged coherence (weights w) and phase of the summed cross-power in 0.1875–0.5, 0.5–1.0, 1.0–2.0 Hz.
   - **Coherent-variance fraction** of each channel: CF_i = Σ C_b P_ii,b / Σ P_ii,b (and CF_j).
   - **Equivalent delay** τ_eq: weighted LS of the unwrapped phase on 2πf over the sub-bands with centres in
     [0.2, 1.0] Hz (13 sub-bands), with intercept; weights ν C/(1 − C), C clipped to [0.01, 0.99]; unwrapping
     anchored on the delay τ₀ ∈ [−3, 3] s that maximises Σ|P_ij,b| cos(φ_b + ω_b τ₀) (no 2π slips from noisy
     sub-bands). Compared with the B2 lags. Also r_delay = Σ w_b cos(ω_b τ_eq) (pure-delay ceiling).
   - **Descriptive:** weighted grid fits of the phase by a pure delay, a first-order lag, and delay + lag
     (φ = −ωτ_d − atan(ωτ_l)), and the H1 gain per sub-band. These separate transport delay (including any recorder
     word-slot skew, which is unknown for these channels; research notes Q8) from spool-lag dynamics.
3. **Decomposition of 1 − r** (ordering A, primary; it is the brief's "lag-only ceiling"):
   - r_shape = Σ w_b (coherence 1, phase 0, observed spectra); r_lag = Σ w_b cos φ_b (coherence 1 at the observed
     phase and gain); r = Σ w_b √C_b cos φ_b.
   - L = 1 − r = **L_dyn** + **L_coh**, with L_dyn = 1 − r_lag (the "phase loss": phase part r_shape − r_lag plus
     gain-shape part 1 − r_shape, both dynamic) and L_coh = r_lag − r (the "coherence loss").
   - L_coh = **L_tex** + **L_beyond**: independent noise multiplies coherence, C = C_true · C_tex with
     C_tex,b = (1 − T_ii,b/P_ii,b)(1 − T_jj,b/P_jj,b); L_tex = Σ w_b (1 − √C_tex,b) cos φ_b; L_beyond = L_coh − L_tex.
   - Shares s_dyn = L_dyn/L, s_tex = L_tex/L, s_beyond = L_beyond/L (they sum to 1).
   - **Sensitivity:** ordering B (coherence loss first at zero phase: L_coh,B = r_shape − Σ w_b √C_b) and the
     Shapley mean of A and B.
4. **Partial and multiple coherence** (per sub-band from the spectral matrix, band-averaged by the conditioned
   power):
   - partial coherence N1–N2 | FF and N1–FF | N2 (fraction of each channel's conditioned power coherent with the
     other's conditioned part);
   - multiple coherence of N1 on {N2, FF} (fraction of N1 fast-band power linearly explained) and, for symmetry,
     of N2 on {N1, FF}; the unexplained part 1 − MCF is split into a texture part U_tex and **U_beyond** = true
     N1 power not explainable by the true inputs (true spectral matrix = P − diag(T), cross-spectra unchanged),
     as a fraction of observed N1 power; the texture-implied ceiling of MCF is reported;
   - **path decomposition** of r into the part carried by components coherent with a third channel k,
     Σ Re(P_ik P_kj / P_kk), and the k-conditioned remainder, for k = PLA of the same engine (lever-driven),
     k = N1 of the partner engine (1↔2, 3↔4; aircraft-common), and k = the within-engine third channel
     (N2→N1 via FF; FF→N1 via N2; N1→EGT via FF; FF→N2 via N1; N2→EGT via FF; FF→EGT via N1).
5. **Texture floor** (per channel, white, passed through the fast operator):
   - **T_q (primary, the brief's definition):** Δ_nat²/12 + Δ_rec²/12 (round-2 M-B rule; double quantiser A2/AD-05):
     N1, N2 0.04²/12 + 0.03125²/12 = 2.147·10⁻⁴ %²; EGT 0.8²/12 + 0.5²/12 = 0.07417 °C²; FF 8²/12 = 5.333 (lb/h)²
     (single lattice); PLA 0.087891²/12 deg² (single lattice, `param_table.csv`). The self-test simulates the
     frozen double quantiser: error variance ratio to the rule 0.999 (N1/N2) and 0.989 (EGT).
   - **T_qi:** T_q plus the round-2 A3 idiosyncratic sensor-noise variance (frozen `results/frozen/S/mb.json`
     σ: N1_1..4 0.0195, 0.0313, 0.0130, 0.0186 %; N2_1..4 0.0026, 0.0075, 0.0082, 0 %; EGT and FF 0).
   - **T_hf (empirical):** the median one-sided PSD of the fast-band signal over 1.5–1.95 Hz (divided by the fast
     operator's power transfer), per flight, class and channel, taken as a white level.
   - Reported per channel: texture fraction Q = ΣT/ΣP, the **texture-only r ceiling** √((1 − Q_i)(1 − Q_j)), the
     **truth-level r** = r / ceiling (texture de-attenuation), and the texture-implied coherent-fraction ceiling.
6. **Cross-engine coherence of the N1-specific residual:** residual of N1_k on {N2_k, FF_k} (frequency-domain
   multiple regression per sub-band); for engines (1, 2) primary (other pairs descriptive): squared coherence,
   **common share |γ|** (power-weighted coherency magnitude = the common fraction of residual variance under a
   symmetric one-common-factor model; self-tested), texture-corrected values, and residual power / residual
   texture power. The same for the N2-specific residual (N2 on {N1, FF}) and for raw N1_1–N1_2.
7. **Descriptive:** PLA activity per class (SD of 1-s PLA differences, as round-2 q02).

## 5. Aggregation and confidence intervals

- Group value = **median over flights** of the per-flight statistic (as B1). 95 % CIs: joint flight bootstrap,
  2,000 resamples (stream `validation.bootstrap`, scenario `mf1-diag`, index = number of flights n); every
  statistic on the same flight set uses the same resamples. For a class, flights lacking it are dropped inside
  each resample. Paired contrasts (AT − MAN; phase pairs; engine 1 − engine 2; U_beyond(N1) − U_beyond(N2)) use the
  per-flight differences of flights that have both.
- **Pooled-spectrum sensitivity:** spectra summed over flights (segment-weighted) before the decomposition, with
  the same flight bootstrap. Reported for the six pairs (engines 1 and 2) in every class.
- Every result file states n (flights contributing) and the justification of n.

## 6. Verification checks (sample stage; each logged in `results/verify/`)

- **V1 formats:** channels present; N1/N2/EGT/FF/PLA at 4 Hz, ATEN and PH at 1 Hz; finite values; sample counts.
- **V2 segments:** airborne fraction; K per class; ATEN and PH coverage per class.
- **V3 B1 sanity:** r_B1 comes from the battery's `b1_stats`. At 5 flights the engine-1/2 medians of the six pairs
  must lie within ±0.10 of the published 51-flight CAL fold-0 medians (`analysis/settling_experiment_round2/
  results/dev_battery_fold0.json`: engine 1 N1–N2 0.438, N1–FF 0.628, N2–FF 0.577, N1–EGT 0.571, N2–EGT 0.077,
  EGT–FF 0.319; engine 2 0.439, 0.642, 0.695, 0.565, 0.043, 0.263). At the final n: within max(0.03, CI
  half-width).
- **V4 spectral reconstruction:** median over flights of |r − r_B1| ≤ 0.03 for each of the six pairs (engines 1, 2).
- **V5 plots:** per verification flight, an SVG of the fast-band PSDs of N1, N2, FF, EGT (engine 1) with the T_q
  and T_hf levels, and the N2→N1 coherence and phase.
- **V6:** estimator self-test PASS (`results/log_selftest.txt`, synthetic signals only, 17 checks).
- On any failure: stop, investigate, record in `DEVIATIONS.md` before continuing. If V4 fails only because of
  sample coverage (take-off/landing edges and runs < 128 s are in r_B1 but not in the Welch segments), the
  decomposition is still interpreted relative to the spectral r, and the discrepancy is stated with the verdict.

## 7. Sample → verify → scale, and the n rule

1. **Verify** on `order[:5]` (all §6 checks).
2. **n rule** (minimal n for precision, written before scaling). Statistics Z = {CF_N1 (w.r.t. N2), CF_N2 (w.r.t.
   N1), s_dyn} for engine 1, class ALL, pair N2→N1. Half-width h = (q97.5 − q2.5)/2 of the bootstrap
   distribution of the median. Target: **h ≤ 0.05 for all three.**
   - Start: n₁ = max(20, ⌈n_pred⌉ rounded up to a multiple of 5), n_pred = (1.96 · 1.2533 · σ̂_max / 0.05)², with
     σ̂_max the largest across-flight SD of the three statistics on the 5 verification flights.
   - Iterate on prefixes of the fixed order: if any h > 0.05 at n, set n ← min(152, max(n + 10, n_pred at the
     current σ̂, rounded up to a multiple of 5)). Stop when all h ≤ 0.05 (n_final) or n = 152 (report the h
     achieved). Every step is logged in `results/n_rule_log.md`.
3. **Split coverage:** classes AT, MAN, CLB, CRZ and DES each need ≥ 15 contributing flights (engine 1). If one
   has fewer at n_final, the split analyses use the smallest prefix (steps of 10) that gives every class ≥ 15
   flights, up to 152 (n_split; coverage of a rare regime, RULES.md rule 1). Overall results are reported at
   n_final (primary) and at n_split.
4. The full CAL set is used only if these rules demand it.

## 8. Interpretation rules (fixed now)

Primary cell: engine 1, class ALL, pair N2→N1, ordering A, texture T_q. "CI" = bootstrap 95 % CI of the median.

| Verdict | Rule | Mechanism implication for MF1 |
|---|---|---|
| **PHASE-DOMINATED** | CI lower bound of s_dyn > 0.5 **and** median CF_N1 ≥ 0.70 | Low N1–N2 is mostly dynamic (fan lag / spool dynamics / loop). Priority: LP spool dynamics and loop; an independent `fan_face` input is secondary |
| **COHERENCE-DOMINATED, BEYOND TEXTURE** | CI lower bound of s_beyond > 0.5 | Independent variance is needed (AD-46 / AD-32). Side: LP-specific if U_beyond(N1 \| N2, FF) − U_beyond(N2 \| N1, FF) has a paired CI above 0, core-specific if below 0, else undetermined. Source: aircraft-common if the median N1-residual common share \|γ\| (engines 1–2) ≥ 0.5, engine-specific if ≤ 0.2, else mixed |
| **TEXTURE-DOMINATED** | CI lower bound of s_tex > 0.5 | M13 carries it; the truth-level target is the median truth-level r (with CI), stated for all six pairs |
| **MIXED** | none of the above | Report s_dyn, s_tex, s_beyond with CIs. A component is **material** if its CI lower bound ≥ 0.15 and **negligible** if its CI upper bound < 0.10. Each material component needs a mechanism |

**Robustness labels** stated with the verdict: *replicated* (engine 2 gives the same verdict); *texture-robust*
(same verdict with T_lo = min(T_q, T_hf) and with T_hi = max(T_qi, T_hf), per channel and flight);
*ordering-robust* (same verdict with the Shapley shares); *class-stable* (same verdict in AT and MAN).

**Joint structure (for W2.4a-1).** For FF→N1 and N1→EGT in class AT: "A/T common-mode driving carries the joint
structure" if the PLA-path share r_via_PLA / r has CI lower bound > 0.5 for both pairs; "does not carry it" if the
CI upper bound < 0.25 for both; otherwise "partial". The partner-engine path share is read the same way as
aircraft-common driving (A/T or atmosphere). Also reported: r, s_dyn, s_tex, s_beyond for both pairs in every
class, the AT − MAN paired differences, and the within-engine third-channel paths (N1–EGT via FF, N1–FF via N2).

**Delay vs lag.** If the dynamic share is material, the descriptive delay/lag fit says whether a pure delay or a
first-order lag describes the N2→N1 phase better (smaller weighted SSE); a pure-delay component cannot be told
apart from recorder word-slot skew (≤ 0.25 s, unknown for these channels) and is reported as such.

**Recommendation.** The mechanism recommendation for MF1 is a proposal for the coordinator, tagged
[MEASURED: Tail 687 CAL proxy airliner] with its transfer limits to the Tejas/F404-IN20 [TRANSFER]. A null or mixed
result is reported as a finding.

## 9. Limits stated in advance

- Proxy data: a four-engine airliner with a hydromechanical/TMS-era control, not a FADEC fighter; structure may
  transfer, magnitudes do not. Credibility ceiling: NASA-STD-7009B Level 2 against proxy data.
- The texture floor assumes white quantisation noise; when a signal dwells within one code, quantisation error is
  neither white nor independent of the signal. T_hf and T_qi bracket this; the texture-robust label reports it.
- Coherence and phase are linear measures; nonlinear (e.g. regime-dependent gain) relations within a flight appear
  partly as coherence loss. The class splits partly control for regime.
- Welch segments exclude airborne runs shorter than 128 s; r_B1 includes them (V4 measures the effect).
- No model is fitted; no holdout is used; nothing is tuned. No Kaggle.

## 10. Outputs

`code/` (scripts), `results/` (flight order, self-test log, verification log and plots, n-rule log, per-flight
statistics CSV, summary JSON and Markdown tables), `README.md` (commands, n and its justification, results),
`DEVIATIONS.md` if needed. A per-flight spectral cache is written to the git-ignored `runs/mf1/` only.
