"""Residual texture in steady segments + heteroscedasticity, on the sampled flights.

Steady regimes: see common.regime_windows docstring (cruise 300 s with autothrottle trim
allowed, climb 120 s, ground idle 120 s with per-engine running/steady check).
Detrending: Savitzky-Golay, 30-s window, polynomial order 2 (residual = x - SG(x)).
Sentinel dropouts (from dropouts.py) are replaced by linear interpolation before analysis.

Usage: python -I texture.py <mat_dir> <results_dir> <fig_dir>
Writes texture_windows.csv, texture_summary.csv, hetero_blocks.csv, hetero_summary_phase.csv,
       hetero_summary_n1.csv, texture_spectra.npz; figures fig_*.png in fig_dir
"""
import os
import sys
import csv
import collections

import numpy as np
from scipy.stats import kurtosis, skew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dlio import load_flight, PHASES  # noqa: E402
from common import (ENG, AIR, engine_ok, read_csv, load_lsb, load_sentinels, regime_windows, segment, clean,  # noqa: E402
                    sg_residual, acf, decorr_time, allan_dev, psd, per_second, unwrap_deg, ANGLE_WRAP)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TARGETS = ENG + AIR
HET = ["N1_1", "N2_1", "EGT_1", "FF_1", "OIP_1", "OIT_1", "VIB_1", "ALT", "CAS", "MACH", "TAT",
       "AOA1", "PTCH", "ROLL", "VRTG", "LATG", "LONG", "PT", "PS", "FPAC", "IVV"]


def window_metrics(x, rate, lsb):
    r = sg_residual(x, rate)
    n = x.size
    sd = float(np.std(r))
    mad = float(1.4826 * np.median(np.abs(r - np.median(r))))
    dx = np.diff(x) / lsb
    adx = np.abs(np.round(dx))
    med = np.median(x)
    ac = acf(r, int(min(n // 4, 60 * rate)))
    lin = x - np.polyval(np.polyfit(np.arange(n), x, 1), np.arange(n))
    acl = acf(lin, int(n // 2))
    m = {
        "n": n, "mean": float(np.mean(x)), "sigma": sd, "sigma_lsb": sd / lsb, "mad_sigma_lsb": mad / lsb,
        "frac_resid_within_half_lsb": float(np.mean(np.abs(r) <= 0.5 * lsb)),
        "frac_resid_within_1lsb": float(np.mean(np.abs(r) <= lsb * 1.0001)),
        "frac_raw_within_1lsb_of_median": float(np.mean(np.abs(x - med) <= lsb * 1.0001)),
        "n_distinct": int(np.unique(x).size), "range_lsb": float(np.ptp(x) / lsb),
        "p_change": float(np.mean(adx > 0)),
        "dx0": float(np.mean(adx == 0)), "dx1": float(np.mean(adx == 1)), "dx2": float(np.mean(adx == 2)),
        "dx3p": float(np.mean(adx >= 3)),
        "kurt_excess": float(kurtosis(r)) if sd > 0 else np.nan,
        "skew": float(skew(r)) if sd > 0 else np.nan,
        "frac_beyond_4sd": float(np.mean(np.abs(r) > 4 * sd)) if sd > 0 else np.nan,
        "lag1_acf": float(ac[1]) if ac.size > 1 else np.nan,
        "tau_e_resid_s": decorr_time(ac, rate),
        "lin_sigma_lsb": float(np.std(lin) / lsb),
        "tau_e_lin_s": decorr_time(acl, rate),
    }
    return m, r, ac


def het_blocks(F, name, lsb, sentinels, B=30):
    """Per 30-s block: high-frequency noise sigma from second differences, p_change."""
    p = F[name]
    x = p.x.astype(float)
    if name in ANGLE_WRAP:
        x = unwrap_deg(x)
    x, _ = clean(x, sentinels.get(name, []), lsb)
    k = int(p.rate * B)
    nb = x.size // k
    ph = F["PH"].x
    n1 = np.mean([per_second(F, f"N1_{i}") for i in range(1, 5)], axis=0)
    # validity gating: engine params only while that engine runs (N2>=40 %); airspeed-derived
    # params only while CAS>=60 kt (they read a held 0 below that)
    gate = None
    if name in ENG:
        gate = per_second(F, f"N2_{name[-1]}") >= 40
    elif name in ("CAS", "MACH", "TAS", "PI", "AOAC"):
        gate = per_second(F, "CAS") >= 60
    rows = []
    for b in range(nb):
        if gate is not None and not np.all(gate[b * B:(b + 1) * B]):
            continue
        seg = x[b * k:(b + 1) * k]
        d2 = np.diff(seg, 2)
        if d2.size < 4:
            continue
        lo, hi = np.percentile(d2, [0.5, 99.5])
        d2t = d2[(d2 >= lo) & (d2 <= hi)]
        s = np.sqrt(np.mean(d2t ** 2) / 6.0)
        phb = ph[b * B:(b + 1) * B]
        vals, cnt = np.unique(phb, return_counts=True)
        rows.append({"param": name, "phase": int(vals[np.argmax(cnt)]), "n1_mean": float(np.mean(n1[b * B:(b + 1) * B])),
                     "sigma_hf_lsb": s / lsb, "p_change": float(np.mean(np.diff(seg) != 0)),
                     "sg_sigma_lsb": float(np.std(sg_residual(seg, p.rate)) / lsb)})
    return rows


def main(mat_dir, res, figdir):
    os.makedirs(figdir, exist_ok=True)
    lsb = load_lsb(res)
    sent = load_sentinels(res)
    sample = [r["file"] for r in read_csv(os.path.join(res, "sample_flights.csv"))]
    W = []
    spectra = collections.defaultdict(list)
    acfs = collections.defaultdict(list)
    avars = collections.defaultdict(list)
    pooled = collections.defaultdict(list)
    hrows = []
    example = None
    for fn in sample:
        F = load_flight(os.path.join(mat_dir, fn))
        wins = regime_windows(F)
        for reg, wl in wins.items():
            for (t0, t1) in wl:
                ctx = {"file": fn, "regime": reg, "t0": t0, "t1": t1,
                       "ALT": float(np.mean(segment(F, "ALT", t0, t1)[0])),
                       "MACH": float(np.mean(segment(F, "MACH", t0, t1)[0])),
                       "TAT": float(np.mean(segment(F, "TAT", t0, t1)[0])),
                       "N1mean": float(np.mean([np.mean(segment(F, f"N1_{i}", t0, t1)[0]) for i in range(1, 5)])),
                       "ATEN": float(np.mean(segment(F, "ATEN", t0, t1)[0]))}
                if example is None and reg == "cruise":
                    example = (fn, t0, t1)
                for name in TARGETS:
                    L = lsb.get(name, np.nan)
                    if not np.isfinite(L) or L <= 0:
                        continue
                    if name in ENG and not engine_ok(F, int(name[-1]), t0, t1, reg):
                        continue
                    x, rate = segment(F, name, t0, t1)
                    x, nrep = clean(x, sent.get(name, []), L)
                    m, r, ac = window_metrics(x, rate, L)
                    m.update(ctx)
                    m.update({"param": name, "rate": rate, "lsb": L, "n_sentinel_replaced": nrep})
                    W.append(m)
                    key = (name, reg)
                    f, pxx = psd(r, rate)
                    spectra[key].append((f, pxx / L ** 2))
                    acfs[key].append(ac)
                    tau, ad = allan_dev(x, rate)
                    avars[key].append((tau, (ad / L) ** 2))
                    if m["sigma"] > 0:
                        pooled[key].append(r / m["sigma"])
        for name in HET:
            hrows.extend(dict(h, file=fn) for h in het_blocks(F, name, lsb[name], sent))
        print(fn, {k: len(v) for k, v in wins.items()}, flush=True)

    # ---------------- write per-window table
    keys = list(W[0].keys())
    with open(os.path.join(res, "texture_windows.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(W)
    # ---------------- summary per (param, regime)
    by = collections.defaultdict(list)
    for m in W:
        by[(m["param"], m["regime"])].append(m)
    S = []
    for (name, reg), ms in sorted(by.items()):
        def med(k):
            v = np.array([q[k] for q in ms], float)
            return float(np.nanmedian(v)) if np.isfinite(v).any() else np.nan

        def pct(k, p):
            v = np.array([q[k] for q in ms], float)
            return float(np.nanpercentile(v, p)) if np.isfinite(v).any() else np.nan
        pr = np.concatenate(pooled[(name, reg)]) if pooled[(name, reg)] else np.array([])
        sig = med("sigma_lsb")
        tog = med("frac_resid_within_1lsb")
        pch = med("p_change")
        lag1 = med("lag1_acf")
        dx1 = np.mean([q["dx1"] for q in ms])
        dx2p = np.mean([q["dx2"] + q["dx3p"] for q in ms])
        if pch < 0.05:
            cls = "held/rarely-updating (>95% repeats)"
        elif sig <= 0.6 and dx2p <= 0.05:
            cls = "quantisation toggling (<=1 LSB)"
        elif sig <= 2:
            cls = "few-LSB (1-2 LSB) mixed"
        elif lag1 > 0.5:
            cls = "multi-LSB coloured"
        else:
            cls = "multi-LSB white-ish"
        S.append({"param": name, "regime": reg, "n_windows": len(ms), "n_flights": len(set(q["file"] for q in ms)),
                  "rate": ms[0]["rate"], "lsb": ms[0]["lsb"],
                  "sigma_lsb_med": sig, "sigma_lsb_p25": pct("sigma_lsb", 25), "sigma_lsb_p75": pct("sigma_lsb", 75),
                  "sigma_phys_med": med("sigma"),
                  "frac_resid_within_1lsb_med": tog, "frac_raw_within_1lsb_of_median_med": med("frac_raw_within_1lsb_of_median"),
                  "n_distinct_med": med("n_distinct"), "p_change_med": pch,
                  "dx0_mean": np.mean([q["dx0"] for q in ms]), "dx1_mean": dx1, "dx2plus_mean": dx2p,
                  "kurt_excess_med": med("kurt_excess"), "skew_med": med("skew"),
                  "pooled_std_kurt_excess": float(kurtosis(pr)) if pr.size > 10 else np.nan,
                  "pooled_frac_beyond_4sd": float(np.mean(np.abs(pr) > 4)) if pr.size else np.nan,
                  "lag1_acf_med": lag1, "tau_e_resid_s_med": med("tau_e_resid_s"),
                  "lin_sigma_lsb_med": med("lin_sigma_lsb"), "tau_e_lin_s_med": med("tau_e_lin_s"),
                  "n_sentinel_replaced_total": int(sum(q["n_sentinel_replaced"] for q in ms)),
                  "texture_class": cls})
    with open(os.path.join(res, "texture_summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(S[0].keys()))
        w.writeheader()
        w.writerows(S)
    # ---------------- heteroscedasticity
    with open(os.path.join(res, "hetero_blocks.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hrows[0].keys()))
        w.writeheader()
        w.writerows(hrows)
    HP, HN = [], []
    for name in HET:
        hs = [h for h in hrows if h["param"] == name]
        for ph in range(0, 8):
            v = np.array([h["sigma_hf_lsb"] for h in hs if h["phase"] == ph])
            pc = np.array([h["p_change"] for h in hs if h["phase"] == ph])
            if v.size >= 5:
                HP.append({"param": name, "phase": ph, "phase_name": PHASES[ph], "n_blocks": v.size,
                           "sigma_hf_lsb_med": float(np.median(v)), "sigma_hf_lsb_p25": float(np.percentile(v, 25)),
                           "sigma_hf_lsb_p75": float(np.percentile(v, 75)), "p_change_med": float(np.median(pc))})
        if name.split("_")[0] in ("N1", "N2", "EGT", "FF", "OIP", "OIT", "VIB"):
            edges = [0, 30, 50, 60, 70, 80, 85, 90, 100]
            for a, b in zip(edges[:-1], edges[1:]):
                sel = [h for h in hs if a <= h["n1_mean"] < b and h["phase"] in (1, 2, 4, 5, 6)]
                v = np.array([h["sigma_hf_lsb"] for h in sel])
                if v.size >= 5:
                    HN.append({"param": name, "n1_bin": f"{a}-{b}", "n_blocks": v.size,
                               "sigma_hf_lsb_med": float(np.median(v)), "sigma_hf_lsb_p75": float(np.percentile(v, 75)),
                               "p_change_med": float(np.median([h["p_change"] for h in sel]))})
    for path, rows in (("hetero_summary_phase.csv", HP), ("hetero_summary_n1.csv", HN)):
        with open(os.path.join(res, path), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    # ---------------- spectra / acf / allan means
    npz = {}
    for key, lst in spectra.items():
        nf = min(len(f) for f, _ in lst)
        npz[f"psd|{key[0]}|{key[1]}|f"] = lst[0][0][:nf]
        npz[f"psd|{key[0]}|{key[1]}|p"] = np.mean([p[:nf] for _, p in lst if len(p) >= nf], axis=0)
    for key, lst in acfs.items():
        nl = min(len(a) for a in lst)
        npz[f"acf|{key[0]}|{key[1]}"] = np.nanmean([a[:nl] for a in lst], axis=0)
    for key, lst in avars.items():
        nt = min(len(t) for t, _ in lst)
        npz[f"adev|{key[0]}|{key[1]}|tau"] = lst[0][0][:nt]
        npz[f"adev|{key[0]}|{key[1]}|adev_lsb"] = np.sqrt(np.mean([a[:nt] for _, a in lst], axis=0))
    np.savez_compressed(os.path.join(res, "texture_spectra.npz"), **npz)
    # narrow-band spectral lines (cruise): bins > 3x the running median over +-0.5 Hz, f > 0.5 Hz
    lines = []
    for nm in ["VRTG", "LATG", "LONG", "FPAC", "BLAC", "CTAC", "PTCH", "ROLL", "AOA1", "AOA2", "IVV", "N1_1", "FF_1"]:
        kf, kp = f"psd|{nm}|cruise|f", f"psd|{nm}|cruise|p"
        if kf not in npz:
            continue
        f, p = npz[kf], npz[kp]
        df = f[1] - f[0]
        h = max(int(0.5 / df), 2)
        for i in range(len(f)):
            if f[i] <= 0.5:
                continue
            loc = np.median(p[max(0, i - h):i + h + 1])
            if p[i] > 3 * loc and p[i] == p[max(0, i - 2):i + 3].max():
                lines.append({"param": nm, "freq_hz": float(f[i]), "peak_over_local_median": float(p[i] / loc),
                              "nyquist_hz": float(f[-1])})
    if lines:
        with open(os.path.join(res, "texture_spectral_lines.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(lines[0].keys()))
            w.writeheader()
            w.writerows(lines)
    make_figures(mat_dir, res, figdir, S, npz, HP, example, lsb, sent)
    print("windows", len(W), "summary rows", len(S))


def make_figures(mat_dir, res, figdir, S, npz, HP, example, lsb, sent):
    plt.rcParams.update({"font.size": 8, "figure.dpi": 130})
    # 1. raw quantised traces from one cruise window
    fn, t0, t1 = example
    F = load_flight(os.path.join(mat_dir, fn))
    names = ["N1_1", "N2_1", "EGT_1", "FF_1", "OIP_1", "OIT_1", "VIB_1", "ALT", "CAS", "MACH", "TAT", "AOA1",
             "PTCH", "VRTG", "LATG", "PT"]
    fig, axs = plt.subplots(4, 4, figsize=(11, 8))
    for ax, nm in zip(axs.flat, names):
        x, rate = segment(F, nm, t0, t0 + 120)
        t = np.arange(x.size) / rate
        ax.step(t, x, where="post", lw=0.8, color="#1f4e79")
        ax.set_title(f"{nm} ({F[nm].units or '-'}; {rate:g} Hz; LSB={lsb[nm]:.4g})", fontsize=7)
        ax.set_xlabel("s", fontsize=7)
        ax.grid(alpha=0.3)
    fig.suptitle(f"Raw recorded values, 120 s of steady cruise ({fn}, t={t0} s). Sentinel dropouts NOT removed.", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_raw_cruise_quantisation.png"))
    plt.close(fig)
    # 2. sigma/LSB dot plot
    params = [p for p in ENG[::1] if p.endswith("_1")] + ["ALT", "BAL1", "CAS", "MACH", "TAS", "TAT", "SAT", "AOA1",
                                                         "AOAC", "PTCH", "ROLL", "VRTG", "LATG", "LONG", "FPAC",
                                                         "BLAC", "CTAC", "TH", "IVV", "ALTR", "PT", "PS", "PI", "GS",
                                                         "N1C", "PLA_1", "FQTY_1", "WS"]
    fig, ax = plt.subplots(figsize=(11, 4))
    cols = {"cruise": "#1f77b4", "climb": "#d62728", "ground_idle": "#2ca02c"}
    for j, reg in enumerate(["ground_idle", "climb", "cruise"]):
        xs, ys, lo, hi = [], [], [], []
        for i, p in enumerate(params):
            r = [s for s in S if s["param"] == p and s["regime"] == reg]
            if r:
                xs.append(i + (j - 1) * 0.22)
                ys.append(max(r[0]["sigma_lsb_med"], 1e-3))
                lo.append(max(r[0]["sigma_lsb_p25"], 1e-3))
                hi.append(max(r[0]["sigma_lsb_p75"], 1e-3))
        ys, lo, hi = map(np.array, (ys, lo, hi))
        ax.errorbar(xs, ys, yerr=[ys - lo, hi - ys], fmt="o", ms=3, color=cols[reg], label=reg, lw=0.8)
    ax.axhline(1 / np.sqrt(12), ls="--", color="k", lw=0.8, label="uniform quantisation LSB/sqrt(12)")
    ax.axhline(1, ls=":", color="k", lw=0.8, label="1 LSB")
    ax.set_yscale("log")
    ax.set_xticks(range(len(params)))
    ax.set_xticklabels(params, rotation=70)
    ax.set_ylabel("residual sigma / LSB (median, IQR)")
    ax.set_title("Residual standard deviation in steady segments, in units of the recorded LSB (SG 30 s, order 2 detrend)")
    ax.legend(fontsize=7, ncol=5)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_sigma_over_lsb.png"))
    plt.close(fig)
    # 3. PSDs
    groups = [("Engine (cruise)", ["N1_1", "N2_1", "EGT_1", "FF_1", "OIP_1", "OIT_1"], "cruise"),
              ("Air data (cruise)", ["ALT", "CAS", "MACH", "TAT", "PT", "PS"], "cruise"),
              ("Inertial/attitude (cruise)", ["VRTG", "LATG", "LONG", "FPAC", "PTCH", "ROLL", "AOA1"], "cruise"),
              ("Engine (ground idle)", ["N1_1", "N2_1", "EGT_1", "FF_1", "OIP_1", "OIT_1"], "ground_idle")]
    fig, axs = plt.subplots(1, 4, figsize=(13, 3.6))
    for ax, (title, names, reg) in zip(axs, groups):
        for nm in names:
            kf, kp = f"psd|{nm}|{reg}|f", f"psd|{nm}|{reg}|p"
            if kf in npz:
                f, p = npz[kf], npz[kp]
                ax.loglog(f[1:], p[1:], lw=0.9, label=nm)
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("Hz")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=6)
    axs[0].set_ylabel("PSD of residual (LSB^2/Hz)")
    fig.suptitle("Welch PSD of SG-detrended residuals (64-s segments, averaged over windows); white uniform quantisation of 1 LSB at fs gives 1/(6 fs) LSB^2/Hz", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_residual_psd.png"))
    plt.close(fig)
    # 4. Allan deviation
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, (title, names) in zip(axs, [("Engine, cruise", ["N1_1", "N2_1", "EGT_1", "FF_1", "OIT_1"]),
                                        ("Air data, cruise", ["ALT", "CAS", "MACH", "TAT", "PT", "AOA1"]),
                                        ("Inertial, cruise", ["VRTG", "LATG", "LONG", "FPAC", "PTCH", "ROLL"])]):
        for nm in names:
            k = f"adev|{nm}|cruise|tau"
            if k in npz:
                ax.loglog(npz[k], npz[f"adev|{nm}|cruise|adev_lsb"], "o-", ms=2, lw=0.9, label=nm)
        ax.axhline(1 / np.sqrt(12), ls="--", color="k", lw=0.7)
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("tau (s)")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=6)
    axs[0].set_ylabel("Allan deviation (LSB)")
    fig.suptitle("Overlapping Allan deviation of raw (sentinel-cleaned, not detrended) 300-s cruise windows, rms over windows", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_allan_deviation.png"))
    plt.close(fig)
    # 5. ACF
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, names in zip(axs, [["N1_1", "N2_1", "EGT_1", "FF_1", "OIT_1"], ["ALT", "CAS", "MACH", "TAT", "PT"],
                               ["VRTG", "LATG", "LONG", "PTCH", "ROLL", "AOA1"]]):
        for nm in names:
            k = f"acf|{nm}|cruise"
            if k in npz:
                ac = npz[k]
                rate = [s for s in S if s["param"] == nm][0]["rate"]
                ax.plot(np.arange(ac.size) / rate, ac, lw=0.9, label=nm)
        ax.axhline(np.exp(-1), ls="--", color="k", lw=0.7)
        ax.set_xlim(0, 30)
        ax.set_xlabel("lag (s)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=6)
    axs[0].set_ylabel("ACF of SG residual (cruise)")
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_residual_acf.png"))
    plt.close(fig)
    # 6. heteroscedasticity by phase
    fig, ax = plt.subplots(figsize=(10, 3.8))
    names = ["N1_1", "N2_1", "EGT_1", "FF_1", "OIP_1", "ALT", "CAS", "AOA1", "PTCH", "VRTG", "LATG", "PT"]
    for nm in names:
        rr = [h for h in HP if h["param"] == nm and h["phase"] in range(1, 8)]
        ax.plot([h["phase"] for h in rr], [max(h["sigma_hf_lsb_med"], 1e-3) for h in rr], "o-", ms=3, lw=0.9, label=nm)
    ax.set_xticks(range(1, 8))
    ax.set_xticklabels([PHASES[i] for i in range(1, 8)])
    ax.set_yscale("log")
    ax.set_ylabel("HF noise sigma (2nd-difference estimator) / LSB")
    ax.set_title("Heteroscedasticity by flight phase (30-s blocks, sampled flights)")
    ax.legend(fontsize=6, ncol=4)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(figdir, "fig_hetero_by_phase.png"))
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
