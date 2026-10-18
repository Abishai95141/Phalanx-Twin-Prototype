"""W0.2 A7 (property tier): time-base invariants over generated inputs (hypothesis, derandomized).

n per property = hypothesis max_examples (stated on each test); inputs span the full int64-exact ranges.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from phalanx.core.time import (
    MAX_TRUTH_STEP,
    NS_PER_S,
    ClockDomain,
    latest_truth_step,
    latest_truth_steps,
    truth_interp,
    truth_step_time_ns,
    truth_step_times_ns,
)

PROP = settings(max_examples=400, derandomize=True, deadline=None)


@pytest.mark.property
@PROP
@given(k=st.integers(0, MAX_TRUTH_STEP))
def test_truth_time_vector_equals_scalar_equals_rational(k):
    exact = Fraction(k * NS_PER_S, 240)
    assert truth_step_time_ns(k) == exact.numerator // exact.denominator
    assert int(truth_step_times_ns(np.array([k]))[0]) == truth_step_time_ns(k)


@pytest.mark.property
@PROP
@given(t=st.integers(0, truth_step_time_ns(MAX_TRUTH_STEP - 1)))
def test_latest_step_is_max_k_with_tk_le_t(t):
    k = latest_truth_step(t)
    assert truth_step_time_ns(k) <= t < truth_step_time_ns(k + 1)
    assert int(latest_truth_steps(np.array([t]))[0]) == k
    kk, w = truth_interp(t)
    assert kk == k and 0 <= w < 1


rational_hz = st.one_of(
    st.integers(1, 1000).map(Fraction),
    st.tuples(st.integers(1, 100_000), st.integers(1, 1000))
    .map(lambda a: Fraction(*a))
    .filter(lambda f: 0 < f <= 1000),
)
# |Delta| <= 2,000 ppm at 0.001 ppm resolution, plus the DASHlink-like values
ppm = st.one_of(
    st.integers(-2_000_000, 2_000_000).map(lambda a: Fraction(a, 1000)),
    st.sampled_from([Fraction(9176, 10), Fraction(910), Fraction(0)]),
)
phase = st.tuples(st.integers(0, 10**9), st.integers(1, 97)).map(lambda a: Fraction(*a))


@pytest.mark.property
@PROP
@given(f=rational_hz, d=ppm, ph=phase, n0=st.integers(0, 40_000_000), m=st.integers(1, 300))
def test_oscillator_vector_block_is_exact(f, d, ph, n0, m):
    """Any window of any domain (f <= 1 kHz, |Delta| <= 2,000 ppm, rational phase) equals exact floor.

    The window must lie inside the int64-ns range (AD-35, about 292 years). Windows beyond it must raise
    OverflowError, which is checked in `test_oscillator_window_beyond_int64_raises`.
    """
    dom = ClockDomain("p", f, d, ph)
    last = dom.phase_ns + (n0 + m - 1) * dom.period_ns
    assume(last.numerator // last.denominator < 2**63)
    t = dom.sample_times_ns(n0, m)
    for j in (0, m // 2, m - 1):
        exact = dom.phase_ns + (n0 + j) * dom.period_ns
        assert int(t[j]) == exact.numerator // exact.denominator
    assert np.all(np.diff(t) > 0)


@pytest.mark.property
def test_oscillator_window_beyond_int64_raises():
    """Regression for the W0.3-reported case: f = 1/925 Hz, n0 = 9,970,915, which is past 2**63 ns."""
    dom = ClockDomain("p", Fraction(1, 925), Fraction(0), Fraction(0))
    with pytest.raises(OverflowError):
        dom.sample_times_ns(9_970_915, 300)


@pytest.mark.property
@PROP
@given(f=rational_hz, d=ppm, ph=phase, t=st.integers(0, 36 * 10**12))
def test_oscillator_index_inverse(f, d, ph, t):
    dom = ClockDomain("p", f, d, ph)
    n = dom.index_at_or_before(t)
    if n >= 0:
        assert dom.sample_time_ns(n) <= t
    assert dom.sample_time_ns(n + 1) > t
    n0, n1 = dom.indices_in(t, t + 50_000_000)
    for i in range(n0, n1):
        assert t <= dom.sample_time_ns(i) < t + 50_000_000
