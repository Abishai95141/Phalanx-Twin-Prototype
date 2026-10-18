"""Joint distances of the base configuration on the joint design's 4 flights (comparison row for the bank
Pareto table): base rows of the n = 20 run restricted to `flight_order()[:4]`.

Usage: python -I base4.py <base_jsonl> <out_json>
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aggregate import _flat, _median
from common import flight_order
from report import SETS, dist


def main(base_jsonl: str, out: str) -> None:
    four = set(flight_order()[:4])
    rows = [json.loads(line) for line in open(base_jsonl)]
    rows = [r for r in rows if r["flight"] in four and "error" not in r]
    rec = [_flat(r["rec"]) for r in rows]
    real = [_flat(r["real"]) for r in rows]
    keys = {k for f in rec for k in f}
    m_rec = {k: _median([f.get(k, float("nan")) for f in rec]) for k in keys}
    m_real = {k: _median([f.get(k, float("nan")) for f in real]) for k in keys}
    res = {"n": len(rows)}
    for sname, groups in SETS.items():
        gd, allk = [], []
        for ks in groups.values():
            d = [dist(k, m_rec.get(k, float("nan")), m_real.get(k, float("nan"))) for k in ks]
            d = [x for x in d if not math.isnan(x)]
            allk += d
            gd.append(math.sqrt(sum(x * x for x in d) / len(d)) if d else float("nan"))
        res[sname] = {
            "joint": math.sqrt(sum(x * x for x in allk) / len(allk)),
            "groups": dict(zip(groups, gd, strict=True)),
        }
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main(*sys.argv[1:])
