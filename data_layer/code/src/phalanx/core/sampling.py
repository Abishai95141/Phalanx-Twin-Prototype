"""Clock-domain sample buffers: how a module emits a variable number of samples per truth step.

A module that samples truth on its own oscillator (architecture §8; AD-36 "rate groups vs clock domains")
produces 0, 1 or more samples per truth step. Ports have fixed shapes, so the pattern is a **fixed-capacity
buffer plus explicit count and index ports** (never NaN padding — the contract has no NaN, architecture
§12 / §18 E1):

| Port | dtype, shape | Meaning |
|---|---|---|
| ``<name>``       | float64 ``(capacity,)``  | values in slots ``[0, n)``; slots ``>= n`` hold 0 |
| ``<name>_t``     | int64 ns ``(capacity,)`` | sample instants ``t_sample`` in slots ``[0, n)``; 0 beyond |
| ``<name>_n``     | int64 ``()``             | ``n``: number of valid samples this step |
| ``<name>_first`` | int64 ``()``             | absolute sample index of slot 0 (index = first + slot) |

Consumers read only ``[:n]``. The absolute sample index is also the stream index for per-sample noise
(AD-37), so noise never depends on which truth step a sample fell in. ``capacity`` comes from
:func:`max_samples_per_step`. :func:`samples_for_steps` assigns samples to steps with one arithmetic path
for a single step and for a block, so ``step`` == ``step_block`` holds by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .module import Port
from .time import NS_PER_S, TRUTH_HZ, ClockDomain


def max_samples_per_step(domain: ClockDomain, divisor: int = 1) -> int:
    """Most samples of ``domain`` that can fall in one module step of ``divisor`` truth frames.

    The longest such step is ``ceil(divisor * 1e9 / 240)`` ns; a half-open interval of length L holds at
    most ``floor(L / P) + 1`` samples of period P.
    """
    longest = -((-divisor * NS_PER_S) // TRUTH_HZ)
    p = domain.period_ns
    return (longest * p.denominator) // p.numerator + 1


def sample_ports(name: str, unit: str, capacity: int, domain: ClockDomain) -> tuple[Port, ...]:
    """The four ports of a sample buffer named ``name`` (see the module docstring)."""
    return (
        Port(name, unit, "<f8", (capacity,), domain),
        Port(f"{name}_t", "ns", "<i8", (capacity,), domain),
        Port(f"{name}_n", "1", "<i8", ()),
        Port(f"{name}_first", "1", "<i8", ()),
    )


@dataclass(frozen=True)
class StepSamples:
    """Samples of a clock domain falling in consecutive module steps ``[t_start[i], t_end[i])``."""

    first: int  # absolute index of the first sample (== n_next on entry)
    next_index: int  # absolute index of the first sample after the last step
    times: np.ndarray  # int64 (total,) sample instants, ns
    step: np.ndarray  # int64 (total,) which step each sample belongs to
    slot: np.ndarray  # int64 (total,) its slot in that step's buffer
    count: np.ndarray  # int64 (n_steps,) samples per step
    first_of_step: np.ndarray  # int64 (n_steps,) absolute index of each step's slot 0

    def pack(self, values: np.ndarray, capacity: int) -> tuple[np.ndarray, np.ndarray]:
        """Zero-filled (n_steps, capacity) value and time buffers for these samples."""
        n = self.count.size
        if n and int(self.count.max(initial=0)) > capacity:
            raise ValueError(f"{int(self.count.max())} samples in one step exceed capacity {capacity}")
        vals = np.zeros((n, capacity), dtype=np.float64)
        ts = np.zeros((n, capacity), dtype=np.int64)
        vals[self.step, self.slot] = values
        ts[self.step, self.slot] = self.times
        return vals, ts


def samples_for_steps(
    domain: ClockDomain, n_next: int, t_start: np.ndarray, t_end: np.ndarray
) -> StepSamples:
    """Assign samples ``n_next, n_next+1, ...`` to contiguous steps (``t_end[i] == t_start[i+1]``).

    ``n_next`` must be the first sample at or after ``t_start[0]`` (kept in module state, starting from
    ``domain.first_index_at_or_after(0)``); the returned ``next_index`` is the value to store back.
    """
    t_start = np.asarray(t_start, dtype=np.int64)
    t_end = np.asarray(t_end, dtype=np.int64)
    if t_start.size == 0:
        e = np.empty(0, np.int64)
        return StepSamples(n_next, n_next, e, e, e, e, e)
    n1 = domain.first_index_at_or_after(int(t_end[-1]))
    times = domain.sample_times_ns(n_next, n1 - n_next)
    step = np.searchsorted(t_end, times, side="right").astype(np.int64)
    count = np.bincount(step, minlength=t_start.size).astype(np.int64)
    before = np.cumsum(count) - count
    slot = np.arange(times.size, dtype=np.int64) - before[step]
    return StepSamples(n_next, n1, times, step, slot, count, n_next + before)
