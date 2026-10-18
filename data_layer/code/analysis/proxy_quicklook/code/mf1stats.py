"""MF1 statistics of one flight record (real or synthetic), with the M20 battery estimators and the MF1-D
spectral estimators. The same function is applied to the real CAL record and to the synthetic record of the
same window, so every comparison is estimator-for-estimator.

Per record:
- **B1** (`phalanx.validation.battery.stats.b1_stats`): fast-band (x - Butterworth-4 low-pass 0.2 Hz)
  Pearson correlations of all 16 channels on the record's own airborne samples (all four N1 > 25 %); the
  within-engine pairs N1-N2, N1-FF, N2-FF, N1-EGT, N2-EGT, FF-EGT and the cross-engine pairs N1_i-N1_j,
  N2_i-N2_j, EGT_i-EGT_j are extracted (engine 1 and the mean over engines / engine pairs).
- **B2** (`b2_stats`): lead-lag of first differences for the battery pairs FF->N2, FF->N1, N2->N1, FF->EGT,
  N1->EGT, per engine (+ = second channel lags).
- **Classes** (MF1-D DEVIATIONS D1/D2): the same fast-band correlation restricted to the airborne samples of
  FLT (PH 4-6), CLB (4), CRZ (5), DES (6), TAXI (2), AT_FLT (FLT and A/T engaged); the taxi share of the
  airborne samples (the composition the 25 % rule admits).
- **Spectral** (MF1-D `spectral.py`, unchanged: Welch 512/256 Hann on the fast-band signals, 32 sub-bands of
  0.0625 Hz, pair decomposition): for N2->N1, FF->N1, N2->FF, N1->EGT, N2->EGT, FF->EGT in classes ALL and
  FLT: r_spec, r_lag (phase ceiling), coherent fraction, tau_eq (phase slope 0.2-1 Hz), coherence and phase
  per report band (0.19-0.5, 0.5-1, 1-2 Hz), and the H1 gain per band (|sum P_ij| / sum P_ii). Texture
  power T_q (native + recorder quantisation, MF1-D prereg §4.5) enters only Q and r_truth.

Engines are statistically exchangeable in both data sets; engine 1 is primary (as MF1-D), the engine mean is
reported for stability.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from spectral import (  # MF1-D estimators (analysis/mf1_lp_structure/code; common.py puts them on the path)
    NSUB,
    REPORT_BANDS,
    SUB_FC,
    csd_matrix,
    pair_decomposition,
    segment_starts,
    subband,
    white_subband_power,
)

from phalanx.validation.battery.config import MIN_AIR_SAMPLES, BatteryConfig
from phalanx.validation.battery.filters import lowpass
from phalanx.validation.battery.stats import airborne_mask, b1_stats, b2_stats
from phalanx.validation.flightdata import FlightRecord

CFG = BatteryConfig()
FAMS = ("N1", "N2", "EGT", "FF")
NE = 4
CH16 = [f"{f}_{k}" for f in FAMS for k in range(1, NE + 1)]
_IU = np.triu_indices(16, 1)
PAIR_INDEX = {frozenset((CH16[i], CH16[k])): n for n, (i, k) in enumerate(zip(*_IU, strict=True))}
WITHIN = (("N1", "N2"), ("N1", "FF"), ("N2", "FF"), ("N1", "EGT"), ("N2", "EGT"), ("FF", "EGT"))
CROSS = ("N1", "N2", "EGT", "FF")
CLASSES = ("ALL", "FLT", "CLB", "CRZ", "DES", "TAXI", "AT_FLT", "GOV", "GOVFLT")
SPECTRAL_CLASSES = ("ALL", "FLT", "GOV")
#: (cause, effect): the effect's phase/gain relative to the cause (tau_eq > 0 = effect lags)
SPEC_PAIRS = (("N2", "N1"), ("FF", "N1"), ("N2", "FF"), ("N1", "EGT"), ("N2", "EGT"), ("FF", "EGT"))
B2_PAIRS = (("FF", "N2"), ("FF", "N1"), ("N2", "N1"), ("FF", "EGT"), ("N1", "EGT"))
#: texture floors T_q: native and recorder quantisation (MF1-D analyse.py LSB, prereg §4.5) [EU]
LSB = {"N1": (0.04, 0.03125), "N2": (0.04, 0.03125), "EGT": (0.8, 0.5), "FF": (None, 8.0)}
TQ16 = np.array([((LSB[f][0] or 0.0) ** 2 + LSB[f][1] ** 2) / 12.0 for f in FAMS for _ in range(NE)])
K_MIN = 6


def _b1_pair(fast: np.ndarray, a: str, b: str) -> float:
    return float(fast[PAIR_INDEX[frozenset((a, b))]])


def class_masks(rec: FlightRecord, aten: np.ndarray, gov: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Class masks on the record's own airborne samples. ``gov`` (paired, from the synthetic run): samples at
    which every synthetic engine's fuel is on the N2 governor (no clamp or limiter): the GOV classes compare
    real and synthetic on the segments where the un-identified proxy plant operates in its governed regime
    (A-W2.4a-19)."""
    Y = {f: np.asarray(rec.outputs[f]) for f in FAMS}
    air = airborne_mask(Y, CFG)
    ph = np.asarray(rec.phase)
    flt = np.isin(ph, (4, 5, 6))
    g = np.zeros_like(air) if gov is None else np.asarray(gov, bool)[: air.size]
    return {
        "GOV": air & g,
        "GOVFLT": air & flt & g,
        "ALL": air,
        "FLT": air & flt,
        "CLB": air & (ph == 4),
        "CRZ": air & (ph == 5),
        "DES": air & (ph == 6),
        "TAXI": air & (ph == 2),
        "AT_FLT": air & flt & (np.asarray(aten)[: ph.size] == 1),
    }


def fast_band(rec: FlightRecord) -> np.ndarray:
    """(16, n) fast-band signals in B1 channel order (the B1 operator on the whole record)."""
    X = np.vstack([np.asarray(rec.outputs[f], float) for f in FAMS])
    return np.vstack([x - lowpass(x, CFG.rate_hz, 0.2) for x in X])


def _corr(Xm: np.ndarray, i: int, j: int) -> float:
    a, b = Xm[i], Xm[j]
    sa, sb = a.std(), b.std()
    if sa <= 0 or sb <= 0:
        return float("nan")
    return float(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb))


def _ch(f: str, k: int) -> int:
    return CH16.index(f"{f}_{k}")


def class_stats(X: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """Time-domain fast-band r of the within-engine pairs (engine 1 and mean) and cross-engine pairs on a
    class mask (B1 estimator restricted to the class, as MF1-D's r_class)."""
    out: dict[str, float] = {"n": int(mask.sum())}
    if mask.sum() < MIN_AIR_SAMPLES:
        return out
    Xm = X[:, mask]
    for a, b in WITHIN:
        v = [_corr(Xm, _ch(a, k), _ch(b, k)) for k in range(1, NE + 1)]
        out[f"{a}-{b}"] = v[0]
        out[f"{a}-{b}_mean"] = float(np.nanmean(v))
    for f in CROSS:
        v = [_corr(Xm, _ch(f, i), _ch(f, j)) for i in range(1, NE + 1) for j in range(i + 1, NE + 1)]
        out[f"{f}x"] = v[0]  # engines 1-2
        out[f"{f}x_mean"] = float(np.nanmean(v))
    return out


def _band_gain(P: np.ndarray, i: int, j: int) -> list[float]:
    Pii = np.real(P[:, i, i])
    Pij = P[:, i, j]
    out = []
    for lo, hi in REPORT_BANDS:
        m = (SUB_FC >= lo) & (SUB_FC < hi)
        den = float(Pii[m].sum())
        out.append(float(np.abs(Pij[m].sum()) / den) if den > 0 else float("nan"))
    return out


def spectral_stats(X: np.ndarray, mask: np.ndarray) -> dict[str, float | list[float]]:
    starts = segment_starts(mask)
    K = len(starts)
    out: dict[str, float | list[float]] = {"K": K}
    if K < K_MIN:
        return out
    G, _ = csd_matrix(X, starts)
    P = subband(G)
    T = white_subband_power(TQ16)
    for a, b in SPEC_PAIRS:
        res = []
        for k in range(1, NE + 1):
            i, j = _ch(a, k), _ch(b, k)
            pr = pair_decomposition(P, T, i, j, K)
            res.append((pr, _band_gain(P, i, j)))
        pr1, g1 = res[0]
        key = f"{a}>{b}"
        out[f"{key}.r"] = pr1.r_spec
        out[f"{key}.r_lag"] = pr1.r_lag
        out[f"{key}.CF_effect"] = pr1.CF_j
        out[f"{key}.tau_eq"] = pr1.tau_eq
        out[f"{key}.coh_bands"] = list(pr1.coh_bands)
        out[f"{key}.phase_bands_deg"] = list(pr1.phase_bands_deg)
        out[f"{key}.gain_bands"] = g1
        out[f"{key}.r_truth"] = pr1.r_truth
        out[f"{key}.tau_eq_mean"] = float(np.mean([r.tau_eq for r, _ in res]))
        out[f"{key}.phase_bands_deg_mean"] = [
            float(
                np.degrees(np.angle(np.mean(np.exp(1j * np.radians([r.phase_bands_deg[b] for r, _ in res])))))
            )
            for b in range(len(REPORT_BANDS))
        ]
        out[f"{key}.gain_bands_mean"] = [
            float(np.mean([g[b] for _, g in res])) for b in range(len(REPORT_BANDS))
        ]
        out[f"{key}.coh_bands_mean"] = [
            float(np.mean([r.coh_bands[b] for r, _ in res])) for b in range(len(REPORT_BANDS))
        ]
    return out


def record_stats(rec: FlightRecord, aten: np.ndarray, gov: np.ndarray | None = None) -> dict:
    """Every MF1 statistic of one record (see module docstring); ``gov`` adds the paired governed classes."""
    Y = {f: np.asarray(rec.outputs[f]) for f in FAMS}
    out: dict = {"n": int(rec.n)}
    b1 = b1_stats(Y, CFG)
    if b1 is not None:
        fast = b1[1]
        for a, b in WITHIN:
            v = [_b1_pair(fast, f"{a}_{k}", f"{b}_{k}") for k in range(1, NE + 1)]
            out[f"B1.{a}-{b}"] = v[0]
            out[f"B1.{a}-{b}_mean"] = float(np.mean(v))
        for f in CROSS:
            v = [
                _b1_pair(fast, f"{f}_{i}", f"{f}_{j}") for i in range(1, NE + 1) for j in range(i + 1, NE + 1)
            ]
            out[f"B1.{f}x"] = v[0]
            out[f"B1.{f}x_mean"] = float(np.mean(v))
    b2 = b2_stats(Y, CFG)
    if b2 is not None:
        b2 = np.asarray(b2).reshape(NE, -1)
        for p, (a, b) in enumerate(B2_PAIRS):
            out[f"B2.{a}>{b}"] = float(b2[0, p])
            out[f"B2.{a}>{b}_mean"] = float(np.mean(b2[:, p]))
    masks = class_masks(rec, aten, gov)
    X = fast_band(rec)
    air = masks["ALL"]
    ph = np.asarray(rec.phase)
    out["air_frac"] = float(air.mean())
    out["taxi_share_of_air"] = float(np.mean(ph[air] == 2)) if air.any() else float("nan")
    out["gov_share_of_air"] = float(np.mean(masks["GOV"][air])) if air.any() else float("nan")
    # fast-band amplitude (the correlations do not constrain the disturbance level): SD of the B1 fast-band
    # signal per family on the airborne and on the governed in-flight samples (engine 1 and engine mean)
    for c in ("ALL", "GOVFLT"):
        m = masks[c]
        if m.sum() >= MIN_AIR_SAMPLES:
            for f in FAMS:
                sd = [float(X[_ch(f, k), m].std()) for k in range(1, NE + 1)]
                out[f"FSD{c}.{f}"] = sd[0]
                out[f"FSD{c}.{f}_mean"] = float(np.mean(sd))
    for c in CLASSES:
        for k, v in class_stats(X, masks[c]).items():
            out[f"{c}.{k}"] = v
    for c in SPECTRAL_CLASSES:
        for k, v in spectral_stats(X, masks[c]).items():
            out[f"S{c}.{k}"] = v
    out["levels"] = {f: float(np.median(Y[f][0][air])) if air.any() else float("nan") for f in FAMS}
    return out


def merge_levels(stats: Mapping[str, dict]) -> dict:
    return {lvl: s.get("levels", {}) for lvl, s in stats.items()}


__all__ = ["CLASSES", "NSUB", "SPEC_PAIRS", "WITHIN", "class_masks", "record_stats"]
