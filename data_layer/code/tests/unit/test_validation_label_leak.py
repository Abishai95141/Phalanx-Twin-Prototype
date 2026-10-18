"""Label-leak guard front end (W2.5; replaces the W0.5 placeholder): texture features are level-blind, the
feature sets on recorded runs, the paired pipeline invariance and the classifier on run features with a
planted leak.

TEST FIXTURE runs are synthetic RecordedRuns built here (module boundary of the guard). Samples: texture
checks on single series (deterministic); the classifier check on 60 runs (30 pairs) x 2 channels x 300
samples, where a planted lattice leak gives AUC 1 (any n separates it; 30 pairs keep the CI clear of 0.5) and
the null twin of the same design stays at chance (fixed keyed draws)."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.faults import load_catalogue
from phalanx.faults.leak import TEXTURE_SENSOR_MODES, texture_visible
from phalanx.validation.guards import RecordedRun, label_leak_audit, leak_features, paired_invariance
from phalanx.validation.guards.label_leak import TEXTURE_FEATURES, texture_features

pytestmark = pytest.mark.unit


def _gen(*key: int) -> np.random.Generator:
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(2525, spawn_key=key)))


def _series(g: np.random.Generator, n: int = 300, lsb: float = 0.25, level: float = 600.0) -> np.ndarray:
    x = level + 5.0 * np.sin(np.arange(n) / 25.0) + 0.3 * g.standard_normal(n)
    return np.round(x / lsb) * lsb


def test_texture_features_are_level_blind():
    x = _series(_gen(0))
    for shift in (0.25 * 40, -0.25 * 4000):  # whole LSB level shifts (a physical level fault)
        assert texture_features(x + shift) == pytest.approx(texture_features(x), abs=1e-12)
    coarse = np.round(x / 1.0) * 1.0  # a different lattice is texture
    assert texture_features(coarse)[0] != pytest.approx(texture_features(x)[0])
    assert len(texture_features(x)) == len(TEXTURE_FEATURES)
    assert np.all(np.isfinite(texture_features(np.full(10, 3.0))))


def _run(i: int, *, value_shift: float = 0.0, lattice: float = 0.25, drop: int = 0) -> RecordedRun:
    g = _gen(1, i)
    a = _series(g, lsb=lattice) + value_shift
    b = _series(g, lsb=0.04, level=80.0)
    n = 300 - drop
    return RecordedRun(
        run_id=f"R{i}",
        value={"ENG.T5": a[:n], "ENG.N2.A": b},
        rate_hz={"ENG.T5": 60.0, "ENG.N2.A": 60.0},
        n_frames=1200,
        validity={"ENG.T5": np.zeros(n, np.int64), "ENG.N2.A": np.zeros(300, np.int64)},
        flags={"ENG.T5": np.zeros(n, np.int64), "ENG.N2.A": np.zeros(300, np.int64)},
        t_sample={"ENG.T5": np.arange(n) * 16_666_667, "ENG.N2.A": np.arange(300) * 16_666_667},
        input_digest={"ENG.T5": "t5-a", "ENG.N2.A": "n2-a"},
    )


def test_feature_sets_on_recorded_runs():
    runs = [_run(i) for i in range(3)]
    X, names = leak_features(runs, "texture_only")
    assert X.shape == (3, 2 * len(TEXTURE_FEATURES)) and len(names) == X.shape[1]
    X, names = leak_features(runs, "metadata_only")
    assert {"record_frames", "ENG.T5_n", "ENG.N2.A_n_over_rate", "ENG.T5_f32repr"} <= set(names)
    assert np.all(np.isfinite(X))
    other = RecordedRun("X", {"ENG.T5": np.zeros(3)}, {"ENG.T5": 1.0}, 12)
    with pytest.raises(ValueError, match="same channels"):
        leak_features([runs[0], other], "texture_only")
    with pytest.raises(ValueError):
        leak_features(runs, "truth")


def test_paired_invariance_finds_only_non_physical_differences():
    h = _run(7)
    assert paired_invariance(h, h) == []
    # the fault reached ENG.T5's acquisition input: its values may differ
    f = _run(7, value_shift=2.5)
    f = RecordedRun(**{**f.__dict__, "input_digest": {"ENG.T5": "t5-b", "ENG.N2.A": "n2-a"}})
    assert paired_invariance(h, f) == []
    # same input, different recorded values: a non-physical cue
    g = _run(7, value_shift=2.5)
    assert any("identical acquisition input" in p for p in paired_invariance(h, g))
    # a dropped sample changes the pipeline whatever the input
    d = _run(7, drop=1)
    assert any("sample count" in p for p in paired_invariance(h, d))
    t = RecordedRun(**{**h.__dict__, "t_sample": {**h.t_sample, "ENG.N2.A": h.t_sample["ENG.N2.A"] + 1}})
    assert any("instants" in p for p in paired_invariance(h, t))


def _pairs(leak: bool) -> tuple[list[RecordedRun], np.ndarray, np.ndarray]:
    runs, y, grp = [], [], []
    for p in range(30):
        runs.append(_run(1000 + p))
        runs.append(_run(1000 + p, value_shift=1.5, lattice=1.0 if leak else 0.25))
        y += [0, 1]
        grp += [p, p]
    return runs, np.array(y), np.array(grp)


def test_classifier_catches_a_planted_lattice_leak_and_passes_its_null_twin():
    runs, y, grp = _pairs(leak=True)
    X, names = leak_features(runs, "texture_only")
    res = label_leak_audit(X, y, grp, names, feature_set="texture_only", seed=25, n_boot=500)
    assert not res.passed and res.top_univariate[0][0].startswith("ENG.T5_")
    runs, y, grp = _pairs(leak=False)
    X, names = leak_features(runs, "texture_only")
    res = label_leak_audit(X, y, grp, names, feature_set="texture_only", seed=25, n_boot=500)
    assert res.passed, res.classifiers


def test_texture_visible_modes_follow_ad_48_7():
    cat = load_catalogue()
    vis = {m for m, mode in cat.items() if texture_visible(mode)}
    assert "FM.SNS.T5_HARNESS_BIAS" not in vis and "FM.ENG.FOULING" not in vis  # level faults stay in
    for m in vis:
        assert any(
            e.target == "sensors" and e.fields.get("mode") in TEXTURE_SENSOR_MODES for e in cat[m].effects
        )
    generic = cat["FM.SNS.GENERIC"]
    assert texture_visible(generic, {"sensor_mode": "stuck"}) and not texture_visible(generic)
