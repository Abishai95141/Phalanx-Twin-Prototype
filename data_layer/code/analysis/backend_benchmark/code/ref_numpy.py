"""NumPy reference implementation of the W0.6 workload (the oracle every backend must match).

Python loop over truth steps, vectorised over lanes (units, or perturbation directions for the complex-step
derivative). dtype-generic: with complex128 parameters/tables it computes complex-step derivatives, so every
comparison and clip acts on the real part (identical results for float64).

Per-lane parameters P[U, NP] and per-lane table values (y: [U, K], z: [U, Kx, Ky]) are accepted so that each lane
can carry its own perturbation; breakpoints and inverse spacings are shared.

Expression order is the contract: the Numba and JAX ports evaluate the same expressions in the same order.
"""

from __future__ import annotations

import numpy as np
import workload as W


def _clip(v, lo, hi):
    return np.where(v.real < lo, lo, np.where(v.real > hi, hi, v))


def _lk1(x, r, y, ar, v):
    """1-D linear lookup with end clamping. x[K], r[K-1] shared; y[U, K] per lane; v[U]."""
    K = x.shape[0]
    vc = _clip(v, x[0], x[K - 1])
    i = np.minimum(np.searchsorted(x, vc.real, side="right") - 1, K - 2)
    t = (vc - x[i]) * r[i]
    yi = y[ar, i]
    return yi + t * (y[ar, i + 1] - yi)


def _lk2(x, rx, yg, ry, z, ar, u, v):
    """2-D bilinear lookup with end clamping on both axes. z[U, Kx, Ky] per lane."""
    Kx, Ky = x.shape[0], yg.shape[0]
    uc = _clip(u, x[0], x[Kx - 1])
    i = np.minimum(np.searchsorted(x, uc.real, side="right") - 1, Kx - 2)
    tx = (uc - x[i]) * rx[i]
    vc = _clip(v, yg[0], yg[Ky - 1])
    j = np.minimum(np.searchsorted(yg, vc.real, side="right") - 1, Ky - 2)
    ty = (vc - yg[j]) * ry[j]
    z00 = z[ar, i, j]
    z10 = z[ar, i + 1, j]
    z01 = z[ar, i, j + 1]
    z11 = z[ar, i + 1, j + 1]
    a = z00 + tx * (z10 - z00)
    b = z01 + tx * (z11 - z01)
    return a + ty * (b - a)


def lane_tables(tables: W.Tables, U: int, dtype=np.float64, override: dict | None = None) -> dict:
    """Broadcast table values to per-lane copies (override: name -> array[U, ...] for perturbed lanes)."""
    d = {}
    for name, a in tables._asdict().items():
        if name.endswith(("_y", "_z")) and name not in ("qhp_y", "qlp_y", "t5_y"):
            d[name] = np.broadcast_to(a.astype(dtype), (U, *a.shape)).copy()
        else:
            d[name] = a
    if override:
        for k, v in override.items():
            d[k] = np.asarray(v)
    return d


def run(X0, S0, P, health, T: dict, inputs, noise):
    """Advance U lanes over L truth steps.

    X0 [U, NX], S0 int64 [U, NS], P [U, NP], health [U, 2], T: lane_tables(...), inputs [U, L, 3],
    noise [U, L, 2]. Returns (X [U, NX], S [U, NS], out [U, L, 6], sel int64 [U, L]).
    """
    U, L = inputs.shape[0], inputs.shape[1]
    ar = np.arange(U)
    X = [X0[:, c].copy() for c in range(W.NX)]
    k = S0[:, W.SK].copy()
    sel_s = S0[:, W.SSEL].copy()
    dtype = np.result_type(X0, P, T["qhp_z"], noise)
    out = np.empty((U, L, W.NOUT), dtype=dtype)
    sel_o = np.empty((U, L), dtype=np.int64)

    p = [P[:, c] for c in range(W.NP)]
    I_LP, I_HP, TAU_ACT, TAU_V = p[W.P_I_LP], p[W.P_I_HP], p[W.P_TAU_ACT], p[W.P_TAU_V]
    TAU_G_REF, W_EXP, TAU_M, K_CLR = p[W.P_TAU_G_REF], p[W.P_W_EXP], p[W.P_TAU_M], p[W.P_K_CLR]
    KP, KI, K_N1, K_T5 = p[W.P_KP], p[W.P_KI], p[W.P_K_N1], p[W.P_K_T5]
    ACC_SCALE, DEC_SCALE, A_EXP, QD_REF = p[W.P_ACC_SCALE], p[W.P_DEC_SCALE], p[W.P_A_EXP], p[W.P_QD_REF]
    PHI_F, S_F, PHI_Q, S_Q = p[W.P_PHI_F], p[W.P_S_F], p[W.P_PHI_Q], p[W.P_S_Q]
    OM1, OM2, N1MAX_C, T5MAX = p[W.P_OMEGA1_100], p[W.P_OMEGA2_100], p[W.P_N1MAX_C], p[W.P_T5MAX]
    WF_MIN, W_REF = p[W.P_WF_MIN], p[W.P_W_REF]
    eta_hp, eta_lp = health[:, 0], health[:, 1]

    def lk1(name, v):
        return _lk1(T[name + "_x"], T[name + "_r"], T[name + "_y"], ar, v)

    def lk2(name, u, v):
        return _lk2(
            T[name + "_x"], T[name + "_rx"], T[name + "_y"], T[name + "_ry"], T[name + "_z"], ar, u, v
        )

    def deriv(x, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq):
        n1, n2, wf, ps3, t5, tm = x
        n1c = n1 / n1den
        n2c = n2 / n2den
        wfc_ = wf / dsth
        g = wfc_ * eta_hp
        qhp = delta * (lk2("qhp", n2c, g) - K_CLR * (t5 - tm))
        qlp = delta * (lk2("qlp", n1c, n2c * eta_lp) - QD_REF * dq)
        d_n1 = qlp / I_LP
        d_n2 = qhp / I_HP
        d_wf = (wf_dem - wf) / TAU_ACT
        d_ps3 = (p2 * lk1("psr", n2c) - ps3) / TAU_V
        w = dosth * lk1("wc", n1c)
        taug = TAU_G_REF * (w / W_REF) ** W_EXP
        t5ss = tha * lk2("t5", n2c, g)
        d_t5 = (t5ss - t5) / taug
        d_tm = (t5 - tm) / TAU_M
        return d_n1, d_n2, d_wf, d_ps3, d_t5, d_tm

    for s in range(L):
        pla = inputs[:, s, W.I_PLA]
        t2 = inputs[:, s, W.I_T2]
        p2 = inputs[:, s, W.I_P2]
        theta = t2 / W.T0
        delta = p2 / W.P0
        sth = np.sqrt(theta)
        tha = theta**A_EXP
        n1den = sth * OM1
        n2den = sth * OM2
        dsth = delta * sth
        dosth = delta / sth

        # process disturbances (AD-32): AR(1) per unit, innovations from keyed blocks
        X[W.DF] = PHI_F * X[W.DF] + S_F * noise[:, s, 0]
        X[W.DQ] = PHI_Q * X[W.DQ] + S_Q * noise[:, s, 1]

        # controller, 60 Hz rate group; MIN/MAX selection with back-calculation anti-windup
        ctrl = (k % W.CTRL_DIV) == 0
        n1, n2, ps3, t5 = X[W.N1], X[W.N2], X[W.PS3], X[W.T5]
        xi, wfc = X[W.XI], X[W.WFC]
        n2c = n2 / n2den
        e2 = lk1("pla", pla) * n2den - n2
        wf_gov = KP * e2 + xi
        wf_n1 = wfc + K_N1 * (N1MAX_C * n1den - n1)
        wf_t5 = wfc + K_T5 * (T5MAX - t5)
        wf_acc = ACC_SCALE * lk1("acc", n2c) * ps3
        wf_dec = DEC_SCALE * lk1("dec", n2c) * ps3
        cur = wf_gov
        sel = np.zeros(U, dtype=np.int64)
        m = wf_n1.real < cur.real
        cur, sel = np.where(m, wf_n1, cur), np.where(m, W.SEL_N1, sel)
        m = wf_t5.real < cur.real
        cur, sel = np.where(m, wf_t5, cur), np.where(m, W.SEL_T5, sel)
        m = wf_acc.real < cur.real
        cur, sel = np.where(m, wf_acc, cur), np.where(m, W.SEL_ACC, sel)
        m = wf_dec.real > cur.real
        cur, sel = np.where(m, wf_dec, cur), np.where(m, W.SEL_DEC, sel)
        m = WF_MIN.real > cur.real
        cur, sel = np.where(m, WF_MIN, cur), np.where(m, W.SEL_MIN, sel)
        xi_new = np.where(sel == W.SEL_GOV, xi + KI * W.DTC * e2, cur - KP * e2)
        X[W.XI] = np.where(ctrl, xi_new, xi)
        X[W.WFC] = np.where(ctrl, cur, wfc)
        sel_s = np.where(ctrl, sel, sel_s)

        # plant: NSUB Heun sub-steps with inputs, command and disturbances held over the truth step
        wf_dem = X[W.WFC] * (1.0 + X[W.DF])
        dq = X[W.DQ]
        x = (X[W.N1], X[W.N2], X[W.WF], X[W.PS3], X[W.T5], X[W.TM])
        for _ in range(W.NSUB):
            k1 = deriv(x, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq)
            xp = tuple(xa + W.H * ka for xa, ka in zip(x, k1, strict=True))
            k2 = deriv(xp, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq)
            x = tuple(xa + W.HH * (ka + kb) for xa, ka, kb in zip(x, k1, k2, strict=True))
        X[W.N1], X[W.N2], X[W.WF], X[W.PS3], X[W.T5], X[W.TM] = x
        k = k + 1
        for c in range(W.NOUT):
            out[:, s, c] = X[c]
        sel_o[:, s] = sel_s

    Xo = np.stack(X, axis=1)
    So = np.stack([k, sel_s], axis=1).astype(np.int64)
    return Xo, So, out, sel_o
