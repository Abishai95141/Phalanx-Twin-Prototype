"""Trim, linearisation and reference-atmosphere helpers for M06 (analysis tools, not the truth loop).

They evaluate the **same compiled force model** as the kernel (``airframe_derivative``), so trim points,
short-period eigenvalues and the time-to-double map are properties of the delivered model, not of a separate
analysis model. Used by the V1-V12 golden tests, by the M05 gain design and by initial-condition builders.

The atmosphere here (:func:`isa`) is the USSA-76 / ICAO standard atmosphere to 20 km [TRANSFER: USSA-76].
It exists only for analysis and tests; the truth loop takes its atmosphere from M03 ports.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import fsolve

from .build import AirframeConfig
from .geodesy import euler_to_quat, gravity_ecef, q_to_dcm
from .ic import AirframeIC, initial_float_state
from .kernel import (
    D_A,
    D_G0,
    D_GM,
    D_J2,
    D_OM,
    F_GEAR,
    F_WX,
    N_SURF,
    U_BRAKE,
    U_CHUTE,
    U_HYDP,
    X_FSX,
    X_FSY,
    X_FSZ,
    airframe_derivative,
    input_width,
)

#: default util.hyd_p of an analysis input row: both systems at the nominal 280 bar gauge [DIRECT: M09.yaml
#: hyd_p_nom, Kala JOAST 67(2A) 2015], so the brake torque is not supply-limited unless a test says so (AD-47)
HYD_P_NOMINAL = 2.8e7  # Pa (gauge)
R_AIR = 287.05287  # J/(kg K), USSA-76
GAMMA_AIR = 1.4
G0 = 9.80665
R_EARTH_GEOPOT = 6356766.0  # m, USSA-76


def isa(h: float) -> tuple[float, float, float, float]:
    """USSA-76 standard atmosphere at geometric height ``h`` (m), 0-20 km: (rho, a, T, p)."""
    hg = R_EARTH_GEOPOT * h / (R_EARTH_GEOPOT + h)
    if hg <= 11000.0:
        t = 288.15 - 0.0065 * hg
        p = 101325.0 * (t / 288.15) ** (G0 / (0.0065 * R_AIR))
    else:
        t = 216.65
        p11 = 101325.0 * (216.65 / 288.15) ** (G0 / (0.0065 * R_AIR))
        p = p11 * math.exp(-G0 * (hg - 11000.0) / (R_AIR * t))
    rho = p / (R_AIR * t)
    return rho, math.sqrt(GAMMA_AIR * R_AIR * t), t, p


def reference_mass_properties(ps) -> tuple[float, np.ndarray, np.ndarray]:
    return (
        float(ps.value("ref_mass")),
        np.asarray(ps.value("ref_cg"), dtype=np.float64),
        np.asarray(ps.value("ref_inertia"), dtype=np.float64),
    )


def input_row(
    n_eng: int,
    surf: np.ndarray,
    thrust: float | np.ndarray,
    mass: float,
    cg: np.ndarray,
    inertia: np.ndarray,
    h: float,
    *,
    atmosphere: Callable[[float], tuple[float, float, float, float]] = isa,
    wind_ned=(0.0, 0.0, 0.0),
    gear_cmd: int = 0,
    brake_cmd=(0.0, 0.0),
    chute_state: int = 0,
    hyd_p=(HYD_P_NOMINAL, HYD_P_NOMINAL),
) -> np.ndarray:
    """One kernel input row (layout of ``kernel.input_width``) with the atmosphere at height ``h``. Brakes
    off, chute stowed and both hydraulic systems at their nominal pressure unless given (AD-47)."""
    rho, a, t, _ = atmosphere(h)
    u = np.zeros(input_width(n_eng))
    u[0:N_SURF] = surf
    if np.ndim(thrust) == 0:
        u[N_SURF : N_SURF + n_eng] = float(thrust) / n_eng  # total thrust shared equally
    else:
        u[N_SURF : N_SURF + n_eng] = np.asarray(thrust, dtype=np.float64)
    o = N_SURF + n_eng
    u[o] = mass
    u[o + 1 : o + 4] = cg
    u[o + 4 : o + 13] = np.asarray(inertia, dtype=np.float64).reshape(9)
    u[o + 13], u[o + 14], u[o + 15] = rho, a, t
    u[o + 16 : o + 19] = wind_ned
    u[o + 25] = gear_cmd
    u[o + U_BRAKE : o + U_BRAKE + 2] = brake_cmd
    u[o + U_CHUTE] = chute_state
    u[o + U_HYDP : o + U_HYDP + 2] = hyd_p
    return u


@dataclass(frozen=True)
class Condition:
    """A steady flight condition for trim and linearisation."""

    h: float  # m
    mach: float
    mass: float
    cg: np.ndarray
    inertia: np.ndarray
    gamma: float = 0.0  # flight-path angle, rad
    psi: float = 0.0  # heading, rad
    lat: float = math.radians(13.0)  # Bengaluru-ish latitude, rad
    lon: float = math.radians(77.6)
    gear: float = 0.0
    slats: np.ndarray | None = None  # 6 slat deflections (rad); None = retracted
    airbrake: float = 0.0
    atmosphere: Callable[[float], tuple[float, float, float, float]] = field(default=isa, repr=False)

    @property
    def tas(self) -> float:
        return self.mach * self.atmosphere(self.h)[1]


@dataclass(frozen=True)
class Trim:
    alpha: float  # rad
    de: float  # symmetric elevon (all four), rad
    thrust: float  # N (total)
    theta: float  # rad
    residual: float
    u: np.ndarray  # kernel input row
    f: np.ndarray  # kernel float state


def _surfaces(de: float, da: float, dr: float, cond: Condition, cfg: AirframeConfig) -> np.ndarray:
    s = np.zeros(N_SURF)
    s[0] = de + da  # LO
    s[1] = de + da  # LI
    s[2] = de - da  # RI
    s[3] = de - da  # RO
    s[4] = dr
    if cond.slats is not None:
        s[5:11] = cond.slats
    s[11] = s[12] = cond.airbrake * cfg.ap[34]
    return s


def state_for(
    cfg: AirframeConfig,
    cond: Condition,
    alpha: float,
    beta: float = 0.0,
    phi: float = 0.0,
    pqr=(0.0, 0.0, 0.0),
    theta: float | None = None,
) -> np.ndarray:
    """Kernel float state for a wings-level (or banked) flight condition with the given body angles."""
    v = cond.tas
    th = cond.gamma + alpha if theta is None else theta
    q_nb = euler_to_quat(phi, th, cond.psi)
    ub, vb, wb = (
        v * math.cos(alpha) * math.cos(beta),
        v * math.sin(beta),
        v * math.sin(alpha) * math.cos(beta),
    )
    q0, q1, q2, q3 = q_nb
    cnb = np.array(
        [
            [q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
            [2 * (q1 * q2 + q0 * q3), q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3, 2 * (q2 * q3 - q0 * q1)],
            [2 * (q1 * q3 - q0 * q2), 2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3],
        ]
    )
    v_ned = cnb @ np.array([ub, vb, wb])
    return initial_float_state(
        cond.lat, cond.lon, cond.h, v_ned, q_nb, np.asarray(pqr, dtype=np.float64), cond.gear, -1000.0, cfg.dp
    )


def body_accel(
    cfg: AirframeConfig, f: np.ndarray, u: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(specific force + gravity, body axes; body angular acceleration; aux) for state ``f`` and row ``u``."""
    xd, aux = airframe_derivative(f, cfg.dp, cfg.ap, cfg.tab, cfg.gtab, cfg.ttab, u, cfg.n_eng, 0)
    ceb = np.empty((3, 3))
    q_to_dcm(f[6], f[7], f[8], f[9], ceb)
    g_e = np.array(gravity_ecef(f[0], f[1], f[2], cfg.dp[D_GM], cfg.dp[D_A], cfg.dp[D_J2], cfg.dp[D_OM]))
    acc = np.array([aux[X_FSX], aux[X_FSY], aux[X_FSZ]]) + ceb.T @ g_e
    return acc, xd[F_WX : F_WX + 3], aux


def trim(cfg: AirframeConfig, cond: Condition, guess=(0.08, 0.0, 30000.0)) -> Trim:
    """Steady wings-level trim (alpha, symmetric elevon, thrust): zero body and pitch accelerations.

    Earth-rotation and path-curvature accelerations (< 0.002 g) are not trimmed out.
    """

    def build(x):
        a, de, t = x
        s = _surfaces(de, 0.0, 0.0, cond, cfg)
        u = input_row(
            cfg.n_eng,
            s,
            t,
            cond.mass,
            cond.cg,
            cond.inertia,
            cond.h,
            atmosphere=cond.atmosphere,
            gear_cmd=int(cond.gear > 0.5),
        )
        f = state_for(cfg, cond, a)
        f[F_GEAR] = cond.gear
        return f, u

    def res(x):
        f, u = build(x)
        acc, wdot, _ = body_accel(cfg, f, u)
        return [acc[0] / G0, acc[2] / G0, wdot[1]]

    sol, _info, ier, msg = fsolve(res, np.asarray(guess, dtype=np.float64), full_output=True, xtol=1e-12)
    r = float(np.max(np.abs(res(sol))))
    if ier != 1 or r > 1e-7:
        raise RuntimeError(f"trim failed at {cond}: {msg} (residual {r:.2e})")
    f, u = build(sol)
    return Trim(float(sol[0]), float(sol[1]), float(sol[2]), cond.gamma + float(sol[0]), r, u, f)


@dataclass(frozen=True)
class ShortPeriod:
    a: np.ndarray  # 2x2 on (alpha, q)
    b: np.ndarray  # (2,) per rad of symmetric elevon
    eig: np.ndarray
    z_alpha: float
    m_alpha: float
    m_q: float
    m_de: float
    z_de: float
    nz_alpha: float  # dnz/dalpha (g/rad) at the CG
    nz_de: float  # dnz/dde (g/rad)


def _alpha_q_rates(cfg, cond, tr: Trim, dalpha: float, dq: float, dde: float) -> tuple[float, float, float]:
    s = _surfaces(tr.de + dde, 0.0, 0.0, cond, cfg)
    u = tr.u.copy()
    u[0:N_SURF] = s
    f = state_for(cfg, cond, tr.alpha + dalpha, pqr=(0.0, dq, 0.0), theta=tr.theta)
    f[F_GEAR] = cond.gear
    acc, wdot, aux = body_accel(cfg, f, u)
    a = tr.alpha + dalpha
    v = cond.tas
    # alpha-dot from body accelerations in the rotating body frame: a_rel = acc - w x v_b
    ub, wb = v * math.cos(a), v * math.sin(a)
    udot = acc[0] - dq * wb
    wdot_b = acc[2] + dq * ub
    alpha_dot = (ub * wdot_b - wb * udot) / (v * v)
    nz = -aux[X_FSZ] / cfg.dp[D_G0]
    return alpha_dot, float(wdot[1]), nz


def short_period(cfg: AirframeConfig, cond: Condition, tr: Trim | None = None) -> ShortPeriod:
    """Two-state (alpha, q) short-period model by central differences of the full nonlinear model."""
    tr = tr or trim(cfg, cond)
    ea, eq, ed = 1e-4, 1e-4, 1e-4

    def d(i):
        p = [0.0, 0.0, 0.0]
        m = [0.0, 0.0, 0.0]
        e = (ea, eq, ed)[i]
        p[i], m[i] = e, -e
        rp = _alpha_q_rates(cfg, cond, tr, *p)
        rm = _alpha_q_rates(cfg, cond, tr, *m)
        return [(x - y) / (2 * e) for x, y in zip(rp, rm, strict=True)]

    da_, dq_, dd_ = d(0), d(1), d(2)
    a = np.array([[da_[0], dq_[0]], [da_[1], dq_[1]]])
    b = np.array([dd_[0], dd_[1]])
    return ShortPeriod(
        a, b, np.sort(np.linalg.eigvals(a).real), da_[0], da_[1], dq_[1], dd_[1], dd_[0], da_[2], dd_[2]
    )


def time_to_double(sp: ShortPeriod) -> float:
    """t2 = ln 2 / lambda_max for an unstable short period; ``inf`` when stable."""
    lam = float(np.max(np.linalg.eigvals(sp.a).real))
    return math.log(2.0) / lam if lam > 0 else math.inf


@dataclass(frozen=True)
class Lateral:
    """Body-axis lateral derivatives (per rad, per rad/s) at trim: rows (beta_dot, p_dot, r_dot)."""

    a: np.ndarray  # 3x3 on (beta, p, r)
    b: np.ndarray  # 3x2 on (da, dr); da = differential elevon (left down positive)


def lateral(cfg: AirframeConfig, cond: Condition, tr: Trim | None = None) -> Lateral:
    tr = tr or trim(cfg, cond)
    v = cond.tas

    def rates(beta, p, r, da, dr):
        s = _surfaces(tr.de, da, dr, cond, cfg)
        u = tr.u.copy()
        u[0:N_SURF] = s
        f = state_for(cfg, cond, tr.alpha, beta=beta, pqr=(p, 0.0, r), theta=tr.theta)
        acc, wdot, _ = body_accel(cfg, f, u)
        a = tr.alpha
        ub, wb = v * math.cos(a) * math.cos(beta), v * math.sin(a) * math.cos(beta)
        vdot = acc[1] - (r * ub - p * wb)
        return np.array([vdot / v, wdot[0], wdot[2]])

    e = 1e-4
    cols = []
    for k in range(5):
        x = [0.0] * 5
        x[k] = e
        rp = rates(*x)
        x[k] = -e
        rm = rates(*x)
        cols.append((rp - rm) / (2 * e))
    m = np.array(cols).T
    return Lateral(m[:, 0:3], m[:, 3:5])


def ari_method1(lat: Lateral, alpha: float) -> float:
    """Rudder per unit differential elevon for a coordinated stability-axis roll (beta = 0, r = p tan alpha).

    Steady roll and yaw moment balance ``L_p p + L_r r + L_da da + L_dr dr = 0``, same for ``N``, with
    ``r = p tan(alpha)`` (roll about the velocity vector). Our reading of 'Method 1' of DSJ 71(2): the
    interconnect that removes the yaw-moment mismatch of a velocity-vector roll.
    """
    a, b = lat.a, lat.b
    t = math.tan(alpha)
    # unknowns da, dr per unit p: [L_da L_dr; N_da N_dr] [da; dr] = -[L_p + L_r t; N_p + N_r t]
    m = np.array([[b[1, 0], b[1, 1]], [b[2, 0], b[2, 1]]])
    rhs = -np.array([a[1, 1] + a[1, 2] * t, a[2, 1] + a[2, 2] * t])
    da, dr = np.linalg.solve(m, rhs)
    return float(dr / da)


def make_ic(cfg: AirframeConfig, cond: Condition, tr: Trim, *, h_ground: float = 0.0) -> AirframeIC:
    """Initial condition for the airframe module at a trimmed flight condition."""
    q_nb = euler_to_quat(0.0, tr.theta, cond.psi)
    v = cond.tas
    v_ned = (
        v * math.cos(cond.gamma) * math.cos(cond.psi),
        v * math.cos(cond.gamma) * math.sin(cond.psi),
        -v * math.sin(cond.gamma),
    )
    return AirframeIC(
        cond.lat, cond.lon, cond.h, v_ned, tuple(q_nb), tr.u.copy(), gear=cond.gear, h_ground=h_ground
    )


__all__ = [
    "Condition",
    "Lateral",
    "ShortPeriod",
    "Trim",
    "ari_method1",
    "body_accel",
    "input_row",
    "isa",
    "lateral",
    "make_ic",
    "reference_mass_properties",
    "short_period",
    "state_for",
    "time_to_double",
    "trim",
]
