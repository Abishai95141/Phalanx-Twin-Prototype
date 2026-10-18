# Round 2 quick look (development diagnostic on 687-CAL only, NOT a verdict)

**Written:** 2026-10-14 15:23 IST (prereg amendment A5). No holdout data were read.
**Script:** `src/q01_quick_look.py`. **Numbers:** `quick_look.json`. **Log:** `log_quick_look.txt`, `log_quick_look_stdout.txt`.

## Setup

- **Simplified M-A:** the pre-registered causal chain and corrections, with K = 5 knots per monotone map.
  - Chain: PLA → rate-limited fuel control → Wf/(δ√θ) → N2c (accel/decel lags) → N1c (lag) → EGT/θ^a (thermal lag).
  - Fitted by staged output-error least squares on **30 CAL flights** (seed 20261015), engine-type maps with per-position unit offsets.
- **M-B:**
  - Double quantiser with the round-1 native steps (A2). The CAL-fitted native-grid offsets reproduce the observed never-used residues exactly: N1/N2 {3, 8, 12, 17, 21, 26, 31} mod 32; EGT {1, 4, 7} mod 8.
  - Idiosyncratic AR(1) sensor noise (A3). The fitted σ is ≈ 0 for EGT, FF and most N2 channels, and 0.010–0.023 % for N1: the idiosyncratic part is smaller than the quantiser variance.
  - Round-1 recorder effects (A4).
- **No M-C.**
- **Synthesis:** 20 *other* CAL flights, generated from their inputs only (PLA, ALT, MACH, TAT, PH), with fleet-prior offsets.
- **R1-ref:** round-1 FULL texture (T1-L6 primary) on the same 20 flights, using round-1 code and parameters (read-only).

## M-A out-of-sample fit (20 held-out CAL flights, running samples)

| Output | RMSE (CAL offsets) | R² (CAL offsets) | RMSE (prior offsets) | R² (prior offsets) |
|---|---|---|---|---|
| FF | 83 lb/h | 0.978 | 120 lb/h | 0.955 |
| N2 | 2.5 % | 0.974 | 3.7 % | 0.942 |
| N1 | 3.0 % | 0.987 | 4.9 % | 0.966 |
| EGT | 21.7 °C | 0.913 | 26.2 °C | 0.873 |

## Battery subset: distance to real (smaller is better; flight-bootstrap 95 % CI)

| Test | R2a-quick vs real | R1-ref vs real | Real vs real (CAL 20 vs 20) | Round-1 real-vs-real (corr_check, TEST) |
|---|---|---|---|---|
| **B1 fast, f_c 0.2 Hz** (primary) | **0.196** [0.184, 0.211] | 0.319 [0.301, 0.336] | 0.021 | 0.021 (early vs late), 0.048 (687 vs 652) |
| B1 slow, f_c 0.2 Hz | 0.038 [0.027, 0.051] | 0.000 (inherited) | 0.009 | 0.019 / 0.009 |
| B1 fast, f_c 0.5 Hz | 0.110 [0.092, 0.143] | 0.151 [0.147, 0.159] | 0.014 | 0.016 / 0.020 |
| **B2 lead–lag** (s) | **0.350** [0.338, 0.400] | 0.256 [0.200, 0.344] | 0.044 | — |
| B5 scatter, \|Δ\|/real | 0.894 (0.093 vs 0.049) | 0.005 (inherited) | 0.003 | — |
| B5 EGT exponent a | 0.11 (0.57 vs 0.68) | 0.00 (inherited) | 0.02 | — |

### Fast-band median correlations, engine 1 and cross-engine (f_c 0.2 Hz)

| Pair | Real | R2a-quick | R1-ref |
|---|---|---|---|
| N1–FF | 0.62 | **0.55** | 0.05 |
| N2–FF | 0.59 | 0.49 | 0.04 |
| N1–N2 | 0.42 | 0.86 | 0.06 |
| N1–EGT | 0.56 | 0.17 | 0.04 |
| EGT–FF | 0.32 | 0.09 | 0.03 |
| N1_1–N1_2 | 0.79 | 0.84 | 0.79 |
| EGT_1–EGT_2 | 0.56 | 0.26 | 0.57 |
| FF_1–FF_2 | 0.57 | 0.74 | 0.33 |

### B2 flight-median lags (engine 1; positive = second channel lags)

| Pair | Real | R2a-quick | R1-ref |
|---|---|---|---|
| FF→N2 | **−0.50 s** | +0.25 | −0.38 |
| FF→N1 | 0.00 | +0.25 | 0.00 |
| N2→N1 | +0.50 | 0.00 | +0.50 |
| FF→EGT | +0.75 | +1.00 | +0.63 |
| N1→EGT | +0.25 | +0.75 | 0.00 |

## Reading (development only)

1. **The physics chain carries much of the within-engine fast coupling that round 1 destroyed.**
   - N1–FF rises from 0.05 (R1-ref) to 0.55 (real 0.62), and N2–FF from 0.04 to 0.49 (real 0.59).
   - The primary B1 fast distance falls from 0.32 to 0.20.
   - It is still about 9× the CAL real-vs-real distance.
2. **The coupling pattern is distorted.**
   - N1–N2 is over-coupled (0.86 vs 0.42), because τ_1 sits at its 0.1 s bound, so N1 is effectively a static map of N2.
   - EGT is under-coupled to the spools and over-driven by the common θ^a·TAT factor at 1-Hz TAT resolution.
   - Cross-engine FF is over-coupled.
3. **Lead–lag order is wrong in a way the pre-registered chain cannot fix.**
   - Real data have **N2 leading FF by 0.5 s**, then N1, then EGT.
   - The fixed open-loop chain PLA → Wf → N2 forces FF to lead.
   - The likely physical causes are a fuel-flow transmitter lag, or closed-loop governing in which fuel flow responds to the speed error. Neither is in M-A.
   - B2 is worse than R1-ref (0.35 vs 0.26 s; R1-ref inherits the real slow and lag structure through the low-passed truth).
4. **B5 fails badly at this stage.**
   - Corrected FF-vs-N2 scatter is 0.093 synthetic vs 0.049 real.
   - Most of it comes from fleet-prior N2 unit offsets (SD ≈ 1.2 %) mapped through the steep Wf_c(N2c) curve at cruise.
   - The fitted EGT exponent is 0.57 vs 0.68 measured on real data.
5. **Implication for the full Phase A** (still CAL-only, before the freeze):
   - K = 8 knots and a joint output-error refinement across stages.
   - Fit-quality checks by 5-fold flight-grouped CV.
   - M-C (arm R2b), the remaining battery, guards and discriminator diagnostics.
   - Any structural refinement prompted by these findings (e.g. a fuel-flow measurement lag) will be logged as an amendment with this evidence, and results reported both ways. Otherwise the pre-registered structure is kept and the lead–lag failure is reported as a finding.
