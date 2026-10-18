"""M07 thermodynamics: NASA-9 humid air / C12H23 products (``phalanx.engine.thermo``).

Reference values: dry air at 300 K, cp = 1005 J/kg/K and gamma = 1.400 (NIST/JANAF tabulations, +-0.3 %),
R = 287.05 J/kg/K (US Standard Atmosphere 1976 composition). Samples: deterministic grids plus hypothesis
property cases (max_examples stated per test).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.engine import thermo as th
from phalanx.engine._mapgen import compressor_rows, janaf_rows, turbine_rows
from phalanx.engine.design import build_tables, load_engine_params


@pytest.fixture(scope="module")
def B():
    return build_tables(load_engine_params()).thermo


@pytest.mark.unit
def test_dry_air_reference_values(B):
    _, cp = th.h_cp(300.0, 0.0, 0.0, B)
    assert abs(cp - 1005.0) / 1005.0 < 3e-3
    assert abs(th.gamma_of(300.0, 0.0, 0.0, B) - 1.400) < 2e-3
    assert abs(th.gas_r(0.0, 0.0, B) - 287.05) < 0.05
    h, _ = th.h_cp(th.T_REF_SENSIBLE, 0.0, 0.0, B)
    assert abs(h) < 1e-6  # sensible-enthalpy datum
    # water vapour: R and cp higher than dry air (humid air is "lighter" and has more heat capacity)
    assert th.gas_r(0.0, 0.02, B) > th.gas_r(0.0, 0.0, B)
    assert th.h_cp(400.0, 0.0, 0.02, B)[1] > th.h_cp(400.0, 0.0, 0.0, B)[1]
    # combustion products: cp rises with fuel-air ratio at combustor temperatures
    assert th.h_cp(1600.0, 0.03, 0.0, B)[1] > th.h_cp(1600.0, 0.0, 0.0, B)[1]


@pytest.mark.unit
def test_basis_mass_balance():
    """The burnt-fuel delta is exactly 1 kg per kg of fuel (C12H23 + 17.75 O2 -> 12 CO2 + 11.5 H2O)."""
    ps = load_engine_params()
    cols = ("species_id", "range_id", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "b1", "b2", "molar_mass")
    table = {c: np.asarray(ps.value(f"thermo_{c}"), float) for c in cols}
    table["molar_mass"] = table["molar_mass"] * 1e3
    _a, mm = th.species_table_to_coeffs(table)
    m_fuel = th.fuel_molar_mass(mm)
    co2 = 12 * mm[3] / m_fuel
    h2o = 11.5 * mm[4] / m_fuel
    o2 = 17.75 * mm[1] / m_fuel
    assert abs(co2 + h2o - o2 - 1.0) < 1e-12
    assert abs(m_fuel - 0.1673110) < 1e-6  # kg/mol, 12 C + 23 H


@pytest.mark.unit
def test_range_boundary_continuity(B):
    """NASA-9 ranges join at 1000 K: h, phi and cp continuous to < 1e-6 relative across the split."""
    for f, w in ((0.0, 0.0), (0.03, 0.01), (0.06, 0.02)):
        lo = th.h_cp(1000.0 - 1e-9, f, w, B)
        hi = th.h_cp(1000.0, f, w, B)
        assert abs(lo[0] - hi[0]) < 1e-6 * abs(hi[0]) + 1e-3
        assert abs(lo[1] - hi[1]) < 1e-6 * hi[1]
        plo, _ = th.phi_cp(1000.0 - 1e-9, f, w, B)
        phi, _ = th.phi_cp(1000.0, f, w, B)
        assert abs(plo - phi) < 1e-6 * abs(phi)


@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(T=st.floats(210.0, 2400.0), f=st.floats(0.0, 0.068), w=st.floats(0.0, 0.03), g=st.floats(0.85, 1.15))
def test_temperature_inversions_converge(B, T, f, w, g):
    """With NEWTON_T = 2 (A-W1.3a-6 performance default) t_from_h / t_from_phi recover T from guesses within
    +-15 % to 1e-6 / 1e-4 relative, and from guesses within +-5 % (what the kernel passes: isentropic
    estimates, previous-state and mixed-stream temperatures) to 1e-8 / 1e-6. Measured kernel-level effect of
    NEWTON_T 2 vs 4: 2.1e-8 relative on the outputs of the 8 s step-halving scenario."""
    assert th.NEWTON_T == 2
    h, _ = th.h_cp(T, f, w, B)
    phi, _ = th.phi_cp(T, f, w, B)
    assert abs(th.t_from_h(h, f, w, B, T * g) - T) < 1e-6 * T
    assert abs(th.t_from_phi(phi, f, w, B, T * g) - T) < 1e-4 * T
    g5 = 1.0 + (g - 1.0) / 3.0
    assert abs(th.t_from_h(h, f, w, B, T * g5) - T) < 1e-8 * T
    assert abs(th.t_from_phi(phi, f, w, B, T * g5) - T) < 1e-6 * T


@pytest.mark.unit
@pytest.mark.parametrize("pr", [1.2, 2.0, 4.35, 6.4, 28.0])
def test_compress_expand_match_converged_inversions(B, pr):
    """compress / expand with NEWTON_T = 2 agree with fully converged Newton inversions (50 iterations,
    written here) to 2e-6 relative over 220-800 K inlets (compress) and 900-1,900 K (expand)."""

    def solve(fun, target, T, deriv_over_T):
        for _ in range(50):
            val, cp = fun(T, 0.0, 0.0, B)
            T = T - (val - target) * (T / cp if deriv_over_T else 1.0 / cp)
        return T

    R = th.gas_r(0.0, 0.0, B)
    for T1 in (220.0, 288.15, 400.0, 600.0, 800.0):
        p1, _ = th.phi_cp(T1, 0.0, 0.0, B)
        h1, _ = th.h_cp(T1, 0.0, 0.0, B)
        t2s = solve(th.phi_cp, p1 + R * np.log(pr), T1 * pr**0.28, True)
        h2s, _ = th.h_cp(t2s, 0.0, 0.0, B)
        ref = solve(th.h_cp, h1 + (h2s - h1) / 0.85, t2s, False)
        assert abs(th.compress(T1, pr, 0.85, 0.0, 0.0, B)[0] / ref - 1.0) < 2e-6
    for T1 in (900.0, 1300.0, 1900.0):
        p1, _ = th.phi_cp(T1, 0.0, 0.0, B)
        h1, _ = th.h_cp(T1, 0.0, 0.0, B)
        t2s = solve(th.phi_cp, p1 - R * np.log(pr), T1 * pr**-0.25, True)
        h2s, _ = th.h_cp(t2s, 0.0, 0.0, B)
        ref = solve(th.h_cp, h1 - 0.9 * (h1 - h2s), t2s, False)
        assert abs(th.expand(T1, pr, 0.9, 0.0, 0.0, B)[0] / ref - 1.0) < 2e-6


@pytest.mark.property
@settings(max_examples=100, deadline=None)
@given(T=st.floats(220.0, 2300.0), f=st.floats(0.0, 0.06), w=st.floats(0.0, 0.03))
def test_derivatives_are_consistent(B, T, f, w):
    """dh/dT = cp and dphi/dT = cp/T (central differences, 1e-6 relative)."""
    e = 1e-3
    hp, _ = th.h_cp(T + e, f, w, B)
    hm, _ = th.h_cp(T - e, f, w, B)
    _, cp = th.h_cp(T, f, w, B)
    if abs(T - 1000.0) > 2 * e:
        assert abs((hp - hm) / (2 * e) - cp) < 1e-6 * cp
        pp, _ = th.phi_cp(T + e, f, w, B)
        pm, _ = th.phi_cp(T - e, f, w, B)
        assert abs((pp - pm) / (2 * e) - cp / T) < 1e-6 * cp / T


@pytest.mark.unit
def test_isentropic_compress_expand_round_trip(B):
    """Ideal compression then ideal expansion over the same PR returns the inlet temperature; real efficiency
    raises the compressor exit temperature and lowers the turbine work (1e-7 relative: NEWTON_T = 2)."""
    for T1, pr in ((288.15, 4.35), (463.0, 6.47)):
        T2, dh = th.compress(T1, pr, 1.0, 0.0, 0.0, B)
        T3, dh2 = th.expand(T2, pr, 1.0, 0.0, 0.0, B)
        assert abs(T3 - T1) < 1e-7 * T1 and abs(dh - dh2) < 1e-6 * dh
        T2r, dhr = th.compress(T1, pr, 0.85, 0.0, 0.0, B)
        assert T2r > T2 and abs(dhr - dh / 0.85) < 1e-6 * dhr
    _, dh_ideal = th.expand(1700.0, 3.0, 1.0, 0.03, 0.0, B)
    _, dh_real = th.expand(1700.0, 3.0, 0.9, 0.03, 0.0, B)
    assert abs(dh_real - 0.9 * dh_ideal) < 1e-9 * dh_ideal


@pytest.mark.unit
def test_complex_step_through_inversion(B):
    """d T / d h of the Newton inversion equals 1/cp (complex step, h = 1e-30) from a kernel-like guess (0.7 %
    off; with NEWTON_T = 2 the derivative is that of the two-step map, converged to 1e-9 here)."""
    T, f, w = 1350.0, 0.025, 0.01
    h, cp = th.h_cp(T, f, w, B)
    Tc = th.t_from_h(h + 1e-30j, f + 0j, w + 0j, B, 1340.0 + 0j)
    assert abs(Tc.imag / 1e-30 - 1.0 / cp) < 1e-12 / cp * 1e3
    assert abs(Tc.real - T) < 1e-8


@pytest.mark.unit
def test_mapgen_parses_without_executing():
    """The pyCycle converter reads literals with ast (no import/exec): a crafted file with a side-effect call
    is parsed for its literals only."""
    text = (
        "import os\nos.system('echo should-not-run')\nM = MapData()\n"
        "M.NcMap = np.array([0.5, 1.0])\nM.RlineMap = np.array([1.0, 2.0])\n"
        "M.WcMap = np.array([[[1.0, 2.0], [3.0, 4.0]]])\nM.PRmap = np.array([[[1.5, 1.2], [2.0, 1.5]]])\n"
        "M.effMap = np.array([[[0.8, 0.81], [0.82, 0.83]]])\n"
    )
    ttext = (
        "import os\nos.system('echo should-not-run')\n"
        "T = MapData()\nT.NpMap = np.array([50.0, 100.0])\nT.PRmap = np.array([2.0, 3.0])\n"
        "T.WpMap = np.array([[[1.0, 1.0], [1.0, 1.0]]])\nT.effMap = np.array([[[0.9, 0.9], [0.91, 0.91]]])\n"
    )
    rows = compressor_rows(text)
    assert rows[0] == [0.5, 1.0, 1.0, 1.5, 0.8] and len(rows) == 4
    trows = turbine_rows(ttext)
    assert len(trows) == 4
    with pytest.raises(ValueError):
        janaf_rows("products = None\n")
