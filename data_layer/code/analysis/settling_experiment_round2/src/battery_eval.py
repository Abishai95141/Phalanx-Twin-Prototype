"""Group distances, joint flight bootstrap and per-test verdicts (PREREGISTRATION sections 4-5).

A *group* = (stats label, flight list). A *comparison* = (group A, group B, paired?). Bootstrap draws are made per
underlying flight list (draw key), so every comparison that involves the same flights (e.g. the real holdout in
D_sim and in D_tail) uses the same resample: the distribution of D_sim - D_tail is a joint bootstrap.
2,000 resamples. Paired comparisons use only flights for which both versions have the statistic.

Distances (smaller = better):
  B1_fast (primary), B1_slow, B1h_fast / B1h_slow (0.5 Hz sensitivity): mean |median_A - median_B| over 120 pairs
  B2: mean |delta flight-median lag| over 20 (pair, engine) cells
  B3: part i  = mean |delta ln gain| + mean |delta coherence| over (engine, pair, band) cells (flight medians)
      part ii = mean |ln(tau_A / tau_B)| over (N1, FF, EGT) x (accel, decel) cells (pooled-step medians)
  B4: mean |delta median log F| over 12 directed pairs
  B5: part i = |scatter_A - scatter_B| / scatter_real ; part ii = |a_A - a_B|
  B6: mean |delta| / real per-phase IQR
Multi-part tests (B3, B5): PASS iff every part passes; FAIL iff any part fails; otherwise INCONCLUSIVE.
B1's verdict uses the fast band (primary); the slow band and 0.5 Hz split are reported.
Verdict: PASS if D_sim <= D_tail; FAIL if the one-sided 95 % bootstrap lower bound of D_sim - D_tail > 0;
otherwise INCONCLUSIVE; STRICT PASS reported when D_sim <= D_temp.
"""
import numpy as np

import battery as BT

NB = 2000
LN10 = np.log(10.0)
TESTS = ["B1_fast", "B1_slow", "B1h_fast", "B1h_slow", "B2", "B3i", "B3ii", "B4", "B5i", "B5ii", "B6"]
VERDICT_TESTS = {"B1": ["B1_fast"], "B2": ["B2"], "B3": ["B3i", "B3ii"], "B4": ["B4"], "B5": ["B5i", "B5ii"], "B6": ["B6"]}
KEY = {"B1_fast": "b1_fast", "B1_slow": "b1_slow", "B1h_fast": "b1h_fast", "B1h_slow": "b1h_slow", "B2": "b2",
       "B4": "b4", "B6": "b6"}


def _has(s, k):
    return s is not None and k in s


def _b5m(s):
    mf = {k: s[f"b5_ff_{k}"] for k in ("XtX", "Xty", "yy", "sy", "n")}
    me = {k: s[f"b5_egt_{k}"] for k in ("XtX", "Xty", "yy", "sy", "n")}
    return mf, me


def _med_abs(A, Bm):
    return float(np.nanmean(np.abs(np.nanmedian(A, 0) - np.nanmedian(Bm, 0))))


def stat_value(test, SA, SB, real_is_B=True):
    """Distance for one test between two lists of per-flight stat dicts (already restricted/resampled)."""
    if test in KEY and test != "B6":
        k = KEY[test]
        A = np.array([s[k] for s in SA if _has(s, k)])
        Bm = np.array([s[k] for s in SB if _has(s, k)])
        if len(A) < 2 or len(Bm) < 2:
            return np.nan
        return _med_abs(A, Bm)
    if test == "B6":
        A = np.array([s["b6"] for s in SA if _has(s, "b6")])
        Bm = np.array([s["b6"] for s in SB if _has(s, "b6")])
        if len(A) < 2 or len(Bm) < 2:
            return np.nan
        return BT.b6_distance(A, Bm, real=Bm if real_is_B else A)
    if test == "B3i":
        cA = np.array([s["b3_coh"] for s in SA if _has(s, "b3_coh")])
        cB = np.array([s["b3_coh"] for s in SB if _has(s, "b3_coh")])
        gA = np.array([s["b3_lgain"] for s in SA if _has(s, "b3_lgain")]) * LN10
        gB = np.array([s["b3_lgain"] for s in SB if _has(s, "b3_lgain")]) * LN10
        if len(cA) < 2 or len(cB) < 2:
            return np.nan
        return _med_abs(gA, gB) + _med_abs(cA, cB)
    if test == "B3ii":
        def taus(S):
            st = [s["b3_steps"] for s in S if s is not None and "b3_steps" in s]
            st = np.vstack(st) if st else np.zeros((0, 3))
            out = []
            for r in range(3):
                for d in range(2):
                    v = st[(st[:, 0] == r) & (st[:, 1] == d), 2]
                    out.append(np.median(v) if v.size >= 3 else np.nan)
            return np.array(out)
        tA, tB = taus(SA), taus(SB)
        v = np.abs(np.log(tA / tB))
        return float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
    if test in ("B5i", "B5ii"):
        MA_ = [_b5m(s) for s in SA if _has(s, "b5_ff_n")]
        MB_ = [_b5m(s) for s in SB if _has(s, "b5_ff_n")]
        if len(MA_) < 2 or len(MB_) < 2:
            return np.nan
        sa, aa = BT.b5_group(MA_)
        sb, ab = BT.b5_group(MB_)
        if test == "B5i":
            real = sb if real_is_B else sa
            return float(abs(sa - sb) / real)
        return float(abs(aa - ab))
    raise ValueError(test)


def group_values(S):
    """Descriptive group values (for the report): B5 scatter and exponent, B3ii taus, B2 lags."""
    out = {}
    M = [_b5m(s) for s in S if _has(s, "b5_ff_n")]
    if len(M) >= 2:
        out["B5_scatter"], out["B5_a"] = BT.b5_group(M)
    b2 = np.array([s["b2"] for s in S if _has(s, "b2")])
    if len(b2):
        out["B2_median_lags"] = np.median(b2, 0).tolist()
    b1 = np.array([s["b1_fast"] for s in S if _has(s, "b1_fast")])
    if len(b1):
        out["B1_fast_median"] = np.median(b1, 0).tolist()
    b1s = np.array([s["b1_slow"] for s in S if _has(s, "b1_slow")])
    if len(b1s):
        out["B1_slow_median"] = np.median(b1s, 0).tolist()
    st = [s["b3_steps"] for s in S if s is not None and "b3_steps" in s]
    st = np.vstack(st) if st else np.zeros((0, 3))
    out["B3ii_median_tau"] = {f"{g}_{d}": (float(np.median(st[(st[:, 0] == r) & (st[:, 1] == di), 2]))
                                           if np.sum((st[:, 0] == r) & (st[:, 1] == di)) >= 3 else None)
                              for r, g in enumerate(("N1", "FF", "EGT")) for di, d in enumerate(("accel", "decel"))}
    out["B3ii_n_steps"] = int(st.shape[0])
    b4 = np.array([s["b4"] for s in S if _has(s, "b4")])
    if len(b4):
        out["B4_median_logF"] = np.nanmedian(b4, 0).tolist()
    out["air_frac_median"] = float(np.median([s["air_frac"] for s in S if s is not None]))
    out["n_flights"] = int(sum(s is not None for s in S))
    return out


class Bootstrap:
    """Per-draw-key resample indices, shared across comparisons."""

    def __init__(self, seed, nb=NB):
        self.rng = np.random.default_rng(seed)
        self.nb = nb
        self.draws = {}

    def get(self, key, n):
        if key not in self.draws:
            self.draws[key] = [self.rng.integers(0, n, n) for _ in range(self.nb)]
        return self.draws[key]


def compare(SA, SB, keyA, keyB, paired, boot, tests=TESTS, real_is_B=True):
    """Point distances and bootstrap distributions for every test. SA/SB aligned with their flight lists."""
    out = {}
    if paired:
        assert len(SA) == len(SB)
    dA = boot.get(keyA, len(SA))
    dB = dA if paired else boot.get(keyB, len(SB))
    for t in tests:
        if paired:
            ok = [i for i in range(len(SA)) if SA[i] is not None and SB[i] is not None]
            A0, B0 = [SA[i] for i in ok], [SB[i] for i in ok]
        else:
            A0, B0 = SA, SB
        d0 = stat_value(t, A0, B0, real_is_B)
        bs = np.empty(boot.nb)
        for b in range(boot.nb):
            ia, ib = dA[b], dB[b]
            if paired:
                sel = [i for i in ia if SA[i] is not None and SB[i] is not None]
                bs[b] = stat_value(t, [SA[i] for i in sel], [SB[i] for i in sel], real_is_B)
            else:
                bs[b] = stat_value(t, [SA[i] for i in ia], [SB[i] for i in ib], real_is_B)
        out[t] = {"D": d0, "boot": bs}
    return out


def verdicts(sim, tail, temp=None):
    """Per-test verdicts from compare() outputs (same bootstrap object => joint distribution)."""
    res = {}
    for test, parts in VERDICT_TESTS.items():
        pv = {}
        for p in parts:
            ds, dt = sim[p]["D"], tail[p]["D"]
            diff = sim[p]["boot"] - tail[p]["boot"]
            lb = float(np.nanpercentile(diff, 5))
            if np.isfinite(ds) and np.isfinite(dt) and ds <= dt:
                v = "PASS"
            elif lb > 0:
                v = "FAIL"
            else:
                v = "INCONCLUSIVE"
            strict = None
            if temp is not None and np.isfinite(temp[p]["D"]):
                strict = bool(ds <= temp[p]["D"])
            pv[p] = {"D_sim": ds, "D_tail": dt, "D_temp": (temp[p]["D"] if temp is not None else None),
                     "lb95_one_sided_Dsim_minus_Dtail": lb, "verdict": v, "strict_pass": strict,
                     "D_sim_ci95": [float(np.nanpercentile(sim[p]["boot"], 2.5)), float(np.nanpercentile(sim[p]["boot"], 97.5))],
                     "D_tail_ci95": [float(np.nanpercentile(tail[p]["boot"], 2.5)), float(np.nanpercentile(tail[p]["boot"], 97.5))]}
        vs = [pv[p]["verdict"] for p in parts]
        overall = "PASS" if all(v == "PASS" for v in vs) else ("FAIL" if any(v == "FAIL" for v in vs) else "INCONCLUSIVE")
        strict = all(pv[p]["strict_pass"] for p in parts) if all(pv[p]["strict_pass"] is not None for p in parts) else None
        res[test] = {"verdict": overall, "strict_pass": strict, "parts": pv}
    return res


def decision(ver, g0_pass):
    n_pass = sum(v["verdict"] == "PASS" for v in ver.values())
    fails = [t for t, v in ver.items() if v["verdict"] == "FAIL"]
    if not g0_pass:
        return {"decision": "REWORK (G0 failed)", "n_pass": n_pass, "fails": fails}
    if not fails and n_pass >= 4:
        return {"decision": "GO", "n_pass": n_pass, "fails": fails}
    if fails:
        return {"decision": "GO WITH FIXES or REWORK (depends on module attribution of the FAILs; see report)",
                "n_pass": n_pass, "fails": fails}
    return {"decision": "NOT GO (fewer than 4 PASS, no FAIL)", "n_pass": n_pass, "fails": fails}


def summarise(cmp):
    return {t: {"D": v["D"], "ci95": [float(np.nanpercentile(v["boot"], 2.5)), float(np.nanpercentile(v["boot"], 97.5))]}
            for t, v in cmp.items()}


# ------------------------------------------------------------------ B9 (report only)
def b9(S_syn, S_real, seed):
    ok = [i for i in range(len(S_real)) if S_real[i] is not None and S_syn[i] is not None
          and "b9_X" in S_real[i] and "b9_X" in S_syn[i]]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(ok)
    tr, te = perm[: len(perm) // 2], perm[len(perm) // 2:]
    if len(tr) < 5 or len(te) < 5:
        return None
    Xte = np.vstack([S_real[i]["b9_X"] for i in te])
    yte = np.concatenate([S_real[i]["b9_y"] for i in te])
    Xr = np.vstack([S_real[i]["b9_X"] for i in tr])
    yr = np.concatenate([S_real[i]["b9_y"] for i in tr])
    Xs = np.vstack([S_syn[i]["b9_X"] for i in tr])
    ys = np.concatenate([S_syn[i]["b9_y"] for i in tr])
    trtr = BT.b9_scores(Xr, yr, Xte, yte, seed)
    tstr = BT.b9_scores(Xs, ys, Xte, yte, seed)
    ratio = {k: (tstr[k] / trtr[k] if trtr[k] > 0 else None) for k in trtr}
    rank_agree = (trtr["ridge"] >= trtr["gbm"]) == (tstr["ridge"] >= tstr["gbm"])
    return {"TRTR_R2": trtr, "TSTR_R2": tstr, "TSTR_over_TRTR": ratio, "ranking_agrees": bool(rank_agree),
            "n_train_flights": len(tr), "n_test_flights": len(te)}


def g1(S_syn, S_real):
    """Total-variation distance between pooled residue-usage histograms (per family), diagnostic."""
    out = {}
    for f in ("N1", "N2", "EGT", "FF"):
        k = f"g1_{f}"
        a = sum(s[k].sum(0) for s in S_syn if s is not None and k in s)
        b = sum(s[k].sum(0) for s in S_real if s is not None and k in s)
        pa, pb = a / max(a.sum(), 1), b / max(b.sum(), 1)
        out[f] = {"tv_distance": float(0.5 * np.abs(pa - pb).sum()), "residues_syn": pa.round(4).tolist(),
                  "residues_real": pb.round(4).tolist()}
    return out
