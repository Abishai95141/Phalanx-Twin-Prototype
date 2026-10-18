"""Scenario construction and the block runner shared by every measurement.

The runner mirrors the build's kernel loop: for each block, the feeding layer (NumPy) builds the exogenous inputs
and draws the keyed innovation blocks; the compiled `step_block` advances the state; outputs are hashed per unit
in time order (so a unit's digest is independent of batching and block length).
"""

from __future__ import annotations

import hashlib

import numpy as np
import rngblocks as R
import workload as W
from common import Digest, cpu_s, now


class StreamDigest:
    """Digest of one unit's output stream that does not depend on how the stream was cut into blocks:
    raw little-endian bytes of the float outputs (time-major, 6 channels) and of the int64 limiter codes,
    hashed separately and combined at the end."""

    def __init__(self):
        self.o = hashlib.blake2b(digest_size=16)
        self.s = hashlib.blake2b(digest_size=16)

    def update(self, out, sel):
        self.o.update(np.ascontiguousarray(out, dtype="<f8").tobytes())
        self.s.update(np.ascontiguousarray(sel, dtype="<i8").tobytes())

    def hex(self) -> str:
        return hashlib.blake2b(self.o.digest() + self.s.digest(), digest_size=16).hexdigest()


class Scenario:
    def __init__(self, units, kind: str, horizon_steps: int):
        self.units = list(units)
        self.kind = kind
        self.horizon_steps = horizon_steps
        self.P = W.default_params()
        self.T = W.make_tables()
        hs = horizon_steps / W.TRUTH_HZ
        self.missions = [
            W.make_mission(R.generator((*R.unit_key(u), "M02.mission")), kind, hs) for u in self.units
        ]
        self.health = np.stack(
            [W.draw_health(R.generator((*R.unit_key(u), "M10.health"))) for u in self.units]
        )
        inp0 = np.stack([W.mission_inputs(m, 0, 1)[0] for m in self.missions])
        self.X0, self.S0 = W.initial_state(inp0, self.health, self.P, self.T)

    @property
    def U(self) -> int:
        return len(self.units)

    def inputs(self, k0: int, n: int) -> np.ndarray:
        return np.stack([W.mission_inputs(m, k0, n) for m in self.missions])

    def noise(self, k0: int, n: int) -> np.ndarray:
        return R.noise_for(self.units, k0, n, W.BLOCK)

    def subset(self, idx) -> Scenario:
        s = object.__new__(Scenario)
        s.units = [self.units[i] for i in idx]
        s.kind, s.horizon_steps, s.P, s.T = self.kind, self.horizon_steps, self.P, self.T
        s.missions = [self.missions[i] for i in idx]
        s.health = self.health[idx]
        s.X0, s.S0 = self.X0[idx], self.S0[idx]
        return s


# ---------------------------------------------------------------- backend adapters: f(X, S, inp, nz) -> (X, S, out, sel)
def make_backend(name: str, scen: Scenario, mode: str = "auto", **opt):
    P, T, health = scen.P, scen.T, scen.health
    if name == "numpy":
        import ref_numpy as ref

        Pl = np.broadcast_to(P, (scen.U, W.NP)).copy()
        Tl = ref.lane_tables(T, scen.U)

        def f(X, S, inp, nz):
            return ref.run(X, S, Pl, health, Tl, inp, nz)

        return f

    if name == "numba":
        import be_numba as nb

        if mode == "auto":
            mode = "single" if scen.U == 1 else "prange"
        if mode == "single":
            assert scen.U == 1

            def f(X, S, inp, nz):
                x, s, o, sl = nb.step_block(X[0], S[0], P, health[0], T, inp[0], nz[0])
                return x[None], s[None], o[None], sl[None]

            return f
        kern = {"prange": nb.step_block_batch, "serial": nb.step_block_batch_serial}[mode]

        def f(X, S, inp, nz):
            return kern(X, S, P, health, T, inp, nz)

        return f

    if name == "jax":
        import be_jax as bj
        import jax

        unroll = int(opt.get("unroll", 1))
        if mode == "auto":
            mode = "single" if scen.U == 1 else "vmap"
        Pj, Tj = jax.numpy.asarray(P), bj.tables_to_jax(T)
        if mode == "single":
            assert scen.U == 1
            hj = jax.numpy.asarray(health[0])

            def f(X, S, inp, nz):
                x, s, o, sl = bj.step_block(X[0], S[0], Pj, hj, Tj, inp[0], nz[0], unroll=unroll)
                return np.asarray(x)[None], np.asarray(s)[None], np.asarray(o)[None], np.asarray(sl)[None]

            return f
        if mode == "vmap":
            hj = jax.numpy.asarray(health)

            def f(X, S, inp, nz):
                r = bj.step_block_batch(X, S, Pj, hj, Tj, inp, nz, unroll=unroll)
                return tuple(np.asarray(a) for a in r)

            return f
        if mode == "sharded":
            ndev = int(opt["ndev"])
            kern, su, rep = bj.sharded_batch(ndev, unroll)
            hj = jax.device_put(health, su)
            Pr = jax.device_put(P, rep)
            Tr = jax.device_put(Tj, rep)

            def f(X, S, inp, nz):
                a = [jax.device_put(v, su) for v in (X, S, inp, nz)]
                r = kern(a[0], a[1], Pr, hj, Tr, a[2], a[3])
                return tuple(np.asarray(v) for v in r)

            return f
        raise ValueError(mode)
    raise ValueError(name)


def run(
    f, scen: Scenario, k0: int, n_steps: int, L: int, X=None, S=None, keep: bool = False, keep_every: int = 1
):
    """Advance from step k0 for n_steps in kernel blocks of L steps.

    Returns dict: X, S, per-unit digests, timings (feed / kernel / total wall, CPU), optional kept outputs.
    """
    X = scen.X0.copy() if X is None else X
    S = scen.S0.copy() if S is None else S
    dig = [StreamDigest() for _ in range(scen.U)]
    kept_o, kept_s = [], []
    t_feed = t_kern = 0.0
    c0, w0 = cpu_s(), now()
    k = k0
    while k < k0 + n_steps:
        n = min(L, k0 + n_steps - k)
        t = now()
        inp = scen.inputs(k, n)
        nz = scen.noise(k, n)
        t1 = now()
        X, S, out, sel = f(X, S, inp, nz)
        t2 = now()
        t_feed += t1 - t
        t_kern += t2 - t1
        for u in range(scen.U):
            dig[u].update(out[u], sel[u])
        if keep:
            kept_o.append(out[:, ::keep_every].copy())
            kept_s.append(sel[:, ::keep_every].copy())
        k += n
    res = {
        "X": X,
        "S": S,
        "digests": [d.hex() for d in dig],
        "t_feed": t_feed,
        "t_kernel": t_kern,
        "t_wall": now() - w0,
        "t_cpu": cpu_s() - c0,
    }
    if keep:
        res["out"] = np.concatenate(kept_o, axis=1)
        res["sel"] = np.concatenate(kept_s, axis=1)
    return res


def state_digest(X, S) -> str:
    return Digest().update(X, S).hex()
