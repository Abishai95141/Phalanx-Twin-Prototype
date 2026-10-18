"""AD-35 time base: int64 nanoseconds, the 240 Hz truth grid, rate groups and LRU clock domains.

Normative sources:
- AD-35 (architecture §17): all times are int64 **nanoseconds**; truth step ``k`` sits at
  ``(k * 10**9) // 240`` ns (exact integer arithmetic, no cumulative drift); physics uses ``dt = 1/240`` s;
  LRU oscillator instants are computed in integer or rational arithmetic and floored to ns.
- Architecture §8 / AD-11 / report §7 ("Separate the truth integrator from LRU sampling"): one fixed
  240 Hz truth step (= 3x80 = 2x120 = 4x60); integer rate groups; each LRU samples truth on its **own
  drifting oscillator**, interpolating truth at its own tick.

Conventions fixed here (documented in ``core/README.md``):
- The timestamp of truth step ``k`` is the floored value ``t_k``; consecutive steps are 4,166,666 or
  4,166,667 ns apart (repeating 666, 667, 667). ``t_k`` is the canonical time of state ``x_k``.
- "Latest truth step at or before t" is ``max{k : t_k <= t}``; the interpolation weight toward step ``k+1``
  is the exact rational ``(t - t_k) / (t_{k+1} - t_k)`` on that ns grid, so sampling exactly at ``t_k``
  returns step ``k`` with weight 0 (no interpolation error at grid points).
- A clock domain with nominal frequency ``f``, fractional frequency offset ``Delta`` (ppm) and phase
  ``phi`` (ns) has sample instants ``t_n = floor(phi + n * 1e9 / (f * (1 + Delta*1e-6)))`` ns, n >= 0.
  Constant offset per domain per run [ASSUMPTION A-W0.2-1: on DASHlink one Delta explains all burst
  rates and the within-flight split-half difference is ~1.5 ppm SD, n = 152 flights (round-1 P2,
  MEASURED); oscillator aging, temperature drift and phase jitter are not modelled].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from functools import cached_property

import numpy as np

NS_PER_S: int = 1_000_000_000
TRUTH_HZ: int = 240
#: physics step in seconds (AD-35: physics uses dt = 1/240 s; the ns grid is floored separately)
TRUTH_DT_S: float = 1.0 / TRUTH_HZ

# (k * 10**9) // 240 == 4_166_666 * k + (2 * k) // 3   (10**9 / 240 = 4_166_666 + 2/3)
_STEP_Q: int = NS_PER_S // TRUTH_HZ  # 4_166_666
_INT64_MAX: int = 2**63 - 1
#: largest k whose timestamp fits in int64 (about 70,000 years of simulated time)
MAX_TRUTH_STEP: int = (_INT64_MAX - 1) // (_STEP_Q + 1)

Rational = Fraction | int | str | float


def _check_k(k: int, what: str = "step index") -> int:
    if isinstance(k, bool) or not isinstance(k, int | np.integer):
        raise TypeError(f"{what} must be an integer, got {type(k).__name__}")
    k = int(k)
    if k < 0:
        raise ValueError(f"{what} must be >= 0, got {k}")
    return k


def truth_step_time_ns(k: int) -> int:
    """Timestamp (ns, exact) of truth step ``k``: ``(k * 10**9) // 240`` (AD-35); exact for any int k."""
    k = _check_k(k)
    return (k * NS_PER_S) // TRUTH_HZ


def truth_step_times_ns(k: np.ndarray) -> np.ndarray:
    """Vectorised, exact ``truth_step_time_ns`` for an int64 array (overflow-checked).

    Uses ``4_166_666*k + (2*k)//3``, which equals ``(k*10**9)//240`` exactly and cannot overflow for
    ``0 <= k <= MAX_TRUTH_STEP``.
    """
    k = np.asarray(k)
    if k.dtype.kind not in "iu":
        raise TypeError(f"step indices must be integers, got dtype {k.dtype}")
    k = k.astype(np.int64, copy=False)
    if k.size and (int(k.min()) < 0 or int(k.max()) > MAX_TRUTH_STEP):
        raise OverflowError("step index outside [0, MAX_TRUTH_STEP]")
    return _STEP_Q * k + (2 * k) // 3


def latest_truth_step(t_ns: int) -> int:
    """``max{k : t_k <= t_ns}`` for ``t_ns >= 0``, exact.

    ``k*10**9 < 240*(t+1)``  <=>  ``k <= (3t+2) // 12_500_000``.
    """
    t = _check_k(t_ns, "time")
    return (3 * t + 2) // 12_500_000


def latest_truth_steps(t_ns: np.ndarray) -> np.ndarray:
    """Vectorised ``latest_truth_step`` (int64, exact for every non-negative int64 time).

    With ``t = 12.5e6*q + r``: ``(3t+2)//12.5e6 = 3q + (3r+2)//12.5e6`` (no intermediate overflow).
    """
    t = np.asarray(t_ns)
    if t.dtype.kind not in "iu":
        raise TypeError(f"times must be integers, got dtype {t.dtype}")
    if t.dtype == np.uint64 and t.size and int(t.max()) > _INT64_MAX:
        raise OverflowError("time exceeds int64")
    t = t.astype(np.int64, copy=False)
    if t.size and int(t.min()) < 0:
        raise ValueError("times must be >= 0")
    q, r = np.divmod(t, 12_500_000)
    return 3 * q + (3 * r + 2) // 12_500_000


def truth_interp(t_ns: int) -> tuple[int, Fraction]:
    """Latest truth step at or before ``t_ns`` and the exact weight toward step ``k+1``.

    ``value(t) = x_k + w * (x_{k+1} - x_k)`` with ``w = (t - t_k) / (t_{k+1} - t_k)`` in ``[0, 1)``.
    Linear interpolation between truth frames is [ASSUMPTION A-W0.2-2] (report §7; verify by step-halving).
    """
    k = latest_truth_step(t_ns)
    t0 = truth_step_time_ns(k)
    t1 = truth_step_time_ns(k + 1)
    return k, Fraction(int(t_ns) - t0, t1 - t0)


def truth_interp_weights(t_ns: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised ``truth_interp``: (k int64, w float64); ``w`` = correctly rounded ratio of exact ints."""
    t = np.asarray(t_ns).astype(np.int64, copy=False)
    k = latest_truth_steps(t)
    t0 = truth_step_times_ns(k)
    t1 = truth_step_times_ns(k + 1)
    # int64 -> float64 is exact for |x| < 2**53; IEEE division is correctly rounded (deterministic).
    w = (t - t0).astype(np.float64) / (t1 - t0).astype(np.float64)
    return k, w


# ---------------------------------------------------------------------------------------------- rate groups

TRUTH_DIVISORS: tuple[int, ...] = tuple(d for d in range(1, TRUTH_HZ + 1) if TRUTH_HZ % d == 0)


@dataclass(frozen=True, order=True)
class RateGroup:
    """An integer rate group of the 240 Hz truth loop: runs on steps ``k`` with ``k % divisor == phase``.

    Rate = 240/divisor Hz; e.g. divisor 3 = 80 Hz (DFCC frame, architecture §8), 24 = 10 Hz (ECMS10).
    Rates that do not divide 240 Hz (1553 at 50/12.5 Hz, FADEC 50-67 Hz) are *clock domains*
    (:class:`ClockDomain`), not rate groups.
    """

    divisor: int = 1
    phase: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.divisor, bool) or not isinstance(self.divisor, int):
            raise TypeError("divisor must be an int")
        if self.divisor not in TRUTH_DIVISORS:
            raise ValueError(f"rate-group divisor {self.divisor} does not divide {TRUTH_HZ}")
        if not (0 <= self.phase < self.divisor):
            raise ValueError(f"phase {self.phase} not in [0, {self.divisor})")

    @property
    def hz(self) -> Fraction:
        return Fraction(TRUTH_HZ, self.divisor)

    @property
    def dt_s(self) -> float:
        """Module step in seconds (correctly rounded ``divisor/240``)."""
        return self.divisor / TRUTH_HZ

    def runs_at(self, k: int) -> bool:
        return k % self.divisor == self.phase

    def ticks(self, k0: int, k1: int) -> np.ndarray:
        """Global step indices in ``[k0, k1)`` at which this group runs (int64)."""
        first = k0 + ((self.phase - k0) % self.divisor)
        return np.arange(first, k1, self.divisor, dtype=np.int64)

    def label(self) -> str:
        return f"RG{self.hz}" if self.phase == 0 else f"RG{self.hz}@{self.phase}"


RG_240 = RateGroup(1)
RG_120 = RateGroup(2)
RG_80 = RateGroup(3)
RG_60 = RateGroup(4)
RG_40 = RateGroup(6)
RG_20 = RateGroup(12)
RG_16 = RateGroup(15)
RG_10 = RateGroup(24)
RG_8 = RateGroup(30)
RG_4 = RateGroup(60)
RG_1 = RateGroup(240)


# ---------------------------------------------------------------------------------------------- clock domains


def as_fraction(x: Rational, what: str = "value") -> Fraction:
    """Exact rational from int / str / Fraction; floats go through ``repr`` (shortest round-trip decimal).

    ``Fraction(repr(917.6)) == Fraction(9176, 10)``: deterministic on every platform, and keeps
    denominators small (a raw binary float would give a 2**52 denominator).
    """
    if isinstance(x, bool):
        raise TypeError(f"{what}: bool is not a number")
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int | np.integer):
        return Fraction(int(x))
    if isinstance(x, float | np.floating):
        if not np.isfinite(x):
            raise ValueError(f"{what} must be finite")
        return Fraction(repr(float(x)))
    if isinstance(x, str):
        return Fraction(x)
    raise TypeError(f"{what}: cannot convert {type(x).__name__} to an exact rational")


_CHUNK_BUDGET = 2**62


@dataclass(frozen=True)
class ClockDomain:
    """An LRU / acquisition-unit oscillator (architecture §8, AD-06, AD-11, AD-35).

    Sample ``n`` (n >= 0) occurs at ``t_n = floor(phase_ns + n * period_ns)`` ns, with
    ``period_ns = 1e9 / (f_nom_hz * (1 + offset_ppm * 1e-6))``, all in exact rational arithmetic.
    No float accumulation: any ``t_n`` is computed directly from ``n``.

    ``offset_ppm`` is the per-unit fractional frequency offset (positive = fast oscillator, more samples per
    second). The DASHlink proxy value for recorder-vs-source is about 910 ppm [MEASURED, report §8].
    """

    name: str
    f_nom_hz: Rational
    offset_ppm: Rational = 0
    phase_ns: Rational = 0
    _period: Fraction = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        f = as_fraction(self.f_nom_hz, "f_nom_hz")
        d = as_fraction(self.offset_ppm, "offset_ppm")
        ph = as_fraction(self.phase_ns, "phase_ns")
        if f <= 0:
            raise ValueError("f_nom_hz must be > 0")
        if d <= -1_000_000:
            raise ValueError("offset_ppm must be > -1e6 (positive frequency)")
        if ph < 0:
            raise ValueError("phase_ns must be >= 0")
        object.__setattr__(self, "f_nom_hz", f)
        object.__setattr__(self, "offset_ppm", d)
        object.__setattr__(self, "phase_ns", ph)
        period = Fraction(NS_PER_S) / (f * (1 + d / 1_000_000))
        object.__setattr__(self, "_period", period)

    @property
    def period_ns(self) -> Fraction:
        return self._period

    @property
    def f_actual_hz(self) -> Fraction:
        return Fraction(NS_PER_S) / self._period

    @cached_property
    def _abd(self) -> tuple[int, int, int]:
        p, ph = self._period, self.phase_ns
        a = p.numerator * ph.denominator
        b = ph.numerator * p.denominator
        d = p.denominator * ph.denominator
        return a, b, d

    def sample_time_ns(self, n: int) -> int:
        """Exact ``floor(phase + n * period)`` in ns (Python int)."""
        n = _check_k(n, "sample index")
        a, b, d = self._abd
        return (n * a + b) // d

    def sample_times_ns(self, n0: int, count: int) -> np.ndarray:
        """Exact sample instants for ``n0 .. n0+count-1`` as int64, vectorised in overflow-safe chunks.

        Chunk start ``(Q, R) = divmod(n_c*A + B, D)`` is exact (Python ints); inside a chunk
        ``t = Q + j*(A//D) + (R + j*(A%D)) // D`` stays below 2**62 by the choice of chunk length.
        """
        n0 = _check_k(n0, "sample index")
        if count < 0:
            raise ValueError("count must be >= 0")
        a, b, d = self._abd
        aq, ar = divmod(a, d)
        chunk = max(1, _CHUNK_BUDGET // d - 1)
        out = np.empty(count, dtype=np.int64)
        pos = 0
        while pos < count:
            m = min(chunk, count - pos)
            q0, r0 = divmod((n0 + pos) * a + b, d)
            last = q0 + (m - 1) * aq + (r0 + (m - 1) * ar) // d
            if last > _INT64_MAX:
                raise OverflowError("sample time exceeds int64 ns")
            j = np.arange(m, dtype=np.int64)
            out[pos : pos + m] = q0 + j * aq + (r0 + j * ar) // d
            pos += m
        return out

    def first_index_at_or_after(self, t_ns: int) -> int:
        """Smallest ``n >= 0`` with ``t_n >= t_ns`` (exact)."""
        t = int(t_ns)
        x = (Fraction(t) - self.phase_ns) / self._period  # t_n >= t  <=>  phase + n*P >= t
        if x <= 0:
            return 0
        return -((-x.numerator) // x.denominator)  # ceil

    def index_at_or_before(self, t_ns: int) -> int:
        """Largest ``n`` with ``t_n <= t_ns``; -1 if the first sample is after ``t_ns``."""
        return self.first_index_at_or_after(int(t_ns) + 1) - 1

    def indices_in(self, t0_ns: int, t1_ns: int) -> tuple[int, int]:
        """Half-open index range ``[n0, n1)`` of samples with ``t0 <= t_n < t1``."""
        n0 = self.first_index_at_or_after(t0_ns)
        n1 = self.first_index_at_or_after(t1_ns)
        return n0, max(n0, n1)

    def describe(self) -> dict[str, str]:
        """Exact, canonical description (for config hashes and manifests)."""
        return {
            "name": self.name,
            "f_nom_hz": str(self.f_nom_hz),
            "offset_ppm": str(self.offset_ppm),
            "phase_ns": str(self.phase_ns),
        }
