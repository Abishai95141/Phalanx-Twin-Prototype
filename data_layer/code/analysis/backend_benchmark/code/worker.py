"""Fresh-process worker: runs one configuration and prints one JSON line (timings, digests, peak RSS).

Every measurement runs in its own process so that compile overhead, caches, thread counts and peak RSS are
attributable to one configuration. Thread limits come from the environment set by the caller
(NUMBA_NUM_THREADS, XLA_FLAGS, jax_num_cpu_devices via --ndev).

Usage: python -I code/worker.py run --backend numba --mode single --units 1 --kind sortie --steps 864000
                                    --block 2400 --reps 5 [--unroll 1] [--ndev 1] [--first 0]
       python -I code/worker.py compile --backend jax --mode vmap --units 1000 --block 2400
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import cpu_s, now, peak_rss_mb

T_START = now()


def _args(argv):
    a = argparse.ArgumentParser()
    a.add_argument("task", choices=["run", "compile"])
    a.add_argument("--backend", required=True, choices=["numpy", "numba", "jax"])
    a.add_argument("--mode", default="auto")
    a.add_argument("--units", type=int, default=1)
    a.add_argument("--first", type=int, default=0, help="first unit id")
    a.add_argument("--kind", default="sortie", choices=["sortie", "combat"])
    a.add_argument("--steps", type=int, default=2400)
    a.add_argument("--block", type=int, default=2400)
    a.add_argument("--reps", type=int, default=1)
    a.add_argument("--unroll", type=int, default=1)
    a.add_argument("--ndev", type=int, default=1)
    a.add_argument("--threads", type=int, default=0, help="numba.set_num_threads (0 = leave)")
    a.add_argument("--keep-digests", type=int, default=1, help="return per-unit digests")
    return a.parse_args(argv)


def main(argv):
    a = _args(argv)
    t0 = now()
    if a.backend == "jax":
        import jax

        jax.config.update("jax_num_cpu_devices", max(a.ndev, 1))
        cache_dir = os.environ.get("BENCH_JAX_CACHE")
        if cache_dir:
            jax.config.update("jax_compilation_cache_dir", cache_dir)
            jax.config.update("jax_persistent_cache_min_compile_time_secs", 0.0)
            jax.config.update("jax_persistent_cache_min_entry_size_bytes", 0)
        import be_jax  # noqa: F401
    elif a.backend == "numba":
        import be_numba  # noqa: F401
        import numba

        if a.threads:
            numba.set_num_threads(a.threads)
    import harness as Hn

    t_import = now() - t0
    units = range(a.first, a.first + a.units)
    t0 = now()
    scen = Hn.Scenario(units, a.kind, a.steps)
    t_scen = now() - t0
    f = Hn.make_backend(a.backend, scen, a.mode, unroll=a.unroll, ndev=a.ndev)

    # first call: compile (or cache load) + one block
    n_first = min(a.block, a.steps)
    t0, c0 = now(), cpu_s()
    r_first = Hn.run(f, scen, 0, n_first, a.block)
    t_first = now() - t0
    c_first = cpu_s() - c0
    # second call on the same shapes (warm)
    t0 = now()
    Hn.run(f, scen, 0, n_first, a.block)
    t_second = now() - t0

    res = {
        "task": a.task,
        "config": vars(a),
        "t_import": t_import,
        "t_scenario": t_scen,
        "t_first_call": t_first,
        "cpu_first_call": c_first,
        "t_second_call": t_second,
        "first_block_digest": r_first["digests"][0],
    }
    if a.task == "run":
        reps = []
        digs = None
        for _ in range(a.reps):
            r = Hn.run(f, scen, 0, a.steps, a.block)
            reps.append({k: r[k] for k in ("t_feed", "t_kernel", "t_wall", "t_cpu")})
            if digs is None:
                digs = r["digests"]
                state = Hn.state_digest(r["X"], r["S"])
            else:
                assert r["digests"] == digs, "repeat run differs (in-process determinism D1 failed)"
        res["reps"] = reps
        res["all_digest"] = hashlib.blake2b("".join(digs).encode(), digest_size=16).hexdigest()
        res["unit_digests"] = digs if a.keep_digests else None
        res["state_digest"] = state
        res["sim_seconds_per_unit"] = a.steps / 240.0
    res["peak_rss_mb"] = peak_rss_mb()
    res["t_process"] = now() - T_START
    print(json.dumps(res))


if __name__ == "__main__":
    main(sys.argv[1:])
