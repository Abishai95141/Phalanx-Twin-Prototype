"""Per-flight battery statistics B1-B6 (port of round-2 `battery.py` + `s04_stats.py`).

Each function is a line-by-line port of the pre-registered round-2 estimator. Statistics are computed once per
(group, flight); distances and bootstraps (`phalanx.validation.battery.evaluate`) work on them. B5 stores
additive least-squares moments so that a bootstrap resample is a sum, not a refit.

Common rule: airborne samples are those where every engine's N1 exceeds `BatteryConfig.airborne_n1_min`
(25 %), computed from the group's own N1 (as `analysis/correlation_check/corr_check.py`).

| Stat | Content (DASHlink: 4 engines, 16 channels) |
|---|---|
| b1_slow / b1_fast | Pearson correlations of the 120 channel pairs, slow = lowpass 0.2 Hz, fast = x - slow |
| b1h_slow / b1h_fast | the same with the 0.5 Hz split (sensitivity) |
| b2 | lag [s] of the peak cross-correlation of first differences, 5 pairs x 4 engines (engine-major) |
| b3_coh / b3_lgain | Welch coherence and log10 |H1| on the longest airborne run, (engine, pair, band) |
| b3_steps | (k, 3) rows (response index N1/FF/EGT, direction 0 accel / 1 decel, tau [s]) |
| b4 | engine-1 VAR(8) log Granger F for the 12 directed pairs |
| b5_ff / b5_egt | least-squares moments for the corrected-FF scatter and the EGT exponent grid |
| b6 | (phase, channel, [median, IQR, fast SD]) with NaN for phases with < 40 airborne samples |
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import partial

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import coherence, csd, welch

from phalanx.validation.battery.config import (
    A_GRID,
    B3_BANDS,
    B3_MIN_RUN_S,
    B3_NPERSEG,
    B3_PAIRS,
    B5_MIN_SAMPLES,
    B6_MIN_SAMPLES,
    FC_PRIMARY,
    FC_SENSITIVITY,
    LAG_PAIRS,
    MIN_AIR_SAMPLES,
    STEP_DIRS,
    STEP_MIN_D_LSB,
    STEP_MIN_DPLA_DEG,
    STEP_POST_S,
    STEP_PRE_S,
    STEP_R2_MIN,
    STEP_RESP,
    VAR_CH,
    VAR_MIN_SEGMENT_S,
    VAR_ORDER,
    VAR_UNIT,
    BatteryConfig,
)
from phalanx.validation.battery.filters import lowpass
from phalanx.validation.flightdata import FlightRecord

__all__ = [
    "B5Moments",
    "FlightStats",
    "airborne_mask",
    "b1_stats",
    "b2_stats",
    "b3_spectral",
    "b3_steps",
    "b4_granger",
    "b5_moments",
    "b6_stats",
    "find_steps",
    "flight_stats",
    "flight_stats_many",
    "fopdt",
    "longest_air_run",
]


@dataclass(frozen=True, eq=False)
class B5Moments:
    """Additive least-squares moments of one flight (summed over flights to fit a group).

    For the corrected-FF cubic: XtX (4, 4), Xty (4,), yy, sy, n (scalars).
    For the EGT exponent grid: XtX (3, 3), Xty (len(A_GRID), 3), yy and sy (len(A_GRID),), n.
    """

    XtX: np.ndarray
    Xty: np.ndarray
    yy: np.ndarray | float
    sy: np.ndarray | float
    n: float


@dataclass(frozen=True, eq=False)
class FlightStats:
    """All per-flight battery statistics of one (real or synthetic) flight; None = not computable."""

    flight_id: str
    air_frac: float
    b1_slow: np.ndarray | None = None
    b1_fast: np.ndarray | None = None
    b1h_slow: np.ndarray | None = None
    b1h_fast: np.ndarray | None = None
    b2: np.ndarray | None = None
    b3_coh: np.ndarray | None = None
    b3_lgain: np.ndarray | None = None
    b3_steps: np.ndarray | None = None
    b4: np.ndarray | None = None
    b5_ff: B5Moments | None = None
    b5_egt: B5Moments | None = None
    b6: np.ndarray | None = None

    def get(self, key: str) -> object | None:
        """Statistic by its round-2 key (`b1_fast`, `b2`, ..., `b5_ff`), None when absent."""
        return getattr(self, key, None)

    def has(self, key: str) -> bool:
        return self.get(key) is not None


# ---------------------------------------------------------------- helpers
def _stack(Y: Mapping[str, np.ndarray], cfg: BatteryConfig) -> np.ndarray:
    return np.vstack([Y[f][k] for f in cfg.families for k in range(cfg.n_units)])


def airborne_mask(Y: Mapping[str, np.ndarray], cfg: BatteryConfig) -> np.ndarray:
    """Airborne rule: every engine's N1 above the threshold (pre-registration section 4)."""
    return np.all(Y["N1"] > cfg.airborne_n1_min, axis=0)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    m = np.r_[False, mask, False].astype(int)
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


# ---------------------------------------------------------------- B1
def b1_stats(
    Y: Mapping[str, np.ndarray], cfg: BatteryConfig, fc: float = FC_PRIMARY
) -> tuple[np.ndarray, np.ndarray] | None:
    """Slow- and fast-band Pearson correlations of all channel pairs on airborne samples (B1)."""
    X = _stack(Y, cfg)
    air = airborne_mask(Y, cfg)
    if air.sum() < MIN_AIR_SAMPLES:
        return None
    slow = np.vstack([lowpass(x, cfg.rate_hz, fc) for x in X])
    fast = X - slow
    s, f = slow[:, air], fast[:, air]
    if not ((s.std(1) > 0) & (f.std(1) > 0)).all():
        return None
    iu = np.triu_indices(X.shape[0], 1)
    return np.corrcoef(s)[iu], np.corrcoef(f)[iu]


# ---------------------------------------------------------------- B2
def _lag(a: np.ndarray, b: np.ndarray, L: int, rate: float) -> float:
    """Lag [s] of the peak cross-correlation of z-scored a and b; positive = b lags a."""
    a = (a - a.mean()) / (a.std() + 1e-12)
    b = (b - b.mean()) / (b.std() + 1e-12)
    cc = [
        np.mean(a[: a.size - l] * b[l:]) if l >= 0 else np.mean(a[-l:] * b[: b.size + l])
        for l in range(-L, L + 1)
    ]
    return (int(np.argmax(cc)) - L) / rate


def b2_stats(Y: Mapping[str, np.ndarray], cfg: BatteryConfig) -> np.ndarray | None:
    """Lead-lag of first differences for the 5 pre-registered pairs, per engine (B2)."""
    air = airborne_mask(Y, cfg)
    if air.sum() < MIN_AIR_SAMPLES:
        return None
    out = []
    for k in range(cfg.n_units):
        for a, b in LAG_PAIRS:
            out.append(_lag(np.diff(Y[a][k][air]), np.diff(Y[b][k][air]), cfg.lag_samples, cfg.rate_hz))
    return np.array(out)


# ---------------------------------------------------------------- B3 (i)
def longest_air_run(
    Y: Mapping[str, np.ndarray], cfg: BatteryConfig, min_s: float = B3_MIN_RUN_S
) -> tuple[int, int] | None:
    """[start, end) of the longest airborne run if it lasts at least `min_s` seconds."""
    runs = _runs(airborne_mask(Y, cfg))
    if not runs:
        return None
    a, b = max(runs, key=lambda r: r[1] - r[0])
    return (a, b) if (b - a) >= min_s * cfg.rate_hz else None


def b3_spectral(
    Y: Mapping[str, np.ndarray], PLA: np.ndarray, cfg: BatteryConfig
) -> tuple[np.ndarray, np.ndarray] | None:
    """(coherence, log10 |H1| gain), each (n_units, 4 pairs, 3 bands), on the longest airborne run (B3 i)."""
    ab = longest_air_run(Y, cfg)
    if ab is None:
        return None
    a, b = ab
    coh = np.full((cfg.n_units, len(B3_PAIRS), len(B3_BANDS)), np.nan)
    lg = np.full_like(coh, np.nan)
    for k in range(cfg.n_units):
        sig = {"PLA": PLA[k][a:b]}
        for f in ("FF", "N2", "N1", "EGT"):
            sig[f] = Y[f][k][a:b]
        for j, (u, v) in enumerate(B3_PAIRS):
            x, y = sig[u] - sig[u].mean(), sig[v] - sig[v].mean()
            if x.std() == 0 or y.std() == 0:
                continue
            f, C = coherence(x, y, fs=cfg.rate_hz, nperseg=B3_NPERSEG, detrend="linear")
            _, Pxy = csd(x, y, fs=cfg.rate_hz, nperseg=B3_NPERSEG, detrend="linear")
            _, Pxx = welch(x, fs=cfg.rate_hz, nperseg=B3_NPERSEG, detrend="linear")
            H = np.abs(Pxy) / np.maximum(Pxx, 1e-300)
            for i, (lo, hi) in enumerate(B3_BANDS):
                m = (f >= lo) & (f < hi)
                coh[k, j, i] = float(np.mean(C[m]))
                lg[k, j, i] = float(np.log10(max(np.mean(H[m]), 1e-300)))
    return coh, lg


# ---------------------------------------------------------------- B3 (ii): round-1 transients.py detector
def fopdt(t: np.ndarray, y0: float, D: float, d: float, tau: float) -> np.ndarray:
    """First order plus dead time: y0 before t = d, then y0 + D (1 - exp(-(t - d)/tau))."""
    s = np.clip(t - d, 0, None)
    return y0 + D * (1 - np.exp(-s / tau))


def find_steps(pla: np.ndarray, rate: float = 4.0) -> list[tuple[int, float, float]]:
    """PLA steps (round-1 `analysis/dashlink_texture/transients.py`): (onset index, pre mean, post mean).

    |PLA(t+2 s) - PLA(t)| >= 5 deg; PLA range <= 1 deg over the 10 s before; <= 1.5 deg over [t+3 s, t+30 s];
    onset = first sample after which |PLA - pre-mean| > 0.5 deg. After a step the search resumes 30 s later.
    """
    r = rate
    n = pla.size
    out = []
    i = int(10 * r)
    while i < n - int(31 * r):
        if abs(pla[i + int(2 * r)] - pla[i]) >= 5:
            pre = pla[i - int(10 * r) : i + 1]
            post = pla[i + int(3 * r) : i + int(30 * r)]
            if np.ptp(pre) <= 1 and np.ptp(post) <= 1.5:
                pm = pre.mean()
                j = i
                while j < i + int(3 * r) and abs(pla[j] - pm) <= 0.5:
                    j += 1
                out.append((j, pm, post.mean()))
                i += int(30 * r)
                continue
        i += 1
    return out


def b3_steps(Y: Mapping[str, np.ndarray], PLA: np.ndarray, cfg: BatteryConfig) -> np.ndarray:
    """FOPDT time constants of N1/FF/EGT after PLA steps (B3 ii).

    Steps are detected on the input PLA, so real and synthetic versions of a flight share one step set.
    Kept: airborne at the onset, |dPLA| >= 5 deg, response change >= 5 recorder LSB, fit R^2 > 0.9.
    Returns (k, 3) rows (response index in STEP_RESP, direction index in STEP_DIRS, tau [s]).
    """
    air = airborne_mask(Y, cfg)
    pre, post = int(STEP_PRE_S * cfg.rate_hz), int(STEP_POST_S * cfg.rate_hz)
    n = Y["N1"].shape[1]
    out: list[tuple[float, float, float]] = []
    for e in range(cfg.n_units):
        for j, pm, qm in find_steps(PLA[e], cfg.rate_hz):
            if not air[j] or abs(qm - pm) < STEP_MIN_DPLA_DEG:
                continue
            a, b = j - pre, j + post
            if a < 0 or b > n:
                continue
            for gi, g in enumerate(STEP_RESP):
                y = Y[g][e][a:b].astype(float)
                t = (np.arange(y.size) - pre) / cfg.rate_hz
                y0, yf = y[:pre].mean(), y[-pre:].mean()
                D = yf - y0
                if abs(D) < STEP_MIN_D_LSB * cfg.lsb_rec[g]:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        p, _ = curve_fit(
                            fopdt,
                            t,
                            y,
                            p0=[y0, D, 0.5, 2.0],
                            bounds=([-np.inf, -np.inf, -2, 0.05], [np.inf, np.inf, 10, 60]),
                            maxfev=4000,
                        )
                except Exception:  # round-2 rule: a failed fit is skipped (any exception)
                    continue
                res = y - fopdt(t, *p)
                r2 = 1 - res.var() / y.var() if y.var() > 0 else np.nan
                if r2 > STEP_R2_MIN:
                    di = STEP_DIRS.index("accel" if qm > pm else "decel")
                    out.append((float(gi), float(di), float(p[3])))
    return np.array(out, float).reshape(-1, 3)


# ---------------------------------------------------------------- B4
def b4_granger(Y: Mapping[str, np.ndarray], cfg: BatteryConfig, p: int = VAR_ORDER) -> np.ndarray | None:
    """Engine-1 VAR(p) on first differences of [FF, N2, N1, EGT] over airborne segments >= 120 s (B4).

    One pooled regression per flight; log F for dropping the cause's p lags, for the 12 directed pairs in
    B4_PAIRS order [(c, e) for e in VAR_CH for c in VAR_CH if c != e].
    """
    nv = len(VAR_CH)
    Xs, Ys = [], []
    for a, b in _runs(airborne_mask(Y, cfg)):
        if b - a < VAR_MIN_SEGMENT_S * cfg.rate_hz:
            continue
        Z = np.column_stack([np.diff(Y[c][VAR_UNIT][a:b]) for c in VAR_CH])
        L = Z.shape[0]
        Xs.append(np.hstack([Z[p - j - 1 : L - j - 1] for j in range(p)]))
        Ys.append(Z[p:])
    if not Xs:
        return None
    X = np.vstack(Xs)
    Yv = np.vstack(Ys)
    X = np.column_stack([X, np.ones(X.shape[0])])
    n = X.shape[0]
    out = []
    for ei in range(nv):
        y = Yv[:, ei]
        bf, *_ = np.linalg.lstsq(X, y, rcond=None)
        rss_f = float(np.sum((y - X @ bf) ** 2))
        for ci in range(nv):
            if ci == ei:
                continue
            keep = [c for c in range(X.shape[1]) if c == X.shape[1] - 1 or (c % nv) != ci]
            Xr = X[:, keep]
            br, *_ = np.linalg.lstsq(Xr, y, rcond=None)
            rss_r = float(np.sum((y - Xr @ br) ** 2))
            if rss_f <= 0:
                out.append(np.nan)
                continue
            F = ((rss_r - rss_f) / p) / (rss_f / (n - X.shape[1]))
            out.append(float(np.log(max(F, 1e-6))))
    return np.array(out)


# ---------------------------------------------------------------- B5
def b5_moments(
    Y: Mapping[str, np.ndarray], theta: np.ndarray, delta: np.ndarray, cfg: BatteryConfig
) -> tuple[B5Moments, B5Moments] | None:
    """Least-squares moments for B5 on 1-Hz decimated airborne samples, pooled over engines.

    (i) corrected FF = FF / (delta sqrt(theta)) about a cubic in corrected N2 = N2 / sqrt(theta);
    (ii) EGT [K] / theta^a about a quadratic in N1 / sqrt(theta), for every a in A_GRID
    (method of `analysis/dashlink_texture/corrected_exponents.py`). Centring constants are numerical
    conditioning only (round-2 values).
    """
    air = airborne_mask(Y, cfg)
    idx = np.flatnonzero(air)[:: round(cfg.rate_hz)]
    if idx.size < B5_MIN_SAMPLES:
        return None
    th, de = theta[idx], delta[idx]
    sq = np.sqrt(th)
    t0k = cfg.kelvin_offset
    xs, ys, xn, tk = [], [], [], []
    for k in range(cfg.n_units):
        xs.append(Y["N2"][k][idx] / sq)
        ys.append(Y["FF"][k][idx] / (de * sq))
        xn.append(Y["N1"][k][idx] / sq)
        tk.append(Y["EGT"][k][idx] + t0k)
    x = (np.concatenate(xs) - 85.0) / 10.0
    y = np.concatenate(ys) / 1000.0
    V = np.vander(x, 4, increasing=True)
    m_ff = B5Moments(XtX=V.T @ V, Xty=V.T @ y, yy=float(y @ y), sy=float(y.sum()), n=float(y.size))
    xq = (np.concatenate(xn) - 70.0) / 20.0
    Vq = np.vander(xq, 3, increasing=True)
    th4 = np.tile(th, cfg.n_units)
    T = np.concatenate(tk)
    XtX = Vq.T @ Vq
    Xty, yy, sy = [], [], []
    lth = np.log(th4)
    for a in A_GRID:
        ya = T * np.exp(-a * lth) / 1000.0
        Xty.append(Vq.T @ ya)
        yy.append(float(ya @ ya))
        sy.append(float(ya.sum()))
    m_egt = B5Moments(XtX=XtX, Xty=np.array(Xty), yy=np.array(yy), sy=np.array(sy), n=float(T.size))
    return m_ff, m_egt


# ---------------------------------------------------------------- B6
def b6_stats(Y: Mapping[str, np.ndarray], PH: np.ndarray, cfg: BatteryConfig) -> np.ndarray:
    """(phase, channel, [median, IQR, fast SD]) of the airborne samples in each phase (B6).

    The fast band (x - lowpass 0.2 Hz) is filtered over the whole record; phases with < 40 airborne samples
    in the flight are NaN.
    """
    X = _stack(Y, cfg)
    air = airborne_mask(Y, cfg)
    fast = X - np.vstack([lowpass(x, cfg.rate_hz, FC_PRIMARY) for x in X])
    out = np.full((len(cfg.phase_codes), X.shape[0], 3), np.nan)
    for i, c in enumerate(cfg.phase_codes):
        m = air & (PH[: X.shape[1]] == c)
        if m.sum() < B6_MIN_SAMPLES:
            continue
        q = np.percentile(X[:, m], [25, 50, 75], axis=1)
        out[i, :, 0] = q[1]
        out[i, :, 1] = q[2] - q[0]
        out[i, :, 2] = fast[:, m].std(1)
    return out


# ---------------------------------------------------------------- per flight
def flight_stats(rec: FlightRecord, cfg: BatteryConfig | None = None) -> FlightStats:
    """All per-flight battery statistics for one (real or synthetic) flight."""
    cfg = cfg or BatteryConfig()
    cfg.check(rec)
    Y = {f: np.asarray(rec.outputs[f], float) for f in cfg.families}
    r1 = b1_stats(Y, cfg, FC_PRIMARY)
    r1h = b1_stats(Y, cfg, FC_SENSITIVITY)
    r3 = b3_spectral(Y, rec.pla, cfg)
    r5 = b5_moments(Y, rec.theta, rec.delta, cfg)
    return FlightStats(
        flight_id=rec.flight_id,
        air_frac=float(airborne_mask(Y, cfg).mean()),
        b1_slow=None if r1 is None else r1[0],
        b1_fast=None if r1 is None else r1[1],
        b1h_slow=None if r1h is None else r1h[0],
        b1h_fast=None if r1h is None else r1h[1],
        b2=b2_stats(Y, cfg),
        b3_coh=None if r3 is None else r3[0],
        b3_lgain=None if r3 is None else r3[1],
        b3_steps=b3_steps(Y, rec.pla, cfg),
        b4=b4_granger(Y, cfg),
        b5_ff=None if r5 is None else r5[0],
        b5_egt=None if r5 is None else r5[1],
        b6=b6_stats(Y, rec.phase, cfg),
    )


def flight_stats_many(
    records: Sequence[FlightRecord], cfg: BatteryConfig | None = None, max_workers: int | None = None
) -> list[FlightStats]:
    """`flight_stats` for many flights, in input order. Each flight is independent and deterministic, so the
    result does not depend on `max_workers` (1 = in-process; None = one process per CPU)."""
    fn = partial(flight_stats, cfg=cfg or BatteryConfig())
    if max_workers == 1 or len(records) <= 1:
        return [fn(r) for r in records]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(fn, records))
