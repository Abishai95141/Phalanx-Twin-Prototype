"""M1: single sortie-hour (864,000 truth steps, 1 unit) wall time per backend; x real time.

Each configuration in its own process: one warm-up block (compile), then 5 timed repetitions of the full hour
(NumPy reference: the 1 h run of s02_ref_hour.py plus 3 x 60 s for variance). One thread everywhere
(NUMBA_NUM_THREADS=1; XLA intra-op threading off). Kernel time excludes the NumPy feeding layer (inputs +
keyed RNG blocks), which is reported separately and is identical for every backend.

Usage: python -I code/s02_m1_sortie_hour.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import RESULTS, machine_info, run_worker, save_json, stats

HOUR = 864_000
ENV1 = {"NUMBA_NUM_THREADS": "1", "XLA_FLAGS": "--xla_cpu_multi_thread_eigen=false"}


def summarize(r, steps):
    k = [x["t_kernel"] for x in r["reps"]]
    w = [x["t_wall"] for x in r["reps"]]
    f = [x["t_feed"] for x in r["reps"]]
    c = [x["t_cpu"] for x in r["reps"]]
    sim_s = steps / 240.0
    return {
        "kernel_s": stats(k),
        "wall_incl_feed_s": stats(w),
        "feed_s": stats(f),
        "cpu_over_wall": stats([ci / wi for ci, wi in zip(c, w, strict=True)]),
        "x_realtime_kernel_median": sim_s / stats(k)["median"],
        "x_realtime_wall_median": sim_s / stats(w)["median"],
        "us_per_step_kernel_median": stats(k)["median"] / steps * 1e6,
        "t_first_call": r["t_first_call"],
        "peak_rss_mb": r["peak_rss_mb"],
        "digest": r["all_digest"],
        "state_digest": r["state_digest"],
    }


def main():
    res = {"machine": machine_info(), "steps": HOUR, "env": ENV1, "rows": {}}
    cfgs = {
        "numba_single": (["--backend", "numba", "--mode", "single"], HOUR, 5),
        "jax_single_unroll4": (["--backend", "jax", "--mode", "single", "--unroll", "4"], HOUR, 5),
        "jax_single_unroll1": (["--backend", "jax", "--mode", "single", "--unroll", "1"], HOUR, 3),
        "numpy_ref_60s": (["--backend", "numpy", "--mode", "auto"], 14_400, 3),
    }
    for name, (args, steps, reps) in cfgs.items():
        r = run_worker(["run", *args, "--steps", str(steps), "--reps", str(reps)], ENV1, timeout=7200)
        res["rows"][name] = summarize(r, steps)
        res["rows"][name]["reps"] = reps
        res["rows"][name]["steps"] = steps
        print(name, json.dumps({k: v for k, v in res["rows"][name].items() if k.startswith(("x_", "us_"))}),
              file=sys.stderr)  # fmt: skip
    ref = RESULTS / "ref_hour.json"
    if ref.exists():
        z = json.load(open(ref))
        res["rows"]["numpy_ref_hour_once"] = {"wall_s": z["t_wall"], "kernel_s": z["t_kernel"], "feed_s": z["t_feed"],
                                              "x_realtime_kernel": 3600.0 / z["t_kernel"], "reps": 1,
                                              "peak_rss_mb": z["peak_rss_mb"]}  # fmt: skip
    save_json("m1_sortie_hour.json", res)


if __name__ == "__main__":
    main()
