"""NumPy reference over the full sortie-hour (1 unit), kept for the A1 comparison at the 1 h scale.

Saves full-rate outputs to _cache/ref_hour.npz (41 MB, not committed) and timing/digests to
results/ref_hour.json. Expensive (~35 min single core); run once.

Usage: python -I code/s02_ref_hour.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as Hn
import numpy as np
from common import CACHE, machine_info, peak_rss_mb, save_json

STEPS = 864_000


def main():
    sc = Hn.Scenario([0], "sortie", STEPS)
    r = Hn.run(Hn.make_backend("numpy", sc), sc, 0, STEPS, 2400, keep=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / "ref_hour.npz", out=r["out"][0], sel=r["sel"][0], X=r["X"], S=r["S"])
    save_json(
        "ref_hour.json",
        {"machine": machine_info(), "steps": STEPS, "t_wall": r["t_wall"], "t_kernel": r["t_kernel"],
         "t_feed": r["t_feed"], "t_cpu": r["t_cpu"], "digest": r["digests"][0],
         "state_digest": Hn.state_digest(r["X"], r["S"]), "peak_rss_mb": peak_rss_mb()},
    )  # fmt: skip
    print(r["t_wall"], r["digests"][0])


if __name__ == "__main__":
    main()
