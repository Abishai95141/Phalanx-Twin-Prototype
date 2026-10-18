"""Python-level driver of the M07 kernel: state construction, input blocks and windowed simulation.

This is the **transient-window simulation API** for identification (W2.3/W2.4, AD-34): given an initial state
and an input block over a window,
return outputs (and optionally the full station diagnostics). It calls the same
compiled kernel the module uses; ``compiled=False`` runs the kernel's outer loop uncompiled (``py_func``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .design import EngineModel
from .layout import (
    AB_LIT,
    AB_OFF,
    F_AB_DELAY,
    F_AB_TIMER,
    F_FLAME_TIMER,
    F_FLT0,
    F_SURGE_TIMER,
    FLT_OIL_LEVEL,
    I_AB,
    I_FLAME,
    N_W_ENGINE,
    NF,
    NI,
    NU,
    NUI,
    NX,
    U_NAMES,
    UI_ABEN,
    UI_IGN,
    X_WFM,
)
from .topology import kernel_functions


@dataclass(frozen=True)
class EngineState:
    """Kernel state for E engines: float state f (E, NF), int state i (E, NI), fuel-delay buffer (E, D)."""

    f: np.ndarray
    i: np.ndarray
    buf: np.ndarray

    def copy(self) -> EngineState:
        return EngineState(self.f.copy(), self.i.copy(), self.buf.copy())


def state_from_x(model: EngineModel, x: np.ndarray, *, n_engines: int = 1, ab_state: int = AB_OFF,
                 flame: int = 1, w_fm: float = 0.0) -> EngineState:  # fmt: skip
    """Kernel state with every engine at continuous state ``x`` (e.g. a steady state); the fuel-delay buffer
    is filled with the metered flow so the delay line is in equilibrium too."""
    x = np.asarray(x, float)
    f = np.zeros((n_engines, NF))
    f[:, :NX] = x
    f[:, F_AB_TIMER] = 0.0
    f[:, F_AB_DELAY] = 0.0
    f[:, F_SURGE_TIMER] = 0.0
    f[:, F_FLAME_TIMER] = 0.0
    f[:, F_FLT0 + FLT_OIL_LEVEL] = 1.0  # full oil charge; every other fault perturbation 0 (healthy)
    i = np.zeros((n_engines, NI), dtype=np.int64)
    i[:, I_AB] = ab_state
    i[:, I_FLAME] = flame
    nd = max(model.n_delay, 1)
    buf = np.full((n_engines, nd), x[X_WFM] * (1.0 + w_fm))
    return EngineState(f, i, buf)


def input_block(n_ticks: int, n_engines: int, base: np.ndarray, **series) -> tuple[np.ndarray, np.ndarray]:
    """Inputs (L, E, NU) from a base row plus per-channel overrides: a scalar, an (L,) series (all engines)
    or an (L, E) array. ``ignition`` / ``ab_enable`` set the int inputs (L, E,
    NUI); ignition defaults to 0."""
    u = np.broadcast_to(np.asarray(base, float), (n_ticks, n_engines, NU)).copy()
    ui = np.zeros((n_ticks, n_engines, NUI), dtype=np.int64)
    for name, val in series.items():
        v = np.asarray(val)
        if name == "w_engine":  # (5,), (E, 5) or (L, E, 5): layout.W_ENGINE_NAMES (AD-32, AD-46)
            lo = U_NAMES.index("w_fuel_metering")
            u[:, :, lo : lo + N_W_ENGINE] = np.broadcast_to(v, (n_ticks, n_engines, N_W_ENGINE))
            continue
        if name == "health":  # (10,), (E, 10) or (L, E, 10)
            lo = U_NAMES.index("h_fan_eta")
            u[:, :, lo:] = np.broadcast_to(v, (n_ticks, n_engines, u.shape[2] - lo))
            continue
        if v.ndim == 1:
            v = v[:, None]
        if name == "ignition":
            ui[:, :, UI_IGN] = v
        elif name == "ab_enable":
            ui[:, :, UI_ABEN] = v
        else:
            u[:, :, U_NAMES.index(name)] = v
    return u, ui


@dataclass(frozen=True)
class WindowResult:
    state: EngineState
    y: np.ndarray  # (L, E, NY) port outputs (layout.Y_NAMES)
    yi: np.ndarray  # (L, E, NYI) int outputs
    aux: np.ndarray  # (L, E, NAUX) diagnostics, or (1, E, NAUX) when not recorded


def simulate(
    model: EngineModel,
    state: EngineState,
    u: np.ndarray,
    ui: np.ndarray | None = None,
    *,
    z_ab: np.ndarray | None = None,
    record_aux: bool = False,
    compiled: bool = True,
    p: np.ndarray | None = None,
    n_sub: int | None = None,
) -> WindowResult:
    """Run the kernel over the window ``u`` (L, E, NU). ``z_ab`` (E, K) are the light-off draws for attempts
    starting at each engine's current attempt counter (default zeros = median delays); ``p`` overrides the
    parameter vector (calibration / complex step; then pass a complex ``state.f``)."""
    n_t, n_e = u.shape[0], u.shape[1]
    if ui is None:
        ui = np.zeros((n_t, n_e, NUI), dtype=np.int64)
    if z_ab is None:
        z_ab = np.zeros((n_e, n_t + 1))
    engine_kernel = kernel_functions(model)[0]  # topology hook (AD-43)
    k = engine_kernel if compiled else engine_kernel.py_func
    f, i, buf, y, yi, aux = k(
        state.f, state.i, state.buf, model.p if p is None else p, model.tables,
        np.ascontiguousarray(u), np.ascontiguousarray(ui), np.ascontiguousarray(z_ab), model.dt,
        model.n_sub if n_sub is None else n_sub, model.n_delay, bool(record_aux),
    )  # fmt: skip
    return WindowResult(EngineState(f, i, buf), y, yi, aux)


__all__ = ["AB_LIT", "EngineState", "WindowResult", "input_block", "simulate", "state_from_x"]
