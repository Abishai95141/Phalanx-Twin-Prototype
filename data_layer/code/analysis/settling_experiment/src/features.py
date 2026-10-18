"""Feature extraction (D1, D2, D3 inputs and Gate-0 metadata) through the identical dlio.load_flight path.

Feature families (pre-registration section 4):
  quant    held fraction, |dx| = 1/2/>=3 LSB fractions, toggle rate, held-run lengths, lattice adherence,
           lattice occupancy
  noise    residual SD/LSB, MAD/LSB, first-difference SD/LSB, regime variance ratios (segment level)
  spectral ACF lags 1-20, normalised band powers, catch22 (pycatch22 0.5.0) of the residual
  tails    excess kurtosis, skewness, 4-sigma exceedance, max|r|/SD
  missing  sentinel count rate, spacing (median, CV), fraction of close events, Fano factor of per-second
           counts, periodicity (best beat frequency and Rayleigh power; 300-s windows and segments only),
           stale reads in transients (digital channels: transient count, stale fraction)
  cross    4-engine residual correlations per family, common-mode fraction, within-engine cross-parameter
           residual correlations, N1->EGT lag
  levels   mean, min, max (excluded from every verdict)
Residual = cleaned - low-pass (sentinels interpolated); D3 residual windows = raw - low-pass (sentinels kept),
in LSB units. Raw z-normalised windows (secondary D3 variant) = per window and channel (x - mean)/SD.
"""
import numpy as np
from scipy.signal import welch

import pycatch22

import config as C
from dlio import load_flight, constant_runs
from pipeline import regimes, windows

DGRID = np.arange(800e-6, 1020e-6 + 1e-9, 2e-6)
C22_MAX = 4096
DTYPES = ["float64", "float32", "uint8", "uint16", "int16", "int32", "int64", "uint32"]


def acf_lags(r, maxlag=20):
    r = r - r.mean()
    v = np.dot(r, r)
    n = r.size
    if v <= 0 or n <= maxlag + 2:
        return np.zeros(maxlag)
    return np.array([np.dot(r[:n - k], r[k:]) / v for k in range(1, maxlag + 1)])


def band_edges(rate, fc):
    e = [0.0, fc]
    while e[-1] * 2 < rate / 2 - 1e-9:
        e.append(e[-1] * 2)
    e.append(rate / 2)
    return e


def band_powers(r, rate, fc):
    nper = int(min(r.size, 64 * rate))
    f, p = welch(r - r.mean(), fs=rate, nperseg=nper, noverlap=nper // 2)
    e = band_edges(rate, fc)
    tot = p.sum()
    if tot <= 0:
        return np.zeros(len(e) - 1)
    return np.array([p[(f >= a) & (f < b if b < rate / 2 else f <= b)].sum() / tot for a, b in zip(e[:-1], e[1:])])


def c22(r):
    if r.size > C22_MAX:
        a = (r.size - C22_MAX) // 2
        r = r[a:a + C22_MAX]
    if r.size < 32 or np.std(r) == 0:
        return np.zeros(22)
    v = np.array(pycatch22.catch22_all(r.tolist())["values"], float)
    return np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)


def digital_transients(x, lsb):
    n = x.size
    if n < 10:
        return 0, 0.0
    k = np.arange(2, n - 2)
    slope = (x[k + 2] + x[k + 1] - x[k - 1] - x[k - 2]) / 6.0 / lsb
    span = np.abs(x[k + 2] - x[k - 2]) / lsb
    kk = k[(np.abs(slope) >= 2) & (span >= 8)]
    if kk.size == 0:
        return 0, 0.0
    return int(kk.size), float(np.mean(x[kk] == x[kk - 1]))


def chan_feats(ch, x, xc, r, mask, rate, pipe, fc, long_win):
    """Return list of (family, name, value) for one channel over one window/segment."""
    L = pipe.step(ch)
    out = []
    sd = r.std()
    # ---- noise
    out += [("noise", "sd", sd / L),
            ("noise", "mad", 1.4826 * np.median(np.abs(r - np.median(r))) / L),
            ("noise", "dsd", np.std(np.diff(xc)) / L)]
    # ---- quantisation / lattice
    dx = np.rint(np.diff(xc) / L)
    adx = np.abs(dx)
    rl = constant_runs(xc)
    good = x[~mask]
    lf = pipe.lattice_frac(ch, good) if good.size else np.zeros(1)
    occ = np.unique(good).size / (np.ptp(good) / L + 1) if good.size else 0.0
    out += [("quant", "held", np.mean(adx == 0)), ("quant", "d1", np.mean(adx == 1)), ("quant", "d2", np.mean(adx == 2)),
            ("quant", "d3p", np.mean(adx >= 3)),
            ("quant", "toggle", np.mean((adx[:-1] == 1) & (dx[1:] == -dx[:-1])) if dx.size > 1 else 0.0),
            ("quant", "run_mean", np.log1p(rl.mean())), ("quant", "run_p90", np.log1p(np.percentile(rl, 90))),
            ("quant", "run_max", np.log1p(rl.max())),
            ("quant", "lat_on", np.mean(np.abs(lf) < 1e-3)), ("quant", "lat_absfrac", np.mean(np.abs(lf))),
            ("quant", "occupancy", occ)]
    # ---- spectral / ACF
    ac = acf_lags(r)
    out += [("spectral", f"acf{k + 1}", ac[k]) for k in range(20)]
    bp = band_powers(r, rate, fc)
    out += [("spectral", f"band{k}", bp[k]) for k in range(bp.size)]
    cc = c22(r)
    out += [("spectral", f"c22_{k}", cc[k]) for k in range(22)]
    # ---- tails
    if sd > 1e-12:
        z = (r - r.mean()) / sd
        z2 = z * z
        # identical to scipy.stats.kurtosis / skew with their defaults (Fisher, biased)
        out += [("tails", "kurt", float(np.mean(z2 * z2) - 3.0)), ("tails", "skew", float(np.mean(z2 * z))),
                ("tails", "exc4", np.mean(np.abs(z) > 4)), ("tails", "maxabs", np.abs(z).max())]
    else:
        out += [("tails", "kurt", 0.0), ("tails", "skew", 0.0), ("tails", "exc4", 0.0), ("tails", "maxabs", 0.0)]
    # ---- missingness / timing
    ev = np.flatnonzero(mask)
    dur_min = x.size / rate / 60
    ns = ev.size
    out.append(("missing", "sent_rate", ns / dur_min))
    if ns >= 2:
        g = np.diff(ev) / rate
        out += [("missing", "gap_med", np.median(g)), ("missing", "gap_cv", g.std() / max(g.mean(), 1e-9)),
                ("missing", "frac_close", np.mean(g <= 10))]
    else:
        out += [("missing", "gap_med", x.size / rate), ("missing", "gap_cv", 0.0), ("missing", "frac_close", 0.0)]
    nsec = int(x.size // rate)
    cnt = np.bincount((ev // int(rate))[ev // int(rate) < nsec], minlength=nsec) if nsec else np.zeros(1)
    out.append(("missing", "fano", cnt.var() / cnt.mean() if cnt.mean() > 0 else 0.0))
    if long_win:
        if ns >= 8:
            P = np.abs(np.exp(2j * np.pi * np.outer(DGRID, ev.astype(float))).sum(1)) ** 2 / ns
            j = int(np.argmax(P))
            out += [("missing", "period_power", P[j] / max(ns, 1)), ("missing", "period_ppm", DGRID[j] * 1e6)]
        else:
            out += [("missing", "period_power", 0.0), ("missing", "period_ppm", 0.0)]
    if ch != C.VRTG:
        ntr, fst = digital_transients(x, pipe.lsb[ch])
        out += [("missing", "n_trans", np.log1p(ntr)), ("missing", "stale_tr", fst)]
    # ---- levels
    out += [("levels", "mean", xc.mean()), ("levels", "min", xc.min()), ("levels", "max", xc.max())]
    return out


def safe_corr(a, b):
    sa, sb = a.std(), b.std()
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def cross_feats(R):
    """R: {engine channel: residual window}. Returns list of (family, name, value)."""
    out = []
    for f in C.FAMILIES:
        X = [R[f"{f}_{k}"] for k in range(1, 5)]
        cs = []
        for i in range(4):
            for j in range(i + 1, 4):
                c = safe_corr(X[i], X[j])
                cs.append(c)
                out.append(("cross", f"{f}_e{i + 1}{j + 1}", c))
        out.append(("cross", f"{f}_emean", float(np.mean(cs))))
        M = np.vstack(X)
        cov = np.cov(M)
        v = np.mean(np.diag(cov))
        off = (cov.sum() - np.trace(cov)) / 12
        out.append(("cross", f"{f}_cmfrac", float(off / v) if v > 1e-18 else 0.0))
    pairs = [("N1", "N2"), ("N1", "FF"), ("N1", "EGT"), ("N2", "FF"), ("N2", "EGT"), ("FF", "EGT")]
    for a, b in pairs:
        cs = [safe_corr(R[f"{a}_{k}"], R[f"{b}_{k}"]) for k in range(1, 5)]
        out += [("cross", f"{a}{b}_k{k}", cs[k - 1]) for k in range(1, 5)]
        out.append(("cross", f"{a}{b}_kmean", float(np.mean(cs))))
    lags = []
    for k in range(1, 5):
        a, b = R[f"N1_{k}"], R[f"EGT_{k}"]
        if a.std() <= 1e-12 or b.std() <= 1e-12 or a.size < 80:
            lags.append(0.0)
            continue
        a = a - a.mean()
        b = b - b.mean()
        n = a.size
        L = 32
        c = [np.dot(a[max(0, -l):n - max(0, l)], b[max(0, l):n - max(0, -l)]) for l in range(-L, L + 1)]
        lags.append((int(np.argmax(c)) - L) / 4.0)
    out.append(("cross", "lag_N1_EGT_mean", float(np.mean(lags))))
    return out


def gate0(F, pipe):
    """Metadata-only features (Gate 0)."""
    out = [("meta", "record_frames", F["FRMC"].x.size), ("meta", "record_s", F["PH"].x.size)]
    for ch in C.GROUP:
        p = F[ch]
        x = p.raw.ravel()
        xf = x.astype(float)
        out += [("meta", f"{ch}_n", x.size), ("meta", f"{ch}_n_over_rate", x.size / p.rate),
                ("meta", f"{ch}_dtype", DTYPES.index(str(x.dtype)) if str(x.dtype) in DTYPES else -1),
                ("meta", f"{ch}_hasnan", float(np.isnan(xf).any()))]
        mask = pipe.sentinel_mask(ch, xf)
        good = xf[~mask & np.isfinite(xf)]
        lf = pipe.lattice_frac(ch, good)
        out.append(("meta", f"{ch}_lat_on", float(np.mean(np.abs(lf) < 1e-3))))
        h = np.histogram(lf, 10, (-0.5, 0.5))[0] / max(lf.size, 1)
        out += [("meta", f"{ch}_fracbin{k}", h[k]) for k in range(10)]
        f32 = np.mean(good.astype(np.float32).astype(np.float64) == good)
        bits = good.view(np.uint64) & np.uint64((1 << 52) - 1)
        tz = np.zeros(bits.size)
        bb = bits.copy()
        for _ in range(52):
            z = (bb & np.uint64(1)) == 0
            nz = bb != 0
            tz += z & nz
            bb = np.where(z & nz, bb >> np.uint64(1), np.uint64(0))
        tz[bits == 0] = 52
        out += [("meta", f"{ch}_f32repr", f32), ("meta", f"{ch}_mantissa_tz_mean", tz.mean()),
                ("meta", f"{ch}_n_sentinel", float(mask.sum())), ("meta", f"{ch}_first", xf[0]), ("meta", f"{ch}_last", xf[-1])]
    return out


def extract(path, pipe, fc_key, fid=None):
    F = load_flight(path)
    fid = fid or C.flight_id(path)
    lab, tat, cas = regimes(F)
    W = windows(lab, fid)
    data = {}
    for ch in C.GROUP:
        p = F[ch]
        fc = C.FC[fc_key]["VRTG" if ch == C.VRTG else "ENG"]
        x = p.x
        xc, tr = pipe.truth(ch, x, p.rate, fc)
        data[ch] = {"x": x, "xc": xc, "r": xc - tr, "rr": x - tr, "mask": pipe.sentinel_mask(ch, x),
                    "rate": p.rate, "fc": fc}
    out = {"names": {}}

    def win_feats(a, b, long_win):
        eng, vr = [], []
        R = {}
        for ch in C.GROUP:
            d = data[ch]
            i0, i1 = int(a * d["rate"]), int(b * d["rate"])
            fl = chan_feats(ch, d["x"][i0:i1], d["xc"][i0:i1], d["r"][i0:i1], d["mask"][i0:i1], d["rate"], pipe,
                            d["fc"], long_win)
            fl = [(fam, f"{ch}|{nm}", v) for fam, nm, v in fl]
            if ch == C.VRTG:
                vr += fl
            else:
                eng += fl
                R[ch] = d["r"][i0:i1]
        eng += [(fam, f"X|{nm}", v) for fam, nm, v in cross_feats(R)]
        return eng, vr

    for W_s in C.WINDOW_S:
        E, V, meta = [], [], []
        de, dv, ze, zv = [], [], [], []
        for (rg, a, b) in W[W_s]:
            eng, vr = win_feats(a, b, W_s >= 300)
            E.append([v for _, _, v in eng])
            V.append([v for _, _, v in vr])
            out["names"][f"eng{W_s}"] = [f"{fam}|{nm}" for fam, nm, _ in eng]
            out["names"][f"vrtg{W_s}"] = [f"{fam}|{nm}" for fam, nm, _ in vr]
            meta.append([rg, a, b, float(np.mean(tat[a:b]))])
            de.append(np.vstack([fit_len(data[ch]["rr"][a * 4:b * 4], W_s * 4) / pipe.step(ch) for ch in C.ENG]))
            dv.append(fit_len(data[C.VRTG]["rr"][a * 8:b * 8], W_s * 8)[None, :] / pipe.step(C.VRTG))
            if W_s == 64:
                ze.append(np.vstack([zn(fit_len(data[ch]["x"][a * 4:b * 4], 256)) for ch in C.ENG]))
                zv.append(zn(fit_len(data[C.VRTG]["x"][a * 8:b * 8], 512))[None, :])
        out[f"eng{W_s}"] = np.array(E, np.float32).reshape(len(E), -1)
        out[f"vrtg{W_s}"] = np.array(V, np.float32).reshape(len(V), -1)
        out[f"meta{W_s}"] = np.array(meta, np.float64).reshape(len(meta), 4)
        out[f"d3e{W_s}"] = np.array(de, np.float16).reshape(len(de), 16, W_s * 4)
        out[f"d3v{W_s}"] = np.array(dv, np.float16).reshape(len(dv), 1, W_s * 8)
        if W_s == 64:
            out["d3ze64"] = np.array(ze, np.float16).reshape(len(ze), 16, 256)
            out["d3zv64"] = np.array(zv, np.float16).reshape(len(zv), 1, 512)
    # ---- whole segments (longest run per regime) + regime variance ratios
    segE, segV = {}, {}
    for (rg, a, b) in W["seg"]:
        segE[rg], segV[rg] = win_feats(a, b, True)
    tmplE, tmplV = next(iter(segE.values())), next(iter(segV.values()))
    vecE, vecV, nE, nV = [], [], [], []
    for rg, rname in enumerate(C.REGIMES):
        e = segE.get(rg)
        v = segV.get(rg)
        vecE += [x for _, _, x in e] if e else [np.nan] * len(tmplE)
        vecV += [x for _, _, x in v] if v else [np.nan] * len(tmplV)
        nE += [f"{fam}|{rname}|{nm}" for fam, nm, _ in tmplE]
        nV += [f"{fam}|{rname}|{nm}" for fam, nm, _ in tmplV]
    cr = C.REGIME_CODE["cruise"]
    for ch in C.GROUP:
        d = data[ch]
        sds = {}
        for (rg, a, b) in W["seg"]:
            sds[rg] = d["r"][int(a * d["rate"]):int(b * d["rate"])].std()
        for rg, rname in enumerate(C.REGIMES):
            if rg == cr:
                continue
            val = np.log(sds[rg] / sds[cr]) if (rg in sds and cr in sds and sds[rg] > 0 and sds[cr] > 0) else np.nan
            if ch == C.VRTG:
                vecV.append(val)
                nV.append(f"noise|ratio|{ch}|{rname}_over_cruise")
            else:
                vecE.append(val)
                nE.append(f"noise|ratio|{ch}|{rname}_over_cruise")
    out["engseg"] = np.array(vecE, np.float32)
    out["vrtgseg"] = np.array(vecV, np.float32)
    out["names"]["engseg"], out["names"]["vrtgseg"] = nE, nV
    # ---- D1 material: residual samples (subsampled from W64 windows) and lattice histograms
    for ch in C.GROUP:
        d = data[ch]
        step = int(d["rate"])
        vals, regs = [], []
        for (rg, a, b) in W[64]:
            seg = d["r"][int(a * d["rate"]):int(b * d["rate"])][::step]
            vals.append(seg)
            regs.append(np.full(seg.size, rg, np.int8))
        out[f"d1r_{ch}"] = (np.concatenate(vals) / pipe.step(ch)).astype(np.float32) if vals else np.zeros(0, np.float32)
        out[f"d1g_{ch}"] = np.concatenate(regs) if regs else np.zeros(0, np.int8)
        dxl = np.clip(np.rint(np.diff(d["xc"]) / pipe.step(ch)), -8, 8).astype(int) + 8
        out[f"d1d_{ch}"] = np.bincount(dxl, minlength=17)
        good = d["x"][~d["mask"]]
        out[f"d1f_{ch}"] = np.histogram(pipe.lattice_frac(ch, good), 20, (-0.5, 0.5))[0]
    g0 = gate0(F, pipe)
    out["gate0"] = np.array([v for _, _, v in g0], np.float64)
    out["names"]["gate0"] = [nm for _, nm, _ in g0]
    return out


def zn(x):
    s = x.std()
    return (x - x.mean()) / s if s > 0 else np.zeros_like(x)


def fit_len(x, n):
    if x.size == n:
        return x
    if x.size > n:
        return x[:n]
    return np.r_[x, np.full(n - x.size, x[-1] if x.size else 0.0)]
