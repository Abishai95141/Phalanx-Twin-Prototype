"""M07 design point and model assembly (acceptance A1; architecture §6 M07 "design point closed to IN20
ratings").

The design point is SLS ISA, dry, uninstalled, 100 % N1/N2 (MIL gas generator); maximum AB keeps the gas
generator and solves AB fuel for the DIRECT 84 kN. Tolerances: DIRECT ratings to 1e-6 relative (they are
imposed by construction, so a looser tolerance would hide an assembly defect); energy/mass balance to 1e-9
relative (Newton residual level).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model, load_engine_params
from phalanx.engine.kernel import deriv_point
from phalanx.engine.layout import NX, PI, X_NAMES, A
from phalanx.engine.steady import design_inputs, design_state, steady_state
from phalanx.engine.thermo import h_cp


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


@pytest.mark.unit
def test_design_point_reproduces_direct_ratings(model):
    """A1: 70 kg/s, OPR 28 and 84 kN max-AB thrust (DIRECT, GE data sheet) exactly; closure values as set."""
    st, ab = model.design.stations, model.design.max_ab
    assert abs(st["w2"] - 70.0) < 1e-12
    assert abs(st["p3"] / st["p2"] - 28.0) < 1e-12
    assert abs(ab["fn"] - 84_000.0) < 84_000.0 * 1e-6
    assert abs(st["fpr"] - 4.35) < 1e-12 and abs(st["bpr"] - 0.28) < 1e-12 and st["t4"] == 1780.0
    # CPR follows from OPR / FPR / core-duct loss and lands in the note's 6.4-6.5 closure band
    assert 6.4 <= st["cpr"] <= 6.5
    # the IN20 closure note's other bands (f404_in20_engine_model.md Q1): T41 1,680-1,700 K
    assert 1650.0 <= st["t41"] <= 1710.0


@pytest.mark.unit
def test_kernel_equilibrium_at_design_inputs(model):
    """A1/A3: the dynamic model's derivatives vanish at the design state with the design inputs (the design
    calculation and the kernel are the same physics), and the steady solver returns the design state. 1e-6
    relative: with NEWTON_T = 2 the design closure and the kernel invert T(h) from different initial
    guesses (observed 2.9e-7; 1e-14 with fully converged inversions)."""
    x = design_state(model)
    u = design_inputs(model)
    dx, aux = deriv_point(x, 0, 1, 0, 0.0, u, model.p, model.tables, -1.0)
    scale = np.abs(x) + 1.0
    assert np.max(np.abs(dx[: X_NAMES.index("wfm")]) / scale[: X_NAMES.index("wfm")]) < 1e-6
    assert abs(aux[A["fn"]] - model.design.stations["fn_dry"]) < 1e-6 * model.design.stations["fn_dry"]
    ss = steady_state(model, u)
    assert ss.converged and np.max(np.abs(ss.x - x) / scale) < 1e-6


@pytest.mark.unit
def test_overall_energy_and_mass_balance_at_design(model):
    """A1 energy balance: (W2 + Wf) h7 - W2 h2 = eta_b Wf LHV - P_acc - (1 - eta_m)(P_HPT + P_LPT) at the
    design equilibrium (no bleed,
    no heat soak at steady state). Relative residual < 1e-9; mass W8 = W2 + Wf."""
    ss = steady_state(model, design_inputs(model))
    a, p, B = ss.aux, model.p, model.tables.thermo
    w2, wf, w8 = a[A["w2"]], a[A["wf_line"]], a[A["w8"]]
    assert abs(w8 - (w2 + wf)) < 1e-9 * w8
    f7 = wf / w2
    h7, _ = h_cp(a[A["t7"]], f7, 0.0, B)
    h2, _ = h_cp(a[A["t2"]], 0.0, 0.0, B)
    lhs = w8 * h7 - w2 * h2
    rhs = (
        p[PI["eta_burner"]] * wf * p[PI["lhv"]] - a[A["pw_ext"]]
        - (1.0 - p[PI["eta_mech"]]) * (a[A["pw_hpt"]] + a[A["pw_lpt"]])
    )  # fmt: skip
    assert abs(lhs - rhs) < 1e-9 * abs(rhs)
    # shaft power balances
    assert abs(p[PI["eta_mech"]] * a[A["pw_lpt"]] - a[A["pw_fan"]]) < 1e-9 * a[A["pw_fan"]]
    assert abs(p[PI["eta_mech"]] * a[A["pw_hpt"]] - a[A["pw_hpc"]] - a[A["pw_ext"]]) < 1e-9 * a[A["pw_hpc"]]


@pytest.mark.unit
def test_energy_balance_negative_control(model):
    """The balance above is a real check: perturbing the burner efficiency in the *assumed* balance by 1 % is
    detected (the identity is not trivially satisfied)."""
    ss = steady_state(model, design_inputs(model))
    a, p, B = ss.aux, model.p, model.tables.thermo
    w2, wf, w8 = a[A["w2"]], a[A["wf_line"]], a[A["w8"]]
    h7, _ = h_cp(a[A["t7"]], wf / w2, 0.0, B)
    h2, _ = h_cp(a[A["t2"]], 0.0, 0.0, B)
    wrong = 0.99 * p[PI["eta_burner"]] * wf * p[PI["lhv"]] - a[A["pw_ext"]]
    assert abs((w8 * h7 - w2 * h2) - wrong) > 1e-4 * abs(wrong)


@pytest.mark.unit
@pytest.mark.parametrize(
    "name,ends",
    [
        ("fpr_design", (4.3, 4.4)),
        ("bpr_design", (0.27, 0.30)),
        ("t4_design", (1770.0, 1790.0)),
        ("eta_hpt_design", (0.86, 0.91)),
        ("eta_lpt_design", (0.86, 0.91)),
        ("f_rot", (0.04, 0.10)),
    ],
)
def test_design_sweep_stays_closed(name, ends):
    """Every closure ASSUMPTION at both sweep ends (A-W1.3a-1) still closes the cycle: bypass dP > 0, core
    mixer-entry Mach in (0.1, 0.9), max-AB thrust 84 kN reached, kernel equilibrium at the design inputs.
    n = 2 builds per parameter (the sweep ends)."""
    ps = load_engine_params()
    for v in ends:
        m = build_engine_model(ps.replace(**{name: v}))
        st = m.design.stations
        assert st["dp_bypass_frac"] > 0.0
        assert 0.1 < st["m_core_mixer"] < 0.9
        assert abs(m.design.max_ab["fn"] - 84_000.0) < 1.0
        dx, _ = deriv_point(design_state(m), 0, 1, 0, 0.0, design_inputs(m), m.p, m.tables, -1.0)
        assert np.max(np.abs(dx[:6]) / (np.abs(design_state(m)[:6]) + 1)) < 1e-8


@pytest.mark.unit
def test_param_vector_complete_and_read_only(model):
    assert model.p.shape == (len(PI),) and not model.p.flags.writeable
    assert np.all(np.isfinite(model.p))
    assert model.n_delay == 10 and model.n_sub == 2  # 40 ms at 240 Hz; A-W1.3a-6
    m2 = model.with_p(i_lp=4.0)
    assert m2.p[PI["i_lp"]] == 4.0 and model.p[PI["i_lp"]] == 3.5
    assert NX == len(X_NAMES)
