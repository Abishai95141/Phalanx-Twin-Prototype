"""Flight-level statistics for profile modelling (all non-duplicate flights in the archive).

* record duration, airborne time (WOW==1, inverted logic), time per PH phase
* throttle activity: rainflow cycle counts of the 4-engine-mean PLA (1 Hz, 0.5-deg hysteresis)
  and of the 4-engine-mean N1 (1 Hz), per flight and per airborne hour, by range bin
Rainflow: ASTM E1049-85 three-point method on turning points; half cycles counted 0.5.

Usage: python -I flight_level.py <mat_dir> <results_dir> <fig_dir> [n_workers]
"""
import os
import sys
import csv
import json
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import load_flight, PHASES  # noqa: E402
from common import read_csv, per_second  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PLA_BINS = [5, 10, 20, 40]
N1_BINS = [10, 20, 40, 60]


def turning_points(x, hyst):
    """Reversal points with hysteresis (excursions smaller than hyst are ignored)."""
    tp = [x[0]]
    ext = x[0]
    trend = 0
    for v in x[1:]:
        if trend == 0:
            if v - tp[0] >= hyst:
                trend, ext = 1, v
            elif tp[0] - v >= hyst:
                trend, ext = -1, v
        elif trend == 1:
            if v > ext:
                ext = v
            elif ext - v >= hyst:
                tp.append(ext)
                trend, ext = -1, v
        else:
            if v < ext:
                ext = v
            elif v - ext >= hyst:
                tp.append(ext)
                trend, ext = 1, v
    tp.append(ext)
    return np.array(tp)


def rainflow(tp):
    """ASTM three-point rainflow; returns list of (range, count)."""
    stack, out = [], []
    for p in tp:
        stack.append(p)
        while len(stack) >= 3:
            X = abs(stack[-1] - stack[-2])
            Y = abs(stack[-2] - stack[-3])
            if X < Y:
                break
            if len(stack) == 3:
                out.append((Y, 0.5))
                stack.pop(0)
            else:
                out.append((Y, 1.0))
                last = stack.pop()
                stack.pop()
                stack.pop()
                stack.append(last)
    for i in range(len(stack) - 1):
        out.append((abs(stack[i + 1] - stack[i]), 0.5))
    return out


def per_flight(path):
    F = load_flight(path)
    fn = os.path.basename(path)
    n = F["PH"].x.size
    pla = np.mean([per_second(F, f"PLA_{i}")[:n] for i in range(1, 5)], axis=0)
    n1 = np.mean([per_second(F, f"N1_{i}")[:n] for i in range(1, 5)], axis=0)
    wow = F["WOW"].x
    air_h = float(np.sum(wow == 1) / 3600)
    rec = {"file": fn, "record_h": n / 3600, "airborne_h": air_h}
    rp = rainflow(turning_points(pla, 0.5))
    rn = rainflow(turning_points(n1, 0.5))
    for b in PLA_BINS:
        rec[f"pla_cycles_ge{b}deg"] = float(sum(c for r, c in rp if r >= b))
    for b in N1_BINS:
        rec[f"n1_cycles_ge{b}pct"] = float(sum(c for r, c in rn if r >= b))
    ph = F["PH"].x
    for c, nm in PHASES.items():
        rec[f"t_{nm}_min"] = float(np.sum(ph == c) / 60)
    rec["n_phase_segments"] = int(np.sum(np.diff(ph) != 0) + 1)
    rec["frac_airborne_AT_engaged"] = float(np.mean(F["ATEN"].x[wow == 1] == 1)) if air_h > 0 else np.nan
    rec["max_ALT"] = float(F["ALT"].x.max())
    return rec


def main(mat_dir, res, figdir, nw=8):
    inv = read_csv(os.path.join(res, "inventory_flights.csv"))
    files = [r["file"] for r in inv if r["dup_suffix"] != "True"]
    with Pool(nw) as pool:
        rows = list(pool.imap(per_flight, [os.path.join(mat_dir, f) for f in files], chunksize=4))
    with open(os.path.join(res, "flight_level.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    elig = set(r["file"] for r in read_csv(os.path.join(res, "eligible_flights.csv")))
    E = [r for r in rows if r["file"] in elig]
    summ = {"n_records_nondup": len(rows), "n_complete_eligible": len(E)}
    rec_h = np.array([r["record_h"] for r in rows])
    air_h = np.array([r["airborne_h"] for r in rows])
    summ["record_h_pct"] = dict(zip(["p0", "p5", "p25", "p50", "p75", "p95", "p100"], np.percentile(rec_h, [0, 5, 25, 50, 75, 95, 100]).round(3).tolist()))
    summ["airborne_h_pct_eligible"] = dict(zip(["p5", "p25", "p50", "p75", "p95"], np.percentile([r["airborne_h"] for r in E], [5, 25, 50, 75, 95]).round(3).tolist()))
    summ["n_records_no_airborne"] = int(np.sum(air_h == 0))
    summ["total_record_h"] = float(rec_h.sum())
    summ["total_airborne_h"] = float(air_h.sum())
    for c, nm in PHASES.items():
        v = np.array([r[f"t_{nm}_min"] for r in E])
        summ[f"phase_{nm}_min_pct"] = dict(zip(["p5", "p25", "p50", "p75", "p95"], np.percentile(v, [5, 25, 50, 75, 95]).round(2).tolist()))
    tot_air = sum(r["airborne_h"] for r in E)
    for b in PLA_BINS:
        k = f"pla_cycles_ge{b}deg"
        summ[f"{k}_per_flight_med"] = float(np.median([r[k] for r in E]))
        summ[f"{k}_per_airborne_h_pooled"] = float(sum(r[k] for r in E) / tot_air)
    for b in N1_BINS:
        k = f"n1_cycles_ge{b}pct"
        summ[f"{k}_per_flight_med"] = float(np.median([r[k] for r in E]))
        summ[f"{k}_per_airborne_h_pooled"] = float(sum(r[k] for r in E) / tot_air)
    summ["frac_airborne_AT_engaged_med"] = float(np.nanmedian([r["frac_airborne_AT_engaged"] for r in E]))
    json.dump(summ, open(os.path.join(res, "flight_level_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))
    # figure
    plt.rcParams.update({"font.size": 8, "figure.dpi": 130})
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5))
    axs[0].hist(rec_h * 60, bins=60, color="#1f4e79")
    axs[0].set_xlabel("record length (min), all non-duplicate records")
    axs[0].set_ylabel("count")
    names = [PHASES[c] for c in range(0, 8)]
    axs[1].boxplot([[r[f"t_{nm}_min"] for r in E] for nm in names], showfliers=False)
    axs[1].set_xticks(range(1, 9))
    axs[1].set_xticklabels(names, rotation=45)
    axs[1].set_ylabel("minutes per flight (complete flights)")
    for b, c in zip(N1_BINS, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]):
        k = f"n1_cycles_ge{b}pct"
        axs[2].hist([r[k] / max(r["airborne_h"], 1e-6) for r in E], bins=40, histtype="step", color=c, label=f"N1 range >= {b} %")
    axs[2].set_xlabel("rainflow N1 cycles per airborne hour (per flight)")
    axs[2].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_flight_level.png"))
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
