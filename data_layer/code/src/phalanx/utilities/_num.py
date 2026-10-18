"""Complex-step-safe scalar helpers for the M09 kernels (AD-22, AD-34).

Every comparison uses ``.real`` so the same compiled source runs on float64 (production) and complex128
(complex-step Jacobians). No ``abs``/``min``/``max`` builtins are applied to derivative-carrying values; these
helpers pick a branch by the real part and return the chosen operand unchanged, so its imaginary
(derivative) part propagates. ``np.exp``/``np.log``/``np.sqrt``/``**`` on scalars were checked bitwise equal
between Numba and the uncompiled reference on this platform (darwin-arm64, NumPy 2.5.4; see
``tests/unit/test_utilities_kernels.py``); ``tanh`` is deliberately not used (carry-forward note W0.2).
"""

from __future__ import annotations

from numba import njit

JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}


@njit(**JIT)
def cmax(a, b):
    """max(a, b) by real part (complex-step safe)."""
    return a if a.real >= b.real else b


@njit(**JIT)
def cmin(a, b):
    """min(a, b) by real part (complex-step safe)."""
    return a if a.real <= b.real else b


@njit(**JIT)
def clip(x, lo, hi):
    """Clamp x into [lo, hi] by real part (complex-step safe)."""
    return cmin(cmax(x, lo), hi)


@njit(**JIT)
def cabs(x):
    """|x| by the sign of the real part (complex-step safe)."""
    return x if x.real >= 0.0 else -x


@njit(**JIT)
def pos(x):
    """max(x, 0) keeping the operand's type (complex-step safe; ``x - x`` is +0, never -0, for finite x)."""
    return x if x.real > 0.0 else x - x
