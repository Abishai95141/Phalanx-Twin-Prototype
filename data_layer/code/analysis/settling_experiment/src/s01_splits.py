"""Step 1 -- make and save the splits (pre-registration section 1). Runs before anything else.

* 687: eligible flights from analysis/dashlink_texture/results/eligible_flights.csv. The eligibility rule
  is re-applied to inventory_flights.csv and must reproduce that list exactly (sanity check).
* 687-CAL = random 40 % (numpy default_rng(20261014).permutation over the sorted file list),
  687-TEST = the remaining 60 %.
* 652: the same eligibility rule applied to every non-"_1" file of archive 8 (read-only directory;
  files are only parsed with scipy.io.loadmat via dlio.load_flight).

Usage: python -I s01_splits.py <mat687_dir> <mat652_dir> <texture_results_dir> <results_dir> [n_workers]
Writes results/splits.csv, results/inventory_652.csv
"""
import csv
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from dlio import load_flight, parse_fname, FNAME_RE  # noqa: E402


def eligible(dur, n_wow, t_ph5, t_ph12, dup):
    """Rule of analysis/dashlink_texture/sample_flights.py (copied verbatim in meaning)."""
    return (not dup) and dur >= 1800 and n_wow == 2 and t_ph5 >= 600 and t_ph12 >= 60


def meta_652(path):
    m = parse_fname(path)
    F = load_flight(path)
    nfr = F["FRMC"].x.size
    ph = F["PH"].x
    w = F["WOW"].x
    return {"file": m["file"], "datestr": m["datestr"], "month": m["month"], "year": m["year"],
            "dup_suffix": m["dup_suffix"], "duration_s": nfr * 4,
            "n_WOW_transitions": int(np.sum(np.abs(np.diff(w)) > 0)),
            "t_PH5_Cruise_s": float(np.sum(ph == 5) / F["PH"].rate),
            "t_PH12_s": float(np.sum((ph == 1) | (ph == 2)) / F["PH"].rate)}


def season(month):
    return "MarMay" if month <= 5 else ("Jun" if month == 6 else ("JulSep" if month <= 9 else "other"))


def main(mat687, mat652, tex_res, res, nw=8):
    os.makedirs(res, exist_ok=True)
    # ---- 687: re-derive eligibility and compare with the stored list
    inv = list(csv.DictReader(open(os.path.join(tex_res, "inventory_flights.csv"))))
    re_elig = sorted(r["file"] for r in inv if eligible(
        float(r["duration_s"]), int(r["n_WOW_transitions"]), float(r["t_PH5_Cruise_s"]),
        float(r["t_PH1_Preflight_s"]) + float(r["t_PH2_Taxi_s"]), r["dup_suffix"] == "True"))
    stored = list(csv.DictReader(open(os.path.join(tex_res, "eligible_flights.csv"))))
    stored_files = sorted(r["file"] for r in stored)
    assert re_elig == stored_files, "eligibility rule does not reproduce eligible_flights.csv"
    for f in stored_files:
        assert os.path.isfile(os.path.join(mat687, f)), f
    n = len(stored_files)
    rng = np.random.default_rng(C.ROOT_SEED)
    perm = rng.permutation(n)
    n_cal = int(round(C.CAL_FRACTION * n))
    cal = set(stored_files[i] for i in perm[:n_cal])
    rows = []
    for r in stored:
        m = parse_fname(r["file"])
        rows.append({"file": r["file"], "tail": "687", "set": "687-CAL" if r["file"] in cal else "687-TEST",
                     "datestr": m["datestr"], "year": m["year"], "month": m["month"], "season": season(m["month"]),
                     "duration_s": int(float(r["duration_s"]))})
    # ---- 652
    files652 = sorted(f for f in os.listdir(mat652) if FNAME_RE.match(f))
    with Pool(nw) as pool:
        metas = pool.map(meta_652, [os.path.join(mat652, f) for f in files652])
    with open(os.path.join(res, "inventory_652.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(metas[0].keys()))
        w.writeheader()
        w.writerows(metas)
    n652 = 0
    for m in metas:
        if eligible(m["duration_s"], m["n_WOW_transitions"], m["t_PH5_Cruise_s"], m["t_PH12_s"], m["dup_suffix"]):
            n652 += 1
            rows.append({"file": m["file"], "tail": "652", "set": "652", "datestr": m["datestr"], "year": m["year"],
                         "month": m["month"], "season": season(m["month"]), "duration_s": m["duration_s"]})
    rows.sort(key=lambda r: (r["tail"] != "687", r["file"]))
    for r in rows:
        r["temporal_group"] = ({"MarMay": "early", "JulSep": "late"}.get(r["season"], "")
                               if r["set"] == "687-TEST" else "")
    with open(os.path.join(res, "splits.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    cnt = {}
    for r in rows:
        cnt[(r["set"], r["year"], r["month"])] = cnt.get((r["set"], r["year"], r["month"]), 0) + 1
    print(f"687 eligible {n}: CAL {n_cal}, TEST {n - n_cal}; 652 files {len(files652)}, eligible {n652}")
    for k in sorted(cnt):
        print("  ", k, cnt[k])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 8)
