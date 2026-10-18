"""M3: batch of 1,000 units x 60 s ('combat' windows), and thread / device scaling.

Each configuration in its own process; one warm-up block, then 3 timed repetitions. Thread counts 1, 2, 4 for
all runs; 8 only once (the machine is shared). NumPy (vectorised over the 1,000 units) once, as a baseline.
  numba prange           NUMBA_NUM_THREADS = 1 / 2 / 4 / 8
  jax vmap               1 device, XLA intra-op threading off (unroll 1 and 4) and on (default thread pool)
  jax sharded            vmap partitioned over 2 / 4 / 8 CPU devices (jax_num_cpu_devices)

Usage: python -I code/s07_m3_batch.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import machine_info, run_worker, save_json, stats

U = 1000
STEPS = 14_400
XLA_OFF = "--xla_cpu_multi_thread_eigen=false"


def summarize(r):
    k = [x["t_kernel"] for x in r["reps"]]
    w = [x["t_wall"] for x in r["reps"]]
    c = [x["t_cpu"] for x in r["reps"]]
    unit_s = U * STEPS / 240.0
    return {
        "kernel_s": stats(k),
        "wall_incl_feed_s": stats(w),
        "feed_s": stats([x["t_feed"] for x in r["reps"]]),
        "cpu_over_wall": stats([ci / wi for ci, wi in zip(c, w, strict=True)]),
        "unit_sim_s_per_wall_s_kernel": unit_s / stats(k)["median"],
        "us_per_unit_step_kernel": stats(k)["median"] / (U * STEPS) * 1e6,
        "t_first_call": r["t_first_call"],
        "peak_rss_mb": r["peak_rss_mb"],
        "digest": r["all_digest"],
    }


def main():
    res = {"machine": machine_info(), "units": U, "steps": STEPS, "rows": {}}
    base = ["run", "--units", str(U), "--kind", "combat", "--steps", str(STEPS), "--keep-digests", "0"]
    cfgs = []
    for t in (1, 2, 4, 8):
        cfgs.append((f"numba_prange_t{t}", ["--backend", "numba", "--mode", "prange"], {"NUMBA_NUM_THREADS": str(t)},
                     3))  # fmt: skip
    for ur in (1, 4):
        cfgs.append((f"jax_vmap_1dev_xla1t_unroll{ur}", ["--backend", "jax", "--mode", "vmap", "--unroll", str(ur)],
                     {"XLA_FLAGS": XLA_OFF}, 3))  # fmt: skip
    cfgs.append(("jax_vmap_1dev_xla_default_threads_unroll4", ["--backend", "jax", "--mode", "vmap", "--unroll", "4"],
                 {"XLA_FLAGS": ""}, 3))  # fmt: skip
    for nd in (2, 4, 8):
        cfgs.append((f"jax_sharded_{nd}dev_unroll4", ["--backend", "jax", "--mode", "sharded", "--ndev", str(nd),
                     "--unroll", "4"], {"XLA_FLAGS": XLA_OFF}, 3))  # fmt: skip
    cfgs.append(("numpy_vectorised", ["--backend", "numpy"], {}, 1))
    for name, args, env, reps in cfgs:
        r = run_worker([*base, *args, "--reps", str(reps)], env, timeout=7200)
        res["rows"][name] = summarize(r)
        res["rows"][name]["reps"] = reps
        print(name, round(res["rows"][name]["kernel_s"]["median"], 3), "s",
              round(res["rows"][name]["cpu_over_wall"]["median"], 2), "cpu/wall", file=sys.stderr)  # fmt: skip
    nb1 = res["rows"]["numba_prange_t1"]["kernel_s"]["median"]
    res["numba_speedup_vs_1t"] = {
        t: nb1 / res["rows"][f"numba_prange_t{t}"]["kernel_s"]["median"] for t in (1, 2, 4, 8)
    }
    j1 = res["rows"]["jax_vmap_1dev_xla1t_unroll4"]["kernel_s"]["median"]
    res["jax_speedup_vs_1dev"] = {nd: j1 / res["rows"][f"jax_sharded_{nd}dev_unroll4"]["kernel_s"]["median"]
                                  for nd in (2, 4, 8)}  # fmt: skip
    save_json("m3_batch.json", res)


if __name__ == "__main__":
    main()
