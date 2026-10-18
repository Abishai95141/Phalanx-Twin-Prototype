"""WGS-84 geodesy, Earth gravity and quaternion helpers for the M06 propagator (``@njit``, scalar math).

Conventions (documented in ``airframe/README.md``):

- ECEF axes: x through (0 deg N, 0 deg E), z through the North pole. NED: north, east, down at the geodetic
  position. Body: x forward, y right, z down.
- Quaternions are Hamilton, scalar first ``[w, x, y, z]``; ``q_ab`` rotates body-frame vectors into frame
  ``a`` (``v_a = q_ab * v_b * conj(q_ab)``), so ``R(q_ab)`` is the body-to-``a`` direction-cosine matrix.
- Earth model parameters are passed as scalars (``a, f, omega, gm, j2``). The NESC-style check cases switch to
  a non-rotating spherical Earth with ``f = omega = j2 = 0`` through the same code path.

Evidence: WGS-84 constants [TRANSFER: WGS-84, NIMA TR8350.2] live in ``configs/tejas/params/M06.yaml``;
the geodetic inversion is Heikkinen's closed form (exact to sub-millimetre off the polar axis); the J2
gravitation is the standard zonal-harmonic expansion (NASA/TM-2015-218675 check cases use the same model).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

NJ = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}
HALF_PI = 1.5707963267948966


@njit(**NJ)
def sin_cos(x):
    """(sin x, cos x) bitwise identical in compiled and interpreted code.

    LLVM fuses ``math.sin(x)`` and ``math.cos(x)`` of the same argument into one ``sincos`` call, which
    differs
    by 1 ulp from the two separate libm calls the interpreted reference makes (424 of 50,000 arguments in
    [-1.6, 1.6] on darwin-arm64, NumPy 2.5.4 / Numba 0.68, measured in W1.2). Two ``sin`` calls on different
    arguments are never fused: ``cos x = sin(pi/2 - x)`` (error below 1 ulp of pi/2, i.e. < 2.3e-16 absolute).
    """
    return math.sin(x), math.sin(HALF_PI - x)


@njit(**NJ)
def geodetic_to_ecef(lat, lon, h, a, f):
    """Geodetic (rad, rad, m above the ellipsoid) -> ECEF (m)."""
    e2 = f * (2.0 - f)
    s, c = sin_cos(lat)
    so, co = sin_cos(lon)
    n = a / math.sqrt(1.0 - e2 * s * s)
    return (n + h) * c * co, (n + h) * c * so, (n * (1.0 - e2) + h) * s


@njit(**NJ)
def ecef_to_geodetic(x, y, z, a, f):
    """ECEF (m) -> geodetic (lat rad, lon rad, h m). Heikkinen (1982) closed form; ``f = 0`` is a sphere."""
    e2 = f * (2.0 - f)
    b = a * (1.0 - f)
    r = math.sqrt(x * x + y * y)
    ep2 = (a * a - b * b) / (b * b)
    big_e2 = a * a - b * b
    ff = 54.0 * b * b * z * z
    g = r * r + (1.0 - e2) * z * z - e2 * big_e2
    c = e2 * e2 * ff * r * r / (g * g * g)
    s = np.cbrt(1.0 + c + math.sqrt(c * c + 2.0 * c))
    k = s + 1.0 / s + 1.0
    pp = ff / (3.0 * k * k * g * g)
    q = math.sqrt(1.0 + 2.0 * e2 * e2 * pp)
    arg = 0.5 * a * a * (1.0 + 1.0 / q) - pp * (1.0 - e2) * z * z / (q * (1.0 + q)) - 0.5 * pp * r * r
    if arg < 0.0:
        arg = 0.0
    r0 = -(pp * e2 * r) / (1.0 + q) + math.sqrt(arg)
    t = r - e2 * r0
    u = math.sqrt(t * t + z * z)
    v = math.sqrt(t * t + (1.0 - e2) * z * z)
    z0 = b * b * z / (a * v)
    h = u * (1.0 - b * b / (a * v))
    lat = math.atan2(z + ep2 * z0, r)
    lon = math.atan2(y, x)
    return lat, lon, h


@njit(**NJ)
def gravity_ecef(x, y, z, gm, a, j2, omega):
    """Gravitation (point mass + J2) plus centrifugal acceleration in ECEF axes (m/s^2)."""
    r2 = x * x + y * y + z * z
    r = math.sqrt(r2)
    k = gm / (r2 * r)
    t = 1.5 * j2 * (a * a) / r2
    zz = 5.0 * z * z / r2
    gx = -k * x * (1.0 + t * (1.0 - zz)) + omega * omega * x
    gy = -k * y * (1.0 + t * (1.0 - zz)) + omega * omega * y
    gz = -k * z * (1.0 + t * (3.0 - zz))
    return gx, gy, gz


@njit(**NJ)
def qmul(a0, a1, a2, a3, b0, b1, b2, b3):
    """Hamilton product a * b."""
    return (
        a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
        a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
        a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1,
        a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0,
    )


@njit(**NJ)
def q_to_dcm(q0, q1, q2, q3, m):
    """Fill ``m`` (3x3) with R(q): the matrix that maps body vectors into the reference frame."""
    m[0, 0] = q0 * q0 + q1 * q1 - q2 * q2 - q3 * q3
    m[0, 1] = 2.0 * (q1 * q2 - q0 * q3)
    m[0, 2] = 2.0 * (q1 * q3 + q0 * q2)
    m[1, 0] = 2.0 * (q1 * q2 + q0 * q3)
    m[1, 1] = q0 * q0 - q1 * q1 + q2 * q2 - q3 * q3
    m[1, 2] = 2.0 * (q2 * q3 - q0 * q1)
    m[2, 0] = 2.0 * (q1 * q3 - q0 * q2)
    m[2, 1] = 2.0 * (q2 * q3 + q0 * q1)
    m[2, 2] = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3


@njit(**NJ)
def q_en(lat, lon):
    """Quaternion of the NED -> ECEF rotation: R_z(lon) R_y(-lat - pi/2)."""
    hz = 0.5 * lon
    hy = 0.5 * (-lat - 0.5 * math.pi)
    a3, a0 = sin_cos(hz)
    b2, b0 = sin_cos(hy)
    # (a0 + a3 k) * (b0 + b2 j) = a0 b0 + a0 b2 j + a3 b0 k + a3 b2 (k j = -i)
    return a0 * b0, -a3 * b2, a0 * b2, a3 * b0


@njit(**NJ)
def dcm_ne(lat, lon, m):
    """Fill ``m`` with C_ne: ECEF vectors -> NED components."""
    sl, cl = sin_cos(lat)
    so, co = sin_cos(lon)
    m[0, 0] = -sl * co
    m[0, 1] = -sl * so
    m[0, 2] = cl
    m[1, 0] = -so
    m[1, 1] = co
    m[1, 2] = 0.0
    m[2, 0] = -cl * co
    m[2, 1] = -cl * so
    m[2, 2] = -sl


def euler_to_quat(phi: float, theta: float, psi: float) -> np.ndarray:
    """Body -> NED quaternion from 3-2-1 Euler angles (roll, pitch, yaw), rad. Python helper (ICs, tests)."""
    cr, sr = math.cos(phi / 2), math.sin(phi / 2)
    cp, sp = math.cos(theta / 2), math.sin(theta / 2)
    cy, sy = math.cos(psi / 2), math.sin(psi / 2)
    return np.array(
        [
            cy * cp * cr + sy * sp * sr,
            cy * cp * sr - sy * sp * cr,
            cy * sp * cr + sy * cp * sr,
            sy * cp * cr - cy * sp * sr,
        ]
    )


def quat_to_euler(q: np.ndarray) -> tuple[float, float, float]:
    """3-2-1 Euler angles (roll, pitch, yaw), rad, of a body -> NED quaternion. Python helper."""
    q0, q1, q2, q3 = (float(v) for v in q)
    phi = math.atan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 * q1 + q2 * q2))
    s = max(-1.0, min(1.0, 2 * (q0 * q2 - q3 * q1)))
    theta = math.asin(s)
    psi = math.atan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (q2 * q2 + q3 * q3))
    return phi, theta, psi
