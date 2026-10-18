"""Tables, figures and the REPORT.md skeleton from a holdout run (results/holdout_<tag>/).

Writes results/holdout_<tag>/report_tables.md and figures/holdout_<tag>_*.png. For the primary holdout (tag "652")
it also writes ../REPORT.md if it does not exist yet (the interpretive sections are then completed by hand and
never overwritten by a re-run).

Usage: python -I s10_report.py <holdout_out_dir> <tag>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r2common as R  # noqa: E402

TESTS = ["B1", "B2", "B3", "B4", "B5", "B6"]
PARTS = {"B1": ["B1_fast"], "B2": ["B2"], "B3": ["B3i", "B3ii"], "B4": ["B4"], "B5": ["B5i", "B5ii"], "B6": ["B6"]}
COL = {"R2a": "#2a78d6", "R2b": "#eb6834", "R1ref": "#1baf7a", "bar": "#52514e", "temp": "#a3a29d"}
SURF = "#fcfcfb"


def fmt(x, d=3):
    return "–" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def figures(bat, tag, figdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "figure.dpi": 140, "axes.facecolor": SURF, "figure.facecolor": SURF,
                         "axes.edgecolor": "#c3c2b7", "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6})
    os.makedirs(figdir, exist_ok=True)
    out = []
    # (1) D_sim / D_tail per test part, primary variant S prior: R2a, R2b, R1-ref; reference lines at 1 and D_temp/D_tail
    parts = [p for t in TESTS for p in PARTS[t]] + ["B1_slow", "B1h_fast"]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    x = np.arange(len(parts))
    w = 0.26
    for j, (lab, key) in enumerate((("R2a (S, prior)", "S_R2a_prior"), ("R2b (S, prior)", "S_R2b_prior"), ("R1-ref", "R1ref"))):
        v = [bat["arms"][key]["D_sim"][p]["D"] / bat["D_tail"][p]["D"] if bat["D_tail"][p]["D"] else np.nan for p in parts]
        ax.bar(x + (j - 1) * w, v, w - 0.03, color=list(COL.values())[j], label=lab)
    temp = [bat["D_temp"][p]["D"] / bat["D_tail"][p]["D"] if bat["D_tail"][p]["D"] else np.nan for p in parts]
    ax.scatter(x, temp, marker="_", s=260, color=COL["bar"], zorder=5, label="D_temp / D_tail (stricter bar)")
    ax.axhline(1.0, color=COL["bar"], lw=1.2, ls="--", label="D_tail (PASS at or below)")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(parts, rotation=0)
    ax.set_ylabel("D_sim / D_tail (log)")
    ax.set_title(f"Battery distance relative to the real-vs-real tail bar (holdout {tag}); zero distances not drawn (log axis)",
                 loc="left", pad=22)
    ax.legend(ncol=5, fontsize=7, loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False)
    fig.tight_layout()
    p = os.path.join(figdir, f"holdout_{tag}_battery_ratio.png")
    fig.savefig(p)
    plt.close(fig)
    out.append(p)
    # (2) B1 fast-band median correlations: synthetic vs real holdout (120 pairs)
    real = np.array(bat["groups"]["real_holdout"].get("B1_fast_median", []))
    if real.size:
        fig, axs = plt.subplots(1, 3, figsize=(9, 3.1), sharex=True, sharey=True)
        for ax, (lab, key) in zip(axs, (("R2a (S, prior)", "S_R2a_prior"), ("R2b (S, prior)", "S_R2b_prior"), ("R1-ref", "R1ref"))):
            s = np.array(bat["arms"][key]["group"].get("B1_fast_median", []))
            ax.plot([-0.2, 1], [-0.2, 1], color=COL["bar"], lw=0.8)
            pp = np.array(bat["groups"]["real_partner"].get("B1_fast_median", []))
            if pp.size:
                ax.scatter(real, pp, s=9, color=COL["temp"], label="partner tail (real)")
            ax.scatter(real, s, s=9, color=COL[key.split("_")[1] if key != "R1ref" else "R1ref"], label=lab)
            ax.set_title(lab, loc="left")
            ax.set_xlabel("real holdout: fast-band corr")
        axs[0].set_ylabel("comparison group: fast-band corr")
        axs[0].legend(fontsize=7, frameon=False, loc="upper left")
        fig.suptitle("B1 fast band (f_c 0.2 Hz): 120 channel-pair median correlations", x=0.01, ha="left", fontsize=9)
        fig.tight_layout()
        p = os.path.join(figdir, f"holdout_{tag}_b1_fast_scatter.png")
        fig.savefig(p)
        plt.close(fig)
        out.append(p)
    # (3) B2 lags, engine 1
    names = ["FF→N2", "FF→N1", "N2→N1", "FF→EGT", "N1→EGT"]
    fig, ax = plt.subplots(figsize=(7, 2.9))
    x = np.arange(5)
    groups = [("real holdout", bat["groups"]["real_holdout"], COL["bar"]), ("partner tail", bat["groups"]["real_partner"], COL["temp"]),
              ("R2a (S)", bat["arms"]["S_R2a_prior"]["group"], COL["R2a"]), ("R2b (S)", bat["arms"]["S_R2b_prior"]["group"], COL["R2b"]),
              ("R1-ref", bat["arms"]["R1ref"]["group"], COL["R1ref"])]
    w = 0.16
    for j, (lab, g, c) in enumerate(groups):
        v = np.array(g.get("B2_median_lags", [np.nan] * 20))[:5]
        ax.bar(x + (j - 2) * w, v, w - 0.02, color=c, label=lab)
    ax.axhline(0, color=COL["bar"], lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel("flight-median lag (s), engine 1")
    ax.set_title("B2 lead–lag (positive: second channel lags)", loc="left", pad=22)
    ax.legend(ncol=5, fontsize=7, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0))
    fig.tight_layout()
    p = os.path.join(figdir, f"holdout_{tag}_b2_lags.png")
    fig.savefig(p)
    plt.close(fig)
    out.append(p)
    return out


def tables(out_dir, tag):
    bat = json.load(open(os.path.join(out_dir, "battery.json")))
    st = json.load(open(os.path.join(out_dir, "state.json")))
    meta = json.load(open(os.path.join(out_dir, "lists_meta.json")))
    L = []
    L.append(f"## Run facts (holdout {tag})\n")
    L.append(f"- Flights: {meta['n']} (holdout dates {meta['date_range'][0]} to {meta['date_range'][1]}; median split "
             f"{meta['median_date_split']}).")
    L.append(f"- Freeze check: frozen at {st['freeze_check']['frozen_at']}; mismatches {st['freeze_check']['mismatches']}.")
    icp = os.path.join(out_dir, "input_checks.json")
    if os.path.exists(icp):
        ic = json.load(open(icp))
        L.append(f"- Holdout input checks (report only, no exclusion): {ic['n_flagged']} of {len(ic['rows'])} flights flagged "
                 f"(airborne MACH zeros > 5 %, PLA range < 5 deg or ALT max < 5,000 ft): "
                 f"{[r['file'] for r in ic['rows'] if r['flag']]}.")
    a2 = st["archive2"]
    L.append(f"- Archive-2 status: ready={a2.get('ready')}, downloaded={a2['downloaded']}, extracted={a2['extracted']}, "
             f"last log line: `{a2['last_line']}`.\n")
    # verdict table, primary
    for v, off, title in (("S", "prior", "PRIMARY: variant S (A6+A7), fleet-prior unit parameters"),
                          ("P", "prior", "Variant P (pre-registered structure), fleet-prior unit parameters"),
                          ("S", "cal", "Secondary: variant S, CAL-fitted unit parameters"),
                          ("P", "cal", "Secondary: variant P, CAL-fitted unit parameters")):
        L.append(f"### Verdicts — {title}\n")
        L.append("| Test | part | D_sim R2a | D_sim R2b | D_tail | D_temp | R2a | R2b | strict R2a | strict R2b |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        va = bat["arms"][f"{v}_R2a_{off}"]["verdicts"]
        vb = bat["arms"][f"{v}_R2b_{off}"]["verdicts"]
        for t in TESTS:
            for p in PARTS[t]:
                pa, pb = va[t]["parts"][p], vb[t]["parts"][p]
                L.append(f"| {t} | {p} | {fmt(pa['D_sim'])} | {fmt(pb['D_sim'])} | {fmt(pa['D_tail'])} | {fmt(pa['D_temp'])} | "
                         f"{pa['verdict']} | {pb['verdict']} | {pa['strict_pass']} | {pb['strict_pass']} |")
            L.append(f"| **{t}** | test | | | | | **{va[t]['verdict']}** | **{vb[t]['verdict']}** | {va[t]['strict_pass']} | {vb[t]['strict_pass']} |")
        dec = st.get("decision", {}).get(f"{v}_{off}")
        if dec:
            L.append(f"\nDecision rule ({v}, {off}): **{dec['decision']}**; better arm {dec['better_arm']}; PASS count "
                     f"{dec['n_pass']}; FAILs {dec['fails']}; G0 used {dec['g0_pass_used']}; ranking {dec['ranking']}.\n")
    # contrast table of all labels
    labs = [k for k in bat["arms"]]
    parts = ["B1_fast", "B1_slow", "B1h_fast", "B2", "B3i", "B3ii", "B4", "B5i", "B5ii", "B6"]
    L.append("### All arms: D_sim (synthetic vs real holdout, paired) with the bars\n")
    L.append("| label | " + " | ".join(parts) + " |")
    L.append("|---|" + "---|" * len(parts))
    for lab in labs:
        L.append(f"| {lab} | " + " | ".join(fmt(bat["arms"][lab]["D_sim"][p]["D"]) for p in parts) + " |")
    L.append("| **D_tail** | " + " | ".join(fmt(bat["D_tail"][p]["D"]) for p in parts) + " |")
    L.append("| **D_temp** | " + " | ".join(fmt(bat["D_temp"][p]["D"]) for p in parts) + " |\n")
    # descriptive values
    L.append("### Descriptive group values\n")
    L.append("| group | B5 scatter | B5 a | B2 lags eng1 (FF→N2, FF→N1, N2→N1, FF→EGT, N1→EGT) | airborne frac |")
    L.append("|---|---|---|---|---|")
    for g, val in [("real_holdout", bat["groups"]["real_holdout"]), ("real_partner", bat["groups"]["real_partner"])] + \
                  [(k, bat["arms"][k]["group"]) for k in labs]:
        L.append(f"| {g} | {fmt(val.get('B5_scatter'))} | {fmt(val.get('B5_a'), 2)} | {val.get('B2_median_lags', [None] * 5)[:5]} | "
                 f"{fmt(val.get('air_frac_median'))} |")
    # B9 and G1
    L.append("\n### B9 (report only) and G1 (diagnostic)\n")
    L.append("| label | TRTR R² ridge/gbm | TSTR R² ridge/gbm | TSTR/TRTR ridge/gbm | ranking agrees | G1 TV N1/N2/EGT/FF |")
    L.append("|---|---|---|---|---|---|")
    for lab in labs:
        b9 = bat["arms"][lab]["B9"]
        g1 = bat["arms"][lab]["G1"]
        if b9:
            L.append(f"| {lab} | {fmt(b9['TRTR_R2']['ridge'])}/{fmt(b9['TRTR_R2']['gbm'])} | {fmt(b9['TSTR_R2']['ridge'])}/"
                     f"{fmt(b9['TSTR_R2']['gbm'])} | {fmt(b9['TSTR_over_TRTR']['ridge'])}/{fmt(b9['TSTR_over_TRTR']['gbm'])} | "
                     f"{b9['ranking_agrees']} | " + "/".join(fmt(g1[f]['tv_distance']) for f in ('N1', 'N2', 'EGT', 'FF')) + " |")
    # G0 and discriminators
    L.append("\n### G0 (binding) and discriminator diagnostics (no verdict)\n")
    L.append("| label | G0 pipeline-only LR AUC [CI] | GB AUC [CI] | G0 | full-metadata LR/GB (diag.) | D2 LR/GB 64 s | D2 LR/GB seg | D3 64 s |")
    L.append("|---|---|---|---|---|---|---|---|")
    ddir = os.path.join(out_dir, "disc")
    abl = {}
    if os.path.isdir(ddir):
        for f in sorted(os.listdir(ddir)):
            js = json.load(open(os.path.join(ddir, f)))
            g = js["G0_pipeline_only"]["classifiers"]
            gf = js["G0_full_metadata_diagnostic"]["classifiers"]
            d2 = js["D2"]
            d3 = js.get("D3_64_res", {}).get("auc")
            L.append(f"| {js['tag']} | {fmt(g['lr']['auc'])} {g['lr']['ci95']} | {fmt(g['gb']['auc'])} {g['gb']['ci95']} | "
                     f"{'PASS' if js['G0_pipeline_only']['pass'] else 'FAIL'} | {fmt(gf['lr']['auc'])}/{fmt(gf['gb']['auc'])} | "
                     f"{fmt(d2['lr_64_tex']['auc'])}/{fmt(d2['gb_64_tex']['auc'])} | {fmt(d2['lr_seg_tex']['auc'])}/"
                     f"{fmt(d2['gb_seg_tex']['auc'])} | {fmt(d3)} |")
            abl[js["tag"]] = js["ablation"]
    for tg, ab in abl.items():
        L.append(f"\nFamily ablation, {tg}, {ab['classifier']}: " +
                 ", ".join(f"{k} {v['auc']:.3f}" for k, v in sorted(ab["configs"].items())))
    # automatic attribution hints
    L.append("\n### Automatic attribution evidence (input to the module attribution in the report)\n")
    for t in TESTS:
        for p in PARTS[t]:
            g = {k: bat["arms"][k]["D_sim"][p]["D"] for k in labs}
            L.append(f"- {p}: R2a→R2b (M-C) S/prior {fmt(g['S_R2a_prior'])}→{fmt(g['S_R2b_prior'])}; P→S (A6+A7) R2a "
                     f"{fmt(g['P_R2a_prior'])}→{fmt(g['S_R2a_prior'])}; prior→cal offsets S/R2a {fmt(g['S_R2a_prior'])}→"
                     f"{fmt(g['S_R2a_cal'])}; R1-ref {fmt(g['R1ref'])}; D_tail {fmt(bat['D_tail'][p]['D'])}")
    figs = figures(bat, tag, os.path.join(R.R2DIR, "figures"))
    L.append("\n### Figures\n")
    for f in figs:
        L.append(f"![{os.path.basename(f)}](../../figures/{os.path.basename(f)})")
    txt = "\n".join(L) + "\n"
    with open(os.path.join(out_dir, "report_tables.md"), "w") as fh:
        fh.write(txt)
    return txt


def main(out_dir, tag):
    txt = tables(out_dir, tag)
    rep = os.path.join(R.R2DIR, "REPORT.md")
    if tag == "652" and not os.path.exists(rep):
        with open(rep, "w") as fh:
            fh.write("# Settling experiment round 2: report (holdout Tail 652, amendment A1)\n\n"
                     "_Auto-generated skeleton; the interpretive sections are completed by hand._\n\n"
                     + txt.replace("](../../figures/", "](figures/"))
    print(f"wrote {os.path.join(out_dir, 'report_tables.md')}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
