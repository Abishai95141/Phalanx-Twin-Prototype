"""A2: aero validation tests V1-V12 (report §10, notes tejas_airframe_aero_fcs.md Q8) as golden tests.

Honesty notes (also in airframe/README.md):
- V1, V3 (eigenvalues), V5 and the trim points of V2 are **construction checks**: AD-08 fits the longitudinal
  core to exactly these Tejas anchors, so they verify the implementation (signs, units, linearisation, the
  analysis tools), not an independent prediction. V4 (time-to-double map) is a calibration of the Mach
  static-margin shift. Independent checks are V2 at M1.0 (no Mach-dependent calibration beyond the trim
  points' M0.4/M0.6 fit), V6 shape, V7 and V9.
- Thrust-dependent items (V9 performance, V10 lift-off) need the M07 thrust model: they are strict xfails
  until W2.1/W2.3 provide ``available_thrust``.
- Samples: deterministic flight-condition grids stated per test (n = number of conditions); no randomness.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.airframe.aero import aero_coeffs
from phalanx.airframe.analysis import (
    Condition,
    ari_method1,
    isa,
    lateral,
    reference_mass_properties,
    short_period,
    time_to_double,
    trim,
)
from phalanx.airframe.build import airframe_param_set, build_config

PS = airframe_param_set()
CFG = build_config(PS, 1)
M0, CG0, J0 = reference_mass_properties(PS)
DEG = math.pi / 180.0


def _slats(alpha: float, mach: float) -> np.ndarray:
    """The M05 slat schedule (A-W1.2-28) evaluated from the M05 registry (auto slats, as in the sources)."""
    from phalanx.fcs.build import fcs_param_set

    f = fcs_param_set()
    a0, a1 = float(f.value("slat_alpha0")), float(f.value("slat_alpha1"))
    m0, m1 = float(f.value("slat_mach0")), float(f.value("slat_mach1"))
    sg = min(max((alpha - a0) / (a1 - a0), 0.0), 1.0)
    mf = min(max((mach - m0) / (m1 - m0), 0.0), 1.0)
    sigma = sg * (1.0 - mf * mf * (3.0 - 2.0 * mf))
    mx = [float(f.value(k)) for k in ("slat_max_ob", "slat_max_mb", "slat_max_ib")]
    return sigma * np.array([mx[0], mx[1], mx[2], mx[2], mx[1], mx[0]])


def _trim_auto_slats(cond: Condition, guess):
    tr = trim(CFG, cond, guess=guess)
    for _ in range(3):  # fixed point: slats follow the trimmed alpha
        c2 = Condition(**{**cond.__dict__, "slats": _slats(tr.alpha, cond.mach)})
        tr = trim(CFG, c2, guess=(tr.alpha, tr.de, tr.thrust))
    return c2, tr


def _coeffs(alpha, beta=0.0, mach=0.2, d=None, qhat=0.0):
    out = np.zeros(9)
    aero_coeffs(
        alpha,
        beta,
        mach,
        0.0,
        qhat,
        0.0,
        np.zeros(13) if d is None else d,
        0.0,
        1e3,
        3e7,
        CFG.ap,
        CFG.tab,
        out,
    )
    return out


@pytest.mark.golden
def test_v1_lift_curve():
    """V1: clean CL(alpha) at M0.2 within +/-0.03 of every digitised Tejas WT point (-15..30 deg, n = 8);
    CL still increasing at 30 deg (CLmax beyond 30 deg, near 35 deg)."""
    a_bp = np.asarray(PS.value("wt_cl_alpha"))
    cl_wt = np.asarray(PS.value("wt_cl"))
    for a, c in zip(a_bp, cl_wt, strict=True):
        assert abs(_coeffs(a)[6] - c) <= 0.03, (math.degrees(a), _coeffs(a)[6], c)
    assert _coeffs(31 * DEG)[6] > _coeffs(30 * DEG)[6] > _coeffs(29 * DEG)[6]
    cl = [_coeffs(a * DEG)[6] for a in range(30, 46)]
    assert 33 <= 30 + int(np.argmax(cl)) <= 40  # CLmax near 35 deg


@pytest.mark.golden
@pytest.mark.parametrize("mach, target", [(0.4, 12.45), (0.6, 6.59), (1.0, 2.46)])
def test_v2_trim_alpha_8km(mach, target):
    """V2: trimmed alpha at 8 km, clean, gear up, auto slats: within +/-1 deg of the ELS value at the mid mass
    8.75 t, and within +/-1.5 deg over the stated 8.5-9.0 t mass band (source mass not stated; n = 3
    masses)."""
    out = {}
    for m in (8500.0, 8750.0, 9000.0):
        _, tr = _trim_auto_slats(Condition(8000.0, mach, m, CG0, J0), (0.1 if mach < 0.5 else 0.05, 0.0, 2e4))
        out[m] = math.degrees(tr.alpha)
    assert abs(out[8750.0] - target) <= 1.0, out
    assert all(abs(v - target) <= 1.5 for v in out.values()), out


@pytest.mark.golden
def test_v3_short_period_eigenvalues():
    """V3: M0.22 / 300 m / 9,060 kg, gear up, auto slats: unstable root +0.26 (+/-0.1) 1/s, stable root
    -1.16 (+/-0.3) 1/s, M_de -3.74 1/s^2 (+/-20 %) (DSJ 57(4) eq. 2)."""
    cond, tr = _trim_auto_slats(Condition(300.0, 0.22, 9060.0, CG0, J0), (0.27, 0.0, 2e4))
    sp = short_period(CFG, cond, tr)
    lo, hi = sp.eig
    assert abs(hi - 0.26) <= 0.1 and abs(lo - (-1.16)) <= 0.3, sp.eig
    assert abs(sp.m_de - (-3.7391)) <= 0.2 * 3.7391, sp.m_de
    # the published model's other entries, loosely (construction check of the linearisation)
    assert abs(sp.z_alpha - (-0.4784)) < 0.1 and abs(sp.m_q - (-0.4276)) < 0.1


def _t2(mach, h):
    cond = Condition(h, mach, M0, CG0, J0)
    tr = trim(CFG, cond, guess=(0.05, 0.0, 3e4))
    return time_to_double(short_period(CFG, cond, tr))


V4_BOX = [(m, h) for m in (0.5, 0.6, 0.7, 0.8) for h in (3000.0, 5500.0, 8000.0)]


@pytest.mark.golden
def test_v4_time_to_double_map():
    """V4 (NFTC Fig-2 map, 9 t), the map's qualitative features: the least stable (shortest t2) point of the
    M0.5-0.8 x 3/5.5/8 km box lies at M >= 0.7 (the published zone of highest instability is M0.5-0.7,
    'dropping to 200 ms'); weak (t2 > 0.7 s or stable) at M0.3; stable for M >= 1.0. The brief's band
    (t2 0.2-0.3 s) is ``test_v4_time_to_double_in_brief_band``; this test also records its current misses
    (a regression guard, not an acceptance claim). Grid n = 4 x 3 + 3 + 3 conditions."""
    box = {k: _t2(*k) for k in V4_BOX}
    assert min(box, key=box.get)[0] >= 0.7, box
    misses = {k: round(v, 3) for k, v in box.items() if k[0] >= 0.6 and not 0.2 <= v <= 0.3}
    assert misses == {(0.6, 8000.0): 0.301, (0.8, 3000.0): 0.194}, misses
    assert all(_t2(0.3, h) > 0.7 for h in (3000.0, 5500.0, 8000.0))
    assert all(math.isinf(_t2(m, 8000.0)) for m in (1.0, 1.2, 1.6))


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration (Mach static-margin shift, A-W1.2-5): at the brief's band 0.2-0.3 s two of the "
    "nine M0.6-0.8 points fall out: t2 0.194 s at M0.8/3 km and 0.301 s at M0.6/8 km (box minimum 0.194 s). "
    "The former 0.18-0.32 s band hid them (E1 verifier §2)",
)
def test_v4_time_to_double_in_brief_band():
    """V4 at the W1.2 brief's band (A2: 'time-to-double 0.2-0.3 s'; notes tejas_airframe_aero_fcs.md V4:
    t2 ~0.2-0.3 s): the minimum t2 of the box is >= 0.2 s and every M0.6-0.8 point at 3-8 km is in
    0.2-0.3 s. M0.5 is excluded as before (t2 0.33-0.38 s): a single rigid Cm_alpha cannot hold 0.2-0.3 s
    over a box spanning a 5x dynamic-pressure range. n = 9 points (12 for the minimum)."""
    box = {k: _t2(*k) for k in V4_BOX}
    assert min(box.values()) >= 0.2, box
    assert all(0.2 <= v <= 0.3 for (m, _h), v in box.items() if m >= 0.6), box


@pytest.mark.golden
@pytest.mark.parametrize(
    "alpha_deg, cma, cmq, cmde", [(4.3, -0.014, -1.32, -0.415), (11.9, 0.077, -1.17, -0.39)]
)
def test_v5_cm_derivatives(alpha_deg, cma, cmq, cmde):
    """V5 (JOAST 56(3) simulator derivatives): Cm_alpha within +/-0.03 /rad, Cm_q within +/-0.3, Cm_de within
    +/-0.05 /rad at alpha 4.3 and 11.9 deg (M0.2, controls neutral). Central differences, step 1e-4."""
    a = alpha_deg * DEG
    e = 1e-4
    d_alpha = (_coeffs(a + e)[4] - _coeffs(a - e)[4]) / (2 * e)
    d_q = (_coeffs(a, qhat=e)[4] - _coeffs(a, qhat=-e)[4]) / (2 * e)
    dp = np.zeros(13)
    dp[0:4] = e
    d_de = (_coeffs(a, d=dp)[4] - _coeffs(a, d=-dp)[4]) / (2 * e)
    assert abs(d_alpha - cma) <= 0.03, d_alpha
    assert abs(d_q - cmq) <= 0.3, d_q
    assert abs(d_de - cmde) <= 0.05, d_de


@pytest.mark.golden
def test_v6_directional():
    """V6 (AeSI FTG 2005 Fig-4/Fig-6): Cn_beta +0.04..+0.06 /rad for alpha <= 15 deg, zero crossing at 23-26
    deg,
    negative (cliff) by 27 deg; Cn_dr -0.0012 /deg +/-20 % over alpha -15..30 deg (M0.2-0.5)."""
    e = 1e-4
    alphas = np.arange(-10.0, 30.01, 0.25)
    cnb = []
    for a in alphas:
        cnb.append((_coeffs(a * DEG, beta=e)[5] - _coeffs(a * DEG, beta=-e)[5]) / (2 * e))
    cnb = np.array(cnb)
    low = cnb[alphas <= 15.0]
    assert np.all((low >= 0.04) & (low <= 0.061))
    cross = alphas[np.argmax(cnb < 0.0)]
    assert 23.0 <= cross <= 26.0, cross
    assert cnb[alphas == 27.0][0] < -0.05
    for a in (-15.0, 0.0, 15.0, 30.0):
        d = np.zeros(13)
        d[4] = e
        cn_dr = (_coeffs(a * DEG, mach=0.5, d=d)[5] - _coeffs(a * DEG, mach=0.5, d=-d)[5]) / (2 * e) * DEG
        assert abs(cn_dr - (-0.0012)) <= 0.2 * 0.0012, (a, cn_dr)


@pytest.mark.golden
@pytest.mark.xfail(
    strict=True,
    reason="W2.3 calibration (lateral derivatives not public, A-W1.2-7): ARI at 6 km is -5.51 / -0.873 / "
    "-0.283 at M0.26 / M0.7 / M1.3 vs -3.47 / +0.60 / +0.319: wrong sign at M0.7 and M1.3, and 1.59x the "
    "magnitude at M0.26 (factor-1.5 band)",
)
def test_v7_ari_trend():
    """V7 (DSJ 71(2) Table 2 at 6 km): the coordinated velocity-vector-roll interconnect of the linearised
    airframe has the published sign pattern (Phalanx signs: negative at M0.26, positive at M0.7 and M1.3) with
    magnitudes within a factor 1.5 of 3.47 / 0.60 / 0.319. n = 3 conditions."""
    target = {0.26: -3.47, 0.7: 0.60, 1.3: 0.319}
    for mach, ari_t in target.items():
        cond = Condition(6000.0, mach, M0, CG0, J0)
        tr = trim(CFG, cond, guess=(0.2 if mach < 0.5 else 0.05, 0.0, 2e4))
        ari = ari_method1(lateral(CFG, cond, tr), tr.alpha)
        assert math.copysign(1.0, ari) == math.copysign(1.0, ari_t), (mach, ari)
        assert 1 / 1.5 <= abs(ari) / abs(ari_t) <= 1.5, (mach, ari)


def available_thrust(mach: float, alt: float) -> float:
    """Maximum-afterburner thrust of the M07 model at (Mach, altitude). Provided by W2.1/W2.3 engine
    coupling."""
    raise NotImplementedError("W2.1/W2.3: needs the M07 F404-IN20 thrust model")


def _required_thrust(mach, alt):
    cond = Condition(alt, mach, M0, CG0, J0)
    return trim(CFG, cond, guess=(0.03, 0.0, 5e4)).thrust


@pytest.mark.golden
def test_v9_required_thrust_is_physical():
    """V9 support (not thrust-dependent): drag-required thrust at the two performance anchors is positive and
    below the IN20 maximum rating 84 kN x 1.3 (a generous ram/altitude bound) - recorded for W2.3
    calibration."""
    t_sl = _required_thrust(620 * 0.514444 / isa(0.0)[1], 0.0)
    t_m16 = _required_thrust(1.6, 11500.0)
    assert 0.0 < t_sl < 84e3 * 1.3 and 0.0 < t_m16 < 84e3 * 1.3, (t_sl, t_m16)


@pytest.mark.golden
@pytest.mark.parametrize(
    "mach, alt, lo, hi",
    [(0.6, 5000.0, 0.0135, 0.0185), (1.15, 10000.0, 0.033, 0.042), (1.6, 11000.0, 0.028, 0.035)],
)
def test_drag_buildup_cd0_band(mach, alt, lo, hi):
    """Drag build-up (A-W1.2-8) at zero lift lands in the research-note CD0 bands: ~0.016 below M0.8,
    0.035-0.040 at M1.1-1.2, 0.030-0.033 at M1.6 (tejas_airframe_aero_fcs.md Q4 #32; ASSUMPTION anchors, so a
    construction check of friction x k_f + wave drag, +/- 15 % margins). n = 3 conditions."""
    rho, a, t, _ = isa(alt)
    mu = 1.458e-6 * t**1.5 / (t + 110.4)
    re = rho * mach * a * CFG.ap[2] / mu
    out = np.zeros(9)

    def coeffs(alpha):
        aero_coeffs(alpha, 0.0, mach, 0.0, 0.0, 0.0, np.zeros(13), 0.0, 1e3, re, CFG.ap, CFG.tab, out)
        return out.copy()

    lo_a, hi_a = -0.2, 0.2
    for _ in range(80):  # bisection for CL = 0
        mid = 0.5 * (lo_a + hi_a)
        if coeffs(mid)[6] > 0.0:
            hi_a = mid
        else:
            lo_a = mid
    cd0 = coeffs(0.5 * (lo_a + hi_a))[7]
    assert lo <= cd0 <= hi, cd0


@pytest.mark.golden
@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="W2.3: thrust-dependent (needs M07)")
def test_v9_performance_level_m16_and_620kt():
    """V9: level M1.6 achievable at 11-12 km clean and >= 620 kt at sea level (available >= required
    thrust)."""
    for mach, alt in ((1.6, 11000.0), (1.6, 12000.0), (620 * 0.514444 / isa(0.0)[1], 0.0)):
        assert available_thrust(mach, alt) >= _required_thrust(mach, alt)


@pytest.mark.golden
def test_v10_approach_speed_from_lift():
    """V10 (aero part): at 7.5-8 t, sea level, the lift-equilibrium speeds over the approach AoA band 12-14
    deg
    overlap the 260-285 km/h approach band of the notes and stay below the 340 km/h emergency chute limit
    (n = 2 masses x 3 AoA). Lift-off speed needs thrust (W2.3)."""
    rho = isa(0.0)[0]
    s = float(PS.value("s_ref"))
    for m in (7500.0, 8000.0):
        v = [math.sqrt(2 * m * 9.80665 / (rho * s * _coeffs(a * DEG)[6])) * 3.6 for a in (12.0, 13.0, 14.0)]
        assert min(v) <= 285.0 and max(v) >= 260.0 and max(v) < 340.0, (m, v)


@pytest.mark.golden
def test_v12_departure_tendency():
    """V12: beyond ~26 deg the airframe is directionally unstable (Cn_beta < 0, the Tejas 'cliff'), so with
    the
    limiter off a departure follows; the closed-loop limiter test (fcs) shows the FCS prevents entry."""
    e = 1e-4
    for a in (27.0, 28.0, 30.0):
        cnb = (_coeffs(a * DEG, beta=e)[5] - _coeffs(a * DEG, beta=-e)[5]) / (2 * e)
        assert cnb < 0.0
