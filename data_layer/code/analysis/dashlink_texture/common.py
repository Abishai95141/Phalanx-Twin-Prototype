"""Shared analysis helpers: steady-window detection, sentinel cleaning, residual metrics."""
import os
import csv

import numpy as np
from scipy.signal import savgol_filter, welch

ENG_GROUPS = ["N1", "N2", "EGT", "FF", "OIP", "OIT", "VIB"]
ENG = [f"{g}_{i}" for g in ENG_GROUPS for i in range(1, 5)]
AIR = ["ALT", "BAL1", "CAS", "MACH", "TAS", "TAT", "SAT", "AOA1", "AOA2", "AOAC", "PTCH", "ROLL",
       "VRTG", "LATG", "LONG", "FPAC", "BLAC", "CTAC", "TH", "IVV", "ALTR", "PT", "PS", "PI", "GS",
       "N1C", "PLA_1", "FQTY_1", "WS"]
ANGLE_WRAP = {"TH", "MH", "TRK", "TRKM", "WD"}
SG_SECONDS = 30.0  # Savitzky-Golay detrending window (s), polyorder 2


def read_csv(path):
    return list(csv.DictReader(open(path)))


def load_lsb(res):
    t = {}
    for r in read_csv(os.path.join(res, "param_table.csv")):
        try:
            t[r["param"]] = float(r["lsb_mode"])
        except ValueError:
            t[r["param"]] = np.nan
    return t


def load_sentinels(res, min_iso_per_hour=0.1):
    """Sentinel (end-of-scale dropout) values per parameter, from dropouts.py."""
    s = {}
    for r in read_csv(os.path.join(res, "dropouts_sentinels.csv")):
        if float(r["isolated_per_record_hour"]) >= min_iso_per_hour:
            s.setdefault(r["param"], []).append(float(r["value"]))
    return s


def unwrap_deg(x):
    return np.rad2deg(np.unwrap(np.deg2rad(x)))


def clean(x, sentinels, lsb):
    """Replace sentinel-valued samples (if the segment median is far from the sentinel)
    by linear interpolation. Returns (clean_x, n_replaced)."""
    x = x.astype(float).copy()
    if not sentinels:
        return x, 0
    med = np.median(x)
    bad = np.zeros(x.size, bool)
    tol = max(10 * (lsb if np.isfinite(lsb) else 0), 1e-9)
    for v in sentinels:
        if abs(med - v) > tol:
            bad |= np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
    n = int(bad.sum())
    if n and n < x.size:
        i = np.arange(x.size)
        x[bad] = np.interp(i[bad], i[~bad], x[~bad])
    return x, n


def per_second(F, name, how="mean"):
    p = F[name]
    k = int(round(p.rate))
    x = p.x
    if name in ANGLE_WRAP:
        x = unwrap_deg(x)
    if k <= 1:
        return x.copy()
    n = (x.size // k) * k
    X = x[:n].reshape(-1, k)
    if how == "mean":
        return X.mean(1)
    if how == "absmax":
        return np.abs(X).max(1)
    raise ValueError(how)


def find_windows(ok, W, cond, step=None):
    """Greedy non-overlapping windows of W seconds inside runs of ok (1-Hz bool),
    accepted when cond(t0, t1) is True."""
    step = step or max(int(W // 5), 1)
    out = []
    m = np.concatenate(([False], ok, [False])).astype(int)
    d = np.diff(m)
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
        t = a
        while t + W <= b:
            if cond(t, t + W):
                out.append((t, t + W))
                t += W
            else:
                t += step
    return out


def regime_windows(F):
    """Return dict regime -> list of (t0, t1) seconds.

    cruise      : PH==5, airborne, 300 s, ALT range<=150 ft, CAS range<=8 kt, |roll|<=5 deg,
                  every PLA range<=8 deg and no 1-s PLA step >1.5 deg (autothrottle trim allowed:
                  A/T is engaged in cruise and moves the levers continuously)
    climb       : PH==4, airborne, 120 s, mean ALTR>500 ft/min, |roll|<=5 deg, every PLA range<=2 deg
    ground_idle : PH in {1,2}, WOW==0 (on ground; WOW is inverted), 120 s, >=2 engines with
                  N2>=40 %, PLA<=30 deg and PLA range<=0.5 deg (engines shut down during taxi are
                  excluded per engine by engine_ok())
    """
    ph = F["PH"].x
    wow = F["WOW"].x
    n = ph.size
    alt = per_second(F, "ALT")[:n]
    cas = per_second(F, "CAS")[:n]
    roll = per_second(F, "ROLL", "absmax")[:n]
    altr = per_second(F, "ALTR")[:n]
    pla = np.vstack([per_second(F, f"PLA_{i}")[:n] for i in range(1, 5)])
    dpla = np.abs(np.diff(pla, axis=1, prepend=pla[:, :1]))
    n2 = np.vstack([per_second(F, f"N2_{i}")[:n] for i in range(1, 5)])

    def rng(x, a, b):
        return np.ptp(x[..., a:b], axis=-1)

    def cruise(a, b):
        return (rng(alt, a, b) <= 150 and rng(cas, a, b) <= 8 and roll[a:b].max() <= 5
                and np.all(rng(pla, a, b) <= 8) and dpla[:, a:b].max() <= 1.5)

    def climb(a, b):
        return (altr[a:b].mean() > 500 and roll[a:b].max() <= 5 and np.all(rng(pla, a, b) <= 2))

    def gidle(a, b):
        run = (n2[:, a:b].min(1) >= 40) & (pla[:, a:b].max(1) <= 30) & (rng(pla, a, b) <= 0.5)
        return run.sum() >= 2

    return {
        "cruise": find_windows((ph == 5) & (wow == 1), 300, cruise),
        "climb": find_windows((ph == 4) & (wow == 1), 120, climb),
        "ground_idle": find_windows(((ph == 1) | (ph == 2)) & (wow == 0), 120, gidle),
    }


def engine_ok(F, engine, t0, t1, regime):
    """For ground_idle: engine running (N2>=40 %), PLA<=30 deg and steady. Always True otherwise."""
    if regime != "ground_idle":
        return True
    n2, _ = segment(F, f"N2_{engine}", t0, t1)
    pla, _ = segment(F, f"PLA_{engine}", t0, t1)
    return n2.min() >= 40 and pla.max() <= 30 and np.ptp(pla) <= 0.5


def segment(F, name, t0, t1):
    p = F[name]
    a, b = int(round(t0 * p.rate)), int(round(t1 * p.rate))
    x = p.x[a:b]
    if name in ANGLE_WRAP:
        x = unwrap_deg(x)
    return x, p.rate


def sg_residual(x, rate, seconds=SG_SECONDS):
    L = int(round(seconds * rate)) | 1
    if x.size < L + 2:
        L = (x.size - 2) | 1
        if L < 5:
            return x - x.mean()
        L = L if L < x.size else L - 2
    return x - savgol_filter(x, L, 2, mode="interp")


def acf(r, maxlag):
    r = r - r.mean()
    v = np.dot(r, r)
    if v == 0:
        return np.full(maxlag + 1, np.nan)
    n = r.size
    return np.array([np.dot(r[: n - k], r[k:]) / v for k in range(maxlag + 1)])


def decorr_time(ac, rate):
    """First lag (s) at which the ACF drops below 1/e (linear interpolation)."""
    if not np.isfinite(ac).all():
        return np.nan
    below = np.flatnonzero(ac < np.exp(-1))
    if below.size == 0:
        return np.nan
    k = below[0]
    if k == 0:
        return 0.0
    y0, y1 = ac[k - 1], ac[k]
    frac = (y0 - np.exp(-1)) / (y0 - y1) if y0 != y1 else 0
    return (k - 1 + frac) / rate


def allan_dev(x, rate, max_frac=1 / 3):
    """Overlapping Allan deviation at tau = m/rate, m = 1,2,4,..."""
    n = x.size
    taus, adev = [], []
    m = 1
    cs = np.concatenate(([0.0], np.cumsum(x)))
    while m <= n * max_frac:
        avg = (cs[m:] - cs[:-m]) / m  # running means of length m
        d = avg[m:] - avg[:-m]
        if d.size < 2:
            break
        taus.append(m / rate)
        adev.append(np.sqrt(0.5 * np.mean(d ** 2)))
        m *= 2
    return np.array(taus), np.array(adev)


def psd(r, rate, seg_seconds=64.0):
    nper = int(min(r.size, seg_seconds * rate))
    f, p = welch(r, fs=rate, nperseg=nper, noverlap=nper // 2, detrend="linear")
    return f, p
