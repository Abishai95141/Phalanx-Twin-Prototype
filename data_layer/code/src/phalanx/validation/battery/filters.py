"""Zero-phase low-pass used by B1 and B6 (port of round-1
`analysis/settling_experiment/src/pipeline.lowpass`).

Butterworth order 4, applied forward-backward with `sosfiltfilt`. Padding is an odd extension of
3 filter time constants (3 * rate / fc samples) instead of scipy's default, so the slow band has no start-up
transient at the record edges (round-1 DEVIATIONS.md C3). Records shorter than 64 samples return their mean.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.signal import butter, sosfiltfilt

from phalanx.validation.battery.config import BUTTER_ORDER

__all__ = ["lowpass"]


@lru_cache(maxsize=32)
def _sos_cached(order: int, fc: float, rate: float) -> np.ndarray:
    return butter(order, fc, btype="low", fs=rate, output="sos")


def _sos(order: int, fc: float, rate: float) -> np.ndarray:
    # a private copy: scipy's sosfilt needs a writable buffer, and the cache must never be mutated
    return _sos_cached(order, fc, rate).copy()


def lowpass(x: np.ndarray, rate: float, fc: float, order: int = BUTTER_ORDER) -> np.ndarray:
    """Zero-phase Butterworth low-pass of a 1-D series.

    Args:
        x: samples (any unit), uniform grid.
        rate: sample rate [Hz].
        fc: cut-off frequency [Hz].
        order: Butterworth order (pre-registered 4).
    """
    sos = _sos(order, float(fc), float(rate))
    if x.size < 64:
        return np.full(x.size, x.mean())
    return sosfiltfilt(sos, x, padlen=min(x.size - 1, int(np.ceil(3 * rate / fc))))
