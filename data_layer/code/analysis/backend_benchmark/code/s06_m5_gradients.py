"""M5: Jacobian / gradient for transient-weighted identification (AD-34), accuracy and wall time per method.

Each method family runs in its own process (peak RSS per configuration, M6):
  cs_ref : complex step on the NumPy reference (accuracy reference; saved to _cache/m5_Jref_n<n>.npz)
  numba  : forward FD, central FD, complex step (same @njit kernel, complex128 specialisation);
           serial and 4 threads (ThreadPoolExecutor over columns; the kernels release the GIL)
  jax_*  : forward_sim, jacfwd (forward mode, all columns), grad of 0.5||r||^2 (reverse mode); jit-compiled,
           one process each
Repetitions: 5 timed repetitions after one warm-up (compile) call; NumPy CS once (it is the reference).

Usage: python -I code/s06_m5_gradients.py [30|240]          (driver)
       python -I code/s06_m5_gradients.py --method numba 30 (one family, prints JSON)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradlib as G
import numpy as np
from common import CACHE, PY, RESULTS, cpu_s, machine_info, now, peak_rss_mb, save_json, stats

REPS = 5
THREADS = 4
EPS = np.finfo(np.float64).eps


def _problem(n):
    import be_numba as nb

    pb = G.Problem(n)
    _, _, out, _ = nb.step_block(pb.X0, pb.S0, pb.P, pb.health, pb.T, pb.inputs, pb.noise)
    pb.set_obs_from(out)
    return pb


def _timeit(fn, reps=REPS):
    fn()  # warm-up / compile
    ts, cs = [], []
    res = None
    for _ in range(reps):
        c0, t0 = cpu_s(), now()
        res = fn()
        ts.append(now() - t0)
        cs.append(cpu_s() - c0)
    return res, stats(ts), stats(cs)


def method_cs_ref(n):
    pb = _problem(n)
    t0 = now()
    J, r0 = G.jac_complex_step_numpy(pb, pb.theta0)
    t = now() - t0
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / f"m5_Jref_n{n}.npz", J=J, r0=r0)
    g = J.T @ r0
    return {"method": "cs_numpy_reference", "n": n, "m": pb.m, "t_wall_once": t, "grad_norm": float(np.linalg.norm(g)),
            "J_colnorm_min": float(np.abs(J).max(axis=0).min())}  # fmt: skip


def _load_ref(n):
    z = np.load(CACHE / f"m5_Jref_n{n}.npz")
    return z["J"], z["r0"]


def method_numba(n):
    from concurrent.futures import ThreadPoolExecutor

    import be_numba as nb

    pb = _problem(n)
    Jref, rref = _load_ref(n)
    gref = Jref.T @ rref
    theta0 = pb.theta0

    def resid(theta):
        P, T = pb.unpack_np(theta)
        X0 = pb.X0.astype(theta.dtype)
        _, _, out, sel = nb.step_block(X0, pb.S0, P, pb.health, T, pb.inputs, pb.noise)
        return pb.residual_from_out(out), sel

    r0, sel0 = resid(theta0)
    res = {"n": n, "m": pb.m, "r0_vs_ref_maxabs": float(np.max(np.abs(r0 - rref)))}

    def fwd():
        return resid(theta0)[0]

    _, ts, _ = _timeit(fwd)
    res["forward_sim"] = ts

    def jac(kind, workers):
        def col(j):
            if kind == "fd_fwd":
                h = np.sqrt(EPS) * max(abs(theta0[j]), 1e-300)
                th = theta0.copy()
                th[j] += h
                r, sel = resid(th)
                return (r - r0) / h, int(np.sum(sel != sel0))
            if kind == "fd_central":
                h = EPS ** (1 / 3) * max(abs(theta0[j]), 1e-300)
                a, b = theta0.copy(), theta0.copy()
                a[j] += h
                b[j] -= h
                ra, sa = resid(a)
                rb, sb = resid(b)
                return (ra - rb) / (2 * h), int(np.sum(sa != sel0) + np.sum(sb != sel0))
            if kind == "cs":
                h = 1e-30
                th = theta0.astype(np.complex128)
                th[j] += 1j * h
                r, sel = resid(th)
                return r.imag / h, int(np.sum(sel != sel0))
            raise ValueError(kind)

        def run():
            if workers == 1:
                cols = [col(j) for j in range(n)]
            else:
                with ThreadPoolExecutor(workers) as ex:
                    cols = list(ex.map(col, range(n)))
            return np.stack([c[0] for c in cols], axis=1), sum(c[1] for c in cols)

        return run

    for kind in ("fd_fwd", "fd_central", "cs"):
        for workers in (1, THREADS):
            (J, flips), ts, cs = _timeit(jac(kind, workers))
            res[f"{kind}_w{workers}"] = {"time": ts, "cpu": cs, "sel_flips_vs_base": flips,
                                         **G.summarize_err(J, Jref, J.T @ r0, gref)}  # fmt: skip
            print(kind, workers, ts["median"], res[f"{kind}_w{workers}"]["col_rel_err_max"], file=sys.stderr)
    return res


def method_jax(n, which=("forward_sim", "jacfwd", "grad")):
    import be_jax as bj
    import jax
    import jax.numpy as jnp

    pb = _problem(n)
    Jref, rref = _load_ref(n)
    gref = Jref.T @ rref
    Pj = jnp.asarray(pb.P)
    Tj = bj.tables_to_jax(pb.T)
    X0, S0, h = jnp.asarray(pb.X0), jnp.asarray(pb.S0), jnp.asarray(pb.health)
    inp, nz = jnp.asarray(pb.inputs), jnp.asarray(pb.noise)
    yobs, wts, scales = jnp.asarray(pb.y_obs), jnp.asarray(pb.weights), jnp.asarray(pb.scales)
    sidx = jnp.asarray(G.SCALAR_IDX)
    qshape = pb.T.qhp_z.shape
    unroll = int(os.environ.get("BENCH_JAX_UNROLL", "4"))

    def r_fn(theta):
        P = Pj.at[sidx].set(theta[:10])
        rep = {"acc_y": theta[10:20], "dec_y": theta[20:30]}
        if n == 240:
            rep["qhp_z"] = theta[30:].reshape(qshape)
        T = Tj._replace(**rep)
        _, _, out, _ = bj._block(X0, S0, P, h, T, inp, nz, unroll)
        y = out[G.DEC - 1 :: G.DEC][:, jnp.asarray(G.CH)] / scales
        return ((y - yobs) * wts).ravel()

    th0 = jnp.asarray(pb.theta0)
    r_j = jax.jit(r_fn)
    jacf = jax.jit(jax.jacfwd(r_fn))
    grad = jax.jit(jax.grad(lambda t: 0.5 * jnp.sum(r_fn(t) ** 2)))
    res = {"n": n, "m": pb.m, "unroll": unroll}
    fns = {"forward_sim": r_j, "jacfwd": jacf, "grad": grad}
    for name in which:
        fn = fns[name]
        t0 = now()
        v = fn(th0)
        jax.block_until_ready(v)
        t_compile = now() - t0
        out, ts, cs = _timeit(lambda fn=fn: jax.block_until_ready(fn(th0)))
        out = np.asarray(out)
        d = {"t_first_call_compile": t_compile, "time": ts, "cpu": cs}
        if name == "forward_sim":
            d["r0_vs_ref_maxabs"] = float(np.max(np.abs(out - rref)))
            d["r0_vs_ref_maxrel"] = float(np.max(np.abs(out - rref)) / np.max(np.abs(rref)))
        elif name == "jacfwd":
            d.update(G.summarize_err(out, Jref, out.T @ rref, gref))
        else:
            d["grad_rel_err"] = float(np.linalg.norm(out - gref) / np.linalg.norm(gref))
        res[name] = d
        print(name, ts["median"], file=sys.stderr)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[-1]) if args else 30
    if "--method" in sys.argv:
        m = sys.argv[sys.argv.index("--method") + 1]
        if m.startswith("jax"):
            import jax

            jax.config.update("jax_enable_x64", True)
        if m.startswith("jax_"):
            res = method_jax(n, (m[4:],))
        else:
            res = {"cs_ref": method_cs_ref, "numba": method_numba}[m](n)
        res["peak_rss_mb"] = peak_rss_mb()
        print(json.dumps(res))
        return
    import subprocess

    env = dict(os.environ, NUMBA_NUM_THREADS=str(THREADS), OMP_NUM_THREADS="1",
               XLA_FLAGS="--xla_cpu_multi_thread_eigen=false", NUMBA_CACHE_DIR=str(CACHE / "numba"))  # fmt: skip
    out = {"machine": machine_info(), "n": n, "reps": REPS, "threads": THREADS, "problem": G.__doc__}
    for m in ("cs_ref", "numba", "jax_forward_sim", "jax_jacfwd", "jax_grad"):
        if m == "cs_ref" and (CACHE / f"m5_Jref_n{n}.npz").exists() and "--reuse-ref" in sys.argv:
            prev = RESULTS / f"m5_gradients_n{n}.json"  # keep the reference entry of the run that produced it
            out["cs_ref"] = {**json.load(open(prev))["cs_ref"], "reused": True}
            continue
        r = subprocess.run([PY, "-I", os.path.abspath(__file__), "--method", m, str(n)], capture_output=True,
                           text=True, env=env)  # fmt: skip
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-3000:])
        out[m] = json.loads(r.stdout.strip().splitlines()[-1])
        print(m, "done", file=sys.stderr)
    save_json(f"m5_gradients_n{n}.json", out)


if __name__ == "__main__":
    main()
