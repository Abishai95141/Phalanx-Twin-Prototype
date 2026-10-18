"""Stores management system (SMS) station status (AD-51; A-W2.2-9).

The SMS is a discrete system: its state changes only on events (mission loading, release / jettison
commands), so it has no continuous kernel. Per truth frame the station content codes (dictionary
``store_station`` code table, synthetic) and the RELEASE word are held; the supply monitor (A-W2.2-1) runs per
frame in a small compiled kernel. A commanded release empties the station and sets its RELEASED bit, except
that with probability ``p_hung`` the store hangs (content kept, bit clear); a jettison always empties. An
unpowered SMS ignores commands.

Events (proposed catalogue additions, not yet in ``configs/interfaces/w1_events.yaml``):
``avio.sms_load`` {"stations": [9 content codes]} and ``avio.sms_release`` {"station": 1..9,
"mode": "release" | "jettison"}.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from .common import NJ, power_step

N_STATIONS = 9
EMPTY = 0
#: int state: station codes 0..8, RELEASED mask, release-command counter, powered, low_ns
I_CODES, I_RELEASED, I_NCMD, I_POWERED, I_LOW_NS = 0, 9, 10, 11, 12
N_I = 13
LOAD_EVENT = "avio.sms_load"
RELEASE_EVENT = "avio.sms_release"


@njit(**NJ)
def sms_kernel(i, vbus, dt, v_drop, hold_s):
    """Advance L frames of the supply monitor; returns (i, codes[L, 9], released[L], powered[L])."""
    i = i.copy()
    L = vbus.shape[0]
    codes = np.empty((L, N_STATIONS), dtype=np.int64)
    released = np.empty(L, dtype=np.int64)
    powered = np.empty(L, dtype=np.int64)
    dt_ns = int(np.rint(dt * 1e9))
    hold_ns = int(np.rint(hold_s * 1e9))
    for j in range(L):
        low, pw, _tr = power_step(vbus[j], i[I_LOW_NS], i[I_POWERED], dt_ns, v_drop, hold_ns)
        i[I_LOW_NS] = low
        i[I_POWERED] = pw
        for k in range(N_STATIONS):
            codes[j, k] = i[I_CODES + k]
        released[j] = i[I_RELEASED]
        powered[j] = pw
    return i, codes, released, powered


def sms_initial_state() -> np.ndarray:
    i = np.zeros(N_I, dtype=np.int64)
    i[I_POWERED] = 1
    return i


def apply_load(i: np.ndarray, stations, n_codes: int) -> np.ndarray:
    """A new mission loading: every station's content code (0 = EMPTY); clears the RELEASED word."""
    codes = [int(x) for x in stations]
    if len(codes) != N_STATIONS or any(not 0 <= c < n_codes for c in codes):
        raise ValueError(
            f"sms_load needs {N_STATIONS} store_station codes in 0..{n_codes - 1}, got {stations}"
        )
    out = i.copy()
    out[I_CODES : I_CODES + N_STATIONS] = codes
    out[I_RELEASED] = 0
    return out


def apply_release(i: np.ndarray, station: int, mode: str, u: float, p_hung: float) -> np.ndarray:
    """A release or jettison command on ``station`` (1..9) with the command's keyed uniform ``u``."""
    if not 1 <= int(station) <= N_STATIONS or mode not in ("release", "jettison"):
        raise ValueError(
            f"sms_release needs station 1..{N_STATIONS} and mode release|jettison, got {station}, {mode}"
        )
    out = i.copy()
    out[I_NCMD] += 1
    k = int(station) - 1
    if out[I_POWERED] == 0 or out[I_CODES + k] == EMPTY:
        return out  # no power, or nothing to release
    if mode == "jettison" or u >= p_hung:
        out[I_CODES + k] = EMPTY
        out[I_RELEASED] |= 1 << k
    return out
