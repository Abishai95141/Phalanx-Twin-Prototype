"""Step 11 -- figures for REPORT.md.

Usage: python -I s11_figures.py <results_dir> <figures_dir>
"""
import csv
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402  (sets MPLCONFIGDIR inside the project before matplotlib loads)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"          # categorical slots 1-3 (validated reference palette)
GREY, INK, MUTED = "#8a8985", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "legend.frameon": False})


def ladder(res, fig):
    V = json.load(open(os.path.join(res, "verdicts.json")))
    S = V["singles"]
    levels = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L6p"]
    lab = ["L0", "L1", "L2", "L3", "L4", "L5", "L6\nFULL", "L6′"]
    f, axs = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, (title, pre, g) in zip(axs, [("Engine, arm T1", "sim_T1", "eng"), ("Engine, arm T2 (L6 = L7)", "sim_T2", "eng"),
                                         ("VRTG, arm T1", "sim_T1", "vrtg")]):
        x, yv, lo, hi = [], [], [], []
        for i, lv in enumerate(levels):
            s = S.get(f"{pre}_{lv}_{g}")
            if s:
                x.append(i)
                yv.append(s["auc_x"])
                lo.append(s["ci95"][0])
                hi.append(s["ci95"][1])
        yv, lo, hi = map(np.array, (yv, lo, hi))
        for nm, col, txt in ((f"tail_{g}", S2, "tail baseline (687 vs 652)"), (f"temporal_{g}", S3, "temporal baseline (687 early vs late)")):
            b = S.get(nm)
            if b:
                ax.axhspan(b["ci95"][0], b["ci95"][1], color=col, alpha=0.15, lw=0)
                ax.axhline(b["auc_x"], color=col, lw=1.5, label=f"{txt}: {b['auc_x']:.2f}")
        ax.plot(x[:7], yv[:7], "-", color=S1, lw=2)
        ax.errorbar(x, yv, yerr=[yv - lo, hi - yv], fmt="o", color=S1, ms=6, capsize=3, lw=1.2, label="synthetic vs real 687-TEST")
        ax.axhline(0.5, color=GREY, lw=0.8, ls=":")
        ax.set_xticks(range(len(levels)))
        ax.set_xticklabels(lab)
        ax.set_title(title, color=INK)
        ax.set_ylim(0.4, 1.02)
    axs[0].set_ylabel("flight-level AUC_x (max over D2/D3), 95 % CI")
    axs[0].legend(loc="lower left", fontsize=7.5)
    f.suptitle("Ablation ladder: how detectable is the synthetic data at each texture level?", color=INK)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig1_ablation_ladder.png"), dpi=150)
    plt.close(f)


def auc_compare(res, fig):
    V = json.load(open(os.path.join(res, "verdicts.json")))
    S = V["singles"]
    keys = ["D2_lr_64_tex", "D2_gb_64_tex", "D2_lr_300_tex", "D2_gb_300_tex", "D2_lr_seg_tex", "D2_gb_seg_tex",
            "D3_64_res", "D3_300_res"]
    f, axs = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, (title, comps) in zip(axs, [("Engine T1", ["sim_T1_L6_eng", "tail_eng", "temporal_eng"]),
                                         ("Engine T2", ["sim_T2_L6_eng", "tail_eng", "temporal_eng"]),
                                         ("VRTG T1", ["sim_T1_L6_vrtg", "tail_vrtg", "temporal_vrtg"])]):
        for j, (c, col, nm) in enumerate(zip(comps, (S1, S2, S3), ("FULL synthetic vs real", "tail 687 vs 652", "temporal early vs late"))):
            s = S.get(c)
            if not s:
                continue
            ys = np.arange(len(keys)) + (j - 1) * 0.22
            a = np.array([s["per_classifier"][k]["auc"] for k in keys])
            lo = np.array([s["per_classifier"][k]["ci95"][0] for k in keys])
            hi = np.array([s["per_classifier"][k]["ci95"][1] for k in keys])
            ax.errorbar(a, ys, xerr=[a - lo, hi - a], fmt="o", color=col, ms=5, capsize=2, lw=1, label=nm)
        ax.axvline(0.5, color=GREY, lw=0.8, ls=":")
        ax.set_yticks(range(len(keys)))
        ax.set_yticklabels([k.replace("_tex", "").replace("_res", " (residual)").replace("D2_", "D2 ").replace("D3_", "D3 MiniRocket ").replace("_", " ") for k in keys])
        ax.set_title(title, color=INK)
        ax.set_xlim(0.3, 1.02)
        ax.set_xlabel("flight-level AUC, 95 % CI")
    axs[0].legend(loc="lower left", fontsize=7.5)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig2_auc_comparison.png"), dpi=150)
    plt.close(f)


def burst_vs_clock(res, fig):
    rows = list(csv.DictReader(open(os.path.join(res, "mechanism_flights.csv"))))
    f, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axs[0]
    for st, col in (("687-CAL", S1), ("687-TEST", S3), ("652", S2)):
        x = np.array([float(r["delta_clock_ppm"] or "nan") for r in rows if r["set"] == st])
        y = np.array([float(r["delta_ppm_8Hz"] or "nan") for r in rows if r["set"] == st])
        se = np.array([float(r["delta_clock_se_ppm"] or "nan") for r in rows if r["set"] == st])
        m = np.isfinite(x) & np.isfinite(y) & (se < 3)
        ax.scatter(x[m], y[m], s=14, color=col, alpha=0.75, edgecolor="white", linewidth=0.5, label=f"{st} (n={m.sum()}, clock SE < 3 ppm)")
    lim = [895, 935]
    ax.plot(lim, lim, color=GREY, lw=1, ls="--", label="burst Δ = clock-word Δ")
    ax.set_xlim(lim)
    ax.set_ylim(905, 922)
    ax.set_xlabel("clock-word offset Δ_clock (ppm; GMT edges vs sample count)")
    ax.set_ylabel("burst-derived Δ_burst (ppm; 8-Hz VRTG)")
    ax.set_title("Per-flight burst beat vs clock-word slope", color=INK)
    ax.legend(fontsize=7)
    ax = axs[1]
    ms = json.load(open(os.path.join(res, "mechanism_summary.json")))
    rates = np.array([8, 4, 2, 1])
    for st, col, mk in (("687-CAL", S1, "o"), ("652", S2, "s")):
        per = [ms[st]["P1"][f"{f}Hz"]["burst_period_s_at_median"] for f in rates]
        ax.plot(rates, per, mk, color=col, ms=7, label=f"{st}: measured burst period")
        d = ms[st]["P1"]["8Hz"]["median_ppm"] * 1e-6
        ff = np.linspace(0.8, 9, 100)
        ax.plot(ff, 1 / (ff * d), color=col, lw=1, label=f"1/(f·Δ), Δ = {d * 1e6:.1f} ppm")
    dcl = ms["687-CAL"]["P1"]["clock"]["median_ppm"] * 1e-6
    ax.plot(ff, 1 / (ff * dcl), color=GREY, lw=1, ls="--", label=f"1/(f·Δ_clock), Δ_clock = {dcl * 1e6:.1f} ppm (687)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(rates)
    ax.set_xticklabels(rates)
    ax.set_xlabel("channel sampling rate f (Hz)")
    ax.set_ylabel("burst period (s)")
    ax.set_title("P1: burst period = 1/(f·Δ) with one Δ", color=INK)
    ax.legend(fontsize=7)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig3_burst_period_vs_clock.png"), dpi=150)
    plt.close(f)


def collision(res, fig):
    ms = json.load(open(os.path.join(res, "mechanism_summary.json")))
    z = np.load(os.path.join(res, "mechanism_profiles.npz"))
    f, axs = plt.subplots(1, 2, figsize=(11, 4))
    ax = axs[0]
    for st, col, dx in (("687-CAL", S1, -0.12), ("687-TEST", S3, 0.0), ("652", S2, 0.12)):
        ch = ms[st]["P5"]["channels"]
        for i, f_ in enumerate((8, 4, 2, 1)):
            w = [v["w_s"] * 1000 for v in ch.values() if v["rate_hz"] == f_]
            ax.scatter(np.full(len(w), i + dx), w, s=16, color=col, alpha=0.8, edgecolor="white", linewidth=0.4,
                       label=st if i == 0 else None)
        g = ms[st]["P5"]["groups"]
        ax.plot(np.arange(4) + dx, [g[f"{f_}Hz"]["w_s_median"] * 1000 for f_ in (8, 4, 2, 1)], "-", color=col, lw=1)
    ax.set_xticks(range(4))
    ax.set_xticklabels(["8 Hz", "4 Hz", "2 Hz", "1 Hz"])
    ax.set_ylabel("collision window w = D·Δ (ms), boxcar ML fit per channel")
    ax.set_ylim(0, 40)
    ax.set_title("P5: collision window is ~constant in absolute time", color=INK)
    ax.legend(fontsize=7.5)
    ax = axs[1]
    for c, f_, col in (("VRTG", 8, S1), ("LATG", 4, S2), ("CCPC", 2, S3), ("OIT_1", 1, "#4a3aa7")):
        ev, sc = z[f"687-CAL_{c}_events"], z[f"687-CAL_{c}_samples"]
        ph = np.linspace(-0.5, 0.5, ev.size + 1)
        mid = 0.5 * (ph[1:] + ph[:-1])
        ms_ = mid / f_ * 1000
        p = ev / np.maximum(sc, 1)
        m = np.abs(ms_) < 60
        ax.plot(ms_[m], p[m], "-", color=col, lw=1.5, label=f"{c} ({f_} Hz)")
    ax.set_xlabel("read time relative to beat-phase centre (ms)")
    ax.set_ylabel("P(sentinel) per read, 687-CAL")
    ax.set_title("Folded loss profiles (asymmetric, ~22 ms wide)", color=INK)
    ax.legend(fontsize=7.5)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig4_collision_window.png"), dpi=150)
    plt.close(f)


def family_ablation(res, fig):
    files = sorted(glob.glob(os.path.join(res, "ablation", "*.json")))
    if not files:
        return
    f, axs = plt.subplots(1, len(files), figsize=(3.3 * len(files), 4.2), sharey=True)
    axs = np.atleast_1d(axs)
    for ax, p in zip(axs, files):
        js = json.load(open(p))
        cf = js["configs"]
        ref = cf["all_texture"]["auc"]
        labs, vals, lo, hi, cols = [], [], [], [], []
        for fam in C.TEXTURE_FAMILIES:
            for kind, col in (("only", S1), ("drop", S2)):
                k = f"{kind}_{fam}"
                if k in cf:
                    labs.append(f"{kind} {fam}")
                    vals.append(cf[k]["auc"])
                    lo.append(cf[k]["ci95"][0])
                    hi.append(cf[k]["ci95"][1])
                    cols.append(col)
        y = np.arange(len(labs))
        vals, lo, hi = map(np.array, (vals, lo, hi))
        ax.errorbar(vals, y, xerr=[vals - lo, hi - vals], fmt="none", ecolor=GREY, lw=1)
        ax.scatter(vals, y, c=cols, s=24, zorder=3)
        ax.axvline(ref, color=INK, lw=1, ls="--")
        ax.axvline(0.5, color=GREY, lw=0.8, ls=":")
        ax.set_yticks(y)
        ax.set_yticklabels(labs, fontsize=7.5)
        ax.set_title(f"{js['comparison']}\n{js['classifier']} (all: {ref:.2f})", fontsize=8, color=INK)
        ax.set_xlim(0.3, 1.02)
        ax.set_xlabel("AUC")
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig5_family_ablation.png"), dpi=150)
    plt.close(f)


def p4(res, fig):
    z = np.load(os.path.join(res, "mechanism_profiles.npz"))
    f, ax = plt.subplots(figsize=(6, 3.4))
    for st, col in (("687-CAL", S1), ("687-TEST", S3), ("652", S2)):
        s, a = z[f"{st}_digital_stale_by_phase"], z[f"{st}_digital_all_by_phase"]
        s, a = s.reshape(40, -1).sum(1), a.reshape(40, -1).sum(1)
        ph = np.linspace(-0.5, 0.5, 41)
        ax.plot(0.5 * (ph[1:] + ph[:-1]), s / np.maximum(a, 1), "-", color=col, lw=1.5, label=st)
    ax.set_xlabel("beat phase k·Δ mod 1 (free phase, cycles)")
    ax.set_ylabel("stale-read rate in transients")
    ax.set_ylim(0, 0.03)
    ax.set_title("P4: digital channels show no stale reads at the beat", color=INK)
    ax.legend(fontsize=7.5)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig6_p4_digital_stale.png"), dpi=150)
    plt.close(f)


def sensitivity(res, fig):
    V = json.load(open(os.path.join(res, "verdicts.json")))
    S = V["singles"]
    f, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, g, comps in ((axs[0], "eng", ["sim_T1_L0", "sim_T1_L6", "sim_T2_L6", "tail", "temporal"]),
                         (axs[1], "vrtg", ["sim_T1_L0", "sim_T1_L6", "tail", "temporal"])):
        for j, (fk, col) in enumerate((("low", S3), ("primary", S1), ("high", S2))):
            sfx = "" if fk == "primary" else f"_{fk}"
            xs, ys, lo, hi = [], [], [], []
            for i, c in enumerate(comps):
                s = S.get(f"{c}_{g}{sfx}")
                if s:
                    xs.append(i + (j - 1) * 0.2)
                    ys.append(s["auc_x"])
                    lo.append(s["ci95"][0])
                    hi.append(s["ci95"][1])
            ys, lo, hi = map(np.array, (ys, lo, hi))
            fc = C.FC[fk]["ENG" if g == "eng" else "VRTG"]
            ax.errorbar(xs, ys, yerr=[ys - lo, hi - ys], fmt="o", color=col, ms=5, capsize=2, lw=1, label=f"f_c = {fc} Hz")
        ax.set_xticks(range(len(comps)))
        ax.set_xticklabels([c.replace("sim_", "") for c in comps], fontsize=8)
        ax.axhline(0.5, color=GREY, lw=0.8, ls=":")
        ax.set_title("Engine" if g == "eng" else "VRTG", color=INK)
    axs[0].set_ylabel("AUC_x, 95 % CI")
    axs[0].legend(fontsize=7.5)
    f.tight_layout()
    f.savefig(os.path.join(fig, "fig7_fc_sensitivity.png"), dpi=150)
    plt.close(f)


def main(res, fig):
    os.makedirs(fig, exist_ok=True)
    for fn in (burst_vs_clock, collision, p4, ladder, auc_compare, family_ablation, sensitivity):
        try:
            fn(res, fig)
            print("ok", fn.__name__)
        except Exception as e:  # keep going; report
            print("FAILED", fn.__name__, repr(e))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
