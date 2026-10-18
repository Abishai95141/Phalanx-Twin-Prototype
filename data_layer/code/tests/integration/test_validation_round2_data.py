"""A1 (data) and real-data A3/A4: the port reproduces round 2 on the 20-flight sample batch `holdout_652_s20`.

Sample: n = 20 flights per group (Tail 652 holdout, the Tail 687-TEST partner, each synthetic arm), the
round-2 sample batch that the pre-registration ran before its full run (prereg section 7). It is the minimal
sample on which every stored round-2 number exists; it exercises every estimator and every verdict branch
(PASS, FAIL, INCONCLUSIVE all occur in the stored results). Arms recomputed from MAT files: S_R2a_prior,
S_R2b_prior (the decision arm), P_R2a_prior (has an INCONCLUSIVE part) and R1ref (has PASS parts); the
evaluation layer is checked on all 9 arms from the stored per-flight statistics.

Tolerances (build environment numpy 2.5 / scipy 1.18 vs round-2 numpy 2.3.5 / scipy 1.17.1):
- evaluation layer on the stored per-flight stats: rtol 1e-12 (observed: bit-identical);
- per-flight stats from MAT: rtol 1e-9 (observed max ~1e-11), except B3 (ii) tau rtol 1e-3 (observed max
  1.7e-4: scipy least-squares path); in the round-2 environment the port is bit-identical (verified once);
- distances, CIs and bounds end to end: rtol 1e-9, B3 (ii) rtol 1e-3; verdicts identical.

Data: Tail 652 and Tail 687 archive 1 (read-only; `PHALANX_DASHLINK_652`, `PHALANX_DASHLINK_687`), stored
round-2 synthetic MAT files and statistics (`PHALANX_ROUND2_SYNTHETIC`). Tail 687 archive 2 is never touched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import RngService, StreamRegistry
from phalanx.validation import dashlink as D
from phalanx.validation.battery import (
    ROUND2_ROOT_SEED,
    Bootstrap,
    compare,
    flight_stats_many,
    run_battery,
    verdicts,
)
from phalanx.validation.battery.config import TESTS
from phalanx.validation.guards import g0_audit, g1_counts, g1_distance
from phalanx.validation.reference import (
    ROUND2_LABELS,
    load_round2_battery,
    load_round2_lists,
    load_round2_stats,
)
from phalanx.validation.samples import SAMPLE_STREAM, select_flights
from phalanx.validation.testing import decouple_fast_band, delay_family, dither_requantise

pytestmark = [pytest.mark.data, pytest.mark.slow, pytest.mark.integration]

TAG = "holdout_652_s20"
ARMS_FROM_MAT = ("S_R2a_prior", "S_R2b_prior", "P_R2a_prior", "R1ref")
RTOL, TAU_RTOL, EVAL_RTOL = 1e-9, 1e-3, 1e-12
STATS = ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6")


@pytest.fixture(scope="module")
def paths(repo_root, dashlink_652_dir, dashlink_687_dir):
    syn = Path(
        os.environ.get(
            "PHALANX_ROUND2_SYNTHETIC",
            "/Users/abishaikc/Phalanx/research_sources/settling_round2_synthetic",
        )
    )
    if not (syn / "652_s20" / "_stats").is_dir():
        pytest.skip("round-2 synthetic files / statistics not available")
    res = repo_root / "analysis" / "settling_experiment_round2" / "results"
    return {
        "res": res / TAG,
        "res_full": res / "holdout_652",
        "syn": syn / "652_s20",
        "m652": dashlink_652_dir,
        "m687": dashlink_687_dir,
        "tex": repo_root / "analysis" / "dashlink_texture" / "results",
        "r1": repo_root / "analysis" / "settling_experiment" / "results",
    }


@pytest.fixture(scope="module")
def lists(paths):
    return load_round2_lists(paths["res"])


@pytest.fixture(scope="module")
def stored(paths):
    return load_round2_battery(paths["res"])


@pytest.fixture(scope="module")
def records(paths, lists):
    H = [D.load_record(paths["m652"] / f) for f in lists["holdout"]]
    recs = {"real_holdout": H, "real_partner": [D.load_record(paths["m687"] / f) for f in lists["partner"]]}
    for lab in ARMS_FROM_MAT:
        recs[lab] = [D.load_record(paths["syn"] / lab / f) for f in lists["holdout"]]
    return recs


@pytest.fixture(scope="module")
def port_stats(records):
    return {k: flight_stats_many(v) for k, v in records.items()}


def _idx(lists):
    i = {f: k for k, f in enumerate(lists["holdout"])}
    return [i[f] for f in lists["early"]], [i[f] for f in lists["late"]]


def _close(a, b, rtol):
    np.testing.assert_allclose(
        np.asarray(a, float), np.asarray(b, float), rtol=rtol, atol=1e-15, equal_nan=True
    )


def _check_against_stored(rep, stored, arms, rtol, b3ii_rtol):
    for bar, cmp in (("D_tail", rep.d_tail), ("D_temp", rep.d_temp)):
        for t in TESTS:
            tol = b3ii_rtol if t == "B3ii" else rtol
            _close(cmp[t].D, stored[bar][t]["D"], tol)
            _close(cmp[t].ci95, stored[bar][t]["ci95"], tol)
    for lab in arms:
        old, new = stored["arms"][lab], rep.arms[lab]
        for t in TESTS:
            tol = b3ii_rtol if t == "B3ii" else rtol
            _close(new.d_sim[t].D, old["D_sim"][t]["D"], tol)
            _close(new.d_sim[t].ci95, old["D_sim"][t]["ci95"], tol)
        for test, ov in old["verdicts"].items():
            nv = new.verdicts[test]
            assert (nv.verdict, nv.strict_pass) == (ov["verdict"], ov["strict_pass"]), (lab, test)
            for p, opv in ov["parts"].items():
                tol = b3ii_rtol if p == "B3ii" else rtol
                npv = nv.parts[p]
                assert npv.verdict == opv["verdict"], (lab, p)
                for k in ("D_sim", "D_tail", "lb95_one_sided_Dsim_minus_Dtail"):
                    _close(getattr(npv, k), opv[k], tol)


def test_a1_evaluation_layer_reproduces_battery_json(paths, lists, stored):
    """All 9 round-2 arms, from the stored per-flight statistics: every distance, CI, bound and verdict."""
    S = {lab: load_round2_stats(paths["syn"] / "_stats", lab, lists["holdout"]) for lab in ROUND2_LABELS}
    SH = load_round2_stats(paths["syn"] / "_stats", "real_holdout", lists["holdout"])
    SP = load_round2_stats(paths["syn"] / "_stats", "real_partner", lists["partner"])
    early, late = _idx(lists)
    rep = run_battery(SH, SP, early, late, S, Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED)))
    assert rep.n_flights["holdout"] == rep.n_flights["partner"] == 20
    _check_against_stored(rep, stored, ROUND2_LABELS, EVAL_RTOL, EVAL_RTOL)
    for lab in ROUND2_LABELS:
        assert rep.arms[lab].group["B5_a"] == stored["arms"][lab]["group"]["B5_a"]


def test_a1_flight_stats_from_mat_reproduce_round2(paths, lists, port_stats):
    for lab, new in port_stats.items():
        files = lists["partner"] if lab == "real_partner" else lists["holdout"]
        old = load_round2_stats(paths["syn"] / "_stats", lab, files)
        assert len(new) == len(old) == 20
        for a, b in zip(new, old, strict=True):
            assert a.air_frac == b.air_frac
            for k in STATS:
                assert (a.get(k) is None) == (b.get(k) is None), (lab, a.flight_id, k)
                if a.get(k) is not None:
                    _close(a.get(k), b.get(k), RTOL)
            for k in ("b5_ff", "b5_egt"):
                for m in ("XtX", "Xty", "yy", "sy", "n"):
                    _close(getattr(a.get(k), m), getattr(b.get(k), m), RTOL)
            assert a.b3_steps.shape == b.b3_steps.shape, (lab, a.flight_id)
            np.testing.assert_array_equal(a.b3_steps[:, :2], b.b3_steps[:, :2])
            _close(a.b3_steps[:, 2], b.b3_steps[:, 2], TAU_RTOL)


def test_a1_end_to_end_battery_reproduces_round2(lists, stored, port_stats):
    """MAT files -> port statistics -> port battery equals the stored round-2 battery for the recomputed
    arms."""
    early, late = _idx(lists)
    arms = {lab: port_stats[lab] for lab in ARMS_FROM_MAT}
    rep = run_battery(
        port_stats["real_holdout"],
        port_stats["real_partner"],
        early,
        late,
        arms,
        Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED)),
    )
    _check_against_stored(rep, stored, ARMS_FROM_MAT, RTOL, TAU_RTOL)


def test_a4_g0_and_g1_reproduce_round2(paths, lists, stored, records):
    """G0 metadata vectors (342 features), the binding pipeline-only audit and G1 equal round 2 exactly."""
    lsb = D.load_lsb(paths["tex"] / "param_table.csv")
    sent = D.load_sentinels(paths["tex"] / "dropouts_sentinels.csv")
    aff = D.load_vrtg_affine(paths["r1"] / "model_params_primary.json")
    names_old = json.loads((paths["syn"] / "_features" / "real" / "_names.json").read_text())["gate0"]
    rows = {"real": [], "S_R2a_prior": []}
    for lab, src in (("real", paths["m652"]), ("S_R2a_prior", paths["syn"] / "S_R2a_prior")):
        for f in lists["holdout"]:
            v, names = D.gate0_metadata(src / f, lsb=lsb, sentinels=sent, affine=aff)
            assert names == names_old
            with np.load(
                paths["syn"] / "_features" / lab / f.replace(".mat", ".npz"), allow_pickle=False
            ) as z:
                np.testing.assert_array_equal(v, z["gate0"])
            rows[lab].append(v)
    res = g0_audit(
        np.vstack(rows["real"]), np.vstack(rows["S_R2a_prior"]), names, paired=True, seed=7, sided="two"
    )
    old = json.loads((paths["res"] / "disc" / "S_R2a_prior.json").read_text())["G0_pipeline_only"]
    assert res.passed == old["pass"] is True
    for k in ("lr", "gb"):
        assert res.classifiers[k]["auc"] == old["classifiers"][k]["auc"]
        assert res.classifiers[k]["ci95"] == old["classifiers"][k]["ci95"]
    assert [list(t) for t in res.top_univariate] == old["top_univariate"]
    real = [g1_counts(r) for r in records["real_holdout"]]
    for lab in ARMS_FROM_MAT:
        g = g1_distance([g1_counts(r) for r in records[lab]], real)
        for f, v in stored["arms"][lab]["G1"].items():
            assert g[f]["tv_distance"] == v["tv_distance"] and g[f]["residues_syn"] == v["residues_syn"]


def test_a3_real_data_controls(paths, lists, records, port_stats):
    """Real-data controls on the s20 batch (2,000 resamples, round-2 seed):
    - fast-band decoupling of the real flights FAILs B1 and B4; FF delayed 2 s FAILs B2;
    - excess independent noise of +-1 LSB FAILs B1 (finding: the fast band is quantisation-dominated);
    - real-vs-real: 20 other Tail 652 flights (unpaired, selector stream `validation.flight_sample`) draw no
    FAIL.
    """
    H = records["real_holdout"]
    arms = {
        "decoupled": flight_stats_many([decouple_fast_band(r) for r in H]),
        "ff_delay_2s": flight_stats_many([delay_family(r, "FF", 2.0) for r in H]),
        "noise_1lsb": flight_stats_many([dither_requantise(r) for r in H]),
    }
    early, late = _idx(lists)
    SH, SP = port_stats["real_holdout"], port_stats["real_partner"]
    rep = run_battery(SH, SP, early, late, arms, Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED)))
    v = {lab: {t: x.verdict for t, x in a.verdicts.items()} for lab, a in rep.arms.items()}
    assert v["decoupled"]["B1"] == "FAIL" and v["decoupled"]["B4"] == "FAIL"
    assert v["ff_delay_2s"]["B2"] == "FAIL"
    assert v["noise_1lsb"]["B1"] == "FAIL"
    rest = sorted(set(load_round2_lists(paths["res_full"])["holdout"]) - set(lists["holdout"]))
    other = select_flights(
        rest,
        20,
        rng=RngService(20261014, StreamRegistry([SAMPLE_STREAM])),
        scenario="w05.real_vs_real",
        purpose="real-vs-real positive control",
        justification="equal count to the 20-flight holdout batch (prereg section 2)",
    )
    SO = flight_stats_many([D.load_record(paths["m652"] / f) for f in other.flights])
    boot = Bootstrap(np.random.SeedSequence(ROUND2_ROOT_SEED))
    tail = compare(SP, SH, "partner", "holdout", False, boot)
    temp = compare([SH[i] for i in late], [SH[i] for i in early], "late", "early", False, boot)
    rr = verdicts(compare(SO, SH, "other652", "holdout", False, boot), tail, temp)
    assert all(x.verdict != "FAIL" for x in rr.values()), {t: x.verdict for t, x in rr.items()}
    assert rr["B1"].verdict == "PASS"
