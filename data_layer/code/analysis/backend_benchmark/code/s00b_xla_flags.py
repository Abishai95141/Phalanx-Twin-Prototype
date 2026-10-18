"""Which XLA CPU flags restore op-level bitwise agreement with NumPy/Numba? (A1 mechanism, JAX only)

Runs a small probe in a fresh process per XLA_FLAGS setting (flags are read once at backend initialisation):
FMA contraction (a*b+c), division by a literal, division by a broadcast runtime scalar, exp, and the same
patterns inside lax.scan (scalar hot-loop context).

Usage: python -I code/s00b_xla_flags.py            (driver; writes results/xla_flags.json)
       python -I code/s00b_xla_flags.py --probe    (one probe in the current environment)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FLAG_SETS = [
    "",
    "--xla_cpu_enable_fast_math=false",
    "--xla_allow_excess_precision=false",
    "--xla_cpu_disable_platform_dependent_math=true",
    "--xla_cpu_enable_platform_dependent_math=false",
    "--xla_cpu_fast_math_honor_division=true --xla_cpu_fast_math_honor_functions=true",
    "--xla_cpu_disable_slp_vectorizer=true",
    "--xla_allow_excess_precision=false --xla_cpu_disable_platform_dependent_math=true",
]


def probe() -> dict:
    import jax
    import numpy as np

    jax.config.update("jax_enable_x64", True)
    import jax.numpy as jnp
    import rngblocks as R

    g = R.generator(("bench", "xla_flags_probe"))
    n = 100_000
    a, b, c = g.uniform(0.5, 2, n), g.uniform(-3, 3, n), g.uniform(0.1, 10, n)
    s = np.array([0.05])
    tests = {
        "fma a*b+c": (lambda a, b, c, s: a * b + c, a * b + c),
        "div literal a/288.15": (lambda a, b, c, s: a / 288.15, a / 288.15),
        "div bcast (b-a)/s": (lambda a, b, c, s: (b - a) / s[0], (b - a) / s[0]),
        "exp(b)": (lambda a, b, c, s: jnp.exp(b), np.exp(b)),
    }
    out = {}
    for k, (f, ref) in tests.items():
        v = np.asarray(jax.jit(f)(a, b, c, s))

        def body(carry, xs, f=f):
            return carry, f(*xs, carry)

        w = np.asarray(jax.jit(lambda a, b, c, s, body=body: jax.lax.scan(body, s, (a, b, c))[1])(a, b, c, s))
        out[k] = {"jit_vector": int(np.sum(v != ref)), "scan_scalar": int(np.sum(w != ref))}
    return out


def main():
    from common import PY, machine_info, save_json

    rows = []
    for fl in FLAG_SETS:
        env = dict(os.environ, XLA_FLAGS=("--xla_cpu_multi_thread_eigen=false " + fl).strip())
        r = subprocess.run(
            [PY, "-I", os.path.abspath(__file__), "--probe"], capture_output=True, text=True, env=env
        )
        if r.returncode != 0:
            rows.append({"flags": fl, "error": r.stderr.strip().splitlines()[-1][:300]})
        else:
            rows.append({"flags": fl, "mismatches_of_100000": json.loads(r.stdout.strip().splitlines()[-1])})
        print(json.dumps(rows[-1]))
    save_json("xla_flags.json", {"machine": machine_info(), "rows": rows})


if __name__ == "__main__":
    if "--probe" in sys.argv:
        print(json.dumps(probe()))
    else:
        main()
