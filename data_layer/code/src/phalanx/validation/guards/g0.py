"""G0 trivial-cue audit (binding guard; architecture §14.1; round-2 pre-registration section 5).

A metadata-only classifier must sit at chance: generation must leave no pipeline artefact that separates
synthetic from real files. Port of round-1 `features.gate0` (the metadata vector) and `s07_gate0.evaluate`
(the audit), as used by round-2 `s06_disc_guard.py`.

- **Binding subset ("pipeline-only"):** per-channel sample count, count / rate, dtype, NaN presence and
  float32 representability, plus record frames and record seconds.
- **Rule (owner decision PD-W0.5-2, option a; AD-40):** one-sided by default. G0 FAILs iff, for LR or GB,
  the lower bound of the 95 % flight-bootstrap CI of the flight-level AUC is above 0.5 (a usable cue). An
  AUC below chance never FAILs: under grouped CV it is an anti-learning artefact, and the pre-registered
  two-sided rule falsely FAILed 6 of 20 null replicates that way (A-W0.5-4). GroupKFold 5 x 3; the real and
  synthetic version of a flight share a fold when paired.
- `sided="two"` applies the pre-registered round-2 rule (PASS iff the CI includes 0.5). Use it only to
  reproduce round-2 results.
- If every feature is constant across both groups, the audit returns AUC 0.5 with CI [0.5, 0.5] without
  fitting (round-1 behaviour). Every round-2 arm gave AUC 0.5, CI [0.5, 0.5] via paired identical metadata.
- The full metadata vector (lattice adherence, value/LSB fractional-part histogram, mantissa trailing zeros,
  sentinel counts, first and last samples) is reported as a diagnostic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from phalanx.validation.battery.config import N_BOOT
from phalanx.validation.guards.classify import auc, boot_auc, boot_indices, cv_scores

__all__ = [
    "DTYPES",
    "PIPELINE_ONLY",
    "SIDED",
    "GuardResult",
    "chance_pass",
    "g0_audit",
    "metadata_features",
    "pipeline_only_columns",
]

DTYPES = ["float64", "float32", "uint8", "uint16", "int16", "int32", "int64", "uint32"]
#: Name suffixes of the binding pipeline-only subset (round-1 `s07_gate0.PIPELINE_ONLY`).
PIPELINE_ONLY = ("_n", "_n_over_rate", "_dtype", "_hasnan", "_f32repr", "record_frames", "record_s")
_MANTISSA = np.uint64((1 << 52) - 1)
#: Chance rules: "one" (default; FAIL iff CI lower bound > 0.5) and "two" (round-2 pre-registration).
SIDED = ("one", "two")


def chance_pass(ci: Sequence[float], sided: str = "one") -> bool:
    """Classifier-at-chance rule on a 95 % CI of the AUC (see the module docstring)."""
    if sided == "one":
        return bool(ci[0] <= 0.5)
    if sided == "two":
        return bool(ci[0] <= 0.5 <= ci[1])
    raise ValueError(f"sided must be one of {SIDED}, got {sided!r}")


@dataclass(frozen=True)
class GuardResult:
    """Outcome of a classifier-at-chance guard (G0 or the label-leak audit)."""

    guard: str
    passed: bool
    classifiers: Mapping[str, Mapping[str, object]]
    top_univariate: Sequence[tuple[str, float, float, float]] = field(default_factory=tuple)
    n_rows: Mapping[str, int] = field(default_factory=dict)
    subset: str = ""
    seed: int = 0
    sided: str = "one"


def _sentinel_mask(x: np.ndarray, values: Sequence[float]) -> np.ndarray:
    m = np.zeros(x.size, bool)
    for v in values:
        m |= np.abs(x - v) <= 1e-6 * max(1.0, abs(v))
    return m


def _lattice_frac(v: np.ndarray, lsb: float, affine: tuple[float, float] | None) -> np.ndarray:
    q = (v - affine[1]) / affine[0] if affine is not None else v / lsb
    return q - np.rint(q)


def _trailing_zeros(good: np.ndarray) -> np.ndarray:
    bits = good.view(np.uint64) & _MANTISSA
    tz = np.zeros(bits.size)
    bb = bits.copy()
    for _ in range(52):
        z = (bb & np.uint64(1)) == 0
        nz = bb != 0
        tz += z & nz
        bb = np.where(z & nz, bb >> np.uint64(1), np.uint64(0))
    tz[bits == 0] = 52
    return tz


def metadata_features(
    channels: Mapping[str, tuple[np.ndarray, float]],
    record_frames: int,
    record_s: int,
    *,
    lsb: Mapping[str, float],
    sentinels: Mapping[str, Sequence[float]] | None = None,
    affine: Mapping[str, tuple[float, float]] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Metadata-only feature vector of one recorded file (port of round-1 `features.gate0`).

    Args:
        channels: name -> (raw samples with their recorded dtype, rate [Hz]), in the audit's channel order.
        record_frames: number of recorder frames in the file.
        record_s: record length [s] (number of 1-Hz samples).
        lsb: recorder LSB per channel (value / LSB fractional-part histogram).
        sentinels: sentinel values per channel (end-of-scale dropout codes), excluded from lattice stats.
        affine: optional (a, b) lattice per channel, value = a * code + b (DASHlink VRTG).
    """
    sentinels = sentinels or {}
    affine = affine or {}
    feats: list[tuple[str, float]] = [("record_frames", record_frames), ("record_s", record_s)]
    for ch, (raw, rate) in channels.items():
        x = np.asarray(raw).ravel()
        xf = x.astype(float)
        feats += [
            (f"{ch}_n", x.size),
            (f"{ch}_n_over_rate", x.size / rate),
            (f"{ch}_dtype", DTYPES.index(str(x.dtype)) if str(x.dtype) in DTYPES else -1),
            (f"{ch}_hasnan", float(np.isnan(xf).any())),
        ]
        mask = _sentinel_mask(xf, sentinels.get(ch, []))
        good = xf[~mask & np.isfinite(xf)]
        lf = _lattice_frac(good, lsb[ch], affine.get(ch))
        with np.errstate(invalid="ignore"):
            feats.append((f"{ch}_lat_on", float(np.mean(np.abs(lf) < 1e-3)) if lf.size else np.nan))
        h = np.histogram(lf, 10, (-0.5, 0.5))[0] / max(lf.size, 1)
        feats += [(f"{ch}_fracbin{k}", h[k]) for k in range(10)]
        f32 = np.mean(good.astype(np.float32).astype(np.float64) == good) if good.size else np.nan
        tz = _trailing_zeros(good)
        feats += [
            (f"{ch}_f32repr", f32),
            (f"{ch}_mantissa_tz_mean", tz.mean() if tz.size else np.nan),
            (f"{ch}_n_sentinel", float(mask.sum())),
            (f"{ch}_first", xf[0]),
            (f"{ch}_last", xf[-1]),
        ]
    return np.array([v for _, v in feats], np.float64), [nm for nm, _ in feats]


def pipeline_only_columns(names: Sequence[str]) -> list[int]:
    """Column indices of the binding pipeline-only subset."""
    return [j for j, n in enumerate(names) if n.endswith(PIPELINE_ONLY)]


def g0_audit(
    XA: np.ndarray,
    XB: np.ndarray,
    names: Sequence[str],
    *,
    paired: bool,
    seed: int,
    subset: str = "pipeline_only",
    n_boot: int = N_BOOT,
    sided: str = "one",
) -> GuardResult:
    """Classifier-at-chance audit of metadata features, real rows XA vs synthetic rows XB.

    Args:
        XA, XB: (n_files, n_features) metadata of the real and synthetic groups (row i of each is the same
            flight when `paired`).
        names: feature names (from `metadata_features`).
        paired: real and synthetic versions of the same flights (fold and bootstrap by pair).
        seed: integer entropy for folds, model draws and bootstrap (identity-derived by the caller).
        subset: "pipeline_only" (binding) or "full" (diagnostic).
        n_boot: bootstrap resamples (pre-registered 2,000).
        sided: "one" (default; build and gate runs) or "two" (round-2 reproduction only).
    """
    if sided not in SIDED:
        raise ValueError(f"sided must be one of {SIDED}, got {sided!r}")
    names = list(names)
    if subset == "pipeline_only":
        keep = pipeline_only_columns(names)
        XA, XB, names = XA[:, keep], XB[:, keep], [names[j] for j in keep]
    elif subset != "full":
        raise ValueError(subset)
    X = np.vstack([XA, XB])
    y = np.r_[np.zeros(len(XA), int), np.ones(len(XB), int)]
    if paired:
        if len(XA) != len(XB):
            raise ValueError("paired audit needs equal row counts")
        pid = np.r_[np.arange(len(XA)), np.arange(len(XB))]
        groups = pid
    else:
        pid = None
        groups = np.arange(len(y))
    bidx = boot_indices(y, pid, n_boot, seed)
    classifiers: dict[str, dict[str, object]] = {}
    for kind in ("lr", "gb"):
        with np.errstate(invalid="ignore"):
            constant = bool(np.all(np.nanstd(X, 0) == 0))
        if constant:
            classifiers[kind] = {
                "auc": 0.5,
                "ci95": [0.5, 0.5],
                "pass": True,
                "note": "all features identical",
            }
            continue
        s, _, _ = cv_scores(kind, X, y, np.arange(len(y)), len(y), groups, seed)
        a = auc(y, s)
        bs = boot_auc(y, s, bidx)
        ci = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        classifiers[kind] = {"auc": a, "ci95": ci, "pass": chance_pass(ci, sided)}
    uni = []
    for j, n in enumerate(names):
        v = X[:, j]
        with np.errstate(invalid="ignore"):
            if np.nanstd(v) == 0:
                continue
        uni.append((n, float(auc(y, v)), float(np.nanmean(XA[:, j])), float(np.nanmean(XB[:, j]))))
    uni.sort(key=lambda t: -abs(t[1] - 0.5))
    return GuardResult(
        guard="G0",
        passed=all(bool(c["pass"]) for c in classifiers.values()),
        classifiers=classifiers,
        top_univariate=tuple(uni[:15]),
        n_rows={"real": len(XA), "synthetic": len(XB)},
        subset=subset,
        seed=seed,
        sided=sided,
    )
