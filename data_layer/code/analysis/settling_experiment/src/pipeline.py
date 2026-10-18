"""Shared measurement pipeline (identical for real and synthetic files).

* regime labels per second from channels OUTSIDE the channel group (PH, WOW, ALT), so real and
  synthetic versions of a flight get identical regimes and windows;
* truth extraction (pre-registration section 2): sentinels identified with common.load_sentinels /
  common.clean and linearly interpolated, then a zero-phase 4th-order Butterworth low-pass
  (scipy.signal.butter(4, fc) applied with sosfiltfilt, odd padding of 3 rate/fc samples);
* lattices: engine channels k*LSB; VRTG float32(code)*float32(a) + float32(b) (fitted on 687-CAL,
  reproduces every observed value bit for bit);
* window and segment selection.
"""
import os

import numpy as np
from scipy.signal import butter, sosfiltfilt

import config as C
from dlio import load_flight  # noqa: F401  (re-exported)
from common import load_sentinels, load_lsb, clean

_SOS = {}


def lowpass(x, rate, fc):
    key = (rate, fc)
    if key not in _SOS:
        _SOS[key] = butter(C.BUTTER_ORDER, fc, btype="low", fs=rate, output="sos")
    if x.size < 64:
        return np.full(x.size, x.mean())
    # Gate-0 fix (DEVIATIONS.md C3): pad with an odd extension of 3 filter time constants (3 rate/fc samples)
    # instead of scipy's default ~15 samples, so the truth has no start-up transient at the record edges.
    return sosfiltfilt(_SOS[key], x, padlen=min(x.size - 1, int(np.ceil(3 * rate / fc))))


class Pipe:
    """Holds the sentinel / LSB tables of the existing texture analysis."""

    def __init__(self, tex_res, lattice=None):
        self.sent = load_sentinels(tex_res)          # pre-registered cleaning rule
        self.lsb = load_lsb(tex_res)
        self.lattice = lattice or {}                  # {"VRTG": {"a": .., "b": ..}}

    # ------------------------------------------------------------- per channel
    def sentinel_mask(self, name, x):
        m = np.zeros(x.size, bool)
        for v in self.sent.get(name, []):
            m |= np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
        return m

    def truth(self, name, x, rate, fc):
        xc, _ = clean(x, self.sent.get(name, []), self.lsb.get(name, np.nan))
        return xc, lowpass(xc, rate, fc)

    def step(self, name):
        if name == C.VRTG and name in self.lattice:
            return float(self.lattice[name]["a"])
        return float(self.lsb[name])

    def quantize(self, name, y):
        """Round a continuous series onto the channel's recording lattice."""
        if name == C.VRTG:
            a, b = self.lattice[name]["a"], self.lattice[name]["b"]
            code = np.clip(np.rint((y - b) / a), 1, 4095)        # code 0 is the zero-count sentinel
            return (code.astype(np.float32) * np.float32(a) + np.float32(b)).astype(np.float64)
        L = self.lsb[name]
        return L * np.rint(y / L)

    def lattice_frac(self, name, v):
        """Signed distance of values from the channel lattice, in steps (0 = on lattice)."""
        if name == C.VRTG and name in self.lattice:
            a, b = self.lattice[name]["a"], self.lattice[name]["b"]
            q = (v - b) / a
        else:
            q = v / self.lsb[name]
        return q - np.rint(q)


# ------------------------------------------------------------------ regimes

def per_second_mean(p, n):
    k = int(round(p.rate))
    x = p.x
    if k <= 1:
        return x[:n].astype(float)
    m = (x.size // k) * k
    return x[:m].reshape(-1, k).mean(1)[:n]


def regimes(F):
    """Per-second regime code (config.REGIMES index, 6 = other) and per-second TAT."""
    ph = F["PH"].x.astype(int)
    wow = F["WOW"].x.astype(int)
    n = ph.size
    alt = per_second_mean(F["ALT"], n)
    n = min(n, alt.size)
    ph, wow, alt = ph[:n], wow[:n], alt[:n]
    air = np.flatnonzero(wow == 1)
    if air.size:
        after = np.arange(n) > air[-1]
        gnd = after & (wow == 0)
        field = np.median(alt[gnd]) if gnd.sum() >= 10 else np.median(alt[wow == 0]) if (wow == 0).any() else 0.0
    else:
        field = np.median(alt)
    lab = np.full(n, C.OTHER, int)
    lab[(wow == 0) & ((ph == 1) | (ph == 2))] = C.REGIME_CODE["ground"]
    lab[(wow == 0) & (ph == 3)] = C.REGIME_CODE["takeoff_roll"]
    lab[(wow == 1) & (ph == 4)] = C.REGIME_CODE["climb"]
    lab[(wow == 1) & (ph == 5)] = C.REGIME_CODE["cruise"]
    hi = alt - field >= C.APPROACH_AGL_FT
    lab[(wow == 1) & (ph == 6) & hi] = C.REGIME_CODE["descent"]
    lab[(wow == 1) & (ph == 6) & ~hi] = C.REGIME_CODE["approach"]
    tat = per_second_mean(F["TAT"], n)
    cas = per_second_mean(F["CAS"], n)
    return lab, tat, cas


def runs(lab, code):
    m = np.r_[False, lab == code, False].astype(int)
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def all_runs(lab):
    """List of (code, start, end) for every contiguous run of a label."""
    out = []
    s = 0
    for i in range(1, lab.size + 1):
        if i == lab.size or lab[i] != lab[s]:
            out.append((int(lab[s]), s, i))
            s = i
    return out


def windows(lab, fid):
    """{W: [(regime, t0, t1)]} for W in 64/300 s plus 'seg' = longest run per regime (>= 20 s).
    Deterministic given the flight id; identical for the real and synthetic versions of a flight."""
    out = {}
    for W in C.WINDOW_S:
        wl = []
        for r, rname in enumerate(C.REGIMES):
            rng = C.rng_for("windows", fid, rname, W)
            cand = []
            for a, b in runs(lab, r):
                L = b - a
                if L < W:
                    continue
                o = int(rng.integers(0, L - W * (L // W) + 1))
                cand.extend((a + o + j * W, a + o + (j + 1) * W) for j in range(L // W) if a + o + (j + 1) * W <= b)
            if len(cand) > C.MAX_WIN_PER_REGIME:
                idx = np.sort(rng.choice(len(cand), C.MAX_WIN_PER_REGIME, replace=False))
                cand = [cand[i] for i in idx]
            wl.extend((r, a, b) for a, b in cand)
        out[W] = wl
    seg = []
    for r in range(len(C.REGIMES)):
        rr = [(b - a, a, b) for a, b in runs(lab, r) if b - a >= C.MIN_SEGMENT_S]
        if rr:
            L, a, b = max(rr)
            seg.append((r, a, b))
    out["seg"] = seg
    return out
