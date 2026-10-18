"""M3b (deviation D1 in DEVIATIONS.md): paired, alternating re-measurement of the 1- and 4-core batch points.

Reason: during M3 the shared machine's load average was 7-8.5; Numba at 4 threads reached only 2.07 CPU/wall,
so the 4-thread points were contention-limited. Here the two backends alternate (A B A B), 2 rounds x 3 reps,
so both see the same background load. Same workload as M3 (1,000 units x 60 s, 'combat').

Usage: python -I code/s07b_m3_paired.py
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import machine_info, run_worker, save_json
from s07_m3_batch import STEPS, XLA_OFF, U, summarize


def load_avg() -> str:
    return subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True).stdout.strip()


def main():
    base = [
        "run",
        "--units",
        str(U),
        "--kind",
        "combat",
        "--steps",
        str(STEPS),
        "--keep-digests",
        "0",
        "--reps",
        "3",
    ]
    cfgs = {
        "numba_prange_t1": (["--backend", "numba", "--mode", "prange"], {"NUMBA_NUM_THREADS": "1"}),
        "jax_vmap_1dev_unroll4": (
            ["--backend", "jax", "--mode", "vmap", "--unroll", "4"],
            {"XLA_FLAGS": XLA_OFF},
        ),
        "numba_prange_t4": (["--backend", "numba", "--mode", "prange"], {"NUMBA_NUM_THREADS": "4"}),
        "jax_sharded_4dev_unroll4": (
            ["--backend", "jax", "--mode", "sharded", "--ndev", "4", "--unroll", "4"],
            {"XLA_FLAGS": XLA_OFF},
        ),
    }
    res = {"machine": machine_info(), "units": U, "steps": STEPS, "rounds": []}
    for rnd in range(2):
        row = {}
        for name, (args, env) in cfgs.items():
            la = load_avg()
            row[name] = {**summarize(run_worker([*base, *args], env, timeout=3600)), "loadavg_before": la}
            print(rnd, name, round(row[name]["kernel_s"]["median"], 2), round(row[name]["cpu_over_wall"]["median"], 2),
                  la, file=sys.stderr)  # fmt: skip
        res["rounds"].append(row)
    save_json("m3b_paired.json", res)


if __name__ == "__main__":
    main()
