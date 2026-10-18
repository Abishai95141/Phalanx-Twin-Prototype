"""Shared utilities: hashing, machine info, timing, peak RSS, JSON results.

Wall-clock reads are benchmark timing only (annotated for the static audit, which scans src/ only).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # analysis/backend_benchmark
RESULTS = ROOT / "results"
CACHE = ROOT / "_cache"
PY = sys.executable


def now() -> float:
    return time.perf_counter()  # audit: allow R4 benchmark timing


def cpu_s() -> float:
    t = os.times()
    return t.user + t.system


def peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024  # macOS: bytes; Linux: KiB


class Digest:
    """blake2b over arrays in a fixed order (dtype, shape and little-endian bytes)."""

    def __init__(self):
        self.h = hashlib.blake2b(digest_size=16)

    def update(self, *arrays):
        for a in arrays:
            a = np.ascontiguousarray(a)
            self.h.update(f"{a.dtype.str}{a.shape}".encode())
            self.h.update(a.astype(a.dtype.newbyteorder("<"), copy=False).tobytes())
        return self

    def hex(self) -> str:
        return self.h.hexdigest()


def digest(*arrays) -> str:
    return Digest().update(*arrays).hex()


def versions() -> dict:
    v = {"python": sys.version.split()[0], "numpy": np.__version__}
    for mod in ("numba", "llvmlite", "jax", "jaxlib", "scipy"):
        try:
            v[mod] = __import__(mod).__version__
        except Exception:  # pragma: no cover - optional
            v[mod] = None
    return v


def machine_info() -> dict:
    def sysctl(k):
        try:
            return subprocess.run(
                ["sysctl", "-n", k], capture_output=True, text=True, check=True
            ).stdout.strip()
        except Exception:
            return None

    env = {
        k: os.environ.get(k) for k in ("NUMBA_NUM_THREADS", "XLA_FLAGS", "OMP_NUM_THREADS", "NUMBA_CACHE_DIR")
    }
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": sysctl("machdep.cpu.brand_string"),
        "ncpu": os.cpu_count(),
        "perf_cores": sysctl("hw.perflevel0.physicalcpu"),
        "eff_cores": sysctl("hw.perflevel1.physicalcpu"),
        "mem_gb": round(int(sysctl("hw.memsize") or 0) / 2**30, 1),
        "versions": versions(),
        "env": env,
    }


def stats(xs) -> dict:
    a = np.asarray(xs, dtype=float)
    return {
        "n": int(a.size),
        "median": float(np.median(a)),
        "min": float(a.min()),
        "max": float(a.max()),
        "mean": float(a.mean()),
        "sd": float(a.std(ddof=1)) if a.size > 1 else 0.0,
        "values": [float(x) for x in a],
    }


def save_json(name: str, obj: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / name
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=_jsonable)
    return p


def _jsonable(o):
    if isinstance(o, np.integer | np.floating):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def log_check(line: str) -> None:
    """Append a sample -> verify -> scale entry to results/log_sample_verify_scale.md."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "log_sample_verify_scale.md", "a") as fh:
        fh.write(f"- {line}\n")


def run_worker(args: list[str], env_extra: dict | None = None, timeout: float = 3600) -> dict:
    """Run `python -I code/worker.py <args>` in a fresh process; return its JSON result (last stdout line)."""
    env = dict(os.environ)
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("NUMBA_CACHE_DIR", str(CACHE / "numba"))
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    r = subprocess.run([PY, "-I", str(HERE / "worker.py"), *args], capture_output=True, text=True, env=env,
                       timeout=timeout)  # fmt: skip
    if r.returncode != 0:
        raise RuntimeError(f"worker failed ({r.returncode}): {' '.join(args)}\n{r.stderr[-4000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])
