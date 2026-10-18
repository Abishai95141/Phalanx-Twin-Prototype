"""Aggregate MF1 sweep rows: per configuration, the median over flights of every statistic at each level
(recorded / sensor / truth), and the paired real medians (targets) from the rows that carry them.

Usage: python -I aggregate.py <out_json> <jsonl> [<jsonl> ...]

Medians over flights with a flight-bootstrap 95 % CI for the real targets (2,000 resamples; keyed stream
`validation.bootstrap` under the study's identity, no global RNG).
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from common import ROOT, SCENARIO

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.validation.battery.evaluate import BOOTSTRAP_STREAM

LEVELS = ("rec", "sen", "tru")
N_BOOT = 2000


def _flat(d: dict, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in d.items():
        if k == "levels":
            for f, x in v.items():
                out[f"level.{f}"] = x
        elif isinstance(v, list):
            for i, x in enumerate(v):
                out[f"{prefix}{k}[{i}]"] = x
        elif isinstance(v, (int, float)):
            out[f"{prefix}{k}"] = float(v)
    return out


def _median(vals: list[float]) -> float:
    a = np.asarray([v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    return float(np.median(a)) if a.size else float("nan")


def boot_ci(vals: list[float], gen) -> tuple[float, float]:
    a = np.asarray([v for v in vals if not math.isnan(v)], float)
    if a.size < 3:
        return float("nan"), float("nan")
    idx = gen.integers(0, a.size, size=(N_BOOT, a.size))
    med = np.median(a[idx], axis=1)
    return float(np.quantile(med, 0.025)), float(np.quantile(med, 0.975))


def aggregate(paths: list[str]) -> dict:
    rows = []
    for p in paths:
        with open(p) as fh:
            rows += [json.loads(line) for line in fh]
    errors = [r for r in rows if "error" in r]
    rows = [r for r in rows if "error" not in r]
    by_cfg: dict[str, list[dict]] = defaultdict(list)
    real: dict[str, dict] = {}
    for r in rows:
        by_cfg[r["config"]].append(r)
    # the targets: real statistics of the base rows (or of the first configuration with real statistics);
    # the GOV classes are paired with each configuration's own run and are reported per configuration
    ref = "base" if "base" in by_cfg else next((c for c, rs in by_cfg.items() if "real" in rs[0]), None)
    for r in by_cfg.get(ref, []):
        if "real" in r:
            real[r["flight"]] = _flat(r["real"])
    svc = RngService(ROOT, StreamRegistry([BOOTSTRAP_STREAM]))
    path = KeyPath.of(
        scenario=SCENARIO, subsystem=BOOTSTRAP_STREAM.subsystem, component=BOOTSTRAP_STREAM.component
    )
    gen = svc.generator(path, len(real))
    out: dict = {"n_errors": len(errors), "errors": [(e["config"], e["flight"], e["error"]) for e in errors]}
    keys = sorted({k for f in real.values() for k in f})
    out["real"] = {
        "n": len(real),
        "flights": sorted(real),
        "median": {k: _median([real[f].get(k, float("nan")) for f in real]) for k in keys},
        "ci": {k: boot_ci([real[f].get(k, float("nan")) for f in real], gen) for k in keys},
    }
    out["configs"] = {}
    for c, rs in by_cfg.items():
        flights = sorted(r["flight"] for r in rs)
        entry = {"n": len(rs), "flights": flights, "spec": rs[0]["spec"]}
        for lvl in LEVELS:
            fl = [_flat(r[lvl]) for r in rs]
            ks = sorted({k for f in fl for k in f})
            entry[lvl] = {k: _median([f.get(k, float("nan")) for f in fl]) for k in ks}
        own = [_flat(r["real"]) for r in rs if "real" in r]
        if own:
            ks = sorted({k for f in own for k in f})
            entry["real_same_flights"] = {k: _median([f.get(k, float("nan")) for f in own]) for k in ks}
        else:
            entry["real_same_flights"] = {
                k: _median([real[f].get(k, float("nan")) for f in flights if f in real]) for k in keys
            }
        lim = defaultdict(list)
        for r in rs:
            for code, share in r["limiter_share"].items():
                lim[code].append(share)
        entry["limiter_share_median"] = {
            k: float(np.median(v + [0.0] * (len(rs) - len(v)))) for k, v in lim.items()
        }
        entry["at_n1_err_med"] = _median([r.get("at_n1_err_med", float("nan")) for r in rs])
        out["configs"][c] = entry
    return out


if __name__ == "__main__":
    res = aggregate(sys.argv[2:])
    with open(sys.argv[1], "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print("configs", len(res["configs"]), "real flights", res["real"]["n"], "errors", res["n_errors"])
