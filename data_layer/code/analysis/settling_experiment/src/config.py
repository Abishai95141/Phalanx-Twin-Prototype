"""Constants for the Phalanx settling experiment (see ../PREREGISTRATION.md).

Nothing here is a fitted value. Fitted texture parameters live in results/model_params_*.json.
Data paths are never hard-coded: every script takes them as arguments.
"""
import os
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# keep every temporary / cache file inside the project tree (joblib memmaps, matplotlib and numba caches)
_TMP = os.path.normpath(os.path.join(HERE, "..", "..", "..", "research_sources", "settling_synthetic", "tmp"))
os.makedirs(_TMP, exist_ok=True)
os.environ.setdefault("JOBLIB_TEMP_FOLDER", _TMP)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(_TMP, "mplconfig"))
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(_TMP, "numba"))
TEXTURE_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "dashlink_texture"))
if TEXTURE_DIR not in sys.path:
    sys.path.insert(0, TEXTURE_DIR)

ROOT_SEED = 20261014          # pre-registered (section 1 and 7)
CAL_FRACTION = 0.40           # pre-registered (section 1)

FAMILIES = ["N1", "N2", "EGT", "FF"]
ENG = [f"{f}_{k}" for f in FAMILIES for k in range(1, 5)]   # 16 digital 4-Hz channels
VRTG = "VRTG"                                                 # 8-Hz analog channel
GROUP = ENG + [VRTG]

# Truth-extraction cut-offs (Hz). Primary is used for the verdict; the others are sensitivity runs.
FC = {
    "primary": {"ENG": 0.2, "VRTG": 0.5},
    "low": {"ENG": 0.05, "VRTG": 0.2},
    "high": {"ENG": 0.5, "VRTG": 1.0},
}
BUTTER_ORDER = 4

REGIMES = ["ground", "takeoff_roll", "climb", "cruise", "descent", "approach"]
REGIME_CODE = {r: i for i, r in enumerate(REGIMES)}
OTHER = 6
APPROACH_AGL_FT = 3000.0      # PH==6 airborne below this height above the landing field = approach
WINDOW_S = (64, 300)
MAX_WIN_PER_REGIME = 4
MIN_SEGMENT_S = 20            # whole-segment unit (take-off roll lasts ~25-30 s)
TAT_BIN_C = 10.0              # TAT bin width for regime x TAT matching

LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L6p"]   # L6p = L6' (old Gilbert-Elliott comparator)
LEVEL_NUM = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L5": 5, "L6": 6, "L6p": 6}

FEATURE_FAMILIES = ["quant", "noise", "spectral", "tails", "missing", "cross", "levels"]
TEXTURE_FAMILIES = ["quant", "noise", "spectral", "tails", "missing", "cross"]


def variant_name(arm, level, fc_key="primary"):
    return f"{arm}_{level}_{fc_key}"


def stable_int(s):
    return zlib.crc32(str(s).encode()) & 0xFFFFFFFF


def rng_for(*keys):
    """NumPy Generator from a SeedSequence keyed by (root seed, *keys) -- pre-registered section 7."""
    return np.random.default_rng(np.random.SeedSequence(ROOT_SEED, spawn_key=tuple(stable_int(k) for k in keys)))


def flight_id(path_or_name):
    return os.path.basename(path_or_name).replace(".mat", "")
