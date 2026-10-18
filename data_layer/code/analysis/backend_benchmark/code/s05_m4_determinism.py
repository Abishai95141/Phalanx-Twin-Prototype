"""M4 determinism checks D1-D6 per backend (D7, cache vs fresh compile, is recorded by s04_m2_compile.py).

  D1 repeated in-process runs                   1 unit and 10 units, 60 s, twice
  D2 separate processes                         1 unit and 100 units, 60 s, two processes
  D3 single vs batched, and position in batch   units 0-9 alone vs in batches of 10 / 100 / 1,000 and an offset
                                                batch (units 5-14): per-unit digests must not depend on the batch
  D4 thread / device counts                     100 units, 60 s: Numba threads 1/2/4; JAX devices 1/2/4 (sharded)
                                                and XLA intra-op threading on/off
  D5 snapshot -> bytes -> restore -> continue   1 unit and 10 units, snapshot at step 5,237 (not a multiple of the
                                                block, 2,400, or of the controller period, 4) vs uninterrupted;
                                                also at 4,800 (a block boundary) to separate block-length effects
  D6 block length                               1 unit, 10 s, kernel block 1 / 240 / 2,400 steps

Digests are blake2b over each unit's output stream (block-partition independent, harness.StreamDigest).
Workload: 'combat' 60 s windows (slams; every limiter branch engages). n is fixed by the property: one
counter-example falsifies determinism, each condition is run at least twice.

Usage: python -I code/s05_m4_determinism.py              (driver -> results/m4_determinism.json)
       python -I code/s05_m4_determinism.py --sub <check> --backend <b> [opts]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from common import CACHE, PY, machine_info, save_json

STEPS = 14_400
JAX_UNROLL = int(os.environ.get("BENCH_JAX_UNROLL", "4"))
BACKENDS = os.environ.get("BENCH_BACKENDS", "numba,jax").split(",")


def _snapshot_bytes(X, S) -> bytes:
    """Canonical snapshot: header (shapes, dtypes) + little-endian raw buffers (no pickle)."""
    hdr = json.dumps(
        {"X": [list(X.shape), "<f8"], "S": [list(S.shape), "<i8"], "v": 1}, sort_keys=True
    ).encode()
    return len(hdr).to_bytes(4, "little") + hdr + X.astype("<f8").tobytes() + S.astype("<i8").tobytes()


def _restore(b: bytes):
    n = int.from_bytes(b[:4], "little")
    hdr = json.loads(b[4 : 4 + n])
    xs, ss = hdr["X"][0], hdr["S"][0]
    nx = int(np.prod(xs)) * 8
    X = np.frombuffer(b[4 + n : 4 + n + nx], "<f8").reshape(xs).copy()
    S = np.frombuffer(b[4 + n + nx :], "<i8").reshape(ss).copy()
    return X, S


def sub(check: str, backend: str, opts: dict) -> dict:
    if backend == "jax":
        import jax

        jax.config.update("jax_num_cpu_devices", int(opts.get("ndev", 1)))
    import harness as Hn

    mode = opts.get("mode", "auto")
    kw = {"unroll": JAX_UNROLL, "ndev": int(opts.get("ndev", 1))}

    def digests(units, steps=STEPS, L=2400, mode=mode):
        sc = Hn.Scenario(units, "combat", steps)
        f = Hn.make_backend(backend, sc, mode, **kw)
        r = Hn.run(f, sc, 0, steps, L)
        return r["digests"], Hn.state_digest(r["X"], r["S"])

    if check == "repeat":
        a = digests(range(int(opts["units"])))
        b = digests(range(int(opts["units"])))
        return {"a": a, "b": b}
    if check == "digests":
        first, n = int(opts.get("first", 0)), int(opts["units"])
        d, s = digests(range(first, first + n))
        return {"units": list(range(first, first + n)), "digests": d, "state": s}
    if check == "singles":
        return {"digests": [digests([u], mode="single")[0][0] for u in range(int(opts["units"]))]}
    if check == "snapshot":
        n = int(opts["units"])
        ksnap = int(opts.get("ksnap", 5237))
        sc = Hn.Scenario(range(n), "combat", STEPS)
        f = Hn.make_backend(backend, sc, mode, **kw)
        full = Hn.run(f, sc, 0, STEPS, 2400, keep=True)
        a = Hn.run(f, sc, 0, ksnap, 2400, keep=True)
        blob = _snapshot_bytes(a["X"], a["S"])
        X, S = _restore(blob)
        b = Hn.run(f, sc, ksnap, STEPS - ksnap, 2400, X=X, S=S, keep=True)
        out = np.concatenate([a["out"], b["out"]], axis=1)
        sel = np.concatenate([a["sel"], b["sel"]], axis=1)
        same_out = bool(np.array_equal(out, full["out"]) and np.array_equal(sel, full["sel"]))
        same_state = bool(np.array_equal(b["X"], full["X"]) and np.array_equal(b["S"], full["S"]))
        return {"k_snapshot": ksnap, "snapshot_bytes": len(blob), "outputs_identical": same_out,
                "final_state_identical": same_state}  # fmt: skip
    if check == "blocklen":
        res = {}
        for L in (1, 240, 2400):
            d, s = digests([0], steps=2400, L=L, mode="single")
            res[str(L)] = {"digest": d[0], "state": s}
        return res
    raise ValueError(check)


def _run(check, backend, env=None, **opts):
    args = [
        PY,
        "-I",
        os.path.abspath(__file__),
        "--sub",
        check,
        "--backend",
        backend,
        "--opts",
        json.dumps(opts),
    ]
    e = dict(os.environ, OMP_NUM_THREADS="1", NUMBA_CACHE_DIR=str(CACHE / "numba"), NUMBA_NUM_THREADS="4",
             XLA_FLAGS="--xla_cpu_multi_thread_eigen=false")  # fmt: skip
    if env:
        e.update(env)
    r = subprocess.run(args, capture_output=True, text=True, env=e)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def driver():
    out = {"machine": machine_info(), "steps": STEPS, "jax_unroll": JAX_UNROLL, "checks": {}}
    C = out["checks"]

    def verdict(name, ok, detail):
        C[name] = {"pass": bool(ok), "detail": detail}
        print(f"{name:45s} {'PASS' if ok else 'FAIL'}", file=sys.stderr)

    for be in BACKENDS:
        batch_mode = "prange" if be == "numba" else "vmap"
        # D1
        for u in (1, 10):
            r = _run("repeat", be, units=u, mode="single" if u == 1 else batch_mode)
            verdict(f"D1 {be} repeat in-process U={u}", r["a"] == r["b"], r)
        # D2
        for u in (1, 100):
            m = "single" if u == 1 else batch_mode
            a = _run("digests", be, units=u, mode=m)
            b = _run("digests", be, units=u, mode=m)
            verdict(f"D2 {be} two processes U={u}", a == b, {"a": a["state"], "b": b["state"]})
        # D3
        singles = _run("singles", be, units=10)["digests"]
        batches = {n: _run("digests", be, units=n, mode=batch_mode) for n in (10, 100, 1000)}
        off = _run("digests", be, units=10, first=5, mode=batch_mode)
        det = {}
        for n, b in batches.items():
            det[f"batch{n}_vs_singles_units0-9_equal"] = int(
                sum(x == y for x, y in zip(b["digests"][:10], singles, strict=False))
            )
        det["batch100_vs_batch1000_units0-99_equal"] = int(
            sum(x == y for x, y in zip(batches[100]["digests"], batches[1000]["digests"][:100], strict=False))
        )
        det["offset_batch_units5-14_vs_batch1000_equal"] = int(
            sum(x == y for x, y in zip(off["digests"], batches[1000]["digests"][5:15], strict=False))
        )
        ok = all(v == (100 if "0-99" in k else 10) for k, v in det.items())
        verdict(f"D3 {be} single vs batched / position", ok, det)
        out[f"_digests_{be}"] = {"singles": singles, "batch1000_first10": batches[1000]["digests"][:10]}
        # D4
        if be == "numba":
            ds = {t: _run("digests", be, {"NUMBA_NUM_THREADS": str(t)}, units=100, mode="prange")["digests"]
                  for t in (1, 2, 4)}  # fmt: skip
            ser = _run("digests", be, units=100, mode="serial")["digests"]
            ok = all(ds[t] == ds[1] for t in ds) and ser == ds[1]
            verdict(
                "D4 numba threads 1/2/4 (+serial loop)",
                ok,
                {"equal_to_1thread": {t: ds[t] == ds[1] for t in ds}},
            )
        else:
            ds = {n: _run("digests", be, units=100, mode="sharded", ndev=n)["digests"] for n in (1, 2, 4)}
            mt = _run("digests", be, {"XLA_FLAGS": ""}, units=100, mode="vmap")["digests"]
            st = batches[100]["digests"]
            det = {f"sharded_ndev{n}_eq_vmap": ds[n] == st for n in ds}
            det["vmap_multithread_eigen_eq_single_thread"] = mt == st
            verdict("D4 jax devices 1/2/4 + intra-op threads", all(det.values()), det)
        # D5
        for u in (1, 10):
            for ks in (5237, 4800):  # arbitrary step; and a block boundary (separates D5 from D6 effects)
                r = _run("snapshot", be, units=u, mode="single" if u == 1 else batch_mode, ksnap=ks)
                verdict(f"D5 {be} snapshot/restore U={u} k={ks}", r["outputs_identical"] and r["final_state_identical"],
                        r)  # fmt: skip
        # D6
        r = _run("blocklen", be)
        ok = len({v["digest"] for v in r.values()}) == 1 and len({v["state"] for v in r.values()}) == 1
        verdict(f"D6 {be} block length 1/240/2400", ok, r)
    # cross-backend (informative): Numba vs JAX unit digests
    if "_digests_numba" in out and "_digests_jax" in out:
        out["numba_vs_jax_singles_equal"] = int(
            sum(a == b for a, b in zip(out["_digests_numba"]["singles"], out["_digests_jax"]["singles"], strict=False))
        )
    save_json(os.environ.get("BENCH_M4_OUT", "m4_determinism.json"), out)


if __name__ == "__main__":
    if "--sub" in sys.argv:
        i = sys.argv.index
        opts = json.loads(sys.argv[i("--opts") + 1]) if "--opts" in sys.argv else {}
        print(json.dumps(sub(sys.argv[i("--sub") + 1], sys.argv[i("--backend") + 1], opts)))
    else:
        driver()
