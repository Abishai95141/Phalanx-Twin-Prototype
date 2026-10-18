"""M06 aero build-up properties (A-W1.2-3..9): symmetry, positive drag, ground-effect PROXY, hinge moments.

Deterministic grids (sizes stated per test); the tables are the delivered Tejas configuration.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.airframe.aero import S_AB_L, S_LI, S_LO, S_RI, S_RO, S_RUD, aero_coeffs, hinge_moments
from phalanx.airframe.build import airframe_param_set, build_config

CFG = build_config(airframe_param_set(), 1)
DEG = math.pi / 180.0
CX, CY, CZ, CROLL, CM, CN, CL, CD = range(8)


def _c(alpha, beta=0.0, mach=0.4, d=None, hob=1e3, rates=(0.0, 0.0, 0.0), gear=0.0):
    out = np.zeros(9)
    d = np.zeros(13) if d is None else d
    aero_coeffs(alpha, beta, mach, *rates, d, gear, hob, 3e7, CFG.ap, CFG.tab, out)
    return out


@pytest.mark.unit
def test_lateral_symmetry():
    """With symmetric controls: beta = 0 gives no side force, roll or yaw; beta -> -beta and mirrored controls
    flip CY, Cl, Cn and keep CL, CD, Cm. Grid alpha -10..60 deg x Mach 0.2/0.9/1.6 (n = 3 x 15)."""
    d = np.zeros(13)
    d[S_LO] = d[S_LI] = d[S_RI] = d[S_RO] = -3 * DEG
    d[S_AB_L] = d[S_AB_L + 1] = 20 * DEG
    dm = d.copy()  # mirrored roll/yaw controls
    d2 = d.copy()
    d2[S_LO], d2[S_LI], d2[S_RI], d2[S_RO], d2[S_RUD] = 2 * DEG, 1 * DEG, -1 * DEG, -2 * DEG, 5 * DEG
    dm[S_LO], dm[S_LI], dm[S_RI], dm[S_RO], dm[S_RUD] = -2 * DEG, -1 * DEG, 1 * DEG, 2 * DEG, -5 * DEG
    for mach in (0.2, 0.9, 1.6):
        for a in np.linspace(-10, 60, 15) * DEG:
            c0 = _c(a, 0.0, mach, d)
            assert abs(c0[CY]) < 1e-15 and abs(c0[CROLL]) < 1e-15 and abs(c0[CN]) < 1e-15
            cp = _c(a, 4 * DEG, mach, d2, rates=(0.1, 0.0, 0.05))
            cm = _c(a, -4 * DEG, mach, dm, rates=(-0.1, 0.0, -0.05))
            for k in (CY, CROLL, CN):
                assert cp[k] == pytest.approx(-cm[k], abs=1e-12)
            for k in (CL, CD, CM):
                assert cp[k] == pytest.approx(cm[k], abs=1e-12)


@pytest.mark.unit
def test_drag_positive_everywhere():
    """CD > 0 over alpha -20..90 deg x Mach 0.05..2.4 x controls at their limits (n = 23 x 8 x 3)."""
    for mach in np.linspace(0.05, 2.4, 8):
        for a in np.linspace(-20, 90, 23) * DEG:
            for de in (-25 * DEG, 0.0, 25 * DEG):
                d = np.zeros(13)
                d[0:4] = de
                assert _c(a, 0.0, mach, d)[CD] > 0.0


@pytest.mark.unit
def test_ground_effect_only_reduces_induced_drag():
    """PROXY exposure (A-W1.2-8): the ground factor (McCormick) only scales induced drag. Lift and pitching
    moment are unchanged in ground effect (a real delta gains lift and a nose-down increment near the ground,
    which this model cannot produce); the drag reduction scales as (1 - phi(h/b)), so the ratio of reductions
    at two heights is (1 - phi1) / (1 - phi2) independent of K and CL. n = 3 heights x 2 alphas (below the
    suction-loss blend) + 1 alpha in it (monotone check only)."""

    def phi(hob):
        x = 16.0 * hob
        return x * x / (1.0 + x * x)

    for a in (4 * DEG, 10 * DEG, 14 * DEG):
        free = _c(a, mach=0.2)
        red = {}
        for hob in (0.05, 0.1, 0.3):
            ge = _c(a, mach=0.2, hob=hob)
            assert ge[CL] == free[CL] and ge[CM] == free[CM] and ge[CY] == free[CY]
            assert ge[CD] < free[CD]
            red[hob] = free[CD] - ge[CD]
        assert red[0.05] > red[0.1] > red[0.3]
        if a < 12 * DEG:
            assert red[0.05] / red[0.3] == pytest.approx(
                (1 - phi(0.05)) / (1 - phi(0.3)), rel=1e-6
            )  # cancellation


@pytest.mark.unit
def test_hinge_moments_linear_and_complex_step_safe():
    """H = (ch0 + ch_alpha alpha + ch_beta beta + ch_delta delta) qbar S c, linear in each argument; evaluates
    on complex inputs (the actuator complex-step Jacobian relies on it)."""
    ht = CFG.htab
    d = np.linspace(-0.2, 0.2, 13)
    out = np.zeros(13)
    hinge_moments(0.1, 0.02, 2e4, d, ht, out)
    ref = (ht[:, 0] + ht[:, 1] * 0.1 + ht[:, 2] * 0.02 + ht[:, 3] * d) * 2e4 * ht[:, 4] * ht[:, 5]
    assert np.allclose(out, ref, rtol=1e-14, atol=0.0)
    oc = np.zeros(13, dtype=np.complex128)
    hinge_moments.py_func(0.1 + 1e-20j, 0.02, 2e4, d.astype(np.complex128), ht, oc)
    assert np.allclose(oc.imag / 1e-20, ht[:, 1] * 2e4 * ht[:, 4] * ht[:, 5], rtol=1e-12)
