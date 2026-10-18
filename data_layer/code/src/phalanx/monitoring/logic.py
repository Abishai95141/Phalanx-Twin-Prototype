"""BIT and monitoring decision logic (architecture §6 M14, §9.4; report §9 "BIT ... persistence"; note
``texture_and_fault_gap_closure.md`` synthesis (d) items 2-4, 9-10).

Two compiled kernels, each with its NumPy reference (the same source uncompiled, bitwise equal, tested):

``bit_test_kernel``
    An LRU's internal test statistic, in σ units of its healthy scatter, sampled on the test grid:

        x_j = μ + z_j,   z_j = φ z_{j-1} + sqrt(1 − φ²) · s_j · ε_j,   ε_j ~ N(0, 1)

    μ = unit offset (per LRU serial) + flight offset (per sortie) + fault condition (M11). The innovation
    scale s_j is a two-component mixture (probability ``p_mix`` of the wide component, ratio ``k_mix``)
    normalised to unit variance, so z is a stationary, *coloured* (AR(1)) and *heavy-tailed* process: the same
    noise form as the recorded sensor texture (M13, round-2 A2/A3: AR(1) with a heavy-tail mixture), which is
    what I6 asks for ("BIT runs on the same coloured, heavy-tailed sensor model"). Independent-sample m-of-n
    arithmetic understates false alarms under coloured noise (RADC-TR-81-220); a property test shows it.

    Declaration (persistence): ``consecutive`` = n consecutive exceedances (FCS 4 frames ≈ 60 ms;
    IECMS "several iterations"), or ``m_of_n`` on **non-overlapping** windows (RADC Table 5-8 set-up;
    overlapping windows raise the false-alarm rate). After a declaration the kernel also reports the first
    sample at which the test has passed ``n_clear`` consecutive times (caution clear).

``limit_kernel``
    A limit-plus-persistence exceedance monitor on a recorded channel (CIR values, engineering units):
    declared after ``n_persist`` consecutive samples beyond the limit, cleared after ``n_clear`` consecutive
    samples back inside the limit minus a hysteresis band; tracks the peak.
"""

from __future__ import annotations

import numpy as np
from numba import njit

__all__ = [
    "BIT_FLOATS",
    "BIT_INTS",
    "LIM_FLOATS",
    "LIM_INTS",
    "MODE_CONSECUTIVE",
    "MODE_M_OF_N",
    "bit_test_kernel",
    "bit_test_reference",
    "limit_kernel",
    "limit_reference",
    "mixture_scales",
]

MODE_CONSECUTIVE, MODE_M_OF_N = 0, 1
#: float state of one BIT test: AR(1) value
BIT_FLOATS = ("z",)
#: int state of one BIT test
BIT_INTS = ("consec", "win_pos", "win_cnt", "declared", "pass_run", "cleared", "initialised")
B_CONSEC, B_WINPOS, B_WINCNT, B_DECL, B_PASS, B_CLR, B_INIT = range(7)


def mixture_scales(p_mix: float, k_mix: float) -> tuple[float, float]:
    """(narrow, wide) innovation scales of the unit-variance two-component mixture."""
    lo = 1.0 / np.sqrt((1.0 - p_mix) + p_mix * k_mix * k_mix)
    return float(lo), float(k_mix * lo)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _bit(z, ist, mu, normals, uniforms, phi, s_lo, s_hi, p_mix, thr, mode, m, n, n_clear):
    """Advance one test over L samples. Returns (z, int state, first_declare, first_clear, n_exceed)."""
    ist = ist.copy()
    a = np.sqrt(1.0 - phi * phi)
    first_decl = -1
    first_clr = -1
    n_ex = 0
    for j in range(normals.shape[0]):
        s = s_hi if uniforms[j] < p_mix else s_lo
        if ist[B_INIT] == 0:  # stationary start: z_0 ~ N(0, 1) from the first draw
            z = s * normals[j]
            ist[B_INIT] = 1
        else:
            z = phi * z + a * s * normals[j]
        ex = mu + z > thr
        if ex:
            n_ex += 1
        if ist[B_DECL] == 0:
            if mode == 0:
                ist[B_CONSEC] = ist[B_CONSEC] + 1 if ex else 0
                if ist[B_CONSEC] >= n:
                    ist[B_DECL] = 1
                    first_decl = j
            else:
                if ex:
                    ist[B_WINCNT] += 1
                ist[B_WINPOS] += 1
                if ist[B_WINPOS] == n:
                    if ist[B_WINCNT] >= m:
                        ist[B_DECL] = 1
                        first_decl = j
                    ist[B_WINPOS] = 0
                    ist[B_WINCNT] = 0
        elif ist[B_CLR] == 0:
            ist[B_PASS] = 0 if ex else ist[B_PASS] + 1
            if ist[B_PASS] >= n_clear:
                ist[B_CLR] = 1
                first_clr = j
    return z, ist, first_decl, first_clr, n_ex


def bit_test_kernel(z, ist, mu, normals, uniforms, *, phi, p_mix, k_mix, thr, mode, m, n, n_clear):
    """Compiled BIT test (see module docstring); ``normals`` and ``uniforms`` are the keyed draws of the
    test samples being evaluated (indexed by absolute test-sample number, AD-37)."""
    s_lo, s_hi = mixture_scales(p_mix, k_mix)
    return _bit(
        float(z),
        np.asarray(ist, np.int64),
        float(mu),
        np.ascontiguousarray(normals, np.float64),
        np.ascontiguousarray(uniforms, np.float64),
        float(phi),
        s_lo,
        s_hi,
        float(p_mix),
        float(thr),
        int(mode),
        int(m),
        int(n),
        int(n_clear),
    )


def bit_test_reference(z, ist, mu, normals, uniforms, *, phi, p_mix, k_mix, thr, mode, m, n, n_clear):
    """NumPy reference of :func:`bit_test_kernel` (same source, uncompiled)."""
    s_lo, s_hi = mixture_scales(p_mix, k_mix)
    return _bit.py_func(
        float(z),
        np.asarray(ist, np.int64),
        float(mu),
        np.ascontiguousarray(normals, np.float64),
        np.ascontiguousarray(uniforms, np.float64),
        float(phi),
        s_lo,
        s_hi,
        float(p_mix),
        float(thr),
        int(mode),
        int(m),
        int(n),
        int(n_clear),
    )


# ------------------------------------------------------------------------------------------ limit monitor
#: float state of one limit monitor: peak beyond the limit since declaration (or since the run started)
LIM_FLOATS = ("peak",)
LIM_INTS = ("count", "active", "clear_count", "t_start", "n_events")
L_COUNT, L_ACTIVE, L_CLR, L_TSTART, L_NEV = range(5)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _limit(peak, ist, t, v, valid, limit, sense, hyst, n_persist, n_clear):
    """Limit monitor over samples. ``sense`` +1 = high limit, -1 = low limit. Invalid samples reset the
    persistence count (a gap is not evidence of an exceedance).

    Returns (peak, int state, decl_idx[], clear_idx[], peaks_at_clear[]) with -1 padding; at most one
    declaration and one clear per sample.
    """
    ist = ist.copy()
    n = t.shape[0]
    decl = np.full(n, -1, np.int64)
    clr = np.full(n, -1, np.int64)
    pk = np.zeros(n, np.float64)
    nd = 0
    nc = 0
    for j in range(n):
        if not valid[j]:
            ist[L_COUNT] = 0
            continue
        x = v[j] * sense
        lim = limit * sense
        if ist[L_ACTIVE] == 0:
            if x > lim:
                ist[L_COUNT] += 1
                if ist[L_COUNT] == 1:  # a new excursion starts its own peak
                    peak = x
                elif x > peak:
                    peak = x
                if ist[L_COUNT] >= n_persist:
                    ist[L_ACTIVE] = 1
                    ist[L_CLR] = 0
                    ist[L_TSTART] = t[j]
                    ist[L_NEV] += 1
                    decl[nd] = j
                    nd += 1
            else:
                ist[L_COUNT] = 0
        else:
            if x > peak:
                peak = x
            if x < lim - hyst:
                ist[L_CLR] += 1
                if ist[L_CLR] >= n_clear:
                    ist[L_ACTIVE] = 0
                    ist[L_COUNT] = 0
                    clr[nc] = j
                    pk[nc] = peak * sense
                    nc += 1
            else:
                ist[L_CLR] = 0
    return peak, ist, decl[:nd], clr[:nc], pk[:nc]


def limit_kernel(peak, ist, t, v, valid, *, limit, sense, hyst, n_persist, n_clear):
    """Compiled limit monitor (see :func:`_limit`)."""
    return _limit(
        float(peak),
        np.asarray(ist, np.int64),
        np.ascontiguousarray(t, np.int64),
        np.ascontiguousarray(v, np.float64),
        np.ascontiguousarray(valid, np.bool_),
        float(limit),
        float(sense),
        float(hyst),
        int(n_persist),
        int(n_clear),
    )


def limit_reference(peak, ist, t, v, valid, *, limit, sense, hyst, n_persist, n_clear):
    return _limit.py_func(
        float(peak),
        np.asarray(ist, np.int64),
        np.ascontiguousarray(t, np.int64),
        np.ascontiguousarray(v, np.float64),
        np.ascontiguousarray(valid, np.bool_),
        float(limit),
        float(sense),
        float(hyst),
        int(n_persist),
        int(n_clear),
    )
