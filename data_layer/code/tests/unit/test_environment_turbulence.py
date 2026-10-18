"""M03 turbulence building blocks: MIL-F-8785C scales, Tustin discretisation, rational von Kármán quality,
1-cosine gusts and the log-profile shear (deterministic; no sample)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.environment.turbulence import (
    FT,
    MODEL_DRYDEN,
    MODEL_VON_KARMAN,
    N_TURB_STATE,
    TUSTIN_TABLE,
    gust_1cos,
    psd_analytic,
    psd_filter,
    psd_filter_discrete,
    scales,
    shear_speed,
    turbulence_step,
)

DT = 1.0 / 240.0


@pytest.mark.unit
def test_scales_follow_mil8785c_low_altitude_formulas():
    w20 = 15.0
    for h_ft in (50.0, 300.0, 999.0):
        su, sv, sw, lu, lv, lw = scales.py_func(h_ft * FT, 1.0, w20, 533.4)
        k = 0.177 + 0.000823 * h_ft
        assert sw == pytest.approx(0.1 * w20, rel=1e-12)
        assert su == sv == pytest.approx(0.1 * w20 / k**0.4, rel=1e-12)
        assert lw == pytest.approx(h_ft * FT, rel=1e-12)
        assert lu == lv == pytest.approx(h_ft / k**1.2 * FT, rel=1e-12)
    # high altitude: isotropic, configured sigma and L
    assert scales.py_func(5000.0, 2.2, w20, 762.0) == (2.2, 2.2, 2.2, 762.0, 762.0, 762.0)
    # clamp below 10 ft
    assert scales.py_func(0.0, 1.0, w20, 533.4) == scales.py_func(10 * FT, 1.0, w20, 533.4)


@pytest.mark.unit
def test_scales_continuous_through_the_transition_band():
    for edge_ft in (1000.0, 2000.0):
        lo = np.array(scales.py_func((edge_ft - 1e-6) * FT, 2.2, 15.0, 762.0))
        hi = np.array(scales.py_func((edge_ft + 1e-6) * FT, 2.2, 15.0, 762.0))
        assert np.allclose(lo, hi, rtol=1e-6, atol=1e-6), edge_ft


@pytest.mark.unit
@pytest.mark.parametrize("model", [MODEL_DRYDEN, MODEL_VON_KARMAN])
@pytest.mark.parametrize("axis", [0, 1, 2, 3])
def test_tustin_filter_matches_continuous_below_10_hz(model, axis):
    f = np.logspace(-3, 1, 50)
    cont = 2 * np.pi * psd_filter(model, axis, 2.0, 500.0, 200.0, 2 * np.pi * f)
    disc = psd_filter_discrete(model, axis, 2.0, 500.0, 200.0, f, DT)
    assert np.max(np.abs(disc / cont - 1)) < 0.02


@pytest.mark.unit
def test_dryden_filter_is_exact_and_von_karman_rational_form_is_close():
    """Dryden: |H|^2 equals the Dryden spectrum. von Kármán: the rational forms stay within 5 % of the
    irrational spectra for 0.01 <= L w / V <= 10 (u) and 0.01..10 (v, w); the high-frequency slope then
    departs (-2 vs -5/3), which is the documented limitation of the forming filters."""
    v, length, sigma = 200.0, 762.0, 2.0
    x = np.logspace(-2, 1, 200)
    w = x * v / length
    for axis in (0, 1, 2):
        d = psd_filter(MODEL_DRYDEN, axis, sigma, length, v, w) / psd_analytic(
            MODEL_DRYDEN, axis, sigma, length, v, w
        )
        assert np.max(np.abs(d - 1)) < 1e-12
        r = psd_filter(MODEL_VON_KARMAN, axis, sigma, length, v, w) / psd_analytic(
            MODEL_VON_KARMAN, axis, sigma, length, v, w
        )
        assert np.max(np.abs(r - 1)) < 0.05, (axis, np.max(np.abs(r - 1)))
    # analytic spectra integrate to sigma^2 (normalisation of the 1.339 constant)
    from scipy.integrate import quad

    for model in (MODEL_DRYDEN, MODEL_VON_KARMAN):
        for axis in (0, 1):
            val, _ = quad(
                lambda ww, m=model, a=axis: psd_analytic(m, a, sigma, length, v, ww), 0, np.inf, limit=400
            )
            assert val == pytest.approx(sigma**2, rel=1e-4), (model, axis)


@pytest.mark.unit
def test_one_cosine_gust_shape():
    d, vm = 100.0, 5.0
    assert gust_1cos.py_func(-1.0, d, vm) == 0.0
    assert gust_1cos.py_func(0.0, d, vm) == 0.0
    assert gust_1cos.py_func(d, d, vm) == pytest.approx(vm)
    assert gust_1cos.py_func(2 * d, d, vm) == pytest.approx(0.0, abs=1e-12)
    assert gust_1cos.py_func(2 * d + 1, d, vm) == 0.0
    assert gust_1cos.py_func(0.5 * d, d, vm) == pytest.approx(0.5 * vm * (1 - math.cos(math.pi / 2)))


@pytest.mark.unit
def test_shear_profile():
    """u(h) = W20 ln(h / z0) / ln(20 ft / z0), clamped to 3 ft..1000 ft; smaller z0 (Category C) gives a
    flatter profile for the same W20."""
    w20 = 10.0
    for z0_ft in (0.15, 2.0):
        z0 = z0_ft * FT
        assert shear_speed.py_func(20 * FT, w20, z0) == pytest.approx(w20)
        assert shear_speed.py_func(500 * FT, w20, z0) == pytest.approx(
            w20 * math.log(500 / z0_ft) / math.log(20 / z0_ft)
        )
        assert shear_speed.py_func(0.0, w20, z0) == shear_speed.py_func(3 * FT, w20, z0)
        assert shear_speed.py_func(5000.0, w20, z0) == shear_speed.py_func(1000 * FT, w20, z0)
    flat = shear_speed.py_func(1000 * FT, w20, 0.15 * FT) / w20
    steep = shear_speed.py_func(1000 * FT, w20, 2.0 * FT) / w20
    assert 1 < flat < steep


@pytest.mark.unit
def test_ground_floor_keeps_filters_finite():
    """At standstill the kernel uses max(V, v_min); the gust filters stay finite and bounded."""
    z = np.zeros(N_TURB_STATE)
    out = np.zeros(6)
    scratch = np.zeros((4, 4))
    g = np.random.Generator(np.random.Philox(7))  # fixed test input, not a simulation stream
    for _ in range(2000):
        turbulence_step(
            MODEL_VON_KARMAN,
            z,
            g.standard_normal(4),
            0.0,
            15.0,
            1.0,
            7.7,
            762.0,
            8.2,
            DT,
            TUSTIN_TABLE,
            scratch,
            out,
        )
        assert np.all(np.isfinite(out)) and np.all(np.abs(out) < 50)
