"""Shared I/O and small numerical helpers for the DASHlink Tail 687 texture analysis.

Data files are treated as untrusted *data*: they are only parsed with
scipy.io.loadmat (MAT v5), nothing in them is executed.
"""
from __future__ import annotations

import os
import re
import numpy as np
import scipy.io as sio

FLOAT32_EPS = np.finfo(np.float32).eps  # values in the files look float32-converted

PHASES = {0: "Unknown", 1: "Preflight", 2: "Taxi", 3: "Takeoff", 4: "Climb",
          5: "Cruise", 6: "Approach", 7: "Rollout"}  # DASHlink FAQ (2014)

FNAME_RE = re.compile(r"^(\d{3})(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(_1)?\.mat$")


def list_flights(mat_dir: str) -> list[str]:
    """Sorted list of absolute paths of .mat files in mat_dir (non-recursive)."""
    out = []
    for fn in sorted(os.listdir(mat_dir)):
        if fn.endswith(".mat") and FNAME_RE.match(fn):
            out.append(os.path.join(mat_dir, fn))
    return out


def parse_fname(path: str) -> dict:
    fn = os.path.basename(path)
    m = FNAME_RE.match(fn)
    if not m:
        return {"file": fn}
    tail, y, mo, d, h, mi, suf = m.groups()
    return {"file": fn, "tail": tail, "year": int(y), "month": int(mo), "day": int(d),
            "hour": int(h), "minute": int(mi), "dup_suffix": suf is not None,
            "datestr": f"{y}-{mo}-{d}T{h}:{mi}"}


class Param:
    __slots__ = ("name", "alpha", "desc", "units", "rate", "dtype", "raw", "x")

    def __init__(self, name, s):
        self.name = name
        self.alpha = str(getattr(s, "Alpha", name))
        self.desc = str(getattr(s, "Description", ""))
        u = getattr(s, "Units", "")
        self.units = u if isinstance(u, str) else ""
        self.rate = float(getattr(s, "Rate", np.nan))
        raw = np.atleast_1d(np.asarray(getattr(s, "data")))
        self.raw = raw
        self.dtype = str(raw.dtype)
        self.x = raw.astype(float)

    def t(self, t0: float = 0.0) -> np.ndarray:
        """Nominal sample times (s) assuming uniform spacing 1/rate from file start."""
        return t0 + np.arange(self.x.size) / self.rate


def load_flight(path: str) -> dict[str, Param]:
    m = sio.loadmat(path, squeeze_me=True, struct_as_record=False)
    out = {}
    for k, v in m.items():
        if k.startswith("__"):
            continue
        if hasattr(v, "_fieldnames") and "data" in v._fieldnames:
            out[k] = Param(k, v)
    return out


# ---------------------------------------------------------------- numerics

def lsb_estimate(x: np.ndarray):
    """Estimate the quantisation step (LSB) of a recorded series.

    Returns (lsb, grid_frac, n_unique) where
      lsb       : smallest recurring positive spacing between distinct values
                  (tolerant to float32 conversion jitter), NaN if <2 distinct values
      grid_frac : fraction of spacings between consecutive distinct values that are
                  integer multiples of lsb (1.0 = perfectly regular affine grid)
    """
    v = x[np.isfinite(x)]
    if v.size == 0:
        return np.nan, np.nan, 0
    u = np.unique(v)
    if u.size < 2:
        return np.nan, np.nan, int(u.size)
    scale = max(np.max(np.abs(u)), 1e-12)
    tol = 8 * FLOAT32_EPS * scale + 1e-12
    du = np.diff(u)
    du = du[du > tol]
    if du.size == 0:
        return np.nan, np.nan, int(u.size)
    dmin = du.min()
    near = du[du <= dmin + 2 * tol + 1e-3 * dmin]
    lsb = float(np.median(near))
    r = du / lsb
    grid = float(np.mean(np.abs(r - np.round(r)) <= (2 * tol / lsb + 1e-3)))
    return lsb, grid, int(u.size)


def run_lengths(mask: np.ndarray):
    """Lengths of consecutive True runs in a boolean array."""
    if mask.size == 0:
        return np.array([], dtype=int)
    m = np.concatenate(([False], mask.astype(bool), [False]))
    d = np.diff(m.astype(int))
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    return ends - starts


def run_bounds(mask: np.ndarray):
    m = np.concatenate(([False], mask.astype(bool), [False]))
    d = np.diff(m.astype(int))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


def constant_runs(x: np.ndarray, tol: float = 0.0):
    """Lengths (samples) of runs of identical consecutive values (run length >=1)."""
    if x.size == 0:
        return np.array([], dtype=int)
    same = np.abs(np.diff(x)) <= tol
    # a run of k identical samples corresponds to k-1 consecutive 'same' flags
    rl = run_lengths(same) + 1
    n_single = x.size - rl.sum()
    return np.concatenate([rl, np.ones(max(n_single, 0), dtype=int)])


def isolated_spikes(x: np.ndarray, thr: float) -> int:
    """Count single-sample excursions: |x_t - x_{t-1}|>thr, |x_t - x_{t+1}|>thr,
    opposite signs, and the neighbours agree to within thr/2."""
    if x.size < 3 or not np.isfinite(thr) or thr <= 0:
        return 0
    a = x[1:-1] - x[:-2]
    b = x[1:-1] - x[2:]
    c = np.abs(x[2:] - x[:-2])
    ok = (np.abs(a) > thr) & (np.abs(b) > thr) & (np.sign(a) == np.sign(b)) & (c < thr / 2)
    return int(np.nansum(ok))


def robust_sigma(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if x.size < 3:
        return np.nan
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def resample_to(x: np.ndarray, rate_from: float, rate_to: float) -> np.ndarray:
    """Align a series to another rate by sample-and-hold (up) or block mean (down),
    assuming both series start at the same instant (frame-aligned)."""
    if rate_from == rate_to:
        return x
    if rate_from < rate_to:
        k = int(round(rate_to / rate_from))
        return np.repeat(x, k)
    k = int(round(rate_from / rate_to))
    n = (x.size // k) * k
    return x[:n].reshape(-1, k).mean(axis=1)
