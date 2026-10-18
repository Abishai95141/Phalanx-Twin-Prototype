"""Regression check (A5): the committed code reproduces the digests recorded in results/m2_compile.json.

Runs each kernel family in a fresh `python -I` process (combat scenario, 2,400 steps) and compares its digest with
the recorded one: Numba single and prange; JAX single and vmap (unroll 4); the NumPy reference against the
Numba batch digest (A1). Exit code 1 on any mismatch.

Usage: python -I code/s11_regress.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import RESULTS, run_worker

ENV = {"NUMBA_NUM_THREADS": "1", "XLA_FLAGS": "--xla_cpu_multi_thread_eigen=false"}
CASES = [("numba", "single", 1), ("numba", "prange", 10), ("jax", "single", 1), ("jax", "vmap", 10), ("numpy", "auto", 10)]


def main() -> int:
    with open(RESULTS / "m2_compile.json") as fh:
        rec = {(r["backend"], r["mode"]): r["digests"] for r in json.load(fh)["rows"]}
    ok = True
    for be, mode, units in CASES:
        args = ["run", "--backend", be, "--mode", mode, "--units", str(units), "--kind", "combat", "--steps", "2400"]
        r = run_worker([*args, "--reps", "1", "--unroll", "4"], ENV)
        ref = rec.get((be, mode)) or rec[("numba", "prange")]  # NumPy must equal the Numba batch digest
        hit = r["all_digest"] in ref
        ok &= hit
        print(f"{be:6s} {mode:7s} {r['all_digest']} {'MATCH' if hit else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
