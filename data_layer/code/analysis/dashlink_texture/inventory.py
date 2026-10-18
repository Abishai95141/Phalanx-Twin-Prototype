"""Archive-wide inventory: per-flight recorder checks and per-parameter-per-flight
texture metadata for every .mat file in a directory.

Usage: python -I inventory.py <mat_dir> <results_dir> [n_workers]
Outputs (CSV, one row per flight / per flight x parameter):
  inventory_flights.csv, inventory_params.csv, param_meta.csv
"""
import os
import sys
import csv
import json
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import (list_flights, parse_fname, load_flight, lsb_estimate, run_lengths,  # noqa: E402
                  constant_runs, isolated_spikes, robust_sigma, PHASES)

SYNC_EXPECTED = {"VAR_1107": 0o1107, "VAR_2670": 0o2670, "VAR_5107": 0o5107, "VAR_6670": 0o6670}
RUN_EDGES_S = [1, 5, 10, 30, 60, 120, 300, 600, 1800]


def mode_val(x):
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.nan
    v, c = np.unique(x, return_counts=True)
    return float(v[np.argmax(c)])


def param_stats(p, n_frames):
    x = p.x
    n = x.size
    n_exp = int(round(n_frames * 4 * p.rate))
    fin = np.isfinite(x)
    n_nan = int((~fin).sum())
    nan_runs = run_lengths(~fin)
    r = {"param": p.name, "alpha": p.alpha, "rate": p.rate, "dtype": p.dtype,
         "n": n, "n_expected": n_exp, "n_nan": n_nan,
         "n_nan_runs": int(nan_runs.size), "max_nan_run_s": float(nan_runs.max() / p.rate) if nan_runs.size else 0.0}
    if fin.sum() == 0:
        r.update({"min": np.nan, "max": np.nan})
        return r
    xf = x[fin]
    lsb, grid, nu = lsb_estimate(xf)
    vmin, vmax = float(xf.min()), float(xf.max())
    dx = np.diff(x)
    dxf = dx[np.isfinite(dx)]
    held = float(np.mean(dxf == 0)) if dxf.size else np.nan
    cr = constant_runs(np.where(fin, x, np.nan))  # NaN breaks runs (nan != nan)
    cr_s = cr / p.rate
    frac_in_runs = {f"frac_in_const_run_ge_{e}s": float(cr[cr_s >= e].sum() / n) for e in RUN_EDGES_S}
    sig_d = robust_sigma(dxf) if dxf.size > 3 else np.nan
    thr = max(10 * (lsb if np.isfinite(lsb) else 0), 8 * (sig_d if np.isfinite(sig_d) else 0))
    spikes = isolated_spikes(x, thr) if thr > 0 else 0
    # update-pattern within the 1-s subframe: P(change) by sample index mod rate
    pchg = ""
    k = int(round(p.rate))
    if k >= 2 and dxf.size > 10 * k:
        ch = (np.abs(dx) > 0).astype(float)
        ch[~np.isfinite(dx)] = np.nan
        idx = (np.arange(1, n) % k)
        pchg = ";".join(f"{np.nanmean(ch[idx == j]):.3f}" for j in range(k))
    vals = ""
    if nu <= 32:
        v, c = np.unique(xf, return_counts=True)
        vals = ";".join(f"{a:g}:{b}" for a, b in zip(v, c))
    r.update({"min": vmin, "max": vmax, "mean": float(xf.mean()), "std": float(xf.std()),
              "n_unique": nu, "lsb": lsb, "grid_frac": grid,
              "count_at_min": int(np.sum(xf == vmin)), "count_at_max": int(np.sum(xf == vmax)),
              "frac_held": held, "max_const_run_s": float(cr_s.max()), "n_spikes": spikes,
              "is_integer_valued": bool(np.all(np.mod(xf, 1) == 0)),
              "pchange_by_subframe_pos": pchg, "values": vals, **frac_in_runs})
    return r


def flight_record(path):
    meta = parse_fname(path)
    try:
        F = load_flight(path)
    except Exception as e:  # corrupted file: report, do not crash
        meta["load_error"] = repr(e)
        return meta, [], {}
    nfr = F["FRMC"].x.size if "FRMC" in F else np.nan
    meta["n_params"] = len(F)
    meta["n_frames"] = nfr
    meta["duration_s"] = nfr * 4
    rows = [param_stats(p, nfr) for p in F.values()]
    meta["n_len_mismatch"] = int(sum(r["n"] != r["n_expected"] for r in rows))
    # identity / counters
    for k in ["ACID", "DATE_YEAR", "DATE_MONTH", "DATE_DAY", "ESN_1", "ESN_2", "ESN_3", "ESN_4",
              "EHRS_1", "EHRS_2", "EHRS_3", "EHRS_4", "ECYC_1", "ECYC_2", "ECYC_3", "ECYC_4",
              "DVER_1", "DVER_2"]:
        if k in F:
            meta[k] = mode_val(F[k].x)
            meta[k + "_nuniq"] = int(np.unique(F[k].x[np.isfinite(F[k].x)]).size)
    # phases and air/ground
    if "PH" in F:
        ph = F["PH"].x
        for c, nm in PHASES.items():
            meta[f"t_PH{c}_{nm}_s"] = float(np.sum(ph == c) / F["PH"].rate)
        meta["n_PH_changes"] = int(np.sum(np.diff(ph) != 0))
    if "WOW" in F:
        w = F["WOW"].x
        meta["t_WOW1_s"] = float(np.sum(w == 1) / F["WOW"].rate)
        meta["n_WOW_transitions"] = int(np.sum(np.abs(np.diff(w)) > 0))
    for k in ["ALT", "CAS", "MACH", "N1_1", "RALT"]:
        if k in F:
            meta[f"max_{k}"] = float(np.nanmax(F[k].x))
    # recorder frame counter: expected +4 per 4-s frame, modulo 4096
    if "FRMC" in F:
        fc = F["FRMC"].x
        d = np.mod(np.diff(fc), 4096)
        meta["frmc_n_steps"] = int(d.size)
        meta["frmc_n_irregular"] = int(np.sum(d != 4))
        u, c = np.unique(d[d != 4], return_counts=True)
        meta["frmc_irregular_steps"] = ";".join(f"{a:g}:{b}" for a, b in zip(u, c))
    # sync words
    for k, exp in SYNC_EXPECTED.items():
        if k in F:
            v = F[k].x
            md = mode_val(v)
            meta[f"{k}_mode"] = md
            meta[f"{k}_n_not_mode"] = int(np.sum(v != md))
    # GMT clock (2 Hz)
    if all(k in F for k in ["GMT_HOUR", "GMT_MINUTE", "GMT_SEC"]):
        tg = F["GMT_HOUR"].x * 3600 + F["GMT_MINUTE"].x * 60 + F["GMT_SEC"].x
        dg = np.diff(tg)
        meta["gmt_sec_unique_values"] = int(np.unique(F["GMT_SEC"].x).size)
        nz = dg[dg != 0]
        u, c = np.unique(nz, return_counts=True)
        meta["gmt_step_hist"] = ";".join(f"{a:g}:{b}" for a, b in zip(u[:20], c[:20]))
        meta["gmt_n_backwards"] = int(np.sum(nz < 0))
        span = (tg[-1] - tg[0]) % 86400
        meta["gmt_span_s"] = float(span)
        meta["gmt_start_s"] = float(tg[0])
    pm = {r["param"]: None for r in rows}
    pmeta = {p.name: (p.alpha, p.desc, p.units, p.rate) for p in F.values()}
    for r in rows:
        r["file"] = meta["file"]
    return meta, rows, pmeta


def write_csv(path, rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(mat_dir, res_dir, nw=8):
    os.makedirs(res_dir, exist_ok=True)
    files = list_flights(mat_dir)
    print(f"{len(files)} flights")
    flights, prow, pmeta_all = [], [], {}
    with Pool(nw) as pool:
        for i, (meta, rows, pmeta) in enumerate(pool.imap(flight_record, files, chunksize=4)):
            flights.append(meta)
            prow.extend(rows)
            for k, v in pmeta.items():
                pmeta_all.setdefault(k, set()).add(v)
            if i % 50 == 0:
                print(i, meta.get("file"), flush=True)
    write_csv(os.path.join(res_dir, "inventory_flights.csv"), flights)
    write_csv(os.path.join(res_dir, "inventory_params.csv"), prow)
    pm_rows = []
    for k, s in sorted(pmeta_all.items()):
        for (alpha, desc, units, rate) in sorted(s, key=str):
            pm_rows.append({"param": k, "alpha": alpha, "description": desc, "units": units,
                            "rate_hz": rate, "n_variants": len(s)})
    write_csv(os.path.join(res_dir, "param_meta.csv"), pm_rows)
    print("done")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
