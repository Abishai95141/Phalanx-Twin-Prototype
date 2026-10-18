"""Throttle-step transients: engine response time constants / lags, and hold (stale-sample)
artefacts during fast changes. Runs on ALL eligible flights.

Step detection (per engine, PLA_i at 4 Hz):
  |PLA(t+2 s) - PLA(t)| >= 5 deg; PLA range <= 1 deg over the 10 s before; PLA range <= 1.5 deg
  over [t+3 s, t+30 s]; t0 = first sample after which |PLA - pre-mean| > 0.5 deg.
Response model fitted to N1_i, N2_i, FF_i, EGT_i over [t0-5 s, t0+30 s] (first order plus dead
time): y = y0 for t < t0+d; y0 + D*(1 - exp(-(t-t0-d)/tau)) after. Also non-parametric
t10/t50/t90 = time from t0 to 10/50/90 % of the final change (final = mean of last 5 s).
Stale-sample check: during transients, fraction of consecutive identical samples where the
local (SG 2-s) slope exceeds 2 LSB per sample, and the median length of identical-value runs.

Usage: python -I transients.py <mat_dir> <results_dir> <fig_dir> [n_workers]
"""
import os
import sys
import csv
from multiprocessing import Pool

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import load_flight, run_lengths  # noqa: E402
from common import read_csv, load_lsb  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESP = ["N1", "N2", "FF", "EGT"]
RATE = 4.0


def fopdt(t, y0, D, d, tau):
    s = np.clip(t - d, 0, None)
    return y0 + D * (1 - np.exp(-s / tau))


def find_steps(pla):
    r = RATE
    n = pla.size
    out = []
    i = int(10 * r)
    while i < n - int(31 * r):
        if abs(pla[i + int(2 * r)] - pla[i]) >= 5:
            pre = pla[i - int(10 * r):i + 1]
            post = pla[i + int(3 * r):i + int(30 * r)]
            if np.ptp(pre) <= 1 and np.ptp(post) <= 1.5:
                pm = pre.mean()
                j = i
                while j < i + int(3 * r) and abs(pla[j] - pm) <= 0.5:
                    j += 1
                out.append((j, pm, post.mean()))
                i += int(30 * r)
                continue
        i += 1
    return out


def per_flight(args):
    path, lsb = args
    F = load_flight(path)
    fn = os.path.basename(path)
    rows, stale = [], []
    alt = F["ALT"].x
    mach = F["MACH"].x
    ph = F["PH"].x
    wow = F["WOW"].x
    aten = F["ATEN"].x
    for e in range(1, 5):
        pla = F[f"PLA_{e}"].x
        for (j, pm, qm) in find_steps(pla):
            t0 = j / RATE
            a, b = j - int(5 * RATE), j + int(30 * RATE)
            sec = int(t0)
            ctx = {"file": fn, "engine": e, "t0_s": t0, "dPLA": qm - pm, "PLA_pre": pm, "PLA_post": qm,
                   "dir": "accel" if qm > pm else "decel", "ALT": float(alt[j]), "MACH": float(mach[j]),
                   "PH": int(ph[min(sec, ph.size - 1)]), "airborne": int(wow[min(sec, wow.size - 1)] == 1),
                   "ATEN": int(aten[min(sec, aten.size - 1)])}
            for g in RESP:
                y = F[f"{g}_{e}"].x[a:b].astype(float)
                t = (np.arange(y.size) - int(5 * RATE)) / RATE
                y0 = y[: int(5 * RATE)].mean()
                yf = y[-int(5 * RATE):].mean()
                D = yf - y0
                rec = dict(ctx, resp=g, y0=y0, D=D, lsb=lsb[f"{g}_1"])
                if abs(D) < 5 * lsb[f"{g}_1"]:
                    rec.update(fit="small")
                    rows.append(rec)
                    continue
                frac = (y - y0) / D
                post = t >= 0
                for q in (0.1, 0.5, 0.9):
                    k = np.flatnonzero(post & (frac >= q))
                    rec[f"t{int(q * 100)}_s"] = float(t[k[0]]) if k.size else np.nan
                try:
                    p, _ = curve_fit(fopdt, t, y, p0=[y0, D, 0.5, 2.0],
                                     bounds=([-np.inf, -np.inf, -2, 0.05], [np.inf, np.inf, 10, 60]), maxfev=4000)
                    res = y - fopdt(t, *p)
                    r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
                    over = (np.max(y[post]) - yf) / D if D > 0 else (np.min(y[post]) - yf) / D
                    rec.update(fit="ok", d_s=float(p[2]), tau_s=float(p[3]), R2=float(r2), overshoot_frac=float(over))
                except Exception:
                    rec.update(fit="fail")
                rows.append(rec)
                # stale-sample check
                yy = F[f"{g}_{e}"].x[j:j + int(20 * RATE)].astype(float)
                if yy.size > 9:
                    sl = savgol_filter(yy, 9, 2, deriv=1)
                    fast = np.abs(sl[1:]) > 2 * lsb[f"{g}_1"]
                    same = np.diff(yy) == 0
                    if fast.sum() >= 4:
                        rl = run_lengths(np.r_[False, same & fast])
                        stale.append({"file": fn, "engine": e, "resp": g, "n_fast": int(fast.sum()),
                                      "frac_identical_while_fast": float(np.mean(same[fast])),
                                      "median_identical_run": float(np.median(rl + 1)) if rl.size else 1.0})
    return rows, stale


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


def main(mat_dir, res, figdir, nw=8):
    lsb = load_lsb(res)
    elig = [r["file"] for r in read_csv(os.path.join(res, "eligible_flights.csv"))]
    rows, stale = [], []
    with Pool(nw) as pool:
        for r, s in pool.imap(per_flight, [(os.path.join(mat_dir, f), lsb) for f in elig], chunksize=2):
            rows.extend(r)
            stale.extend(s)
    write(os.path.join(res, "transients_steps.csv"), rows)
    write(os.path.join(res, "transients_stale.csv"), stale)
    # summary by response x direction x altitude band
    S = []
    bands = [(-1000, 5000), (5000, 15000), (15000, 40000)]
    for g in RESP:
        for dr in ("accel", "decel"):
            for lo, hi in bands:
                rr = [r for r in rows if r["resp"] == g and r["dir"] == dr and r.get("fit") == "ok"
                      and lo <= r["ALT"] < hi and r.get("R2", 0) > 0.9 and abs(r["dPLA"]) >= 5]
                if len(rr) < 3:
                    continue
                v = lambda k: np.array([r[k] for r in rr], float)  # noqa: E731
                S.append({"resp": g, "dir": dr, "alt_band_ft": f"{lo}-{hi}", "n_steps": len(rr),
                          "n_flights": len(set(r["file"] for r in rr)),
                          "tau_s_med": float(np.median(v("tau_s"))), "tau_s_p25": float(np.percentile(v("tau_s"), 25)),
                          "tau_s_p75": float(np.percentile(v("tau_s"), 75)),
                          "dead_s_med": float(np.median(v("d_s"))),
                          "t10_s_med": float(np.nanmedian(v("t10_s"))), "t50_s_med": float(np.nanmedian(v("t50_s"))),
                          "t90_s_med": float(np.nanmedian(v("t90_s"))),
                          "overshoot_med": float(np.median(v("overshoot_frac"))),
                          "dPLA_med": float(np.median(v("dPLA"))), "R2_med": float(np.median(v("R2"))),
                          "frac_AT_engaged": float(np.mean(v("ATEN")))})
    write(os.path.join(res, "transients_summary.csv"), S)
    St = []
    for g in RESP:
        ss = [s for s in stale if s["resp"] == g]
        if ss:
            St.append({"resp": g, "n_transients": len(ss),
                       "frac_identical_while_fast_med": float(np.median([s["frac_identical_while_fast"] for s in ss])),
                       "frac_identical_while_fast_p90": float(np.percentile([s["frac_identical_while_fast"] for s in ss], 90)),
                       "median_identical_run_med": float(np.median([s["median_identical_run"] for s in ss]))})
    write(os.path.join(res, "transients_stale_summary.csv"), St)
    # figure: example step and tau vs altitude
    plt.rcParams.update({"font.size": 8, "figure.dpi": 130})
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    ok = [r for r in rows if r.get("fit") == "ok" and r.get("R2", 0) > 0.9]
    for g, c in zip(RESP, ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]):
        for dr, mk in (("accel", "o"), ("decel", "x")):
            rr = [r for r in ok if r["resp"] == g and r["dir"] == dr]
            axs[0].scatter([r["ALT"] for r in rr], [r["tau_s"] for r in rr], s=4, marker=mk, color=c, alpha=0.5,
                           label=f"{g} {dr}")
    axs[0].set_yscale("log")
    axs[0].set_xlabel("pressure altitude at step (ft)")
    axs[0].set_ylabel("fitted time constant tau (s)")
    axs[0].legend(fontsize=6, ncol=2)
    axs[0].grid(alpha=0.3, which="both")
    axs[0].set_title("FOPDT time constant after PLA steps >= 5 deg (R2>0.9)")
    # example: largest airborne decel step
    cand = [r for r in ok if r["resp"] == "N1" and r["airborne"] == 1]
    if cand:
        ex = max(cand, key=lambda r: abs(r["dPLA"]))
        F = load_flight(os.path.join(mat_dir, ex["file"]))
        e = ex["engine"]
        j = int(ex["t0_s"] * RATE)
        a, b = j - 20, j + 120
        t = (np.arange(a, b) - j) / RATE
        ax = axs[1]
        ax2 = ax.twinx()
        for g, c in zip(["PLA", "N1", "N2"], ["k", "#1f77b4", "#ff7f0e"]):
            ax.step(t, F[f"{g}_{e}"].x[a:b], where="post", color=c, lw=0.9, label=g)
        ax2.step(t, F[f"FF_{e}"].x[a:b], where="post", color="#2ca02c", lw=0.9, label="FF (right)")
        ax2.step(t, F[f"EGT_{e}"].x[a:b], where="post", color="#d62728", lw=0.9, label="EGT (right)")
        ax.set_xlabel("s from PLA step")
        ax.set_title(f"Example airborne step, engine {e}, {ex['file']} ALT {ex['ALT']:.0f} ft", fontsize=7)
        ax.legend(fontsize=6, loc="center left")
        ax2.legend(fontsize=6, loc="center right")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_throttle_transients.png"))
    plt.close(fig)
    print("steps rows", len(rows), "stale rows", len(stale))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8)
