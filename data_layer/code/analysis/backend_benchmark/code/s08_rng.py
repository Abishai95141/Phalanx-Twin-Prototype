"""RNG question: can RNG stay backend-independent by feeding pre-generated keyed Philox blocks?

  R1 feed cost: keyed block generation (SeedSequence(root, spawn_key) -> Philox -> standard_normal, 2,400 x 2)
     per block and per unit-hour; share of the M1 kernel time (5 reps).
  R2 Numba in-loop: a NumPy Generator(Philox) passed into @njit, standard_normal() per draw. Same stream as the
     pre-generated block? (bitwise) Cost vs feeding. Generator state after the loop == NumPy's after the block?
  R3 Numba kernel with in-kernel block generation vs block-fed kernel: identical outputs? (60 s, 1 unit)
  R4 JAX in-loop threefry (normal(fold_in(key, k))): cost per step vs fed; deterministic single vs vmap; the
     stream necessarily differs from NumPy's (different generator and normal transform) -> backend-specific.

Usage: python -I code/s08_rng.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import rngblocks as R
import workload as W
from common import digest, machine_info, now, save_json, stats

REPS = 5


def _state_eq(a, b) -> bool:
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_state_eq(a[k], b[k]) for k in a)
    return bool(np.array_equal(a, b))


def r1_feed():
    key = R.disturbance_key(0)
    ts = []
    for _ in range(REPS):
        t0 = now()
        for b in range(36):  # 6 minutes of blocks
            R.normal_block(key, b, (W.BLOCK, 2))
        ts.append((now() - t0) / 36)
    per_block = stats(ts)
    # split: SeedSequence/Philox construction vs drawing
    tc = []
    for _ in range(REPS):
        t0 = now()
        for b in range(36):
            R.generator(key, b)
        tc.append((now() - t0) / 36)
    return {"per_block_s": per_block, "construct_per_block_s": stats(tc),
            "per_unit_hour_s": per_block["median"] * 360, "block_steps": W.BLOCK,
            "block_bytes": W.BLOCK * 2 * 8}  # fmt: skip


def r2_r3_numba():
    import be_numba as nb
    import harness as Hn
    from numba import njit

    @njit(cache=False)
    def fill(gen, L):
        out = np.empty((L, 2))
        for i in range(L):
            out[i, 0] = gen.standard_normal()
            out[i, 1] = gen.standard_normal()
        return out

    key = R.disturbance_key(0)
    g_np = R.generator(key, 7)
    ref = g_np.standard_normal((W.BLOCK, 2))
    g_nb = R.generator(key, 7)
    t0 = now()
    got = fill(g_nb, W.BLOCK)
    t_compile = now() - t0
    same_stream = bool(np.array_equal(ref, got))
    same_state = _state_eq(g_np.bit_generator.state, g_nb.bit_generator.state)
    ts = []
    for _ in range(REPS):
        g = R.generator(key, 7)
        t0 = now()
        fill(g, W.BLOCK)
        ts.append(now() - t0)
    tn = []
    for _ in range(REPS):
        g = R.generator(key, 7)
        t0 = now()
        g.standard_normal((W.BLOCK, 2))
        tn.append(now() - t0)

    @njit(cache=False)
    def block_ingen(X, S, P, health, T, inputs, gen):
        L = inputs.shape[0]
        nz = np.empty((L, 2))
        for i in range(L):
            nz[i, 0] = gen.standard_normal()
            nz[i, 1] = gen.standard_normal()
        return nb.step_block(X, S, P, health, T, inputs, nz)

    sc = Hn.Scenario([0], "combat", 14_400)
    fed = Hn.run(Hn.make_backend("numba", sc, "single"), sc, 0, 14_400, W.BLOCK, keep=True)
    X, S = sc.X0[0].copy(), sc.S0[0].copy()
    outs, sels = [], []
    for b in range(6):
        g = R.generator(R.disturbance_key(0), b)
        X, S, o, s = block_ingen(X, S, sc.P, sc.health[0], sc.T, sc.inputs(b * W.BLOCK, W.BLOCK)[0], g)
        outs.append(o)
        sels.append(s)
    same_out = bool(np.array_equal(np.concatenate(outs), fed["out"][0]) and np.array_equal(np.concatenate(sels),
                                                                                        fed["sel"][0]))  # fmt: skip
    return {
        "R2_numba_generator_same_stream_as_numpy_block": same_stream,
        "R2_generator_state_after_equal": bool(same_state),
        "R2_numba_inloop_fill_s": stats(ts),
        "R2_numpy_block_fill_s": stats(tn),
        "R2_compile_s": t_compile,
        "R3_ingen_kernel_outputs_equal_fed": same_out,
    }


def r4_jax():
    import jax

    jax.config.update("jax_enable_x64", True)
    import be_jax as bj
    import harness as Hn
    import jax.numpy as jnp

    sc = Hn.Scenario(range(10), "combat", 14_400)
    Pj, Tj = jnp.asarray(sc.P), bj.tables_to_jax(sc.T)
    # keyed threefry key per unit, derived from the unit's SeedSequence (no seed arithmetic)
    kd = np.stack([np.random.SeedSequence(R.ROOT_SEED, spawn_key=R.spawn_key(R.disturbance_key(u)))
                   .generate_state(2, np.uint32) for u in range(10)])  # fmt: skip
    inp = sc.inputs(0, W.BLOCK)
    nz = sc.noise(0, W.BLOCK)
    X, S, H = sc.X0, sc.S0, sc.health

    def t_single(fn, *args):
        jax.block_until_ready(fn(*args))
        ts = []
        for _ in range(REPS):
            t0 = now()
            jax.block_until_ready(fn(*args))
            ts.append(now() - t0)
        return stats(ts)

    fed = t_single(lambda: bj.step_block(X[0], S[0], Pj, H[0], Tj, inp[0], nz[0], unroll=4))
    ing = t_single(lambda: bj.step_block_rng(X[0], S[0], Pj, H[0], Tj, inp[0], kd[0], unroll=4))
    singles = [
        np.asarray(bj.step_block_rng(X[u], S[u], Pj, H[u], Tj, inp[u], kd[u], unroll=4)[2]) for u in range(10)
    ]
    batch = np.asarray(bj.step_block_rng_batch(X, S, Pj, H, Tj, inp, kd, unroll=4)[2])
    same = all(np.array_equal(singles[u], batch[u]) for u in range(10))
    return {
        "R4_jax_fed_block_s": fed,
        "R4_jax_inloop_threefry_block_s": ing,
        "R4_inloop_single_vs_vmap_equal": bool(same),
        "R4_inloop_stream_digest_unit0": digest(singles[0]),
        "R4_note": "threefry + erf-inverse normals: a different stream from NumPy Philox + ziggurat by construction",
    }


def main():
    res = {"machine": machine_info(), "reps": REPS}
    res["R1"] = r1_feed()
    print("R1", res["R1"]["per_block_s"]["median"], file=sys.stderr)
    res.update(r2_r3_numba())
    print({k: v for k, v in res.items() if k.startswith("R2_numba") or k.startswith("R3")}, file=sys.stderr)
    res.update(r4_jax())
    print({k: v for k, v in res.items() if k.startswith("R4_inloop")}, file=sys.stderr)
    save_json("rng.json", res)


if __name__ == "__main__":
    main()
