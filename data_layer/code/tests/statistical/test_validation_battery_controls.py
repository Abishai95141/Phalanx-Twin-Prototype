"""A3 (data-free): the battery and guards can fail. Broken synthetics FAIL, a replicate of the real process
PASSES.

Control flights come from `phalanx.validation.testing` (CONTROL FIXTURE, a toy coupled chain; not a model).
Each
"real" flight has paired synthetic versions that share its inputs:
- replicate: same toy tail, independent process-disturbance realisation (real-vs-real of one tail): must PASS;
- decoupled: each channel's fast band circularly shifted independently (coupling destroyed): B1 and B4 must
FAIL;
- FF delayed 2 s (lead-lag order broken, nothing else): B2 must FAIL.
D_tail comes from another toy tail with different dynamics and maps; D_temp from the holdout's two halves.

Sample: n = 6 flights per group (3 + 3 temporal halves). The broken controls sit 5-10x above the bar and the
replicate 3-20x below it in a pilot run, so 6 flights give unambiguous verdicts; 500 bootstrap resamples
(instead of the pre-registered 2,000) keep `make check` fast without moving any verdict in the pilot.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.validation.battery import Bootstrap, decision, flight_stats_many, run_battery
from phalanx.validation.guards import (
    g0_audit,
    g1_counts,
    g1_distance,
    label_leak_audit,
    metadata_features,
)
from phalanx.validation.testing import (
    PARTNER_TAIL,
    REFERENCE_TAIL,
    STANDIN_AFFINE,
    STANDIN_LSB,
    STANDIN_SENTINELS,
    control_flight,
    decouple_fast_band,
    delay_family,
    double_quantise,
    g0_control_matrices,
    gate0_standin,
)

N = 6
N_BOOT = 500
pytestmark = pytest.mark.statistical


@pytest.fixture(scope="module")
def recs():
    H = [control_flight(i, REFERENCE_TAIL, "real") for i in range(N)]
    return {
        "holdout": H,
        "partner": [control_flight(100 + i, PARTNER_TAIL, "real") for i in range(N)],
        "replicate": [control_flight(i, REFERENCE_TAIL, "replicate") for i in range(N)],
        "decoupled": [decouple_fast_band(r) for r in H],
        "ff_delay_2s": [delay_family(r, "FF", 2.0) for r in H],
    }


@pytest.fixture(scope="module")
def report(recs):
    S = {g: flight_stats_many(v) for g, v in recs.items()}
    h = N // 2
    return run_battery(
        S["holdout"],
        S["partner"],
        list(range(h)),
        list(range(N - h, N)),
        {a: S[a] for a in ("replicate", "decoupled", "ff_delay_2s")},
        Bootstrap(np.random.SeedSequence(20261014, spawn_key=(5,)), N_BOOT),
    )


def _verdicts(report, arm):
    return {t: v.verdict for t, v in report.arms[arm].verdicts.items()}


def test_replicate_passes_all_six(report):
    """Real-vs-real of one tail: every test PASSES and the pre-registered decision is GO."""
    assert _verdicts(report, "replicate") == {t: "PASS" for t in ("B1", "B2", "B3", "B4", "B5", "B6")}
    assert decision(report.arms["replicate"].verdicts, g0_pass=True)["decision"] == "GO"


def test_decoupled_fast_band_fails_cohesion(report):
    """Independent per-channel fast bands destroy within-engine coupling: B1 and B4 FAIL, decision not GO."""
    v = _verdicts(report, "decoupled")
    assert v["B1"] == "FAIL" and v["B4"] == "FAIL"
    p = report.arms["decoupled"].verdicts["B1"].parts["B1_fast"]
    assert p.D_sim > 3 * p.D_tail and p.lb95_one_sided_Dsim_minus_Dtail > 0
    assert decision(report.arms["decoupled"].verdicts, g0_pass=True)["decision"] != "GO"


def test_ff_delay_fails_lead_lag(report):
    """A 2-s FF delay leaves levels intact but breaks the lead-lag order: B2 FAILs; B6 (levels) still
    PASSES."""
    v = _verdicts(report, "ff_delay_2s")
    assert v["B2"] == "FAIL"
    assert v["B6"] == "PASS"
    p = report.arms["ff_delay_2s"].verdicts["B2"].parts["B2"]
    assert p.D_sim > 3 * p.D_tail


def test_g0_flags_a_dtype_cue_and_passes_identical_metadata(recs):
    """G0 (pipeline-only): identical file metadata PASSES; storing the synthetic words as float64 FAILS."""

    def X(rs, dtype):
        rows, names = [], None
        for r in rs:
            ch, fr, rs_ = gate0_standin(r, dtype)
            v, names = metadata_features(
                ch, fr, rs_, lsb=STANDIN_LSB, sentinels=STANDIN_SENTINELS, affine=STANDIN_AFFINE
            )
            rows.append(v)
        return np.vstack(rows), names

    XA, names = X(recs["holdout"], "float32")
    XB, _ = X(recs["replicate"], "float32")
    XC, _ = X(recs["replicate"], "float64")
    assert g0_audit(XA, XB, names, paired=True, seed=3).passed
    bad = g0_audit(XA, XC, names, paired=True, seed=3)
    assert not bad.passed
    assert bad.top_univariate[0][0].endswith("_dtype")
    M = g0_control_matrices(40)
    assert not g0_audit(M["sep_A"], M["sep_B"], [str(x) for x in M["names"]], paired=True, seed=3).passed


def test_g1_separates_single_from_double_quantiser(recs):
    """G1: a double-quantised synthetic matches a double-quantised real; a single lattice does not."""
    native = {"N1": 0.04, "N2": 0.04, "EGT": 0.8}
    real = [g1_counts(double_quantise(r, native)) for r in recs["holdout"]]
    good = g1_distance([g1_counts(double_quantise(r, native)) for r in recs["replicate"]], real)
    bad = g1_distance([g1_counts(r) for r in recs["replicate"]], real)
    for f in native:
        assert bad[f]["tv_distance"] > 5 * good[f]["tv_distance"], f
        assert bad[f]["tv_distance"] > 0.1
    # never-used residues of the double quantiser (EGT: 1, 4, 7 mod 8) are reproduced by the good synthetic
    egt = np.array(good["EGT"]["residues_syn"])
    assert np.all(egt[[1, 4, 7]] == 0) and np.all(np.array(good["EGT"]["residues_real"])[[1, 4, 7]] == 0)


def test_label_leak_core_flags_a_planted_cue():
    """Label-leak core: a metadata column that encodes the fault label FAILS; label-free twins PASS."""
    g = np.random.Generator(np.random.PCG64(np.random.SeedSequence(7, spawn_key=(1,))))
    n = 60
    base = g.random((n, 4))
    X = np.vstack([base, base])  # every healthy run has a faulty twin with identical features
    y = np.r_[np.zeros(n, int), np.ones(n, int)]
    groups = np.r_[np.arange(n), np.arange(n)] // 3  # tails: twins share a tail
    names = [f"m{j}" for j in range(4)]
    ok = label_leak_audit(X, y, groups, names, feature_set="metadata_only", seed=5, n_boot=300)
    assert ok.passed
    leak = X.copy()
    leak[:, 2] += 0.5 * y  # e.g. a record length that differs only for faulty runs
    bad = label_leak_audit(leak, y, groups, names, feature_set="metadata_only", seed=5, n_boot=300)
    assert not bad.passed
    assert bad.top_univariate[0][0] == "m2"


def test_g0_one_sided_rule_null_metadata_passes_and_a_moderate_cue_fails():
    """Owner decision PD-W0.5-2 (AD-40): G0 is one-sided by default. Null metadata (both groups drawn from one
    distribution, 40 pairs) that the pre-registered two-sided rule falsely FAILs (GB AUC below chance) is not
    a
    FAIL; a planted record-length cue (AUC ~0.8, well above chance) still FAILs. 500 resamples."""
    M = g0_control_matrices(40)
    names = [str(x) for x in M["names"]]
    null_one = g0_audit(M["null_A"], M["null_B"], names, paired=True, seed=11, n_boot=500)
    null_two = g0_audit(M["null_A"], M["null_B"], names, paired=True, seed=11, n_boot=500, sided="two")
    assert null_one.passed and not null_two.passed
    assert null_two.classifiers["gb"]["ci95"][1] < 0.5  # the two-sided false FAIL is below chance
    cue = M["null_B"].copy()
    cue[:, 0] += 80.0  # record frames
    cue[:, 1] += 320.0  # record seconds
    res = g0_audit(M["null_A"], cue, names, paired=True, seed=11, n_boot=500)
    assert not res.passed and res.classifiers["lr"]["ci95"][0] > 0.6
