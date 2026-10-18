# W0.6 Backend benchmark: pre-registration

**Decides:** AD-22 (Numba vs JAX on CPU, or a hybrid). **Brief:** `docs/build_briefs/W0.6_backend_benchmark.md`.
**Written and committed before any measurement is generated** (RULES.md rule 4). Deviations go to
`DEVIATIONS.md` with date, reason and results both ways.

No real data is read. The workload is a synthetic, deterministic benchmark model; there is no holdout.

## 1. Question

Which backend should the build's compiled hot loops use: Numba, JAX on CPU, or a hybrid (Numba time-stepping +
JAX for calibration gradients)? Sub-question: can RNG stay backend-independent by feeding pre-generated keyed
Philox blocks into the compiled loop?

## 2. Workload (fixed before measuring)

A two-spool engine mini-model in closed loop with an M08-like governor. **It is a benchmark workload, not a
physics deliverable**: parameter values are representative (tagged in `code/workload.py`), never used by the build.

- **Plant (continuous, SI):** N1, N2 rotor ODEs (dN/dt = Q/I) with net torques from **2-D bilinear tables on
  non-uniform grids** (HP: Q(N2c, Wfc); LP: Q(N1c, N2c)); fuel-metering actuator lag; PS3 volume lag; EGT (T5)
  first-order response with τ = τ_ref·(W/W_ref)^w_exp, w_exp = −0.5 (τ ∝ W^−0.5, `pow` per evaluation); a metal
  temperature state that opens HP clearance (heat soak); θ^a inlet correction with a = 0.73 (`pow` per step).
  Per-unit health scalars (AD-07 style) enter as map-input multipliers.
- **Sub-stepping:** outer step 240 Hz (AD-11), 4 inner Heun (RK2) sub-steps → 8 derivative evaluations, 24 2-D and
  16 1-D table lookups per outer step.
- **Controller (M08-like):** 60 Hz rate group (every 4th truth step, phase kept in state). PI on N2 error with
  back-calculation anti-windup; MIN/MAX selection over {N2 governor, N1 topping limiter, T5 limiter, accel Wf/PS3
  schedule} then MAX with {decel Wf/PS3 schedule, Wf_min}. Selected branch kept in state.
- **Disturbances (AD-32):** two AR(1) per-unit process disturbances (fuel metering, LP load torque), innovations
  drawn from **pre-generated keyed blocks**: NumPy `SeedSequence(root, spawn_key=digest(key path) + (block,))` →
  `Philox` → `standard_normal`, block = 2,400 steps (10 s). In-loop generation is tried where natural (Numba
  `Generator` argument; JAX `threefry` `fold_in`).
- **State:** 10 float64 + 2 int64 (step index, selected limiter). Inputs per step: PLA, T2, P2.
- **Outputs per step:** N1, N2, Wf, PS3, T5, Tm (float64) and the selected-limiter code.

## 3. Implementations

1. **NumPy reference** (`code/ref_numpy.py`): Python loop over steps, vectorised over units; dtype-generic, so the
   same code runs in complex128 for the complex-step derivative reference.
2. **Numba** (`code/be_numba.py`): `@njit(cache=True, fastmath=False)` scalar kernel; `step_block` over a block;
   batch via `prange` over units.
3. **JAX** (`code/be_jax.py`): x64 enabled; `lax.scan` over a block inside `jax.jit`; batch via `vmap`; multi-core
   via multiple CPU devices; gradients via `jacfwd` / `grad`.

Every backend evaluates the same expression tree in the same order as the reference. fastmath is off everywhere.

## 4. Measurements, sample sizes and repetitions (fixed in advance)

Sample → verify → scale: 10 s × 1 unit vs the reference first, then 60 s, then 1 h; batch 10 units, then 1,000.
Each check is logged in `results/log_sample_verify_scale.md`.

| ID | Measurement | Sample | Repetitions | Statistic |
|---|---|---|---|---|
| M1 | Single sortie-hour (864,000 outer steps), 1 unit | 1 unit × 1 h | 5 per compiled backend (warm, in one process); NumPy reference 1 (expensive; a 60 s × 3 run gives its variance) | median, min, max, SD; × real time |
| M2 | Compile overhead: cold (fresh process, empty cache), warm (same process, 2nd call), cache-hit (fresh process, populated cache) | each kernel variant | 3 fresh processes per condition | median, min, max |
| M3 | 1,000 units × 60 s; thread scaling 1, 2, 4 (and 8 once) | 1,000 units | 3 per thread count | median, min, max; speed-up and efficiency |
| M4 | Determinism (see §5) | 10–60 s; 1–1,000 units | as listed per check | bitwise yes/no (blake2b hashes) |
| M5 | Jacobian / gradient over a 60 s transient window, n = 30 parameters (scalars + accel/decel schedule knots), and n ≈ 200 (+ HP torque-map entries) | 1 unit, 60 s | 5 | time median/min/max; accuracy vs complex-step reference |
| M6 | Peak RSS per configuration (each run in its own process) | per M1/M3/M5 config | from the same runs | max RSS |
| M7 | Ergonomics: logical LOC, how lookups / MIN-MAX / pure step map, debuggability | code | — | table |
| M8 | Usage-mode estimate: sortie-summary surrogate for 30 tails × 2 years | rough | 3 | extrapolated wall time |

**Why these n.** Timing medians over 5 (M1/M5) or 3 (M2/M3) repetitions are enough to detect the ≥ 1.5× differences
the decision rule cares about; min–max ranges are reported so overlap is visible. Determinism is a yes/no property:
one counter-example falsifies it, so each condition is run at least twice (repeat) and in two processes.
Thread limits: ≤ 4 threads for all runs except one 8-thread scaling point (machine shared with four agents).

## 5. Determinism checks (M4 → A3)

Per backend, bitwise-identical outputs (blake2b of outputs + final state) across: (D1) repeated in-process runs;
(D2) separate processes; (D3) single-unit vs batched execution (unit i of a batch vs unit i alone); (D4) thread
counts / device counts 1, 2, 4; (D5) snapshot at a step that is not a multiple of the block length or of the
controller period → serialise to bytes → restore → continue, vs uninterrupted; (D6) block length 1 / 240 / 2,400;
(D7) compiled-from-cache vs freshly compiled. Plus: agreement with the NumPy reference (A1), bitwise or within a
stated tolerance with the mechanism identified by an op-level conformance test (exp, pow, sqrt, division, a·b+c).

## 6. Decision rule (fixed before measuring)

**Gate for the primary time-stepping backend** (all must hold): D1–D7 bitwise; agreement with the reference
bitwise or ≤ 1e-12 relative over 60 s with an identified mechanism.

**Engine-loop budget:** ≥ 1,000× real time on one core for M1 (≤ 3.6 s per sortie-hour). Rationale: at the
architecture's ≥ 50× target the whole telemetry chain gets 72 s per sortie-hour; the engine loop is one of ≳ 10
continuous modules plus encoding, so it should take ≤ 5 % of that budget.

**Materially faster:** ≥ 1.5× on the median with non-overlapping min–max ranges.

**Gradient requirement (AD-34):** a full residual Jacobian (n ≈ 30) over a 60 s window with ≥ 95 % of columns
within 1e-6 relative (∞-norm) of the complex-step reference; time per Jacobian recorded.

**Choice:**
1. If one backend passes the gate, is not materially slower on M1 and M3, and offers a gradient path meeting the
   requirement within 2× of the fastest gradient path → that backend alone.
2. If Numba passes the gate and is materially faster on M1 or M3, but every Numba gradient path (forward/central
   FD, complex step through the same kernel) misses the accuracy requirement or is > 5× slower than JAX `jacfwd`
   → hybrid (Numba time-stepping, JAX for calibration), conditional on the JAX port matching the Numba kernel to
   ≤ 1e-12 relative on the calibration window.
3. If JAX passes the gate, is within 1.5× of Numba on M1 and at least as fast on M3 → JAX alone.
4. Otherwise: the backend that passes the gate with the best M1, with the gradient path stated as a risk.

Compile overhead (M2) and ergonomics (M7) are tie-breakers and risk items, not gates, unless cold compile exceeds
60 s per process with no working persistent cache (then it counts as a fail for usage-mode forks).

**Flip conditions** are reported from the measured margins: the result that would reverse the choice.

## 7. Credibility and scope

Benchmark on one machine (Apple M4, 10 cores, 16 GB, macOS); Kaggle (x86, 4 cores) is not measured. Platform
transfer of bitwise results is not claimed. The workload approximates the cost structure of M07/M08/M03; it omits
an iterative component-matching solve, which is reported as a risk item.
