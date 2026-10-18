"""W0.2 A7: AD-35 time base is exact (truth grid, rate groups, oscillator schedules).

Sample sizes: the truth grid is checked exhaustively for every k in [0, 240*3600*100] (the A7 range,
86.4 M steps, chunked); oscillator schedules are scanned exhaustively over 10 h at 1 kHz (36 M samples,
chunked) plus exact Fraction checks at all chunk edges and 2,000 deterministic random indices.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from phalanx.core.time import (
    MAX_TRUTH_STEP,
    NS_PER_S,
    RG_80,
    TRUTH_DIVISORS,
    ClockDomain,
    RateGroup,
    as_fraction,
    latest_truth_steps,
    truth_interp,
    truth_interp_weights,
    truth_step_time_ns,
    truth_step_times_ns,
)

A7_K_MAX = 240 * 3600 * 100  # 100 h of truth steps


def _exact_floor(fr: Fraction) -> int:
    return fr.numerator // fr.denominator


@pytest.mark.unit
def test_truth_step_time_matches_definition_small():
    assert truth_step_time_ns(0) == 0
    assert truth_step_time_ns(1) == 4_166_666
    assert truth_step_time_ns(2) == 8_333_333
    assert truth_step_time_ns(3) == 12_500_000
    assert truth_step_time_ns(240) == NS_PER_S
    # step lengths repeat 666, 667, 667 (no cumulative drift: every 3 steps is exactly 12.5 ms)
    d = np.diff(truth_step_times_ns(np.arange(10)))
    assert d.tolist() == [4_166_666, 4_166_667, 4_166_667] * 3


@pytest.mark.unit
def test_truth_grid_exhaustive_to_100h():
    """Every k in [0, 240*3600*100]: vector formula == (k*1e9)//240 (exact in int64 for this range)."""
    chunk = 1 << 22
    starts = list(range(0, A7_K_MAX + 1, chunk))
    for k0 in starts:
        k = np.arange(k0, min(k0 + chunk, A7_K_MAX + 1), dtype=np.int64)
        ref = (k * NS_PER_S) // 240  # k*1e9 <= 8.64e16 < 2**63: exact reference
        np.testing.assert_array_equal(truth_step_times_ns(k), ref)
        if k0 in (starts[0], starts[-1]):
            # inverse on the first and last chunks: latest step at or before t_k is k; at t_k - 1, k - 1
            np.testing.assert_array_equal(latest_truth_steps(ref), k)
            np.testing.assert_array_equal(latest_truth_steps(ref[1:] - 1), k[1:] - 1)
    for k in (0, 1, 7, 86_399_999, A7_K_MAX, 10**12, MAX_TRUTH_STEP):
        assert truth_step_time_ns(k) == _exact_floor(Fraction(k * NS_PER_S, 240))


@pytest.mark.unit
def test_truth_grid_overflow_guard_and_types():
    with pytest.raises(OverflowError):
        truth_step_times_ns(np.array([MAX_TRUTH_STEP + 1]))
    with pytest.raises(ValueError):
        truth_step_time_ns(-1)
    with pytest.raises(TypeError):
        truth_step_time_ns(1.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        truth_step_times_ns(np.array([1.0]))
    # the vector path stays exact right up to the largest representable step
    k = np.array([MAX_TRUTH_STEP - 2, MAX_TRUTH_STEP - 1, MAX_TRUTH_STEP], dtype=np.int64)
    assert truth_step_times_ns(k).tolist() == [truth_step_time_ns(int(x)) for x in k]


@pytest.mark.unit
def test_interp_weights_exact_at_grid_and_between():
    k, w = truth_interp(truth_step_time_ns(5))
    assert (k, w) == (5, 0)
    t = truth_step_time_ns(5) + 1
    k, w = truth_interp(t)
    assert k == 5 and w == Fraction(1, truth_step_time_ns(6) - truth_step_time_ns(5))
    ts = np.array([0, 1, 4_166_665, 4_166_666, 4_166_667, 12_499_999, 12_500_000], dtype=np.int64)
    kk, ww = truth_interp_weights(ts)
    for t, kv, wv in zip(ts.tolist(), kk.tolist(), ww.tolist(), strict=True):
        ke, we = truth_interp(t)
        assert kv == ke and wv == float(we)  # float(Fraction) is correctly rounded, like the ratio
        assert 0.0 <= wv < 1.0


@pytest.mark.unit
def test_rate_groups():
    assert TRUTH_DIVISORS[:6] == (1, 2, 3, 4, 5, 6)
    assert RG_80.hz == 80 and RG_80.dt_s == 3 / 240
    with pytest.raises(ValueError):
        RateGroup(7)  # 240/7 Hz is not an integer rate group
    with pytest.raises(ValueError):
        RateGroup(3, 3)
    g = RateGroup(3, 1)
    assert g.ticks(0, 10).tolist() == [1, 4, 7]
    assert g.ticks(2, 11).tolist() == [4, 7, 10]
    assert [k for k in range(12) if g.runs_at(k)] == [1, 4, 7, 10]


def _scan_domain(dom: ClockDomain, n_total: int, chunk: int) -> None:
    """Exhaustive chunked scan: exact edges, step sizes in {floor P, ceil P}, chunk continuity."""
    p = dom.period_ns
    lo, hi = p.numerator // p.denominator, -((-p.numerator) // p.denominator)
    prev_last = None
    for n0 in range(0, n_total, chunk):
        m = min(chunk, n_total - n0)
        t = dom.sample_times_ns(n0, m)
        assert t[0] == _exact_floor(dom.phase_ns + n0 * p)
        assert t[-1] == _exact_floor(dom.phase_ns + (n0 + m - 1) * p)
        d = np.diff(t)
        assert d.min() >= lo and d.max() <= hi
        if prev_last is not None:
            assert lo <= t[0] - prev_last <= hi
        prev_last = int(t[-1])


@pytest.mark.unit
def test_oscillator_exact_over_10h_at_1khz():
    """A7: 10 h at f=1 kHz with a DASHlink-like 917.6 ppm offset and a rational phase, every sample."""
    dom = ClockDomain("lru", f_nom_hz=1000, offset_ppm="917.6", phase_ns=Fraction(12345, 7))
    n_total = 1000 * 3600 * 10 + 37_000  # a little beyond 10 h of nominal samples
    _scan_domain(dom, n_total, chunk=1 << 21)
    # exact Fraction check at deterministic random indices across the whole range (n = 2,000)
    idx = np.random.Generator(np.random.Philox(20261014)).integers(0, n_total, 2000)
    for n in idx.tolist():
        assert dom.sample_times_ns(n, 1)[0] == dom.sample_time_ns(n)
        assert dom.sample_time_ns(n) == _exact_floor(dom.phase_ns + n * dom.period_ns)


@pytest.mark.unit
def test_float_accumulation_would_fail():
    """Negative control: naive float64 ``phase + n*period`` is NOT exact over 10 h at 1 kHz.

    Shows the exactness test above can fail on an implementation that uses float arithmetic.
    """
    dom = ClockDomain("lru", f_nom_hz=1000, offset_ppm="917.6", phase_ns=Fraction(12345, 7))
    n = np.arange(36_000_000 - 200_000, 36_000_000, dtype=np.int64)
    exact = dom.sample_times_ns(int(n[0]), n.size)
    naive = np.floor(float(dom.phase_ns) + n.astype(np.float64) * float(dom.period_ns)).astype(np.int64)
    assert np.any(naive != exact)


@pytest.mark.unit
def test_oscillator_index_inverse_and_ranges():
    dom = ClockDomain("bc", f_nom_hz="12.5", offset_ppm=-40, phase_ns=1_000_000)
    assert dom.sample_time_ns(0) == 1_000_000
    assert dom.index_at_or_before(999_999) == -1
    assert dom.index_at_or_before(1_000_000) == 0
    for n in (0, 1, 2, 3, 12_345):
        t = dom.sample_time_ns(n)
        assert dom.index_at_or_before(t) == n
        assert dom.index_at_or_before(t - 1) == n - 1
        assert dom.first_index_at_or_after(t) == n
        assert dom.first_index_at_or_after(t + 1) == n + 1
    n0, n1 = dom.indices_in(0, NS_PER_S)
    assert (n0, n1) == (0, 13)  # samples at 1 ms + n*80.0032 ms < 1 s: n = 0..12
    assert dom.indices_in(5, 5) == (dom.first_index_at_or_after(5),) * 2


@pytest.mark.unit
def test_float_parameters_convert_via_repr():
    assert as_fraction(917.6) == Fraction(9176, 10)
    assert as_fraction("917.6") == Fraction(9176, 10)
    assert ClockDomain("x", 12.5, 917.6) == ClockDomain("x", "12.5", "917.6")
    with pytest.raises(TypeError):
        as_fraction(True)
    with pytest.raises(ValueError):
        ClockDomain("x", 0)
    with pytest.raises(ValueError):
        ClockDomain("x", 10, phase_ns=-1)


@pytest.mark.unit
def test_clock_slip_period_is_one_over_f_delta():
    """The oscillator model reproduces the slip mechanism of report §8 / architecture §8 (AD-06).

    A recorder reading at f = 8 Hz on its own clock, a source updating at 8 Hz with a relative offset of
    910 ppm: reads that see 0 or 2 new source updates ("slips") recur every 1/(f*Delta) = 137.4 s
    (DASHlink burst interval at 8 Hz: 137 s [MEASURED, report §8 table]).
    """
    f, delta_ppm = 8, 910
    src = ClockDomain("source", f, offset_ppm=delta_ppm)
    rec = ClockDomain("recorder", f, offset_ppm=0, phase_ns=Fraction(1, 3) * NS_PER_S / f)
    n_rec = 8 * 3600  # 1 h of reads
    t_read = rec.sample_times_ns(0, n_rec)
    n_src_seen = np.array([src.index_at_or_before(int(t)) for t in t_read])
    updates_between_reads = np.diff(n_src_seen)
    slips = np.flatnonzero(updates_between_reads != 1)
    gaps_s = np.diff(t_read[slips + 1]) / NS_PER_S
    expected = 1.0 / (f * delta_ppm * 1e-6)  # exact beat 1/(f_src - f_rec) = 1/(f*Delta) = 137.4 s
    assert len(slips) >= 20
    assert np.all(np.abs(gaps_s - expected) <= 1.0 / f + 1e-9)
