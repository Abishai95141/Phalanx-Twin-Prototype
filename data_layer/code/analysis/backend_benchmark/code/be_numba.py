"""Numba backend for the W0.6 workload: a scalar kernel compiled with @njit, fastmath off.

- `step_block(X, S, P, health, T, inputs, noise)` advances one unit over one block (pure function: new arrays out).
- `step_block_batch(...)` advances U units with `prange` over units (each unit runs the same scalar kernel, so a
  unit's result cannot depend on the batch it is in or on the thread count; no cross-unit reductions).
- dtype-generic: comparisons act on `.real`, so the same source compiles a complex128 specialisation for
  complex-step derivatives (M5).

Expression order follows ref_numpy.py exactly (the bitwise-agreement contract, A1).
"""

from __future__ import annotations

import numpy as np
import workload as W
from numba import njit, prange

# compile-time constants (frozen into the machine code)
T0, P0 = W.T0, W.P0
H, HH, DTC = W.H, W.HH, W.DTC
NSUB, CTRL_DIV = W.NSUB, W.CTRL_DIV
SEL_GOV, SEL_N1, SEL_T5, SEL_ACC, SEL_DEC, SEL_MIN = (
    W.SEL_GOV, W.SEL_N1, W.SEL_T5, W.SEL_ACC, W.SEL_DEC, W.SEL_MIN,
)  # fmt: skip
P_I_LP, P_I_HP, P_TAU_ACT, P_TAU_V = W.P_I_LP, W.P_I_HP, W.P_TAU_ACT, W.P_TAU_V
P_TAU_G_REF, P_W_EXP, P_TAU_M, P_K_CLR = W.P_TAU_G_REF, W.P_W_EXP, W.P_TAU_M, W.P_K_CLR
P_KP, P_KI, P_K_N1, P_K_T5 = W.P_KP, W.P_KI, W.P_K_N1, W.P_K_T5
P_ACC_SCALE, P_DEC_SCALE, P_A_EXP, P_QD_REF = W.P_ACC_SCALE, W.P_DEC_SCALE, W.P_A_EXP, W.P_QD_REF
P_PHI_F, P_S_F, P_PHI_Q, P_S_Q = W.P_PHI_F, W.P_S_F, W.P_PHI_Q, W.P_S_Q
P_OM1, P_OM2, P_N1MAX_C, P_T5MAX = W.P_OMEGA1_100, W.P_OMEGA2_100, W.P_N1MAX_C, W.P_T5MAX
P_WF_MIN, P_W_REF = W.P_WF_MIN, W.P_W_REF

JIT = dict(cache=True, fastmath=False, error_model="numpy", nogil=True)


@njit(inline="always", **JIT)
def _bracket(x, vr):
    """Largest i in [0, K-2] with x[i] <= vr (vr already clamped to [x0, x_{K-1}]); binary search."""
    lo = 0
    hi = x.shape[0] - 1
    while hi - lo > 1:
        mid = (lo + hi) >> 1
        if x[mid] <= vr:
            lo = mid
        else:
            hi = mid
    return lo


@njit(inline="always", **JIT)
def lk1(x, r, y, v):
    K = x.shape[0]
    if v.real < x[0]:
        vc = x[0]
    elif v.real > x[K - 1]:
        vc = x[K - 1]
    else:
        vc = v
    i = _bracket(x, vc.real)
    t = (vc - x[i]) * r[i]
    yi = y[i]
    return yi + t * (y[i + 1] - yi)


@njit(inline="always", **JIT)
def lk2(x, rx, yg, ry, z, u, v):
    Kx = x.shape[0]
    Ky = yg.shape[0]
    if u.real < x[0]:
        uc = x[0]
    elif u.real > x[Kx - 1]:
        uc = x[Kx - 1]
    else:
        uc = u
    i = _bracket(x, uc.real)
    tx = (uc - x[i]) * rx[i]
    if v.real < yg[0]:
        vc = yg[0]
    elif v.real > yg[Ky - 1]:
        vc = yg[Ky - 1]
    else:
        vc = v
    j = _bracket(yg, vc.real)
    ty = (vc - yg[j]) * ry[j]
    z00 = z[i, j]
    z10 = z[i + 1, j]
    z01 = z[i, j + 1]
    z11 = z[i + 1, j + 1]
    a = z00 + tx * (z10 - z00)
    b = z01 + tx * (z11 - z01)
    return a + ty * (b - a)


@njit(inline="always", **JIT)
def _deriv(
    n1, n2, wf, ps3, t5, tm, P, eta_hp, eta_lp, T, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq
):
    n1c = n1 / n1den
    n2c = n2 / n2den
    wfc_ = wf / dsth
    g = wfc_ * eta_hp
    qhp = delta * (lk2(T.qhp_x, T.qhp_rx, T.qhp_y, T.qhp_ry, T.qhp_z, n2c, g) - P[P_K_CLR] * (t5 - tm))
    qlp = delta * (lk2(T.qlp_x, T.qlp_rx, T.qlp_y, T.qlp_ry, T.qlp_z, n1c, n2c * eta_lp) - P[P_QD_REF] * dq)
    d_n1 = qlp / P[P_I_LP]
    d_n2 = qhp / P[P_I_HP]
    d_wf = (wf_dem - wf) / P[P_TAU_ACT]
    d_ps3 = (p2 * lk1(T.psr_x, T.psr_r, T.psr_y, n2c) - ps3) / P[P_TAU_V]
    w = dosth * lk1(T.wc_x, T.wc_r, T.wc_y, n1c)
    taug = P[P_TAU_G_REF] * (w / P[P_W_REF]) ** P[P_W_EXP]
    t5ss = tha * lk2(T.t5_x, T.t5_rx, T.t5_y, T.t5_ry, T.t5_z, n2c, g)
    d_t5 = (t5ss - t5) / taug
    d_tm = (t5 - tm) / P[P_TAU_M]
    return d_n1, d_n2, d_wf, d_ps3, d_t5, d_tm


@njit(**JIT)
def _advance(x, s, P, eta_hp, eta_lp, T, inp, nz, out, selo):
    """Advance one unit in place over len(inp) truth steps; x[NX], s[NS] are updated at the end."""
    n1, n2, wf, ps3, t5, tm = x[0], x[1], x[2], x[3], x[4], x[5]
    xi, df, dq, wfc = x[6], x[7], x[8], x[9]
    k = s[0]
    sel_s = s[1]
    KP, KI, K_N1, K_T5 = P[P_KP], P[P_KI], P[P_K_N1], P[P_K_T5]
    ACC_SCALE, DEC_SCALE, A_EXP = P[P_ACC_SCALE], P[P_DEC_SCALE], P[P_A_EXP]
    PHI_F, S_F, PHI_Q, S_Q = P[P_PHI_F], P[P_S_F], P[P_PHI_Q], P[P_S_Q]
    OM1, OM2, N1MAX_C, T5MAX, WF_MIN = P[P_OM1], P[P_OM2], P[P_N1MAX_C], P[P_T5MAX], P[P_WF_MIN]
    for st in range(inp.shape[0]):
        pla = inp[st, 0]
        t2 = inp[st, 1]
        p2 = inp[st, 2]
        theta = t2 / T0
        delta = p2 / P0
        sth = np.sqrt(theta)
        tha = theta**A_EXP
        n1den = sth * OM1
        n2den = sth * OM2
        dsth = delta * sth
        dosth = delta / sth

        df = PHI_F * df + S_F * nz[st, 0]
        dq = PHI_Q * dq + S_Q * nz[st, 1]

        if k % CTRL_DIV == 0:
            n2c = n2 / n2den
            e2 = lk1(T.pla_x, T.pla_r, T.pla_y, pla) * n2den - n2
            wf_gov = KP * e2 + xi
            wf_n1 = wfc + K_N1 * (N1MAX_C * n1den - n1)
            wf_t5 = wfc + K_T5 * (T5MAX - t5)
            wf_acc = ACC_SCALE * lk1(T.acc_x, T.acc_r, T.acc_y, n2c) * ps3
            wf_dec = DEC_SCALE * lk1(T.dec_x, T.dec_r, T.dec_y, n2c) * ps3
            cur = wf_gov
            sel = SEL_GOV
            if wf_n1.real < cur.real:
                cur = wf_n1
                sel = SEL_N1
            if wf_t5.real < cur.real:
                cur = wf_t5
                sel = SEL_T5
            if wf_acc.real < cur.real:
                cur = wf_acc
                sel = SEL_ACC
            if wf_dec.real > cur.real:
                cur = wf_dec
                sel = SEL_DEC
            if WF_MIN.real > cur.real:
                cur = WF_MIN
                sel = SEL_MIN
            if sel == SEL_GOV:
                xi = xi + KI * DTC * e2
            else:
                xi = cur - KP * e2
            wfc = cur
            sel_s = sel

        wf_dem = wfc * (1.0 + df)
        for _ in range(NSUB):
            a1, a2, a3, a4, a5, a6 = _deriv(
                n1,
                n2,
                wf,
                ps3,
                t5,
                tm,
                P,
                eta_hp,
                eta_lp,
                T,
                delta,
                n1den,
                n2den,
                dsth,
                dosth,
                tha,
                p2,
                wf_dem,
                dq,
            )
            b1, b2, b3, b4, b5, b6 = _deriv(
                n1 + H * a1, n2 + H * a2, wf + H * a3, ps3 + H * a4, t5 + H * a5, tm + H * a6,
                P, eta_hp, eta_lp, T, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq,
            )  # fmt: skip
            n1 = n1 + HH * (a1 + b1)
            n2 = n2 + HH * (a2 + b2)
            wf = wf + HH * (a3 + b3)
            ps3 = ps3 + HH * (a4 + b4)
            t5 = t5 + HH * (a5 + b5)
            tm = tm + HH * (a6 + b6)
        k += 1
        out[st, 0] = n1
        out[st, 1] = n2
        out[st, 2] = wf
        out[st, 3] = ps3
        out[st, 4] = t5
        out[st, 5] = tm
        selo[st] = sel_s
    x[0], x[1], x[2], x[3], x[4], x[5] = n1, n2, wf, ps3, t5, tm
    x[6], x[7], x[8], x[9] = xi, df, dq, wfc
    s[0] = k
    s[1] = sel_s


@njit(**JIT)
def step_block(X, S, P, health, T, inputs, noise):
    """One unit, one block. X[NX], S[NS], health[2], inputs[L,3], noise[L,2] -> (X', S', out[L,6], sel[L])."""
    Xo = X.copy()  # float64, or complex128 for complex-step (M5)
    So = S.copy()
    L = inputs.shape[0]
    out = np.empty((L, 6), dtype=X.dtype)
    selo = np.empty(L, dtype=np.int64)
    _advance(Xo, So, P, health[0], health[1], T, inputs, noise, out, selo)
    return Xo, So, out, selo


@njit(parallel=True, **JIT)
def step_block_batch(X, S, P, health, T, inputs, noise):
    """U units, one block, prange over units. X[U,NX], S[U,NS], health[U,2], inputs[U,L,3], noise[U,L,2]."""
    U = X.shape[0]
    L = inputs.shape[1]
    Xo = X.copy()
    So = S.copy()
    out = np.empty((U, L, 6), dtype=X.dtype)
    selo = np.empty((U, L), dtype=np.int64)
    for u in prange(U):
        _advance(Xo[u], So[u], P, health[u, 0], health[u, 1], T, inputs[u], noise[u], out[u], selo[u])
    return Xo, So, out, selo


@njit(**JIT)
def step_block_batch_serial(X, S, P, health, T, inputs, noise):
    """Same as step_block_batch without threads (reference for the batching/threads determinism checks)."""
    U = X.shape[0]
    L = inputs.shape[1]
    Xo = X.copy()
    So = S.copy()
    out = np.empty((U, L, 6), dtype=X.dtype)
    selo = np.empty((U, L), dtype=np.int64)
    for u in range(U):
        _advance(Xo[u], So[u], P, health[u, 0], health[u, 1], T, inputs[u], noise[u], out[u], selo[u])
    return Xo, So, out, selo
