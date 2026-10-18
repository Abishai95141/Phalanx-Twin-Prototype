"""Op-level conformance (A1 mechanism): which elementary float64 operations agree bitwise across backends?

For each op, evaluate on n keyed random inputs with NumPy (reference), Numba (scalar loop), JAX jit (vectorised)
and JAX inside lax.scan (one element per step, the hot-loop context). Report mismatches and max ULP distance.
Patterns probe compiler rewrites: a*b+c (FMA contraction), x/c with a runtime scalar c (reciprocal-multiply),
x/288.15 with a literal divisor, pow with runtime / literal exponents, exp/log/sqrt.

Usage: python -I code/s00_oplevel.py [n]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import rngblocks as R
from common import machine_info, save_json


def ulp_dist(a, b):
    """ULP distance between float64 arrays (same sign assumed; inf where signs differ)."""
    return np.abs(a.view(np.int64) - b.view(np.int64))  # exact in int64 (same-sign finite values)


def main(n: int = 100_000):
    g = R.generator(("bench", "oplevel"))
    a = g.uniform(0.5, 2.0, n)
    b = g.uniform(-3.0, 3.0, n)
    c = g.uniform(0.1, 10.0, n)
    y = g.uniform(-1.5, 1.5, n)
    s = np.array([0.73, -0.5, 1.0 / 960.0, 0.05])  # runtime scalars: exponent, exponent, h, tau

    ops = {
        "add a+b": (lambda a, b, c, y, s: a + b),
        "mul a*b": (lambda a, b, c, y, s: a * b),
        "div a/c": (lambda a, b, c, y, s: a / c),
        "sqrt a": (lambda a, b, c, y, s: _sqrt(a)),
        "a*b+c (fma?)": (lambda a, b, c, y, s: a * b + c),
        "a + h*b (h runtime)": (lambda a, b, c, y, s: a + s[2] * b),
        "(b-a)/tau (tau runtime)": (lambda a, b, c, y, s: (b - a) / s[3]),
        "a/288.15 (literal)": (lambda a, b, c, y, s: a / 288.15),
        "pow(a, y)": (lambda a, b, c, y, s: a**y),
        "pow(a, 0.73 runtime)": (lambda a, b, c, y, s: a ** s[0]),
        "pow(a, -0.5 runtime)": (lambda a, b, c, y, s: a ** s[1]),
        "exp(b)": (lambda a, b, c, y, s: _exp(b)),
        "log(a)": (lambda a, b, c, y, s: _log(a)),
    }
    res = {"n": n, "machine": machine_info(), "ops": {}}

    # NumPy reference (vectorised ufuncs)
    global _sqrt, _exp, _log
    _sqrt, _exp, _log = np.sqrt, np.exp, np.log
    ref = {k: f(a, b, c, y, s) for k, f in ops.items()}

    # Python scalar math (libm) for the transcendental ops
    import math

    pym = {
        "sqrt a": np.array([math.sqrt(v) for v in a]),
        "exp(b)": np.array([math.exp(v) for v in b]),
        "log(a)": np.array([math.log(v) for v in a]),
        "pow(a, y)": np.array([math.pow(u, v) for u, v in zip(a, y, strict=True)]),
        "pow(a, 0.73 runtime)": np.array([math.pow(u, s[0]) for u in a]),
        "pow(a, -0.5 runtime)": np.array([math.pow(u, s[1]) for u in a]),
    }

    # Numba scalar loop, fastmath off
    from numba import njit

    nb_impl = {}

    def make_nb(f):
        sf = njit(f, fastmath=False)

        @njit(fastmath=False)
        def loop(a, b, c, y, s):
            out = np.empty(a.size)
            for i in range(a.size):
                out[i] = sf(a[i], b[i], c[i], y[i], s)
            return out

        return loop

    _sqrt, _exp, _log = np.sqrt, np.exp, np.log
    for k, f in ops.items():
        nb_impl[k] = make_nb(f)(a, b, c, y, s)

    # JAX: jit (vectorised) and inside lax.scan (scalar per step)
    import jax

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp

    _sqrt, _exp, _log = jnp.sqrt, jnp.exp, jnp.log
    jx_vec, jx_scan = {}, {}
    for k, f in ops.items():
        jf = jax.jit(f)
        jx_vec[k] = np.asarray(jf(a, b, c, y, s))

        def body(carry, xs, f=f):
            return carry, f(*xs, carry)

        sf = jax.jit(lambda a, b, c, y, s, body=body: jax.lax.scan(body, s, (a, b, c, y))[1])
        jx_scan[k] = np.asarray(sf(a, b, c, y, s))

    for k in ops:
        row = {}
        for name, d in (("numba", nb_impl), ("jax_jit", jx_vec), ("jax_scan", jx_scan), ("python_math", pym)):
            if k not in d:
                continue
            v = d[k]
            mism = int(np.sum(v != ref[k]))
            row[name] = {"mismatches": mism, "max_ulp": float(ulp_dist(v, ref[k]).max()) if mism else 0.0}
        res["ops"][k] = row
        print(
            f"{k:28s} "
            + "  ".join(f"{nm}: {r['mismatches']:6d} ({r['max_ulp']:.0f} ulp)" for nm, r in row.items())
        )
    save_json("oplevel.json", res)


_sqrt = _exp = _log = None

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100_000)
