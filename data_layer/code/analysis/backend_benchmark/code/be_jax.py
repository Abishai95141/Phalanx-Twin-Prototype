"""JAX (CPU, float64) backend for the W0.6 workload.

- `step_block(X, S, P, health, T, inputs, noise)`: one unit, one block; `lax.scan` over truth steps inside `jit`.
  The scan carry is a flat tuple of scalars (state arrays are packed/unpacked at the block boundary).
- `step_block_batch`: `vmap` over units (tables and type parameters broadcast).
- `sharded_batch(ndev)`: the vmapped kernel partitioned over `ndev` CPU devices (multi-core JAX on CPU).
- `step_block_rng`: in-loop generation variant (threefry `fold_in(key, k)`), for the RNG question only.
- Branches (controller rate group, MIN/MAX selection, clamps) are `jnp.where` selects: both sides are evaluated.

Expression order follows ref_numpy.py exactly (A1). x64 is enabled at import (JAX defaults to float32).
"""

from __future__ import annotations

import os
from functools import partial

import jax

jax.config.update("jax_enable_x64", True)

import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402
import workload as W  # noqa: E402
from jax import lax  # noqa: E402

T0, P0 = W.T0, W.P0
H, HH, DTC = W.H, W.HH, W.DTC
NSUB, CTRL_DIV = W.NSUB, W.CTRL_DIV


def tables_to_jax(T: W.Tables) -> W.Tables:
    return W.Tables(*[jnp.asarray(a) for a in T])


def _clip(v, lo, hi):
    return jnp.where(v < lo, lo, jnp.where(v > hi, hi, v))


# Bracket search variant (tuning knob, chosen by the M1 tuning sweep; all give the same index):
#   sumcmp: count of interior breakpoints <= v (branch-free compare-all); otherwise jnp.searchsorted(method=...).
BRACKET = os.environ.get("BENCH_JAX_BRACKET", "compare_all")  # fastest in s01_jax_tuning


def _bracket(x, vc):
    """Largest i in [0, K-2] with x[i] <= vc (vc clamped to [x0, x_{K-1}])."""
    if BRACKET == "sumcmp":
        return jnp.sum(x[1:-1] <= vc)
    return jnp.minimum(jnp.searchsorted(x, vc, side="right", method=BRACKET) - 1, x.shape[0] - 2)


def lk1(x, r, y, v):
    K = x.shape[0]
    vc = _clip(v, x[0], x[K - 1])
    i = _bracket(x, vc)
    t = (vc - x[i]) * r[i]
    yi = y[i]
    return yi + t * (y[i + 1] - yi)


def lk2(x, rx, yg, ry, z, u, v):
    Kx, Ky = x.shape[0], yg.shape[0]
    uc = _clip(u, x[0], x[Kx - 1])
    i = _bracket(x, uc)
    tx = (uc - x[i]) * rx[i]
    vc = _clip(v, yg[0], yg[Ky - 1])
    j = _bracket(yg, vc)
    ty = (vc - yg[j]) * ry[j]
    z00 = z[i, j]
    z10 = z[i + 1, j]
    z01 = z[i, j + 1]
    z11 = z[i + 1, j + 1]
    a = z00 + tx * (z10 - z00)
    b = z01 + tx * (z11 - z01)
    return a + ty * (b - a)


def make_step(P, eta_hp, eta_lp, T: W.Tables):
    """Pure per-truth-step function for lax.scan: (carry, (inputs_k, noise_k)) -> (carry', (out_k, sel_k))."""
    I_LP, I_HP, TAU_ACT, TAU_V = P[W.P_I_LP], P[W.P_I_HP], P[W.P_TAU_ACT], P[W.P_TAU_V]
    TAU_G_REF, W_EXP, TAU_M, K_CLR = P[W.P_TAU_G_REF], P[W.P_W_EXP], P[W.P_TAU_M], P[W.P_K_CLR]
    KP, KI, K_N1, K_T5 = P[W.P_KP], P[W.P_KI], P[W.P_K_N1], P[W.P_K_T5]
    ACC_SCALE, DEC_SCALE, A_EXP, QD_REF = P[W.P_ACC_SCALE], P[W.P_DEC_SCALE], P[W.P_A_EXP], P[W.P_QD_REF]
    PHI_F, S_F, PHI_Q, S_Q = P[W.P_PHI_F], P[W.P_S_F], P[W.P_PHI_Q], P[W.P_S_Q]
    OM1, OM2, N1MAX_C, T5MAX = P[W.P_OMEGA1_100], P[W.P_OMEGA2_100], P[W.P_N1MAX_C], P[W.P_T5MAX]
    WF_MIN, W_REF = P[W.P_WF_MIN], P[W.P_W_REF]

    def deriv(n1, n2, wf, ps3, t5, tm, delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq):
        n1c = n1 / n1den
        n2c = n2 / n2den
        wfc_ = wf / dsth
        g = wfc_ * eta_hp
        qhp = delta * (lk2(T.qhp_x, T.qhp_rx, T.qhp_y, T.qhp_ry, T.qhp_z, n2c, g) - K_CLR * (t5 - tm))
        qlp = delta * (lk2(T.qlp_x, T.qlp_rx, T.qlp_y, T.qlp_ry, T.qlp_z, n1c, n2c * eta_lp) - QD_REF * dq)
        d_n1 = qlp / I_LP
        d_n2 = qhp / I_HP
        d_wf = (wf_dem - wf) / TAU_ACT
        d_ps3 = (p2 * lk1(T.psr_x, T.psr_r, T.psr_y, n2c) - ps3) / TAU_V
        w = dosth * lk1(T.wc_x, T.wc_r, T.wc_y, n1c)
        taug = TAU_G_REF * (w / W_REF) ** W_EXP
        t5ss = tha * lk2(T.t5_x, T.t5_rx, T.t5_y, T.t5_ry, T.t5_z, n2c, g)
        d_t5 = (t5ss - t5) / taug
        d_tm = (t5 - tm) / TAU_M
        return d_n1, d_n2, d_wf, d_ps3, d_t5, d_tm

    def step(carry, xs):
        n1, n2, wf, ps3, t5, tm, xi, df, dq, wfc, k, sel_s = carry
        inp, nz = xs
        pla, t2, p2 = inp[0], inp[1], inp[2]
        theta = t2 / T0
        delta = p2 / P0
        sth = jnp.sqrt(theta)
        tha = theta**A_EXP
        n1den = sth * OM1
        n2den = sth * OM2
        dsth = delta * sth
        dosth = delta / sth

        df = PHI_F * df + S_F * nz[0]
        dq = PHI_Q * dq + S_Q * nz[1]

        ctrl = (k % CTRL_DIV) == 0
        n2c = n2 / n2den
        e2 = lk1(T.pla_x, T.pla_r, T.pla_y, pla) * n2den - n2
        wf_gov = KP * e2 + xi
        wf_n1 = wfc + K_N1 * (N1MAX_C * n1den - n1)
        wf_t5 = wfc + K_T5 * (T5MAX - t5)
        wf_acc = ACC_SCALE * lk1(T.acc_x, T.acc_r, T.acc_y, n2c) * ps3
        wf_dec = DEC_SCALE * lk1(T.dec_x, T.dec_r, T.dec_y, n2c) * ps3
        cur = wf_gov
        sel = jnp.zeros((), jnp.int64)
        m = wf_n1 < cur
        cur, sel = jnp.where(m, wf_n1, cur), jnp.where(m, W.SEL_N1, sel)
        m = wf_t5 < cur
        cur, sel = jnp.where(m, wf_t5, cur), jnp.where(m, W.SEL_T5, sel)
        m = wf_acc < cur
        cur, sel = jnp.where(m, wf_acc, cur), jnp.where(m, W.SEL_ACC, sel)
        m = wf_dec > cur
        cur, sel = jnp.where(m, wf_dec, cur), jnp.where(m, W.SEL_DEC, sel)
        m = WF_MIN > cur
        cur, sel = jnp.where(m, WF_MIN, cur), jnp.where(m, W.SEL_MIN, sel)
        xi_new = jnp.where(sel == W.SEL_GOV, xi + KI * DTC * e2, cur - KP * e2)
        xi = jnp.where(ctrl, xi_new, xi)
        wfc = jnp.where(ctrl, cur, wfc)
        sel_s = jnp.where(ctrl, sel, sel_s)

        wf_dem = wfc * (1.0 + df)
        for _ in range(NSUB):
            a1, a2, a3, a4, a5, a6 = deriv(n1, n2, wf, ps3, t5, tm, delta, n1den, n2den, dsth, dosth, tha, p2,
                                           wf_dem, dq)  # fmt: skip
            b1, b2, b3, b4, b5, b6 = deriv(
                n1 + H * a1, n2 + H * a2, wf + H * a3, ps3 + H * a4, t5 + H * a5, tm + H * a6,
                delta, n1den, n2den, dsth, dosth, tha, p2, wf_dem, dq,
            )  # fmt: skip
            n1 = n1 + HH * (a1 + b1)
            n2 = n2 + HH * (a2 + b2)
            wf = wf + HH * (a3 + b3)
            ps3 = ps3 + HH * (a4 + b4)
            t5 = t5 + HH * (a5 + b5)
            tm = tm + HH * (a6 + b6)
        k = k + 1
        out = jnp.stack([n1, n2, wf, ps3, t5, tm])
        return (n1, n2, wf, ps3, t5, tm, xi, df, dq, wfc, k, sel_s), (out, sel_s)

    return step


def _block(X, S, P, health, T, inputs, noise, unroll=1):
    carry0 = (*(X[i] for i in range(W.NX)), S[0], S[1])
    step = make_step(P, health[0], health[1], T)
    carry, (out, sel) = lax.scan(step, carry0, (inputs, noise), unroll=unroll)
    return jnp.stack(carry[: W.NX]), jnp.stack(carry[W.NX :]), out, sel


def _batch(X, S, P, health, T, inputs, noise, unroll=1):
    def one(x, s, h, i, n):
        return _block(x, s, P, h, T, i, n, unroll)

    return jax.vmap(one)(X, S, health, inputs, noise)


step_block = jax.jit(_block, static_argnames=("unroll",))
step_block_batch = jax.jit(_batch, static_argnames=("unroll",))


def sharded_batch(ndev: int, unroll: int = 1):
    """Batch kernel partitioned over the first `ndev` CPU devices along the unit axis (SPMD)."""
    from jax.sharding import Mesh, NamedSharding
    from jax.sharding import PartitionSpec as PS

    mesh = Mesh(np.array(jax.devices()[:ndev]), ("u",))
    su = NamedSharding(mesh, PS("u"))
    rep = NamedSharding(mesh, PS())
    f = jax.jit(
        partial(_batch, unroll=unroll),
        in_shardings=(su, su, rep, su, rep, su, su),
        out_shardings=(su, su, su, su),
    )
    return f, su, rep


# ---------------------------------------------------------------- in-loop RNG variant (RNG question only)
def _block_rng(X, S, P, health, T, inputs, key_data, unroll=1):
    """Innovations generated in the loop: normal(fold_in(key, k)) per truth step k (counter-based, keyed).

    key_data: uint32[2] raw threefry key derived from the unit's SeedSequence (rngblocks.jax_key_data)."""
    key = jax.random.wrap_key_data(key_data, impl="threefry2x32")
    carry0 = (*(X[i] for i in range(W.NX)), S[0], S[1])
    step = make_step(P, health[0], health[1], T)

    def step_rng(carry, inp):
        nz = jax.random.normal(jax.random.fold_in(key, carry[W.NX]), (2,), dtype=jnp.float64)
        return step(carry, (inp, nz))

    carry, (out, sel) = lax.scan(step_rng, carry0, inputs, unroll=unroll)
    return jnp.stack(carry[: W.NX]), jnp.stack(carry[W.NX :]), out, sel


def _batch_rng(X, S, P, health, T, inputs, key_data, unroll=1):
    def one(x, s, h, i, kd):
        return _block_rng(x, s, P, h, T, i, kd, unroll)

    return jax.vmap(one)(X, S, health, inputs, key_data)


step_block_rng = jax.jit(_block_rng, static_argnames=("unroll",))
step_block_rng_batch = jax.jit(_batch_rng, static_argnames=("unroll",))
