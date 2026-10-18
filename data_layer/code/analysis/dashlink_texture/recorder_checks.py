"""Recorder / timing / discrete-semantics checks over every flight in the archive.

Usage: python -I recorder_checks.py <mat_dir> <results_dir> [n_workers]
Writes recorder_checks_flights.csv, recorder_glitch_frames.csv, recorder_discrete_lags.csv,
       recorder_skew_pairs.csv, recorder_checks_summary.json
"""
import os
import sys
import csv
import json
import hashlib
import collections
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import list_flights, load_flight, parse_fname  # noqa: E402

IDENT = ["ACID", "ESN_1", "ESN_2", "ESN_3", "ESN_4", "DVER_1", "DVER_2", "DATE_YEAR", "DATE_MONTH",
         "DATE_DAY", "VAR_1107", "VAR_2670", "VAR_5107", "VAR_6670"]


def transitions(x, rate):
    """Return (times_s, new_values) of value changes in a discrete series."""
    i = np.flatnonzero(np.diff(x) != 0) + 1
    return i / rate, x[i]


def xcorr_lag(a, b, rate, maxlag_s=3.0):
    """Lag (s) of b relative to a maximising the correlation of first differences
    (positive = b lags a), with parabolic sub-sample refinement."""
    da, db = np.diff(a), np.diff(b)
    n = min(da.size, db.size)
    da, db = da[:n] - da[:n].mean(), db[:n] - db[:n].mean()
    if np.std(da) == 0 or np.std(db) == 0:
        return np.nan, np.nan
    L = int(maxlag_s * rate)
    lags = np.arange(-L, L + 1)
    c = np.array([np.dot(da[max(0, -l):n - max(0, l)], db[max(0, l):n - max(0, -l)]) for l in lags])
    c = c / (np.std(da) * np.std(db) * n)
    k = int(np.argmax(c))
    frac = 0.0
    if 0 < k < len(c) - 1:
        y0, y1, y2 = c[k - 1], c[k], c[k + 1]
        den = y0 - 2 * y1 + y2
        frac = 0.5 * (y0 - y2) / den if den != 0 else 0.0
    return (lags[k] + frac) / rate, float(c[k])


def block_mean(x, k):
    n = (x.size // k) * k
    return x[:n].reshape(-1, k).mean(axis=1)


def per_flight(path):
    F = load_flight(path)
    meta = parse_fname(path)
    fn = meta["file"]
    h = hashlib.sha1()
    for k in sorted(F):
        h.update(F[k].raw.tobytes())
    rec = {"file": fn, "content_sha1": h.hexdigest(), "n_frames": F["FRMC"].x.size}
    glitches = []
    # ---- frame counter
    fc = F["FRMC"].x
    d = np.mod(np.diff(fc), 4096)
    irr = np.flatnonzero(d != 4)
    wrap = [(fc[i] >= 4088 or fc[i + 1] <= 8) and d[i] == 3 for i in irr]
    rec["frmc_irregular"] = int(irr.size)
    rec["frmc_irregular_at_wrap_step3"] = int(sum(wrap))
    rec["frmc_irregular_other"] = ";".join(f"{int(fc[i])}->{int(fc[i + 1])}@frame{i}" for i, w in zip(irr, wrap) if not w)
    rec["frmc_max"] = float(fc.max())
    # ---- identity / sync words: glitch frames
    nfr = fc.size
    bad = np.zeros(nfr, bool)
    for k in IDENT:
        x = F[k].x
        v, c = np.unique(x, return_counts=True)
        md = v[np.argmax(c)]
        b = x != md
        if b.any():
            for i in np.flatnonzero(b):
                glitches.append({"file": fn, "param": k, "frame": int(i), "n_frames": nfr,
                                 "value": float(x[i]), "mode": float(md)})
        bad |= b
    rec["n_glitch_frames"] = int(bad.sum())
    rec["glitch_frame_positions"] = ";".join(str(int(i)) for i in np.flatnonzero(bad)[:10])
    # ---- GMT clock
    H, M, S = F["GMT_HOUR"].x, F["GMT_MINUTE"].x, F["GMT_SEC"].x
    rec["gmt_out_of_range_samples"] = int(np.sum((H > 23) | (M > 59) | (S > 59)))
    tg = H * 3600 + M * 60 + S
    ok = (H <= 23) & (M <= 59) & (S <= 59)
    ts = np.arange(tg.size) / 2.0
    tgu = np.unwrap(tg * 2 * np.pi / 86400) * 86400 / (2 * np.pi)
    dev = (tgu - ts)[ok]
    if dev.size > 10:
        dev = dev - np.median(dev)
        rec["gmt_minus_sample_time_p01"] = float(np.percentile(dev, 1))
        rec["gmt_minus_sample_time_p99"] = float(np.percentile(dev, 99))
        jumps = np.abs(np.diff(dev)) > 12  # beyond the 6-s clock granularity
        rec["gmt_jumps_gt12s"] = int(np.sum(jumps))
        sl = np.polyfit(ts[ok], tgu[ok], 1)[0] if ok.sum() > 100 else np.nan
        rec["gmt_vs_sample_slope"] = float(sl)
    rec["gmt_sec_values"] = ";".join(f"{v:g}" for v in np.unique(S)[:12])
    rec["gmt_sec_constant"] = bool(np.unique(S[ok]).size <= 1)
    rec["file_hhmm_minus_gmt_start_min"] = float(((meta.get("hour", 0) * 60 + meta.get("minute", 0)) - tg[0] / 60 + 720) % 1440 - 720) if ok[0] else np.nan
    # ---- discrete polarity (WOW=1 airborne per FAQ)
    wow = F["WOW"].x
    ralt = block_mean(F["RALT"].x, 8)
    cas = block_mean(F["CAS"].x, 4)
    alt = block_mean(F["ALT"].x, 4)
    n = min(wow.size, ralt.size, cas.size)
    air = (ralt[:n] > 1000) & (cas[:n] > 150)
    gnd = (cas[:n] < 30) & (ralt[:n] < 20) & (ralt[:n] > -20)
    rec["P_WOW1_given_clearly_airborne"] = float(np.mean(wow[:n][air] == 1)) if air.any() else np.nan
    rec["P_WOW1_given_clearly_ground"] = float(np.mean(wow[:n][gnd] == 1)) if gnd.any() else np.nan
    hi = alt[:n] > 15000
    for k in ["LGDN", "LGUP"]:
        rec[f"mean_{k}_above_FL150"] = float(np.mean(F[k].x[:n][hi])) if hi.any() else np.nan
        rec[f"mean_{k}_clearly_ground"] = float(np.mean(F[k].x[:n][gnd])) if gnd.any() else np.nan
    for k in ["MSQT_1", "MSQT_2", "NSQT"]:
        r = F[k].rate
        x = block_mean(F[k].x, int(r))[:n]
        rec[f"mean_{k}_clearly_airborne"] = float(np.mean(x[air])) if air.any() else np.nan
        rec[f"mean_{k}_clearly_ground"] = float(np.mean(x[gnd])) if gnd.any() else np.nan
    # ---- discrete event timing around WOW transitions
    lags = []
    tw, vw = transitions(wow, 1.0)
    for t0, v0 in zip(tw, vw):
        ev = "liftoff" if v0 == 1 else "touchdown"
        row = {"file": fn, "event": ev, "t_wow": t0}
        for k in ["MSQT_1", "MSQT_2", "NSQT", "LGUP", "LGDN", "PH"]:
            tk, vk = transitions(F[k].x, F[k].rate)
            if tk.size:
                j = np.argmin(np.abs(tk - t0))
                if abs(tk[j] - t0) < 120:
                    row[f"lag_{k}_s"] = float(tk[j] - t0)
                    row[f"new_{k}"] = float(vk[j])
        lags.append(row)
    # ---- inter-channel time skews (airborne only, flights with >= 20 min airborne)
    skews = []
    if np.sum(wow == 1) > 1200:
        a0 = np.flatnonzero(wow == 1)[0]
        a1 = np.flatnonzero(wow == 1)[-1]
        sl = slice(a0 * 4, a1 * 4)

        def seg(name, rate_out=4):
            p = F[name]
            x = p.x
            if p.rate > rate_out:
                x = block_mean(x, int(p.rate // rate_out))
            elif p.rate < rate_out:
                x = np.repeat(x, int(rate_out // p.rate))
            return x[sl]
        alt = seg("ALT")
        dalt = np.gradient(alt) * 4 * 60  # ft/min
        pairs = [("AOA1", "AOA2"), ("BAL1", "BAL2"), ("ALT", "BAL1"), ("TH", "MH"), ("N1C", "N1_1"),
                 ("PLA_1", "N1C"), ("ALTR", "IVV")]
        for a, b in pairs:
            x, y = seg(a), seg(b)
            if a in ("TH", "MH") or b in ("TH", "MH"):
                x, y = np.unwrap(np.deg2rad(x)), np.unwrap(np.deg2rad(y))
            lag, c = xcorr_lag(x, y, 4.0, 3.0 if a != "PLA_1" else 10.0)
            skews.append({"file": fn, "pair": f"{a}->{b}", "lag_s": lag, "peak_corr": c})
        lag, c = xcorr_lag(np.cumsum(seg("IVV")) / 240.0, alt, 4.0, 5.0)
        skews.append({"file": fn, "pair": "int(IVV)->ALT", "lag_s": lag, "peak_corr": c})
        lag, c = xcorr_lag(np.cumsum(seg("ALTR")) / 240.0, alt, 4.0, 5.0)
        skews.append({"file": fn, "pair": "int(ALTR)->ALT", "lag_s": lag, "peak_corr": c})
    return rec, glitches, lags, skews


def write(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main(mat_dir, res, nw=8):
    files = list_flights(mat_dir)
    R, G, L, S = [], [], [], []
    with Pool(nw) as pool:
        for rec, g, l, s in pool.imap(per_flight, files, chunksize=4):
            R.append(rec)
            G.extend(g)
            L.extend(l)
            S.extend(s)
    write(os.path.join(res, "recorder_checks_flights.csv"), R)
    write(os.path.join(res, "recorder_glitch_frames.csv"), G)
    write(os.path.join(res, "recorder_discrete_lags.csv"), L)
    write(os.path.join(res, "recorder_skew_pairs.csv"), S)
    # duplicate content check
    by = collections.defaultdict(list)
    for r in R:
        by[r["content_sha1"]].append(r["file"])
    dups = [v for v in by.values() if len(v) > 1]
    summ = {"n_flights": len(R), "identical_content_groups": dups,
            "frmc_irregular_total": int(sum(r["frmc_irregular"] for r in R)),
            "frmc_irregular_at_wrap_step3": int(sum(r["frmc_irregular_at_wrap_step3"] for r in R)),
            "frmc_irregular_other": [(r["file"], r["frmc_irregular_other"]) for r in R if r["frmc_irregular_other"]],
            "flights_with_glitch_frames": int(sum(r["n_glitch_frames"] > 0 for r in R)),
            "glitch_frames_total": int(sum(r["n_glitch_frames"] for r in R)),
            "frames_total": int(sum(r["n_frames"] for r in R))}
    pos = [(g["frame"], g["n_frames"]) for g in G]
    summ["glitch_in_first_frame"] = int(sum(1 for f, n in pos if f == 0))
    summ["glitch_in_last_frame"] = int(sum(1 for f, n in pos if f == n - 1))
    json.dump(summ, open(os.path.join(res, "recorder_checks_summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != "frmc_irregular_other"}, indent=1)[:2000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
