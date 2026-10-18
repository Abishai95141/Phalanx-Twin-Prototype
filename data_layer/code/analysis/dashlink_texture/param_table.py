"""Aggregate the per-flight inventory into one row per parameter.

Usage: python -I param_table.py <results_dir>
Reads  inventory_params.csv, param_meta.csv, inventory_flights.csv
Writes param_table.csv  (one row per parameter, all flights in the archive)
"""
import os
import sys
import csv
import collections

import numpy as np


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def sig(x, n=6):
    return float(f"{x:.{n}g}") if np.isfinite(x) else np.nan


def main(res):
    P = list(csv.DictReader(open(os.path.join(res, "inventory_params.csv"))))
    M = {r["param"]: r for r in csv.DictReader(open(os.path.join(res, "param_meta.csv")))}
    Fl = {r["file"]: r for r in csv.DictReader(open(os.path.join(res, "inventory_flights.csv")))}
    by = collections.defaultdict(list)
    for r in P:
        by[r["param"]].append(r)
    out = []
    for name, rows in by.items():
        m = M.get(name, {})
        rate = f(rows[0]["rate"])
        hours = sum(f(r["n"]) for r in rows) / rate / 3600
        mins = np.array([f(r["min"]) for r in rows])
        maxs = np.array([f(r["max"]) for r in rows])
        nun = np.array([f(r["n_unique"]) for r in rows])
        lsbs = np.array([f(r["lsb"]) for r in rows])
        good = np.isfinite(lsbs) & (nun >= 3)
        if good.any():
            c = collections.Counter(sig(v, 5) for v in lsbs[good])
            lsb_mode, lsb_cnt = c.most_common(1)[0]
            lsb_min = float(np.nanmin(lsbs[good]))
            lsb_agree = lsb_cnt / good.sum()
        else:
            lsb_mode = lsb_min = lsb_agree = np.nan
        grid = np.nanmedian([f(r["grid_frac"]) for r in rows])
        intval = all(r["is_integer_valued"] == "True" for r in rows if r["is_integer_valued"])
        vals = collections.Counter()
        for r in rows:
            if r["values"]:
                for kv in r["values"].split(";"):
                    k, v = kv.rsplit(":", 1)
                    vals[float(k)] += int(v)
        total_unique_bound = max(nun[np.isfinite(nun)]) if np.isfinite(nun).any() else 0
        all_small = all(r["values"] for r in rows)
        union_vals = sorted(vals) if all_small else []
        is_discrete = bool(all_small and len(union_vals) <= 16 and intval)
        # update pattern by sub-frame position
        pc = [np.array([f(v) for v in r["pchange_by_subframe_pos"].split(";")])
              for r in rows if r["pchange_by_subframe_pos"]]
        pcm = np.nanmean(np.vstack(pc), axis=0) if pc else np.array([])
        held = np.nanmedian([f(r["frac_held"]) for r in rows])
        run60 = np.nanmedian([f(r["frac_in_const_run_ge_60s"]) for r in rows])
        run600 = np.nanmean([f(r["frac_in_const_run_ge_600s"]) for r in rows])
        maxrun = np.nanmax([f(r["max_const_run_s"]) for r in rows])
        spikes = sum(f(r["n_spikes"]) for r in rows)
        flights_const = sum(1 for r in rows if f(r["n_unique"]) <= 1)
        # airborne-only stats: flights with WOW transitions == 2
        rec = {
            "param": name, "alpha": m.get("alpha", ""), "description": m.get("description", ""),
            "units": m.get("units", ""), "rate_hz": rate, "n_flights": len(rows),
            "dtypes": ";".join(f"{k}:{v}" for k, v in collections.Counter(r["dtype"] for r in rows).most_common()),
            "type": "discrete" if is_discrete else ("integer-continuous" if intval else "continuous"),
            "global_min": float(np.nanmin(mins)), "global_max": float(np.nanmax(maxs)),
            "p01_flight_min": float(np.nanpercentile(mins, 1)), "p99_flight_max": float(np.nanpercentile(maxs, 99)),
            "max_n_unique_in_flight": total_unique_bound,
            "lsb_mode": lsb_mode, "lsb_min": lsb_min, "lsb_agreement": lsb_agree, "grid_frac_median": grid,
            "lsb_x4096": sig(lsb_mode * 4096) if np.isfinite(lsb_mode) else np.nan,
            "frac_held_median": held, "frac_in_const_runs_ge60s_median": run60,
            "frac_in_const_runs_ge600s_mean": run600, "max_const_run_s": maxrun,
            "flights_entirely_constant": flights_const,
            "isolated_spikes_per_hour": spikes / hours if hours > 0 else np.nan,
            "pchange_by_subframe_pos": ";".join(f"{v:.3f}" for v in pcm),
            "values_union": ";".join(f"{v:g}" for v in union_vals[:20]),
        }
        out.append(rec)
    out.sort(key=lambda r: (-r["rate_hz"], r["param"]))
    keys = list(out[0].keys())
    with open(os.path.join(res, "param_table.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(out)
    print(len(out), "parameters written")
    print(collections.Counter(r["rate_hz"] for r in out))
    print(collections.Counter(r["type"] for r in out))


if __name__ == "__main__":
    main(sys.argv[1])
