"""M14 decision kernels (acceptance A5 "persistence and latch logic"): compiled == reference bitwise, chunk
invariance, the m-of-n debounce arithmetic against RADC-TR-81-220 Table 5-8, latch and clear behaviour, the
coloured-noise effect, and the limit monitor (persistence, hysteresis clear, peak, invalid samples)."""

from __future__ import annotations

from math import comb

import numpy as np
import pytest
from scipy import stats

from phalanx.monitoring.logic import (
    BIT_INTS,
    LIM_INTS,
    MODE_CONSECUTIVE,
    MODE_M_OF_N,
    bit_test_kernel,
    bit_test_reference,
    limit_kernel,
    limit_reference,
)

KW = {"phi": 0.5, "p_mix": 0.05, "k_mix": 3.0, "thr": 2.0, "mode": MODE_M_OF_N, "m": 3, "n": 4, "n_clear": 10}


def gen(*key):
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(1415, spawn_key=key)))


def fresh():
    return 0.0, np.zeros(len(BIT_INTS), np.int64)


@pytest.mark.unit
def test_bit_kernel_equals_reference_and_is_chunk_invariant():
    g = gen(1)
    nr, ur = g.standard_normal(3000), g.random(3000)
    a = bit_test_kernel(*fresh(), 0.4, nr, ur, **KW)
    b = bit_test_reference(*fresh(), 0.4, nr, ur, **KW)
    assert a[0] == b[0] and np.array_equal(a[1], b[1]) and a[2:] == b[2:]
    z, ist = fresh()
    first, off = -1, 0
    for idx in np.array_split(np.arange(3000), 9):
        z, ist, fd, _fc, _ = bit_test_kernel(z, ist, 0.4, nr[idx], ur[idx], **KW)
        if fd >= 0 and first < 0:
            first = off + fd
        off += idx.size
    assert z == a[0] and np.array_equal(ist, a[1]) and first == a[2]


def p_m_of_n(p, m, n):
    return sum(comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(m, n + 1))


@pytest.mark.unit
def test_m_of_n_arithmetic_matches_radc_table_5_8():
    """100 signals x 100 tests/h at ±2σ (two-sided, independent), non-overlapping windows: RADC Table 5-8
    gives
    454 (1-of-1), 10 (2-of-2), 0.90 (3-of-4), 0.04 (4-of-5) alarms per hour."""
    p = 2 * stats.norm.sf(2.0)
    for (m, n), table in (((1, 1), 454), ((2, 2), 10), ((3, 4), 0.90), ((4, 5), 0.04)):
        rate = 100 * (100 / n) * p_m_of_n(p, m, n)
        assert rate == pytest.approx(table, rel=0.1), (m, n, rate)


@pytest.mark.unit
def test_kernel_m_of_n_declaration_probability():
    """Independent Gaussian (φ = 0, no mixture), threshold 1σ (one-sided p = 0.1587), 3-of-4 window: the
    kernel's
    per-window declaration probability is the binomial tail 0.01408 (n = 20,000 fresh windows, 99 % CI)."""
    g = gen(2)
    nr, ur = g.standard_normal((20_000, 4)), g.random((20_000, 4))
    kw = {**KW, "phi": 0.0, "p_mix": 0.0, "thr": 1.0}
    hits = sum(bit_test_kernel(*fresh(), 0.0, nr[j], ur[j], **kw)[2] >= 0 for j in range(20_000))
    p = p_m_of_n(stats.norm.sf(1.0), 3, 4)
    lo, hi = stats.binom.ppf(0.005, 20_000, p), stats.binom.ppf(0.995, 20_000, p)
    assert lo <= hits <= hi, (hits, p * 20_000)


@pytest.mark.unit
def test_coloured_noise_raises_false_alarms_over_independent():
    """RADC lesson (R§9): independent-sample m-of-n arithmetic understates false alarms under coloured noise.
    Same threshold and 3-of-4 windows, 150 samples per flight: φ = 0.5 alarms more often than φ = 0
    (n = 3,000 flights each; one-sided two-proportion test p < 1e-3)."""
    counts = {}
    for phi in (0.0, 0.5):
        g = gen(3)
        k = 0
        for _ in range(3000):
            nr, ur = g.standard_normal(150), g.random(150)
            k += bit_test_kernel(*fresh(), 0.0, nr, ur, **{**KW, "phi": phi, "thr": 2.0})[2] >= 0
        counts[phi] = k
    p0, p1 = counts[0.0] / 3000, counts[0.5] / 3000
    pooled = (counts[0.0] + counts[0.5]) / 6000
    z = (p1 - p0) / np.sqrt(pooled * (1 - pooled) * 2 / 3000)
    assert z > 3.1, counts


@pytest.mark.unit
def test_consecutive_persistence_latch_and_clear():
    """n consecutive exceedances declare at the n-th; the test then latches (one declaration per flight) and
    reports a clear after n_clear consecutive passes."""
    nr = np.zeros(30)
    ur = np.ones(30)
    kw = {**KW, "mode": MODE_CONSECUTIVE, "n": 4, "n_clear": 5, "phi": 0.0, "p_mix": 0.0, "thr": 1.0}
    z, ist, fd, fc, nex = bit_test_kernel(*fresh(), 2.0, nr, ur, **kw)
    assert fd == 3 and fc == -1 and nex == 30
    z, ist, fd2, _fc2, _ = bit_test_kernel(z, ist, 2.0, nr, ur, **kw)
    assert fd2 == -1  # latched: no second declaration
    z, ist, fd3, fc3, _ = bit_test_kernel(z, ist, 0.0, nr, ur, **kw)
    assert fd3 == -1 and fc3 == 4
    # an interrupted run never reaches 4 in a row
    mu_series = np.array([2.0, 2.0, 2.0, 0.0] * 5)
    z, ist = fresh()
    for x in mu_series:
        z, ist, fd, *_ = bit_test_kernel(z, ist, x, nr[:1], ur[:1], **kw)
        assert fd == -1


@pytest.mark.unit
def test_limit_monitor_persistence_hysteresis_and_peak():
    t = np.arange(20, dtype=np.int64) * 100
    v = np.array([1, 5, 6, 1, 6, 7, 9, 8, 6, 5.0, 4.95, 4.9, 4.8, 4.7, 4.6, 4, 3, 2, 1, 0])
    ok = np.ones(20, bool)
    kw = {"limit": 5.5, "sense": 1.0, "hyst": 0.6, "n_persist": 3, "n_clear": 3}
    peak, ist, dec, clr, pk = limit_kernel(0.0, np.zeros(len(LIM_INTS), np.int64), t, v, ok, **kw)
    # 6 at j=2 is a 1-sample excursion (reset at j=3); 6, 7, 9 -> declared at j=6; cleared after 3 samples <
    # 4.9
    assert list(dec) == [6] and list(clr) == [14] and list(pk) == [9.0]
    ref = limit_reference(0.0, np.zeros(len(LIM_INTS), np.int64), t, v, ok, **kw)
    assert ref[0] == peak and np.array_equal(ref[1], ist) and np.array_equal(ref[2], dec)
    # chunks
    st = (0.0, np.zeros(len(LIM_INTS), np.int64))
    decs = []
    for idx in np.array_split(np.arange(20), 4):
        p_, i_, d_, _c, _ = limit_kernel(*st, t[idx], v[idx], ok[idx], **kw)
        st = (p_, i_)
        decs += list(idx[d_])
    assert decs == [6]
    # a low limit and invalid samples (an invalid sample resets the persistence count)
    v2 = np.array([10, 2, 2, 2, 10, 2, 2, 2.0])
    ok2 = np.array([1, 1, 1, 0, 1, 1, 1, 1], bool)
    _, _, dec2, _, _ = limit_kernel(
        0.0,
        np.zeros(len(LIM_INTS), np.int64),
        t[:8],
        v2,
        ok2,
        limit=3.0,
        sense=-1.0,
        hyst=0.0,
        n_persist=3,
        n_clear=1,
    )
    assert list(dec2) == [7]
