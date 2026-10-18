"""JAX configuration selection (fairness): scan unroll x bracket-search method, single unit, 60 s horizon.

Each configuration runs in a fresh process (1 compile + 3 timed repetitions). The fastest configuration whose
digest equals the others' is used for JAX in M1-M6. Single XLA thread (--xla_cpu_multi_thread_eigen=false).

Usage: python -I code/s01_jax_tuning.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from common import machine_info, run_worker, save_json

STEPS = 14_400  # 60 s: long enough that per-call overhead is < 1 % of a rep; 3 reps for the median
XLA_1T = "--xla_cpu_multi_thread_eigen=false"


def main():
    rows = []
    for bracket in ("sumcmp", "compare_all", "scan", "sort"):
        for unroll in (1, 2, 4, 8, 16):
            r = run_worker(
                ["run", "--backend", "jax", "--mode", "single", "--steps", str(STEPS), "--reps", "3",
                 "--unroll", str(unroll)],
                {"XLA_FLAGS": XLA_1T, "BENCH_JAX_BRACKET": bracket},
            )  # fmt: skip
            k = [x["t_kernel"] for x in r["reps"]]
            row = {"bracket": bracket, "unroll": unroll, "t_compile_first_call": r["t_first_call"],
                   "kernel_median_s": float(np.median(k)), "kernel_reps": k, "digest": r["all_digest"],
                   "us_per_step": float(np.median(k)) / STEPS * 1e6}  # fmt: skip
            rows.append(row)
            print(row)
    digs = {r["digest"] for r in rows}
    best = min(rows, key=lambda r: r["kernel_median_s"])
    save_json("jax_tuning.json", {"machine": machine_info(), "steps": STEPS, "rows": rows,
                                  "distinct_digests": sorted(digs), "best": best})  # fmt: skip
    print("distinct digests:", len(digs), "best:", best)


if __name__ == "__main__":
    main()
