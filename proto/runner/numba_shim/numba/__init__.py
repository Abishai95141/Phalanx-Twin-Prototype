"""Pure-Python stand-in for numba on machines without a numba build (IBM Z / s390x).

The data layer decorates kernels with ``@njit`` / ``@njit(**options)``. Here the decorator returns the Python
function unchanged — exactly what numba itself does with ``NUMBA_DISABLE_JIT=1`` — so results are the
interpreted results. Measured on the preview fleet worlds: one tail to 22 Jun in 13.2 s and one day in 0.31 s
without JIT (vs 6.4 s / 0.3 s with it). Only put this on PYTHONPATH where the real numba cannot be installed.
"""

__version__ = "0.0+shim"
SHIM = True


def njit(*args, **kwargs):
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]

    def deco(fn):
        return fn

    return deco


jit = njit
