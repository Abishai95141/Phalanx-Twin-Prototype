"""W2.1b entry gate 2 / AD-50: the committed M08 schedules are the ones derived from the nominal M07 model.

Drift test: `phalanx.fadec.harmonise` re-derives every harmonised table (VG = M07's reference schedules, the
core-speed demand, ratio units, on-board model) and the nozzle scalars from the current M07 model, and they
must equal what is committed under `configs/tejas/params/M08/` and in M08.yaml (at the CSV resolution, 1e-6).
So an M07 recalibration (W2.3) or identification (W2.4a) that is not followed by a regeneration fails here,
and the FADEC can never silently drift back to fixture-matched tables. Negative control: a 2 % HPC-efficiency
change in M07 moves the derived tables by far more than the tolerance (the test can fail).

Structural checks on the derived schedules (A-W2.1b-1): VG schedules equal M07's `vg_reference` at the M08
breakpoints; the nozzle floor at the N1-limit onset is the throat where M07 reaches the N1 and T5 limits
together (no step in the throttle map), the IRP floor is below it (the T5 loop holds T5 at IRP) and the
clamps are M07's actuator stops; the demand passes through the two anchors; the line is monotonic and ends at
N1 = N1 limit with T5 = T5 limit.

Sample: deterministic derivation (one nominal model, one perturbed); no randomness.
"""

from __future__ import annotations

import csv
import itertools

import numpy as np
import pytest

from phalanx.dictionary.params import params_dir
from phalanx.engine.design import build_engine_model
from phalanx.engine.layout import PI
from phalanx.engine.steady import vg_reference
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.harmonise import CSV_DECIMALS, IN2, harmonise
from phalanx.fadec.layout import P_LAYOUT

pytestmark = pytest.mark.integration
TOL = 1.5 * 10.0**-CSV_DECIMALS


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


@pytest.fixture(scope="module")
def derived(model):
    return harmonise(model)


def _committed(name: str) -> tuple[list[str], np.ndarray]:
    rows = list(csv.reader((params_dir("tejas") / "M08" / f"{name}.csv").read_text().splitlines()))
    return rows[0], np.array([[float(c) for c in r] for r in rows[1:] if r])


def _max_dev(h) -> float:
    dev = 0.0
    for name, (head, cols) in h.tables.items():
        chead, arr = _committed(name)
        assert tuple(chead) == head, name
        got = np.column_stack(cols)
        if got.shape != arr.shape:
            return np.inf
        dev = max(dev, float(np.max(np.abs(got - arr) / np.maximum(1.0, np.abs(arr)))))
    return dev


def test_committed_m08_schedules_equal_the_m07_derivation(derived):
    assert _max_dev(derived) <= TOL
    ps = load_fadec_params()
    assert ps.value("a8_scale") == pytest.approx(derived.scalars["a8_scale"], rel=2e-6)
    # M08.yaml stores the clamps in in2 to 6 decimals (CSV_DECIMALS): compare to that rounding
    assert ps.value("a8_min") == pytest.approx(derived.scalars["a8_min"] * IN2, abs=0.6e-6 * IN2)
    assert ps.value("a8_max") == pytest.approx(derived.scalars["a8_max"] * IN2, abs=0.6e-6 * IN2)


def test_drift_test_negative_control_a_changed_m07_moves_the_tables(model):
    """A 2 % HPC efficiency change (a plausible W2.3 recalibration) changes the derived schedules by far
    more than the tolerance, so the drift test above would fail until the tables are regenerated."""
    pert = model.with_p(s_eff_hpc=0.98 * float(model.p[PI["s_eff_hpc"]]))
    assert _max_dev(harmonise(pert)) > 100 * TOL


def test_harmonised_schedules_are_tied_to_m07(model, derived):
    cfg = FadecConfig.build(load_fadec_params())
    tb = cfg.tables
    der = model.design.derived
    # VG = M07's reference schedule at M08's breakpoints (CVG re-based to fractions of 16,810 rpm)
    for x in np.linspace(0.6, 1.08, 25):
        f, _ = vg_reference(model, x, 1.0)
        assert np.interp(x, tb.fvg_x, tb.fvg_y) == pytest.approx(float(f), abs=2e-5)
    for x in np.linspace(0.5, 0.8, 25):
        _, c = vg_reference(model, 1.0, x * 16810.0 / der["n2c_des_rpm"])
        assert np.interp(x, tb.cvg_x, tb.cvg_y) == pytest.approx(float(c), abs=2e-5)
    # nozzle: the onset floor is the N1/T5 coincidence throat, the IRP floor is below it; clamps = M07 stops
    p = {k: float(cfg.p[i]) for k, i in P_LAYOUT.index.items()}
    ps = load_fadec_params()
    n1on = float(ps.value("harm_n1_onset_pla"))
    floor_on = float(np.interp(n1on, tb.a8_pla_x, tb.a8_pla_y)) * p["a8_scale"]
    floor_irp = float(np.interp(p["pla_irp"], tb.a8_pla_x, tb.a8_pla_y)) * p["a8_scale"]
    assert floor_on == pytest.approx(derived.anchors["a8_star_m2"], rel=2e-6)
    assert floor_irp < derived.anchors["a8_star_m2"]
    assert p["a8_min"] * p["a8_scale"] == pytest.approx(float(model.p[PI["a8_min"]]), rel=2e-6)
    assert p["a8_max"] * p["a8_scale"] == pytest.approx(float(model.p[PI["a8_max"]]), rel=2e-6)
    # the demand passes through both anchors and the operating line is monotonic
    gi = float(ps.value("pla_gi"))
    assert np.interp(gi, tb.n2c_pla_x, tb.n2c_pla_y) == pytest.approx(derived.anchors["idle_n2c25"], abs=TOL)
    assert np.interp(n1on, tb.n2c_pla_x, tb.n2c_pla_y) == pytest.approx(
        derived.anchors["n1_onset_n2c25"], abs=TOL
    )
    line = derived.line
    # the closed-loop idle point runs M08's VG tables (M07's reference sampled at M08 breakpoints, linear in
    # between), so its T2.5 and hence physical N2 differ from the reference-VG anchor trim by the
    # interpolation error (measured 6e-5)
    # (W2.3a: the line is the installed engine's, nominal extraction on; the anchors stay on the bare engine)
    assert line[0].n2 == pytest.approx(float(ps.value("harm_idle_n2")), rel=1e-3)
    assert derived.anchors["n1_onset_n1"] == pytest.approx(1.02, rel=1e-9)
    for a, b in itertools.pairwise(line):
        assert b.n2 > a.n2 and b.n1 > a.n1 and b.wf_kgs > a.wf_kgs and b.fn_n > a.fn_n
    assert line[-1].n1 == pytest.approx(1.02, rel=1e-6)
    assert line[-1].t5_k == pytest.approx(float(cfg.tables.t5lim_y[0]), abs=1e-3)


def test_installed_design_condition_and_sub_idle_line(model, derived):
    """W2.3a (A-W2.3-1): the fuel-control lines are the installed engine's: with the nominal extraction the
    steady Wf/PS3 at ground idle is above the bare engine's, and below idle the reference follows M07's
    installed steady line (one point per SUB_IDLE_STEP down to harm_line_min_n2c), where Wf/PS3 rises as N2
    falls (the W1.3b shape it replaced fell). Negative control: the bare derivation gives a lower idle
    line."""
    from phalanx.fadec.harmonise import SUB_IDLE_STEP

    ps = load_fadec_params()
    sub = derived.sub_idle
    lo = float(ps.value("harm_line_min_n2c"))
    assert sub[0].n2c1 == pytest.approx(lo, abs=1e-6)
    assert len(sub) == round((derived.line[0].n2c1 - lo) / SUB_IDLE_STEP)
    ru_sub = [q.ru_pph_psi for q in sub]
    assert all(b < a for a, b in itertools.pairwise(ru_sub))  # Wf/PS3 falls as N2 rises below idle
    assert ru_sub[-1] > derived.line[0].ru_pph_psi
    bare = harmonise(model, ps.replace(harm_bleed=0.0, harm_pto=0.0))
    assert derived.line[0].ru_pph_psi > 1.05 * bare.line[0].ru_pph_psi


def test_governor_gain_schedule_follows_the_line_slope(derived):
    """W2.3a (A-W2.3-3): the governor gain multiplier is >= 1 everywhere, exactly 1 where the installed steady
    Wf/PS3 rises with N2 (part power and above: AD-57's Kp unchanged there) and > 1 where it falls (ground
    idle); negative control on the function: a rising line gives 1 everywhere."""
    from phalanx.fadec.harmonise import governor_gain_schedule

    _h, (x, g) = derived.tables["gov_ks"]
    assert np.all(np.diff(x) > 0) and np.all(g >= 1.0)
    idle = derived.line[0].n2c1
    assert np.interp(idle, x, g) > 2.0
    rising = [q.n2c1 for a, q in itertools.pairwise(derived.line) if q.ru_pph_psi > a.ru_pph_psi]
    assert rising and all(np.interp(v, x, g) == 1.0 for v in rising[1:])
    _h, (_x2, g2) = governor_gain_schedule(np.linspace(0.6, 1.0, 9), np.linspace(10.0, 30.0, 9), 1.5, 2.5)
    assert np.all(g2 == 1.0)


def test_config_from_reproduces_the_committed_configuration(derived):
    """``harmonise.config_from`` builds the configuration the committed CSVs and M08.yaml give (sweeps and
    negative controls use it without writing files): every derived table equal to the CSV resolution."""
    from phalanx.fadec.harmonise import config_from

    cfg = FadecConfig.build(load_fadec_params())
    got = config_from(derived, cfg)
    names = ("ru_x", "ru_y", "ruff_x", "ruff_y", "n2c_pla_y", "fvg_y", "cvg_x", "govk_x", "govk_y")
    for name in names:
        a, b = getattr(got.tables, name), getattr(cfg.tables, name)
        tol = 2e-6 * max(1.0, float(np.abs(b).max()))
        assert a.shape == b.shape and np.allclose(a, b, rtol=2e-6, atol=tol), name
    assert np.allclose(got.p, cfg.p, rtol=2e-6, atol=1e-12)
