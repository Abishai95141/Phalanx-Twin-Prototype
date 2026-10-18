"""MF1-D per-flight extraction: masks, B1/B2 statistics and Welch sub-band spectral matrices per class.

For each 687-CAL flight (guarded path) this computes, without fitting anything:
- V1 format facts (channel rates, finiteness, sample counts) and V2 segment facts (K and samples per class);
- B1 fast-band correlations (`phalanx.validation.battery.stats.b1_stats`, ALL) and B2 lags (`b2_stats`, ALL);
- per class: the 20 x 20 fast-band time-domain correlation matrix (channels N1, N2, FF, EGT, PLA of
  engines 1-4), the Welch sub-band cross-power matrices P (32 x 20 x 20), K, the empirical HF white level
  per channel, pooled-run lead-lag (round-2 q02 method) and PLA activity.

Results are cached as one npz per flight in a git-ignored directory (runs/mf1/cache); the cache holds derived
spectra only, never raw samples.

Usage: python -I extract.py <mat_dir> <flight_order_json> <n_first> <cache_dir> [n_workers]
"""

from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir

import numpy as np
from common import cal_flights, guard_path
from spectral import csd_matrix, hf_white_level, segment_starts, subband

from phalanx.validation.battery.config import MIN_AIR_SAMPLES, BatteryConfig
from phalanx.validation.battery.filters import lowpass
from phalanx.validation.battery.stats import airborne_mask, b1_stats, b2_stats
from phalanx.validation.dashlink import load_mat, load_record

CFG = BatteryConfig()
FAMS = ("N1", "N2", "FF", "EGT", "PLA")
NE = 4
#: channel index of (family, engine k = 1..4)
CH = {(f, k): i * NE + (k - 1) for i, f in enumerate(FAMS) for k in range(1, NE + 1)}
CH_NAMES = [f"{f}_{k}" for f in FAMS for k in range(1, NE + 1)]
PHASES = {"CLB": 4, "CRZ": 5, "DES": 6}
CLASSES = (
    "ALL",
    "AT",
    "MAN",
    "CLB",
    "CRZ",
    "DES",
    "AT_CLB",
    "AT_CRZ",
    "AT_DES",
    "MAN_CLB",
    "MAN_CRZ",
    "MAN_DES",
    # DEVIATIONS.md D1 (added at verification): in-flight classes, because the airborne rule admits taxi at
    # ground idle (N1 25-26 %) and the pre-registered MAN class is then mostly taxi
    "FLT",
    "TAXI",
    "AT_FLT",
    "MAN_FLT",
)
K_MIN = {"ALL": 8}  # other classes: 6 (prereg section 3)
K_MIN_DEFAULT = 6
LAG_PAIRS = (("FF", "N2"), ("FF", "N1"), ("N2", "N1"), ("FF", "EGT"), ("N1", "EGT"), ("N2", "EGT"))
LAG_L = 40
RUN_MIN = 480  # 120 s at 4 Hz, as round-2 q02


def class_masks(air: np.ndarray, aten: np.ndarray, ph: np.ndarray) -> dict[str, np.ndarray]:
    m = {"ALL": air, "AT": air & (aten == 1), "MAN": air & (aten == 0)}
    for nm, code in PHASES.items():
        m[nm] = air & (ph == code)
        m[f"AT_{nm}"] = m["AT"] & (ph == code)
        m[f"MAN_{nm}"] = m["MAN"] & (ph == code)
    flt = np.isin(ph, (4, 5, 6))
    m["FLT"] = air & flt
    m["TAXI"] = air & (ph == 2)
    m["AT_FLT"] = m["AT"] & flt
    m["MAN_FLT"] = m["MAN"] & flt
    return m


def _runs(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    m = np.r_[False, mask, False].astype(np.int8)
    d = np.diff(m)
    return [
        (a, b)
        for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1), strict=True)
        if b - a >= min_len
    ]


def pooled_lag(xs: list[np.ndarray], ys: list[np.ndarray]) -> float:
    """Round-2 q02 pooled cross-correlation of first differences over runs; peak lag [s] (+ = y lags)."""
    num = np.zeros(2 * LAG_L + 1)
    cnt = np.zeros(2 * LAG_L + 1)
    for a, b in zip(xs, ys, strict=True):
        a = (a - a.mean()) / (a.std() + 1e-12)
        b = (b - b.mean()) / (b.std() + 1e-12)
        for i, lag in enumerate(range(-LAG_L, LAG_L + 1)):
            if lag >= 0:
                x, y = a[: a.size - lag], b[lag:]
            else:
                x, y = a[-lag:], b[: b.size + lag]
            num[i] += np.sum(x * y)
            cnt[i] += x.size
    cc = num / np.maximum(cnt, 1)
    return (int(np.argmax(cc)) - LAG_L) / 4.0


def extract(args: tuple[str, str, str, list[str]]) -> dict:
    fname, mat_dir, cache_dir, allowed = args
    path = guard_path(os.path.join(mat_dir, fname), mat_dir, set(allowed))
    rec = load_record(path)  # phalanx loader (its own raw2 guard stays active)
    F = load_mat(path)
    n = rec.n
    info: dict = {"file": fname, "n_samples": int(n)}
    # V1 formats
    rates = {}
    for f in ("N1", "N2", "EGT", "FF", "PLA"):
        for k in range(1, NE + 1):
            rates[f"{f}_{k}"] = float(F[f"{f}_{k}"].rate)
    rates["ATEN"] = float(F["ATEN"].rate)
    rates["PH"] = float(F["PH"].rate)
    info["rates"] = rates
    info["rates_ok"] = all(rates[c] == 4.0 for c in rates if c not in ("ATEN", "PH")) and (
        rates["ATEN"] == 1.0 and rates["PH"] == 1.0
    )
    info["finite_ok"] = bool(all(np.all(np.isfinite(v)) for v in rec.outputs.values())) and bool(
        np.all(np.isfinite(rec.pla))
    )
    aten = F["ATEN"].x.astype(int)
    t4 = np.arange(n) / 4.0
    aten4 = aten[np.minimum((t4 * F["ATEN"].rate).astype(int), aten.size - 1)]
    Y = {f: np.asarray(rec.outputs[f]) for f in ("N1", "N2", "EGT", "FF")}
    air = airborne_mask(Y, CFG)
    info["air_samples"] = int(air.sum())
    info["air_frac"] = float(air.mean())
    info["aten_values"] = sorted({int(v) for v in np.unique(aten)})
    # B1 / B2 (exact battery estimators, class ALL)
    b1 = b1_stats(Y, CFG)
    b2 = b2_stats(Y, CFG)
    # fast-band signals (B1 operator on the whole record)
    X = np.zeros((len(CH_NAMES), n))
    for (f, k), i in CH.items():
        x = rec.pla[k - 1] if f == "PLA" else Y[f][k - 1]
        X[i] = x - lowpass(np.asarray(x, float), 4.0, 0.2)
    masks = class_masks(air, aten4, np.asarray(rec.phase))
    out = {"b1_fast": b1[1] if b1 is not None else np.full(120, np.nan), "b2": b2 if b2 is not None else []}
    info["classes"] = {}
    for c in CLASSES:
        m = masks[c]
        starts = segment_starts(m)
        K = len(starts)
        ns = int(m.sum())
        kmin = K_MIN.get(c, K_MIN_DEFAULT)
        ph_m = np.asarray(rec.phase)[m]
        ci = {
            "samples": ns,
            "K": K,
            "included": bool(ns >= MIN_AIR_SAMPLES and K >= kmin),
            "ph_counts": {int(p): int(np.sum(ph_m == p)) for p in np.unique(ph_m)},
        }
        info["classes"][c] = ci
        if K >= 1:  # spectra kept for the pooled estimator even below the per-flight K rule (D1)
            G, _ = csd_matrix(X, starts)
            out[f"P_{c}"] = subband(G).astype(np.complex128)
            out[f"hf_{c}"] = hf_white_level(G)
            out[f"K_{c}"] = np.array(K)
        if ns < MIN_AIR_SAMPLES:
            continue
        Xm = X[:, m]
        sd = Xm.std(1)
        R = np.corrcoef(Xm) if np.all(sd > 0) else np.full((X.shape[0], X.shape[0]), np.nan)
        out[f"rtd_{c}"] = R
        if c == "ALL" and K >= 1:
            # V4 diagnostic: time-domain r on exactly the samples covered by the Welch segments, and on the
            # airborne samples not covered (short runs at the 25 % threshold, take-off/landing edges)
            cov = np.zeros(n, bool)
            for s0 in starts:
                cov[s0 : s0 + 512] = True
            for nm, mm in (("ALLSEG", m & cov), ("ALLNOSEG", m & ~cov)):
                Xs = X[:, mm]
                ok = mm.sum() >= 40 and np.all(Xs.std(1) > 0)
                out[f"rtd_{nm}"] = np.corrcoef(Xs) if ok else np.full((X.shape[0], X.shape[0]), np.nan)
                info["classes"][c][f"samples_{nm}"] = int(mm.sum())
                ph_s = np.asarray(rec.phase)[mm]
                info["classes"][c][f"ph_counts_{nm}"] = {
                    int(p): int(np.sum(ph_s == p)) for p in np.unique(ph_s)
                }
        # pooled-run lead-lag (q02 method, runs >= 120 s) and PLA activity
        rr = _runs(m, RUN_MIN)
        lags = np.full((NE, len(LAG_PAIRS)), np.nan)
        act = np.full(NE, np.nan)
        if sum(b - a for a, b in rr) >= MIN_AIR_SAMPLES:
            for k in range(1, NE + 1):
                for j, (u, v) in enumerate(LAG_PAIRS):
                    xs = [np.diff(Y[u][k - 1][a:b]) for a, b in rr]
                    ys = [np.diff(Y[v][k - 1][a:b]) for a, b in rr]
                    lags[k - 1, j] = pooled_lag(xs, ys)
                d = np.concatenate([np.diff(rec.pla[k - 1][a:b:4]) for a, b in rr])
                act[k - 1] = float(np.std(d))
        out[f"lag_{c}"] = lags
        out[f"plaact_{c}"] = act
    np.savez_compressed(os.path.join(cache_dir, fname.replace(".mat", ".npz")), **out)
    with open(os.path.join(cache_dir, fname.replace(".mat", ".json")), "w") as fh:
        json.dump(info, fh, indent=1)
    return info


def main(mat_dir: str, order_json: str, n_first: int, cache_dir: str, nw: int = 6) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    with open(order_json) as fh:
        order = json.load(fh)["order"]
    allowed = cal_flights()
    todo = [
        f for f in order[:n_first] if not os.path.exists(os.path.join(cache_dir, f.replace(".mat", ".npz")))
    ]
    args = [(f, mat_dir, cache_dir, allowed) for f in todo]
    if nw > 1 and len(args) > 1:
        with Pool(nw) as pool:
            infos = pool.map(extract, args)
    else:
        infos = [extract(a) for a in args]
    print(f"extracted {len(infos)} new flights; prefix n = {n_first}")


if __name__ == "__main__":
    main(
        sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 6
    )
