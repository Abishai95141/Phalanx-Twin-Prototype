"""M-B: revised sensor/acquisition texture, fitted on CAL residuals AFTER M-A (PREREGISTRATION section 3, A2-A4).

Components (applied in this order to the continuous engine-model signal x of one channel):
  1. independent per-sensor noise, AR(1): e_t = phi e_{t-1} + sqrt(1 - phi^2) sigma z_t, only while the engine runs.
     sigma^2 = idiosyncratic residual variance in CAL steady windows (amendment A3): the fast-band (x - lowpass
     0.2 Hz) residual after M-A, regressed on the other three channels of the same engine and the same channel of
     the other three engines (lags -2..+2); the unexplained variance, minus the quantiser's own variance
     (LSB_nat^2/12 + LSB_rec^2/12), floored at 0. phi = lag-1 autocorrelation of that unexplained part.
  2. double quantiser (A2): native grid LSB_rec (m r + phi0) [r = LSB_nat / LSB_rec], then the recorder lattice:
     y = LSB_rec * rint(x_nat / LSB_rec), x_nat = LSB_rec (r rint((x / LSB_rec - phi0) / r) + phi0).
     FF: single recorder lattice (8 lb/h). phi0 is fitted on CAL code usage (never-used residues).
  3. recorder effects carried over unchanged from round 1 (A4; model_params_primary.json "fixed"): validity
     gating (0 below the lowest valid reading, N1/N2/FF), non-negativity, glitch words (CAL rate 0 for these
     channels), airborne episodic freezes. No clock-slip missingness on digital channels (P4 refuted).
  4. container cast (round-1 C1): float64 containers hold float32-representable values; uint containers rint+clip.
"""
import json
import os

import numpy as np
from scipy.signal import lfilter

import r2common as R

NATIVE = {"N1": 1.28, "N2": 1.28, "EGT": 1.6, "FF": None}       # LSB_nat / LSB_rec (A2)
PERIOD = {"N1": 32, "N2": 32, "EGT": 8}
PHI_GRID = np.arange(0.0, 1.6, 0.0025)


# ------------------------------------------------------------------ quantiser
def double_quantise(x, fam, phi0):
    L = R.LSB_REC[fam]
    r = NATIVE[fam]
    if r is None:
        return L * np.rint(x / L)
    xn = L * (r * np.rint((x / L - phi0) / r) + phi0)
    return L * np.rint(xn / L)


def predicted_used(fam, phi0):
    """Residues mod P that the double quantiser can produce."""
    P, r = PERIOD[fam], NATIVE[fam]
    m = np.arange(0, 4 * P)
    k = np.rint(m * r + phi0).astype(int)
    return np.unique(k % P)


def fit_phi(fam, code_counts):
    """code_counts: {code: count} pooled over CAL running samples of the four positions. Returns phi0 and the
    match statistics (predicted never-used residue set must equal the observed one)."""
    if NATIVE[fam] is None:
        return None, {}
    P = PERIOD[fam]
    codes = np.array(sorted(code_counts))
    cnt = np.array([code_counts[c] for c in codes], float)
    # dense range: 1st..99th percentile of samples
    cs = np.cumsum(cnt) / cnt.sum()
    lo, hi = codes[np.searchsorted(cs, 0.01)], codes[np.searchsorted(cs, 0.99)]
    full = np.zeros(hi - lo + 1)
    sel = (codes >= lo) & (codes <= hi)
    full[codes[sel] - lo] = cnt[sel]
    kk = np.arange(lo, hi + 1)
    res_cnt = np.array([full[(kk % P) == q].sum() for q in range(P)])
    obs_unused = set(np.flatnonzero(res_cnt == 0).tolist())
    scores = []
    for phi in PHI_GRID:
        pu = set(predicted_used(fam, phi).tolist())
        pred_unused = set(range(P)) - pu
        scores.append(len(pred_unused ^ obs_unused))
    scores = np.array(scores)
    ok = PHI_GRID[scores == scores.min()]
    # centre of the first contiguous feasible interval
    grp = np.split(ok, np.flatnonzero(np.diff(ok) > 0.003) + 1)
    best = max(grp, key=len)
    phi0 = float(np.mean(best))
    return phi0, {"observed_unused_residues": sorted(obs_unused), "mismatch": int(scores.min()),
                  "feasible_interval": [float(best[0]), float(best[-1])], "residue_usage": (res_cnt / res_cnt.sum()).tolist()}


# ------------------------------------------------------------------ noise estimation
def idiosyncratic_noise(res_fast, steady_mask, lags=2):
    """res_fast: {fam: (4, n)} fast-band M-A residuals of one or more concatenated flights; steady_mask: (n,) bool.
    Returns ({channel: sum of squared unexplained}, {channel: n}, {channel: lag-1 sums}) for pooling."""
    out = {}
    n = steady_mask.size
    idx = np.flatnonzero(steady_mask)
    idx = idx[(idx >= lags) & (idx < n - lags)]
    if idx.size < 200:
        return out
    for f in R.FAM:
        for k in range(4):
            y = res_fast[f][k][idx]
            X = []
            for g in R.FAM:
                for j in range(4):
                    if (g == f) == (j == k):
                        continue                       # same channel: skip; others: same engine OR same family
                    if g != f and j != k:
                        continue
                    for l in range(-lags, lags + 1):
                        X.append(res_fast[g][j][idx + l])
            X = np.column_stack(X + [np.ones(idx.size)])
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            u = y - X @ beta
            out[f"{f}_{k + 1}"] = (u, idx)
    return out


def ar1_noise(n, sigma, phi, rng):
    z = rng.standard_normal(n)
    if phi > 0:
        z, _ = lfilter([np.sqrt(1 - phi ** 2)], [1.0, -phi], z, zi=[phi * rng.standard_normal()])
    return sigma * z


# ------------------------------------------------------------------ apply
class MB:
    def __init__(self, params):
        self.P = params          # {"phi0": {fam: v}, "noise": {ch: {"sigma":, "phi":}}, "fixed": round-1 fixed subset}

    def apply(self, ch, x, running, air_mask, fid, truth_for_gate=None):
        """x: continuous engine-model output (n,), running: bool (n,), air_mask: bool (n,) airborne samples (from
        PH codes 3..6, inputs only) for episodic freezes. Returns float array on the recorder lattice."""
        fam = ch.split("_")[0]
        nz = self.P["noise"][ch]
        e = ar1_noise(x.size, nz["sigma"], nz["phi"], R.rng_for(fid, ch, "MB_noise"))
        y = x + np.where(running, e, 0.0)
        y = double_quantise(y, fam, self.P["phi0"].get(fam))
        fx = self.P["fixed"]
        g = fx["gate"].get(ch)
        base = truth_for_gate if truth_for_gate is not None else x
        if g is not None:
            y = np.where(base < g - 0.5 * R.LSB_REC[fam], 0.0, y)
        y = np.maximum(y, 0.0)
        gl = fx["glitch"].get(ch)
        if gl and gl["rate_per_h"] > 0:
            rng = R.rng_for(fid, ch, "MB_glitch")
            m = rng.poisson(gl["rate_per_h"] * x.size / R.RATE / 3600)
            if m:
                y = y.copy()
                y[rng.integers(0, x.size, m)] = gl["value"]
        fr = fx["freeze"].get(ch)
        if fr and fr["rate_per_air_h"] > 0 and fr["durations_s"]:
            air = np.flatnonzero(air_mask)
            if air.size:
                rng = R.rng_for(fid, ch, "MB_freeze")
                m = rng.poisson(fr["rate_per_air_h"] * air.size / R.RATE / 3600)
                y = y.copy()
                for _ in range(m):
                    a = int(air[rng.integers(0, air.size)])
                    dd = int(round(fr["durations_s"][rng.integers(0, len(fr["durations_s"]))] * R.RATE))
                    y[a:a + dd] = y[a]
        return y


def cast(y, dtype):
    dt = np.dtype(dtype)
    if dt.kind in "ui":
        info = np.iinfo(dt)
        return np.clip(np.rint(y), info.min, info.max).astype(dt)
    if dt == np.float32:
        return y.astype(np.float32)
    return y.astype(np.float32).astype(np.float64)


def round1_fixed(r1_res=None):
    """Round-1 L5 recorder-effect parameters (687-CAL), engine channels only."""
    r1_res = r1_res or R.R1_RES
    fx = json.load(open(os.path.join(r1_res, "model_params_primary.json")))["fixed"]
    keep = set(R.CH16)
    return {"gate": {k: v for k, v in fx["gate"].items() if k in keep},
            "glitch": {k: v for k, v in fx["glitch"].items() if k in keep},
            "freeze": {k: v for k, v in fx["freeze"].items() if k in keep}}


# ------------------------------------------------------------------ fitting on CAL
def steady_mask(d, win_s=60, pla_range=2.0, alt_range=150.0):
    """CAL steady cruise samples: PH 5, in 60-s blocks where every PLA range <= 2 deg and ALT range <= 150 ft."""
    n = d["n"]
    W = int(win_s * R.RATE)
    m = np.zeros(n, bool)
    for a in range(0, n - W + 1, W):
        b = a + W
        if not np.all(d["PH"][a:b] == 5):
            continue
        if np.ptp(d["ALT"][a:b]) > alt_range or np.any(np.ptp(d["PLA"][:, a:b], axis=1) > pla_range):
            continue
        m[a:b] = True
    return m


def ma_residuals(d, ma, mask):
    """Measured minus M-A (CAL offsets) on running samples of a CAL flight; 0 elsewhere. {fam: (4, n)}."""
    import ma_model as MAM
    B = MAM.Batch([d], [mask], with_outputs=False, min_len_s=0.25, burn_s=0.0)
    sim = ma.simulate(B)                     # CAL-fitted unit parameters
    res = {f: np.zeros((4, d["n"])) for f in R.FAM}
    for f in R.FAM:
        res[f][B.eng, B.idx] = d["Y"][f][B.eng, B.idx] - sim[f]
    return res, B, sim


def fit(flights, ma, r1_res=None, log=print):
    import ma_model as MAM
    from pipeline import lowpass
    # ---- native-grid offsets from CAL code usage (running samples)
    phi0, phi_info = {}, {}
    for fam in ("N1", "N2", "EGT"):
        cc = {}
        for d in flights:
            run = MAM.running_mask_cal(d)
            for k in range(4):
                c = np.rint(d["Y"][fam][k][run[k]] / R.LSB_REC[fam]).astype(np.int64)
                u, n = np.unique(c, return_counts=True)
                for a, b in zip(u.tolist(), n.tolist()):
                    cc[a] = cc.get(a, 0) + b
        phi0[fam], phi_info[fam] = fit_phi(fam, cc)
        log(f"  M-B phi0 {fam}: {phi0[fam]:.4f} LSB, mismatch {phi_info[fam]['mismatch']}, "
            f"unused residues {phi_info[fam]['observed_unused_residues']}")
    # ---- idiosyncratic sensor noise in steady cruise
    acc = {ch: [0.0, 0, 0.0, 0.0, 0] for ch in R.CH16}      # sum u^2, n, sum u_t u_t+1, sum u_t^2 (pairs), n pairs
    for d in flights:
        run = MAM.running_mask_cal(d)
        res, _, _ = ma_residuals(d, ma, run)
        fast = {f: np.vstack([res[f][k] - lowpass(res[f][k], R.RATE, 0.2) for k in range(4)]) for f in R.FAM}
        st = steady_mask(d) & run.all(0)
        U = idiosyncratic_noise(fast, st)
        for ch, (u, idx) in U.items():
            a = acc[ch]
            a[0] += float(u @ u)
            a[1] += u.size
            cons = np.flatnonzero(np.diff(idx) == 1)
            a[2] += float(u[cons] @ u[cons + 1])
            a[3] += float(u[cons] @ u[cons])
            a[4] += cons.size
    noise = {}
    for ch, a in acc.items():
        fam = ch.split("_")[0]
        L = R.LSB_REC[fam]
        q2 = (L ** 2 / 12.0) + ((NATIVE[fam] * L) ** 2 / 12.0 if NATIVE[fam] else 0.0)
        v = a[0] / max(a[1], 1)
        s2 = max(v - q2, 0.0)
        phi = float(np.clip(a[2] / a[3], 0.0, 0.98)) if a[3] > 0 else 0.0
        noise[ch] = {"sigma": float(np.sqrt(s2)), "phi": phi, "unexplained_var": v, "quantiser_var": q2,
                     "n_samples": int(a[1])}
    fx = round1_fixed(r1_res)
    return {"phi0": phi0, "phi0_info": phi_info, "noise": noise, "fixed": fx,
            "native_step_lsb": NATIVE, "period_codes": PERIOD}
