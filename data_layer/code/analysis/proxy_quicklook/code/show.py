"""Print the key MF1 statistics of rows in a sweep JSONL (development viewer; no computation).

Usage: python -I show.py <jsonl> [config ...]
"""

from __future__ import annotations

import json
import sys

KEYS = (
    "B1.N1-N2",
    "B1.N1-FF",
    "B1.N2-FF",
    "B1.N1-EGT",
    "B1.N1x",
    "B1.N2x",
    "B1.EGTx",
    "FLT.N1-N2",
    "FLT.N1-FF",
    "FLT.N2-FF",
    "FLT.N1-EGT",
    "B2.FF>N2",
    "B2.FF>N1",
    "B2.N2>N1",
    "B2.FF>EGT",
    "SALL.N2>N1.phase_bands_deg",
    "SALL.N2>N1.gain_bands",
    "SALL.N2>N1.coh_bands",
    "SALL.N2>N1.tau_eq",
    "SALL.N1>EGT.phase_bands_deg",
    "SALL.N1>EGT.tau_eq",
    "SALL.N2>FF.tau_eq",
    "SALL.FF>N1.tau_eq",
    "taxi_share_of_air",
)


def fmt(v):
    if isinstance(v, list):
        return "[" + ", ".join(f"{x:.2f}" for x in v) + "]"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def main(path: str, *configs: str) -> None:
    rows = [json.loads(line) for line in open(path)]
    for r in rows:
        if configs and r["config"] not in configs:
            continue
        if "error" in r:
            print(r["config"], r["flight"], "ERROR", r["error"])
            continue
        print(f"== {r['config']} {r['flight']} lim {r['limiter_share']} at_err {r.get('at_n1_err_med')}")
        levels = [x for x in ("real", "rec", "sen", "tru") if x in r]
        print(f"{'stat':34s}" + "".join(f"{x:>26s}" for x in levels))
        for k in KEYS:
            print(f"{k:34s}" + "".join(f"{fmt(r[x].get(k, '-')):>26s}" for x in levels))
        print(
            f"{'levels':34s}"
            + "".join(f"{fmt([r[x]['levels'][f] for f in ('N1', 'N2', 'EGT', 'FF')]):>26s}" for x in levels)
        )


if __name__ == "__main__":
    main(*sys.argv[1:])
