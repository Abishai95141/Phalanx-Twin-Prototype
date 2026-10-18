"""A2: data-free golden reproduction. The port equals the ORIGINAL round-2 code on control flights.

Fixture: `src/phalanx/validation/golden/round2_golden.{npz,json}`, written by `make_round2_golden.py`, which
runs
the pre-registered round-2 code read-only in the round-2 environment (Python 3.14, numpy 2.3.5, scipy 1.17.1).
This test runs in the build environment (Python 3.13, numpy 2.5, scipy 1.18), so it states its tolerances:

| What | Tolerance | Why |
|---|---|---|
| control-flight inputs | SHA-256 identical | generator uses only raw PCG64 bits and correctly rounded IEEE
ops |
| per-flight stats except B3 (ii) tau | rtol 1e-9, atol 1e-12 | library versions differ |
| B3 (ii) step rows | codes and count identical; tau rtol 1e-3 | scipy's trust-region optimiser path differs
between 1.17 and 1.18 (the port is bit-identical in the round-2 environment) |
| evaluation layer fed with the round-2 per-flight stats | rtol 1e-12 (observed 0) | same inputs, same
arithmetic |
| verdicts | identical | |

Sample: n = 4 control flights per group (holdout, partner, three paired arms): the smallest batch that gives
2 + 2
temporal halves and non-degenerate medians; the bootstrap uses 100 resamples (structure, not power, is
tested).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.validation.battery import Bootstrap, flight_stats_many, run_battery
from phalanx.validation.battery.config import TESTS
from phalanx.validation.guards import g0_audit, g1_counts, g1_distance, metadata_features
from phalanx.validation.reference import flight_stats_from_round2_npz
from phalanx.validation.testing import (
    PARTNER_TAIL,
    REFERENCE_TAIL,
    STANDIN_AFFINE,
    STANDIN_LSB,
    STANDIN_SENTINELS,
    control_flight,
    delay_family,
    fixture_sha256,
    g0_control_matrices,
    gate0_standin,
)

GOLDEN = Path(__file__).resolve().parents[2] / "src" / "phalanx" / "validation" / "golden"
RTOL, ATOL = 1e-9, 1e-12
TAU_RTOL = 1e-3
EVAL_RTOL = 1e-12
ARMS = ("arm_replicate", "arm_partner_tail", "arm_ff_delay")
STAT_ARRAYS = ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6")

pytestmark = pytest.mark.golden


@pytest.fixture(scope="module")
def golden():
    with np.load(GOLDEN / "round2_golden.npz", allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    meta = json.loads((GOLDEN / "round2_golden.json").read_text())
    return arrays, meta


@pytest.fixture(scope="module")
def records(golden):
    _, meta = golden
    n = meta["n_per_group"]
    H = [control_flight(i, REFERENCE_TAIL, "real") for i in range(n)]
    return {
        "holdout": H,
        "partner": [control_flight(100 + i, PARTNER_TAIL, "real") for i in range(n)],
        "arm_replicate": [control_flight(i, REFERENCE_TAIL, "replicate") for i in range(n)],
        "arm_partner_tail": [control_flight(i, PARTNER_TAIL, "sim") for i in range(n)],
        "arm_ff_delay": [delay_family(r, "FF", 2.0) for r in H],
    }


@pytest.fixture(scope="module")
def port_stats(records):
    return {g: flight_stats_many(recs) for g, recs in records.items()}


def _old_flight(arrays, group, i):
    pre = f"stats/{group}/{i}/"
    return {k[len(pre) :]: v for k, v in arrays.items() if k.startswith(pre)}


@pytest.fixture(scope="module")
def old_stats(golden, records):
    arrays, _ = golden
    return {
        g: [flight_stats_from_round2_npz(_old_flight(arrays, g, i), r.flight_id) for i, r in enumerate(recs)]
        for g, recs in records.items()
    }


def _close(a, b, rtol=RTOL, atol=ATOL):
    np.testing.assert_allclose(
        np.asarray(a, float), np.asarray(b, float), rtol=rtol, atol=atol, equal_nan=True
    )


def test_control_inputs_bit_identical(golden, records):
    """The control flights regenerate bit-for-bit in this environment (else every comparison below is
    moot)."""
    _, meta = golden
    for g, recs in records.items():
        assert [fixture_sha256(r) for r in recs] == meta["inputs_sha256"][g], g


def test_flight_stats_match_round2(port_stats, old_stats):
    for g in port_stats:
        for new, old in zip(port_stats[g], old_stats[g], strict=True):
            assert new.air_frac == old.air_frac
            for k in STAT_ARRAYS:
                a, b = new.get(k), old.get(k)
                assert (a is None) == (b is None), (g, new.flight_id, k)
                if a is not None:
                    _close(a, b)
            for k in ("b5_ff", "b5_egt"):
                a, b = new.get(k), old.get(k)
                assert (a is None) == (b is None), (g, new.flight_id, k)
                for m in ("XtX", "Xty", "yy", "sy", "n"):
                    _close(getattr(a, m), getattr(b, m))
            s_new, s_old = new.b3_steps, old.b3_steps
            assert s_new.shape == s_old.shape, (g, new.flight_id)
            np.testing.assert_array_equal(s_new[:, :2], s_old[:, :2])
            _close(s_new[:, 2], s_old[:, 2], rtol=TAU_RTOL, atol=0)


def _run(stats, n_boot, seed):
    return run_battery(
        stats["holdout"],
        stats["partner"],
        [0, 1],
        [2, 3],
        {a: stats[a] for a in ARMS},
        Bootstrap(np.random.SeedSequence(seed), n_boot),
    )


def _check_report(rep, arrays, meta, rtol, b3ii_rtol):
    bat = meta["battery"]
    for name, cmp in (("D_tail", rep.d_tail), ("D_temp", rep.d_temp)):
        for t in TESTS:
            tol = b3ii_rtol if t == "B3ii" else rtol
            _close(cmp[t].D, bat[name][t], rtol=tol, atol=0)
            _close(cmp[t].boot, arrays[f"boot/{name}/{t}"], rtol=tol, atol=0)
    for arm in ARMS:
        old = bat["arms"][arm]
        for t in TESTS:
            tol = b3ii_rtol if t == "B3ii" else rtol
            _close(rep.arms[arm].d_sim[t].D, old["D_sim"][t], rtol=tol, atol=0)
            _close(rep.arms[arm].d_sim[t].boot, arrays[f"boot/{arm}/{t}"], rtol=tol, atol=0)
        for test, ov in old["verdicts"].items():
            nv = rep.arms[arm].verdicts[test]
            assert nv.verdict == ov["verdict"], (arm, test)
            assert nv.strict_pass == ov["strict_pass"], (arm, test)
            for p, opv in ov["parts"].items():
                npv = nv.parts[p]
                assert npv.verdict == opv["verdict"], (arm, p)
                tol = b3ii_rtol if p == "B3ii" else rtol
                for k in ("D_sim", "D_tail", "D_temp", "lb95_one_sided_Dsim_minus_Dtail"):
                    _close(getattr(npv, k), opv[k], rtol=tol, atol=1e-15)
                _close(npv.D_sim_ci95, opv["D_sim_ci95"], rtol=tol, atol=1e-15)
                _close(npv.D_tail_ci95, opv["D_tail_ci95"], rtol=tol, atol=1e-15)


def test_evaluation_layer_exact_on_round2_stats(golden, old_stats):
    """Distances, bootstrap distributions, CIs and verdicts from the round-2 per-flight statistics."""
    arrays, meta = golden
    rep = _run(old_stats, meta["n_boot"], meta["bootstrap_seed"])
    _check_report(rep, arrays, meta, rtol=EVAL_RTOL, b3ii_rtol=EVAL_RTOL)


def test_end_to_end_port_matches_round2(golden, port_stats):
    """Port per-flight stats -> port battery equals round 2 (B3 ii within the stated tau tolerance)."""
    arrays, meta = golden
    rep = _run(port_stats, meta["n_boot"], meta["bootstrap_seed"])
    _check_report(rep, arrays, meta, rtol=RTOL, b3ii_rtol=TAU_RTOL)
    for arm in ARMS:
        new_g, old_g = rep.arms[arm].group, meta["battery"]["arms"][arm]["group"]
        assert new_g["n_flights"] == old_g["n_flights"]
        assert new_g["B3ii_n_steps"] == old_g["B3ii_n_steps"]
        _close(new_g["B1_fast_median"], old_g["B1_fast_median"])
        _close(new_g["B2_median_lags"], old_g["B2_median_lags"])
        _close(new_g["B5_scatter"], old_g["B5_scatter"])
        assert new_g["B5_a"] == old_g["B5_a"]


def test_g1_matches_round2(golden, records):
    arrays, meta = golden
    real = [g1_counts(r) for r in records["holdout"]]
    for i, c in enumerate(real):
        for f, v in c.items():
            np.testing.assert_array_equal(v, arrays[f"stats/holdout/{i}/g1_{f}"])
    for arm in ARMS:
        syn = [g1_counts(r) for r in records[arm]]
        new = g1_distance(syn, real)
        for f, old in meta["battery"]["arms"][arm]["G1"].items():
            assert new[f]["tv_distance"] == old["tv_distance"], (arm, f)
            assert new[f]["residues_syn"] == old["residues_syn"]
            assert new[f]["residues_real"] == old["residues_real"]


def test_g0_metadata_matches_round2(golden, records):
    arrays, meta = golden
    for i, rec in enumerate(records["holdout"][:2]):
        for dt in ("float32", "float64"):
            ch, frames, rec_s = gate0_standin(rec, dt)
            v, names = metadata_features(
                ch, frames, rec_s, lsb=STANDIN_LSB, sentinels=STANDIN_SENTINELS, affine=STANDIN_AFFINE
            )
            assert names == meta["g0_feature_names"]
            np.testing.assert_array_equal(v, arrays[f"g0file/{i}/{dt}"])


def test_g0_audit_matches_round2(golden):
    """Round-2 G0 reproduces through the pre-registered two-sided rule (`sided="two"`). Seed-independent cases
    match fully; the null case matches for LR (the GB draw seed is derived by spawn key in the port instead of
    round-1 seed arithmetic, a documented deviation). The default one-sided rule (owner decision, AD-40) does
    not FAIL the null case that the two-sided rule falsely FAILs (A-W0.5-4)."""
    _, meta = golden
    M = g0_control_matrices(40)
    names = [str(x) for x in M["names"]]
    cases = {
        "identical": (M["null_A"], M["null_A"].copy()),
        "null": (M["null_A"], M["null_B"]),
        "separable": (M["sep_A"], M["sep_B"]),
    }
    for case, (XA, XB) in cases.items():
        new = g0_audit(XA, XB, names, paired=True, seed=11, sided="two")
        old = meta["g0_audit"][case]
        kinds = ("lr",) if case == "null" else ("lr", "gb")
        for k in kinds:
            assert new.classifiers[k]["auc"] == pytest.approx(old["classifiers"][k]["auc"], rel=1e-12)
            _close(new.classifiers[k]["ci95"], old["classifiers"][k]["ci95"], rtol=1e-12)
            assert new.classifiers[k]["pass"] == old["classifiers"][k]["pass"]
        if case != "null":
            assert new.passed == old["pass"]
        else:
            # the pre-registered two-sided rule falsely FAILs null metadata: the grouped-CV boosting AUC falls
            # below chance (round 1 and port alike)
            assert old["pass"] is False and new.passed is False
            assert new.classifiers["gb"]["ci95"][1] < 0.5 and old["classifiers"]["gb"]["ci95"][1] < 0.5
        assert [list(t)[:2] for t in new.top_univariate] == [list(t)[:2] for t in old["top_univariate"]]
        one = g0_audit(XA, XB, names, paired=True, seed=11)  # default: one-sided
        assert one.sided == "one" and one.classifiers["lr"]["ci95"] == new.classifiers["lr"]["ci95"]
        assert one.passed is (case != "separable")  # null: not a FAIL; real cue: still FAILs
