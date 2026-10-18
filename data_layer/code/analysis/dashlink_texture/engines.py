"""Four-engine natural experiment, cross-sensor residual relations, corrected-parameter collapse.

Runs on ALL eligible flights (eligible_flights.csv from sample_flights.py).
Per steady window (common.regime_windows) and engine group g in N1,N2,EGT,FF,OIP,OIT,VIB,PLA:
  offsets o_i = mean_i - mean over the 4 engines            (persistent per-unit bias)
  SG-30s residual covariance C (4x4):
     common-mode variance  c  = mean off-diagonal C_ij
     independent variance  v_i = C_ii - mean_{j!=i} C_ij     (Grubbs-type, model r_i = s + e_i)
Ground-idle windows are used only when all four engines pass common.engine_ok.
Cross-sensor (cruise and climb windows): per engine zero-lag correlation of SG residuals among
N1, N2, FF, EGT, and lag (s) of the cross-correlation peak (positive = second lags first).
Corrected parameters (all airborne quasi-steady 30-s blocks: every PLA range<=1 deg, every N1
range<=1 %): theta = (TAT+273.15)/288.15, delta = PT/1013.25;
   N1c = N1/sqrt(theta), N2c = N2/sqrt(theta), FFc = FF/(delta*sqrt(theta)), EGTc = (EGT+273.15)/theta.

Usage: python -I engines.py <mat_dir> <results_dir> <fig_dir> [n_workers]
"""
import os
import sys
import csv
import json
import collections
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import load_flight, parse_fname  # noqa: E402
from common import (read_csv, load_lsb, load_sentinels, regime_windows, engine_ok, segment, clean,  # noqa: E402
                    sg_residual, per_second)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

GROUPS = ["N1", "N2", "EGT", "FF", "OIP", "OIT", "VIB", "PLA"]
XS = ["N1", "N2", "FF", "EGT"]
LSB = SENT = None


def init(res):
    global LSB, SENT
    LSB = load_lsb(res)
    SENT = load_sentinels(res)


def xlag(a, b, rate, maxlag_s=8.0):
    a = a - a.mean()
    b = b - b.mean()
    n = a.size
    if np.std(a) == 0 or np.std(b) == 0:
        return np.nan, np.nan
    L = int(maxlag_s * rate)
    lags = np.arange(-L, L + 1)
    c = np.array([np.dot(a[max(0, -l):n - max(0, l)], b[max(0, l):n - max(0, -l)]) for l in lags]) / (n * a.std() * b.std())
    k = int(np.argmax(np.abs(c)))
    return lags[k] / rate, float(c[k])


def per_flight(args):
    path, res = args
    if LSB is None:
        init(res)
    F = load_flight(path)
    fn = os.path.basename(path)
    meta = parse_fname(path)
    wins = regime_windows(F)
    rows, xrows = [], []
    for reg, wl in wins.items():
        for (t0, t1) in wl:
            alt = float(np.mean(segment(F, "ALT", t0, t1)[0]))
            mach = float(np.mean(segment(F, "MACH", t0, t1)[0]))
            if reg == "ground_idle" and not all(engine_ok(F, e, t0, t1, reg) for e in range(1, 5)):
                continue
            resid = {}
            for g in GROUPS:
                X, R = [], []
                for i in range(1, 5):
                    nm = f"{g}_{i}"
                    x, rate = segment(F, nm, t0, t1)
                    x, _ = clean(x, SENT.get(nm, []), LSB[nm])
                    X.append(x)
                    R.append(sg_residual(x, rate))
                X, R = np.vstack(X), np.vstack(R)
                m = X.mean(1)
                C = np.cov(R)
                off = C[~np.eye(4, dtype=bool)].reshape(4, 3)
                cm = float(off.mean())
                indep = np.diag(C) - off.mean(1)
                sd = np.sqrt(np.diag(C))
                with np.errstate(invalid="ignore", divide="ignore"):
                    corr = C / np.outer(sd, sd)
                rec = {"file": fn, "date": meta.get("datestr"), "regime": reg, "t0": t0, "group": g, "ALT": alt,
                       "MACH": mach, "lsb": LSB[f"{g}_1"], "mean4": float(m.mean()), "common_var": cm,
                       "mean_var": float(np.mean(np.diag(C))),
                       "mean_offdiag_corr": float(np.nanmean(corr[~np.eye(4, dtype=bool)]))}
                for i in range(4):
                    rec[f"mean_{i + 1}"] = float(m[i])
                    rec[f"off_{i + 1}"] = float(m[i] - m.mean())
                    rec[f"indep_var_{i + 1}"] = float(indep[i])
                    rec[f"var_{i + 1}"] = float(C[i, i])
                rows.append(rec)
                resid[g] = (R, rate)
            if reg in ("cruise", "climb"):
                for e in range(4):
                    for a in range(len(XS)):
                        for b in range(a + 1, len(XS)):
                            ra, rate = resid[XS[a]][0][e], resid[XS[a]][1]
                            rb = resid[XS[b]][0][e]
                            with np.errstate(invalid="ignore", divide="ignore"):
                                c0 = float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else np.nan
                            lag, cpk = xlag(ra, rb, rate)
                            xrows.append({"file": fn, "regime": reg, "engine": e + 1, "pair": f"{XS[a]}-{XS[b]}",
                                          "corr0": c0, "lag_s": lag, "corr_peak": cpk})
    # corrected-parameter blocks (30 s) over the whole airborne flight
    wow = F["WOW"].x
    n = wow.size
    blocks = []
    pla = np.vstack([per_second(F, f"PLA_{i}")[:n] for i in range(1, 5)])
    sec = {k: per_second(F, k)[:n] for k in ["TAT", "PT", "ALT", "MACH", "CAS"]}
    eng = {f"{g}_{i}": per_second(F, f"{g}_{i}")[:n] for g in ["N1", "N2", "FF", "EGT"] for i in range(1, 5)}
    for b in range(n // 30):
        s = slice(b * 30, (b + 1) * 30)
        if not np.all(wow[s] == 1):
            continue
        if np.ptp(pla[:, s], axis=1).max() > 1 or max(np.ptp(eng[f"N1_{i}"][s]) for i in range(1, 5)) > 1:
            continue
        rec = {"file": fn, "phase": int(np.median(F["PH"].x[s]))}
        for k, v in sec.items():
            rec[k] = float(np.mean(v[s]))
        for k, v in eng.items():
            rec[k] = float(np.mean(v[s]))
        blocks.append(rec)
    return rows, xrows, blocks, fn


def write(path, rows):
    keys = list(rows[0].keys())
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def fit_r(x, y, deg=2):
    p = np.polyfit(x, y, deg)
    r = y - np.polyval(p, x)
    return p, r, 1 - r.var() / y.var()


def main(mat_dir, res, figdir, nw=8):
    elig = [r["file"] for r in read_csv(os.path.join(res, "eligible_flights.csv"))]
    rows, xrows, blocks = [], [], []
    with Pool(nw, initializer=init, initargs=(res,)) as pool:
        for r, x, b, fn in pool.imap(per_flight, [(os.path.join(mat_dir, f), res) for f in elig], chunksize=2):
            rows.extend(r)
            xrows.extend(x)
            blocks.extend(b)
    write(os.path.join(res, "engines_windows.csv"), rows)
    write(os.path.join(res, "engines_crosssensor.csv"), xrows)
    write(os.path.join(res, "engines_corrected_blocks.csv"), blocks)
    summary = {"n_flights": len(elig)}
    # ----- offsets & variance decomposition
    S = []
    for reg in ["ground_idle", "climb", "cruise"]:
        for g in GROUPS:
            rr = [r for r in rows if r["regime"] == reg and r["group"] == g]
            if not rr:
                continue
            L = rr[0]["lsb"]
            offs = np.array([[r[f"off_{i}"] for i in range(1, 5)] for r in rr])
            files = np.array([r["file"] for r in rr])
            # per-flight median offsets -> between-flight spread
            uf = sorted(set(files))
            fmed = np.array([np.median(offs[files == f], axis=0) for f in uf])
            within = []
            for f in uf:
                o = offs[files == f]
                if len(o) >= 2:
                    within.append(o.std(0, ddof=1))
            within = np.nanmean(within, axis=0) if within else np.full(4, np.nan)
            mv = np.array([r["mean_var"] for r in rr])
            cv = np.array([r["common_var"] for r in rr])
            iv = np.array([[r[f"indep_var_{i}"] for i in range(1, 5)] for r in rr])
            rec = {"regime": reg, "group": g, "lsb": L, "n_windows": len(rr), "n_flights": len(uf),
                   "mean_level": float(np.median([r["mean4"] for r in rr]))}
            for i in range(4):
                rec[f"offset_med_{i + 1}"] = float(np.median(offs[:, i]))
                rec[f"offset_med_lsb_{i + 1}"] = float(np.median(offs[:, i]) / L)
                rec[f"offset_between_flight_sd_{i + 1}"] = float(np.std(fmed[:, i], ddof=1)) if len(uf) > 1 else np.nan
                rec[f"offset_within_flight_sd_{i + 1}"] = float(within[i])
                rec[f"indep_sd_lsb_med_{i + 1}"] = float(np.sqrt(max(np.median(iv[:, i]), 0)) / L)
            rec["offset_spread_sd_across_units_lsb"] = float(np.std(np.median(offs, 0), ddof=1) / L)
            rec["resid_sd_lsb_med"] = float(np.sqrt(np.median(mv)) / L)
            rec["common_mode_fraction_med"] = float(np.median(np.where(mv > 0, cv / mv, np.nan)[mv > 0])) if (mv > 0).any() else np.nan
            rec["mean_offdiag_corr_med"] = float(np.nanmedian([r["mean_offdiag_corr"] for r in rr]))
            S.append(rec)
    write(os.path.join(res, "engines_summary.csv"), S)
    # ----- offset vs level (scale-type vs bias-type)
    lv = []
    for g in ["N1", "N2", "EGT", "FF"]:
        rr = [r for r in rows if r["group"] == g and r["regime"] in ("cruise", "climb", "ground_idle")]
        lev = np.array([r["mean4"] for r in rr])
        for i in range(1, 5):
            o = np.array([r[f"off_{i}"] for r in rr])
            p = np.polyfit(lev, o, 1)
            lv.append({"group": g, "engine": i, "slope_offset_per_unit_level": float(p[0]), "intercept": float(p[1]),
                       "corr": float(np.corrcoef(lev, o)[0, 1])})
    write(os.path.join(res, "engines_offset_vs_level.csv"), lv)
    # ----- drift of per-flight cruise offsets over calendar time
    dr = []
    for g in ["N1", "N2", "EGT", "FF", "OIP", "OIT"]:
        rr = [r for r in rows if r["group"] == g and r["regime"] == "cruise"]
        files = sorted(set(r["file"] for r in rr))
        days = []
        fo = []
        for f in files:
            m = parse_fname(f)
            d = np.datetime64(f"{m['year']:04d}-{m['month']:02d}-{m['day']:02d}")
            days.append((d - np.datetime64("2001-01-01")).astype(int))
            fo.append(np.median([[r[f"off_{i}"] for i in range(1, 5)] for r in rr if r["file"] == f], axis=0))
        days, fo = np.array(days, float), np.array(fo)
        for i in range(4):
            p = np.polyfit(days, fo[:, i], 1)
            half = days < np.median(days)
            dr.append({"group": g, "engine": i + 1, "n_flights": len(files),
                       "slope_per_30d": float(p[0] * 30), "first_half_med": float(np.median(fo[half, i])),
                       "second_half_med": float(np.median(fo[~half, i])),
                       "lag1_autocorr_consecutive_flights": float(np.corrcoef(fo[:-1, i], fo[1:, i])[0, 1])})
    write(os.path.join(res, "engines_offset_drift.csv"), dr)
    # ----- cross-sensor summary
    xs = []
    for reg in ["cruise", "climb"]:
        for pair in sorted(set(r["pair"] for r in xrows)):
            rr = [r for r in xrows if r["regime"] == reg and r["pair"] == pair]
            c0 = np.array([r["corr0"] for r in rr], float)
            lg = np.array([r["lag_s"] for r in rr], float)
            cp = np.array([r["corr_peak"] for r in rr], float)
            strong = np.abs(cp) > 0.3
            xs.append({"regime": reg, "pair": pair, "n": len(rr), "corr0_med": float(np.nanmedian(c0)),
                       "corr0_p25": float(np.nanpercentile(c0, 25)), "corr0_p75": float(np.nanpercentile(c0, 75)),
                       "lag_s_med_when_|peak|>0.3": float(np.nanmedian(lg[strong])) if strong.any() else np.nan,
                       "frac_|peak|>0.3": float(np.mean(strong))})
    write(os.path.join(res, "engines_crosssensor_summary.csv"), xs)
    # ----- corrected-parameter collapse
    B = blocks
    alt = np.array([b["ALT"] for b in B])
    theta = (np.array([b["TAT"] for b in B]) + 273.15) / 288.15
    delta = np.array([b["PT"] for b in B]) / 1013.25
    coll = []
    figdata = {}
    for e in range(1, 5):
        n1 = np.array([b[f"N1_{e}"] for b in B])
        n2 = np.array([b[f"N2_{e}"] for b in B])
        ff = np.array([b[f"FF_{e}"] for b in B])
        egt = np.array([b[f"EGT_{e}"] for b in B])
        ok = (n1 > 20) & (ff > 0) & (delta > 0.1)
        n1c = n1 / np.sqrt(theta)
        cases = {"FF~N1": (n1, ff), "FFc~N1c": (n1c, ff / (delta * np.sqrt(theta))),
                 "EGT~N1": (n1, egt + 273.15), "EGTc~N1c": (n1c, (egt + 273.15) / theta),
                 "N2~N1": (n1, n2), "N2c~N1c": (n1c, n2 / np.sqrt(theta))}
        for name, (x, y) in cases.items():
            p, r, r2 = fit_r(x[ok], y[ok])
            ra = np.polyfit(alt[ok], r, 1)
            coll.append({"engine": e, "relation": name, "n_blocks": int(ok.sum()), "R2_quadratic": float(r2),
                         "resid_sd": float(r.std()), "resid_sd_rel_to_mean_pct": float(100 * r.std() / y[ok].mean()),
                         "resid_slope_per_10kft": float(ra[0] * 1e4),
                         "resid_corr_with_alt": float(np.corrcoef(alt[ok], r)[0, 1])})
            if e == 1:
                figdata[name] = (x[ok], y[ok], alt[ok])
    write(os.path.join(res, "engines_corrected_collapse.csv"), coll)
    json.dump(summary, open(os.path.join(res, "engines_meta.json"), "w"))
    figures(rows, S, figdata, figdir)
    print("windows", len(rows), "xrows", len(xrows), "blocks", len(blocks))


def figures(rows, S, figdata, figdir):
    plt.rcParams.update({"font.size": 8, "figure.dpi": 130})
    # offsets per engine across flights (cruise), by group
    fig, axs = plt.subplots(2, 3, figsize=(12, 6))
    for ax, g in zip(axs.flat, ["N1", "N2", "EGT", "FF", "OIP", "OIT"]):
        rr = [r for r in rows if r["group"] == g and r["regime"] == "cruise"]
        files = sorted(set(r["file"] for r in rr))
        for i, c in zip(range(1, 5), ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]):
            y = [np.median([r[f"off_{i}"] for r in rr if r["file"] == f]) for f in files]
            ax.plot(range(len(files)), y, ".", ms=2.5, color=c, label=f"engine {i}")
        ax.set_title(f"{g}: engine minus 4-engine mean, cruise (per-flight median)", fontsize=7)
        ax.set_xlabel("flight index (chronological)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=6, markerscale=3)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_engine_offsets_over_flights.png"))
    plt.close(fig)
    # corrected collapse
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.5))
    for ax, name in zip(axs.flat, ["FF~N1", "EGT~N1", "N2~N1", "FFc~N1c", "EGTc~N1c", "N2c~N1c"]):
        x, y, a = figdata[name]
        sc = ax.scatter(x, y, c=a, s=1.5, cmap="viridis", rasterized=True)
        ax.set_title(name + " (engine 1)", fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("Raw (top) vs theta/delta-corrected (bottom) engine relations; airborne quasi-steady 30-s blocks, all eligible flights", fontsize=8)
    fig.colorbar(sc, ax=axs, label="pressure altitude (ft)", shrink=0.8)
    fig.savefig(os.path.join(figdir, "fig_corrected_parameter_collapse.png"))
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
