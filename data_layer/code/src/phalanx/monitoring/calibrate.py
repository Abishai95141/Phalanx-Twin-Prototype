"""Calibration procedure of the BIT threshold regimes (A-W1.5-31): a fleet of healthy test units simulated
with exactly the M14 test model (``logic.bit_test_kernel`` with the M14 parameters: per-unit offset,
per-flight offset, AR(1) heavy-tailed statistic, m-of-n windows, one declaration per flight).

It answers "which threshold gives the target false-alarm behaviour?" faster than running the module, and it is
the procedure behind the regime values in ``configs/tejas/params/M14.yaml``:

- immature: 0.1-1 FH between false alarms (aircraft level) and 67-81 % of false-alarm episodes lasting one
  flight, 10-18 % lasting ≥ 3 flights (RADC-TR-81-220 Cat II persistence);
- mature: ≥ 50 FH between false alarms; gas-path EHM ≤ 1 per 1,000 flights.

Draws come from a Philox generator built from an explicit integer entropy (a calibration study, not a
simulation stream). The module-level statistical tests check the module against the same targets.
"""

from __future__ import annotations

import numpy as np

from phalanx.core.module import ParamSet

from .logic import BIT_INTS, MODE_M_OF_N, bit_test_kernel

__all__ = ["episode_lengths", "regime_thresholds", "simulate_test_fleet"]


def regime_thresholds(params: ParamSet, regime: str) -> tuple[float, int, int]:
    """(k, m, n) of ``regime`` ("immature" or "mature"; gas-path "ehm" tests use the mature thresholds with
    the baseline-corrected unit offset, see :func:`simulate_test_fleet`)."""
    if regime == "mature":
        return float(params.value("mat_k")), int(params.value("mat_m")), int(params.value("mat_n"))
    if regime == "immature":
        return float(params.value("imm_k")), int(params.value("imm_m")), int(params.value("imm_n"))
    raise ValueError(f"unknown regime {regime!r}")


def simulate_test_fleet(
    params: ParamSet,
    *,
    regime: str,
    n_units: int,
    n_flights: int,
    flight_s: float = 5400.0,
    entropy: int = 20261014,
    k_offset: float = 0.0,
) -> np.ndarray:
    """(n_units, n_flights) boolean: did unit u's test declare a false alarm on flight f (healthy units)."""
    k, m, n = regime_thresholds(params, "mature" if regime == "ehm" else regime)
    k = k - k_offset
    sb = float(params.value("ehm_unit_offset_sd" if regime == "ehm" else "unit_offset_sd"))
    se = float(params.value("flight_offset_sd"))
    rate = float(params.value("test_rate"))
    samples = int(np.floor(flight_s * rate))
    kw = {
        "phi": float(params.value("test_phi")),
        "p_mix": float(params.value("test_p_mix")),
        "k_mix": float(params.value("test_k_mix")),
        "thr": k,
        "mode": MODE_M_OF_N,
        "m": m,
        "n": n,
        "n_clear": int(params.value("n_clear")),
    }
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(entropy)))
    b = sb * g.standard_normal(n_units)
    out = np.zeros((n_units, n_flights), bool)
    for u in range(n_units):
        e = se * g.standard_normal(n_flights)
        for f in range(n_flights):
            nr = g.standard_normal(samples)
            ur = g.random(samples)
            _, _, fd, _, _ = bit_test_kernel(
                0.0, np.zeros(len(BIT_INTS), np.int64), b[u] + e[f], nr, ur, **kw
            )
            out[u, f] = fd >= 0
    return out


def episode_lengths(alarms: np.ndarray) -> np.ndarray:
    """Lengths (in flights) of runs of consecutive flights with a false alarm, per unit (row)."""
    out: list[int] = []
    for row in np.asarray(alarms, bool):
        run = 0
        for a in row:
            if a:
                run += 1
            elif run:
                out.append(run)
                run = 0
        if run:
            out.append(run)
    return np.array(out, np.int64)
