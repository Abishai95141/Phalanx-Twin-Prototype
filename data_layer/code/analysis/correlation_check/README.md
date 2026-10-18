# Cross-channel cohesion check (2026-10-14)

**Question:** although synthetic data can be told apart from real data, do the synthetic channels co-vary like real ones?

**Script:** `corr_check.py`, which reuses the experiment's loader (`dlio.load_flight`) and low-pass filter (`pipeline.lowpass`).

## Method

- **Data:** the 16 engine channels (N1, N2, EGT and FF, for each of 4 engines, at 4 Hz), airborne samples only.
- **Flights:** 60 Tail 687 TEST flights (seed 20261014), each compared with its own FULL synthetic version (T1-L6, T2-L6).
- **Baselines:** real-vs-real comparisons, 687 early-season vs late-season flights and Tail 687 vs Tail 652.
- **Bands:**
  - *Slow band:* correlations of the low-passed signal (the "truth" part).
  - *Fast band:* correlations of the residual, i.e. the band the texture model generates.
- **Statistic:** median correlation per channel pair across flights; distance = mean absolute difference over the 120 pairs, with a flight-bootstrap 95 % CI.

## Results

### Mean |Δ correlation| over the 120 channel pairs

| Comparison | Slow, f_c = 0.2 Hz | Fast, f_c = 0.2 Hz | Slow, f_c = 0.5 Hz | Fast, f_c = 0.5 Hz |
|---|---|---|---|---|
| Synthetic T1-L6 vs real 687 | 0.0008 | **0.320** | 0.0003 | **0.082** |
| Synthetic T2-L6 vs real 687 | 0.006 | **0.317** | 0.006 | **0.081** |
| Real 687 early vs late | 0.019 | 0.021 | 0.019 | 0.016 |
| Real 687 vs real 652 | 0.009 | 0.048 | 0.009 | 0.020 |

### Fast-band median correlation, selected pairs (f_c = 0.2 Hz)

| Pair | Real 687 | Synthetic T1-L6 | Real 652 |
|---|---|---|---|
| N1_1–FF_1 (same engine) | 0.65 | 0.04 | 0.66 |
| N1_1–EGT_1 (same engine) | 0.56 | 0.05 | 0.56 |
| N1_1–N2_1 (same engine) | 0.43 | 0.05 | 0.49 |
| N1_1–N1_2 (across engines) | 0.80 | 0.78 | 0.81 |
| EGT_1–EGT_2 (across engines) | 0.58 | 0.57 | 0.60 |

## Reading

1. **Slow band: matches real, but by construction.** Synthetic slow structure sits well inside the real-vs-real spread. In this experiment the truth is the low-passed real signal, so this does not test any physics model.
2. **Fast band: cross-engine coupling reproduced, within-engine coupling missing.**
   - The texture model's common-mode component reproduces cross-engine correlations of the same parameter.
   - It generates each parameter's residual independently, so it destroys the strong within-engine coupling between FF, N1, N2 and EGT.
   - The gap is 7–15× the real-vs-real distance at f_c = 0.2 Hz, and still ≈4–5× at 0.5 Hz.
3. **Cause: fast fluctuations up to ≈0.5 Hz in real engine data are mostly coupled engine dynamics, not sensor noise.** These are fuel-flow changes driving spool speeds and EGT, i.e. closed-loop control activity. Splitting truth from texture with a frequency cutoff wrongly assigns that coupled dynamics to "noise".

## Implications

- **Supports the architecture principle.** Coupled dynamics must come from the physics/dynamic model (engine transient model + FADEC + throttle activity). The texture layer should hold only effects that are plausibly independent per sensor: quantisation, sensor noise, recorder artefacts.
- **For the DASHlink proxy (round 2).** Replace independent per-channel residuals with a coupled multivariate model fitted on CAL flights only: a shared driver (fuel-flow activity) passed through channel-specific lagged transfer functions, or a VAR with cross terms. Alternatively, raise the truth/texture boundary.
- **New acceptance check.** The fast-band cross-correlation distance should be ≤ the real-vs-real distance, measured with this script. It is a direct test of "cohesive behaviour".
