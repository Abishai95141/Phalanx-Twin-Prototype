"""Label-leak audit front end (binding guard, I6): ``phalanx.faults.leak_features`` + the W0.5 classifier
core.

A *physical* fault (EGT +10 °C level shift, same quantiser and noise path) must stay at chance on texture-only
and metadata-only features; a *planted* non-physical cue (the faulty runs quantised on a different lattice, a
different generation path) must be caught by the texture-only audit (negative control).

Sample: n = 100 runs (50 healthy, 50 faulty), 600 samples at 4 Hz each, one group per run; the guard's
classifiers are fixed a priori (round-1 ports). TEST FIXTURE: synthetic FlightRecords built here."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.faults import leak_features
from phalanx.validation.flightdata import FlightRecord
from phalanx.validation.guards import label_leak_audit

N_RUNS = 100  # 40 runs gave a below-chance GB AUC (CV anti-learning, cf. AD-40) that the two-sided rule fails


def record(i: int, faulty: bool, *, lattice_leak: bool = False) -> FlightRecord:
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(31, spawn_key=(i,))))
    n = 600
    t = np.arange(n) / 4.0
    base_n2, base_egt = 85 + 3 * g.random(), 600 + 25 * g.random()  # run-to-run level scatter
    n2 = base_n2 + 5 * np.sin(t / 30 + i) + 0.02 * g.standard_normal(n)
    egt = base_egt + 40 * np.sin(t / 30 + i) + (10.0 if faulty else 0.0) + 0.3 * g.standard_normal(n)
    lsb_egt = 1.0 if (faulty and lattice_leak) else 0.8
    out = {
        "N2": np.round(n2 / 0.04) * 0.04,
        "EGT": np.round(egt / lsb_egt) * lsb_egt,
        "N1": np.round((n2 - 10) / 0.04) * 0.04,
        "FF": np.round((2000 + 30 * n2) / 8.0) * 8.0,
    }
    return FlightRecord(
        flight_id=f"R{i}",
        rate_hz=4.0,
        outputs={k: v[None, :] for k, v in out.items()},
        pla=np.full((1, n), 50.0),
        theta=np.ones(n),
        delta=np.ones(n),
        phase=np.full(n, 5),
        t0_ns=1_800_000_000 * 10**9,
    )


def audit(recs, labels, feature_set):
    X, names = leak_features(recs, feature_set)
    return label_leak_audit(
        X, labels, np.arange(len(recs)), names, feature_set=feature_set, seed=11, n_boot=500
    )


def one_sided_pass(res) -> bool:
    """AD-40 form of the rule (owner decision for G0): fail only if a classifier's 95 % CI lower bound is
    above
    0.5. Below-chance AUCs are a grouped-CV anti-learning artefact; the guard's two-sided rule fails them."""
    return all(c["ci95"][0] <= 0.5 for c in res.classifiers.values())


@pytest.mark.integration
def test_physical_fault_leaves_no_metadata_cue():
    labels = np.r_[np.zeros(N_RUNS // 2, int), np.ones(N_RUNS // 2, int)]
    recs = [record(i, bool(lab)) for i, lab in enumerate(labels)]
    res = audit(recs, labels, "metadata_only")
    assert res.passed, res.classifiers


@pytest.mark.slow
@pytest.mark.integration
def test_physical_fault_leaves_no_texture_cue_replicated():
    """Null texture audit, 5 replicates of n = 100 runs (fixture keys 1000 r + i). Under the null the
    one-sided rule falsely fails with probability ≈ 5 % per replicate, so at least 4 of 5 must pass (P(≥ 2
    false fails) ≈ 2 %); the guard's two-sided rule is reported, not asserted (it fails null data on
    anti-learning, see the
    W1.5 report's proposed decision for W2.5)."""
    passes = []
    for rep in range(5):
        labels = np.r_[np.zeros(N_RUNS // 2, int), np.ones(N_RUNS // 2, int)]
        recs = [record(1000 * (rep + 1) + i, bool(lab)) for i, lab in enumerate(labels)]
        passes.append(one_sided_pass(audit(recs, labels, "texture_only")))
    assert sum(passes) >= 4, passes


@pytest.mark.integration
def test_planted_lattice_leak_is_caught():
    labels = np.r_[np.zeros(N_RUNS // 2, int), np.ones(N_RUNS // 2, int)]
    recs = [record(i, bool(lab), lattice_leak=True) for i, lab in enumerate(labels)]
    res = audit(recs, labels, "texture_only")
    assert not res.passed
    assert res.top_univariate[0][0].startswith("EGT_")


@pytest.mark.integration
def test_feature_shapes_and_errors():
    recs = [record(i, False) for i in range(3)]
    X, names = leak_features(recs, "texture_only")
    assert X.shape == (3, 4 * 7) and len(names) == X.shape[1] and np.all(np.isfinite(X))
    X, names = leak_features(recs, "metadata_only")
    assert X.shape[0] == 3 and "n" in names and "EGT_f32repr" in names
    with pytest.raises(ValueError):
        leak_features(recs, "truth")
