"""Behavioural fidelity battery B1-B6 and B9 (PREREGISTRATION section 4): per-flight statistics and group distances.

Common rules: identical estimator for every group; airborne samples = all four N1 > 25 % (computed from the
group's own N1, as in analysis/correlation_check/corr_check.py); flight-level bootstrap (2,000 resamples, paired
when the groups are versions of the same flights); smaller distance = better.

Per-flight statistics (function flight_stats) are computed once per (group, flight) and stored; distances and
bootstraps work on those (B5 uses additive least-squares moments so a bootstrap resample is a sum, not a refit).

B1  Pearson correlation of the 16 channels (N1, N2, EGT, FF x 4) on airborne samples, slow band = lowpass(x)
    (round-1 pipeline.lowpass, Butterworth-4 zero phase, f_c 0.2 Hz; 0.5 Hz sensitivity), fast = x - slow.
    Group value = per-pair median over flights; D = mean |difference| over the 120 pairs (fast band primary).
    Identical logic to corr_check.flight_stats (verified bit-for-bit on real files, see quick look log).
B2  Per engine, lag (s) of the peak cross-correlation of first differences (airborne samples, +-10 s, positive
    = second channel lags) for FF->N2, FF->N1, N2->N1, FF->EGT, N1->EGT. D = mean |difference of flight-median
    lags| over the 20 (pair, engine) cells.
B3  (i) Welch coherence and |H| (H1 = Pxy/Pxx) per engine for PLA->FF, FF->N2, FF->N1, FF->EGT, averaged in
    bands 0.01-0.05, 0.05-0.2, 0.2-1 Hz, on the longest airborne run (>= 10 min) of each flight, nperseg 512.
    D = mean |delta log gain| + mean |delta coherence| (flight medians).
    (ii) FOPDT time constants of N1/FF/EGT after detected PLA steps (round-1 transients.py detector and fit),
    accel/decel separately: D = mean |log(tau_sim / tau_real)| over the (response, direction) cells (group medians).
B4  Engine 1, VAR(8) on first differences of [FF, N2, N1, EGT] per airborne segment (>= 120 s), Granger F for each
    of the 12 directed pairs (restricted model drops the 8 lags of the cause); flight median of log F;
    D = mean |delta log F|.
B5  (i) relative RMS scatter of corrected fuel flow FF/(delta sqrt(theta)) about a cubic in corrected N2
    N2/sqrt(theta), pooled over the group's flights and engines (1-Hz decimated airborne samples);
    D = |delta scatter| / scatter_real. (ii) EGT temperature exponent a: argmin over a in [0, 1.2] (step 0.01) of
    the relative residual SD of (EGT+273.15)/theta^a about a quadratic in N1/sqrt(theta) (method of
    analysis/dashlink_texture/corrected_exponents.py); D = |delta a|.
B6  Per flight phase (PH 1..7) and channel (16): median, IQR and fast-band SD (x - lowpass 0.2 Hz, filtered over the
    whole record) of the airborne-rule samples in that phase (phases with < 40 such samples in a flight are
    missing for that flight); group value = median over flights; D = mean over (phase, channel, statistic) of
    |delta| / real per-phase IQR (group median of the per-flight IQR).
B9  (secondary, report only) EGT 10 s ahead from the other channels: ridge and gradient boosting; TSTR / TRTR R^2.
"""
import numpy as np

import r2common as R
from pipeline import lowpass   # round-1 measurement pipeline (read-only import)

IU = np.triu_indices(16, 1)
PAIR_NAMES = [f"{R.CH16[i]}~{R.CH16[k]}" for i, k in zip(*IU)]
LAG_PAIRS = [("FF", "N2"), ("FF", "N1"), ("N2", "N1"), ("FF", "EGT"), ("N1", "EGT")]
LAG_L = 40
A_GRID = np.round(np.arange(0.0, 1.2001, 0.01), 2)
B3_PAIRS = [("PLA", "FF"), ("FF", "N2"), ("FF", "N1"), ("FF", "EGT")]
B3_BANDS = [(0.01, 0.05), (0.05, 0.2), (0.2, 1.0)]
VAR_CH = ["FF", "N2", "N1", "EGT"]
PH_CODES = [1, 2, 3, 4, 5, 6, 7]


def X16(Y):
    return np.vstack([Y[f][k] for f in R.FAM for k in range(4)])


def air_mask(Y):
    return np.all(Y["N1"] > 25.0, axis=0)


# ------------------------------------------------------------------ B1
def b1_stats(Y, fc=0.2):
    X = X16(Y)
    air = np.all(X[0:4] > 25.0, axis=0)
    if air.sum() < 600:
        return None
    slow = np.vstack([lowpass(x, R.RATE, fc) for x in X])
    fast = X - slow
    s, f = slow[:, air], fast[:, air]
    if not ((s.std(1) > 0) & (f.std(1) > 0)).all():
        return None
    return np.corrcoef(s)[IU], np.corrcoef(f)[IU]


# ------------------------------------------------------------------ B2
def _lag(a, b, L=LAG_L):
    a = (a - a.mean()) / (a.std() + 1e-12)
    b = (b - b.mean()) / (b.std() + 1e-12)
    cc = [np.mean(a[:a.size - l] * b[l:]) if l >= 0 else np.mean(a[-l:] * b[:b.size + l]) for l in range(-L, L + 1)]
    return (int(np.argmax(cc)) - L) / R.RATE


def b2_stats(Y):
    air = air_mask(Y)
    if air.sum() < 600:
        return None
    out = []
    for k in range(4):
        for a, b in LAG_PAIRS:
            out.append(_lag(np.diff(Y[a][k][air]), np.diff(Y[b][k][air])))
    return np.array(out)


# ------------------------------------------------------------------ B5 (additive moments)
def b5_moments(Y, theta, delta):
    air = air_mask(Y)
    idx = np.flatnonzero(air)[::4]
    if idx.size < 150:
        return None
    th, de = theta[idx], delta[idx]
    sq = np.sqrt(th)
    xs, ys, xn, tk = [], [], [], []
    for k in range(4):
        xs.append(Y["N2"][k][idx] / sq)
        ys.append(Y["FF"][k][idx] / (de * sq))
        xn.append(Y["N1"][k][idx] / sq)
        tk.append(Y["EGT"][k][idx] + R.T0K)
    x = (np.concatenate(xs) - 85.0) / 10.0
    y = np.concatenate(ys) / 1000.0
    V = np.vander(x, 4, increasing=True)
    m_ff = {"XtX": V.T @ V, "Xty": V.T @ y, "yy": float(y @ y), "sy": float(y.sum()), "n": float(y.size)}
    xq = (np.concatenate(xn) - 70.0) / 20.0
    Vq = np.vander(xq, 3, increasing=True)
    th4 = np.tile(th, 4)
    T = np.concatenate(tk)
    XtX = Vq.T @ Vq
    Xty, yy, sy = [], [], []
    lth = np.log(th4)
    for a in A_GRID:
        ya = T * np.exp(-a * lth) / 1000.0
        Xty.append(Vq.T @ ya)
        yy.append(float(ya @ ya))
        sy.append(float(ya.sum()))
    m_egt = {"XtX": XtX, "Xty": np.array(Xty), "yy": np.array(yy), "sy": np.array(sy), "n": float(T.size)}
    return m_ff, m_egt


def b5_group(mlist):
    """(scatter, a) from a list of per-flight (m_ff, m_egt) moments."""
    XtX = sum(m[0]["XtX"] for m in mlist)
    Xty = sum(m[0]["Xty"] for m in mlist)
    yy = sum(m[0]["yy"] for m in mlist)
    sy = sum(m[0]["sy"] for m in mlist)
    n = sum(m[0]["n"] for m in mlist)
    beta = np.linalg.solve(XtX, Xty)
    rss = max(yy - beta @ Xty, 0.0)
    scatter = np.sqrt(rss / n) / (sy / n)
    XtX = sum(m[1]["XtX"] for m in mlist)
    Xty = sum(m[1]["Xty"] for m in mlist)
    yy = sum(m[1]["yy"] for m in mlist)
    sy = sum(m[1]["sy"] for m in mlist)
    n = sum(m[1]["n"] for m in mlist)
    Xinv = np.linalg.inv(XtX)
    rel = []
    for j in range(A_GRID.size):
        b = Xinv @ Xty[j]
        r = max(yy[j] - b @ Xty[j], 0.0)
        rel.append(np.sqrt(r / n) / (sy[j] / n))
    a = float(A_GRID[int(np.argmin(rel))])
    return float(scatter), a


# ------------------------------------------------------------------ distances / bootstrap
def boot_sets(n_a, n_b, paired, B=2000, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        ia = rng.integers(0, n_a, n_a)
        ib = ia if paired else rng.integers(0, n_b, n_b)
        out.append((ia, ib))
    return out


def d_median_abs(A, B, sets):
    """D = mean |median_A - median_B| (columns), with bootstrap distribution."""
    A, B = np.asarray(A), np.asarray(B)
    d0 = float(np.mean(np.abs(np.median(A, 0) - np.median(B, 0))))
    bs = np.array([np.mean(np.abs(np.median(A[ia], 0) - np.median(B[ib], 0))) for ia, ib in sets])
    return d0, bs


def d_b5(MA_, MB_, sets):
    sa, aa = b5_group(MA_)
    sb, ab = b5_group(MB_)
    d_sc = abs(sa - sb) / sb if True else None
    out = {"scatter": (sa, sb), "a": (aa, ab)}
    bs_sc, bs_a = [], []
    for ia, ib in sets:
        s1, a1 = b5_group([MA_[i] for i in ia])
        s2, a2 = b5_group([MB_[i] for i in ib])
        bs_sc.append(abs(s1 - s2) / s2)
        bs_a.append(abs(a1 - a2))
    out["D_scatter"] = (float(d_sc), np.array(bs_sc))
    out["D_a"] = (float(abs(aa - ab)), np.array(bs_a))
    return out


def ci(bs):
    return [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


# ------------------------------------------------------------------ B3
def longest_air_run(Y, min_s=600):
    air = air_mask(Y)
    m = np.r_[False, air, False].astype(int)
    d = np.diff(m)
    runs = list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    return (a, b) if (b - a) >= min_s * R.RATE else None


def b3_spectral(Y, PLA):
    """(coh, log10 gain) arrays of shape (4 engines, 4 pairs, 3 bands) on the longest airborne run."""
    from scipy.signal import coherence, csd, welch
    ab = longest_air_run(Y)
    if ab is None:
        return None
    a, b = ab
    coh = np.full((4, len(B3_PAIRS), len(B3_BANDS)), np.nan)
    lg = np.full_like(coh, np.nan)
    for k in range(4):
        sig = {"PLA": PLA[k][a:b], "FF": Y["FF"][k][a:b], "N2": Y["N2"][k][a:b], "N1": Y["N1"][k][a:b], "EGT": Y["EGT"][k][a:b]}
        for j, (u, v) in enumerate(B3_PAIRS):
            x, y = sig[u] - sig[u].mean(), sig[v] - sig[v].mean()
            if x.std() == 0 or y.std() == 0:
                continue
            f, C = coherence(x, y, fs=R.RATE, nperseg=512, detrend="linear")
            _, Pxy = csd(x, y, fs=R.RATE, nperseg=512, detrend="linear")
            _, Pxx = welch(x, fs=R.RATE, nperseg=512, detrend="linear")
            H = np.abs(Pxy) / np.maximum(Pxx, 1e-300)
            for i, (lo, hi) in enumerate(B3_BANDS):
                m = (f >= lo) & (f < hi)
                coh[k, j, i] = float(np.mean(C[m]))
                lg[k, j, i] = float(np.log10(max(np.mean(H[m]), 1e-300)))
    return coh, lg


def b3_steps(Y, PLA):
    """Round-1 transients.py detector and FOPDT fit (same rules) for N1, FF, EGT after PLA steps (detected on the
    input PLA, so identical step sets for real and synthetic versions of a flight). Returns list of
    (resp, dir, tau_s) for fits with R^2 > 0.9 and |dPLA| >= 5 deg at airborne-rule samples."""
    import warnings
    from scipy.optimize import curve_fit
    from transients import find_steps, fopdt          # analysis/dashlink_texture/transients.py (read-only import)
    air = air_mask(Y)
    out = []
    for e in range(4):
        for (j, pm, qm) in find_steps(PLA[e]):
            if not air[j] or abs(qm - pm) < 5:
                continue
            a, b = j - int(5 * R.RATE), j + int(30 * R.RATE)
            if a < 0 or b > Y["N1"].shape[1]:
                continue
            for g in ("N1", "FF", "EGT"):
                y = Y[g][e][a:b].astype(float)
                t = (np.arange(y.size) - int(5 * R.RATE)) / R.RATE
                y0, yf = y[:int(5 * R.RATE)].mean(), y[-int(5 * R.RATE):].mean()
                D = yf - y0
                if abs(D) < 5 * R.LSB_REC[g]:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        p, _ = curve_fit(fopdt, t, y, p0=[y0, D, 0.5, 2.0],
                                         bounds=([-np.inf, -np.inf, -2, 0.05], [np.inf, np.inf, 10, 60]), maxfev=4000)
                except Exception:
                    continue
                res = y - fopdt(t, *p)
                r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
                if r2 > 0.9:
                    out.append((g, "accel" if qm > pm else "decel", float(p[3])))
    return out


STEP_CELLS = [(g, dr) for g in ("N1", "FF", "EGT") for dr in ("accel", "decel")]


def b3_tau_group(step_lists):
    """Median tau per (resp, dir) cell over all steps of the group's flights."""
    out = np.full(len(STEP_CELLS), np.nan)
    for i, (g, dr) in enumerate(STEP_CELLS):
        v = [t for sl in step_lists for (gg, dd, t) in sl if gg == g and dd == dr]
        if len(v) >= 3:
            out[i] = np.median(v)
    return out


# ------------------------------------------------------------------ B4
def b4_granger(Y, p=8, min_s=120):
    """Engine-1 VAR(p) on first differences of [FF, N2, N1, EGT] over airborne segments (>= 120 s); log F for the
    12 directed pairs (cause -> effect), order [(c, e) for e in VAR_CH for c in VAR_CH if c != e]."""
    air = air_mask(Y)
    m = np.r_[False, air, False].astype(int)
    d = np.diff(m)
    Xs, Ys = [], []
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        if b - a < min_s * R.RATE:
            continue
        Z = np.column_stack([np.diff(Y[c][0][a:b]) for c in VAR_CH])
        L = Z.shape[0]
        Xs.append(np.hstack([Z[p - j - 1:L - j - 1] for j in range(p)]))
        Ys.append(Z[p:])
    if not Xs:
        return None
    X = np.vstack(Xs)
    Yv = np.vstack(Ys)
    X = np.column_stack([X, np.ones(X.shape[0])])
    n = X.shape[0]
    out = []
    for ei in range(4):
        y = Yv[:, ei]
        bf, *_ = np.linalg.lstsq(X, y, rcond=None)
        rss_f = float(np.sum((y - X @ bf) ** 2))
        for ci in range(4):
            if ci == ei:
                continue
            keep = [c for c in range(X.shape[1]) if c == X.shape[1] - 1 or (c % 4) != ci]
            Xr = X[:, keep]
            br, *_ = np.linalg.lstsq(Xr, y, rcond=None)
            rss_r = float(np.sum((y - Xr @ br) ** 2))
            if rss_f <= 0:
                out.append(np.nan)
                continue
            F = ((rss_r - rss_f) / p) / (rss_f / (n - X.shape[1]))
            out.append(float(np.log(max(F, 1e-6))))
    return np.array(out)


B4_PAIRS = [f"{c}->{e}" for e in VAR_CH for c in VAR_CH if c != e]


# ------------------------------------------------------------------ B6
def b6_stats(Y, PH):
    """(7 phases, 16 channels, 3 stats [median, IQR, fast SD]) with NaN for phases with < 40 airborne samples."""
    X = X16(Y)
    air = np.all(X[0:4] > 25.0, axis=0)
    fast = X - np.vstack([lowpass(x, R.RATE, 0.2) for x in X])
    out = np.full((len(PH_CODES), 16, 3), np.nan)
    for i, c in enumerate(PH_CODES):
        m = air & (PH[:X.shape[1]] == c)
        if m.sum() < 40:
            continue
        q = np.percentile(X[:, m], [25, 50, 75], axis=1)
        out[i, :, 0] = q[1]
        out[i, :, 1] = q[2] - q[0]
        out[i, :, 2] = fast[:, m].std(1)
    return out


def b6_distance(A, Bm, real=None):
    """A, Bm: (n_flights, 7, 16, 3) for synthetic/other and real. D = mean |median_A - median_B| / IQR_real."""
    real = Bm if real is None else real
    gA, gB = np.nanmedian(A, 0), np.nanmedian(Bm, 0)
    iqr = np.nanmedian(real[..., 1], 0)                               # (7, 16)
    den = np.where(iqr > 0, iqr, np.nan)[..., None]
    v = np.abs(gA - gB) / den
    return float(np.nanmean(v))


# ------------------------------------------------------------------ B9 data
def b9_rows(Y, horizon_s=10, lag_s=5):
    """1-Hz airborne rows: features = N1, N2, FF of all four engines at t and t - 5 s; target = EGT_1(t + 10 s)."""
    air = air_mask(Y)
    n = Y["N1"].shape[1]
    h, l = int(horizon_s * R.RATE), int(lag_s * R.RATE)
    t = np.arange(l, n - h, 4)
    t = t[air[t] & air[t + h] & air[t - l]]
    if t.size < 60:
        return None
    F = [Y[c][k][t] for c in ("N1", "N2", "FF") for k in range(4)] + \
        [Y[c][k][t] - Y[c][k][t - l] for c in ("N1", "N2", "FF") for k in range(4)]
    return np.column_stack(F).astype(np.float32), Y["EGT"][0][t + h].astype(np.float32)


def b9_scores(train_X, train_y, test_X, test_y, seed=0):
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import r2_score
    out = {}
    for name, mdl in (("ridge", make_pipeline(StandardScaler(), Ridge(alpha=1.0))),
                      ("gbm", HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                                            random_state=seed))):
        mdl.fit(train_X, train_y)
        out[name] = float(r2_score(test_y, mdl.predict(test_X)))
    return out


# ------------------------------------------------------------------ per-flight extraction
def flight_stats(Y, d):
    """All per-flight battery statistics for one (real or synthetic) flight; d carries the inputs."""
    n = min(Y["N1"].shape[1], d["n"])
    Y = {f: np.asarray(Y[f][:, :n], float) for f in R.FAM}
    out = {}
    r = b1_stats(Y, 0.2)
    out["b1_slow"], out["b1_fast"] = (r if r is not None else (None, None))
    r = b1_stats(Y, 0.5)
    out["b1h_slow"], out["b1h_fast"] = (r if r is not None else (None, None))
    out["b2"] = b2_stats(Y)
    r = b3_spectral(Y, d["PLA"][:, :n])
    out["b3_coh"], out["b3_lgain"] = (r if r is not None else (None, None))
    out["b3_steps"] = b3_steps(Y, d["PLA"][:, :n])
    out["b4"] = b4_granger(Y)
    out["b5"] = b5_moments(Y, d["theta"][:n], d["delta"][:n])
    out["b6"] = b6_stats(Y, d["PH"][:n])
    out["b9"] = b9_rows(Y)
    out["air_frac"] = float(air_mask(Y).mean())
    return out
