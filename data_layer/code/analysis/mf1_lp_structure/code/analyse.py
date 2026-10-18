"""MF1-D per-flight statistics, flight medians, joint flight bootstrap and the pre-registered verdict.

Reads the per-flight spectral cache written by `extract.py` (no MAT file is opened here) and computes every
statistic of PREREGISTRATION.md section 4 for each flight, class and engine, then the group medians with
bootstrap 95 % CIs (section 5) and the verdict (section 8).

Library module; the command-line stages live in `run.py`.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from common import REPO, bootstrap_generator
from extract import CH, CLASSES
from spectral import (
    FIT_SUBS,
    NSUB,
    SUB_FC,
    delay_lag_fit,
    gain_phase,
    multiple_coherence,
    pair_decomposition,
    partial_coherence,
    path_decomposition,
    residual_cross,
    texture_first_decomposition,
    white_subband_power,
)

NE = 4
#: (label, cause, effect, third channel for the within-engine path), B2 orientation (+ tau = effect lags)
PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("N1-N2", "N2", "N1", "FF"),
    ("N1-FF", "FF", "N1", "N2"),
    ("N2-FF", "FF", "N2", "N1"),
    ("N1-EGT", "N1", "EGT", "FF"),
    ("N2-EGT", "N2", "EGT", "FF"),
    ("FF-EGT", "FF", "EGT", "N1"),
)
#: extract.LAG_PAIRS order: (FF,N2), (FF,N1), (N2,N1), (FF,EGT), (N1,EGT), (N2,EGT)
LAG_INDEX = {"N2-FF": 0, "N1-FF": 1, "N1-N2": 2, "FF-EGT": 3, "N1-EGT": 4, "N2-EGT": 5}
#: B2 (phalanx b2_stats) per-engine order: (FF,N2), (FF,N1), (N2,N1), (FF,EGT), (N1,EGT)
B2_INDEX = {"N2-FF": 0, "N1-FF": 1, "N1-N2": 2, "FF-EGT": 3, "N1-EGT": 4}
PARTNER = {1: 2, 2: 1, 3: 4, 4: 3}
B1_CH16 = [f"{f}_{k}" for f in ("N1", "N2", "EGT", "FF") for k in range(1, NE + 1)]
_IU = np.triu_indices(16, 1)
B1_PAIR_INDEX = {frozenset((B1_CH16[i], B1_CH16[k])): n for n, (i, k) in enumerate(zip(*_IU, strict=True))}

# ---------------------------------------------------------------- texture floors (prereg section 4.5)
LSB = {
    "N1": (0.04, 0.03125),
    "N2": (0.04, 0.03125),
    "EGT": (0.8, 0.5),
    "FF": (None, 8.0),
    "PLA": (None, 0.087891),
}


def _tq(fam: str) -> float:
    nat, rec = LSB[fam]
    return (nat**2 / 12 if nat else 0.0) + rec**2 / 12


def _load_idio() -> dict[str, float]:
    p = REPO / "analysis" / "settling_experiment_round2" / "results" / "frozen" / "S" / "mb.json"
    with open(p) as fh:
        noise = json.load(fh)["noise"]
    return {k: float(v["sigma"]) ** 2 for k, v in noise.items()}


IDIO = _load_idio()
CH_ORDER = sorted(CH, key=lambda fk: CH[fk])
TQ = np.array([_tq(f) for f, _ in CH_ORDER])
TQI = TQ + np.array([IDIO.get(f"{f}_{k}", 0.0) for f, k in CH_ORDER])
TEX_MODES = ("q", "qi", "hf", "lo", "hi")


def texture_power(mode: str, hf: np.ndarray) -> np.ndarray:
    """(NSUB, 20) texture sub-band powers for a texture mode (prereg section 4.5)."""
    if mode == "q":
        v = TQ
    elif mode == "qi":
        v = TQI
    elif mode == "hf":
        v = np.asarray(hf, float)
    elif mode == "lo":
        v = np.minimum(TQ, hf)
    elif mode == "hi":
        v = np.maximum(TQI, hf)
    else:
        raise ValueError(mode)
    return white_subband_power(v)


# ---------------------------------------------------------------- cache
def load_flight(cache_dir: str, fname: str) -> dict:
    stem = fname.replace(".mat", "")
    with np.load(os.path.join(cache_dir, stem + ".npz"), allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    with open(os.path.join(cache_dir, stem + ".json")) as fh:
        d["info"] = json.load(fh)
    return d


# ---------------------------------------------------------------- per-flight statistics
def class_stats(d: dict, cls: str) -> dict[tuple[int, str], dict[str, float]] | None:
    """All statistics of one flight and class: {(engine, item): {stat: value}}.

    item = pair label, "eng" (engine level) or "xeng" (cross-engine, stored on engines 1 and 3).
    None if the class is absent for this flight."""
    if f"P_{cls}" not in d:
        return None
    P = d[f"P_{cls}"]
    K = int(d[f"K_{cls}"])
    hf = d[f"hf_{cls}"]
    rtd = d.get(f"rtd_{cls}")
    lags = d.get(f"lag_{cls}")
    act = d.get(f"plaact_{cls}")
    T = {m: texture_power(m, hf) for m in TEX_MODES}
    out: dict[tuple[int, str], dict[str, float]] = {}
    for e in range(1, NE + 1):
        for label, a, b, third in PAIRS:
            i, j = CH[(a, e)], CH[(b, e)]
            pr = pair_decomposition(P, T["q"], i, j, K)
            s: dict[str, float] = {
                "K": K,
                "r_spec": pr.r_spec,
                "r_shape": pr.r_shape,
                "r_lag": pr.r_lag,
                "r_cohonly": pr.r_cohonly,
                "L_total": pr.L_total,
                "L_dyn": pr.L_dyn_A,
                "L_phase": pr.L_phase_A,
                "L_shape": pr.L_shape,
                "L_coh": pr.L_coh_A,
                "L_tex": pr.L_tex_A,
                "L_beyond": pr.L_beyond_A,
                "CF_i": pr.CF_i,
                "CF_j": pr.CF_j,
                "CFtex_i": pr.CFtex_i,
                "CFtex_j": pr.CFtex_j,
                "Ubeyond_i": pr.U_beyond_i,
                "Ubeyond_j": pr.U_beyond_j,
                "Q_i": pr.Q_i,
                "Q_j": pr.Q_j,
                "r_tex_ceiling": pr.r_tex_ceiling,
                "r_truth": pr.r_truth,
                "tau_eq": pr.tau_eq,
                "tau_eq_se": pr.tau_eq_se,
                "r_delay": pr.r_delay,
            }
            for nm, v in pr.shares_A.items():
                s[f"s_{nm}"] = v
            for nm, v in pr.shares_S.items():
                s[f"sS_{nm}"] = v
            s["sB_coh"] = pr.L_coh_B / pr.L_total
            s["sB_tex"] = pr.L_tex_B / pr.L_total
            s["sB_beyond"] = pr.L_beyond_B / pr.L_total
            for k, (cb, pb) in enumerate(zip(pr.coh_bands, pr.phase_bands_deg, strict=True)):
                s[f"coh_band{k}"] = cb
                s[f"phase_band{k}"] = pb
            for m in ("qi", "hf", "lo", "hi"):
                pm = pair_decomposition(P, T[m], i, j, K)
                s[f"s_tex_{m}"] = pm.shares_A["tex"]
                s[f"s_beyond_{m}"] = pm.shares_A["beyond"]
                s[f"sS_tex_{m}"] = pm.shares_S["tex"]
                s[f"sS_beyond_{m}"] = pm.shares_S["beyond"]
                s[f"r_truth_{m}"] = pm.r_truth
                s[f"Q_i_{m}"] = pm.Q_i
                s[f"Q_j_{m}"] = pm.Q_j
            # D3: texture-first decomposition (sensitivity)
            for m in ("q", "lo", "hi"):
                tf = texture_first_decomposition(P, T[m], i, j)
                sfx = "" if m == "q" else f"_{m}"
                s[f"tf_s_dyn{sfx}"] = tf["s_dyn"]
                s[f"tf_s_tex{sfx}"] = tf["s_tex"]
                s[f"tf_s_beyond{sfx}"] = tf["s_beyond"]
                s[f"tf_r_lag{sfx}"] = tf["r_lag"]
            # paths: lever, partner-engine N1, within-engine third channel
            for nm, k in (
                ("pla", CH[("PLA", e)]),
                ("xN1", CH[("N1", PARTNER[e])]),
                ("third", CH[(third, e)]),
            ):
                via, part = path_decomposition(P, i, j, k)
                s[f"r_via_{nm}"] = via
                s[f"r_part_{nm}"] = part
            s["r_td"] = float(rtd[i, j]) if rtd is not None else np.nan
            s["lag_q02"] = float(lags[e - 1, LAG_INDEX[label]]) if lags is not None else np.nan
            dl = delay_lag_fit(P[:, i, j], gain_phase(P, i, j)[0], K)
            for nm, v in dl.items():
                s[f"fit_{nm}"] = v
            out[(e, label)] = s
        # engine-level: partial and multiple coherence
        n1, n2, ff = CH[("N1", e)], CH[("N2", e)], CH[("FF", e)]
        eng: dict[str, float] = {"K": K}
        eng["pc_N1N2_FF_N1"], eng["pc_N1N2_FF_N2"] = partial_coherence(P, n1, n2, ff)
        eng["pc_N1FF_N2_N1"], eng["pc_N1FF_N2_FF"] = partial_coherence(P, n1, ff, n2)
        for m in TEX_MODES:
            mc1 = multiple_coherence(P, T[m], n1, [n2, ff])
            mc2 = multiple_coherence(P, T[m], n2, [n1, ff])
            sfx = "" if m == "q" else f"_{m}"
            eng[f"mc_N1{sfx}"] = mc1.MCF
            eng[f"mcU_tex_N1{sfx}"] = mc1.U_tex
            eng[f"mcU_beyond_N1{sfx}"] = mc1.U_beyond
            eng[f"mc_ceiling_N1{sfx}"] = mc1.MC_ceiling
            eng[f"mc_N2{sfx}"] = mc2.MCF
            eng[f"mcU_tex_N2{sfx}"] = mc2.U_tex
            eng[f"mcU_beyond_N2{sfx}"] = mc2.U_beyond
            eng[f"mc_ceiling_N2{sfx}"] = mc2.MC_ceiling
            eng[f"mcU_beyond_diff{sfx}"] = mc1.U_beyond - mc2.U_beyond
        eng["pla_activity"] = float(act[e - 1]) if act is not None else np.nan
        eng["Q_PLA"] = float(
            T["q"][:, CH[("PLA", e)]].sum() / np.real(P[:, CH[("PLA", e)], CH[("PLA", e)]]).sum()
        )
        out[(e, "eng")] = eng
    # cross-engine residuals (engines 1-2 primary, 3-4 descriptive), stored on the lower engine
    for e1, e2 in ((1, 2), (3, 4)):
        x: dict[str, float] = {}
        for m in ("q", "hf"):
            sfx = "" if m == "q" else f"_{m}"
            r1 = residual_cross(
                P,
                T[m],
                CH[("N1", e1)],
                [CH[("N2", e1)], CH[("FF", e1)]],
                CH[("N1", e2)],
                [CH[("N2", e2)], CH[("FF", e2)]],
            )
            r2 = residual_cross(
                P,
                T[m],
                CH[("N2", e1)],
                [CH[("N1", e1)], CH[("FF", e1)]],
                CH[("N2", e2)],
                [CH[("N1", e2)], CH[("FF", e2)]],
            )
            for k, v in r1.items():
                x[f"N1res_{k}{sfx}"] = v
            for k, v in r2.items():
                x[f"N2res_{k}{sfx}"] = v
        out[(e1, "xeng")] = x
    return out


def flight_table(d: dict, classes: Sequence[str] = CLASSES) -> dict[tuple[str, int, str], dict[str, float]]:
    """{(class, engine, item): stats} for one flight; ALL also carries the exact B1 and B2 values."""
    tab: dict[tuple[str, int, str], dict[str, float]] = {}
    for c in classes:
        cs = class_stats(d, c)
        if cs is None:
            continue
        inc = bool(d["info"]["classes"][c]["included"])
        for (e, item), s in cs.items():
            s = dict(s)
            s["included"] = float(inc)
            tab[(c, e, item)] = s
    b1 = d["b1_fast"]
    b2 = d["b2"]
    for e in range(1, NE + 1):
        for label, a, b, _ in PAIRS:
            key = ("ALL", e, label)
            if key not in tab:
                continue
            fa = "EGT" if a == "EGT" else a
            fb = "EGT" if b == "EGT" else b
            idx = B1_PAIR_INDEX[frozenset((f"{fa}_{e}", f"{fb}_{e}"))]
            tab[key]["r_B1"] = float(b1[idx])
            tab[key]["b2_lag"] = (
                float(b2[(e - 1) * 5 + B2_INDEX[label]]) if label in B2_INDEX and len(b2) else np.nan
            )
    return tab


# ---------------------------------------------------------------- aggregation
def collect(tables: list[dict]) -> dict[tuple[str, int, str], dict[str, np.ndarray]]:
    """Per (class, engine, item) and stat: the per-flight vector (NaN when absent or not included)."""
    keys = sorted({k for t in tables for k in t})
    out: dict[tuple[str, int, str], dict[str, np.ndarray]] = {}
    nf = len(tables)
    for k in keys:
        stats = sorted({s for t in tables if k in t for s in t[k]})
        dd: dict[str, np.ndarray] = {}
        for s in stats:
            v = np.full(nf, np.nan)
            for f, t in enumerate(tables):
                if k in t and s in t[k] and t[k].get("included", 1.0) == 1.0:
                    v[f] = t[k][s]
            dd[s] = v
        out[k] = dd
    return out


def boot_sets(n: int, nb: int = 2000) -> tuple[np.ndarray, dict]:
    gen, src = bootstrap_generator(n)
    return gen.integers(0, n, size=(nb, n)), src


def med_ci(v: np.ndarray, R: np.ndarray) -> dict[str, float]:
    """Median over flights (ignoring NaN) and its percentile bootstrap 95 % CI (flights resampled jointly)."""
    ok = np.isfinite(v)
    if ok.sum() == 0:
        return {"median": np.nan, "lo": np.nan, "hi": np.nan, "n": 0}
    with np.errstate(all="ignore"):
        bs = np.nanmedian(v[R], axis=1)
    bs = bs[np.isfinite(bs)]
    return {
        "median": float(np.median(v[ok])),
        "lo": float(np.percentile(bs, 2.5)) if bs.size else np.nan,
        "hi": float(np.percentile(bs, 97.5)) if bs.size else np.nan,
        "n": int(ok.sum()),
    }


def summarise(coll: dict, R: np.ndarray) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    for (c, e, item), dd in coll.items():
        for s, v in dd.items():
            if s in ("included",):
                continue
            out[f"{c}|{e}|{item}"][s] = med_ci(v, R)
    return out


def paired(v1: np.ndarray, v2: np.ndarray, R: np.ndarray) -> dict[str, float]:
    return med_ci(v1 - v2, R)


def pooled_stats(
    ds: list[dict], cls: str, idx: np.ndarray | None = None
) -> dict[tuple[int, str], dict[str, float]]:
    """Pooled-spectrum estimator: segment-weighted sum of the flights' sub-band matrices (all K >= 1),
    then the pair decomposition (texture T_q)."""
    sel = [d for d in ds if f"P_{cls}" in d] if idx is None else [ds[i] for i in idx if f"P_{cls}" in ds[i]]
    if not sel:
        return {}
    Ks = np.array([int(d[f"K_{cls}"]) for d in sel], float)
    P = sum(d[f"P_{cls}"] * k for d, k in zip(sel, Ks, strict=True)) / Ks.sum()
    T = texture_power("q", np.zeros(len(CH)))
    out = {}
    for e in (1, 2):
        for label, a, b, _ in PAIRS:
            pr = pair_decomposition(P, T, CH[(a, e)], CH[(b, e)], int(Ks.sum()))
            out[(e, label)] = {
                "r_spec": pr.r_spec,
                "CF_i": pr.CF_i,
                "CF_j": pr.CF_j,
                "tau_eq": pr.tau_eq,
                "r_truth": pr.r_truth,
                **{f"s_{k}": v for k, v in pr.shares_A.items()},
            }
    return out


__all__ = [
    "FIT_SUBS",
    "NSUB",
    "PAIRS",
    "SUB_FC",
    "TEX_MODES",
    "TQ",
    "TQI",
    "boot_sets",
    "collect",
    "flight_table",
    "load_flight",
    "med_ci",
    "paired",
    "pooled_stats",
    "summarise",
    "texture_power",
]
