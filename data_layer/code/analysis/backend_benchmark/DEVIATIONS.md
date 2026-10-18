# Deviations from PREREGISTRATION.md (W0.6)

All dated 2026-10-14. Results are reported both ways where a deviation changed a measurement.

## D1. Paired re-measurement of the batch thread points (M3b), added after M3

- **Reason.** During M3 the shared machine's load average was 7–8.5 (other agents); Numba at 4 threads reached
  only 2.07 CPU/wall, so the 4-thread points were contention-limited.
- **Change.** `code/s07b_m3_paired.py`: Numba 1 thr / JAX vmap 1 dev / Numba 4 thr / JAX 4 dev alternating,
  2 rounds × 3 reps, so both backends share the background load.
- **Results both ways.** M3 as pre-registered (RESULTS §6) and M3b (RESULTS §6b). M3b was itself swamped (load
  average 22–38, CPU/wall down to 0.36), so it is inconclusive for speed; M3 remains the record. Digests were
  unchanged under contention. The decision does not depend on either (per-core comparable; no JAX scaling
  advantage).

## D2. M5 JAX methods split into one process per method (after the n = 30 run)

- **Reason.** The n = 30 run measured `forward_sim`, `jacfwd` and `grad` in one process (peak 2.3 GB), which
  does not attribute RSS per method (M6).
- **Change.** For n = 240 each JAX method ran in its own process (`--method jax_<name>`). The n = 30 run was not
  repeated because the machine load had risen to 22–40 (timings would not be comparable).
- **Effect.** n = 30 JAX RSS is reported as the combined 2.3 GB; n = 240 per method (jacfwd 2.25 GB, grad
  1.52 GB, forward 0.52 GB). Timings are unaffected by the split.

## D3. Additions that do not change pre-registered criteria

- **JAX configuration selection** (`s01_jax_tuning.py`): 4 bracket methods × 5 unroll factors chosen the fastest
  JAX configuration before M1 (fairness). Not pre-registered; it can only favour JAX.
- **M4 re-run for JAX with unroll 1** after the unroll-4 failures of D5/D6, to separate configuration effects
  from fundamental ones. Both runs are reported.
- **D5 at a block boundary (k = 4,800)** in addition to the pre-registered arbitrary step (k = 5,237), to separate
  snapshot effects from block-length effects.
- **Op-level conformance** (`s00_oplevel.py`, `s00b_xla_flags.py`) to identify the A1 mechanism; the first run's
  ULP column had an int64 → float64 cast bug (mismatch counts were right); fixed and re-run, the JSON is the
  re-run.
- **M5 at n = 240** besides the pre-registered n = 30 (pre-registered as "n ≈ 200"; 240 = 30 + the 15 × 14 map).
- **M8**: measured on 1,000 sorties and extrapolated, as the brief asks for a rough estimate.
