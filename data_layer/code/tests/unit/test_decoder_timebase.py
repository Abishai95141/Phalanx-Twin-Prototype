"""Decoder time base (M17; A-W1.7-17): raw aircraft time vs causal best reconstruction, holdover, flags."""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from phalanx.ground.decoder.reader import TimeRecords
from phalanx.ground.decoder.timebase import TimeBase
from phalanx.recorder.timesource import Outage, RecorderClock, time_packets

NS = 10**9
T0 = 1_790_000_000 * NS


def _tb(clock, outages=(), t1=T0 + 60 * NS, rate_tol=100.0, holdover_s=300.0, mutate=None):
    tp = time_packets(clock, T0, t1, outages)
    rec = TimeRecords(
        rtc=np.array([p.rtc for p in tp], np.int64),
        utc_ms=np.array([p.utc_ms for p in tp], np.int64),
        fmt=np.zeros(len(tp), np.int64),
        src=np.array([p.src for p in tp], np.int64),
        day_format=np.zeros(len(tp), bool),
        sync_error=np.zeros(len(tp), bool),
    )
    if mutate:
        rec = mutate(rec)
    return TimeBase.from_records(
        rec, rate_tolerance_ppm=rate_tol, tail_tolerance_s=2.0, holdover_tolerance_s=holdover_s
    )


def test_locked_best_time_removes_the_crystal_offset():
    """+80 ppm recorder crystal: raw t_utc has the RCC sawtooth (up to 80 us); the best time, once a crystal
    rate is measured (after the second locked packet), is exact to ~1 RTC tick per second."""
    c = RecorderClock(1234, T0, Fraction(80))
    tb = _tb(c)
    t_true = T0 + NS + np.arange(0, 50_000) * 1_000_037  # from the second time packet on
    r = c.rtc(t_true)
    raw, internal, before = tb.raw_utc(r)
    best, fl = tb.best(r)
    assert np.abs(best - t_true).max() <= 250
    assert 70_000 < np.abs(raw - t_true).max() <= 81_000
    assert not (internal.any() or before.any() or fl.interpolated.any() or fl.suspect.any())
    first = c.rtc(np.array([T0 + 900_000_000]))  # first second: nominal rate only (no rate measured yet)
    assert abs(int(tb.best(first)[0][0]) - (T0 + 900_000_000)) < 80_000


def test_holdover_is_carried_on_the_pre_loss_crystal_rate_and_flagged():
    c = RecorderClock(0, T0, Fraction(-60))
    out = (Outage(T0 + 10 * NS + 300_000_000, T0 + 40 * NS + 700_000_000),)
    tb = _tb(c, out)
    t_true = T0 + np.arange(12, 39) * NS + 123_456_789
    r = c.rtc(t_true)
    raw, internal, _ = tb.raw_utc(r)
    best, fl = tb.best(r)
    assert internal.all() and fl.interpolated.all() and not fl.suspect.any()
    assert np.abs(best - t_true).max() <= 3_250  # rate known to ~1e-7: <= 100 ns per second of holdover
    assert np.abs(raw - t_true).max() > 1_000  # the free-running aircraft time drifted (60 ppm x 28 s)
    after = c.rtc(np.array([T0 + 45 * NS]))  # relocked: back to normal
    assert not tb.best(after)[1].suspect.any() and not tb.best(after)[1].interpolated.any()


def test_long_holdover_and_missing_time_packets_are_suspect():
    c = RecorderClock(0, T0, Fraction(10))
    out = (Outage(T0 + 50 * NS + 1, T0 + 120 * NS),)
    tb = _tb(c, out, holdover_s=3.0)
    _, fl = tb.best(c.rtc(np.array([T0 + 30 * NS, T0 + 52 * NS, T0 + 55 * NS])))
    assert fl.suspect.tolist() == [False, False, True]
    tb2 = _tb(c, (), t1=T0 + 10 * NS)
    _, fl2 = tb2.best(c.rtc(np.array([T0 + 10 * NS + 500_000_000, T0 + 13 * NS])))
    assert fl2.suspect.tolist() == [False, True]  # 0.5 s past the last packet is normal, 3.5 s is not


def test_a_time_jump_while_locked_is_suspect_causally():
    """Negative control: shift one locked packet's time by 1 ms -> the crystal rate measured at that packet
    and the next one is off by 1000 ppm -> CLOCK_SUSPECT after it, never before it (causal)."""
    c = RecorderClock(0, T0, Fraction(0))

    def shift(rec):
        ms = rec.utc_ms.copy()
        ms[20] += 1
        return TimeRecords(rec.rtc, ms, rec.fmt, rec.src, rec.day_format, rec.sync_error)

    tb = _tb(c, mutate=shift)
    t = (T0 + np.array([5, 19.5, 20.5, 21.5, 30]) * NS).astype(np.int64)
    _, fl = tb.best(c.rtc(t))
    assert fl.suspect.tolist() == [False, False, True, True, False]


def test_prefix_decoding_gives_the_same_times():
    """Causality: a time base built from a prefix of the time packets gives identical times and flags for
    every tag before the prefix's last packet."""
    c = RecorderClock(77, T0, Fraction(33))
    out = (Outage(T0 + 20 * NS, T0 + 26 * NS),)
    full = _tb(c, out)
    part = _tb(c, out, t1=T0 + 30 * NS)
    r = c.rtc(T0 + np.arange(1, 290) * 100_000_000)
    a_t, a_f = full.best(r)
    b_t, b_f = part.best(r)
    assert np.array_equal(a_t, b_t)
    assert np.array_equal(a_f.suspect, b_f.suspect) and np.array_equal(a_f.interpolated, b_f.interpolated)


def test_before_the_first_packet_and_day_format_are_suspect():
    c = RecorderClock(10_000_000, T0, Fraction(0))
    tb = _tb(c)
    _, fl = tb.best(np.array([0, 10_000_000 + 5]))
    assert fl.suspect.tolist() == [True, False]

    def dayfmt(rec):
        return TimeRecords(
            rec.rtc, rec.utc_ms, rec.fmt, rec.src, np.ones_like(rec.day_format), rec.sync_error
        )

    _, fl2 = _tb(c, mutate=dayfmt).best(np.array([10_000_000 + 5]))
    assert fl2.suspect.all()
