"""Data-free boundary golden: the port equals the ORIGINAL round-1/round-2 code on inputs placed exactly on
the
battery's thresholds, so a change of any threshold by one sample (or a fraction of an LSB) fails `make check`.

Fixture: `src/phalanx/validation/golden/round2_boundaries.{npz,json}` from `make_round2_boundaries.py`
(original
code, read-only, round-2 environment). Inputs: `phalanx.validation.boundary_fixtures` (CONTROL FIXTURE,
bit-reproducible; SHA-256 checked). Each threshold has a case just inside and one just outside (module table).

Tolerances (build vs round-2 environment): per-flight statistics rtol 1e-9, B3 (ii) tau rtol 1e-3 (scipy
optimiser path), presence / NaN pattern and step codes exact; `find_steps`, the evaluation layer, the decision
rule, classifier settings, folds, bootstrap indices and G0 metadata exact; DASHlink adapter rtol 1e-12.
Sample: the fixtures are single constructed flights or traces per threshold; n is not a statistical quantity
here.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.rng import RngService, StreamRegistry
from phalanx.validation import dashlink as D
from phalanx.validation.battery import BOOTSTRAP_STREAM, Bootstrap, decision, flight_stats_many
from phalanx.validation.battery.config import N_BOOT, TESTS, VERDICT_TESTS
from phalanx.validation.battery.evaluate import PartResult, TestResult, group_values, stat_value
from phalanx.validation.battery.stats import FlightStats, find_steps
from phalanx.validation.boundary_fixtures import (
    BOUNDARY_FLIGHTS,
    DECISION_PATTERNS,
    STEP_GROUPS,
    adapter_inputs,
    boundary_flight,
    gate0_boundary_channels,
    mach_trace,
    pla_traces,
    write_mat,
)
from phalanx.validation.guards import classify as CL
from phalanx.validation.guards import g0_audit, label_leak_audit, metadata_features
from phalanx.validation.reference import flight_stats_from_round2_npz
from phalanx.validation.testing import STANDIN_AFFINE, STANDIN_LSB, STANDIN_SENTINELS, fixture_sha256

GOLDEN = Path(__file__).resolve().parents[2] / "src" / "phalanx" / "validation" / "golden"
STATS = ("b1_slow", "b1_fast", "b1h_slow", "b1h_fast", "b2", "b3_coh", "b3_lgain", "b4", "b6")
pytestmark = pytest.mark.golden


@pytest.fixture(scope="module")
def golden():
    with np.load(GOLDEN / "round2_boundaries.npz", allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    return arrays, json.loads((GOLDEN / "round2_boundaries.json").read_text())


@pytest.fixture(scope="module")
def records():
    return {name: boundary_flight(name) for name in BOUNDARY_FLIGHTS}


@pytest.fixture(scope="module")
def port(records):
    return dict(zip(records, flight_stats_many(list(records.values())), strict=True))


@pytest.fixture(scope="module")
def old(golden, records):
    arrays, _ = golden

    def one(name):
        pre = f"stats/{name}/"
        return flight_stats_from_round2_npz(
            {k[len(pre) :]: v for k, v in arrays.items() if k.startswith(pre)}, f"bnd_{name}"
        )

    return {name: one(name) for name in records}


def _close(a, b, rtol=1e-9):
    np.testing.assert_allclose(
        np.asarray(a, float), np.asarray(b, float), rtol=rtol, atol=1e-15, equal_nan=True
    )


def test_boundary_inputs_bit_identical(golden, records):
    _, meta = golden
    assert {n: fixture_sha256(r) for n, r in records.items()} == meta["inputs_sha256"]


def test_threshold_flights_land_on_the_designed_side(port):
    """Self-check of the fixture design (independent of round 2): each pair straddles its threshold."""
    p = port
    assert p["air600"].b1_fast is not None and p["air599"].b1_fast is None  # >= 600 airborne samples
    assert p["air600"].b2 is not None and p["air599"].b2 is None
    assert p["b5_597"].b5_ff is not None and p["b5_596"].b5_ff is None  # >= 150 decimated samples
    assert p["run2400"].b3_coh is not None and p["run2399"].b3_coh is None  # run >= 600 s
    assert p["seg480"].b4 is not None and p["seg479"].b4 is None  # segment >= 120 s
    assert np.log(1e-6) in p["seg480"].b4.tolist()  # F floor on a constant cause
    assert np.all(np.isfinite(p["ph40"].b6[3])) and np.all(np.isnan(p["ph40"].b6[5]))  # 40 kept, 39 missing
    assert p["n1_edge"].air_frac == 0.7  # N1 = 25.0 not airborne, 25.03125 airborne
    assert p["lag_edge"].b2[:5].tolist() == [10.0, 9.0, 0.25, 9.75, -0.5]  # 10 s inside, 10.25 s outside
    st = p["steps_edge"].b3_steps
    assert st.shape == (18, 3)  # 7 accel + 11 decel rows (see boundary_fixtures)
    assert np.sum(st[:, 1] == 0) == 7 and np.sum(st[:, 1] == 1) == 11


def test_threshold_flights_match_round2(port, old):
    for name in port:
        a, b = port[name], old[name]
        assert a.air_frac == b.air_frac, name
        for k in STATS:
            assert (a.get(k) is None) == (b.get(k) is None), (name, k)
            if a.get(k) is not None:
                assert np.array_equal(np.isnan(a.get(k)), np.isnan(b.get(k))), (name, k)
                _close(a.get(k), b.get(k))
        for k in ("b5_ff", "b5_egt"):
            assert (a.get(k) is None) == (b.get(k) is None), (name, k)
            if a.get(k) is not None:
                for m in ("XtX", "Xty", "yy", "sy", "n"):
                    _close(getattr(a.get(k), m), getattr(b.get(k), m))
        assert a.b3_steps.shape == b.b3_steps.shape, name
        np.testing.assert_array_equal(a.b3_steps[:, :2], b.b3_steps[:, :2])
        _close(a.b3_steps[:, 2], b.b3_steps[:, 2], rtol=1e-3)


def test_find_steps_matches_round1_detector(golden):
    """round-1 `transients.find_steps` on traces at every one of its literals (jump, ranges, onset, windows,
    skip, scan bounds): onset index and pre/post means identical."""
    arrays, _ = golden
    traces = pla_traces()
    assert set(traces) == {k[len("steps/") :] for k in arrays if k.startswith("steps/")}
    for name, pla in traces.items():
        new = np.array([(j, pm, qm) for j, pm, qm in find_steps(pla)], float).reshape(-1, 3)
        np.testing.assert_array_equal(new, arrays[f"steps/{name}"], err_msg=name)
    assert len(find_steps(traces["jump_0"])) == 1 and len(find_steps(traces["jump_m"])) == 0


def _fs(rows):
    return FlightStats(flight_id="x", air_frac=1.0, b3_steps=np.array(rows, float).reshape(-1, 3))


def test_evaluation_boundaries_match_round2(golden, old):
    """B3 (ii) needs >= 3 steps per cell; every distance needs >= 2 flights per group; GO needs >= 4 PASS."""
    _, meta = golden
    A = [_fs(r) for r in STEP_GROUPS["A"]]
    B = [_fs(r) for r in STEP_GROUPS["B"]]
    assert stat_value("B3ii", A, B) == meta["b3ii"]["A_vs_B"]
    assert stat_value("B3ii", B, A) == meta["b3ii"]["B_vs_A"]
    assert group_values(A)["B3ii_median_tau"] == meta["b3ii"]["tau_A"]
    assert group_values(B)["B3ii_median_tau"] == meta["b3ii"]["tau_B"]
    one = ([old["air600"]], [old["run2400"]])
    two = ([old["air600"], old["ph40"]], [old["run2400"], old["n1_edge"]])
    for t in TESTS:
        for name, groups in (("one", one), ("two", two)):
            want = meta["min_flights"][name][t]
            got = stat_value(t, *groups)
            assert (np.isnan(got) and np.isnan(want)) or got == pytest.approx(want, rel=1e-12), (name, t)
    for name, (vs, g0) in DECISION_PATTERNS.items():
        ver = {
            t: TestResult(t, v, None, {p: _part(p, v) for p in VERDICT_TESTS[t]})
            for t, v in zip(VERDICT_TESTS, vs, strict=True)
        }
        assert decision(ver, g0) == meta["decision"][name], name


def _part(p, v):
    return PartResult(p, 0.0, 0.0, None, 0.0, v, None, (0.0, 0.0), (0.0, 0.0), {})


def test_bootstrap_resample_count_is_the_preregistered_one(golden):
    _, meta = golden
    assert N_BOOT == meta["NB"] == 2000
    assert Bootstrap(np.random.SeedSequence(1)).nb == N_BOOT
    svc = RngService(1, StreamRegistry([BOOTSTRAP_STREAM]))
    assert Bootstrap.from_service(svc, "x").nb == N_BOOT
    for fn, arg in ((g0_audit, "n_boot"), (label_leak_audit, "n_boot"), (CL.boot_indices, "B")):
        assert inspect.signature(fn).parameters[arg].default == N_BOOT


def test_classifier_settings_match_round1(golden):
    """Round-1 `learn`: model hyper-parameters, K x REPEATS folds and bootstrap index sets."""
    arrays, meta = golden
    L = meta["learn"]
    assert (CL.K, CL.REPEATS) == (L["K"], L["REPEATS"])
    lr = CL.make_model("lr").get_params(deep=True)
    lr = {k: v for k, v in lr.items() if isinstance(v, (int, float, str, bool, type(None)))}
    assert set(lr) == set(L["lr"])
    for k, v in L["lr"].items():
        assert (isinstance(v, float) and np.isnan(v) and np.isnan(lr[k])) or lr[k] == v, k
    gb = {k: v for k, v in CL.make_model("gb", 0).get_params().items() if k != "random_state"}
    assert gb == L["gb"]
    groups = np.repeat(np.arange(13), 2)
    for r, fl in enumerate(CL.folds(groups, 11)):
        fold_of = np.sum([k * te for k, (_, te) in enumerate(fl)], axis=0)
        np.testing.assert_array_equal(fold_of, arrays[f"learn/fold_of/{r}"])
    y = np.r_[np.zeros(9, int), np.ones(9, int)]
    pid = np.r_[np.arange(9), np.arange(9)]
    np.testing.assert_array_equal(np.array(CL.boot_indices(y, pid, 7, 3)), arrays["learn/boot_paired"])
    np.testing.assert_array_equal(np.array(CL.boot_indices(y, None, 7, 3)), arrays["learn/boot_unpaired"])


def test_g0_boundary_metadata_matches_round1(golden):
    """Lattice fractions either side of 1e-3, sentinel distances either side of 1e-6, bin-edge fractions."""
    arrays, meta = golden
    ch, frames, rec_s = gate0_boundary_channels()
    v, names = metadata_features(
        ch, frames, rec_s, lsb=STANDIN_LSB, sentinels=STANDIN_SENTINELS, affine=STANDIN_AFFINE
    )
    assert names == meta["g0_names"]
    np.testing.assert_array_equal(v, arrays["g0/boundary"])
    d = dict(zip(names, v, strict=True))
    assert d["N1_1_lat_on"] == pytest.approx(2 / 6, abs=0.01) and d["FF_1_n_sentinel"] == 20.0


def test_dashlink_adapter_matches_round2(golden, tmp_path):
    """`_clean_mach` (2-s window, median > 0.15), ISA corrections across the tropopause, and the 4-Hz load."""
    arrays, meta = golden
    a = adapter_inputs()
    np.testing.assert_array_equal(D._clean_mach(mach_trace()), arrays["adapter/clean_mach"])
    th, de = D.corrections(a["alt"], a["mach"], a["tat"])
    _close(th, arrays["adapter/theta"], rtol=1e-12)
    _close(de, arrays["adapter/delta"], rtol=1e-12)
    _close(D.delta_static(a["alt"]), arrays["adapter/delta_static"], rtol=1e-12)
    p = tmp_path / "652209901010000.mat"
    write_mat(p)
    r = D.load_record(p)
    assert r.n == meta["adapter_load"]["n"] and r.flight_id == meta["adapter_load"]["fid"]
    np.testing.assert_array_equal(r.pla, arrays["adapter/load/PLA"])
    np.testing.assert_array_equal(r.phase, arrays["adapter/load/PH"])
    _close(r.theta, arrays["adapter/load/theta"], rtol=1e-12)
    _close(r.delta, arrays["adapter/load/delta"], rtol=1e-12)
    for f in ("N1", "N2", "EGT", "FF"):
        np.testing.assert_array_equal(r.outputs[f], arrays[f"adapter/load/Y/{f}"])
