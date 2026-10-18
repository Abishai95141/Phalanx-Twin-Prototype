"""Fleet side: training worlds — the same 8 tails, built by the same builder as the live fleet, with extra session
seeds and a 3-year horizon (DEVELOPMENT.md §2.3 "Generated data", Phase 1-C).

Each world is ``TailRunner(tail, days, root=<root of seed k>)``: the preview builder's own usage-mode world
(``build_preview._fleet_world``), its data-quality defect injector and the station routine (``ScheduledPolicy``)
deciding at every 08:00 IST epoch. Only the session root seed differs from the live fleet, so every world is a
different realisation of the same simulated squadron. Nothing in the data layer is edited.

Layout (consumer and restricted trees are siblings, never nested)::

    <out>/seed=<k>/fleet/<topic>/…                      # consumer tree, contract 0.2.0
    <out>/seed=<k>/_restricted_labels/fleet/labels.truth/…   # truth: evaluation only
    <out>/seed=<k>/_runs/<tail>.json                    # per-world run report
    <out>/train_manifest.json                           # seeds, roots, days, timings, row counts

Each world runs in its own process (sessions are not picklable). Optional ``--stress <yaml>`` passes a copy of
the fault parameters with higher rates (a labelled stress scenario, written under ``<out>-stress``); without it
the data layer's own parameters are used.

Usage::

    proto/runner/run.sh proto/runner/train_worlds.py [--seeds 1-4] [--tails TJ101,…] [--days 735]
                                                     [--horizon 730] [--workers 2] [--out proto/runs/train]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "runs" / "train"
#: training-world roots: a fixed base distinct from the live fleet's ``FLEET_ROOT`` (0x09F1EE7), plus the seed
TRAIN_ROOT_BASE = 0x7A1_0000
SOURCE_LABEL = "Simulated fleet history"


def root_for(seed: int) -> int:
    return TRAIN_ROOT_BASE + int(seed)


def _apply_stress(path: str | None) -> dict[str, Any] | None:
    """Patch, in this worker process only, the loader the builder calls for the fault parameters, so the world
    is built with a copy of them at higher rates. Returns the overrides applied (for the run report)."""
    if not path:
        return None
    import yaml  # the data layer's own dependency

    import phalanx.faults as pf

    spec = yaml.safe_load(Path(path).read_text())
    base = pf.load_fault_params
    overrides = dict(spec.get("multiply", {}))

    def load_stressed(*a, **k):
        p = base(*a, **k)
        return _scaled_params(p, overrides)

    pf.load_fault_params = load_stressed  # module attribute only; the source file is untouched
    return {"file": str(path), "multiply": overrides}


def _scaled_params(p: Any, overrides: dict[str, float]) -> Any:
    import dataclasses

    if dataclasses.is_dataclass(p):
        vals = getattr(p, "values", None)
        if isinstance(vals, dict):
            new = dict(vals)
            for k, m in overrides.items():
                if k not in new:
                    raise KeyError(f"stress: no fault parameter {k!r}")
                new[k] = _mul(new[k], m)
            return dataclasses.replace(p, values=new)
    raise TypeError(f"stress: unsupported fault-parameter object {type(p).__name__}")


def _mul(v: Any, m: float) -> Any:
    if isinstance(v, int | float):
        return v * m
    if hasattr(v, "value"):
        import dataclasses

        return dataclasses.replace(v, value=v.value * m)
    raise TypeError(f"stress: cannot scale {v!r}")


def build_one(seed: int, tail: str, days: int, horizon: int, out: str, stress: str | None) -> dict[str, Any]:
    """One training world: build, run ``horizon`` days with the station routine, publish everything once."""
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    w0 = time.perf_counter()
    applied = _apply_stress(stress)
    from datalayer import DAY, bp, fmt_ist  # imported in the worker (phalanx stays per process)
    from ipcstore import store_class  # Arrow IPC by default: Parquet is unreliable on big-endian IBM Z
    from world import TailRunner

    seed_dir = Path(out) / f"seed={seed}"
    store = store_class()(
        seed_dir / "fleet", bp._contract(), restricted_root=seed_dir / "_restricted_labels" / "fleet"
    )
    tr = TailRunner(tail, days, root=root_for(seed))
    w_build = time.perf_counter() - w0
    t_end = tr.epoch_utc + horizon * DAY
    w = time.perf_counter()
    tr.advance(t_end)
    w_run = time.perf_counter() - w
    w = time.perf_counter()
    pub = tr.publish(store, None, t_end)
    w_pub = time.perf_counter() - w
    doc = {
        "source_label": SOURCE_LABEL + (" (stress scenario)" if applied else ""),
        "world_seed": seed,
        "tail_no": tail,
        "root": hex(root_for(seed)),
        "scenario_days": days,
        "horizon_days": horizon,
        "t_start": fmt_ist(tr.epoch_utc),
        "t_end": fmt_ist(t_end),
        "routine_orders": tr.routine_orders,
        "rows": {k: v for k, v in pub.items() if k != "files"},
        "files": len(pub["files"]),
        "stress": applied,
        "build_s": round(w_build, 2),
        "run_s": round(w_run, 2),
        "publish_s": round(w_pub, 2),
        "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2**20 if sys.platform == "darwin" else 2**10), 1),
    }
    (seed_dir / "_runs").mkdir(parents=True, exist_ok=True)
    (seed_dir / "_runs" / f"{tail}.json").write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def _parse_seeds(s: str) -> list[int]:
    out: list[int] = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += range(int(a), int(b) + 1)
        elif part:
            out.append(int(part))
    return out


def main(argv: list[str] | None = None) -> int:
    from datalayer import TAILS

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="1-4")
    ap.add_argument("--tails", default=",".join(TAILS))
    ap.add_argument("--days", type=int, default=735, help="scenario length of each world")
    ap.add_argument("--horizon", type=int, default=730, help="days simulated and published")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--stress", default=None, help="YAML with fault-parameter multipliers (stress scenario)")
    a = ap.parse_args(argv)
    seeds, tails = _parse_seeds(a.seeds), [t for t in a.tails.split(",") if t]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(s, t) for s in seeds for t in tails]
    w0 = time.perf_counter()
    docs: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(build_one, s, t, a.days, a.horizon, str(out), a.stress): (s, t) for s, t in jobs}
        for f in as_completed(futs):
            s, t = futs[f]
            try:
                d = f.result()
                docs.append(d)
                print(f"seed={s} {t}: run {d['run_s']} s, rss {d['max_rss_mb']} MB, rows {d['rows']}", flush=True)
            except Exception as e:  # report and continue; the manifest lists failures
                errors.append({"world_seed": s, "tail_no": t, "error": repr(e)})
                print(f"seed={s} {t}: FAILED {e!r}", file=sys.stderr, flush=True)
    docs.sort(key=lambda d: (d["world_seed"], d["tail_no"]))
    manifest = {
        "source_label": SOURCE_LABEL + (" (stress scenario)" if a.stress else ""),
        "builder": "build_preview._fleet_world via proto/runner/world.py TailRunner",
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16],
        "seeds": seeds,
        "roots": {s: hex(root_for(s)) for s in seeds},
        "tails": tails,
        "scenario_days": a.days,
        "horizon_days": a.horizon,
        "workers": a.workers,
        "stress": a.stress,
        "worlds_ok": len(docs),
        "worlds_failed": errors,
        "wall_s": round(time.perf_counter() - w0, 1),
        "worlds": docs,
    }
    (out / "train_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"done: {len(docs)} worlds ok, {len(errors)} failed, {manifest['wall_s']} s")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
