"""What does the reference belief posterior change at the snapshot? (diagnostic for the README)

For members 0..k-1, fork the epoch snapshot in ensemble and in belief mode (same member root) and report which
modules' state differs (names only; no hidden values are read or written out).

Usage: ./run.sh belief_check.py TJ107 TJ108 TJ105   -> video/data/forks/belief_check.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from phx_forks import BranchSpec, TailWorld, belief_posterior
from run_forks import FORK_DAYS, OUT, T0


def differs(a, b) -> bool:
    for f in a:
        x, y = np.asarray(a[f]), np.asarray(b[f])
        if x.shape != y.shape or x.dtype != y.dtype or x.tobytes() != y.tobytes():
            return True
    return False


def main(tails: list[str], k: int = 3) -> None:
    out = {}
    for tail in tails:
        tw = TailWorld(tail, FORK_DAYS)
        s, _ = tw.run_reference(T0)
        snap = tw.fs.snapshot(s)
        rows = []
        for m in range(k):
            e = tw.fs.fork(snap, BranchSpec("e", mode="ensemble", member=m))
            b = tw.fs.fork(snap, BranchSpec("b", mode="belief", member=m, belief=belief_posterior()))
            mods = sorted(x for x in e.world.states if differs(e.world.states[x], b.world.states[x]))
            rows.append({"member": m, "modules_whose_state_differs": mods})
        out[tail] = rows
    doc = {
        "what": "modules whose state differs between the belief fork and the ensemble fork of the same member at "
        "the epoch (the posterior's footprint); module names only",
        "result": out,
    }
    Path(OUT / "belief_check.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:] or ["TJ107", "TJ108", "TJ105"])
