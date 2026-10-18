# W0.6 Backend benchmark (AD-22: Numba vs JAX on CPU)

Decides which backend compiles the build's hot loops. Brief: `docs/build_briefs/W0.6_backend_benchmark.md`.
Pre-registration: `PREREGISTRATION.md` (committed before any measurement). Results and the recommendation:
`RESULTS.md`. Raw results: `results/*.json`. Sample → verify → scale log: `results/log_sample_verify_scale.md`.

## Workload

A two-spool engine mini-model in closed loop with an M08-like governor (`code/workload.py`). It is a
**benchmark workload, not a physics deliverable**: values are representative and tagged; the build never reads
them. Structure: N1/N2 rotor ODEs on 2-D bilinear torque maps (non-uniform grids), fuel-actuator lag, PS3 volume
lag, EGT lag with τ ∝ W^−0.5 (`pow` per evaluation), metal temperature (heat soak), θ^0.73 correction; 4 Heun
sub-steps per 240 Hz truth step (8 derivative evaluations, 24 2-D + 16 1-D lookups per step); 60 Hz controller
with PI + MIN/MAX selection over five limiters; two AR(1) per-unit process disturbances fed from keyed Philox
blocks (`code/rngblocks.py`).

## Code

| File | Role |
|---|---|
| `code/workload.py` | Parameters (tagged), tables, mission inputs, initial state, index constants |
| `code/rngblocks.py` | Keyed, counter-addressable RNG blocks (SeedSequence spawn keys → Philox) |
| `code/ref_numpy.py` | NumPy reference (oracle); dtype-generic (float64 / complex128 for complex step) |
| `code/be_numba.py` | Numba backend: `step_block`, `step_block_batch` (prange), serial batch |
| `code/be_jax.py` | JAX backend: `step_block` (scan in jit), `step_block_batch` (vmap), `sharded_batch`, in-loop RNG variant |
| `code/harness.py` | Scenario (units, missions, health, initial state), backend adapters, block runner, stream digests |
| `code/worker.py` | Fresh-process runner (one configuration → one JSON line) |
| `code/gradlib.py` | M5 problem (60 s transient window, transient-weighted residuals) and complex-step reference |
| `code/s00_oplevel.py`, `code/s00b_xla_flags.py` | Op-level conformance across backends; XLA flag probe |
| `code/s01_jax_tuning.py` | JAX configuration selection (scan unroll × bracket search) |
| `code/s02_ref_hour.py`, `code/s02_m1_sortie_hour.py` | NumPy 1 h reference; M1 |
| `code/s03_a1_agreement.py` | A1 agreement with the reference (10 s, 60 s × 10 units, 1 h) |
| `code/s04_m2_compile.py` | M2 compile overhead, caches, D7 |
| `code/s05_m4_determinism.py` | M4 D1–D6 |
| `code/s06_m5_gradients.py` | M5 Jacobians / gradients (n = 30, 240) |
| `code/s07_m3_batch.py` | M3 1,000 units × 60 s, thread / device scaling |
| `code/s07b_m3_paired.py` | M3b paired, alternating 1-/4-core re-measurement (DEVIATIONS D1) |
| `code/s08_rng.py` | RNG question (feed cost; Numba in-loop Generator; JAX in-loop threefry) |
| `code/s09_m8_usage.py` | M8 usage-mode estimate |
| `code/s10_m7_ergonomics.py` | M7 LOC and debuggability evidence |
| `code/s11_regress.py` | Regression check: committed code reproduces the recorded digests (exit 1 on mismatch) |
| `code/summarize.py` | Prints compact summaries of the JSON results |

## Environment

- Shared pinned `.venv-build` (uv.lock): Python 3.13.3, NumPy 2.5.4, Numba 0.68.0 (llvmlite 0.50.0, threading
  layer `workqueue`), JAX/jaxlib 0.11.2 (CPU), SciPy 1.18.1. Nothing added.
- Machine: Apple M4 (4 performance + 6 efficiency cores), 16 GB, macOS 26.2. Shared with other agents; thread
  counts ≤ 4 except one 8-thread scaling point.
- Thread control: `NUMBA_NUM_THREADS`; JAX `XLA_FLAGS=--xla_cpu_multi_thread_eigen=false` (one intra-op thread)
  and `jax_num_cpu_devices` for multi-device runs; `OMP_NUM_THREADS=1`.
- Caches: Numba `NUMBA_CACHE_DIR=_cache/numba`; JAX persistent cache via `BENCH_JAX_CACHE` (M2 only).
  `_cache/` is git-ignored (large regenerable files: reference outputs, Jacobians).

## Commands (from this directory; `PY=/Users/abishaikc/Phalanx/.venv-build/bin/python`)

```bash
$PY -I code/s00_oplevel.py            # op-level conformance          -> results/oplevel.json
$PY -I code/s00b_xla_flags.py         # XLA flags probe               -> results/xla_flags.json
$PY -I code/s01_jax_tuning.py         # JAX config selection          -> results/jax_tuning.json
$PY -I code/s02_ref_hour.py           # NumPy 1 h reference (~35 min) -> results/ref_hour.json, _cache/ref_hour.npz
$PY -I code/s03_a1_agreement.py       # A1                            -> results/a1_agreement.json
$PY -I code/s02_m1_sortie_hour.py     # M1                            -> results/m1_sortie_hour.json
$PY -I code/s04_m2_compile.py         # M2 + D7                       -> results/m2_compile.json
$PY -I code/s07_m3_batch.py           # M3                            -> results/m3_batch.json
$PY -I code/s07b_m3_paired.py         # M3b (deviation D1)            -> results/m3b_paired.json
$PY -I code/s05_m4_determinism.py     # M4 D1-D6                      -> results/m4_determinism.json
BENCH_BACKENDS=jax BENCH_JAX_UNROLL=1 BENCH_M4_OUT=m4_determinism_jax_unroll1.json $PY -I code/s05_m4_determinism.py
$PY -I code/s06_m5_gradients.py 30    # M5 n=30                       -> results/m5_gradients_n30.json
$PY -I code/s06_m5_gradients.py 240   # M5 n=240                      -> results/m5_gradients_n240.json
$PY -I code/s08_rng.py                # RNG question                  -> results/rng.json
$PY -I code/s09_m8_usage.py           # M8                            -> results/m8_usage.json
$PY -I code/s10_m7_ergonomics.py      # M7                            -> results/m7_ergonomics.json
$PY -I code/s11_regress.py            # regression: recorded digests reproduce (A5)
```

Each driver starts every configuration in a fresh `python -I` process (scripts insert their own directory into
`sys.path`; nothing is executed from data directories; no real data is read).

## Assumptions and validation criteria

- The workload's numbers are `[ASSUMPTION]`/`[TRANSFER]`/`[MEASURED: proxy]` benchmark values (tags in
  `code/workload.py`); registered as A-W0.6-1 in `docs/assumptions.md`. They affect timings only through the
  frequency of limiter switching and table-cell crossings.
- Validation criteria are the pre-registered acceptance checks A1–A5 and the decision rule (PREREGISTRATION §6).

## Lint

`analysis/` is excluded from the project's ruff gate (`pyproject.toml`). The benchmark code is ruff-formatted and
passes `ruff check` except 51 E501 long lines (tagged parameter strings, tables).

## Known limitations

- One machine (arm64 macOS). Bitwise results are not claimed to transfer to x86 (Kaggle) or other library
  versions; the build's golden files must be per platform and backend (build plan risk R7).
- The workload has no iterative (Newton) component-matching solve; see RESULTS.md risks.
- Timings were taken on a machine shared with other agents; variance is reported, not hidden.
