"""A1: agreement of every backend with the NumPy reference (sample -> verify -> scale).

  S1  10 s, 1 unit (sortie start)          NumPy vs Numba (single) vs JAX (single; unroll 1 and 4)
  S2  60 s, 10 units ('combat' windows)    NumPy (vectorised) vs Numba (prange) vs JAX (vmap)
  S3  1 h, 1 unit (full sortie)            Numba and JAX vs _cache/ref_hour.npz (s02_ref_hour.py)

Metrics per channel: bitwise equality; max |a - b| / max |ref| (channel-scaled); max pointwise relative error;
first differing step; number of steps whose selected limiter differs (a discrete-branch flip), first flip time;
growth of the difference over 10-minute windows (S3).

Usage: python -I code/s03_a1_agreement.py [S1 S2 S3]   (each stage in its own process per backend)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from common import CACHE, PY, machine_info, save_json

CHN = ["N1", "N2", "Wf", "PS3", "T5", "Tm"]


def compare(out, sel, ref_out, ref_sel) -> dict:
    d = {
        "bitwise_outputs": bool(np.array_equal(out, ref_out)),
        "bitwise_sel": bool(np.array_equal(sel, ref_sel)),
    }
    diff = np.abs(out - ref_out)
    scale = np.max(np.abs(ref_out), axis=tuple(range(ref_out.ndim - 1)))
    d["max_abs_over_channel_scale"] = {c: float(diff[..., i].max() / scale[i]) for i, c in enumerate(CHN)}
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(ref_out != 0, diff / np.abs(ref_out), 0.0)
    d["max_pointwise_rel"] = float(rel.max())
    neq = np.any(out != ref_out, axis=-1)
    d["first_differing_step"] = int(np.argmax(neq.reshape(-1, neq.shape[-1]).any(0))) if neq.any() else None
    flips = sel != ref_sel
    d["sel_flip_steps"] = int(flips.sum())
    d["first_sel_flip_s"] = (
        float(np.argmax(flips.any(0) if flips.ndim > 1 else flips) / 240.0) if flips.any() else None
    )
    return d


def stage(name: str, backend: str, unroll: int = 4) -> dict:
    import harness as Hn

    if name == "S1":
        sc = Hn.Scenario([0], "sortie", 2400)
        r = Hn.run(Hn.make_backend(backend, sc, "single" if backend != "numpy" else "auto", unroll=unroll), sc, 0,
                   2400, 2400, keep=True)  # fmt: skip
    elif name == "S2":
        sc = Hn.Scenario(range(10), "combat", 14_400)
        mode = {"numpy": "auto", "numba": "prange", "jax": "vmap"}[backend]
        r = Hn.run(Hn.make_backend(backend, sc, mode, unroll=unroll), sc, 0, 14_400, 2400, keep=True)
    elif name == "S3":
        sc = Hn.Scenario([0], "sortie", 864_000)
        r = Hn.run(Hn.make_backend(backend, sc, "single", unroll=unroll), sc, 0, 864_000, 2400, keep=True)
    else:
        raise ValueError(name)
    np.savez(CACHE / f"a1_{name}_{backend}_u{unroll}.npz", out=r["out"], sel=r["sel"])
    return {"digests": r["digests"]}


def main():
    stages = [a for a in sys.argv[1:] if a in ("S1", "S2", "S3")] or ["S1", "S2", "S3"]
    if "--stage" in sys.argv:
        i = sys.argv.index
        if sys.argv[i("--backend") + 1] == "jax":
            import jax

            jax.config.update("jax_enable_x64", True)
        print(json.dumps(stage(sys.argv[i("--stage") + 1], sys.argv[i("--backend") + 1],
                               int(sys.argv[i("--unroll") + 1]))))  # fmt: skip
        return
    env = dict(os.environ, OMP_NUM_THREADS="1", NUMBA_NUM_THREADS="4", NUMBA_CACHE_DIR=str(CACHE / "numba"),
               XLA_FLAGS="--xla_cpu_multi_thread_eigen=false")  # fmt: skip
    path = CACHE.parent / "results" / "a1_agreement.json"
    res = json.load(open(path)) if path.exists() else {}
    res["machine"] = machine_info()
    for st in stages:
        runs = [("numba", 4), ("jax", 4), ("jax", 1)] + ([("numpy", 4)] if st != "S3" else [])
        for be, ur in runs:
            r = subprocess.run([PY, "-I", os.path.abspath(__file__), "--stage", st, "--backend", be, "--unroll", str(ur)],
                               capture_output=True, text=True, env=env)  # fmt: skip
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-3000:])
        if st == "S3":
            z = np.load(CACHE / "ref_hour.npz")
            ref_o, ref_s = z["out"][None], z["sel"][None]
        else:
            z = np.load(CACHE / f"a1_{st}_numpy_u4.npz")
            ref_o, ref_s = z["out"], z["sel"]
        res[st] = {}
        for be, ur in [("numba", 4), ("jax", 4), ("jax", 1)]:
            z = np.load(CACHE / f"a1_{st}_{be}_u{ur}.npz")
            key = be if be == "numba" else f"jax_unroll{ur}"
            res[st][key] = compare(z["out"], z["sel"], ref_o, ref_s)
            if st == "S3":
                o = z["out"][0]
                win = 240 * 600
                res[st][key]["max_abs_over_scale_per_10min"] = [
                    float(np.max(np.abs(o[a : a + win] - ref_o[0, a : a + win]) / np.abs(ref_o[0]).max(0)))
                    for a in range(0, o.shape[0], win)
                ]
            print(st, key, json.dumps(res[st][key])[:400], file=sys.stderr)
    save_json("a1_agreement.json", res)


if __name__ == "__main__":
    main()
