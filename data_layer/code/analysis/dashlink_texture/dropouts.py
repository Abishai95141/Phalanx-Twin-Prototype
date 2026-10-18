"""Archive-wide missingness / dropout / stuck-value analysis.

The DASHlink files contain no NaN at all (verified by inventory.py), so missing data
must be identified from value patterns. This script measures, for every non-discrete
parameter and every flight in the archive:
  * sentinel samples: samples equal to the parameter's global min or max value
    (candidate "end-of-scale" words), split into isolated (both neighbours far away)
    and non-isolated occurrences, their run lengths, rate by flight phase, and
    position inside the 4-s ARINC-717-style frame;
  * co-occurrence of sentinel events across parameters (same 1-s subframe);
  * sibling-referenced stuck runs for the 4-engine groups: one engine's value is
    constant for >= 30 s while the other three engines' same parameter moves by
    >= 5 LSB, aircraft airborne (WOW == 1, inverted logic per DASHlink FAQ).

Usage: python -I dropouts.py <mat_dir> <results_dir> [n_workers]
Writes dropouts_sentinels.csv, dropouts_cooccurrence.csv, dropouts_stuck.csv,
       dropouts_runlengths.json
"""
import os
import sys
import csv
import json
import collections
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import list_flights, load_flight, run_lengths, run_bounds, robust_sigma  # noqa: E402

ENGINE_GROUPS = ["N1", "N2", "EGT", "FF", "OIP", "OIT", "VIB", "PLA"]
TABLE = {}
STUCK_MIN_S = 30.0


def load_table(res):
    t = {}
    for r in csv.DictReader(open(os.path.join(res, "param_table.csv"))):
        t[r["param"]] = r
    return t


def per_flight(args):
    path, table = args
    F = load_flight(path)
    fn = os.path.basename(path)
    ph = F["PH"].x
    wow = F["WOW"].x
    out = []
    events = {}
    runl = collections.defaultdict(list)
    for name, p in F.items():
        t = table[name]
        if t["type"] == "discrete":
            continue
        x = p.x
        r = p.rate
        k = max(int(round(r)), 1)
        lsb = float(t["lsb_mode"]) if t["lsb_mode"] not in ("", "nan") else np.nan
        dx = np.diff(x)
        sd = robust_sigma(dx)
        J = max(10 * (lsb if np.isfinite(lsb) else 0), 5 * (sd if np.isfinite(sd) else 0))
        # phase / air-ground at the parameter's rate
        if r >= 1:
            phr = np.repeat(ph, k)[: x.size]
            wr = np.repeat(wow, k)[: x.size]
        else:
            step = int(round(1 / r))
            phr = ph[::step][: x.size]
            wr = wow[::step][: x.size]
        for which, v in (("min", float(t["global_min"])), ("max", float(t["global_max"]))):
            m = np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
            n = int(m.sum())
            rec = {"file": fn, "param": name, "which": which, "value": v, "n": x.size, "n_eq": n}
            if n:
                idx = np.flatnonzero(m)
                prev = np.r_[np.nan, x[:-1]][idx]
                nxt = np.r_[x[1:], np.nan][idx]
                iso = (np.abs(x[idx] - prev) > J) & (np.abs(x[idx] - nxt) > J)
                rec["n_isolated"] = int(np.nansum(iso))
                rec["n_airborne"] = int(np.sum(wr[idx] == 1))
                rl = run_lengths(m)
                runl[(name, which)].extend(rl.tolist())
                for c in range(8):
                    rec[f"n_PH{c}"] = int(np.sum(phr[idx] == c))
                if r >= 1:
                    pos = idx % int(4 * k)
                    rec["frame_pos_counts"] = ";".join(str(c) for c in np.bincount(pos, minlength=int(4 * k)))
                    events[(name, which)] = np.unique(idx[iso] // k)  # seconds holding an ISOLATED sentinel
            else:
                rec["n_isolated"] = 0
            out.append(rec)
    # samples available per phase (for rates), at 1 Hz
    phase_secs = {c: int(np.sum(ph == c)) for c in range(8)}
    # sibling stuck detection for 4-engine groups
    stuck = []
    for g in ENGINE_GROUPS:
        names = [f"{g}_{i}" for i in range(1, 5)]
        if not all(n in F for n in names):
            continue
        X = np.vstack([F[n].x for n in names])
        r = F[names[0]].rate
        k = int(round(r))
        wr = np.repeat(wow, k)[: X.shape[1]]
        lsb = float(table[names[0]]["lsb_mode"])
        for i in range(4):
            same = np.r_[False, np.diff(X[i]) == 0]
            # run of identical values: mark samples equal to previous
            s, e = run_bounds(same)
            for a, b in zip(s, e):
                a0 = a - 1  # first sample of the constant run
                dur = (b - a0) / r
                if dur < STUCK_MIN_S:
                    continue
                if np.mean(wr[a0:b] == 1) < 0.99:
                    continue
                others = [j for j in range(4) if j != i]
                mov = [np.ptp(X[j, a0:b]) for j in others]
                if min(mov) >= 5 * lsb:
                    stuck.append({"file": fn, "param": names[i], "start_s": a0 / r, "dur_s": dur,
                                  "value": float(X[i, a0]), "sibling_min_range": float(min(mov)),
                                  "sibling_range_in_lsb": float(min(mov) / lsb)})
    airborne_s = float(np.sum(wow == 1))
    return fn, out, events, dict(runl), phase_secs, stuck, airborne_s, F["PH"].x.size


def main(mat_dir, res, nw=8):
    table = load_table(res)
    files = list_flights(mat_dir)
    rows, stuck_all = [], []
    co = collections.Counter()
    single = collections.Counter()
    runl_all = collections.defaultdict(list)
    phase_tot = collections.Counter()
    air_tot = 0.0
    rec_tot = 0
    with Pool(nw) as pool:
        for fn, out, events, runl, phs, stuck, air_s, nsec in pool.imap(per_flight, [(f, table) for f in files], chunksize=4):
            rows.extend(out)
            stuck_all.extend(stuck)
            for k, v in runl.items():
                runl_all[f"{k[0]}|{k[1]}"].extend(v)
            for c, s in phs.items():
                phase_tot[c] += s
            air_tot += air_s
            rec_tot += nsec
            keys = [k for k, v in events.items() if v.size]
            for a in keys:
                single[a] += events[a].size
            for i, a in enumerate(keys):
                for b in keys[i + 1:]:
                    n = np.intersect1d(events[a], events[b]).size
                    if n:
                        co[(a, b)] += n
    # aggregate sentinel table
    agg = collections.defaultdict(lambda: collections.Counter())
    pos_agg = {}
    for r in rows:
        key = (r["param"], r["which"], r["value"])
        a = agg[key]
        a["n"] += r["n"]
        a["n_eq"] += r["n_eq"]
        a["n_isolated"] += r.get("n_isolated", 0)
        a["n_airborne"] += r.get("n_airborne", 0)
        a["flights_with"] += int(r["n_eq"] > 0)
        a["flights_with_isolated"] += int(r.get("n_isolated", 0) > 0)
        a["flights"] += 1
        for c in range(8):
            a[f"n_PH{c}"] += r.get(f"n_PH{c}", 0)
        if r.get("frame_pos_counts"):
            v = np.array([int(c) for c in r["frame_pos_counts"].split(";")])
            pos_agg[key] = pos_agg.get(key, 0) + v
    out = []
    for (p, w, v), a in agg.items():
        rate = float(table[p]["rate_hz"])
        rec = {"param": p, "which": w, "value": v, "rate_hz": rate, "n_samples": a["n"], "n_eq": a["n_eq"],
               "frac_eq": a["n_eq"] / a["n"], "n_isolated": a["n_isolated"],
               "frac_isolated_of_eq": a["n_isolated"] / a["n_eq"] if a["n_eq"] else np.nan,
               "isolated_per_record_hour": a["n_isolated"] / (a["n"] / rate / 3600),
               "flights_with": a["flights_with"], "flights_with_isolated": a["flights_with_isolated"],
               "flights": a["flights"], "frac_eq_airborne": a["n_airborne"] / a["n_eq"] if a["n_eq"] else np.nan}
        pa = pos_agg.get((p, w, v))
        if pa is not None and pa.sum() > 0:
            # chi-square-like uniformity index of within-frame position (1 = uniform)
            rec["frame_pos_max_over_mean"] = float(pa.max() / pa.mean())
        else:
            rec["frame_pos_max_over_mean"] = np.nan
        for c in range(8):
            secs = phase_tot[c]
            rec[f"rate_per_sample_PH{c}"] = a[f"n_PH{c}"] / (secs * rate) if secs else np.nan
        out.append(rec)
    out.sort(key=lambda r: -r["n_isolated"])
    with open(os.path.join(res, "dropouts_sentinels.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    # co-occurrence: P(B in same second | A)
    corows = []
    for (a, b), n in co.most_common():
        if n < 5:
            continue
        pa, pb = single[a] / rec_tot, single[b] / rec_tot
        corows.append({"A": f"{a[0]}|{a[1]}", "B": f"{b[0]}|{b[1]}", "n_same_second": n,
                       "n_A_seconds": single[a], "n_B_seconds": single[b],
                       "P_B_given_A": n / single[a], "P_A_given_B": n / single[b],
                       "lift_vs_independent": (n / rec_tot) / (pa * pb)})
    with open(os.path.join(res, "dropouts_cooccurrence.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(corows[0].keys()))
        w.writeheader()
        w.writerows(corows)
    with open(os.path.join(res, "dropouts_stuck.csv"), "w", newline="") as fh:
        keys = ["file", "param", "start_s", "dur_s", "value", "sibling_min_range", "sibling_range_in_lsb"]
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(stuck_all)
    rl_summary = {}
    for k, v in runl_all.items():
        v = np.array(v)
        rl_summary[k] = {"n_runs": int(v.size), "hist_1_to_10_plus": np.bincount(np.minimum(v, 11), minlength=12)[1:].tolist(),
                         "max": int(v.max()) if v.size else 0}
    json.dump({"run_lengths_samples": rl_summary, "phase_seconds_total": dict(phase_tot),
               "airborne_seconds_total": air_tot, "record_seconds_total": rec_tot,
               "stuck_rule": f"constant >= {STUCK_MIN_S}s while all 3 siblings move >= 5 LSB, WOW==1 throughout"},
              open(os.path.join(res, "dropouts_runlengths.json"), "w"), indent=1)
    print("rows", len(out), "co", len(corows), "stuck", len(stuck_all), "airborne h", air_tot / 3600, "record h", rec_tot / 3600)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
