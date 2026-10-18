"""Round-2 shared constants, seeds and the flight loader (see ../PREREGISTRATION.md).

Data files are untrusted data: they are only parsed with scipy.io.loadmat through the round-1 loader
(analysis/dashlink_texture/dlio.py, imported read-only), never executed. Data paths are always passed in as
arguments; only the scratch/cache directory is derived from this file's location (inside research_sources/,
which is gitignored).

Flight representation (all at 4 Hz, aligned on the 4-Hz sample grid of the engine words):
  inputs : PLA (4, n) deg, ALT ft, MACH, TAT degC (1 Hz -> 4 Hz linear interpolation), PH (1 Hz, held),
           theta = (TAT + 273.15) / 288.15, delta = delta_s(ALT) * (1 + 0.2 M^2)^3.5 (ISA, inlet total pressure)
  outputs: Y[ch] (4, n) for ch in N1, N2, EGT, FF  (recorded values, float)
"""
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
R2DIR = os.path.abspath(os.path.join(HERE, ".."))
SCRATCH = os.path.join(ROOT, "research_sources", "settling_round2_synthetic")
_TMP = os.path.join(SCRATCH, "tmp")
os.makedirs(_TMP, exist_ok=True)
os.environ.setdefault("JOBLIB_TEMP_FOLDER", _TMP)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(_TMP, "mplconfig"))
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(_TMP, "numba"))

TEXTURE_DIR = os.path.join(ROOT, "analysis", "dashlink_texture")
R1_SRC = os.path.join(ROOT, "analysis", "settling_experiment", "src")
R1_RES = os.path.join(ROOT, "analysis", "settling_experiment", "results")
for p in (TEXTURE_DIR,):
    if p not in sys.path:
        sys.path.insert(0, p)
if R1_SRC not in sys.path:
    sys.path.append(R1_SRC)          # appended: round-2 modules shadow nothing of round 1 by name

from dlio import load_flight  # noqa: E402

ROOT_SEED = 20261015          # pre-registered (section 7)
RATE = 4.0
DT = 1.0 / RATE
FAM = ["N1", "N2", "EGT", "FF"]                       # channel families (output order used everywhere)
CH16 = [f"{p}_{k}" for p in FAM for k in (1, 2, 3, 4)]   # B1 order (as analysis/correlation_check)
LSB_REC = {"N1": 0.03125, "N2": 0.03125, "EGT": 0.5, "FF": 8.0}
T0K = 273.15


def stable_int(s):
    return zlib.crc32(str(s).encode()) & 0xFFFFFFFF


def rng_for(*keys):
    """Generator from SeedSequence(root 20261015, spawn_key = keys) -- streams keyed by (flight, engine, component)."""
    return np.random.default_rng(np.random.SeedSequence(ROOT_SEED, spawn_key=tuple(stable_int(k) for k in keys)))


def flight_id(p):
    return os.path.basename(p).replace(".mat", "")


# ------------------------------------------------------------------ atmosphere
def delta_static(alt_ft):
    h = np.asarray(alt_ft, float)
    tropo = (1.0 - 6.87559e-6 * np.minimum(h, 36089.0)) ** 5.2559
    strat = np.exp(-4.80634e-5 * np.maximum(h - 36089.0, 0.0))
    return tropo * strat


def corrections(alt, mach, tat):
    theta = (np.asarray(tat, float) + T0K) / 288.15
    delta = delta_static(alt) * (1.0 + 0.2 * np.asarray(mach, float) ** 2) ** 3.5
    return theta, delta


# ------------------------------------------------------------------ loader
def _clean_mach(m):
    """MACH = 0 is the channel's sentinel in flight (dlio tables); isolated zeros whose 2-s neighbourhood is
    well above 0.15 are interpolated. Ground zeros (genuine low speed) are kept."""
    m = m.astype(float).copy()
    z = m == 0
    if z.any():
        k = 9
        pad = np.r_[np.full(k, m[0]), m, np.full(k, m[-1])]
        from numpy.lib.stride_tricks import sliding_window_view
        nb = np.median(sliding_window_view(pad, 2 * k + 1), axis=1)
        bad = z & (nb > 0.15)
        if bad.any() and (~bad).any():
            i = np.arange(m.size)
            m[bad] = np.interp(i[bad], i[~bad], m[~bad])
    return m


def load(path, with_outputs=True):
    """Return dict with 4-Hz aligned inputs and (optionally) outputs. n = number of 4-Hz engine samples."""
    F = load_flight(path)
    n = min(F[f"N1_{k}"].x.size for k in (1, 2, 3, 4))
    n = min(n, F["PLA_1"].x.size, F["ALT"].x.size, F["MACH"].x.size)
    t4 = np.arange(n) * DT
    tat1 = F["TAT"].x.astype(float)
    tat = np.interp(t4, np.arange(tat1.size) / F["TAT"].rate, tat1)
    ph = F["PH"].x.astype(int)
    ph4 = ph[np.minimum((t4 * F["PH"].rate).astype(int), ph.size - 1)]
    wow = F["WOW"].x.astype(int)
    wow4 = wow[np.minimum((t4 * F["WOW"].rate).astype(int), wow.size - 1)]
    alt = F["ALT"].x[:n].astype(float)
    mach = _clean_mach(F["MACH"].x[:n])
    th, de = corrections(alt, mach, tat)
    d = {"fid": flight_id(path), "n": n, "PLA": np.vstack([F[f"PLA_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)]),
         "ALT": alt, "MACH": mach, "TAT": tat, "PH": ph4, "WOW": wow4, "theta": th, "delta": de}
    if with_outputs:
        d["Y"] = {f: np.vstack([F[f"{f}_{k}"].x[:n].astype(float) for k in (1, 2, 3, 4)]) for f in FAM}
        d["dtype"] = {f"{f}_{k}": F[f"{f}_{k}"].dtype for f in FAM for k in (1, 2, 3, 4)}
        d["nraw"] = {f"{f}_{k}": F[f"{f}_{k}"].x.size for f in FAM for k in (1, 2, 3, 4)}
    return d


def splits(path_csv=None):
    import csv
    path_csv = path_csv or os.path.join(R1_RES, "splits.csv")
    return list(csv.DictReader(open(path_csv)))


def cal_files(path_csv=None):
    return sorted(r["file"] for r in splits(path_csv) if r["set"] == "687-CAL")
