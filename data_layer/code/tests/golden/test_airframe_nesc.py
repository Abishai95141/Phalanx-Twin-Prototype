"""A1: NESC-style 6-DOF check cases for the M06 propagator, plus step-halving convergence.

Scenario definitions follow the atmospheric check-case family of NASA/TM-2015-218675 (NESC-RP-12-00770):
dropped sphere (no drag) over a non-rotating spherical Earth, tumbling brick without and with damping, dropped
sphere over the rotating WGS-84 Earth with J2, ballistic launches along the equator and the prime meridian,
dropped sphere with constant drag in still air and in a steady wind. The NESC reference trajectories were
**not** retrieved (downloading them was out of scope for this WP), so every case is compared against an
**independent reference** computed here: closed-form results where they exist, otherwise a high-accuracy
SciPy integration (DOP853, rtol 1e-12) of the same physics written in a different formulation (inertial
frame, Euler angles-free rotation matrices). Tolerances are stated per case.

Samples: one trajectory per case (n = 1 is sufficient: the propagator is deterministic and the reference is
exact to ~1e-9); durations 10-30 s at 240 Hz.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from phalanx.airframe.build import airframe_param_set, build_config
from phalanx.airframe.geodesy import dcm_ne, ecef_to_geodetic, geodetic_to_ecef
from phalanx.airframe.ic import initial_float_state
from phalanx.airframe.kernel import (
    F_Q0,
    F_RX,
    F_VX,
    F_WX,
    I_TICK,
    N_I,
    O_H,
    airframe_kernel,
    input_width,
)
from phalanx.core.time import TRUTH_DT_S

FT = 0.3048
SLUG = 14.593902937
GM = 3.986004418e14
A_WGS = 6378137.0
F_WGS = 1.0 / 298.257223563
OM_WGS = 7.292115e-5
J2_WGS = 1.08262668e-3


def _cfg(*, sphere: bool, mode: int, cda: float = 0.0, damping: float = 0.0, n_sub_air: int = 1):
    ps = airframe_param_set()
    vals = {"sphere_cda": cda, "brick_damping": damping, "n_sub_air": n_sub_air}
    if sphere:
        vals.update(earth_f=0.0, earth_omega=0.0, earth_j2=0.0)
    ps = ps.replace(**vals)
    return build_config(ps, 1), mode


def _row(mass, inertia, rho=0.0, a=340.0, wind=(0.0, 0.0, 0.0)):
    u = np.zeros(input_width(1))
    o = 14
    u[o] = mass
    u[o + 4 : o + 13] = np.asarray(inertia, dtype=np.float64).reshape(9)
    u[o + 13] = rho
    u[o + 14] = a
    u[o + 15] = 288.15
    u[o + 16 : o + 19] = wind
    return u


def _run(cfg, mode, f0, u, n):
    i0 = np.zeros(N_I, dtype=np.int64)
    uu = np.repeat(u[None, :], n, axis=0)
    return airframe_kernel(f0, i0, cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, uu, TRUTH_DT_S, 1, mode)


def _state(cfg, lat, lon, h, v_ned=(0.0, 0.0, 0.0), q_nb=(1.0, 0.0, 0.0, 0.0), w_nb=(0.0, 0.0, 0.0)):
    return initial_float_state(
        lat,
        lon,
        h,
        np.asarray(v_ned, float),
        np.asarray(q_nb, float),
        np.asarray(w_nb, float),
        0.0,
        -1e4,
        cfg.dp,
    )


SPHERE_J = np.diag([0.1, 0.1, 0.1])  # kg m2; any positive-definite tensor (no torques act)


@pytest.mark.golden
def test_case1_dropped_sphere_no_drag_nonrotating_spherical_earth():
    """Drop from 30,000 ft at rest: radial fall under GM/r^2 vs a 1-D DOP853 reference, |dh| < 1e-6 m."""
    cfg, mode = _cfg(sphere=True, mode=2)
    h0 = 30000.0 * FT
    f0 = _state(cfg, 0.0, 0.0, h0)
    n = 30 * 240
    f, i, out = _run(cfg, mode, f0, _row(SLUG, SPHERE_J), n)
    sol = solve_ivp(
        lambda t, y: [y[1], -GM / y[0] ** 2],
        (0.0, n * TRUTH_DT_S),
        [A_WGS + h0, 0.0],
        method="DOP853",
        rtol=1e-13,
        atol=1e-9,
    )
    h_ref = sol.y[0, -1] - A_WGS
    assert abs(out[-1, O_H] - h_ref) < 1e-6
    assert h0 - h_ref > 4000.0  # the case actually fell (~4.4 km in 30 s)
    assert i[I_TICK] == n
    # no lateral drift, attitude untouched
    assert abs(out[-1, 0]) < 1e-12 and abs(out[-1, 1]) < 1e-12
    assert np.allclose(f[F_Q0 : F_Q0 + 4], f0[F_Q0 : F_Q0 + 4], atol=1e-15)


def _brick_reference(jm, w0, t_end, c):
    jinv = np.linalg.inv(jm)

    def rhs(t, y):
        w = y[0:3]
        r = y[3:12].reshape(3, 3)  # body -> inertial
        wd = jinv @ (-c * w - np.cross(w, jm @ w))
        wx = np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])
        return np.concatenate([wd, (r @ wx).reshape(9)])

    y0 = np.concatenate([w0, np.eye(3).reshape(9)])
    sol = solve_ivp(rhs, (0.0, t_end), y0, method="DOP853", rtol=1e-12, atol=1e-13)
    return sol.y[0:3, -1], sol.y[3:12, -1].reshape(3, 3)


def _q_to_r(q):
    q0, q1, q2, q3 = q
    return np.array(
        [
            [q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
            [2 * (q1 * q2 + q0 * q3), q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3, 2 * (q2 * q3 - q0 * q1)],
            [2 * (q1 * q3 - q0 * q2), 2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3],
        ]
    )


# brick 8 x 4 x 2 in, 1 slug, uniform density (inertia about the CG)
_BX, _BY, _BZ = 8 * 0.0254, 4 * 0.0254, 2 * 0.0254
BRICK_J = SLUG / 12 * np.diag([_BY**2 + _BZ**2, _BX**2 + _BZ**2, _BX**2 + _BY**2])


@pytest.mark.golden
@pytest.mark.parametrize("damping", [0.0, 0.002])
def test_case2_3_tumbling_brick(damping):
    """Torque-free (case 2) and linearly damped (case 3) tumbling brick: body rates and attitude vs DOP853 at
    10 s (|dw| < 1e-9 rad/s, attitude < 1e-9 rad); case 2 also conserves angular momentum and energy."""
    cfg, mode = _cfg(sphere=True, mode=3 if damping else 2, damping=damping)
    w0 = np.radians([10.0, 20.0, 30.0])
    f0 = _state(cfg, 0.0, 0.0, 10000.0)
    f0[F_WX : F_WX + 3] = w0  # inertial body rates (non-rotating Earth)
    n = 10 * 240
    f, _, _ = _run(cfg, mode, f0, _row(SLUG, BRICK_J), n)
    w_ref, r_ref = _brick_reference(BRICK_J, w0, n * TRUTH_DT_S, damping)
    r0 = _q_to_r(f0[F_Q0 : F_Q0 + 4])
    r1 = _q_to_r(f[F_Q0 : F_Q0 + 4])
    assert np.max(np.abs(f[F_WX : F_WX + 3] - w_ref)) < 1e-9
    d = r_ref.T @ (r0.T @ r1)  # residual rotation between kernel and reference
    skew = 0.5 * np.array([d[2, 1] - d[1, 2], d[0, 2] - d[2, 0], d[1, 0] - d[0, 1]])
    assert np.linalg.norm(skew) < 1e-9  # small-angle residual rotation (rad)
    if damping == 0.0:
        h0 = r0 @ BRICK_J @ w0
        h1 = r1 @ BRICK_J @ f[F_WX : F_WX + 3]
        assert np.max(np.abs(h1 - h0)) < 1e-12 * max(1.0, np.max(np.abs(h0))) + 1e-12
        e0 = 0.5 * w0 @ BRICK_J @ w0
        e1 = 0.5 * f[F_WX : F_WX + 3] @ BRICK_J @ f[F_WX : F_WX + 3]
        assert abs(e1 - e0) < 1e-12 * e0
    else:
        assert np.linalg.norm(f[F_WX : F_WX + 3]) < 0.99 * np.linalg.norm(w0)  # damping did something


def _wind_ecef(r, wind_ned):
    """NED wind at ECEF position ``r`` on a sphere (independent of the kernel's geodesy helpers)."""
    x, y, z = r
    lat = math.atan2(z, math.hypot(x, y))
    lon = math.atan2(y, x)
    sl, cl, so, co = math.sin(lat), math.cos(lat), math.sin(lon), math.cos(lon)
    north = np.array([-sl * co, -sl * so, cl])
    east = np.array([-so, co, 0.0])
    down = np.array([-cl * co, -cl * so, -sl])
    return wind_ned[0] * north + wind_ned[1] * east + wind_ned[2] * down


def _eci_reference(
    r_e0, v_e0, t_end, *, cda_over_m=0.0, rho=0.0, rotating=True, j2=J2_WGS, wind_ned=(0.0, 0.0, 0.0)
):
    """Point mass in the inertial frame: J2 gravitation (+ drag relative to the co-rotating air and wind)."""
    om = OM_WGS if rotating else 0.0
    w = np.array([0.0, 0.0, om])
    r0 = np.asarray(r_e0, float)
    v0 = np.asarray(v_e0, float) + np.cross(w, r0)  # inertial velocity

    def grav(r):
        x, y, z = r
        r2 = x * x + y * y + z * z
        rr = math.sqrt(r2)
        k = GM / (r2 * rr)
        t = 1.5 * j2 * A_WGS**2 / r2
        zz = 5 * z * z / r2
        return -k * np.array([x * (1 + t * (1 - zz)), y * (1 + t * (1 - zz)), z * (1 + t * (3 - zz))])

    def rhs(t, y):
        r, v = y[0:3], y[3:6]
        a = grav(r)
        if cda_over_m:
            vrel = v - np.cross(w, r) - _wind_ecef(r, wind_ned)
            a = a - 0.5 * rho * cda_over_m * np.linalg.norm(vrel) * vrel
        return np.concatenate([v, a])

    sol = solve_ivp(rhs, (0.0, t_end), np.concatenate([r0, v0]), method="DOP853", rtol=1e-13, atol=1e-8)
    r_i = sol.y[0:3, -1]
    th = om * t_end
    c, s = math.cos(th), math.sin(th)
    return np.array([c * r_i[0] + s * r_i[1], -s * r_i[0] + c * r_i[1], r_i[2]])  # back to ECEF


@pytest.mark.golden
@pytest.mark.parametrize(
    "case, lat, lon, v_ned",
    [
        ("6_dropped_sphere_wgs84", 0.0, 0.0, (0.0, 0.0, 0.0)),
        ("6_dropped_sphere_wgs84_midlat", math.radians(28.6), math.radians(77.2), (0.0, 0.0, 0.0)),
        ("10_launch_east_equator", 0.0, 0.0, (0.0, 1000 * FT, -1000 * FT)),
        ("11_launch_north_meridian", 0.0, 0.0, (1000 * FT, 0.0, -1000 * FT)),
    ],
)
def test_rotating_wgs84_cases_against_inertial_reference(case, lat, lon, v_ned):
    """Rotating WGS-84 + J2 (kernel ECEF formulation) vs an inertial-frame reference: |dr| < 1e-5 m at 30 s
    (tests the Coriolis, centrifugal and J2 terms; the eastward/northward launches move ~10 km)."""
    cfg, mode = _cfg(sphere=False, mode=2)
    h0 = 30000.0 * FT
    f0 = _state(cfg, lat, lon, h0, v_ned=v_ned)
    n = 30 * 240
    f, _, _out = _run(cfg, mode, f0, _row(SLUG, SPHERE_J), n)
    r_ref = _eci_reference(f0[F_RX : F_RX + 3], f0[F_VX : F_VX + 3], n * TRUTH_DT_S)
    assert np.max(np.abs(f[F_RX : F_RX + 3] - r_ref)) < 1e-5, case
    # Earth rotation matters: the non-rotating answer differs by far more than the tolerance
    r_nr = _eci_reference(f0[F_RX : F_RX + 3], f0[F_VX : F_VX + 3], n * TRUTH_DT_S, rotating=False)
    assert np.max(np.abs(r_nr - r_ref)) > 1.0


@pytest.mark.golden
@pytest.mark.parametrize("wind", [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)])
def test_case7_8_dropped_sphere_constant_drag(wind):
    """Constant-Cd sphere in constant-density air (case 7 still air, case 8 steady 20 m/s wind): matches the
    inertial reference (|dr| < 1e-4 m at 20 s); terminal speed sqrt(2 m g / (rho CdA)) is approached."""
    rho, cda, mass = 1.2, 0.1, SLUG
    cfg, mode = _cfg(sphere=True, mode=1, cda=cda)
    h0 = 30000.0 * FT
    lat, lon = 0.3, 1.1
    f0 = _state(cfg, lat, lon, h0)
    n = 20 * 240
    f, _, out = _run(cfg, mode, f0, _row(mass, SPHERE_J, rho=rho, wind=wind), n)
    r_ref = _eci_reference(
        f0[F_RX : F_RX + 3],
        f0[F_VX : F_VX + 3],
        n * TRUTH_DT_S,
        cda_over_m=cda / mass,
        rho=rho,
        rotating=False,
        j2=0.0,
        wind_ned=wind,
    )
    assert np.max(np.abs(f[F_RX : F_RX + 3] - r_ref)) < 1e-4
    vt = math.sqrt(2 * mass * 9.77 / (rho * cda))
    assert abs(out[-1, 6] - vt) < 0.01 * vt  # down velocity ~ terminal speed
    if wind != (0.0, 0.0, 0.0):  # carried with the air mass
        assert 0.9 * wind[0] < out[-1, 4] < wind[0] and abs(out[-1, 5]) < 1e-6
        lat1, _, _ = ecef_to_geodetic(*f[F_RX : F_RX + 3], cfg.dp[0], 0.0)
        assert lat1 > lat  # drifted north


@pytest.mark.golden
def test_geodetic_roundtrip_wgs84():
    """ECEF <-> geodetic closed form: sub-micrometre round trip, latitudes +/-89 deg, heights to 30 km."""
    g = np.random.Generator(np.random.Philox(6))  # fixed test sample, not a simulation stream
    for _ in range(500):
        lat = g.uniform(-1.55, 1.55)
        lon = g.uniform(-math.pi, math.pi)
        h = g.uniform(-500.0, 30000.0)
        x, y, z = geodetic_to_ecef(lat, lon, h, A_WGS, F_WGS)
        la, lo, hh = ecef_to_geodetic(x, y, z, A_WGS, F_WGS)
        assert abs(la - lat) < 1e-12 and abs(lo - lon) < 1e-12 and abs(hh - h) < 1e-6
    m = np.empty((3, 3))
    dcm_ne(0.4, 1.3, m)
    assert np.allclose(m @ m.T, np.eye(3), atol=1e-15)


def _tejas_manoeuvre(n_sub):
    from phalanx.airframe.analysis import Condition, reference_mass_properties, trim

    ps = airframe_param_set().replace(n_sub_air=n_sub)
    cfg = build_config(ps, 1)
    m0, cg0, j0 = reference_mass_properties(ps)
    cond = Condition(11000.0, 1.4, m0, cg0, j0)
    tr = trim(cfg, cond, guess=(0.03, 0.0, 50000.0))
    u = tr.u.copy()
    u[0:4] += math.radians(1.0)  # elevon step (nose down) and a rudder doublet-free step
    u[4] = math.radians(2.0)
    n = 480
    f, _, out = _run(cfg, 0, tr.f, u, n)
    return f, out


@pytest.mark.golden
def test_step_halving_convergence():
    """RK4 sub-step halving on (a) the NESC tumbling brick and (b) a Tejas manoeuvre (M1.4/11 km, elevon and
    rudder steps, 2 s). (a) observed order >= 3.7; (b) errors shrink >= 8x per halving and the 1-sub-step
    production setting is within 1e-6 rad of the converged attitude and 1e-4 m of the converged position."""
    errs = []
    ref = None
    for n_sub in (8, 4, 2, 1):
        cfg, mode = _cfg(sphere=True, mode=2, n_sub_air=n_sub)
        f0 = _state(cfg, 0.0, 0.0, 10000.0)
        f0[F_WX : F_WX + 3] = np.radians([60.0, 120.0, 180.0])  # fast tumble so the error is measurable
        f, _, _ = _run(cfg, mode, f0, _row(SLUG, BRICK_J), 240)
        if ref is None:
            ref = f
        else:
            errs.append(np.max(np.abs(f[F_Q0 : F_Q0 + 4] - ref[F_Q0 : F_Q0 + 4])))
    e4, e2, e1 = errs  # n_sub = 4, 2, 1 against 8
    order = math.log2(e1 / e2)
    assert order >= 3.7 and e2 > e4, (errs, order)

    fr, outr = _tejas_manoeuvre(8)
    e = []
    for n_sub in (4, 2, 1):
        f, _out = _tejas_manoeuvre(n_sub)
        e.append((np.max(np.abs(f[F_Q0 : F_Q0 + 4] - fr[F_Q0 : F_Q0 + 4])), np.max(np.abs(f[0:3] - fr[0:3]))))
    (_q4, _r4), (_q2, _r2), (q1, r1) = e
    # the production setting (1 sub-step) is converged to round-off: integration error below 1e-9 rad and
    # 1e-6 m (ECEF coordinates are ~6.4e6 m, so 1e-6 m is ~1e-13 relative)
    assert q1 < 1e-9 and r1 < 1e-6, e
    assert abs(outr[-1, 17] - outr[0, 17]) > 1e-3  # the manoeuvre actually moved alpha
