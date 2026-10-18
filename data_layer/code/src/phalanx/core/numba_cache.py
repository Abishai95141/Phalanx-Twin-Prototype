"""Numba cache keyed by the package sources (stale-cache guard; AD-22 uses ``@njit(cache=True)``).

Numba's on-disk cache is keyed by the *decorated function's own file* (path + timestamp). It does not see
changes to constants imported from other modules (e.g. swapping two index constants in ``layout.py``
without touching ``kernel.py``), so a stale compiled kernel can silently disagree with its source; a
concurrent process can also leave entries behind. The rule:

- **Production runs** call :func:`configure_numba_cache` first thing, before any kernel module is imported.
  It points ``NUMBA_CACHE_DIR`` at ``<package>/__pycache__/numba/src-<digest16>``, where ``digest`` is a
  blake2b over every ``*.py`` file of the ``phalanx`` package (relative path + bytes). Any source edit
  anywhere in the package therefore selects a fresh, empty cache directory; identical sources share one.
  The run manifest records the key (:func:`numba_cache_status`).
- **Tests** (``tests/conftest.py``) use a fresh per-session cache directory, so ``make check`` always
  compiles from the current sources.

Kernel parameters are passed as arrays (AD-22), never baked in from data files, so ``*.py`` sources are the
complete compile-time input. ``__pycache__`` is git-ignored; old ``src-*`` directories can be deleted freely.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

PERSON_SOURCES = b"phx.sources.v1"


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _digest_of(root: str) -> str:
    h = hashlib.blake2b(digest_size=32, person=PERSON_SOURCES)
    base = Path(root)
    for p in sorted(base.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(base).as_posix().encode()
        data = p.read_bytes()
        h.update(len(rel).to_bytes(8, "little") + rel + len(data).to_bytes(8, "little") + data)
    return h.hexdigest()


def source_digest(root: Path | None = None) -> str:
    """blake2b-256 over every ``*.py`` file of the package (sorted relative paths and contents)."""
    return _digest_of(str(root or package_root()))


def cache_key(root: Path | None = None) -> str:
    return f"src-{source_digest(root)[:16]}"


def numba_cache_dir(base: Path | None = None, root: Path | None = None) -> Path:
    """The source-keyed cache directory: ``<base>/src-<digest16>`` (base: ``<package>/__pycache__/numba``)."""
    base = base if base is not None else package_root() / "__pycache__" / "numba"
    return base / cache_key(root)


def _cached_kernels_loaded() -> list[str]:
    """Already-imported phalanx functions compiled with ``cache=True`` (they keep their old locator)."""
    if "numba" not in sys.modules:
        return []
    from numba.core.dispatcher import Dispatcher

    found = []
    for name, mod in list(sys.modules.items()):
        if not name.startswith("phalanx.") or mod is None:
            continue
        for attr, obj in list(vars(mod).items()):
            if isinstance(obj, Dispatcher) and type(getattr(obj, "_cache", None)).__name__ == "FunctionCache":
                found.append(f"{name}.{attr}")
    return sorted(found)


def configure_numba_cache(base: Path | None = None) -> Path:
    """Point Numba's cache at the source-keyed directory. Call before importing any kernel module."""
    loaded = _cached_kernels_loaded()
    if loaded:
        raise RuntimeError(
            "configure_numba_cache() must run before kernel modules are imported; already loaded: "
            + ", ".join(loaded[:5])
        )
    d = numba_cache_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = str(d)
    if "numba" in sys.modules:  # numba read the environment at import: update its live config too
        from numba.core import config

        config.CACHE_DIR = str(d)
    return d


def numba_cache_status() -> dict[str, Any]:
    """For the run manifest: the source digest, the expected key, and whether the cache in effect uses it."""
    in_effect = os.environ.get("NUMBA_CACHE_DIR", "")
    if "numba" in sys.modules:
        from numba.core import config

        in_effect = str(config.CACHE_DIR or in_effect)
    key = cache_key()
    return {"source_digest": source_digest(), "key": key, "configured": Path(in_effect).name == key}
