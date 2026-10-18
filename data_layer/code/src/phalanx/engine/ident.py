"""Identification hooks for W2.3/W2.4 (AD-34): transient-weighted residuals and complex-step Jacobians.

AD-34: engine dynamics are identified on transients with a loss that weights detected accel and decel steps
separately from steady levels (round 2 left decel schedule, fan lag and gas-path thermal lag at their bounds
under a level-dominated output-error fit). The building blocks:

- ``transient_weights``: per-sample weights from a driving signal (fuel command, PLA, ...): samples within
  ``window_s`` after a detected rise get ``w_accel``, after a detected fall ``w_decel``,
  the rest ``w_steady``.
- ``residuals``: weighted, scaled output-error residuals of a simulated window against measured outputs, as a
  function of selected kernel parameters (by name, ``layout.P_NAMES``).
- ``jacobian_cs``: d residuals / d parameters by complex step through the unchanged kernel (exact to
  rounding; finite differences fail on map kinks and limiter switches, W0.6 M5).

The windowed simulation itself is ``sim.simulate`` (same compiled kernel as the module).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .design import EngineModel
from .layout import PI, Y_NAMES
from .sim import EngineState, simulate


def transient_weights(
    signal: np.ndarray,
    dt: float,
    *,
    threshold: float,
    window_s: float = 5.0,
    rate_window_s: float = 1.0,
    w_accel: float = 5.0,
    w_decel: float = 5.0,
    w_steady: float = 1.0,
) -> np.ndarray:
    """Weights (L,) from a driving signal: a step is a change larger than ``threshold`` over
    ``rate_window_s``.

    Accel and decel windows are weighted separately (AD-34); overlapping windows take the larger weight."""
    s = np.asarray(signal, float)
    n = s.size
    k = max(1, round(rate_window_s / dt))
    d = np.zeros(n)
    d[k:] = s[k:] - s[:-k]
    w = np.full(n, float(w_steady))
    span = max(1, round(window_s / dt))
    for idx in np.flatnonzero(d > threshold):
        w[idx - k : idx - k + span] = np.maximum(w[idx - k : idx - k + span], w_accel)
    for idx in np.flatnonzero(d < -threshold):
        w[idx - k : idx - k + span] = np.maximum(w[idx - k : idx - k + span], w_decel)
    return w


def _p_with(model: EngineModel, names: Sequence[str], theta: np.ndarray) -> np.ndarray:
    dt = np.result_type(np.asarray(theta).dtype, np.float64)
    p = model.p.astype(dt)
    for nm, v in zip(names, theta, strict=True):
        p[PI[nm]] = v
    return p


def residuals(
    model: EngineModel,
    names: Sequence[str],
    theta: np.ndarray,
    state0: EngineState,
    u: np.ndarray,
    ui: np.ndarray,
    y_meas: np.ndarray,
    channels: Sequence[str],
    scales: Sequence[float],
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Weighted output-error residual vector (L * E * len(channels),) for kernel parameters ``names = theta``.

    ``y_meas`` is (L, E, len(channels)); ``weights`` (L,) from ``transient_weights`` (default 1). Complex
    ``theta`` propagates (complex step)."""
    p = _p_with(model, names, np.asarray(theta))
    f0 = state0.f.astype(p.dtype)
    buf0 = state0.buf.astype(p.dtype)
    r = simulate(model, EngineState(f0, state0.i, buf0), u, ui, p=p)
    cols = [Y_NAMES.index(c) for c in channels]
    sim = r.y[:, :, cols]
    sc = np.asarray(scales, float)
    w = np.ones(u.shape[0]) if weights is None else np.asarray(weights, float)
    res = (sim - y_meas) / sc * np.sqrt(w)[:, None, None]
    return res.reshape(-1)


def jacobian_cs(
    model: EngineModel,
    names: Sequence[str],
    theta: np.ndarray,
    state0: EngineState,
    u: np.ndarray,
    ui: np.ndarray,
    y_meas: np.ndarray,
    channels: Sequence[str],
    scales: Sequence[float],
    weights: np.ndarray | None = None,
    h: float = 1e-30,
) -> np.ndarray:
    """Complex-step Jacobian (n_residuals, n_params) of ``residuals`` with respect to ``theta``."""
    theta = np.asarray(theta, float)
    cols = []
    for j in range(theta.size):
        tc = theta.astype(np.complex128)
        tc[j] += 1j * h
        cols.append(residuals(model, names, tc, state0, u, ui, y_meas, channels, scales, weights).imag / h)
    return np.stack(cols, axis=1)
