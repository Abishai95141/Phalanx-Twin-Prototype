"""AD-22 flat-vector layouts: named float64/int64 state vectors and a flat float64 parameter vector.

AD-22 (Numba): kernels take positional arrays, never dicts. A module's state is one float64 vector and one
int64 vector with name -> index constants; its kernel parameters are one flat float64 vector (calibratable
entries are perturbed by index). These helpers keep the names, the index constants and the
:class:`~phalanx.core.state.StateSchema` consistent, so the state still serialises through the normal
``get_state`` / ``set_state`` path (two fields, ``f`` and ``i``). See ``core/example_kernel.py``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

import numpy as np

from .module import ContractError, ParamSet
from .state import Field, State, StateSchema

_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class VectorLayout:
    """Ordered names of one flat vector -> indices."""

    def __init__(self, names: Sequence[str]) -> None:
        names = tuple(names)
        if len(set(names)) != len(names):
            raise ContractError(f"duplicate names in layout {names}")
        for n in names:
            if not _NAME_RE.match(n):
                raise ContractError(f"layout name {n!r} must match {_NAME_RE.pattern}")
        self.names = names
        self.index = {n: i for i, n in enumerate(names)}

    def __len__(self) -> int:
        return len(self.names)

    def check(self, **constants: int) -> None:
        """Assert that module-level index constants match the names (catch drift at import time)."""
        for name, idx in constants.items():
            if self.index.get(name) != idx:
                raise ContractError(
                    f"index constant for {name!r} is {idx}, layout says {self.index.get(name)}"
                )
        missing = sorted(set(self.names) - set(constants))
        if missing:
            raise ContractError(f"no index constant checked for {missing}")


class StateLayout:
    """A module state as ``{"f": float64[nf], "i": int64[ni]}`` with named entries."""

    def __init__(self, name: str, version: int, floats: Sequence[str], ints: Sequence[str]) -> None:
        self.f = VectorLayout(floats)
        self.i = VectorLayout(ints)
        overlap = sorted(set(self.f.names) & set(self.i.names))
        if overlap:
            raise ContractError(f"names in both vectors: {overlap}")
        self.schema = StateSchema(
            name, version, (Field("f", "<f8", (len(self.f),)), Field("i", "<i8", (len(self.i),)))
        )

    def pack(self, **values: float | int) -> State:
        """Build a state; every named entry must be given (no silent defaults)."""
        want = set(self.f.names) | set(self.i.names)
        if set(values) != want:
            raise ContractError(
                f"pack needs exactly {sorted(want)}; missing {sorted(want - set(values))}, "
                f"unknown {sorted(set(values) - want)}"
            )
        f = np.array([values[n] for n in self.f.names], dtype=np.float64)
        i = np.array([values[n] for n in self.i.names], dtype=np.int64)
        return {"f": f, "i": i}

    def unpack(self, state: Mapping[str, np.ndarray]) -> dict[str, float | int]:
        out: dict[str, float | int] = {n: float(state["f"][j]) for n, j in self.f.index.items()}
        out.update({n: int(state["i"][j]) for n, j in self.i.index.items()})
        return out


class ParamLayout(VectorLayout):
    """Kernel parameters as one read-only flat float64 vector, taken from a ParamSet by name."""

    def vector(self, params: ParamSet) -> np.ndarray:
        missing = [n for n in self.names if n not in params]
        if missing:
            raise ContractError(f"ParamSet {params.name} lacks kernel parameters {missing}")
        vals = []
        for n in self.names:
            v = params.value(n)
            if isinstance(v, bool) or not isinstance(v, int | float):
                raise ContractError(f"kernel parameter {n!r} must be a real scalar, got {type(v).__name__}")
            vals.append(float(v))
        vec = np.array(vals, dtype=np.float64)
        vec.flags.writeable = False
        return vec
