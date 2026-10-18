"""Residual statistics shared by the fit (real 687-CAL targets) and the simulation-based calibration."""
import numpy as np
from scipy.stats import kurtosis

import config as C
from pipeline import runs, windows
from texture_model import N1_EDGES, CAS_EDGES, per_sample, engine

NB_ENG = len(N1_EDGES) + 1
NB_V = len(CAS_EDGES) + 1


def build_ctx(F, pipe, fc_key, lab=None, cas=None):
    from pipeline import regimes
    if lab is None:
        lab, _, cas = regimes(F)
    ctx = {"lab": lab, "cas": cas}
    for ch in C.GROUP:
        p = F[ch]
        fc = C.FC[fc_key]["VRTG" if ch == C.VRTG else "ENG"]
        xc, tr = pipe.truth(ch, p.x, p.rate, fc)
        ctx[ch] = {"x": p.x, "xc": xc, "truth": tr, "rate": p.rate, "dtype": p.dtype, "n": p.x.size}
    return ctx


def residuals(arrays, ctx, pipe, fc_key):
    """Residual (cleaned - low-pass) of each group channel of a (real or synthetic) flight."""
    out = {}
    for ch in C.GROUP:
        fc = C.FC[fc_key]["VRTG" if ch == C.VRTG else "ENG"]
        x = np.asarray(arrays[ch], float)
        xc, tr = pipe.truth(ch, x, ctx[ch]["rate"], fc)
        out[ch] = xc - tr
    return out


def bins_for(ctx):
    """Per-sample power bin per channel (from the real truth; identical for real and synthetic)."""
    lab, cas = ctx["lab"], ctx["cas"]
    b = {}
    for ch in C.GROUP:
        n, rate = ctx[ch]["n"], ctx[ch]["rate"]
        idx = per_sample(lab, rate, n)
        if ch == C.VRTG:
            b[ch] = np.searchsorted(CAS_EDGES, cas[idx], side="right")
        else:
            b[ch] = np.searchsorted(N1_EDGES, ctx[f"N1_{engine(ch)}"]["truth"][:n], side="right")
    n = ctx["N1_1"]["n"]
    b["mean"] = np.searchsorted(N1_EDGES, np.mean([ctx[f"N1_{k}"]["truth"][:n] for k in range(1, 5)], 0), side="right")
    return b


def acf1(r):
    r = r - r.mean()
    v = np.dot(r, r)
    return float(np.dot(r[:-1], r[1:]) / v) if v > 0 else np.nan


def flight_stats(res, ctx, pipe, fid, with_segments=False):
    """Sums for pooled SD by (channel, regime, bin), common-mode covariances by (family, regime, mean bin),
    W64-window medians of acf1 / kurtosis / 4-sigma exceedance, and (optionally) segment log-SD halves."""
    lab = ctx["lab"]
    B = bins_for(ctx)
    st = {"ss": {}, "nn": {}, "cov": {}, "cvn": {}, "win": {}, "seg": []}
    for ch in C.GROUP:
        n, rate = ctx[ch]["n"], ctx[ch]["rate"]
        reg = lab[per_sample(lab, rate, n)]
        nb = NB_V if ch == C.VRTG else NB_ENG
        key = reg * nb + B[ch]
        r = res[ch]
        st["ss"][ch] = np.bincount(key, r * r, minlength=7 * nb)
        st["nn"][ch] = np.bincount(key, minlength=7 * nb).astype(float)
    for f in C.FAMILIES:
        n = ctx[f"{f}_1"]["n"]
        reg = lab[per_sample(lab, 4, n)]
        key = reg * NB_ENG + B["mean"][:n]
        R = np.vstack([res[f"{f}_{k}"][:n] for k in range(1, 5)])
        s = R.sum(0)
        off = (s * s - (R * R).sum(0)) / 12.0                 # mean of the 12 ordered off-diagonal products
        st["cov"][f] = np.bincount(key, off, minlength=7 * NB_ENG)
        st["cvn"][f] = np.bincount(key, minlength=7 * NB_ENG).astype(float)
    W = windows(lab, fid)
    for ch in C.GROUP:
        rate = ctx[ch]["rate"]
        L = pipe.step(ch)
        rows = []
        for (rg, a, b) in W[64]:
            r = res[ch][int(a * rate):int(b * rate)]
            sd = r.std()
            if r.size < 32:
                continue
            ok = sd > 0.1 * L
            rows.append((rg, acf1(r) if ok else np.nan, float(kurtosis(r)) if ok else np.nan,
                         float(np.mean(np.abs(r) > 4 * sd)) if ok else np.nan, sd / L))
        st["win"][ch] = rows
    for f in C.FAMILIES:
        rows = []
        for (rg, a, b) in W[64]:
            r = np.mean([res[f"{f}_{k}"][int(a * 4):int(b * 4)] for k in range(1, 5)], 0)
            rows.append((rg, acf1(r) if r.std() > 0.05 * pipe.step(f"{f}_1") else np.nan))
        st["win"]["mean_" + f] = rows
    if with_segments:
        for r_code in range(7):
            for a, b in runs(lab, r_code):
                if b - a < 64:
                    continue
                h = (a + b) // 2
                row = {"regime": r_code}
                for ch in C.GROUP:
                    rate = ctx[ch]["rate"]
                    r1 = res[ch][int(a * rate):int(h * rate)]
                    r2 = res[ch][int(h * rate):int(b * rate)]
                    row[ch] = (np.log(max(r1.std(), 1e-12)), np.log(max(r2.std(), 1e-12)), r1.std() > 0 and r2.std() > 0)
                st["seg"].append(row)
    return st


def merge(stats_list):
    out = {"ss": {}, "nn": {}, "cov": {}, "cvn": {}, "win": {}, "seg": []}
    for s in stats_list:
        for k in ("ss", "nn", "cov", "cvn"):
            for ch, v in s[k].items():
                out[k][ch] = out[k].get(ch, 0) + v
        for ch, v in s["win"].items():
            out["win"].setdefault(ch, []).extend(v)
        out["seg"].extend(s["seg"])
    return out


def summary(M):
    """Moments used as calibration targets."""
    S = {"sd": {}, "cov": {}, "acf1": {}, "acf1_mean": {}, "kurt": {}, "exc4": {}}
    for ch in C.GROUP:
        nb = NB_V if ch == C.VRTG else NB_ENG
        ss = M["ss"][ch].reshape(7, nb).sum(1)
        nn = M["nn"][ch].reshape(7, nb).sum(1)
        S["sd"][ch] = {str(r): float(np.sqrt(ss[r] / nn[r])) if nn[r] > 50 else np.nan for r in range(7)}
        rows = np.array([w[1:] for w in M["win"][ch]], float) if M["win"][ch] else np.full((1, 4), np.nan)
        S["acf1"][ch] = float(np.nanmedian(rows[:, 0]))
        S["kurt"][ch] = float(np.nanmedian(rows[:, 1]))
        S["exc4"][ch] = float(np.nanmedian(rows[:, 2]))
    for f in C.FAMILIES:
        c = M["cov"][f].reshape(7, NB_ENG).sum(1)
        n = M["cvn"][f].reshape(7, NB_ENG).sum(1)
        S["cov"][f] = {str(r): float(c[r] / n[r]) if n[r] > 50 else np.nan for r in range(7)}
        rows = np.array([w[1] for w in M["win"]["mean_" + f]], float)
        S["acf1_mean"][f] = float(np.nanmedian(rows)) if rows.size else np.nan
    return S
