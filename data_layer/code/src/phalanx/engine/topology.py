"""M07 topology option dispatch (AD-43): which compiled kernel and point-derivative function a model uses.

``mixed_ab`` (Tejas F404-IN20) is the default and returns the original ``kernel.engine_kernel`` /
``kernel.deriv_point`` objects, so the Tejas path is unchanged (bitwise). ``separate_fixed`` (DASHlink proxy,
W2.4a) returns ``separate.engine_kernel_sf`` / ``separate.deriv_point_sf``. A model declares its topology with
a ``topology`` attribute (``separate_design.SeparateFixedModel``); a plain ``EngineModel`` is ``mixed_ab``.
"""

from __future__ import annotations

from collections.abc import Callable

from .kernel import deriv_point, engine_kernel

MIXED_AB = "mixed_ab"
SEPARATE_FIXED = "separate_fixed"
TOPOLOGIES = (MIXED_AB, SEPARATE_FIXED)


def topology_of(model) -> str:
    """The model's topology option (``mixed_ab`` unless the model says otherwise)."""
    t = getattr(model, "topology", MIXED_AB)
    if t not in TOPOLOGIES:
        raise ValueError(f"unknown M07 topology {t!r} (known: {TOPOLOGIES})")
    return t


def kernel_functions(model) -> tuple[Callable, Callable]:
    """(engine_kernel, deriv_point) of the model's topology (compiled dispatchers; ``.py_func`` =
    reference)."""
    if topology_of(model) == SEPARATE_FIXED:
        from .separate import deriv_point_sf, engine_kernel_sf

        return engine_kernel_sf, deriv_point_sf
    return engine_kernel, deriv_point


__all__ = ["MIXED_AB", "SEPARATE_FIXED", "TOPOLOGIES", "kernel_functions", "topology_of"]
