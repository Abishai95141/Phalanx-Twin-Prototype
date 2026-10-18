"""M09 leaf kernels: complex-step-safe helpers, free-surface geometry, and compiled == uncompiled (py_func)
bitwise for every leaf on sampled inputs (A5). The fused kernel is checked in
tests/integration/test_utilities_kernel.py.

Samples: geometry on a 21 x 13 grid of fills and slopes (both slope signs); leaves on 200 seeded draws each.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.utilities import _num, fuel, hydraulics, landing
from phalanx.utilities import layout as L
from phalanx.utilities.params import load_m09_params, param_vector


@pytest.fixture(scope="module")
def p():
    return param_vector(load_m09_params())


def _rng(seed):
    return np.random.Generator(np.random.Philox(seed))  # fixed test inputs, not a simulation stream


@pytest.mark.unit
def test_helpers_pick_by_real_part_and_keep_the_derivative():
    a = 1.0 + 2e-30j
    b = 3.0 + 5e-30j
    assert _num.cmax(a, b) == b and _num.cmin(a, b) == a
    assert _num.clip(5.0 + 1e-30j, 0.0, 1.0) == 1.0
    assert _num.clip(0.5 + 1e-30j, 0.0, 1.0).imag == 1e-30
    assert _num.cabs(-2.0 - 3e-30j) == 2.0 + 3e-30j
    z = _num.pos(-1.5)
    assert z == 0.0 and math.copysign(1.0, z) == 1.0  # +0, never -0
    for f in (_num.cmax, _num.cmin):
        for x, y in ((1.0, 2.0), (-3.0, 0.5), (2.0, 2.0)):
            assert f(x, y) == f.py_func(x, y)


@pytest.mark.unit
def test_transcendentals_are_bitwise_equal_compiled_and_reference():
    """exp/log/pow/sqrt on scalars agree bitwise between Numba and Python on this platform (the kernels rely
    on it; tanh is deliberately avoided, W0.2 carry-forward). n = 2,000 seeded values."""
    t = _rng(1).uniform(200.0, 420.0, 2000)
    got = np.array([hydraulics.visc_ratio(v, 2000.0, 313.15) for v in t])
    ref = np.array([hydraulics.visc_ratio.py_func(v, 2000.0, 313.15) for v in t])
    assert np.array_equal(got, ref)
    x = _rng(2).uniform(1e-3, 50.0, 2000)
    eps = np.array([hydraulics.crossflow_effectiveness(v, 0.4) for v in x])
    eps_ref = np.array([hydraulics.crossflow_effectiveness.py_func(v, 0.4) for v in x])
    assert np.array_equal(eps, eps_ref)


@pytest.mark.unit
def test_section_area_is_the_exact_inverse_of_the_intercept_solver():
    length, height = 1.3, 0.6
    for fill in np.linspace(0.0, 1.0, 21):
        a = fill * length * height
        for s in np.linspace(0.0, 3.0, 13):
            c = fuel.surface_intercept(a, s, length, height)
            assert fuel.section_area(c, s, length, height) == pytest.approx(a, abs=1e-10)  # 1e-10 of 0.78 m^2


@pytest.mark.unit
def test_depth_profile_geometry_level_tilted_and_mirrored():
    cap, length, height, rho = 0.6, 1.2, 0.5, 800.0
    m = 0.5 * cap * rho  # half full
    # level surface: depth = H/2 everywhere
    for frac in (0.1, 0.5, 0.9):
        assert fuel.depth_at(m, rho, cap, length, height, 0.0, frac) == pytest.approx(0.25)
    # nose-up (fuel aft): deeper aft than forward; slope s means depth falls s per metre forward
    aft = fuel.depth_at(m, rho, cap, length, height, 0.3, 0.1)
    fwd = fuel.depth_at(m, rho, cap, length, height, 0.3, 0.9)
    assert aft > 0.25 > fwd and (aft - fwd) == pytest.approx(0.3 * 0.8 * length)
    # mirror symmetry: slope -s at station f equals slope s at station 1 - f
    for frac in (0.05, 0.3, 0.7):
        assert fuel.depth_at(m, rho, cap, length, height, -0.8, frac) == pytest.approx(
            fuel.depth_at(m, rho, cap, length, height, 0.8, 1.0 - frac)
        )
    # very steep: forward station dry, aft station fills to the ceiling at most
    assert fuel.depth_at(m * 0.1, rho, cap, length, height, 3.0, 0.9) == 0.0
    assert fuel.depth_at(m, rho, cap, length, height, 3.0, 0.0) <= height


@pytest.mark.unit
def test_leaf_kernels_bitwise_compiled_vs_reference(p):
    """A5 at leaf level: hydraulic system, fuel step, mass properties and brake/tyre step on seeded states."""
    from phalanx.utilities import ecs, electrical, fire, jfs

    rng = _rng(7)
    ps = load_m09_params()
    for trial in range(40):
        f = np.zeros(L.NF)
        i = np.zeros(L.NI, dtype=np.int64)
        f[L.F_HYD_P : L.F_HYD_P + 2] = rng.uniform(0.0, 3.2e7, 2)
        f[L.F_HYD_X : L.F_HYD_X + 2] = rng.uniform(0, 1, 2)
        f[L.F_HYD_T : L.F_HYD_T + 2] = rng.uniform(240, 380, 2)
        f[L.F_HYD_VRES : L.F_HYD_VRES + 2] = 0.005
        f[L.F_FUEL_M : L.F_FUEL_M + L.N_TANKS] = (
            rng.uniform(0, 1, L.N_TANKS) * np.asarray(ps.value("tank_cap")) * 790.0
        )
        f[L.F_FUEL_T] = rng.uniform(250, 320)
        f[L.F_SLOSH_S] = rng.uniform(-1.5, 1.5)
        f[L.F_BATT_SOC] = rng.uniform(0.1, 1.0)
        f[L.F_BATT_T] = rng.uniform(240, 320)
        f[L.F_BRK_T : L.F_BRK_T + 2] = rng.uniform(250, 900, 2)
        f[L.F_ECS_PCAB] = rng.uniform(5e4, 1.0e5)
        f[L.F_ECS_TPHX] = f[L.F_ECS_TCAB] = f[L.F_ECS_TAV] = f[L.F_BAY_T] = 290.0
        f[L.F_JFS_N] = rng.uniform(0, 1)
        f[L.F_JFS_OILT] = rng.uniform(240, 330)
        i[L.I_JFS_MODE] = trial % 5
        i[L.I_GEN_ON] = trial % 2
        i[L.I_ESS_SRC] = 1 + trial % 3
        args_h = (
            0,
            1700.0 * rng.uniform(0.3, 1.05),
            rng.uniform(0, 3e-3),
            rng.uniform(0, 4),
            285.0,
            280.0,
            7e4,
        )
        hl = (rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0, 0.02), rng.uniform(-0.05, 0.05), 0.3, 0.2)
        outs = []
        for impl in ("compiled", "ref"):
            ff, ii = f.copy(), i.copy()
            call = (lambda fn: fn) if impl == "compiled" else (lambda fn: fn.py_func)
            r1 = call(hydraulics.hyd_system)(ff, p, *args_h, *hl, 1 / 240, 8)
            call(fuel.slosh_step)(ff, p, 6.0, -7.0, 1 / 240)
            call(fuel.fuel_step)(ff, ii, p, 3.0, 285.0, 0.1, 1 / 240)
            mp = np.empty(13)
            call(fuel.mass_properties)(ff, p, mp)
            r2 = call(electrical.electrical_step)(ff, ii, p, 0.6, 1.0, 270.0, True, 8.0, 0.1, 8, 1 / 240)
            r3 = call(jfs.jfs_step)(ff, ii, p, 120.0, 900.0, 900.0, 7e4, 260.0, 270.0, 0.3, 0.0, 0.0, 1 / 240)
            bo = np.empty(1)
            bp = np.empty(2)
            r4 = call(ecs.ecs_step)(
                ff,
                p,
                1,
                np.array([4e5]),
                np.array([600.0]),
                np.array([0.01]),
                7e4,
                280.0,
                0.9,
                150.0,
                0.2,
                0.1,
                3000.0,
                bo,
                1 / 240,
            )
            call(landing.landing_step)(
                ff,
                ii,
                p,
                np.array([2e5, 1e5]),
                np.array([10.0, 50.0]),
                1.0,
                1.0,
                60.0,
                9000.0,
                288.0,
                np.array([0.5, 0.7]),
                np.array([0.2, 0.3]),
                2.5e7,
                bp,
                1 / 240,
            )
            call(fire.fire_step)(ff, ii, p, 650.0, 290.0, 1.0, 100.0, 1 / 240)
            outs.append((ff, ii, np.array(r1), mp, np.array(r2, dtype=np.float64), r3, np.array(r4), bo, bp))
        for a, b in zip(outs[0], outs[1], strict=True):
            assert np.array_equal(np.asarray(a), np.asarray(b)), trial


@pytest.mark.unit
def test_brake_and_tyre_increment_laws_are_monotone(p):
    w_cold = landing.brake_wear_rate(p, 1e6, 400.0)
    w_hot = landing.brake_wear_rate(p, 1e6, 1000.0)
    assert w_hot > w_cold > 0.0  # oxidation above brk_t_ox
    assert landing.touchdown_tyre_wear(p, 12000.0, 80.0) > landing.touchdown_tyre_wear(p, 9000.0, 70.0)
    assert landing.heat_capacity(p, 0.9) < landing.heat_capacity(p, 0.5) < landing.heat_capacity(p, 0.0)
