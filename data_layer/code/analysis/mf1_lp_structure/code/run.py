"""MF1-D stages: verify (5 flights), n rule (scale), final summary. See ../PREREGISTRATION.md sections 6-8.

Usage:
  python -I run.py verify <mat_dir> <cache_dir>
  python -I run.py nrule  <mat_dir> <cache_dir>
  python -I run.py final  <mat_dir> <cache_dir> <n_final> <n_split>

All outputs go to ../results/. MAT files are read only through extract.py (guarded); this script reads the
derived cache.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir

import numpy as np
from analyse import (
    PAIRS,
    TQ,
    TQI,
    boot_sets,
    collect,
    flight_table,
    load_flight,
    med_ci,
    pooled_stats,
    texture_power,
)
from common import RESULTS
from extract import CH, CH_NAMES
from extract import main as extract_main
from spectral import FIT_SUBS, G_FAST, NBIN, NSUB, SUB_FC, gain_phase, pair_decomposition, unwrapped_phase
from svgplot import page, panel

ORDER_JSON = RESULTS / "flight_order.json"
FOLD0 = {  # published 51-flight CAL fold-0 medians (round-2 dev_battery_fold0.json), engines 1 and 2
    1: {"N1-N2": 0.438, "N1-FF": 0.628, "N2-FF": 0.577, "N1-EGT": 0.571, "N2-EGT": 0.077, "FF-EGT": 0.319},
    2: {"N1-N2": 0.439, "N1-FF": 0.642, "N2-FF": 0.695, "N1-EGT": 0.565, "N2-EGT": 0.043, "FF-EGT": 0.263},
}
NRULE_STATS = (("CF_N1", "CF_j"), ("CF_N2", "CF_i"), ("s_dyn", "s_dyn"))  # pair N1-N2 is (N2 -> N1)
TARGET_H = 0.05
SPLIT_CLASSES = ("AT", "MAN", "CLB", "CRZ", "DES")
SPLIT_MIN = 15


def order() -> list[str]:
    with open(ORDER_JSON) as fh:
        return json.load(fh)["order"]


def tables_for(cache: str, flights: list[str]) -> tuple[list[dict], list[dict]]:
    ds = [load_flight(cache, f) for f in flights]
    return ds, [flight_table(d) for d in ds]


# ---------------------------------------------------------------- verify
def plot_flight(d: dict, path: str) -> None:
    P = d["P_ALL"]
    hf = d["hf_ALL"]
    gsub = np.array([G_FAST[NBIN * b + 1 : NBIN * b + NBIN + 1].mean() for b in range(NSUB)])
    m = SUB_FC >= 0.15
    f = SUB_FC[m]

    def raw_psd(c):  # raw-signal-equivalent one-sided PSD [unit^2/Hz] (fast operator removed)
        return np.real(P[:, c, c])[m] / 0.0625 / gsub[m]

    panels = []
    for fams, unit in ((("N1", "N2"), "%^2/Hz"), (("FF",), "(lb/h)^2/Hz"), (("EGT",), "degC^2/Hz")):
        series = [(f"{fa}_1", f, raw_psd(CH[(fa, 1)])) for fa in fams]
        c0 = CH[(fams[0], 1)]
        hl = [(f"T_q {fams[0]}", 2 * TQ[c0] / 4.0), (f"T_hf {fams[0]}", 2 * hf[c0] / 4.0)]
        if fams[0] == "N1":
            hl.append(("T_qi N1_1", 2 * TQI[c0] / 4.0))
        panels.append(
            panel(
                series,
                title=f"PSD {'/'.join(fams)} (engine 1)",
                xlabel="Hz",
                ylabel=unit,
                xlog=True,
                ylog=True,
                hlines=hl,
            )
        )
    coh_series, ph_series, g_series = [], [], []
    for a, b in (("N2", "N1"), ("FF", "N1"), ("FF", "N2"), ("N1", "EGT")):
        C, G, _ = gain_phase(P, CH[(a, 1)], CH[(b, 1)])
        coh_series.append((f"{a}->{b}", f, C[m]))
        full = np.full(NSUB, np.nan)
        full[FIT_SUBS] = np.degrees(unwrapped_phase(P[:, CH[(a, 1)], CH[(b, 1)]]))
        ph_series.append((f"{a}->{b}", SUB_FC, full))
        if (a, b) == ("N2", "N1"):
            g_series.append(("|H1| N2->N1", f, G[m]))
    panels.append(
        panel(coh_series, title="Coherence (engine 1)", xlabel="Hz", ylabel="MSC", xlog=True, ylim=(0, 1))
    )
    ok = np.isfinite(ph_series[0][2])
    ph_series = [(n, x[ok], y[ok]) for n, x, y in ph_series]
    ph_series.append(("-360 f x 0.5 s", SUB_FC[ok], -360 * SUB_FC[ok] * 0.5))
    panels.append(panel(ph_series, title="Phase, 0.2-1 Hz (+ lag = negative)", xlabel="Hz", ylabel="deg"))
    panels.append(panel(g_series, title="Gain N2->N1 (H1)", xlabel="Hz", ylabel="%/%", xlog=True))
    with open(path, "w") as fh:
        fh.write(page(panels, cols=2, title=f"{d['info']['file']} ALL class, fast band (MF1-D verification)"))


def verify(mat_dir: str, cache: str) -> None:
    vdir = RESULTS / "verify"
    vdir.mkdir(exist_ok=True)
    flights = order()[:5]
    extract_main(mat_dir, str(ORDER_JSON), 5, cache, 5)
    ds, tabs = tables_for(cache, flights)
    L = ["# MF1-D verification on 5 CAL flights (order[:5])", ""]
    L.append(
        "n = 5: verification stage of PREREGISTRATION.md section 7 (formats, segments, B1 sanity, spectra)."
    )
    L.append("")
    L.append("## V1 formats")
    L.append("")
    L.append("| Flight | samples | rates OK | finite | airborne frac | ATEN values |")
    L.append("|---|---|---|---|---|---|")
    v1 = True
    for d in ds:
        i = d["info"]
        v1 &= i["rates_ok"] and i["finite_ok"]
        L.append(
            f"| {i['file']} | {i['n_samples']} | {i['rates_ok']} | {i['finite_ok']} | {i['air_frac']:.3f} | "
            f"{i['aten_values']} |"
        )
    L += ["", f"**V1: {'PASS' if v1 else 'FAIL'}**", "", "## V2 segments (samples / K / included)", ""]
    cls = ("ALL", "AT", "MAN", "CLB", "CRZ", "DES", "FLT", "TAXI", "AT_FLT", "MAN_FLT")
    L.append("| Flight | " + " | ".join(cls) + " |")
    L.append("|---|" + "---|" * len(cls))
    for d in ds:
        c = d["info"]["classes"]
        L.append(
            f"| {d['info']['file']} | "
            + " | ".join(f"{c[k]['samples']}/{c[k]['K']}/{'y' if c[k]['included'] else 'n'}" for k in cls)
            + " |"
        )
    L += [
        "",
        "PH composition of the ALL (airborne-rule) and MAN classes (PH 2 taxi, 3 take-off, 4 climb, "
        "5 cruise, "
        "6 approach, 7 rollout):",
        "",
    ]
    for d in ds:
        c = d["info"]["classes"]
        L.append(
            f"- {d['info']['file']}: ALL {c['ALL']['ph_counts']}; MAN {c['MAN']['ph_counts']}; "
            f"airborne samples outside Welch segments {c['ALL']['samples_ALLNOSEG']} "
            f"({c['ALL']['ph_counts_ALLNOSEG']})"
        )
    L += [
        "",
        "## V3 B1 sanity (5-flight medians vs published 51-flight CAL fold-0 medians; tolerance 0.10)",
        "",
    ]
    L.append("| Engine | Pair | median r_B1 (n=5) | fold-0 | diff | within 0.10 |")
    L.append("|---|---|---|---|---|---|")
    v3 = True
    exact = True
    for e in (1, 2):
        for label, *_ in PAIRS:
            v = np.array([t[("ALL", e, label)]["r_B1"] for t in tabs])
            vt = np.array([t[("ALL", e, label)]["r_td"] for t in tabs])
            exact &= bool(np.max(np.abs(v - vt)) < 1e-12)
            med = float(np.median(v))
            dlt = med - FOLD0[e][label]
            ok = abs(dlt) <= 0.10
            v3 &= ok
            L.append(f"| {e} | {label} | {med:.3f} | {FOLD0[e][label]:.3f} | {dlt:+.3f} | {ok} |")
    L += [
        "",
        f"r_B1 (battery `b1_stats`) equals this pipeline's time-domain fast-band r on the same samples to "
        f"< 1e-12 for every flight and pair: **{exact}**.",
        "",
        f"**V3: {'PASS' if v3 and exact else 'FAIL'}**",
        "",
    ]
    L += ["## V4 spectral reconstruction (median over flights of |r_spec - r_B1|; tolerance 0.03)", ""]
    L.append(
        "| Engine | Pair | median abs(r_spec - r_B1) | median abs(r_spec - r_seg) | max abs(r_spec - r_B1) |"
    )
    L.append("|---|---|---|---|---|")
    v4 = True
    for e in (1, 2):
        for label, a, b, _ in PAIRS:
            rs = np.array([t[("ALL", e, label)]["r_spec"] for t in tabs])
            rb = np.array([t[("ALL", e, label)]["r_B1"] for t in tabs])
            rseg = np.array([d["rtd_ALLSEG"][CH[(a, e)], CH[(b, e)]] for d in ds])
            m1 = float(np.median(np.abs(rs - rb)))
            v4 &= m1 <= 0.03
            L.append(
                f"| {e} | {label} | {m1:.3f} | {float(np.median(np.abs(rs - rseg))):.3f} | "
                f"{float(np.max(np.abs(rs - rb))):.3f} |"
            )
    L += [
        "",
        "r_seg = time-domain r on exactly the samples covered by the Welch segments. Differences between "
        "r_B1 "
        "and r_seg come only from airborne-rule samples outside the segments (all PH 2 taxi at the 25 % N1 "
        "threshold, see V2).",
        "",
        f"**V4: {'PASS' if v4 else 'FAIL (see text)'}**",
        "",
    ]
    L += ["## V5 spectra", ""]
    for d in ds:
        fn = f"spectra_{d['info']['file'].replace('.mat', '')}.svg"
        plot_flight(d, str(vdir / fn))
        L.append(f"- `{fn}`")
    st = (RESULTS / "log_selftest.txt").read_text()
    L += [
        "",
        f"## V6 self-test: {'PASS' if 'OVERALL: PASS' in st else 'FAIL'} (`results/log_selftest.txt`)",
        "",
    ]
    # first look (primary cell) and the n-rule start
    L += ["## Primary cell on the 5 flights (engine 1, ALL, N1-N2; development look, no verdict)", ""]
    sel = {}
    for name, key in NRULE_STATS:
        v = np.array([t[("ALL", 1, "N1-N2")][key] for t in tabs])
        sel[name] = v
        L.append(f"- {name}: {np.round(v, 3).tolist()} (SD {np.std(v, ddof=1):.3f})")
    sd = max(float(np.std(v, ddof=1)) for v in sel.values())
    n_pred = (1.96 * 1.2533 * sd / TARGET_H) ** 2
    n1 = min(152, max(20, 5 * math.ceil(n_pred / 5)))
    L += ["", f"n rule start: sigma_max = {sd:.4f}, n_pred = {n_pred:.1f} -> n1 = {n1}.", ""]
    (vdir / "log_verify.md").write_text("\n".join(L) + "\n")
    with open(vdir / "nrule_start.json", "w") as fh:
        json.dump(
            {"sigma_max": sd, "n_pred": n_pred, "n1": n1, "V1": v1, "V3": bool(v3 and exact), "V4": v4},
            fh,
            indent=1,
        )
    print("\n".join(L))


# ---------------------------------------------------------------- n rule
def _primary(d: dict) -> dict[str, float]:
    """The n-rule statistics of one flight (engine 1, ALL, N2 -> N1, texture T_q) without the full table."""
    if "P_ALL" not in d or not d["info"]["classes"]["ALL"]["included"]:
        return {}
    T = texture_power("q", d["hf_ALL"])
    pr = pair_decomposition(d["P_ALL"], T, CH[("N2", 1)], CH[("N1", 1)], int(d["K_ALL"]))
    return {"CF_j": pr.CF_j, "CF_i": pr.CF_i, "s_dyn": pr.shares_A["dyn"]}


def halfwidths(cache: str, n: int) -> dict[str, dict[str, float]]:
    flights = order()[:n]
    ds = [load_flight(cache, f) for f in flights]
    prim = [_primary(d) for d in ds]
    R, _ = boot_sets(n)
    out = {}
    for name, key in NRULE_STATS:
        v = np.array([p.get(key, np.nan) for p in prim])
        mc = med_ci(v, R)
        out[name] = {**mc, "h": (mc["hi"] - mc["lo"]) / 2, "sd": float(np.nanstd(v, ddof=1))}
    counts = {}
    for c in (*SPLIT_CLASSES, "MAN_FLT", "AT_FLT", "FLT"):
        counts[c] = int(sum(1 for d in ds if d["info"]["classes"][c]["included"]))
    # D1: flights contributing at least one in-flight manual segment (pooled estimator)
    counts["MAN_FLT_K1"] = int(sum(1 for d in ds if d["info"]["classes"]["MAN_FLT"]["K"] >= 1))
    out["_class_counts"] = counts
    return out


def nrule(mat_dir: str, cache: str) -> None:
    with open(RESULTS / "verify" / "nrule_start.json") as fh:
        n = int(json.load(fh)["n1"])
    log = [
        "# n-rule log (PREREGISTRATION.md section 7)",
        "",
        f"Target: bootstrap 95 % CI half-width <= {TARGET_H} for the medians of CF_N1, CF_N2 and s_dyn "
        "(engine 1, ALL, N1-N2). Prefixes of results/flight_order.json.",
        "",
    ]
    while True:
        extract_main(mat_dir, str(ORDER_JSON), n, cache, 6)
        hw = halfwidths(cache, n)
        hs = {k: v["h"] for k, v in hw.items() if not k.startswith("_")}
        line = (
            f"- n = {n}: "
            + "; ".join(
                f"{k} median {hw[k]['median']:.3f} [{hw[k]['lo']:.3f}, {hw[k]['hi']:.3f}] "
                f"h {hs[k]:.3f} sd {hw[k]['sd']:.3f}"
                for k in hs
            )
            + f"; class counts {hw['_class_counts']}"
        )
        log.append(line)
        print(line)
        if all(h <= TARGET_H for h in hs.values()) or n >= 152:
            break
        sd = max(hw[k]["sd"] for k in hs)
        n_pred = (1.96 * 1.2533 * sd / TARGET_H) ** 2
        n = min(152, max(n + 10, 5 * math.ceil(n_pred / 5)))
    n_final = n
    log += [
        "",
        f"**n_final = {n_final}** (all half-widths <= {TARGET_H}: {all(h <= TARGET_H for h in hs.values())})",
        "",
    ]
    # split coverage (section 7.3; MAN_FLT added by DEVIATIONS.md D1)
    n_split = n_final
    while True:
        hw = halfwidths(cache, n_split) if n_split != n_final else hw
        cc = hw["_class_counts"]
        need = {c: cc[c] for c in (*SPLIT_CLASSES, "MAN_FLT_K1") if cc[c] < SPLIT_MIN}
        log.append(f"- split coverage at n = {n_split}: {cc}; short: {need or 'none'}")
        if not need or n_split >= 152:
            break
        n_split = min(152, n_split + 10)
        extract_main(mat_dir, str(ORDER_JSON), n_split, cache, 6)
    log += ["", f"**n_split = {n_split}**", ""]
    (RESULTS / "n_rule_log.md").write_text("\n".join(log) + "\n")
    with open(RESULTS / "n_rule.json", "w") as fh:
        json.dump({"n_final": n_final, "n_split": n_split}, fh, indent=1)
    print("\n".join(log))


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage == "verify":
        verify(sys.argv[2], sys.argv[3])
    elif stage == "nrule":
        nrule(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(f"unknown stage {stage}")

__all__ = ["CH_NAMES", "collect", "pooled_stats"]
