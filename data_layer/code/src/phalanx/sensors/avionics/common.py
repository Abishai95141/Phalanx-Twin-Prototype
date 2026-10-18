"""Shared compiled helpers of the avionics kernels (AD-22): frames, filters, Gauss-Markov steps, power
state.

Every helper is ``@njit`` with fastmath off; the NumPy reference of each kernel is the kernel's own
``py_func`` calling the same helpers uncompiled, so compiled and reference agree bitwise (tested).
Numerical pitfalls of this machine are avoided by construction (core README, W1.2 notes): explicit products
instead of ``x**2``, ``airframe.geodesy.sin_cos`` where a sine and a cosine of the same angle are needed.
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from phalanx.airframe.geodesy import sin_cos

NJ = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}
TWO_PI = 6.283185307179586

# power-state transitions returned by power_step
P_NONE, P_LOST, P_RESTORED = 0, 1, 2


@njit(**NJ)
def quat_to_dcm(w, x, y, z, c):
    """Body -> NED direction-cosine matrix of a scalar-first unit quaternion (AD-49), into ``c[9]``
    (row-major: c[3 i + j] = C_ij, rows N, E, D; columns body x, y, z)."""
    ww = w * w
    xx = x * x
    yy = y * y
    zz = z * z
    c[0] = ww + xx - yy - zz
    c[1] = 2.0 * (x * y - w * z)
    c[2] = 2.0 * (x * z + w * y)
    c[3] = 2.0 * (x * y + w * z)
    c[4] = ww - xx + yy - zz
    c[5] = 2.0 * (y * z - w * x)
    c[6] = 2.0 * (x * z - w * y)
    c[7] = 2.0 * (y * z + w * x)
    c[8] = ww - xx - yy + zz


@njit(**NJ)
def body_to_nav(c, bx, by, bz, out):
    """out = C b (body vector to NED)."""
    out[0] = c[0] * bx + c[1] * by + c[2] * bz
    out[1] = c[3] * bx + c[4] * by + c[5] * bz
    out[2] = c[6] * bx + c[7] * by + c[8] * bz


@njit(**NJ)
def euler_with_error(c, pn, pe, pd):
    """(roll, pitch, yaw in [0, 2 pi)) of the computed attitude (I - [psi x]) C, psi the NED error angles."""
    # rows of (I - [psi x]) C needed for 3-2-1 Euler angles: row D (c31, c32, c33), entries c21, c11
    c11 = c[0] + pd * c[3] - pe * c[6]
    c21 = c[3] - pd * c[0] + pn * c[6]
    c31 = c[6] + pe * c[0] - pn * c[3]
    c32 = c[7] + pe * c[1] - pn * c[4]
    c33 = c[8] + pe * c[2] - pn * c[5]
    s = -c31
    if s > 1.0:
        s = 1.0
    elif s < -1.0:
        s = -1.0
    roll = math.atan2(c32, c33)
    pitch = math.asin(s)
    yaw = math.atan2(c21, c11)
    if yaw < 0.0:
        yaw = yaw + TWO_PI
    if yaw >= TWO_PI:
        yaw = yaw - TWO_PI
    return roll, pitch, yaw


@njit(**NJ)
def wrap_2pi(a):
    """Angle in [0, 2 pi)."""
    k = math.floor(a / TWO_PI)
    r = a - k * TWO_PI
    if r >= TWO_PI:
        r = r - TWO_PI
    if r < 0.0:
        r = 0.0
    return r


@njit(**NJ)
def gm_coeffs(dt, tau):
    """(phi, sqrt(1 - phi^2)) of a first-order Gauss-Markov process sampled every ``dt`` (exact)."""
    phi = math.exp(-dt / tau)
    return phi, math.sqrt(1.0 - phi * phi)


@njit(**NJ)
def lag2_step(y, yd, u0, u1, wn, zeta, dt, n_sub):
    """Second-order low-pass y'' + 2 zeta wn y' + wn^2 y = wn^2 u over one frame, trapezoidal rule on
    ``n_sub`` sub-steps with u linear inside the frame (A-stable; the M12 vane/gyro scheme).

    Returns (y, yd).
    """
    h = dt / n_sub
    c = 0.5 * h * wn * wn
    d = 1.0 + h * zeta * wn
    det = d + 0.5 * h * c
    for s in range(n_sub):
        ua = u0 + (u1 - u0) * (s / n_sub)
        ub = u0 + (u1 - u0) * ((s + 1) / n_sub)
        r0 = y + 0.5 * h * yd
        r1 = -c * y + (1.0 - h * zeta * wn) * yd + c * (ua + ub)
        y = (d * r0 + 0.5 * h * r1) / det
        yd = (-c * r0 + r1) / det
    return y, yd


@njit(**NJ)
def power_step(v, low_ns, powered, dt_ns, v_drop, hold_ns):
    """One frame of an LRU's supply monitor. Below ``v_drop`` for longer than ``hold_ns`` the LRU drops out;
    it restarts at the first frame back at or above ``v_drop``. Returns (low_ns, powered, transition)."""
    tr = P_NONE
    if v < v_drop:
        low_ns = low_ns + dt_ns
        if powered == 1 and low_ns > hold_ns:
            powered = 0
            tr = P_LOST
    else:
        low_ns = 0
        if powered == 0:
            powered = 1
            tr = P_RESTORED
    return low_ns, powered, tr


@njit(**NJ)
def interp_clamped(x, tx, ty):
    """Piecewise-linear table lookup, clamped at the ends (x real)."""
    n = tx.shape[0]
    if x <= tx[0]:
        return ty[0]
    if x >= tx[n - 1]:
        return ty[n - 1]
    lo = 0
    hi = n - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if tx[mid] <= x:
            lo = mid
        else:
            hi = mid
    w = (x - tx[lo]) / (tx[hi] - tx[lo])
    return ty[lo] + w * (ty[hi] - ty[lo])


@njit(**NJ)
def mag_deviation(heading, b, c):
    """One-cycle residual compass deviation B sin H + C cos H (rad)."""
    s, co = sin_cos(heading)
    return b * s + c * co


def empty_draws(n: int, k: int) -> np.ndarray:
    """Zero draw block (unused draws: shape kept so the kernels type the same way)."""
    return np.zeros((n, k), dtype=np.float64)
