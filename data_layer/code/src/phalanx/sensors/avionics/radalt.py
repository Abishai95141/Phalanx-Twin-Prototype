"""Radar (radio) altimeter kernel (AD-51; A-W2.2-8).

Physics, per frame:

- the beam reaches the nearest ground point inside its half-angle: with the body z axis tilted by ``tilt``
  from the vertical (``cos tilt = C_33``), the slant range over flat ground is ``h`` while
  ``tilt <= beam_half`` and ``h / cos(tilt - beam_half)`` beyond (the return comes from the beam edge);
- the ground under the beam is ``af.hag``'s flat ground raised by a terrain/vegetation height drawn as a
  spatial Gauss-Markov process along the flown path (correlation length ``terrain_length``; draw index =
  along-track cell of length ``terrain_cell``), so the texture belongs to the place flown over, and forks
  along the same path share it (CRN);
- per-unit scale and zero errors (installation, keyed by the unit serial), first-order tracker lag;
- **validity** (ARINC-429 SSM, dictionary ssm_bnr): NO_COMPUTED_DATA above ``h_max`` or beyond
  ``track_max_tilt`` (the reading holds its last tracked value), NORMAL otherwise; the electrical supply from
  ``util.bus_v`` (A-W2.2-1) stops the transmitter (bus silent, value held).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .common import NJ, gm_coeffs, power_step

(
    P_H_MAX,
    P_BEAM_HALF,
    P_TILT_MAX,
    P_TERRAIN_SIG,
    P_TERRAIN_LEN,
    P_CELL,
    P_TRACK_TAU,
    P_V_DROP,
    P_HOLD,
) = range(9)
N_P = 9
F_S, F_TERRAIN, F_Y, F_SCALE, F_OFFSET = 0, 1, 2, 3, 4
N_F = 5
I_TICK, I_POWERED, I_LOW_NS, I_CELL, I_PRIMED, I_SSM = 0, 1, 2, 3, 4, 5
N_I = 6
SSM_FW, SSM_NCD, SSM_NORMAL = 0, 1, 3


@njit(**NJ)
def radalt_kernel(f, i, p, truth, vbus, zcell, dt):
    """Advance L frames. Pure: returns (f, i, out[L], ssm[L], powered[L], tru[L]).

    truth: (L, 7) frame-end [hag, qw, qx, qy, qz, vn, ve] (SI). zcell: (K,) standard normals of the
    along-track cells [cell, cell + K) (K covers the block's flown distance).
    """
    f = f.copy()
    i = i.copy()
    L = truth.shape[0]
    out = np.empty(L)
    tru = np.empty(L)
    ssm = np.empty(L, dtype=np.int64)
    powered = np.empty(L, dtype=np.int64)
    dt_ns = int(np.rint(dt * 1e9))
    hold_ns = int(np.rint(p[P_HOLD] * 1e9))
    cell0 = i[I_CELL]
    phi, sq = gm_coeffs(p[P_CELL], p[P_TERRAIN_LEN])
    a_track = 1.0 - math.exp(-dt / p[P_TRACK_TAU])
    for j in range(L):
        row = truth[j]
        qn = math.sqrt(row[1] * row[1] + row[2] * row[2] + row[3] * row[3] + row[4] * row[4])
        qw = row[1] / qn
        qx = row[2] / qn
        qy = row[3] / qn
        qz = row[4] / qn
        c33 = qw * qw - qx * qx - qy * qy + qz * qz  # cos(tilt of the body z axis from the vertical)
        if c33 > 1.0:
            c33 = 1.0
        elif c33 < -1.0:
            c33 = -1.0
        tilt = math.acos(c33)
        # along-track terrain cells (draw index = cell number)
        if i[I_PRIMED] == 0:
            f[F_TERRAIN] = p[P_TERRAIN_SIG] * zcell[0]
        gs = math.sqrt(row[5] * row[5] + row[6] * row[6])
        f[F_S] = f[F_S] + gs * dt
        while f[F_S] >= p[P_CELL]:
            f[F_S] = f[F_S] - p[P_CELL]
            i[I_CELL] += 1
            k = i[I_CELL] - cell0
            if k >= zcell.shape[0]:
                raise ValueError(
                    "radar-altimeter terrain draws exhausted (ground speed above the block bound)"
                )
            f[F_TERRAIN] = phi * f[F_TERRAIN] + p[P_TERRAIN_SIG] * sq * zcell[k]
        h = row[0] - f[F_TERRAIN]
        if h < 0.0:
            h = 0.0
        r = h
        if tilt > p[P_BEAM_HALF]:
            r = h / math.cos(tilt - p[P_BEAM_HALF])
        r = (1.0 + f[F_SCALE]) * r + f[F_OFFSET]
        if i[I_PRIMED] == 0:
            f[F_Y] = r
            i[I_PRIMED] = 1
        low, pw, _tr = power_step(vbus[j], i[I_LOW_NS], i[I_POWERED], dt_ns, p[P_V_DROP], hold_ns)
        i[I_LOW_NS] = low
        i[I_POWERED] = pw
        track = tilt <= p[P_TILT_MAX] and r <= p[P_H_MAX]
        if pw == 1:
            if track:
                f[F_Y] = f[F_Y] + (r - f[F_Y]) * a_track
                i[I_SSM] = SSM_NORMAL
            else:
                i[I_SSM] = SSM_NCD  # lost track: value held, NCD
        out[j] = f[F_Y]
        ssm[j] = i[I_SSM]
        powered[j] = pw
        tru[j] = row[0]
        i[I_TICK] += 1
    return f, i, out, ssm, powered, tru


def radalt_reference(f, i, p, truth, vbus, zcell, dt):
    """NumPy reference: the same source uncompiled."""
    return radalt_kernel.py_func(f, i, p, truth, vbus, zcell, dt)


def radalt_initial_state(scale: float, offset: float) -> tuple[np.ndarray, np.ndarray]:
    """Initial state with the unit's installation scale and zero errors (drawn by the caller)."""
    f = np.zeros(N_F)
    f[F_SCALE] = scale
    f[F_OFFSET] = offset
    i = np.zeros(N_I, dtype=np.int64)
    i[I_POWERED] = 1
    i[I_SSM] = SSM_NORMAL
    return f, i


def cells_needed(dt: float, n: int, cell: float, v_max: float = 1000.0) -> int:
    """Draws to supply for one block: cells flown at up to ``v_max`` m/s plus the current cell."""
    return int(np.ceil(n * dt * v_max / cell)) + 2
