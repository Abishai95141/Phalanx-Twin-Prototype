"""MF1 sweep driver: run every configuration of a named sweep on the first n flights of the MF1-D order.

Usage (from the worktree root; MAT dir read-only, outputs to a git-ignored run directory)::

    PY=<main repo>/.venv-build/bin/python
    $PY -I analysis/proxy_quicklook/code/sweep.py <mat_dir> <sweep> <n_flights> <out_dir> [workers]

Writes ``<out_dir>/<sweep>.jsonl`` (one row per configuration x flight, appended; rows already present are
skipped, so an interrupted sweep resumes). Each row holds the MF1 statistics at truth, sensor and recorded
level, the paired real statistics (only for the configuration named ``base``: the targets do not depend on
the configuration) and the run digest.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

from common import flight_order
from configs import SWEEPS


def _worker(args):
    from runner import run_one

    try:
        return run_one(args)
    except Exception as exc:  # a failed run is a finding: record it, do not stop the sweep
        spec, fname, k, _m, _r = args
        return {"config": spec.get("name"), "flight": fname, "k": k, "error": repr(exc)}


def main(mat_dir: str, sweep: str, n_flights: int, out_dir: str, workers: int = 10) -> None:
    specs = SWEEPS[sweep]()
    flights = flight_order()[:n_flights]
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{sweep}.jsonl")
    done = set()
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                r = json.loads(line)
                if "error" not in r:
                    done.add((r["config"], r["flight"]))
    jobs = [
        (spec, f, k, mat_dir, True)  # real statistics per row: the GOV classes pair with each run
        for spec in specs
        for k, f in enumerate(flights)
        if (spec.get("name"), f) not in done
    ]
    print(f"{sweep}: {len(specs)} configurations x {len(flights)} flights; {len(jobs)} to run", flush=True)
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, maxtasksperchild=8) as pool, open(path, "a") as out:
        for i, row in enumerate(pool.imap_unordered(_worker, jobs), 1):
            out.write(json.dumps(row) + "\n")
            out.flush()
            tag = "ERROR " + row["error"] if "error" in row else f"{row.get('seconds')} s"
            print(
                f"[{i}/{len(jobs)}] {row['config']} {row['flight']} {tag} ({time.time() - t0:.0f} s)",
                flush=True,
            )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], *(int(x) for x in sys.argv[5:6]))
