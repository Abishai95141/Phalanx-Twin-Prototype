"""Temporal structure (burstiness) of isolated sentinel dropouts, all non-duplicate flights.

For each parameter with systematic sentinel dropouts (dropouts_sentinels.csv, isolated rate
>= 5 per record-hour), mark seconds containing >= 1 isolated sentinel sample. Then:
  * Fano factor (variance/mean of event counts) in 10-s and 60-s windows (Poisson = 1)
  * P(event second | previous second was an event second) vs P(event second)
  * bursts = maximal groups of event seconds separated by gaps <= G s (G = 10 s):
    burst duration, events per burst, gap between bursts, fraction of record time in bursts,
    per-sample dropout probability inside / outside bursts
These give a two-state (Gilbert-Elliott-type) parameterisation:
  mean bad-state (burst) duration, mean good-state duration, per-sample loss prob per state.

Usage: python -I dropout_bursts.py <mat_dir> <results_dir> [n_workers]
"""
import os
import sys
import csv
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import load_flight, robust_sigma  # noqa: E402
from common import read_csv, load_lsb  # noqa: E402

G = 10


def targets(res):
    t = {}
    for r in read_csv(os.path.join(res, "dropouts_sentinels.csv")):
        if float(r["isolated_per_record_hour"]) >= 5 and float(r["frac_isolated_of_eq"]) > 0.5:
            t[r["param"]] = float(r["value"])
    return t


def per_flight(args):
    path, T, lsb = args
    F = load_flight(path)
    out = {}
    for name, v in T.items():
        p = F[name]
        x = p.x
        k = int(round(p.rate))
        m = np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
        dx = np.diff(x)
        sd = robust_sigma(dx)
        J = max(10 * lsb[name], 5 * (sd if np.isfinite(sd) else 0))
        prev = np.r_[np.nan, x[:-1]]
        nxt = np.r_[x[1:], np.nan]
        iso = m & (np.abs(x - prev) > J) & (np.abs(x - nxt) > J)
        nsec = x.size // k
        ev = np.zeros(nsec, int)
        np.add.at(ev, np.flatnonzero(iso)[np.flatnonzero(iso) < nsec * k] // k, 1)
        out[name] = (ev, k)
    return out


def main(mat_dir, res, nw=8):
    T = targets(res)
    lsb = load_lsb(res)
    files = [r["file"] for r in read_csv(os.path.join(res, "inventory_flights.csv")) if r["dup_suffix"] != "True"]
    acc = {n: [] for n in T}
    with Pool(nw) as pool:
        for out in pool.imap(per_flight, [(os.path.join(mat_dir, f), T, lsb) for f in files], chunksize=4):
            for n, v in out.items():
                acc[n].append(v)
    rows = []
    for name, lst in acc.items():
        k = lst[0][1]
        fano = {}
        for W in (10, 60):
            c = np.concatenate([e[: (e.size // W) * W].reshape(-1, W).sum(1) for e, _ in lst if e.size >= W])
            fano[W] = float(c.var() / c.mean()) if c.mean() > 0 else np.nan
        es = np.concatenate([(e > 0).astype(int) for e, _ in lst])
        p1 = es.mean()
        pairs = np.concatenate([np.c_[(e[:-1] > 0), (e[1:] > 0)] for e, _ in lst if e.size > 1])
        p11 = pairs[pairs[:, 0] == 1, 1].mean() if (pairs[:, 0] == 1).any() else np.nan
        bdur, bev, gaps, cyc = [], [], [], []
        in_burst_s = 0
        ev_in, ev_tot = 0, 0
        tot_s = 0
        for e, _ in lst:
            tot_s += e.size
            idx = np.flatnonzero(e > 0)
            ev_tot += e.sum()
            if idx.size == 0:
                continue
            br = np.split(idx, np.flatnonzero(np.diff(idx) > G) + 1)
            for b in br:
                if b.size >= 2:
                    d = b[-1] - b[0] + 1
                    bdur.append(d)
                    bev.append(e[b[0]:b[-1] + 1].sum())
                    in_burst_s += d
                    ev_in += e[b[0]:b[-1] + 1].sum()
            bst = [b[0] for b in br if b.size >= 2]
            cyc.extend(np.diff(bst).tolist())
            starts = [b[0] for b in br]
            ends = [b[-1] for b in br]
            gaps.extend((np.array(starts[1:]) - np.array(ends[:-1])).tolist())
        bdur, bev, gaps, cyc = map(np.array, (bdur, bev, gaps, cyc))
        out_s = tot_s - in_burst_s
        rows.append({"param": name, "rate_hz": k, "record_s": int(tot_s), "events": int(ev_tot),
                     "P_event_second": float(p1), "P_event_given_prev_event": float(p11),
                     "fano_10s": fano[10], "fano_60s": fano[60],
                     "n_bursts(>=2 event-seconds, gap<=10s)": int(bdur.size),
                     "bursts_per_record_hour": float(bdur.size / (tot_s / 3600)),
                     "burst_dur_s_med": float(np.median(bdur)) if bdur.size else np.nan,
                     "burst_dur_s_p90": float(np.percentile(bdur, 90)) if bdur.size else np.nan,
                     "events_per_burst_med": float(np.median(bev)) if bev.size else np.nan,
                     "gap_s_med": float(np.median(gaps)) if gaps.size else np.nan,
                     "burst_start_interval_s_p10_p50_p90": ";".join(f"{v:.0f}" for v in np.percentile(cyc, [10, 50, 90])) if cyc.size else "",
                     "frac_time_in_bursts": float(in_burst_s / tot_s),
                     "frac_events_in_bursts": float(ev_in / ev_tot) if ev_tot else np.nan,
                     "p_loss_per_sample_in_burst": float(ev_in / (in_burst_s * k)) if in_burst_s else np.nan,
                     "p_loss_per_sample_outside": float((ev_tot - ev_in) / (out_s * k)) if out_s else np.nan})
    with open(os.path.join(res, "dropout_bursts.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
