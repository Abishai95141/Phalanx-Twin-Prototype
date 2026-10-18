"""Initial conditions of the M06 airframe as parameters (so they enter the config hash, AD-36).

An :class:`AirframeIC` is run configuration (the sortie start), not a model parameter. ``ic_params`` turns it
into ``ic_*`` entries that are merged into the module ParamSet; ``initial_float_state`` builds the kernel
float state (ECEF position, Earth-relative velocity, body -> ECEF quaternion, inertial body rate). The
inertial rate includes the Earth rate and the transport rate, so a level-trimmed start stays level.
``u_ref`` is the input row (kernel input layout) the aircraft was initialised with (``initial_outputs``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from phalanx.core.module import Param

from .geodesy import dcm_ne, geodetic_to_ecef, q_en, qmul
from .kernel import D_A, D_F, D_OM, D_RROLL, F_GEAR, F_HGND, F_Q0, F_RX, F_VX, F_WHL, F_WHR, F_WX, N_F

IC_SOURCE = (
    "run configuration: sortie initial condition (set by the scenario / W2.1 wiring), not a model parameter"
)


@dataclass(frozen=True)
class AirframeIC:
    lat: float  # rad
    lon: float  # rad
    h: float  # m above the ellipsoid
    vel_ned: tuple[float, float, float]  # m/s relative to the Earth
    quat_nb: tuple[float, float, float, float]  # body -> NED
    u_ref: np.ndarray = field(repr=False)  # reference input row (kernel layout)
    omega_nb: tuple[float, float, float] = (0.0, 0.0, 0.0)  # body rate relative to NED, rad/s
    gear: float = 0.0  # 0 retracted .. 1 down and locked
    h_ground: float = 0.0  # runway height above the ellipsoid, m

    def __post_init__(self) -> None:
        q = np.asarray(self.quat_nb, dtype=np.float64)
        if abs(float(np.linalg.norm(q)) - 1.0) > 1e-9:
            raise ValueError("quat_nb must be a unit quaternion")
        if not np.all(np.isfinite(np.asarray(self.u_ref, dtype=np.float64))):
            raise ValueError("u_ref must be finite")


def ic_params(ic: AirframeIC) -> dict[str, Param]:
    def p(v, unit):
        return Param(v, unit, "ASSUMPTION", IC_SOURCE)

    return {
        "ic_lat": p(float(ic.lat), "rad"),
        "ic_lon": p(float(ic.lon), "rad"),
        "ic_h": p(float(ic.h), "m"),
        "ic_vel_ned": p(np.asarray(ic.vel_ned, dtype=np.float64), "m/s"),
        "ic_quat_nb": p(np.asarray(ic.quat_nb, dtype=np.float64), "1"),
        "ic_omega_nb": p(np.asarray(ic.omega_nb, dtype=np.float64), "rad/s"),
        "ic_gear": p(float(ic.gear), "1"),
        "ic_h_ground": p(float(ic.h_ground), "m"),
        "ic_u_ref": p(np.asarray(ic.u_ref, dtype=np.float64), "1"),
    }


def initial_float_state(
    lat: float,
    lon: float,
    h: float,
    vel_ned: np.ndarray,
    quat_nb: np.ndarray,
    omega_nb: np.ndarray,
    gear: float,
    h_ground: float,
    dp: np.ndarray,
) -> np.ndarray:
    a, f, om = float(dp[D_A]), float(dp[D_F]), float(dp[D_OM])
    e2 = f * (2.0 - f)
    f_state = np.zeros(N_F)
    f_state[F_RX : F_RX + 3] = geodetic_to_ecef(lat, lon, h, a, f)
    cne = np.empty((3, 3))
    dcm_ne(lat, lon, cne)
    v_ned = np.asarray(vel_ned, dtype=np.float64)
    f_state[F_VX : F_VX + 3] = cne.T @ v_ned
    qe = q_en(lat, lon)
    qn = [float(v) for v in quat_nb]
    f_state[F_Q0 : F_Q0 + 4] = qmul(*qe, *qn)
    # inertial body rate = rate relative to NED + C_bn (Earth rate + transport rate), NED components
    sl, cl = math.sin(lat), math.cos(lat)
    rn = a / math.sqrt(1.0 - e2 * sl * sl)
    rm = a * (1.0 - e2) / (1.0 - e2 * sl * sl) ** 1.5
    w_ie = np.array([om * cl, 0.0, -om * sl])
    w_en = np.array([v_ned[1] / (rn + h), -v_ned[0] / (rm + h), -v_ned[1] * sl / cl / (rn + h)])
    q0, q1, q2, q3 = qn
    cnb = np.array(
        [
            [q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
            [2 * (q1 * q2 + q0 * q3), q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3, 2 * (q2 * q3 - q0 * q1)],
            [2 * (q1 * q3 - q0 * q2), 2 * (q2 * q3 + q0 * q1), q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3],
        ]
    )
    f_state[F_WX : F_WX + 3] = np.asarray(omega_nb, dtype=np.float64) + cnb.T @ (w_ie + w_en)
    f_state[F_GEAR] = gear
    f_state[F_HGND] = h_ground
    if gear > 0.999 and h - h_ground < 5.0:  # starting on the ground: wheels roll at ground speed
        u_ground = float(cnb[:, 0] @ v_ned)
        f_state[F_WHL] = f_state[F_WHR] = u_ground / float(dp[D_RROLL])
    return f_state
