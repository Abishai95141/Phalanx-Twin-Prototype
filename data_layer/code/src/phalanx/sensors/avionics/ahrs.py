"""Standby AHRS kernel: MEMS strapdown attitude with gravity erection and magnetic heading slaving (AD-51).

The AHRS output is the truth seen through a **structured attitude-error state** psi (NED small angles,
psi-angle form as the INS; A-W2.2-5):

- MEMS gyro errors (turn-on bias per power-on, Gauss-Markov in-run bias, angle random walk; TRANSFER: HG4930)
  integrate into psi: ``psi' = -C (b_g + w_g)``.
- **Erection** pulls the estimated vertical toward the accelerometer's apparent vertical with time constant
  ``erect_tau``: the levelling signal is the horizontal part of the estimated specific force
  ``f_hat = (I - [psi x]) (f_n + C b_a)``, which is non-zero both from a tilt error and from a real
  horizontal acceleration. A sustained coordinated turn therefore drags the attitude toward a false vertical
  (the classic AHRS turn error) unless the erection is cut out (``| |f| - g | > erect_cut_g g`` or body rate
  above ``erect_cut_rate``).
- **Heading** is slaved to a magnetic sensor with time constant ``slave_tau``; the sensor carries a residual
  one-cycle deviation ``B sin H + C cos H``; the output heading is magnetic (true minus declination).
- Electrical supply from ``util.bus_v`` (A-W2.2-1): unpowered -> outputs held (bus silent); a power-on draws
  fresh turn-on biases and re-erects quickly (psi reset to the accelerometer-level equilibrium).

Draws: per tick ``N_TICK_DRAWS`` normals (ARW xyz, GM drive xyz); per power-on ``N_ON_DRAWS`` (gyro, accel).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .common import (
    NJ,
    P_RESTORED,
    body_to_nav,
    euler_with_error,
    gm_coeffs,
    mag_deviation,
    power_step,
    wrap_2pi,
)

(
    P_BG_SIG,
    P_BG_GM_SIG,
    P_BG_GM_TAU,
    P_ARW,
    P_BA_SIG,
    P_ERECT_TAU,
    P_CUT_G,
    P_CUT_RATE,
    P_SLAVE_TAU,
    P_DECL,
    P_DEV_B,
    P_DEV_C,
    P_G0,
    P_V_DROP,
    P_HOLD,
) = range(15)
N_P = 15

F_PSI, F_BG0, F_BGM, F_BA0, F_HOLD = 0, 3, 6, 9, 12  # held outputs: heading, pitch, roll
N_OUT = 3
N_F = F_HOLD + N_OUT
I_TICK, I_POWERED, I_LOW_NS, I_NPOWER, I_PRIMED = 0, 1, 2, 3, 4
N_I = 5
OUT_NAMES = ("heading", "pitch", "roll")
N_TICK_DRAWS = 6
N_ON_DRAWS = 6


@njit(**NJ)
def _power_on(f, p, zon, row, c, g):
    """Fresh turn-on biases (row of ``zon``) and a fast initial erection to the level equilibrium."""
    if row >= zon.shape[0]:
        raise ValueError("AHRS power-on draws exhausted (more power cycles in the block than supplied)")
    for a in range(3):
        f[F_BG0 + a] = p[P_BG_SIG] * zon[row, a]
        f[F_BA0 + a] = p[P_BA_SIG] * zon[row, 3 + a]
        f[F_BGM + a] = 0.0
    dan = np.empty(3)
    body_to_nav(c, f[F_BA0], f[F_BA0 + 1], f[F_BA0 + 2], dan)
    f[F_PSI] = dan[1] / g
    f[F_PSI + 1] = -dan[0] / g
    f[F_PSI + 2] = 0.0


@njit(**NJ)
def ahrs_kernel(f, i, p, truth, vbus, ztick, zon, dt):
    """Advance L frames. Pure: returns (f, i, out[L, 3], powered[L], tru[L, 3]).

    truth: (L, 10) frame-end [qw, qx, qy, qz, p, q, r, fx, fy, fz] (SI). Output columns: magnetic heading
    [0, 2 pi), pitch, roll (rad); truth columns: true heading, pitch, roll.
    """
    f = f.copy()
    i = i.copy()
    L = truth.shape[0]
    out = np.empty((L, N_OUT))
    tru = np.empty((L, N_OUT))
    powered = np.empty(L, dtype=np.int64)
    c = np.empty(9)
    dwn = np.empty(3)
    dan = np.empty(3)
    dt_ns = int(np.rint(dt * 1e9))
    hold_ns = int(np.rint(p[P_HOLD] * 1e9))
    on0 = i[I_NPOWER]
    phg, sqg = gm_coeffs(dt, p[P_BG_GM_TAU])
    g = p[P_G0]
    sw = p[P_ARW] / math.sqrt(dt)
    for j in range(L):
        row = truth[j]
        qn = math.sqrt(row[0] * row[0] + row[1] * row[1] + row[2] * row[2] + row[3] * row[3])
        qw = row[0] / qn
        qx = row[1] / qn
        qy = row[2] / qn
        qz = row[3] / qn
        ww = qw * qw
        xx = qx * qx
        yy = qy * qy
        zz = qz * qz
        c[0] = ww + xx - yy - zz
        c[1] = 2.0 * (qx * qy - qw * qz)
        c[2] = 2.0 * (qx * qz + qw * qy)
        c[3] = 2.0 * (qx * qy + qw * qz)
        c[4] = ww - xx + yy - zz
        c[5] = 2.0 * (qy * qz - qw * qx)
        c[6] = 2.0 * (qx * qz - qw * qy)
        c[7] = 2.0 * (qy * qz + qw * qx)
        c[8] = ww - xx - yy + zz
        low, pw, tr = power_step(vbus[j], i[I_LOW_NS], i[I_POWERED], dt_ns, p[P_V_DROP], hold_ns)
        i[I_LOW_NS] = low
        i[I_POWERED] = pw
        if tr == P_RESTORED:
            i[I_NPOWER] += 1
            _power_on(f, p, zon, i[I_NPOWER] - on0, c, g)
        if i[I_PRIMED] == 0:
            _power_on(f, p, zon, i[I_NPOWER] - on0, c, g)
            i[I_PRIMED] = 1
        z = ztick[j]
        wgx = f[F_BG0] + f[F_BGM] + sw * z[0]
        wgy = f[F_BG0 + 1] + f[F_BGM + 1] + sw * z[1]
        wgz = f[F_BG0 + 2] + f[F_BGM + 2] + sw * z[2]
        for a in range(3):
            f[F_BGM + a] = phg * f[F_BGM + a] + p[P_BG_GM_SIG] * sqg * z[3 + a]
        body_to_nav(c, wgx, wgy, wgz, dwn)
        body_to_nav(
            c, row[7] + f[F_BA0], row[8] + f[F_BA0 + 1], row[9] + f[F_BA0 + 2], dan
        )  # measured f, NED
        pn = f[F_PSI]
        pe = f[F_PSI + 1]
        pd = f[F_PSI + 2]
        dpn = -dwn[0]
        dpe = -dwn[1]
        dpd = -dwn[2]
        # erection on the horizontal part of the estimated specific force f_hat = (I - [psi x]) f_meas
        fhn = dan[0] + pd * dan[1] - pe * dan[2]
        fhe = dan[1] - pd * dan[0] + pn * dan[2]
        fmag = math.sqrt(row[7] * row[7] + row[8] * row[8] + row[9] * row[9])
        rate = math.sqrt(row[4] * row[4] + row[5] * row[5] + row[6] * row[6])
        dev_g = fmag - g
        if dev_g < 0.0:
            dev_g = -dev_g
        if dev_g <= p[P_CUT_G] * g and rate <= p[P_CUT_RATE]:
            dpe = dpe - fhn / (g * p[P_ERECT_TAU])
            dpn = dpn + fhe / (g * p[P_ERECT_TAU])
        # heading slaving: output heading error (= -psi_D) toward the magnetic-sensor deviation
        roll_t, pitch_t, yaw_t = euler_with_error(c, 0.0, 0.0, 0.0)
        dev = mag_deviation(yaw_t, p[P_DEV_B], p[P_DEV_C])
        dpd = dpd - (pd + dev) / p[P_SLAVE_TAU]
        f[F_PSI] = pn + dt * dpn
        f[F_PSI + 1] = pe + dt * dpe
        f[F_PSI + 2] = pd + dt * dpd
        tru[j, 0] = yaw_t
        tru[j, 1] = pitch_t
        tru[j, 2] = roll_t
        if i[I_POWERED] == 1:
            roll, pitch, yaw = euler_with_error(c, f[F_PSI], f[F_PSI + 1], f[F_PSI + 2])
            f[F_HOLD] = wrap_2pi(yaw - p[P_DECL])
            f[F_HOLD + 1] = pitch
            f[F_HOLD + 2] = roll
        for k in range(N_OUT):
            out[j, k] = f[F_HOLD + k]
        powered[j] = i[I_POWERED]
        i[I_TICK] += 1
    return f, i, out, powered, tru


def ahrs_reference(f, i, p, truth, vbus, ztick, zon, dt):
    """NumPy reference: the same source uncompiled."""
    return ahrs_kernel.py_func(f, i, p, truth, vbus, ztick, zon, dt)


def ahrs_initial_state() -> tuple[np.ndarray, np.ndarray]:
    f = np.zeros(N_F)
    i = np.zeros(N_I, dtype=np.int64)
    i[I_POWERED] = 1
    return f, i
