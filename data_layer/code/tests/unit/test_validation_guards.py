"""Unit tests of the G0 metadata vector, the pipeline-only subset, G1 counting and the label-leak
interface."""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from phalanx.validation.guards import (
    FEATURE_SETS,
    PIPELINE_ONLY,
    g0_audit,
    g1_counts,
    label_leak_audit,
    leak_features,
    metadata_features,
)
from phalanx.validation.guards.g0 import pipeline_only_columns
from phalanx.validation.testing import REFERENCE_TAIL, control_flight

pytestmark = pytest.mark.unit


def _meta(raw: np.ndarray, rate: float = 4.0, sentinels=None):
    return metadata_features({"N1_1": (raw, rate)}, 10, 40, lsb={"N1_1": 0.25}, sentinels=sentinels)


def test_metadata_features_capture_pipeline_cues():
    x32 = (np.arange(160, dtype=np.float32) * np.float32(0.25)).astype(np.float32)
    v32, names = _meta(x32)
    d = dict(zip(names, v32, strict=True))
    assert d["record_frames"] == 10 and d["record_s"] == 40
    assert d["N1_1_n"] == 160 and d["N1_1_n_over_rate"] == 40.0
    assert d["N1_1_dtype"] == 1 and d["N1_1_hasnan"] == 0.0 and d["N1_1_f32repr"] == 1.0
    assert d["N1_1_lat_on"] == 1.0
    v64 = dict(zip(names, _meta(x32.astype(np.float64) + 1e-9)[0], strict=True))
    assert v64["N1_1_dtype"] == 0 and v64["N1_1_f32repr"] < 1.0  # values no longer float32-representable
    with_nan = x32.astype(np.float64)
    with_nan[3] = np.nan
    assert dict(zip(names, _meta(with_nan)[0], strict=True))["N1_1_hasnan"] == 1.0


def test_sentinels_are_excluded_from_lattice_statistics():
    x = np.r_[np.full(10, -3.375), np.arange(100) * 0.25]
    d = dict(zip(*reversed(_meta(x, sentinels={"N1_1": [-3.375]})), strict=True))
    assert d["N1_1_n_sentinel"] == 10.0 and d["N1_1_lat_on"] == 1.0


def test_pipeline_only_subset_is_the_preregistered_one():
    names = [
        "record_frames",
        "record_s",
        "N1_1_n",
        "N1_1_n_over_rate",
        "N1_1_dtype",
        "N1_1_hasnan",
        "N1_1_f32repr",
        "N1_1_lat_on",
        "N1_1_fracbin3",
        "N1_1_mantissa_tz_mean",
        "N1_1_first",
    ]
    keep = [names[j] for j in pipeline_only_columns(names)]
    assert keep == names[:7]
    assert set(PIPELINE_ONLY) == {
        "_n",
        "_n_over_rate",
        "_dtype",
        "_hasnan",
        "_f32repr",
        "record_frames",
        "record_s",
    }


def test_g0_identical_metadata_is_exactly_at_chance():
    X = np.column_stack([np.arange(30) % 7, 4 * (np.arange(30) % 7), np.ones(30)]).astype(float)
    r = g0_audit(X, X.copy(), ["record_frames", "record_s", "N1_1_dtype"], paired=True, seed=1, n_boot=200)
    assert r.passed and r.guard == "G0" and r.subset == "pipeline_only"
    for c in r.classifiers.values():
        assert c["auc"] == 0.5 and c["ci95"] == [0.5, 0.5]


def test_g0_constant_features_short_circuit():
    X = np.ones((10, 2))
    r = g0_audit(X, X.copy(), ["record_frames", "record_s"], paired=True, seed=1, n_boot=50)
    assert r.passed and all(c.get("note") == "all features identical" for c in r.classifiers.values())


def test_g1_counts_residues_of_airborne_samples_only():
    rec = control_flight(0, REFERENCE_TAIL, "real")
    c = g1_counts(rec)
    assert set(c) == {"N1", "N2", "EGT", "FF"}
    assert c["N1"].shape == (4, 32) and c["EGT"].shape == (4, 8) and c["FF"].shape == (4, 8)
    air = np.all(np.asarray(rec.outputs["N1"]) > 25.0, axis=0).sum()
    assert np.all(c["EGT"].sum(1) == air)


def test_label_leak_interface():
    sig = inspect.signature(label_leak_audit)
    assert list(sig.parameters)[:4] == ["features", "labels", "groups", "names"]
    assert {"feature_set", "seed", "n_boot"} <= set(sig.parameters)
    assert FEATURE_SETS == ("texture_only", "metadata_only")
    X = np.zeros((4, 2))
    with pytest.raises(ValueError, match="feature_set"):
        label_leak_audit(X, np.array([0, 1, 0, 1]), np.arange(4), ["a", "b"], feature_set="levels", seed=0)
    with pytest.raises(ValueError, match="both classes"):
        label_leak_audit(X, np.zeros(4), np.arange(4), ["a", "b"], feature_set="metadata_only", seed=0)
    with pytest.raises(ValueError, match="agree"):
        label_leak_audit(
            X, np.array([0, 1, 0]), np.arange(4), ["a", "b"], feature_set="metadata_only", seed=0
        )
    with pytest.raises(ValueError, match="no records"):  # the W2.5 front end (was a placeholder until W2.5)
        leak_features([], "texture_only")


def test_chance_rule_sidedness():
    """One-sided (default): FAIL only if the CI lower bound is above 0.5. Two-sided: the CI must include
    0.5."""
    from phalanx.validation.guards.g0 import chance_pass

    assert chance_pass([0.20, 0.45]) and not chance_pass([0.20, 0.45], "two")  # below chance: not a FAIL
    assert not chance_pass([0.55, 0.90]) and not chance_pass([0.55, 0.90], "two")  # cue: FAIL either way
    assert chance_pass([0.40, 0.60]) and chance_pass([0.40, 0.60], "two")
    assert chance_pass([0.50, 0.70]) and not chance_pass(
        [0.5000001, 0.7]
    )  # boundary: lower bound exactly 0.5
    with pytest.raises(ValueError, match="sided"):
        chance_pass([0.4, 0.6], "both")
    X = np.ones((10, 2))
    with pytest.raises(ValueError, match="sided"):
        g0_audit(X, X.copy(), ["record_frames", "record_s"], paired=True, seed=1, sided="2")
    r = g0_audit(X, X.copy(), ["record_frames", "record_s"], paired=True, seed=1, n_boot=20)
    assert r.sided == "one"
    y = np.array([0, 1] * 5)
    with pytest.raises(ValueError, match="sided"):
        label_leak_audit(X, y, np.arange(10), ["a", "b"], feature_set="metadata_only", seed=0, sided="x")
