# W0.6 Backend benchmark: results and recommendation (AD-22)

**Recommendation: Numba alone** for the build's compiled hot loops, with keyed Philox RNG blocks generated in
NumPy and fed into the kernel, and complex-step Jacobians from the same dtype-generic kernel source for AD-34.
No hybrid now. JAX is kept as a measured, conditional option for large-n calibration (flip condition F1).

Pre-registration: `PREREGISTRATION.md` (commit `d08a94b`, before any measurement). Deviations: `DEVIATIONS.md`.
Credibility: one machine, one workload that approximates the M07/M08/M03 cost structure (PROXY A-W0.6-2);
bitwise claims are for this platform and pinned stack only (A-W0.6-3).

## 0. Verdict against the pre-registered decision rule (§6)

| Criterion (pre-registered) | Numba | JAX (CPU, x64) |
|---|---|---|
| Gate: D1–D7 bitwise | **PASS** (all) | **FAIL**: D6 fails for both unroll settings; D5 fails with the fastest config (unroll 4) |
| Gate: agreement with the NumPy reference | **Bitwise** at 10 s, 60 s × 10 units, 1 h, 1,000 units | ≤ 4.7e-14 relative over 1 h, 0 limiter-selection flips (within the 1e-12 tolerance; mechanism identified) |
| Engine-loop budget ≥ 1,000× real time, 1 core (M1) | **PASS**: 5,270× (0.68 s per sortie-hour) | **FAIL**: 330× (10.9 s), using 1.7 cores |
| Materially faster on M1 (≥ 1.5×, disjoint ranges) | 15.9× faster | — |
| Materially faster on M3 (1,000 units, 1 core) | 1.14× faster (not material) | — |
| Gradient requirement, n ≈ 30 (≥ 95 % of columns within 1e-6) | **PASS** via complex step (100 %, max 2.8e-14), 0.88 s serial / 0.52 s 4 threads; FD fails (27 % / 83 %) | **PASS** via jacfwd (100 %, max 3.2e-14), 1.51 s + 22 s compile |
| Fastest accurate Jacobian at n ≈ 30 | **Numba complex step** | 1.7× slower (2.9× vs 4 threads) |

Rule 1 applies: Numba passes the gate, is not materially slower on M1 or M3, and its gradient path meets the
requirement and is the fastest at the pre-registered scale → **Numba alone**. Rule 2 (hybrid) is not triggered:
Numba's complex step is neither inaccurate nor > 5× slower than `jacfwd` (at n = 30 it is faster; at n = 240 it
is 3.3× slower serial, 1.5× with 4 threads).

## 1. Setup

- Machine: Apple M4 (4 P + 6 E cores), 16 GB, macOS 26.2; shared with four other agents (load average 5–8.5
  during M1–M3, up to 38 during M3b). Python 3.13.3, NumPy 2.5.4, Numba 0.68.0 / llvmlite 0.50.0 (threading
  layer `workqueue`), JAX/jaxlib 0.11.2, SciPy 1.18.1 (`.venv-build`, nothing added).
- Workload (`code/workload.py`; PREREGISTRATION §2): 10 float + 2 int states per unit; per 240 Hz step 8
  derivative evaluations (4 Heun sub-steps), 24 bilinear + 16 linear lookups on non-uniform grids, 9 `pow`;
  a 60 Hz controller with PI + MIN/MAX selection over five limiters; two AR(1) process disturbances from keyed
  Philox blocks. Over a sortie-hour every limiter branch engages (governor 755,232 steps, N1 11,456, T5 50,940,
  accel 10,336, decel 35,960, Wf_min 76) with 42,691 selection switches: representative MIN/MAX stress.
- JAX configuration (fairness, `results/jax_tuning.json`): 4 bracket-search methods × 5 scan unroll factors,
  60 s, 3 reps each. Fastest: `compare_all` + unroll 4 (15.2 µs/step); used for all JAX timings. unroll 1 is
  used where a determinism property needs it (§7).

## 2. Acceptance → checks

| ID | Criterion | Named check (script → result) | Outcome |
|---|---|---|---|
| A1 | Every backend agrees with the NumPy reference | `CHK-A1-S1/S2/S3` (`s03_a1_agreement.py` → `a1_agreement.json`); `CHK-A1-OPS` (`s00_oplevel.py` → `oplevel.json`); `CHK-A1-XLAFLAGS` (`s00b_xla_flags.py`); `CHK-A1-1000` (M3 digest: NumPy = Numba at 1,000 units) | **PASS**: Numba bitwise everywhere; JAX within tolerance, mechanism identified (§3) |
| A2 | M1–M6 measured with stated n and repetitions; variance reported | `CHK-M1`…`CHK-M6` (§4–§9; every table gives n, median, min–max) | **PASS** (contention caveat stated) |
| A3 | Determinism verdict per backend | `CHK-M4-D1`…`D7` (`s05_m4_determinism.py`, `s04_m2_compile.py`) | **PASS** (verdict given): Numba deterministic in all 7; JAX conditionally (§7) |
| A4 | Recommendation with evidence table and flip conditions | §0, §13–§15 | **PASS** |
| A5 | Code runs with `-I` from `.venv-build`; `make check` green | `CHK-A5-REGRESS` (`s11_regress.py`: the committed code reproduces the recorded digests of all 5 kernel families in fresh `python -I` processes); `make check` output in the report | **PASS** |

## 3. A1: agreement with the NumPy reference

| Stage | Sample | Numba | JAX unroll 4 | JAX unroll 1 |
|---|---|---|---|---|
| S1 | 10 s, 1 unit | bitwise | max rel 2.3e-14; first diff at step 0 (Wf); limiter codes identical | same |
| S2 | 60 s, 10 units (prange / vmap) | bitwise | max rel 2.0e-14; channel-scaled ≤ 3.0e-15 | same |
| S3 | 1 h, 1 unit (vs the NumPy hour) | bitwise | max rel 4.7e-14; channel-scaled ≤ 5.2e-15; **0 selection flips**; per-10-min max 2.7e-15–5.2e-15 (no growth) | same |
| M3 | 60 s, 1,000 units | NumPy vectorised digest `73496c09` = Numba prange digest | different digest | — |

**Mechanism** (op-level conformance, n = 100,000 keyed inputs; `oplevel.json`). Numba = NumPy bitwise on all 13
ops (fastmath off; Numba scalar `pow`/`exp`/`log` call the same libm as NumPy). JAX jit differs on:

| Op | JAX mismatches / 100,000 | Max ULP | Cause |
|---|---|---|---|
| a·b + c | 20,189 | 17,017 (cancellation) | FMA contraction |
| a + h·b (runtime h) | 212 | 1 | FMA contraction |
| x / 288.15 (literal) | 21,002 | 1 | division → multiply by reciprocal |
| (b − a) / s, s a broadcast runtime scalar | 28,232 (vectorised); 0 (inside scan) | 1 | same rewrite, vectorised context only |
| exp | 13,478 | 2 | XLA's own exp |
| +, ×, ÷, sqrt, pow (runtime exponents), log | 0 | 0 | — |

No accepted XLA flag changes any count (`xla_flags.json`: `xla_cpu_enable_fast_math=false`,
`xla_allow_excess_precision=false`, `xla_cpu_enable_platform_dependent_math=false`,
`xla_cpu_fast_math_honor_{division,functions}=true`; two other flags are unknown to this jaxlib). JAX **eager**
(`jax.disable_jit`) reproduces the NumPy/Numba digest bitwise (M7 E2), so the differences come from XLA
compilation, not from JAX's op semantics. No configuration exposed by this jaxlib changes it (8 flag sets
tested), so we treat it as a property of the jit path on this stack, not a fixable setting.

## 4. M1: single sortie-hour (864,000 steps, 1 unit, 1 thread)

Fresh process per configuration; 1 warm-up block, then repetitions of the full hour. Kernel time excludes the
NumPy feeding layer (inputs + keyed RNG blocks), shown separately (`m1_sortie_hour.json`).

| Backend | n reps | Kernel s: median [min–max] | × real time | µs / step | Feed s | CPU/wall | Peak RSS |
|---|---|---|---|---|---|---|---|
| Numba | 5 | **0.683** [0.672–0.862] | **5,270×** | 0.79 | 0.085 | 1.00 | 119 MB |
| JAX unroll 4 | 5 | 10.90 [9.98–12.25] | 330× | 12.6 | 0.112 | 1.72 | 513 MB |
| JAX unroll 1 | 3 | 12.59 [10.47–12.71] | 286× | 14.6 | 0.126 | 1.97 | 303 MB |
| NumPy reference (1 h) | 1 | 922.5 | 3.9× | 1,068 | 0.145 | 1.0 | 265 MB |
| NumPy reference (60 s) | 3 | 15.16 [14.12–15.21] | 4.0× | 1,053 | — | 1.00 | 36 MB |

- Numba is 15.9× faster than the best JAX configuration on the median, with disjoint ranges.
- JAX uses 1.7–2.0 cores for a single-unit scan even with XLA intra-op threading off (`CPU/wall`), so its
  per-core cost is ≈ 2× its wall time.
- Variance across sessions is larger than within one: an earlier Numba hour on a busier machine took 2.29 s
  (1,570×). Apple P/E-core scheduling under load is the likely cause. Budgets should use the pessimistic figure,
  which still clears 1,000× by 1.5×.
- Feed cost (NumPy inputs + keyed RNG) is 0.085–0.145 s per unit-hour: ≈ 12 % of the Numba kernel, < 1 % of JAX.

## 5. M2: compile overhead and caches (3 fresh processes per condition; `m2_compile.json`)

Compile ≈ first call − second call (same shapes). Median [min–max], seconds.

| Kernel | Cold (empty cache) | Cache hit | JAX: populate persistent cache | Import | Process total, cache hit | Cache size | D7 |
|---|---|---|---|---|---|---|---|
| Numba single-unit `step_block` | 4.34 [4.28–4.41] | 0.20 [0.19–0.20] | — | 0.15 | 0.36 | 325 kB | 1 digest |
| Numba `prange` batch | 5.67 [5.65–5.90] | 0.20 [0.20–0.20] | — | 0.15 | 0.39 | 367 kB | 1 digest |
| JAX single (scan, unroll 4) | 2.26 [2.22–5.89] | 1.13 [0.61–1.65] | 4.53 [2.33–6.73] | 0.31–0.65 | 2.11 | 557 kB | 1 digest |
| JAX vmap batch (10 units) | 6.44 [2.68–7.05] | 0.87 [0.87–2.19] | 2.95 [2.93–8.99] | 0.28–0.69 | 1.34 | 684 kB | 1 digest |
| JAX jacfwd (M5, n = 30 / 240) | 22.1 / 23.0 | not measured | — | — | — | — | — |
| JAX grad (M5, n = 30 / 240) | 19.1 / 16.3 | not measured | — | — | — | — | — |

- Numba compiles once per type signature; the block length is a runtime value (no recompilation). `cache=True`
  makes a fresh process start in 0.36 s. A complex128 specialisation (complex step) compiles separately (~5 s).
- JAX recompiles for every new static shape: block length, batch size, unroll, and each transformation
  (`jit`, `vmap`, `jacfwd`, `grad`). The persistent cache works (D7 holds) but a hit still costs ~1 s.
- Neither backend exceeds the 60 s cold-compile risk threshold.

## 6. M3: 1,000 units × 60 s, thread / device scaling (3 reps; `m3_batch.json`)

Same scenario for every row; one digest per backend family.

| Configuration | Kernel s: median [min–max] | Unit-s simulated / wall-s | µs / unit-step | CPU/wall | Peak RSS | Digest |
|---|---|---|---|---|---|---|
| Numba prange, 1 thread | **10.72** [10.71–10.82] | 5,596 | 0.745 | 1.00 | 645 MB | `73496c09` |
| Numba prange, 2 threads | 5.39 [5.38–11.62] | 11,141 | 0.374 | 1.69 | 682 MB | same |
| Numba prange, 4 threads | 6.29 [5.38–7.22] | 9,541 | 0.437 | 2.07 (contended) | 698 MB | same |
| Numba prange, 8 threads (once) | 2.35 [2.33–2.44] | 25,548 | 0.163 | 3.99 | 643 MB | same |
| JAX vmap, 1 device, unroll 4 | 12.21 [12.07–16.92] | 4,915 | 0.848 | 1.16 | 1,244 MB | `f11fd17c` |
| JAX vmap, 1 device, unroll 1 | 16.04 [10.26–19.72] | 3,740 | 1.114 | 1.12 | 1,016 MB | `6f65c7ac` |
| JAX vmap, XLA default thread pool | 13.96 [13.65–16.46] | 4,299 | 0.969 | 1.14 | 1,211 MB | `f11fd17c` |
| JAX sharded, 2 devices | 10.90 [10.55–10.97] | 5,503 | 0.757 | 1.85 | 1,476 MB | `f11fd17c` |
| JAX sharded, 4 devices | 6.98 [6.81–7.45] | 8,598 | 0.485 | 2.86 | 1,372 MB | `f11fd17c` |
| JAX sharded, 8 devices (once) | 5.98 [5.37–6.02] | 10,035 | 0.415 | 3.08 | 1,428 MB | `f11fd17c` |
| NumPy vectorised (once) | 149.2 | 402 | 10.36 | 0.64 | 548 MB | `73496c09` |

Feed (NumPy inputs + keyed blocks for 1,000 units): 1.2–2.3 s per 60 s batch, the same for every backend.

- **Per core**, `vmap` amortises JAX's per-step overhead: JAX is within 1.14× of Numba in wall time (1.3× per
  CPU-second). Not materially different by the pre-registered bar; Numba is ahead.
- Scaling was contention-limited (load average 7–8.5: Numba at 4 threads reached only 2.07 CPU/wall). Speed-ups
  measured: Numba 2.0× (2 t), 1.7× (4 t, contended), 4.6× (8 t); JAX 1.1× (2 dev), 1.75× (4 dev), 2.0× (8 dev).
  The XLA default intra-op thread pool gives no speed-up for this workload (ops are too small to split).
- **M3b (paired re-measurement, deviation D1):** see §6b.

### 6b. M3b: paired, alternating 1-core / 4-core re-measurement (`m3b_paired.json`)

Reason and design in `DEVIATIONS.md` (D1): the backends alternate (A B A B), 2 rounds × 3 reps, to share the
background load. **Result: inconclusive for speed.** Load average rose to 22–38 on 10 cores during the run
(other agents), and the processes did not get their cores (CPU/wall 0.36–1.81):

| Round | Load avg (1 min) | Numba 1 thr | JAX vmap 1 dev | Numba 4 thr | JAX 4 dev |
|---|---|---|---|---|---|
| 0 | 7.9–21.9 | 19.1 s (CPU/wall 0.97) | 19.3 s (1.13) | 10.9 s (1.28) | 11.6 s (1.40) |
| 1 | 21.0–37.7 | 55.0 s (0.36) | 24.9 s (0.95) | 10.7 s (1.25) | 8.3 s (1.81) |

What it does show: digests were unchanged under heavy contention (Numba `73496c09`, JAX `f11fd17c` in every
run). M3 (§6) remains the measurement of record; multi-core efficiency on an unloaded machine is not established
here (follow-up: rerun `s07_m3_batch.py` on a quiet machine or a Kaggle kernel). Neither result bears on the
decision: per core the backends are comparable, and JAX showed no scaling advantage in M3.

## 7. M4: determinism (`m4_determinism.json`, `m4_determinism_jax_unroll1.json`; D7 from M2)

Digests: blake2b over each unit's output stream, independent of how the stream is cut into blocks.

| Check | Sample | Numba | JAX unroll 4 | JAX unroll 1 |
|---|---|---|---|---|
| D1 repeated in-process | 1 and 10 units × 60 s, twice | PASS | PASS | PASS |
| D2 separate processes | 1 and 100 units, two processes | PASS | PASS | PASS |
| D3 single vs batched; position in batch | units 0–9 alone vs in batches of 10 / 100 / 1,000 and an offset batch (5–14); units 0–99 of 100 vs 1,000 | PASS | PASS | PASS |
| D4 threads / devices | 100 units: Numba 1/2/4 threads + serial loop; JAX 1/2/4 devices (sharded) + intra-op threading on/off | PASS | PASS | PASS |
| D5 snapshot → bytes → restore → continue | 1 and 10 units; at step 5,237 (not a multiple of 2,400 or 4) and at 4,800 (block boundary) | PASS | **FAIL** at 5,237; PASS at 4,800 | PASS |
| D6 block length 1 / 240 / 2,400 | 1 unit, 10 s | PASS | **FAIL** (L = 1 final state differs) | **FAIL** (L = 1 outputs and state differ) |
| D7 cache vs fresh compile | M2, 3 processes per condition | PASS | PASS | (not run) |

**Verdict.** Numba: deterministic under every condition tested, including per-step vs block execution (the W0.2
A6 property). JAX: deterministic *for a frozen compiled program* (D1–D4, D7), but its bits depend on the program's
shape: the scan `unroll` factor (5 unrolls → 5 digests), a remainder (peeled) iteration when the scan length is
not a multiple of `unroll` (D5 at unroll 4), a loop-free length-1 program vs a rolled loop (D6), and jit vs
eager. A JAX kernel can therefore satisfy D5 only with unroll 1 (or block-aligned snapshots), and cannot make
per-step execution bitwise-equal to block execution (W0.2 A6) on this stack. No XLA flag changes this (§3).

## 8. M5: Jacobians / gradients for transient-weighted identification (AD-34)

Problem (`code/gradlib.py`): 1 unit, 60 s window at 2 km / M0.6 with slams and chops (1,737 limiter switches in the
window), residuals N1, N2, Wf, T5 at 10 Hz (m = 2,400), transient weights 1 + 4·[≤ 5 s after a PLA move],
Jacobian at θ0 = θ*(1 + 0.05u). Reference: complex step (h = 1e-30) on the NumPy reference, all directions as
lanes (accuracy ≈ 1e-15; NumPy-CS vs Numba-CS ≤ 2.7e-15). 5 timed reps after one warm-up. Column error =
‖J_col − J_ref,col‖∞ / ‖J_ref,col‖∞. Threads: Numba columns spread over a 4-thread pool (kernels release the GIL).

**n = 30** (10 dynamic scalars + 10 accel + 10 decel schedule values; `m5_gradients_n30.json`)

| Method | Time s: median [min–max] | Col. error median / p95 / max | Cols ≤ 1e-6 | ∇ rel. error | Compile | Peak RSS |
|---|---|---|---|---|---|---|
| Numba forward sim (1×) | 0.0108 [0.0108–0.0108] | — | — | — | — | 140 MB |
| Numba forward FD, serial / 4 thr | 0.324 / 0.093 | 5.4e-6 / 3.6e-4 / 1.4e-3 | 27 % | 5.0e-6 | — | 140 MB |
| Numba central FD, serial / 4 thr | 0.648 / 0.183 | 1.1e-8 / 5.4e-5 / 1.1e-4 | 83 % | 1.9e-6 | — | 140 MB |
| **Numba complex step, serial / 4 thr** | **0.879** [0.878–0.886] / **0.523** [0.500–0.596] | 2.1e-15 / 2.0e-14 / 2.8e-14 | **100 %** | 1.2e-14 | ≈ 5.7 s (complex specialisation; sample check) | 140 MB |
| JAX forward sim | 0.130 [0.124–0.172] | — | — | — | 2.35 s | — |
| JAX jacfwd | 1.509 [1.204–2.386] | 4.2e-15 / 2.7e-14 / 3.2e-14 | 100 % | 2.0e-14 | 22.1 s | 2.3 GB* |
| JAX grad (reverse, scalar loss) | 0.989 [0.932–1.045] | — | — | 1.8e-14 | 19.1 s | 2.3 GB* |
| NumPy complex-step reference (once) | 17.5 | (reference) | | | — | 163 MB |

\* n = 30 JAX methods ran in one process (2.3 GB peak); they were split into one process per method for n = 240
(below) to attribute RSS (DEVIATIONS D2).

**n = 240** (n30 + the HP torque map, 15 × 14; many map cells are never visited → exact-zero columns;
`m5_gradients_n240.json`)

| Method | Time s: median [min–max] | Col. error p95 / max | Cols ≤ 1e-6 | ∇ rel. error | Compile | Peak RSS |
|---|---|---|---|---|---|---|
| Numba forward FD, serial / 4 thr | 4.12 / 1.10 | 6.0e-4 / 0.29 | 67 % | 6.7e-6 | — | 159 MB |
| Numba central FD, serial / 4 thr | 8.12 / 2.21 | 1.8e-6 / 3.5e-3 | 95 % | 3.1e-6 | — | 159 MB |
| Numba complex step, serial / 4 thr | 9.66 [9.45–9.94] / 4.43 [3.90–8.51] | 2.2e-14 / 3.3e-13 | 100 % | 8.4e-15 | — | 159 MB |
| JAX jacfwd | 2.92 [2.74–3.02] | 3.2e-14 / 9.5e-13 | 100 % | 6.7e-15 | 23.0 s | 2.25 GB |
| JAX grad | 1.04 [0.97–1.06] | — | — | 2.5e-14 | 16.3 s | 1.52 GB |
| JAX forward sim | 0.108 | — | — | — | 2.2 s | 523 MB |

**Reading.**
- Finite differences are **not acceptable** for AD-34 here: forward FD meets 1e-6 on 27 % (n = 30) of columns;
  central FD 83 % (at n = 240 central FD reaches 95 % only because many map columns are exactly zero, unvisited
  cells; its worst column is still 3.5e-3). The failures are schedule-knot and map columns (kinks in
  piecewise-linear tables and MIN/MAX selection), exactly the dynamic parameters AD-34 must identify. No FD perturbation flipped a limiter selection,
  so the error is kink/truncation error, not branch flips.
- **Complex step through the unchanged Numba kernel** is exact to ~1e-14 and costs ≈ 2.7 forward runs per column
  (complex arithmetic). Cost model: ≈ 29–40 ms per column serial, ≈ 17–19 ms with 4 threads.
- JAX `jacfwd` cost ≈ 1.3 s + 6.7 ms per column; reverse-mode `grad` ≈ 1.0 s regardless of n (two points,
  n = 30 and 240). Crossover with Numba complex step for a full Jacobian: n ≈ 40–50 (serial) or ≈ 115 (Numba on
  4 threads vs JAX on 1 device); for a scalar-loss gradient alone, JAX `grad` wins from n ≈ 35 (serial) to ≈ 55
  (4 threads). JAX pays 16–23 s compile per transformation and shape, and 1.5–2.3 GB RSS per process.
- **What calibration loses without autodiff** (owner question): nothing in accuracy; at n ≈ 30 (the size of the
  round-2 per-stage fits, and of AD-34's dynamic parameter sets, which are identified separately from the steady
  maps) nothing in speed either. It loses reverse-mode gradients whose cost does not grow with n (relevant only
  for gradient-only optimisation over large parameter sets), higher-order derivatives (Hessian-vector products),
  and it imposes a coding discipline: kernels must stay complex-analytic (comparisons on `.real`; no
  `abs`/`min`/`max` on derivative-carrying values; explicit branches).

## 9. M6: peak RSS per configuration (each in its own process)

| Configuration | Numba | JAX | NumPy |
|---|---|---|---|
| Sortie-hour, 1 unit (M1) | 119 MB | 513 MB (unroll 4) / 303 MB (unroll 1) | 265 MB (keeps 1 h outputs) |
| Cold compile process (M2) | 235–252 MB | 500–632 MB | — |
| Cache-hit process (M2) | 118–121 MB | 449–517 MB | — |
| 1,000 units × 60 s (M3) | 643–698 MB | 1.0–1.24 GB (vmap); 1.37–1.48 GB (sharded) | 548 MB |
| Jacobian n = 30 / 240 (M5) | 140 / 159 MB | 2.3 GB (n = 30, all methods) / 2.25 GB jacfwd, 1.52 GB grad (n = 240) | 163 / 308 MB (complex-step reference) |

All runs stayed under the 4 GB limit. For multiprocessing across tails, JAX's 0.3–0.6 GB per simulation process
(and 1.5–2.3 GB per calibration process) limits concurrency on a 16 GB machine; Numba's ≈ 120 MB does not.

## 10. M7: ergonomics (`m7_ergonomics.json`)

| Aspect | Numba | JAX |
|---|---|---|
| Kernel logical LOC (no comments/docstrings; NumPy reference 136) | 220 (single, prange batch, serial batch) | 162 (single, vmap, sharded, in-loop RNG) |
| Jacobian code (LOC) | 56 (FD + complex step; same kernel) | 49 (jacfwd + grad) |
| "Pure step over explicit state" | Pure `step_block(state arrays, params, tables, inputs, noise) → (new state, outputs)`; an in-place inner `_advance` per unit (local scalars) is shared by single, prange and serial entry points | `lax.scan` carry (tuple of scalars) in `jit`; functional by construction; pytrees free |
| Table lookups | Clamp + binary search loop + linear/bilinear formula; any grid | Clamp + `searchsorted(method="compare_all")` + gathers; the default `scan` method is 2–3× slower per step and `sort` 4–6× (tuning) |
| MIN/MAX limiter selection | `if` chain; only the taken branch executes | `jnp.where` chain; every branch executes (also under `vmap`); `lax.cond` becomes select under `vmap` |
| Rate groups (60 Hz controller in 240 Hz loop) | `if k % 4 == 0` | `jnp.where(ctrl, …)`: controller computed every step |
| Static shapes | Block length and batch size are runtime values | Each block length / batch size / unroll / transformation is a separate compile |
| Precision | float64 by default | x64 must be enabled globally at start-up (default float32) |
| Debugging | `NUMBA_DISABLE_JIT=1` runs the same source as Python, **bitwise-identical digest** (E2); pdb/print work; typing errors at compile are verbose | `jax.disable_jit()` runs eagerly but gives **different bits** from jit (E2); tracer errors for Python control flow on traced values; `jax.debug.print` |
| Derivatives | Complex step (same source, complex128 specialisation) or FD | Built-in `grad`/`jacfwd`/`jvp` |
| Branch-heavy discrete logic (BIT persistence, state machines) | Natural | Possible (`lax.switch`, `while_loop`), but `while_loop` is not reverse-differentiable and every select branch costs |

## 11. M8: usage-mode relevance (rough; `m8_usage.json`)

1 Hz PWL-style sortie-summary surrogate (N2 lag, T5 from the map, counters: time above 95 % N2c, a T5
exceedance integral, max T5, Type III-like cycles), measured on 1,000 sorties (3 reps), extrapolated to 30 tails
× 2 years × S sorties/tail/year (S = 150 / 200 / 250 [ASSUMPTION], 1 h sorties).

| S | Sorties | Surrogate NumPy | Surrogate Numba (4 thr) | Mission generation | Telemetry mode for every sortie: Numba / JAX (engine loop only, 1 core) |
|---|---|---|---|---|---|
| 150 | 9,000 | 4.7 s | 3.3 s | 21.6 s | 1.7 / 27.2 core-h |
| 200 | 12,000 | 6.3 s | 4.4 s | 28.8 s | 2.3 / 36.3 core-h |
| 250 | 15,000 | 7.8 s | 5.5 s | 36.0 s | 2.8 / 45.4 core-h |

The backend choice is irrelevant for the usage-mode surrogate (seconds either way; NumPy suffices; scenario
generation and the event-driven operations layer will dominate). It matters for telemetry-mode rendering: a
16× difference in engine-loop core-hours if sorties are rendered at full rate.

## 12. RNG: can it stay backend-independent? **Yes** (`rng.json`)

| Check | Result |
|---|---|
| R1 keyed block cost (SeedSequence(root, spawn_key) → Philox → 2,400 × 2 normals) | 70 µs per block (29 µs of it construction), 38 kB; **25 ms per unit-hour** (≈ 4 % of the Numba hour kernel; < 0.3 % of JAX) |
| Blocks fed into every backend | Numba and JAX consume the same float64 arrays; Numba = NumPy bitwise (A1), JAX within 5e-14 (A1) |
| R2 Numba in-loop `Generator(Philox)` passed into `@njit` | **Same stream as the NumPy block, bitwise**; same generator state afterwards; 47 µs vs NumPy's 41 µs per block |
| R3 Numba kernel with in-kernel block generation vs block-fed | Outputs bitwise identical (60 s) |
| R4 JAX in-loop threefry (`normal(fold_in(key, k))`) | Deterministic (single = vmap) but **doubles** JAX block time (55 vs 27 ms per 2,400 steps) and is a **different stream** by construction (threefry + inverse-erf vs Philox + ziggurat) → backend-specific |

Feeding pre-generated keyed blocks keeps RNG backend-independent, keeps CRN and forks exact (a snapshot needs only
the key path, block index and offset), and costs a few per cent. Architecture §15's "Threefry if JAX is chosen"
does not apply.

## 13. Recommendation and evidence

**AD-22 → D: Numba (`@njit`, fastmath off, `cache=True`) for all compiled hot loops; RNG stays in NumPy
(keyed Philox blocks fed to the kernel); AD-34 Jacobians by complex step through the same kernel source.**

| Evidence | Numba | JAX | Weight |
|---|---|---|---|
| Determinism D1–D7 incl. block = per-step | all pass | D5/D6 depend on program shape | gate |
| Agreement with the reference | bitwise | 5e-14, no branch flips | gate (both pass tolerance) |
| Sortie-hour, 1 core | 0.68 s (5,270×) | 10.9 s (330×), 1.7 cores | budget: Numba only |
| 1,000 × 60 s, 1 core | 10.7 s | 12.2 s | comparable |
| Jacobian n = 30 (accuracy ≤ 1e-6 all cols) | 0.88 s / 0.52 s (4 thr) | 1.51 s + 22 s compile | Numba |
| Jacobian n = 240 | 9.7 s / 4.4 s | 2.9 s + 23 s compile | JAX (flip F1) |
| Gradient of scalar loss, n = 240 | (= Jacobian) | 1.0 s + 16 s compile | JAX (flip F1) |
| Compile, cold / cache hit | 4–6 s / 0.2 s | 2–7 s / 0.9–1.1 s per shape; 16–23 s for AD | Numba |
| Peak RSS | 0.12–0.7 GB | 0.3–2.3 GB | Numba |
| Debug path bitwise = compiled | yes | no | Numba |

## 14. Implications for the core module contract (W0.2)

1. **State: arrays, not pytrees.** Each module's state is a fixed schema of named fields stored as contiguous
   typed arrays (per unit: one float64 vector and one int64 vector, or `[U, n]` for batches), with name → index
   constants. The W0.2 "flat typed pytree of NumPy arrays" is fine at the Python level and for serialisation, but
   kernels take positional arrays / NamedTuples of arrays, never dicts (`typed.Dict` is slow). Integer phase
   counters (rate-group phase, step index) live in the int state so arbitrary-step snapshots are exact (D5).
2. **`step_block`** = `@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)` pure function
   `(state arrays, params vector, tables NamedTuple, inputs[L, ·], noise[L, ·]) → (new state arrays,
   outputs[L, ·])`. One per-unit inner `_advance` (local scalars, in-place on fresh copies) serves the single-unit
   path, the `prange` batch and a serial batch. Block length L is a runtime value; per-step execution is
   `step_block` with L = 1 and is bitwise identical (W0.2 A6 holds by construction). No cross-unit reductions
   inside `prange`; reduce afterwards in a fixed order.
3. **RNG feeding.** The kernel's feeding layer draws keyed, counter-addressable blocks in NumPy
   (`block(key_path, b, size)` → float64 arrays) and passes them as an input array. Snapshots store (key path,
   block index, offset). In-kernel `Generator` draws reproduce the same stream bitwise but put generator state
   into the snapshot; keep them as an option, not the default.
4. **Parameters** as a flat float64 vector + index constants (calibratable entries are perturbed by index); tables
   as NamedTuples of arrays with breakpoint reciprocals precomputed once in NumPy. Never bake calibrated values in
   as compile-time globals.
5. **Complex-step-safe kernels (AD-34).** Comparisons on `.real`, explicit `if` branches instead of
   `abs`/`min`/`max` on derivative-carrying values, no truncation of state to int. Each W1 module gets a test:
   complex-step Jacobian ≈ central FD on a smooth window.
6. **Golden files**: the NumPy reference and the `NUMBA_DISABLE_JIT=1` path are bitwise-identical to compiled
   code, so golden digests can be produced and debugged without compilation; digests are per platform (R7).
7. **Threads**: `NUMBA_NUM_THREADS` set by the run configuration; the `workqueue` layer must not be entered
   concurrently from several Python threads (one parallel region at a time per process; use processes across
   tails). Calibration may use a thread pool over Jacobian columns (kernels release the GIL).

## 15. Risks and flip conditions

**Flip conditions** (the measured result that would reverse the choice):
- **F1 → hybrid** (Numba time-stepping + a JAX calibration-only port): AD-34 fits need Jacobians with n ≳ 100–150
  parameters per fit, or gradient-only optimisation with n ≳ 40, run often enough that JAX's 1.5–9× per-evaluation
  advantage (n = 240: `jacfwd` 2.9 s, `grad` 1.0 s vs complex step 9.7 s serial / 4.4 s on 4 threads) outweighs
  16–23 s compile per shape, 1.5–2.3 GB per process and a second implementation that agrees only to ~5e-14.
  Measured today at n = 30: not met.
- **F2 → JAX alone**: requires **both** (a) an XLA option that disables FMA contraction and reciprocal rewrites so
  numerics stop depending on program shape (D5 and D6 pass, block = per-step bitwise), and (b) single-unit cost
  ≤ ~1 µs/step (≥ 1,000× with margin; measured 12.6 µs/step). Neither exists on this stack.
- **F3**: wide-batch telemetry rendering (≥ 1,000 lanes) becoming the dominant cost **and** JAX vmap per-core
  throughput ≥ 1.5× Numba's (measured 0.88×).
- Not flips: a heavier real M07 step (A-W0.6-2) scales both backends; Numba keeps its margin (iterative Newton
  solves are natural in Numba, awkward to differentiate in JAX). GPU is out of scope (architecture §13).

**Risks** (Numba path):
- Complex-step discipline can be broken silently by one non-analytic op → wrong derivatives. Mitigation: the
  per-module CS-vs-FD test (§14.5).
- Jacobian cost is O(n) (≈ 3 forward runs per column); large map identification grows linearly (F1).
- Bitwise results are platform- and version-specific (A-W0.6-3): golden digests per platform; pin Numba/llvmlite.
- Timing variance on the shared Apple P/E-core machine (Numba hour 0.67–2.29 s across sessions): budget on the
  pessimistic figure (still ≥ 1,500×).
- `workqueue` threading layer is not thread-safe for concurrent parallel regions; TBB/OpenMP layers are not
  installed (would need a coordinator-added package).
- The workload omits an iterative CLM solve (PROXY A-W0.6-2): re-run this harness on the W1 M07/M08 kernel.

## 16. Proposed AD-22 register entry (for the coordinator)

| ID | Decision | Choice | Evidence | Status |
|---|---|---|---|---|
| AD-22 | Compute | CPU-first, compiled hot loops in **Numba** (`@njit`, fastmath off, `cache=True`); `step_block` pure over state arrays with runtime block length; batches via `prange` over units; RNG as keyed NumPy Philox blocks fed to kernels; AD-34 Jacobians by complex step through the same kernel. JAX not used in the build (revisit only under flip F1/F2). | W0.6 `analysis/backend_benchmark/RESULTS.md`: bitwise determinism D1–D7 and reference agreement (Numba); 5,270× vs 330× real time (M1); complex-step Jacobian n = 30 in 0.88 s, exact to 3e-14, FD fails (M5) | D |

Also: architecture §15 "Threefry if the JAX backend is chosen" → delete; §13 "decided by the phase-1 benchmark" →
reference this file.
