"""M5 machinery: transient-weighted output-error residuals (AD-34) and their Jacobian by several methods.

Problem (fixed): one unit, a 60 s transient window at a fixed flight condition with throttle slams and chops
(accel and decel schedules engage), keyed disturbance realisation held fixed. Residuals are the outputs N1, N2,
Wf, T5 at 10 Hz (every 24th truth step), scaled, minus "observed" outputs from the true parameters, weighted by
1 + 4 x [within 5 s after a PLA move > 5 deg] (transient weighting). Jacobian taken at a perturbed parameter
vector theta0 = theta* (1 + 0.05 u), u keyed uniform(-1, 1).

Parameter sets: n30 = 10 dynamic scalars + accel (10) + decel (10) Wf/PS3 schedule values;
               n240 = n30 + the HP torque map (15 x 14 = 210 entries).

Methods: complex-step on the NumPy reference (accuracy reference, all directions as lanes), Numba forward / central
FD and complex step (same kernel, complex128 specialisation), JAX jacfwd and grad.
"""

from __future__ import annotations

import numpy as np
import rngblocks as R
import workload as W

STEPS = 14_400  # 60 s
DEC = 24  # 10 Hz residual sampling
CH = [0, 1, 2, 4]  # N1, N2, Wf, T5
SCALAR_NAMES = ["I_LP", "I_HP", "TAU_ACT", "TAU_V", "TAU_G_REF", "W_EXP", "TAU_M", "K_CLR", "KP", "KI"]
SCALAR_IDX = np.array([W.PNAMES.index(n) for n in SCALAR_NAMES])


def pla_profile():
    t = np.array([0, 5, 5.4, 20, 20.5, 35, 35.3, 45, 45.3, 60, 61.0])
    p = np.array([40, 40, 87, 87, 22, 22, 70, 70, 30, 30, 30.0])
    return t, p


class Problem:
    def __init__(self, nparam: int = 30):
        assert nparam in (30, 240)
        self.n = nparam
        self.P = W.default_params()
        self.T = W.make_tables()
        tp, pp = pla_profile()
        m = W.Mission(tp, pp, np.full(tp.size, 2000.0), np.full(tp.size, 0.6), 10.0)
        self.inputs = W.mission_inputs(m, 0, STEPS)
        self.noise = R.noise_for([0], 0, STEPS, W.BLOCK)[0]
        self.health = np.array([1.0, 1.0])
        X0, S0 = W.initial_state(self.inputs[:1], self.health[None], self.P, self.T)
        self.X0, self.S0 = X0[0], S0[0]
        self.theta_star = self.pack(self.P, self.T)
        u = R.generator(("bench", "M5", "theta0")).uniform(-1.0, 1.0, self.n)
        self.theta0 = self.theta_star * (1.0 + 0.05 * u)
        om = self.P
        self.scales = np.array([om[W.P_OMEGA1_100], om[W.P_OMEGA2_100], 1.0, 100.0])
        pla = self.inputs[:, W.I_PLA]
        moved = np.abs(np.diff(pla, prepend=pla[0])) > 0
        k_move = np.flatnonzero(moved)
        trans = np.zeros(STEPS, bool)
        for k in k_move:
            trans[k : k + 5 * W.TRUTH_HZ] = True
        self.weights = (1.0 + 4.0 * trans[DEC - 1 :: DEC])[:, None]
        self.y_obs = None  # set by caller from a float64 run at theta_star

    # ---------------------------------------------------------------- theta <-> (P, tables)
    def pack(self, P, T) -> np.ndarray:
        parts = [P[SCALAR_IDX], T.acc_y, T.dec_y]
        if self.n == 240:
            parts.append(T.qhp_z.ravel())
        return np.concatenate(parts).astype(np.float64)

    def unpack_np(self, theta):
        """theta [n] (float64 or complex128) -> (P, Tables) in NumPy (dtype of theta)."""
        dt = theta.dtype
        P = self.P.astype(dt)
        P[SCALAR_IDX] = theta[:10]
        rep = {"acc_y": theta[10:20], "dec_y": theta[20:30]}
        if self.n == 240:
            rep["qhp_z"] = theta[30:].reshape(self.T.qhp_z.shape)
        T = self.T._replace(**rep)
        if dt == np.complex128:  # one Numba specialisation: all value arrays complex
            T = T._replace(**{k: np.asarray(v, dt) for k, v in T._asdict().items() if k.endswith(("_y", "_z"))
                              and k not in ("qhp_y", "qlp_y", "t5_y")})  # fmt: skip
        return P, T

    def residual_from_out(self, out):
        y = out[DEC - 1 :: DEC][:, CH] / self.scales
        return ((y - self.y_obs) * self.weights).ravel()

    def set_obs_from(self, out_star):
        self.y_obs = out_star[DEC - 1 :: DEC][:, CH] / self.scales

    @property
    def m(self) -> int:
        return (STEPS // DEC) * len(CH)


# ---------------------------------------------------------------- reference: complex step on the NumPy reference
def jac_complex_step_numpy(pb: Problem, theta, h: float = 1e-30, chunk: int = 64):
    """J[m, n] = Im r(theta + i h e_j) / h, all directions as lanes of the vectorised reference (chunked)."""
    import ref_numpy as ref

    n = theta.size
    J = np.empty((pb.m, n))
    r0 = None
    for c0 in range(0, n, chunk):
        cols = list(range(c0, min(n, c0 + chunk)))
        U = len(cols)
        th = np.broadcast_to(theta.astype(np.complex128), (U, n)).copy()
        th[np.arange(U), cols] += 1j * h
        Pl = np.empty((U, W.NP), np.complex128)
        Tl = ref.lane_tables(pb.T, U, np.complex128)
        for ui in range(U):
            P, T = pb.unpack_np(th[ui])
            Pl[ui] = P
            Tl["acc_y"][ui], Tl["dec_y"][ui] = T.acc_y, T.dec_y
            if pb.n == 240:
                Tl["qhp_z"][ui] = T.qhp_z
        X0 = np.broadcast_to(pb.X0, (U, W.NX)).astype(np.complex128)
        S0 = np.broadcast_to(pb.S0, (U, W.NS)).copy()
        H = np.broadcast_to(pb.health, (U, 2)).copy()
        _, _, out, _ = ref.run(X0, S0, Pl, H, Tl, np.broadcast_to(pb.inputs, (U, *pb.inputs.shape)),
                               np.broadcast_to(pb.noise, (U, *pb.noise.shape)))  # fmt: skip
        for ui, j in enumerate(cols):
            J[:, j] = pb.residual_from_out(out[ui]).imag / h
        if r0 is None:
            r0 = pb.residual_from_out(out[0]).real
    return J, r0


def col_rel_err(J, Jref):
    num = np.max(np.abs(J - Jref), axis=0)
    den = np.max(np.abs(Jref), axis=0)
    return np.where(den > 0, num / np.where(den > 0, den, 1.0), num)


def summarize_err(J, Jref, g=None, gref=None) -> dict:
    e = col_rel_err(J, Jref)
    d = {
        "col_rel_err_median": float(np.median(e)),
        "col_rel_err_p95": float(np.percentile(e, 95)),
        "col_rel_err_max": float(e.max()),
        "frac_cols_le_1e-6": float(np.mean(e <= 1e-6)),
        "frac_cols_le_1e-9": float(np.mean(e <= 1e-9)),
        "worst_cols": [int(i) for i in np.argsort(e)[::-1][:5]],
    }
    if g is not None:
        d["grad_rel_err"] = float(np.linalg.norm(g - gref) / np.linalg.norm(gref))
    return d
