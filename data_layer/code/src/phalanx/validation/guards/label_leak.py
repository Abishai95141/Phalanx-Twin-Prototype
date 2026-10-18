"""Label-leak audit (binding guard of the fault build; architecture §14.1, invariant I6; W2.5).

Question: can anything but the physics tell a faulty run from a healthy one? If a classifier that sees only
texture-level or metadata-level features of a run predicts its fault label, or if the recording pipeline
behaves differently for identical acquisition inputs, faults have left a non-physical cue (a different
generation path, a pipeline artefact) and the synthetic fault data are unusable for training or benchmarking
(RULES.md rule 4, binding guards).

Three parts (W2.5 pre-registration ``analysis/faults_b7b8/PREREGISTRATION.md`` §5):

1. :func:`paired_invariance` (deterministic): a healthy and a faulty run of one identity share every exogenous
   draw (CRN, AD-37), so wherever the acquisition input of a channel is bitwise identical, its recorded
   samples must be bitwise identical too, and the pipeline metadata (sample counts and instants, run frames)
   must be identical for every channel. Any difference is a leak, whatever a classifier says.
2. :func:`label_leak_audit` (classifier at chance): grouped CV (groups = the unit that must not straddle
   folds: the pair), L2 logistic regression and gradient boosting (the W0.5 core shared with G0), run-level
   AUC with a stratified bootstrap CI. Rule (AD-40, one-sided by default): FAIL iff, for either classifier,
   the lower bound of the 95 % CI of the AUC is above 0.5. ``sided="two"`` applies the round-2 form.
3. :func:`leak_features`: the two feature sets, ``texture_only`` (quantisation and noise texture, blind to
   levels and trends) and ``metadata_only`` (pipeline facts), on :class:`RecordedRun` (per-channel recorded
   series, each at its own rate: the bench and fleet runs) or on the battery's
   :class:`~phalanx.validation.flightdata.FlightRecord` (families on one grid).

Texture-only features per series: empirical LSB (smallest non-zero step, log10), lattice adherence (fraction
of values on that lattice from the series minimum), zero-step fraction (repeats, stale holds),
first-difference scale in LSB (MAD), kurtosis of the first differences (heavy tails), lag-1 autocorrelation of
the second differences (colour of the high-pass residual), fraction of samples at the series minimum
(sentinel-like floors). Metadata-only: sample counts, count over rate, float32 representability per series;
run frames, run seconds, sub-second phase of the start, number of series (and, on FlightRecords, families,
units and phase codes).

A *physical* fault changes levels, not texture or metadata, so both audits must sit at chance; a fault class
whose physical effect *is* texture (sensor spikes, stuck values, intermittents, open/short, slow response) is
excluded from the texture-only audit by the caller (AD-48.7) and judged by the metadata audit, G0 and the
paired invariance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

from phalanx.validation.battery.config import N_BOOT
from phalanx.validation.flightdata import FlightRecord
from phalanx.validation.guards.classify import auc, boot_auc, boot_indices, cv_scores
from phalanx.validation.guards.g0 import SIDED, GuardResult, chance_pass

__all__ = [
    "FEATURE_SETS",
    "TEXTURE_FEATURES",
    "RecordedRun",
    "label_leak_audit",
    "leak_features",
    "paired_invariance",
    "texture_features",
]

#: Feature sets the audit is run on (each separately).
FEATURE_SETS: tuple[str, ...] = ("texture_only", "metadata_only")
#: names of the per-series texture features, in :func:`texture_features` order
TEXTURE_FEATURES: tuple[str, ...] = (
    "log10_lsb",
    "lattice_on",
    "zero_step",
    "mad_step_lsb",
    "kurt_step",
    "acf1_d2",
    "at_min",
)


@dataclass(frozen=True)
class RecordedRun:
    """One run as a ground station records it, per channel (each series at its own acquisition rate).

    ``value``: recorded value (EU); ``validity``, ``flags``: per-sample codes; ``t_sample``: acquisition
    instants [ns]; ``rate_hz``: nominal rate; ``input_digest``: a digest of the channel's acquisition input
    (the M12 output frames, or the owner's computed value), used only by :func:`paired_invariance`;
    ``n_frames``: truth steps of the run; ``t0_ns``: start. No truth enters any feature."""

    run_id: str
    value: Mapping[str, np.ndarray]
    rate_hz: Mapping[str, float]
    n_frames: int
    t0_ns: int = 0
    validity: Mapping[str, np.ndarray] = field(default_factory=dict)
    flags: Mapping[str, np.ndarray] = field(default_factory=dict)
    t_sample: Mapping[str, np.ndarray] = field(default_factory=dict)
    input_digest: Mapping[str, str] = field(default_factory=dict)

    @property
    def channels(self) -> tuple[str, ...]:
        return tuple(sorted(self.value))


def texture_features(x: np.ndarray) -> list[float]:
    """The :data:`TEXTURE_FEATURES` of one recorded series (level- and trend-blind by construction)."""
    x = np.asarray(x, np.float64).ravel()
    if x.size == 0:
        return [0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0]
    d = np.diff(x)
    nz = np.abs(d[d != 0.0])
    lsb = float(nz.min()) if nz.size else 1.0
    q = (x - x.min()) / lsb
    lattice_on = float(np.mean(np.abs(q - np.rint(q)) < 1e-6))
    zero = float(np.mean(d == 0.0)) if d.size else 1.0
    mad = float(np.median(np.abs(d - np.median(d)))) / lsb if d.size else 0.0
    if d.size > 3 and np.std(d) > 0:
        z = (d - d.mean()) / d.std()
        kurt = float(np.mean(z**4))
    else:
        kurt = 0.0
    d2 = np.diff(d)
    if d2.size > 2 and np.std(d2) > 0:
        a, b = d2[:-1] - d2.mean(), d2[1:] - d2.mean()
        acf1 = float(np.sum(a * b) / np.sum((d2 - d2.mean()) ** 2))
    else:
        acf1 = 0.0
    at_min = float(np.mean(x == x.min()))
    return [float(np.log10(lsb)), lattice_on, zero, mad, kurt, acf1, at_min]


def _f32repr(a: np.ndarray) -> float:
    a = np.asarray(a, np.float64)
    return float(np.mean(a.astype(np.float32).astype(np.float64) == a)) if a.size else 1.0


def _flight_rows(records: Sequence[FlightRecord], feature_set: str) -> tuple[list[list[float]], list[str]]:
    fams = sorted(records[0].outputs)
    for r in records:
        if sorted(r.outputs) != fams:
            raise ValueError("all records must carry the same output families")
    rows: list[list[float]] = []
    names: list[str] = []
    for r in records:
        row: list[float] = []
        nm: list[str] = []
        if feature_set == "texture_only":
            for f in fams:
                row += texture_features(r.outputs[f])
                nm += [f"{f}_{k}" for k in TEXTURE_FEATURES]
        else:
            row += [float(r.n), float(r.rate_hz), float(r.n) / float(r.rate_hz), float(r.n_units)]
            nm += ["n", "rate_hz", "duration_s", "n_units"]
            row += [float(len(fams)), float(r.t0_ns % 1_000_000_000) / 1e9, float(np.unique(r.phase).size)]
            nm += ["n_families", "t0_subsecond", "n_phase_codes"]
            for f in fams:
                row.append(_f32repr(r.outputs[f]))
                nm.append(f"{f}_f32repr")
        rows.append(row)
        names = nm
    return rows, names


def _run_rows(records: Sequence[RecordedRun], feature_set: str) -> tuple[list[list[float]], list[str]]:
    chans = records[0].channels
    for r in records:
        if r.channels != chans:
            raise ValueError("all runs must record the same channels")
    rows: list[list[float]] = []
    names: list[str] = []
    for r in records:
        row: list[float] = []
        nm: list[str] = []
        if feature_set == "texture_only":
            for c in chans:
                row += texture_features(r.value[c])
                nm += [f"{c}_{k}" for k in TEXTURE_FEATURES]
        else:
            row += [float(r.n_frames), float(r.n_frames) / 240.0, float(r.t0_ns % 1_000_000_000) / 1e9]
            nm += ["record_frames", "record_s", "t0_subsecond"]
            row.append(float(len(chans)))
            nm.append("n_channels")
            for c in chans:
                n = float(np.asarray(r.value[c]).size)
                row += [n, n / float(r.rate_hz[c]), _f32repr(r.value[c])]
                nm += [f"{c}_n", f"{c}_n_over_rate", f"{c}_f32repr"]
        rows.append(row)
        names = nm
    return rows, names


def leak_features(
    records: Sequence[FlightRecord] | Sequence[RecordedRun], feature_set: str
) -> tuple[np.ndarray, list[str]]:
    """(n_runs, n_features) features and their names for ``feature_set`` in :data:`FEATURE_SETS`.

    All records must be of one kind and carry the same output families (FlightRecord) or channels
    (RecordedRun); no feature is derived from truth or labels."""
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"feature_set must be one of {FEATURE_SETS}, got {feature_set!r}")
    if not records:
        raise ValueError("no records")
    if all(isinstance(r, RecordedRun) for r in records):
        rows, names = _run_rows(records, feature_set)  # type: ignore[arg-type]
    elif all(isinstance(r, FlightRecord) for r in records):
        rows, names = _flight_rows(records, feature_set)  # type: ignore[arg-type]
    else:
        raise ValueError("records must all be FlightRecord or all RecordedRun")
    return np.array(rows, np.float64), names


def _equal(a: Mapping[str, np.ndarray], b: Mapping[str, np.ndarray], c: str) -> bool:
    if (c in a) != (c in b):
        return False
    if c not in a:
        return True
    return np.array_equal(np.asarray(a[c]), np.asarray(b[c]))


def paired_invariance(healthy: RecordedRun, faulty: RecordedRun) -> list[str]:
    """Problems of a healthy/faulty pair recorded under one identity (empty list = no non-physical
    difference).

    - the run metadata (channels, frames, start) and every channel's sample count and sample instants are
      identical (the clocks and the pipeline do not depend on the fault);
    - every channel whose acquisition input digest is identical in both runs has bitwise identical recorded
      values, validity and flags (identical input + common draws = identical output). A channel whose
      input changed (the fault's physics reached it) may differ in value, validity and flags only."""
    out: list[str] = []
    if healthy.channels != faulty.channels:
        out.append(f"channel sets differ: {sorted(set(healthy.channels) ^ set(faulty.channels))}")
        return out
    if healthy.n_frames != faulty.n_frames or healthy.t0_ns != faulty.t0_ns:
        out.append("run frames or start differ")
    for c in healthy.channels:
        nh, nf = np.asarray(healthy.value[c]).size, np.asarray(faulty.value[c]).size
        if nh != nf:
            out.append(f"{c}: sample count {nh} vs {nf}")
            continue
        if not _equal(healthy.t_sample, faulty.t_sample, c):
            out.append(f"{c}: sample instants differ")
        same_input = c in healthy.input_digest and healthy.input_digest.get(c) == faulty.input_digest.get(c)
        if same_input:
            for name, h, f in (
                ("value", healthy.value, faulty.value),
                ("validity", healthy.validity, faulty.validity),
                ("flags", healthy.flags, faulty.flags),
            ):
                if not _equal(h, f, c):
                    out.append(f"{c}: {name} differs with an identical acquisition input")
    return out


def label_leak_audit(
    features: np.ndarray,
    labels: np.ndarray,
    groups: np.ndarray,
    names: Sequence[str],
    *,
    feature_set: str,
    seed: int,
    n_boot: int = N_BOOT,
    sided: str = "one",
) -> GuardResult:
    """Classifier-at-chance test of fault labels from texture-only or metadata-only features.

    Args:
        features: (n_runs, n_features) one row per run (sortie or window), never truth-derived.
        labels: (n_runs,) 0 = healthy, 1 = faulty (from the restricted labels store).
        groups: (n_runs,) grouping for the CV folds (all runs of a group in one fold), e.g. the pair id.
        names: feature names (for the univariate diagnostic).
        feature_set: one of FEATURE_SETS (recorded in the result).
        seed: integer entropy for folds, model draws and bootstrap.
        n_boot: bootstrap resamples over runs (stratified by label).
        sided: "one" (default) or "two" (round-2 form).
    """
    if sided not in SIDED:
        raise ValueError(f"sided must be one of {SIDED}, got {sided!r}")
    if feature_set not in FEATURE_SETS:
        raise ValueError(f"feature_set must be one of {FEATURE_SETS}, got {feature_set!r}")
    X = np.asarray(features, float)
    y = np.asarray(labels).astype(int)
    g = np.asarray(groups)
    if X.ndim != 2 or X.shape[0] != y.size or g.size != y.size or len(names) != X.shape[1]:
        raise ValueError("features (n, p), labels (n,), groups (n,) and names (p) must agree")
    if set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError("labels must contain both classes 0 (healthy) and 1 (faulty)")
    bidx = boot_indices(y, None, n_boot, seed)
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
        s, _, _ = cv_scores(kind, X, y, np.arange(y.size), y.size, g, seed)
        a = auc(y, s)
        bs = boot_auc(y, s, bidx)
        ci = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        classifiers[kind] = {"auc": a, "ci95": ci, "pass": chance_pass(ci, sided)}
    uni = []
    for j, n in enumerate(names):
        with np.errstate(invalid="ignore"):
            if np.nanstd(X[:, j]) == 0:
                continue
        uni.append(
            (n, float(auc(y, X[:, j])), float(np.nanmean(X[y == 0, j])), float(np.nanmean(X[y == 1, j])))
        )
    uni.sort(key=lambda t: -abs(t[1] - 0.5))
    return GuardResult(
        guard="label_leak",
        passed=all(bool(c["pass"]) for c in classifiers.values()),
        classifiers=classifiers,
        top_univariate=tuple(uni[:15]),
        n_rows={
            "healthy": int((y == 0).sum()),
            "faulty": int((y == 1).sum()),
            "groups": int(np.unique(g).size),
        },
        subset=feature_set,
        seed=seed,
        sided=sided,
    )
