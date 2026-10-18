"""Recorder RTC and time source (M16; IRIG 106 §10.6.1.1 i, §10.6.3)."""

from __future__ import annotations

import itertools
from fractions import Fraction

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.recorder.timesource import (
    EXTERNAL,
    INTERNAL,
    Outage,
    RecorderClock,
    lock_loss_episodes,
    time_packets,
)
from phalanx.recorder.writer import STREAMS

NS = 10**9
T0 = 1_790_000_000 * NS


@settings(max_examples=200, deadline=None)
@given(
    dt=st.integers(min_value=0, max_value=6 * 3600 * NS),
    ppb=st.integers(min_value=-100_000, max_value=100_000),
    rtc0=st.integers(min_value=0, max_value=(1 << 40) - 1),
)
def test_rtc_is_exact_against_rational_reference(dt, ppb, rtc0):
    """rtc(t) = rtc0 + floor((t - t_ref) * 1e7 (1 + Delta) / 1e9), exactly (int64 path vs rationals)."""
    c = RecorderClock(rtc0, T0, Fraction(ppb, 1000))
    ref = rtc0 + (Fraction(dt) * Fraction(10**7, 10**9) * (1 + Fraction(ppb, 10**9))).__floor__()
    assert c.rtc_at(T0 + dt) == ref
    r = c.rtc_at(T0 + dt)
    t = c.time_of(r)
    assert c.rtc_at(t) == r and (t == T0 or c.rtc_at(t - 1) < r)  # earliest instant showing that count


def test_rtc_vectorised_matches_scalar_and_rejects_the_past():
    c = RecorderClock(123, T0, Fraction(-17, 1))
    t = T0 + np.array([0, 1, 99, 100, 10**9, 3 * 3600 * NS + 7], dtype=np.int64)
    assert c.rtc(t).tolist() == [c.rtc_at(int(x)) for x in t.tolist()]
    with pytest.raises(ValueError):
        c.rtc(np.array([T0 - 1]))


def test_locked_time_packets_mark_every_true_second():
    c = RecorderClock(5_000, T0, Fraction(20))
    tp = time_packets(c, T0, T0 + 10 * NS, ())
    assert len(tp) == 10 and all(p.src == EXTERNAL for p in tp)
    assert [p.utc_ms for p in tp] == [(T0 + k * NS) // 10**6 for k in range(10)]
    d = np.diff([p.rtc for p in tp])
    assert np.all(np.abs(d - 10_000_200) <= 1)  # 1e7 ticks * (1 + 20 ppm) per true second


def test_holdover_free_runs_on_the_crystal_and_relocks_with_a_jump():
    """While unlocked: SRC internal, marks every 1e7 RTC ticks (fast crystal -> early marks); relock at the
    next true second, so the time carried jumps back by n * Delta seconds."""
    c = RecorderClock(0, T0, Fraction(50))  # +50 ppm
    out = (Outage(T0 + 3 * NS + 400_000_000, T0 + 9 * NS + 100_000_000),)
    tp = time_packets(c, T0, T0 + 15 * NS, out)
    src = [p.src for p in tp]
    assert src[:4] == [EXTERNAL] * 4 and INTERNAL in src
    internal = [p for p in tp if p.src == INTERNAL]
    assert np.all(np.diff([p.rtc for p in internal]) == 10_000_000)
    assert np.all(np.diff([p.utc_ms for p in internal]) == 1000)
    first_ext_after = next(p for p in tp if p.src == EXTERNAL and p.rtc > internal[-1].rtc)
    assert first_ext_after.utc_ms == (T0 + 10 * NS) // 10**6  # first true second at or after relock
    # the internal clock ran 50 ppm fast: its last mark claims a later time than the truth by n * 50 us
    n = len(internal)
    t_true_last = c.time_of(internal[-1].rtc)
    claimed = internal[-1].utc_ms * 10**6
    expected = n * 1e9 * (1 - 1 / (1 + 50e-6))  # n s claimed vs n / (1 + Delta) s elapsed
    assert abs((claimed - t_true_last) - expected) <= 101  # one RTC tick of capture granularity


def test_time_packets_require_a_locked_whole_second_start():
    c = RecorderClock(0, T0, Fraction(0))
    with pytest.raises(ValueError):
        time_packets(c, T0 + 1, T0 + 5 * NS, ())
    with pytest.raises(ValueError):
        time_packets(c, T0, T0 + 5 * NS, (Outage(T0 - NS, T0 + NS),))


def test_lock_loss_episodes_are_keyed_and_prefix_stable():
    rng = RngService(99, StreamRegistry(STREAMS))
    path = KeyPath.of(scenario="S", tail="T", sortie="X", subsystem="recorder", component="lock_loss")
    a = lock_loss_episodes(rng, path, T0, T0 + 4 * 3600 * NS, rate_per_h=2.0, median_s=20, sigma_ln=1.0)
    b = lock_loss_episodes(rng, path, T0, T0 + 8 * 3600 * NS, rate_per_h=2.0, median_s=20, sigma_ln=1.0)
    assert len(a) >= 2 and b[: len(a) - 1] == a[:-1]  # a longer recording only appends (CRN, I8)
    assert all(o.start < o.end for o in b) and all(x.end <= y.start for x, y in itertools.pairwise(b))
    assert lock_loss_episodes(rng, path, T0, T0 + NS, rate_per_h=0.0, median_s=20, sigma_ln=1.0) == ()


def test_lock_loss_rate_matches_poisson_rate():
    """n = 200 sortie keys x 4 h at 0.5/h: expected 400 episodes; Poisson 99.9 % band ~ +-62."""
    rng = RngService(7, StreamRegistry(STREAMS))
    total = 0
    for k in range(200):
        path = KeyPath.of(scenario="S", tail="T", sortie=f"X{k}", subsystem="recorder", component="lock_loss")
        total += len(
            lock_loss_episodes(rng, path, T0, T0 + 4 * 3600 * NS, rate_per_h=0.5, median_s=20, sigma_ln=1.0)
        )
    assert abs(total - 400) < 65
