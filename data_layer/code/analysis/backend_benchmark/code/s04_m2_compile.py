"""M2: compile / JIT overhead and cache options; D7 (results from cache == freshly compiled).

Per backend and kernel (single-unit block; 10-unit batch block), 3 fresh processes per condition:
  cold      empty cache directory (Numba: new NUMBA_CACHE_DIR; JAX: no persistent cache)
  populate  JAX only: empty persistent cache directory that the process fills
  hit       populated cache (Numba cache=True files; JAX persistent compilation cache)
Within each process: import time, first call (compile or cache load + one 2,400-step block), second call (same
shapes: execution only). Compile ~= first - second. Digest of the first block (D7).

Usage: python -I code/s04_m2_compile.py
"""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import CACHE, machine_info, run_worker, save_json, stats

REPS = 3
XLA_1T = "--xla_cpu_multi_thread_eigen=false"


def _w(backend, mode, units, env):
    return run_worker(["run", "--backend", backend, "--mode", mode, "--units", str(units), "--kind", "combat",
                       "--steps", "2400", "--reps", "1", "--unroll", "4"], env)  # fmt: skip


def main():
    root = CACHE / "m2"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    res = {"machine": machine_info(), "reps": REPS, "rows": []}
    configs = [("numba", "single", 1), ("numba", "prange", 10), ("jax", "single", 1), ("jax", "vmap", 10)]
    for be, mode, units in configs:
        rows = {"cold": [], "hit": []}
        if be == "jax":
            rows["populate"] = []
        for i in range(REPS):
            if be == "numba":
                d = root / f"numba_{mode}_{i}"
                env = {"NUMBA_CACHE_DIR": str(d), "NUMBA_NUM_THREADS": "4"}
                rows["cold"].append(_w(be, mode, units, env))
                rows["hit"].append(_w(be, mode, units, env))
            else:
                env = {"XLA_FLAGS": XLA_1T}
                rows["cold"].append(_w(be, mode, units, env))
                d = root / f"jax_{mode}_{i}"
                env_c = {"XLA_FLAGS": XLA_1T, "BENCH_JAX_CACHE": str(d)}
                rows["populate"].append(_w(be, mode, units, env_c))
                rows["hit"].append(_w(be, mode, units, env_c))
        summary = {"backend": be, "mode": mode, "units": units}
        digests = set()
        for cond, rs in rows.items():
            summary[cond] = {
                "t_import": stats([r["t_import"] for r in rs]),
                "t_first_call": stats([r["t_first_call"] for r in rs]),
                "t_second_call": stats([r["t_second_call"] for r in rs]),
                "compile_est": stats([r["t_first_call"] - r["t_second_call"] for r in rs]),
                "t_process": stats([r["t_process"] for r in rs]),
                "peak_rss_mb": stats([r["peak_rss_mb"] for r in rs]),
            }
            digests |= {r["all_digest"] for r in rs}
        summary["D7_distinct_digests_across_conditions"] = len(digests)
        summary["digests"] = sorted(digests)
        if be == "numba":
            summary["cache_dir_bytes"] = sum(f.stat().st_size for f in (root / f"numba_{mode}_0").rglob("*")
                                             if f.is_file())  # fmt: skip
        else:
            summary["cache_dir_bytes"] = sum(f.stat().st_size for f in (root / f"jax_{mode}_0").rglob("*")
                                             if f.is_file())  # fmt: skip
        res["rows"].append(summary)
        print(be, mode, {c: round(summary[c]["compile_est"]["median"], 3) for c in rows},
              "digests", len(digests), file=sys.stderr)  # fmt: skip
    save_json("m2_compile.json", res)


if __name__ == "__main__":
    main()
