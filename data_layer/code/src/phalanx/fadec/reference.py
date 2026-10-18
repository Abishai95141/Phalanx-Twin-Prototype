"""The NumPy reference of the M08 kernel: `kernel.py`'s own source executed with the identity decorator.

`_block.py_func` alone would still call the compiled helpers (`_frame`, `_lk`, ...), so it is not a reference.
Executing the same source text with `_REFERENCE_MODE = True` gives a pure-Python/NumPy copy of every function
(the module-level effect of `NUMBA_DISABLE_JIT=1`) while the compiled kernel stays cacheable. AD-22: the
compiled kernel and this reference must agree bitwise (`tests/integration/test_fadec_kernel.py`).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from functools import lru_cache


@lru_cache(maxsize=1)
def _namespace() -> dict:
    spec = importlib.util.find_spec("phalanx.fadec.kernel")
    if spec is None or spec.loader is None or spec.origin is None:
        raise ImportError("phalanx.fadec.kernel not found")
    src = spec.loader.get_source("phalanx.fadec.kernel")
    ns: dict = {
        "__name__": "phalanx.fadec._kernel_reference",
        "__package__": "phalanx.fadec",
        "__file__": spec.origin,
        "_REFERENCE_MODE": True,
    }
    exec(compile(src, spec.origin, "exec"), ns)  # same source text, identity decorator
    if not ns["_REFERENCE"]:
        raise RuntimeError("reference namespace did not enter reference mode")
    return ns


def kernel_reference() -> Callable:
    """The uncompiled `_block` (same signature as `kernel.fadec_block`)."""
    return _namespace()["_block"]


__all__ = ["kernel_reference"]
