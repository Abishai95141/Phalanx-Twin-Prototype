"""MF1-D final stage: statistics at n_final and n_split, pooled sensitivity, verdict, tables and figures.

Reads only the derived per-flight cache (written by extract.py for the prefixes fixed by the n rule).

Usage: python -I final.py <cache_dir>
"""

from __future__ import annotations

import csv
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir

import numpy as np
from analyse import PAIRS, boot_sets, collect, flight_table, load_flight, med_ci, pooled_stats
from common import RESULTS
from extract import CH
from run import FOLD0, order
from spectral import FIT_SUBS, NSUB, SUB_FC, gain_phase, unwrapped_phase
from svgplot import page, panel

CLASSES_MAIN = ("ALL", "AT", "MAN", "CLB", "CRZ", "DES", "FLT", "TAXI", "AT_FLT", "MAN_FLT")
POOLED_CLASSES = (
    "ALL",
    "AT",
    "MAN",
    "CLB",
    "CRZ",
    "DES",
    "FLT",
    "TAXI",
    "AT_FLT",
    "MAN_FLT",
    "AT_DES",
    "MAN_DES",
)
CF_HIGH = 0.70
MATERIAL_LO = 0.15
NEGLIGIBLE_HI = 0.10


def _ft(args):
    cache, f = args
    return flight_table(load_flight(cache, f))


def tables(cache: str, flights: list[str]) -> list[dict]:
    with Pool(6) as pool:
        return pool.map(_ft, [(cache, f) for f in flights])


def fmt(mc: dict, nd: int = 3) -> str:
    if not np.isfinite(mc.get("median", np.nan)):
        return "n/a"
    return f"{mc['median']:.{nd}f} [{mc['lo']:.{nd}f}, {mc['hi']:.{nd}f}]"


# ---------------------------------------------------------------- verdict (prereg section 8)
def verdict_from(sd: dict, cf: dict, st: dict, sb: dict) -> dict:
    """sd, st, sb: med_ci of the dynamic, texture and beyond-texture shares; cf: med_ci of CF_N1."""
    if sd["lo"] > 0.5 and cf["median"] >= CF_HIGH:
        v = "PHASE-DOMINATED"
    elif sb["lo"] > 0.5:
        v = "COHERENCE-DOMINATED, BEYOND TEXTURE"
    elif st["lo"] > 0.5:
        v = "TEXTURE-DOMINATED"
    else:
        v = "MIXED"
    lab = {}
    for nm, x in (("dynamic", sd), ("texture", st), ("beyond_texture", sb)):
        lab[nm] = (
            "material" if x["lo"] >= MATERIAL_LO else ("negligible" if x["hi"] < NEGLIGIBLE_HI else "neither")
        )
    return {
        "verdict": v,
        "components": lab,
        "s_dyn": sd,
        "s_tex": st,
        "s_beyond": sb,
        "CF_N1": cf,
        "rule_checks": {
            "s_dyn_lo_gt_0.5": bool(sd["lo"] > 0.5),
            "CF_N1_median_ge_0.70": bool(cf["median"] >= CF_HIGH),
            "s_beyond_lo_gt_0.5": bool(sb["lo"] > 0.5),
            "s_tex_lo_gt_0.5": bool(st["lo"] > 0.5),
        },
    }


def cell(coll: dict, R: np.ndarray, cls: str, e: int, item: str, stat: str) -> dict:
    v = coll.get((cls, e, item), {}).get(stat)
    if v is None:
        return {"median": np.nan, "lo": np.nan, "hi": np.nan, "n": 0}
    return med_ci(v, R)


def verdicts(coll: dict, R: np.ndarray) -> dict:
    out = {}
    for cls in ("ALL", "AT", "MAN", "FLT", "AT_FLT", "CLB", "CRZ", "DES", "TAXI"):
        for e in (1, 2):
            if (cls, e, "N1-N2") not in coll:
                continue

            def g(s: str, cls: str = cls, e: int = e) -> dict:
                return cell(coll, R, cls, e, "N1-N2", s)

            cf = g("CF_j")
            sd = g("s_dyn")
            out[f"{cls}|{e}|A_q"] = verdict_from(sd, cf, g("s_tex"), g("s_beyond"))
            for m in ("lo", "hi", "hf", "qi"):
                out[f"{cls}|{e}|A_{m}"] = verdict_from(sd, cf, g(f"s_tex_{m}"), g(f"s_beyond_{m}"))
            out[f"{cls}|{e}|S_q"] = verdict_from(g("sS_dyn"), cf, g("sS_tex"), g("sS_beyond"))
            for m in ("", "_lo", "_hi"):  # D3 texture-first
                out[f"{cls}|{e}|TF{m or '_q'}"] = verdict_from(
                    g(f"tf_s_dyn{m}"), cf, g(f"tf_s_tex{m}"), g(f"tf_s_beyond{m}")
                )
    return out


# ---------------------------------------------------------------- pooled (D1 primary for in-flight manual)
def pooled_with_ci(ds: list[dict], R: np.ndarray, classes=POOLED_CLASSES) -> dict:
    out = {}
    stats = ("r_spec", "CF_i", "CF_j", "tau_eq", "r_truth", "s_dyn", "s_tex", "s_beyond")
    boots = {c: [pooled_stats(ds, c, idx=R[b]) for b in range(R.shape[0])] for c in classes}
    point = {c: pooled_stats(ds, c) for c in classes}
    for c in classes:
        nf = sum(1 for d in ds if f"P_{c}" in d)
        K = int(sum(int(d[f"K_{c}"]) for d in ds if f"P_{c}" in d))
        for key, val in point[c].items():
            e, label = key
            rec = {"n_flights": nf, "K_total": K}
            for s in stats:
                bs = np.array([b[key][s] for b in boots[c] if key in b])
                rec[s] = {
                    "value": float(val[s]),
                    "lo": float(np.percentile(bs, 2.5)) if bs.size else np.nan,
                    "hi": float(np.percentile(bs, 97.5)) if bs.size else np.nan,
                }
            out[f"{c}|{e}|{label}"] = rec
    # paired pooled contrasts
    for a, b in (("AT_FLT", "MAN_FLT"), ("AT_DES", "MAN_DES"), ("AT", "MAN")):
        for key in point[a]:
            if key not in point[b]:
                continue
            e, label = key
            rec = {}
            for s in stats:
                diffs = np.array(
                    [
                        x[key][s] - y[key][s]
                        for x, y in zip(boots[a], boots[b], strict=True)
                        if key in x and key in y
                    ]
                )
                rec[s] = {
                    "value": float(point[a][key][s] - point[b][key][s]),
                    "lo": float(np.percentile(diffs, 2.5)) if diffs.size else np.nan,
                    "hi": float(np.percentile(diffs, 97.5)) if diffs.size else np.nan,
                }
            out[f"{a}-{b}|{e}|{label}"] = rec
    return out


# ---------------------------------------------------------------- figures
def summary_figure(ds: list[dict], cls: str, path: str, title: str) -> None:
    """Medians over flights (engine 1): coherence, unwrapped phase over 0.2-1 Hz, H1 gain, and the share of
    fast-band power per sub-band for N1 and N2."""
    pairs = (("N2", "N1"), ("FF", "N1"), ("FF", "N2"), ("N1", "EGT"), ("N2", "EGT"))
    m = SUB_FC >= 0.15
    coh, ph, gain, pw = {}, {}, {}, {"N1": [], "N2": []}
    for a, b in pairs:
        cs, ps, gs = [], [], []
        for d in ds:
            if f"P_{cls}" not in d or not d["info"]["classes"][cls]["included"]:
                continue
            P = d[f"P_{cls}"]
            C, G, _ = gain_phase(P, CH[(a, 1)], CH[(b, 1)])
            cs.append(C)
            gs.append(G)
            full = np.full(NSUB, np.nan)
            full[FIT_SUBS] = np.degrees(unwrapped_phase(P[:, CH[(a, 1)], CH[(b, 1)]]))
            ps.append(full)
            if (a, b) == ("N2", "N1"):
                for fam in ("N1", "N2"):
                    p = np.real(P[:, CH[(fam, 1)], CH[(fam, 1)]])
                    pw[fam].append(p / p.sum())
        coh[(a, b)] = np.median(np.array(cs), axis=0)
        gain[(a, b)] = np.median(np.array(gs), axis=0)
        with np.errstate(all="ignore"):
            ph[(a, b)] = np.nanmedian(np.array(ps), axis=0)
    n = len(pw["N1"])
    p1 = panel(
        [(f"{a}->{b}", SUB_FC[m], coh[(a, b)][m]) for a, b in pairs],
        title=f"Median coherence (engine 1, n={n})",
        xlabel="Hz",
        ylabel="MSC",
        xlog=True,
        ylim=(0, 1),
    )
    fs = SUB_FC[FIT_SUBS]
    p2 = panel(
        [(f"{a}->{b}", fs, ph[(a, b)][FIT_SUBS]) for a, b in pairs]
        + [("0.5 s delay", fs, -360 * fs * 0.5), ("1.25 s delay", fs, -360 * fs * 1.25)],
        title="Median phase, 0.2-1 Hz (second channel lags = negative)",
        xlabel="Hz",
        ylabel="deg",
    )
    p3 = panel(
        [("N2->N1 (%/%)", SUB_FC[m], gain[("N2", "N1")][m])],
        title="Median H1 gain N2->N1",
        xlabel="Hz",
        ylabel="gain",
        xlog=True,
    )
    p4 = panel(
        [(f"{k} power share", SUB_FC[m], np.median(np.array(v), axis=0)[m]) for k, v in pw.items()],
        title="Median share of fast-band power per 0.0625-Hz sub-band",
        xlabel="Hz",
        ylabel="share",
        xlog=True,
        ylog=True,
    )
    with open(path, "w") as fh:
        fh.write(page([p1, p2, p3, p4], cols=2, title=title))


def figures(cache: str) -> None:
    with open(RESULTS / "n_rule.json") as fh:
        nr = json.load(fh)
    n_final, n_split = int(nr["n_final"]), int(nr["n_split"])
    ds = [load_flight(cache, f) for f in order()[:n_split]]
    fig = RESULTS / "figures"
    fig.mkdir(exist_ok=True)
    for cls in ("ALL", "FLT", "AT_FLT", "TAXI", "CLB", "CRZ", "DES"):
        sel = ds[:n_final] if cls == "ALL" else ds
        summary_figure(
            sel, cls, str(fig / f"median_spectra_{cls}.svg"), f"MF1-D class {cls}: medians over flights"
        )


# ---------------------------------------------------------------- main
KEY_STATS = (
    "r_B1",
    "r_td",
    "r_spec",
    "r_lag",
    "r_shape",
    "CF_i",
    "CF_j",
    "s_dyn",
    "s_phase",
    "s_shape",
    "s_coh",
    "s_tex",
    "s_beyond",
    "sS_dyn",
    "sS_tex",
    "sS_beyond",
    "s_tex_lo",
    "s_beyond_lo",
    "s_tex_hi",
    "s_beyond_hi",
    "tf_s_dyn",
    "tf_s_tex",
    "tf_s_beyond",
    "tf_r_lag",
    "tf_s_dyn_lo",
    "tf_s_tex_lo",
    "tf_s_beyond_lo",
    "tf_s_dyn_hi",
    "tf_s_tex_hi",
    "tf_s_beyond_hi",
    "s_tex_qi",
    "s_beyond_qi",
    "s_tex_hf",
    "s_beyond_hf",
    "sB_coh",
    "sB_tex",
    "sB_beyond",
    "L_total",
    "r_cohonly",
    "r_truth_lo",
    "Q_i_hi",
    "Q_j_hi",
    "CFtex_i",
    "CFtex_j",
    "tau_eq_se",
    "tau_eq",
    "b2_lag",
    "lag_q02",
    "r_delay",
    "Q_i",
    "Q_j",
    "Q_i_hf",
    "Q_j_hf",
    "r_tex_ceiling",
    "r_truth",
    "r_truth_hf",
    "r_truth_hi",
    "Ubeyond_i",
    "Ubeyond_j",
    "r_via_pla",
    "r_via_xN1",
    "r_via_third",
    "coh_band0",
    "coh_band1",
    "coh_band2",
    "phase_band0",
    "phase_band1",
    "phase_band2",
    "fit_delay_only_tau",
    "fit_delay_only_wsse",
    "fit_lag_only_tau",
    "fit_lag_only_wsse",
    "fit_delay_lag_tau_d",
    "fit_delay_lag_tau_l",
    "fit_delay_lag_wsse",
)
ENG_STATS = (
    "pc_N1N2_FF_N1",
    "pc_N1N2_FF_N2",
    "pc_N1FF_N2_N1",
    "pc_N1FF_N2_FF",
    "mc_N1",
    "mcU_tex_N1",
    "mcU_beyond_N1",
    "mc_ceiling_N1",
    "mc_N2",
    "mcU_tex_N2",
    "mcU_beyond_N2",
    "mc_ceiling_N2",
    "mcU_beyond_diff",
    "mcU_beyond_N1_hi",
    "mcU_beyond_N2_hi",
    "mcU_beyond_diff_hi",
    "mcU_beyond_N1_hf",
    "mcU_beyond_N2_hf",
    "pla_activity",
    "Q_PLA",
)
X_STATS = (
    "N1res_res_coh",
    "N1res_res_common_share",
    "N1res_res_common_share_texcorr",
    "N1res_raw_common_share",
    "N1res_res_frac_1",
    "N1res_res_over_tex_1",
    "N1res_res_over_tex_1_hf",
    "N1res_res_common_share_texcorr_hf",
    "N2res_res_common_share",
    "N2res_res_common_share_texcorr",
    "N2res_raw_common_share",
    "N2res_res_frac_1",
    "N2res_res_over_tex_1",
)


def summarise_set(tabs: list[dict], n: int) -> tuple[dict, dict, np.ndarray]:
    coll = collect(tabs)
    R, src = boot_sets(n)
    summ: dict = {}
    for (c, e, item), dd in coll.items():
        stats = KEY_STATS if item not in ("eng", "xeng") else (ENG_STATS if item == "eng" else X_STATS)
        rec = {s: med_ci(dd[s], R) for s in stats if s in dd}
        if item not in ("eng", "xeng") and "r_spec" in dd:
            for nm in ("pla", "xN1", "third"):
                with np.errstate(all="ignore"):
                    rec[f"share_via_{nm}"] = med_ci(dd[f"r_via_{nm}"] / dd["r_spec"], R)
            rec["r_spec_minus_r_B1"] = med_ci(np.abs(dd["r_spec"] - dd.get("r_B1", np.full(n, np.nan))), R)
        summ[f"{c}|{e}|{item}"] = rec
    # paired contrasts (per-flight differences)
    for a, b in (("AT", "MAN"), ("FLT", "TAXI"), ("CLB", "CRZ"), ("DES", "CRZ")):
        for e in (1, 2):
            for label, *_ in PAIRS:
                ka, kb = coll.get((a, e, label)), coll.get((b, e, label))
                if ka is None or kb is None:
                    continue
                summ[f"{a}-{b}|{e}|{label}"] = {
                    s: med_ci(ka[s] - kb[s], R)
                    for s in ("r_spec", "r_td", "CF_j", "s_dyn", "s_beyond", "tau_eq")
                }
    return summ, {"bootstrap": src, "n": n}, R


def write_perflight(tabs: list[dict], flights: list[str], path: str) -> None:
    cols = (
        "r_B1",
        "r_td",
        "r_spec",
        "CF_i",
        "CF_j",
        "s_dyn",
        "s_tex",
        "s_beyond",
        "tau_eq",
        "Q_i",
        "Q_j",
        "r_truth",
        "r_via_pla",
        "r_via_xN1",
        "r_via_third",
        "K",
        "included",
    )
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flight", "class", "engine", "pair", *cols])
        for f, t in zip(flights, tabs, strict=True):
            for c in CLASSES_MAIN:
                for e in (1, 2):
                    for label, *_ in PAIRS:
                        s = t.get((c, e, label))
                        if s is None:
                            continue
                        w.writerow([f, c, e, label, *(f"{s.get(k, np.nan):.6g}" for k in cols)])


def main(cache: str) -> None:
    with open(RESULTS / "n_rule.json") as fh:
        nr = json.load(fh)
    n_final, n_split = int(nr["n_final"]), int(nr["n_split"])
    flights = order()[:n_split]
    tabs = tables(cache, flights)
    out = {}
    for tag, n in (("n_final", n_final), ("n_split", n_split)):
        summ, meta, R = summarise_set(tabs[:n], n)
        coll = collect(tabs[:n])
        out[tag] = {"n": n, "meta": meta, "summary": summ, "verdicts": verdicts(coll, R)}
    # B1 sanity at n_final
    s = out["n_final"]["summary"]
    v3 = {}
    for e in (1, 2):
        for label, *_ in PAIRS:
            mc = s[f"ALL|{e}|{label}"]["r_B1"]
            h = (mc["hi"] - mc["lo"]) / 2
            v3[f"{e}|{label}"] = {
                "median": mc["median"],
                "fold0": FOLD0[e][label],
                "diff": mc["median"] - FOLD0[e][label],
                "tol": max(0.03, h),
                "pass": bool(abs(mc["median"] - FOLD0[e][label]) <= max(0.03, h)),
            }
    out["V3_final"] = v3
    # pooled sensitivity (n_split flights; D1 primary for in-flight manual)
    ds = [load_flight(cache, f) for f in flights]
    R_split, _ = boot_sets(n_split)
    out["pooled_n_split"] = pooled_with_ci(ds, R_split)
    # full summary (all classes, engines 1-4) stays in the git-ignored run folder; the committed summary keeps
    # engines 1-2 (cross-engine 1-2 and 3-4) and the reported classes, rounded to 4 decimals
    with open(os.path.join(os.path.dirname(os.path.abspath(cache)), "summary_full.json"), "w") as fh:
        json.dump(out, fh, default=float)
    with open(RESULTS / "summary.json", "w") as fh:
        json.dump(compact(out), fh, separators=(",", ":"), default=float)
    write_perflight(tabs, flights, str(RESULTS / "perflight_primary.csv"))
    figures(cache)
    verdict = {k: v["verdicts"]["ALL|1|A_q"]["verdict"] for k, v in out.items() if k.startswith("n_")}
    print("primary-cell verdict (engine 1, ALL, N1-N2, ordering A, T_q):", verdict)


KEEP_CLASSES = {
    "ALL",
    "AT",
    "MAN",
    "FLT",
    "TAXI",
    "AT_FLT",
    "MAN_FLT",
    "CLB",
    "CRZ",
    "DES",
    "AT_DES",
    "MAN_DES",
}


def _round(o):
    """Round to 4 decimals (NaN -> None); median/CI records become {m, l, h, n}, pooled {v, l, h}."""
    if isinstance(o, float):
        return round(o, 4) if o == o else None
    if isinstance(o, dict):
        if set(o) == {"median", "lo", "hi", "n"}:
            return {"m": _round(o["median"]), "l": _round(o["lo"]), "h": _round(o["hi"]), "n": o["n"]}
        if set(o) == {"value", "lo", "hi"}:
            return {"v": _round(o["value"]), "l": _round(o["lo"]), "h": _round(o["hi"])}
        return {k: _round(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v) for v in o]
    return o


def _keep(key: str) -> bool:
    parts = key.split("|")
    if len(parts) != 3:
        return True
    cls, e, item = parts
    base = cls.split("-")
    if not all(b in KEEP_CLASSES for b in base):
        return False
    if item == "xeng":
        return e in ("1", "3")
    if e == "2":  # engine-2 replicate kept for the primary and control-mode classes only
        return all(b in ("ALL", "AT", "MAN", "FLT") for b in base)
    return e == "1"


def compact(out: dict) -> dict:
    res: dict = {}
    for k, v in out.items():
        if isinstance(v, dict) and "summary" in v:
            res[k] = {
                "n": v["n"],
                "meta": v["meta"],
                "summary": {kk: vv for kk, vv in v["summary"].items() if _keep(kk)},
                "verdicts": {kk: vv for kk, vv in v["verdicts"].items() if _keep(kk)},
            }
        elif k == "pooled_n_split":
            res[k] = {kk: vv for kk, vv in v.items() if _keep(kk)}
        else:
            res[k] = v
    return _round(res)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--figures-only":
        figures(sys.argv[1])
    else:
        main(sys.argv[1])
