"""W2.4a-2 stage 1: which bit of the EAI (engine anti-ice) and BLV (bleed valves) words belongs to which
engine.

Method (stated before running): the engines are started one at a time on the ground. A single bit of the word
that switches on while exactly one engine is starting (its N2 rises by more than 15 % over the 20 s before
the switch to 10 s after it, every other engine's N2 varies by less than 2 %) belongs to that engine. Counts
per (bit, engine) are reported; the mapping is the majority. CAL flights only (``common.guarded``). Words
whose bits never switch with a start (BLV opens in the climb, all valves within seconds) are not mapped here.

Usage::

    $PY -I analysis/proxy_quicklook/code/st_bits.py <mat_dir> <first> <n_flights> <out.json>
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script directory

from common import flight_order
from st_points import flight_arrays

PRE = 80  # 20 s at 4 Hz
POST = 40  # 10 s


def events(a: dict, word: str) -> list[tuple[int, int, int]]:
    """(bit, starting engine, sample) per single-bit switch-on that coincides with exactly one engine
    start."""
    x = a[word]
    out = []
    for i in np.flatnonzero(np.diff(x) != 0) + 1:
        prev, new = int(x[i - 1]), int(x[i])
        on = new & ~prev
        if new & prev != prev or bin(on).count("1") != 1 or i < PRE or i + POST >= x.size:
            continue
        n2 = a["N2"][:, i - PRE : i + POST]
        rng = n2.max(1) - n2.min(1)
        starting = np.flatnonzero(rng > 15.0)
        if starting.size == 1 and np.all(np.delete(rng, starting) < 2.0):
            out.append((int(on).bit_length() - 1, int(starting[0]) + 1, int(i)))
    return out


def main(mat_dir: str, first: int, n_flights: int, out_json: str) -> None:
    res: dict[str, list] = {"BLV": [], "EAI": []}
    flights = flight_order()[first : first + n_flights]
    for fn in flights:
        a = flight_arrays(mat_dir, fn)
        for w in res:
            res[w] += [(fn, *e) for e in events(a, w)]
    summary = {}
    for w, ev in res.items():
        cnt: dict[str, dict[str, int]] = {}
        for _fn, bit, eng, _i in ev:
            cnt.setdefault(str(bit), {}).setdefault(str(eng), 0)
            cnt[str(bit)][str(eng)] += 1
        summary[w] = cnt
    out = {
        "flights": flights,
        "n_events": {w: len(e) for w, e in res.items()},
        "counts": summary,
        "events": res,
    }
    with open(out_json, "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"n_events": out["n_events"], "counts": summary}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
