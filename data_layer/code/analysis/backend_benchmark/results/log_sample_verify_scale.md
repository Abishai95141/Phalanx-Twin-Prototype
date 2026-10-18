# Sample → verify → scale log (W0.6)

Chronological. Each entry: sample, check, outcome, decision to scale.

1. **10 s × 1 unit (sortie start), NumPy vs Numba (in-process smoke).** Outputs and limiter codes bitwise equal
   (digest `50135d5f…`, pre-StreamDigest scheme); Numba first call 18.3 s (compile), second 8.5 ms. NumPy 5.6 s
   (2.35 ms/step → ≈ 34 min per sortie-hour). → scale Numba to 1 h; run the NumPy hour once in the background.
2. **10 s × 1 unit, NumPy vs JAX (unroll 1).** Not bitwise: 8,627 of 14,400 output values differ, max relative
   2.3e-14, first difference at step 0 in Wf; limiter codes identical. → op-level conformance test to find the
   mechanism before scaling.
3. **Op-level conformance, n = 100,000 keyed inputs (`s00_oplevel.py`).** Numba = NumPy bitwise on all 13 ops.
   JAX jit differs on a·b+c (FMA contraction), x/288.15 (reciprocal multiply), (b−a)/s with a broadcast runtime
   scalar (vectorised context only), exp (XLA's own implementation); pow, log, sqrt, +, ×, ÷ agree.
   (The first run's ULP column had an int64→float64 cast bug; fixed to exact int64 differences and re-run.)
4. **XLA flag probe (`s00b_xla_flags.py`), 8 flag sets.** No accepted flag changes any mismatch count
   (`xla_cpu_enable_fast_math=false`, `xla_allow_excess_precision=false`,
   `xla_cpu_enable_platform_dependent_math=false`, `xla_cpu_fast_math_honor_*`); two candidate flags are not
   recognised by this jaxlib. → JAX is compared to the reference within a tolerance (A1), not bitwise.
5. **1 h × 1 unit, Numba (sanity before timing).** All finite; N2c 0.69–1.03, N1c 0.63–1.03, Wf 0.04–1.18 kg/s,
   T5 661–1,172 K; every limiter branch engages (governor 755,232 steps, N1 11,456, T5 50,940, accel 10,336,
   decel 35,960, Wf_min 76); 42,691 selection switches. Kernel 2.29 s, feed 0.25 s. → workload is
   representative of MIN/MAX stress; proceed.
6. **JAX tuning, 60 s × 1 unit, 20 configurations × 3 reps (`s01_jax_tuning.py`).** Fastest: `compare_all`
   bracket, unroll 4 (15.2 µs/step). The bracket method never changes the digest; **the unroll factor does
   (5 unroll values → 5 distinct digests)**. → use compare_all + unroll 4 for timing; test unroll 1 in M4.
7. **M5 sample: 3 Jacobian columns, complex step, NumPy reference vs Numba kernel.** Agree to ≤ 2.7e-15 relative
   (complex arithmetic implementations differ); the complex run's real part differs from the float run by
   ≤ 8.9e-15 (complex vs real `pow`). → reference accuracy ≈ 1e-15; scale to all 30 columns.
8. **M5 n = 30 (full).** FD fails the pre-registered accuracy bar (forward 27 %, central 83 % of columns ≤ 1e-6);
   Numba complex step and JAX AD both ≤ 3.2e-14. JAX gradient processes peak at 2.3 GB RSS (combined process). →
   split JAX methods into separate processes for M6; run n = 240.
9. **M4 D1–D6 (both backends; 1 / 10 / 100 / 1,000 units).** Numba passes all. JAX (unroll 4) passes D1–D4,
   fails D5 at an arbitrary step (passes at a block boundary) and D6. → re-run JAX with unroll 1.
10. **M4 JAX unroll 1.** D1–D5 pass (including the arbitrary-step snapshot); D6 still fails for block length 1
    (a loop-free program has different numerics from the rolled scan loop). → recorded as a JAX constraint.
11. **M7 E2 (240 steps).** Numba compiled = Numba uncompiled (`NUMBA_DISABLE_JIT=1`) bitwise; JAX eager
    (`disable_jit`) = NumPy/Numba bitwise, JAX jit differs → the JAX differences come from XLA compilation.
12. **RNG (`s08_rng.py`).** Numba in-loop `Generator(Philox)` reproduces the NumPy block stream bitwise and ends
    in the same generator state; in-kernel generation = block-fed outputs bitwise; JAX in-loop threefry is
    deterministic single vs vmap but doubles JAX block time.
