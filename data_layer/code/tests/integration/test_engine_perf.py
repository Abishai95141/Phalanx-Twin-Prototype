"""M07 performance (acceptance A9): microseconds per 240 Hz step for 1 and 2 engines.

Reference: the W0.6 representative workload ran 0.79 us/step (analysis/backend_benchmark/RESULTS.md, M1).
Budget: telemetry mode >= 50x real time per core for the whole chain (architecture §11) = 83 us per 240 Hz
step; the engine may use only part of it. Sample: 60 s of simulated time (14,400 steps) per configuration,
one warm-up run, then the median of 5 repetitions in this process (timings vary across sessions; W0.6 saw
up to 3x under load). Marked ``slow``: timing is reported, not part of ``make check``.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from phalanx.engine.design import build_engine_model
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.engine.steady import design_inputs, steady_state

W06_US_PER_STEP = 0.79
BUDGET_US_PER_STEP = 1e6 / (50.0 * 240.0)
N_STEPS = 240 * 60


def _median_us_per_step(model, n_engines: int, reps: int = 5) -> float:
    ss = steady_state(model, design_inputs(model))
    u, ui = input_block(N_STEPS, n_engines, ss.u)
    st = state_from_x(model, ss.x, n_engines=n_engines)
    simulate(model, st, u[:240], ui[:240])  # warm-up (JIT cache load)
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        simulate(model, st, u, ui)
        times.append(time.perf_counter() - t0)
    return float(np.median(times)) / N_STEPS * 1e6


@pytest.mark.slow
@pytest.mark.parametrize("n_engines", [1, 2, 4])
def test_a9_us_per_step(n_engines, record_property):
    """A9: report us/step (kernel path incl. the NumPy input feed) and the ratio to W0.6's 0.79 us/step;
    sanity bound: one engine uses less than the whole telemetry-mode step budget."""
    model = build_engine_model()
    us = _median_us_per_step(model, n_engines)
    record_property("us_per_step", round(us, 2))
    record_property("us_per_engine_step", round(us / n_engines, 2))
    record_property("ratio_to_w06", round(us / W06_US_PER_STEP, 1))
    record_property("x_real_time", round(1e6 / (us * 240.0), 0))
    print(f"\nA9 n_engines={n_engines}: {us:.2f} us/step, ratio to W0.6 {us / W06_US_PER_STEP:.1f}")
    assert us / n_engines < BUDGET_US_PER_STEP
