"""Linear analysis of the DFCC pitch loop as implemented: lifted 80 Hz sampled-data model, margins (A3, V8).

The loop is broken at the **actuator command** (the "actuator consolidation point" of JOAST 58(4)): the DFCC
output ``u_k`` computed at frame ``k`` reaches the actuators ``delay`` later (two 240 Hz ticks = 8.33 ms, the
8 ms computation delay quantised to the truth frame, AD-36), is held until the next frame's command arrives,
drives the second-order servo (``wn``, ``zeta``) and the short-period airframe; the DFCC samples ``q`` and
``nz`` (with the elevon-lift feedthrough) at the frame instants and runs the PI law. Everything is exact for
the linearised airframe: the sampled-data loop is lifted to the 80 Hz frame with the matrix exponential
(``expm``), so ZOH, the fractional delay and the frame rate are all in the margins.

Used by the gain design (``design.py``) and the margin tests. Functions take plain matrices, so a test can
feed any airframe linearisation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.linalg import expm


@dataclass(frozen=True)
class PitchGains:
    g_n: float  # rad per g of measured (nz - 1)
    g_q: float  # rad per rad/s of pitch rate
    g_i: float  # rad per (normalised error x s)
    g_ff: float  # rad per normalised command


@dataclass(frozen=True)
class Margins:
    gm_db: float  # gain margin (min over the upper/lower crossings), dB
    pm_deg: float  # phase margin, deg
    w_gc: float  # gain-crossover frequency, rad/s
    w_pc: float  # phase-crossover frequency, rad/s
    stable: bool  # nominal closed loop stable


def _phi_gamma(a: np.ndarray, b: np.ndarray, t: float) -> tuple[np.ndarray, np.ndarray]:
    """exp(A t) and int_0^t exp(A s) ds B (augmented-matrix exponential)."""
    n, m = a.shape[0], b.shape[1]
    big = np.zeros((n + m, n + m))
    big[:n, :n] = a
    big[:n, n:] = b
    e = expm(big * t)
    return e[:n, :n], e[:n, n:]


def lifted_pitch_loop(
    a_sp: np.ndarray,
    b_sp: np.ndarray,
    nz_alpha: float,
    nz_de: float,
    gains: PitchGains,
    blend_w: float,
    n_ref: float,
    q_ref: float,
    *,
    wn: float,
    zeta: float,
    frame: float = 1.0 / 80.0,
    delay: float = 2.0 / 240.0,
    x_asa: float = 0.0,
    g0: float = 9.80665,
    rsa_wn: float = 0.0,
    rsa_zeta: float = 0.7,
    asa_wn: float = 0.0,
    asa_zeta: float = 0.7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Discrete (A, B, C, D) of the open loop from the injected command u_k to the DFCC output (loop broken).

    Continuous states: alpha, q, actuator position and rate, then (optional) second-order rate-gyro (RSA)
    and accelerometer (ASA) sensor dynamics. Discrete states: the continuous ones, the held previous command
    and the integrator. ``a_sp``/``b_sp``: short period on (alpha, q) per rad of elevon position.
    ``x_asa``: accelerometer station forward of the CG, m; the sensed normal acceleration is
    ``nz_cg + x_asa q'/g0`` (the pitch-acceleration term offsets the elevon-lift feedthrough).
    ``rsa_wn``/``asa_wn`` = 0 disables the sensor dynamics (ideal sensors).
    """
    # truth signals as rows on the plant part [alpha, q, d, ddot]
    nz_row = np.array(
        [nz_alpha + x_asa * a_sp[1, 0] / g0, x_asa * a_sp[1, 1] / g0, nz_de + x_asa * b_sp[1] / g0, 0.0]
    )
    q_row = np.array([0.0, 1.0, 0.0, 0.0])
    use_q = rsa_wn > 0.0
    use_n = asa_wn > 0.0
    nc = 4 + (2 if use_q else 0) + (2 if use_n else 0)
    ac = np.zeros((nc, nc))
    ac[0:2, 0:2] = a_sp
    ac[0:2, 2] = b_sp
    ac[2, 3] = 1.0
    ac[3, 2] = -(wn**2)
    ac[3, 3] = -2.0 * zeta * wn
    bc = np.zeros((nc, 1))
    bc[3, 0] = wn**2
    c_nz = np.zeros(nc)
    c_q = np.zeros(nc)
    k = 4
    if use_q:  # y'' = wn^2 (q - y) - 2 zeta wn y'
        ac[k, k + 1] = 1.0
        ac[k + 1, 0:4] = rsa_wn**2 * q_row
        ac[k + 1, k] = -(rsa_wn**2)
        ac[k + 1, k + 1] = -2.0 * rsa_zeta * rsa_wn
        c_q[k] = 1.0
        k += 2
    else:
        c_q[0:4] = q_row
    if use_n:
        ac[k, k + 1] = 1.0
        ac[k + 1, 0:4] = asa_wn**2 * nz_row
        ac[k + 1, k] = -(asa_wn**2)
        ac[k + 1, k + 1] = -2.0 * asa_zeta * asa_wn
        c_nz[k] = 1.0
    else:
        c_nz[0:4] = nz_row
    t1 = delay
    t2 = frame - delay
    phi_t1, gam_t1 = _phi_gamma(ac, bc, t1)
    phi_t2, gam_t2 = _phi_gamma(ac, bc, t2)
    phi = phi_t2 @ phi_t1
    g_prev = phi_t2 @ gam_t1  # previous command acts during [0, delay)
    g_new = gam_t2  # new command acts during [delay, frame)
    c_y = blend_w * c_nz / n_ref + (1.0 - blend_w) * c_q / q_ref
    # discrete states X = [x(nc), u_prev, z]; input u_k (injected command); output = DFCC command
    n = nc + 2
    ad = np.zeros((n, n))
    bd = np.zeros((n, 1))
    ad[0:nc, 0:nc] = phi
    ad[0:nc, nc] = g_prev[:, 0]
    bd[0:nc, 0] = g_new[:, 0]
    bd[nc, 0] = 1.0  # u_prev <- u_k
    ad[nc + 1, 0:nc] = -frame * c_y  # z_{k+1} = z_k + T (y_c - y_k), y_c = 0 for the loop analysis
    ad[nc + 1, nc + 1] = 1.0
    cd = np.zeros((1, n))
    cd[0, 0:nc] = gains.g_n * c_nz + gains.g_q * c_q
    cd[0, nc + 1] = gains.g_i
    dd = np.zeros((1, 1))
    return ad, bd, cd, dd


def margins_discrete(
    ad: np.ndarray, bd: np.ndarray, cd: np.ndarray, dd: np.ndarray, frame: float, n_freq: int = 1500
) -> Margins:
    """Gain/phase margins of the negative-feedback loop ``u = -L u`` with ``L(z) = -(C (zI - A)^-1 B + D)``.

    The DFCC output is the command itself (positive feedback in the sign convention of the law), so the
    loop transfer for the standard ``1 + L`` form is ``L = -G_open``.
    """
    wmax = math.pi / frame
    w = np.logspace(-2, math.log10(wmax * 0.999), n_freq)
    z = np.exp(1j * w * frame)
    eye = np.eye(ad.shape[0])
    lw = np.empty(w.size, dtype=complex)
    for k, zk in enumerate(z):
        lw[k] = -(cd @ np.linalg.solve(zk * eye - ad, bd))[0, 0] - dd[0, 0]
    mag = np.abs(lw)
    # closed loop stability: eigenvalues of A + B C / (1 - D) for u = C x + D u (u fed back unchanged)
    acl = ad + bd @ cd / (1.0 - dd[0, 0])
    stable = bool(np.max(np.abs(np.linalg.eigvals(acl))) < 1.0)
    # gain margin: at every crossing of the negative real axis, the gain change (either way) that moves the
    # crossing onto -1; the smallest in dB (the airframe is open-loop unstable, so both directions matter)
    gm = math.inf
    w_pc = math.nan
    for k in range(w.size - 1):
        i0, i1 = lw[k].imag, lw[k + 1].imag
        if i0 == 0.0 or i0 * i1 < 0.0:
            frac = i0 / (i0 - i1) if i0 != i1 else 0.0
            lc = lw[k] + frac * (lw[k + 1] - lw[k])
            if lc.real < 0.0 and abs(lc) > 0.0:
                g = abs(20.0 * math.log10(1.0 / abs(lc)))
                if g < gm:
                    gm, w_pc = g, w[k] + frac * (w[k + 1] - w[k])
    # phase margin: at every |L| = 1 crossing, 180 deg minus |arg L|
    pm = math.inf
    w_gc = math.nan
    for k in range(w.size - 1):
        if (mag[k] - 1.0) * (mag[k + 1] - 1.0) <= 0.0 and mag[k] != mag[k + 1]:
            frac = (1.0 - mag[k]) / (mag[k + 1] - mag[k])
            lc = lw[k] + frac * (lw[k + 1] - lw[k])
            margin = 180.0 - abs(math.degrees(math.atan2(lc.imag, lc.real)))
            if margin < pm:
                pm, w_gc = margin, w[k] + frac * (w[k + 1] - w[k])
    return Margins(gm, pm, w_gc, w_pc, stable)
