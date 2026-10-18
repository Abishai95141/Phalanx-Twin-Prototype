# Behavioural targets: how real engines behave, and what the simulation must reproduce

This sheet collects the **measured real-data behaviour** the build must reproduce, in one place. Every number comes
from `analysis/settling_experiment_round2/REPORT.md` (Tail 652 holdout, n = 110 flights; Tail 687-TEST as a second
real tail). Each value also cites the module(s) that must produce it.

**Which targets apply where:**
- **Proxy mode** (DASHlink Tail 687: a **four-engine regional jet** with separate-flow high-bypass engines, no afterburner; W2.4) is held to these numbers directly. The B1/B2 tables use engines 1 and 2 of the four. Its final gate is the reserved archive 2 (AD-33).
- **Tejas mode** (single F404-IN20) must reproduce the **structure** of these targets: signs, orderings, coherence < 1, closed-loop lead–lag. Magnitudes are platform-specific and come from IN20 evidence or sweeps.

## The pass rule (architecture §14.1)

For each test, compute D_sim = distance(synthetic, real) with the same estimator used for the bars below.

| Outcome | Condition |
|---|---|
| **PASS** | D_sim ≤ D_tail: synthetic is as close to real as one real tail is to another |
| **STRICT PASS** | D_sim ≤ D_temp: as close as a tail is to itself across time |
| **FAIL** | The one-sided 95 % lower bound of (D_sim − D_tail) is above 0 |

The round-2 open-loop deterministic model (S_R2b) is the **negative baseline the build must beat**.

| Test | What it measures | D_tail (bar) | D_temp (strict) | Round-2 S_R2b (failed) |
|---|---|---|---|---|
| B1 fast | Fast-band (>0.2 Hz) correlation structure | 0.047 | 0.045 | 0.196 |
| B1 slow | Slow-band correlation structure | 0.010 | 0.005 | 0.017 |
| B2 | Lead–lag order (peak cross-correlation lags) | 0.050 | 0.000 | 0.212 |
| B3 (i) | Coherence and gain/phase | 0.078 | 0.058 | 0.417 |
| B3 (ii) | Step time constants | 0.115 | 0.100 | 0.682 |
| B4 | Directional dependence (VAR Granger matrix): the **causal** structure | 0.154 | 0.086 | 0.690 |
| B5 (i) | Corrected-parameter collapse | 0.491 | 0.209 | 0.686 |
| B5 (ii) | EGT temperature exponent | 0.03 | 0.17 | 0.20 |
| B6 | Per-phase regime behaviour | 0.488 | 0.747 | 1.675 |

## Correlation (B1): fast band, flight medians

| Pair | Real 652 | Real 687-TEST | Round-2 open loop | Producing modules |
|---|---|---|---|---|
| N1–N2 (within engine) | **0.47** | 0.43 | 0.92 (over-coupled) | M07 spool dynamics + M03 per-spool disturbance + M08 loop |
| N1–EGT | 0.56 | 0.57 | 0.81 | M07 + M12 thermocouple lag |
| N1–FF | 0.65 | 0.63 | 0.54 | M07/M08 loop + M12 FF meter |
| N2–FF | 0.67 | 0.57 | 0.45 | M08 governing (FF responds to N2 error) |
| N1_1–N1_2 (across engines) | **0.81** | 0.80 | 0.91 | Shared inputs (A/T) + **independent** per-engine disturbances (M03) |
| N2_1–N2_2 | 0.75 | 0.71 | 0.98 | same |
| EGT_1–EGT_2 | **0.59** | 0.58 | 0.99 (lockstep) | same |

**Lesson:** engines and spools share inputs but have their own disturbances, so they are correlated without moving
in lockstep. Independent sensor noise cannot fix this (round 2 M-C, AD-29); it must come from the dynamics (AD-32).

## Lead–lag order (B2): engine 1, flight-median lag (s; positive = second channel lags)

| Pair | Real 652 | Real 687-TEST | Round-2 open loop | Meaning |
|---|---|---|---|---|
| FF→N2 | **−0.50** | −0.50 | +0.25 (wrong sign) | Small-signal fuel *responds* to speed error: closed-loop governing (AD-31) |
| FF→N1 | 0.00 | 0.00 | +0.25 | |
| N2→N1 | +0.50 | +0.50 | 0.00 | The fan follows the core |
| FF→EGT | +0.75 | +0.75 | +0.75 | Gas-path thermal lag + thermocouple lag |

Post hoc on CAL flights: FF→N2 is **−0.375 s with autothrottle engaged** (147 flights) vs **0.00 s manual** (87
flights). The proxy configuration must model the A/T loop (§14.3).

## Phase structure behind B1/B2 (MF1-D, 687-CAL, engine 1, n = 20 flights; AD-52)

Measured on the **fit split** by the pre-registered diagnostic in `analysis/mf1_lp_structure/`.

| Quantity | Value | Meaning |
|---|---|---|
| N2→N1 phase, 0.19–0.5 Hz (82–84 % of fast-band power) | ≈ −55° | The fan follows the core |
| N2→N1 phase, 0.5–1 Hz | ≈ −96° | |
| N2→N1 gain (to 0.55 Hz) | ≈ 1.0 (0.97–1.11) | |
| N2→N1 equivalent delay τ_eq | 0.33 s (fit: 0.15 s delay + 0.38 s first-order lag) | The 0.15 s part may include recorder word-slot skew |
| Coherent fraction of N1 fast-band power (with N2) | 0.69 [0.67, 0.72] | |
| Share of 1 − r(N1,N2) due to phase | 0.91 | **Low N1–N2 is mostly timing, not independent input** |
| N1 power unexplained by own N2 + FF, beyond texture | 24 % [20, 27] (in flight 33 %; A/T flight 41 %); ≈ half aircraft-common | Size of the LP-specific (`fan_face`) input |
| τ_eq: FF→N1 / N2→FF / N1→EGT / FF→EGT | +0.18 / +0.16 / +0.25 / +0.53 s | EGT lags N1; N2–EGT ≈ 0 is pure phase (≈ −88°) |
| Truth-level (pre-texture) r | N1–N2 0.43–0.46; N1–FF 0.77; N2–FF 0.72; N1–EGT 0.61 | Texture lowers the FF and EGT pairs, not N1–N2 |

**Also:** the B1 airborne rule (all four N1 > 25 %) admits taxi at ground idle (7–21 % of samples). Synthetic
flights must reproduce that mix, by being driven over whole recorded flights, and B1 is also reported on phases
4–6.

## Dynamic response (B3 ii): step time constants, median τ (s)

| Response | Real 652 | Real 687-TEST | Round-2 open loop |
|---|---|---|---|
| N1 accel / decel | 1.03 / **3.06** | 1.09 / 3.03 | 1.75 / 1.73 |
| FF accel / decel | 0.81 / **1.58** | 1.08 / 1.56 | 0.97 / 0.40 |
| EGT accel / decel | 3.45 / **4.70** | 4.17 / 4.10 | 2.87 / 1.34 |

**Lesson:** deceleration is much slower than acceleration in real engines, and round 2 had it far too fast. The cause
is unidentified decel schedules and lags under a level-dominated fit. This is why AD-34 requires transient-weighted
identification.

## Physical laws (B5)

| Quantity | Real | Round-2 |
|---|---|---|
| EGT corrected-temperature exponent a | **0.73** (652), 0.70 (687-TEST) | 0.53–0.55 |

## Sensor and acquisition (M12/M13)

| Quantity | Value | Source |
|---|---|---|
| FF meter lag τ_FFs | 0.218 s (CV 0.19–0.29) | Round-2 fit, proxy |
| Thermocouple τ_TC,ref | 0.81 s (CV 0.55–1.18), τ ∝ W^-0.5 | Round-2 fit, proxy; AGARD |
| Native steps (proxy) | N1/N2 0.04 %, EGT 0.8 °C, FF 8 lb/h | `native_step_cal.json` |
| **Noise ceiling** | Independent noise ≤ the measured idiosyncratic level. ±1 LSB extra noise FAILs B1, B3 (i) and B4 | W0.5 finding |
| Missingness | Clock-slip windows only (period 1/(f·Δ), Δ ≈ 910 ppm); no independent dropout | AD-06 |

## Tejas usage gates (M02 and the loop; structural targets for the Tejas configuration)

| Gate | Target |
|---|---|
| Type III cycles | 5 ± 2 per FH |
| AB lights | 4–5 per FH |
| Time ≥ IRP | 17–20 % |
| AB time | ≈5 % |
| TAC | 2.2–3.3 per FH |
| EOT/EFH | 1.56 |
| Per-flight usage CV | ≈0.5 |
| Engine dispersion | ≈1.3 |
| Nz spectrum | Within ±30 % of the F-16 curve |

## When each target is checked

| When | Check |
|---|---|
| W1, module level, with labelled test fixtures | M07 within-engine coherence < 1 and cross-engine independence (W1.3a A4/A6); M08 sign of small-signal Wf vs N2 lag, and commanded-step lead (W1.3b A2); M03 PSD and coherence (W1.1 A3); M13 noise ceiling (W1.6 A3) |
| W2.2 skeleton | First quick look of B1–B6 on synthetic flights (development only) |
| W2.4 proxy mode | Fit on 687-CAL; develop against Tail 652 (already seen); then **one** pre-registered gate run on archive 2 |
