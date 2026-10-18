"""Deterministic stratified sample of complete flights for the texture analysis.

Eligible = not a "_1" twin (those are byte-identical duplicates except DATE_DAY, see
recorder notes), record >= 30 min, exactly 2 WOW transitions (one lift-off, one touchdown),
>= 10 min of PH==5 (cruise), >= 60 s of PH in {1,2} (ground before departure available).
Strata = calendar block (Mar-May / Jul / Aug / Sep 2001) x record-duration tercile.
Allocation: proportional to stratum size, minimum 2 per non-empty stratum, total N.
Seed fixed (default 687).

Usage: python -I sample_flights.py <results_dir> [N=40] [seed=687]
Writes sample_flights.csv and eligible_flights.csv
"""
import os
import sys
import csv

import numpy as np


def main(res, N=40, seed=687):
    F = list(csv.DictReader(open(os.path.join(res, "inventory_flights.csv"))))
    elig = []
    for r in F:
        dur = float(r["duration_s"])
        ok = (r["dup_suffix"] != "True" and dur >= 1800 and int(r["n_WOW_transitions"]) == 2 and float(r["t_PH5_Cruise_s"]) >= 600
              and float(r["t_PH1_Preflight_s"]) + float(r["t_PH2_Taxi_s"]) >= 60)
        if ok:
            elig.append(r)
    durs = np.array([float(r["duration_s"]) for r in elig])
    q = np.percentile(durs, [100 / 3, 200 / 3])
    for r in elig:
        m = int(r["month"])
        blk = "MarMay" if m <= 5 else {7: "Jul", 8: "Aug", 9: "Sep"}.get(m, "other")
        d = float(r["duration_s"])
        terc = 0 if d <= q[0] else (1 if d <= q[1] else 2)
        r["stratum"] = f"{blk}_T{terc}"
    strata = sorted(set(r["stratum"] for r in elig))
    sizes = {s: sum(1 for r in elig if r["stratum"] == s) for s in strata}
    tot = sum(sizes.values())
    alloc = {s: max(2, int(round(N * sizes[s] / tot))) for s in strata}
    # adjust to exactly N (deterministic: trim/add on largest strata)
    while sum(alloc.values()) > N:
        s = max((k for k in alloc if alloc[k] > 2), key=lambda k: (alloc[k] - N * sizes[k] / tot, k))
        alloc[s] -= 1
    while sum(alloc.values()) < N:
        s = max(alloc, key=lambda k: (N * sizes[k] / tot - alloc[k], k))
        alloc[s] += 1
    rng = np.random.default_rng(seed)
    chosen = []
    for s in strata:
        cand = sorted([r for r in elig if r["stratum"] == s], key=lambda r: r["file"])
        idx = rng.choice(len(cand), size=min(alloc[s], len(cand)), replace=False)
        chosen.extend(cand[i] for i in sorted(idx))
    chosen.sort(key=lambda r: r["file"])
    keys = ["file", "stratum", "datestr", "duration_s", "t_WOW1_s", "t_PH5_Cruise_s", "max_ALT"]
    with open(os.path.join(res, "sample_flights.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(chosen)
    with open(os.path.join(res, "eligible_flights.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(elig)
    print(f"eligible {len(elig)} of {len(F)}; duration terciles {q / 60} min")
    print("strata sizes", sizes)
    print("allocation", alloc, "total", len(chosen))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40, int(sys.argv[3]) if len(sys.argv) > 3 else 687)
