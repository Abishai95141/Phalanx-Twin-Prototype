"""POST HOC diagnostic (requested by the coordinator after the quick look; NOT pre-registered, NOT a verdict).

Question: does the real N2 -> FF lead-lag differ between autothrottle-engaged and manual flight? If small-signal
fluctuations come from closed-loop governing (FADEC/autothrottle acting on a speed error), the N2-leads-FF signature
should depend on whether the loop is closed around the levers (ATEN = 1) or not.

Method (same estimator as B2): per flight and engine, airborne-rule samples (all four N1 > 25 %) in cruise (PH 5),
split into contiguous runs (>= 120 s) with ATEN = 1 (A/T engaged, 1 Hz word held to 4 Hz) or ATEN = 0; first
differences within each run; cross-correlation pooled over the runs of one class (sum of products / counts per lag,
+-10 s); lag of the peak for FF->N2 (positive: N2 lags FF), N2->N1 and FF->EGT. Group value = median over flights
that have >= 600 samples in the class; flight-bootstrap 95 % CI of the median difference (A/T minus manual), paired
over flights that have both classes.
Also reported: PLA activity (SD of 1-s PLA differences) per class, because A/T moves the levers.

Phases: default cruise only (PH 5); "--phases 4,5,6" pools climb, cruise and descent/approach (confounded with phase:
A/T use differs by phase; reported as such).

Usage: python -I q02_at_leadlag.py <mat_dir> <flight_list_file> <out_json> [n_workers] [--phases 4,5,6]
"""
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402
from dlio import load_flight  # noqa: E402

L = 40
PHASES = [5]
PAIRS = [("FF", "N2"), ("N2", "N1"), ("FF", "EGT")]


def runs(mask, min_len):
    m = np.r_[False, mask, False].astype(int)
    d = np.diff(m)
    return [(a, b) for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)) if b - a >= min_len]


def pooled_lag(segs_a, segs_b):
    num = np.zeros(2 * L + 1)
    cnt = np.zeros(2 * L + 1)
    for a, b in zip(segs_a, segs_b):
        a = (a - a.mean()) / (a.std() + 1e-12)
        b = (b - b.mean()) / (b.std() + 1e-12)
        for i, l in enumerate(range(-L, L + 1)):
            if l >= 0:
                x, y = a[:a.size - l], b[l:]
            else:
                x, y = a[-l:], b[:b.size + l]
            num[i] += np.sum(x * y)
            cnt[i] += x.size
    cc = num / np.maximum(cnt, 1)
    return (int(np.argmax(cc)) - L) / R.RATE


def job(args):
    path, phases = args
    F = load_flight(path)
    d = R.load(path)
    n = d["n"]
    aten = F["ATEN"].x.astype(int)
    at4 = aten[np.minimum((np.arange(n) * R.DT * F["ATEN"].rate).astype(int), aten.size - 1)]
    air = np.all(d["Y"]["N1"] > 25.0, axis=0) & np.isin(d["PH"], phases)
    out = {"file": os.path.basename(path)}
    for cls, val in (("AT", 1), ("manual", 0)):
        rr = runs(air & (at4 == val), int(120 * R.RATE))
        nsamp = sum(b - a for a, b in rr)
        out[f"{cls}_n"] = int(nsamp)
        if nsamp < 600:
            continue
        for k in range(4):
            for u, v in PAIRS:
                sa = [np.diff(d["Y"][u][k][a:b]) for a, b in rr]
                sb = [np.diff(d["Y"][v][k][a:b]) for a, b in rr]
                out[f"{cls}_{u}->{v}_e{k + 1}"] = pooled_lag(sa, sb)
        pla = np.concatenate([np.diff(d["PLA"][:, a:b:4], axis=1).ravel() for a, b in rr])
        out[f"{cls}_PLA_1s_diff_sd"] = float(np.std(pla))
    return out


def main(mat_dir, lst, out_json, nw=8):
    files = [l.strip() for l in open(lst) if l.strip()]
    with Pool(nw) as pool:
        rows = pool.map(job, [(os.path.join(mat_dir, f), list(PHASES)) for f in files])
    res = {"note": "POST HOC diagnostic, not pre-registered, no verdict.", "phases": PHASES, "n_files": len(files), "pairs": {}}
    rng = np.random.default_rng(R.ROOT_SEED)
    for u, v in PAIRS:
        key = f"{u}->{v}"
        at = np.array([np.mean([r[f"AT_{key}_e{k}"] for k in range(1, 5)]) for r in rows if f"AT_{key}_e1" in r])
        mn = np.array([np.mean([r[f"manual_{key}_e{k}"] for k in range(1, 5)]) for r in rows if f"manual_{key}_e1" in r])
        both = [r for r in rows if f"AT_{key}_e1" in r and f"manual_{key}_e1" in r]
        diff = np.array([np.mean([r[f"AT_{key}_e{k}"] - r[f"manual_{key}_e{k}"] for k in range(1, 5)]) for r in both])
        bs = [np.median(diff[rng.integers(0, diff.size, diff.size)]) for _ in range(2000)] if diff.size >= 5 else []
        res["pairs"][key] = {"AT_median_lag_s": float(np.median(at)) if at.size else None, "AT_n_flights": int(at.size),
                             "manual_median_lag_s": float(np.median(mn)) if mn.size else None, "manual_n_flights": int(mn.size),
                             "paired_n_flights": int(diff.size),
                             "median_paired_diff_AT_minus_manual_s": float(np.median(diff)) if diff.size else None,
                             "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))] if bs else None}
    res["PLA_activity"] = {cls: float(np.median([r[f"{cls}_PLA_1s_diff_sd"] for r in rows if f"{cls}_PLA_1s_diff_sd" in r]))
                           if any(f"{cls}_PLA_1s_diff_sd" in r for r in rows) else None for cls in ("AT", "manual")}
    res["rows"] = rows
    with open(out_json, "w") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    if "--phases" in sys.argv:
        i = sys.argv.index("--phases")
        PHASES[:] = [int(x) for x in sys.argv[i + 1].split(",")]
        del sys.argv[i:i + 2]
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
