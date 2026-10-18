"""Recorder relative time counter (RTC) and the aircraft time source behind the Ch10 time packets (M16).

**RTC** (IRIG 106 §10.6.1.1 i): a free-running 48-bit counter at 10 MHz from the recorder's own crystal, with
an arbitrary start value ("there is no constraint on the absolute value of the RTC", RCC 123-16 §5.6). The
crystal has a per-unit fractional offset ``Delta_rec`` (keyed by the recorder serial), so
``rtc(t) = rtc0 + floor((t - t_ref) * 1e7 (1 + Delta_rec) / 1e9)``, computed exactly in integers.

**Time source** (architecture §8 ``t_utc``; IRIG 106 §10.6.3): an external IRIG-B/GPS time code. While locked,
the recorder's time-code generator (TCG) writes one time packet per second at the source's on-time mark
(true UTC second boundary), SRC = external, header RTC = the RTC captured at the mark. On loss of lock the
TCG free-runs on the recorder crystal: marks every 10,000,000 RTC ticks after the last locked mark, time
value advancing one second per mark, SRC = internal (§10.6.3.2: "If the time source is external and lock
... is lost then the time source shall indicate Internal"). Its time therefore drifts by ``Delta_rec`` per
second; on relock the next external mark corrects it (a jump the ground decoder sees). Lock-loss episodes are
a Poisson process with lognormal durations (ASSUMPTION A-W1.7-9), drawn on an episode-indexed stream so the
episodes of a sortie do not depend on how long the recording is (CRN, I8).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from phalanx.core.rng import KeyPath, RngService

__all__ = [
    "EXTERNAL",
    "INTERNAL",
    "IRIG_B",
    "Outage",
    "RecorderClock",
    "TimePacket",
    "lock_loss_episodes",
    "time_packets",
]

RTC_HZ = 10_000_000
IRIG_B = 0x0
EXTERNAL = 0x1
INTERNAL = 0x0
_NS = 1_000_000_000
_SPLIT = 1 << 30


@dataclass(frozen=True)
class RecorderClock:
    """The recorder RTC: value ``rtc0`` at sim-UTC instant ``t_ref`` (ns), crystal offset ``offset_ppm``."""

    rtc0: int
    t_ref: int
    offset_ppm: Fraction

    @property
    def ratio(self) -> Fraction:
        """RTC ticks per ns of true time."""
        return Fraction(RTC_HZ, _NS) * (1 + self.offset_ppm / 1_000_000)

    def rtc(self, t_ns: np.ndarray) -> np.ndarray:
        """Exact ``rtc0 + floor((t - t_ref) * ratio)`` for t >= t_ref (int64, vectorised, overflow-safe)."""
        t = np.asarray(t_ns, dtype=np.int64)
        dt = t - np.int64(self.t_ref)
        if dt.size and int(dt.min()) < 0:
            raise ValueError("time before the RTC reference")
        a, b = self.ratio.numerator, self.ratio.denominator
        if a >= 8 * 10**9 or b >= 10**15:  # lo*a < 2**30 * 8e9 and r < b keep r + lo*a below 2**63
            raise OverflowError("RTC ratio too fine for the int64 path")
        hi, lo = np.divmod(dt, _SPLIT)
        uh, inv = np.unique(hi, return_inverse=True)
        qr = [divmod(int(h) * _SPLIT * a, b) for h in uh.tolist()]
        q = np.array([x[0] for x in qr], dtype=np.int64)[inv]
        r = np.array([x[1] for x in qr], dtype=np.int64)[inv]
        out = np.int64(self.rtc0) + q + (r + lo * np.int64(a)) // np.int64(b)
        if out.size and int(out.max()) >= 1 << 48:
            raise OverflowError("RTC exceeded 48 bits")
        return out.reshape(np.shape(t_ns))

    def rtc_at(self, t_ns: int) -> int:
        return int(self.rtc(np.array([t_ns], dtype=np.int64))[0])

    def time_of(self, rtc_value: int) -> int:
        """Earliest sim-UTC ns at which the RTC reads ``rtc_value`` (exact inverse of :meth:`rtc`)."""
        k = int(rtc_value) - self.rtc0
        if k < 0:
            raise ValueError("RTC value before the reference")
        r = self.ratio
        return self.t_ref + -((-k * r.denominator) // r.numerator)  # ceil(k / ratio)


@dataclass(frozen=True)
class Outage:
    """Time-source lock lost during ``[start, end)`` (sim-UTC ns)."""

    start: int
    end: int


@dataclass(frozen=True)
class TimePacket:
    """One time packet: header RTC, the time it carries (UTC ms since 1970) and its source code."""

    rtc: int
    utc_ms: int
    src: int


def lock_loss_episodes(
    rng: RngService,
    path: KeyPath,
    t0: int,
    t1: int,
    *,
    rate_per_h: float,
    median_s: float,
    sigma_ln: float,
    max_episodes: int = 10_000,
) -> tuple[Outage, ...]:
    """Poisson lock-loss episodes on ``[t0, t1)`` with lognormal durations.

    Episode i uses draws 2i (exponential gap from the end of episode i-1) and 2i+1 (duration) of the UNIFORM
    stream ``path``; episodes after ``t1`` are never drawn, so a longer recording only appends episodes.
    """
    if rate_per_h <= 0:
        return ()
    stream = rng.stream(path)
    nd = statistics.NormalDist()
    out = []
    t = int(t0)
    for i in range(max_episodes):
        u = stream.draws(2 * i, 2)
        gap_s = -math.log1p(-float(u[0])) * 3600.0 / rate_per_h
        start = t + int(gap_s * 1e9)
        if start >= t1:
            break
        z = nd.inv_cdf(min(max(float(u[1]), 1e-12), 1 - 1e-12))
        dur = int(median_s * math.exp(sigma_ln * z) * 1e9)
        end = start + max(dur, 1)
        out.append(Outage(start, min(end, int(t1))))
        t = end
    return tuple(out)


def time_packets(
    clock: RecorderClock, t0: int, t1: int, outages: tuple[Outage, ...]
) -> tuple[TimePacket, ...]:
    """Time packets of a recording on ``[t0, t1)``; ``t0`` must be a locked true-second boundary.

    Locked: one packet per true UTC second (SRC external). In an outage: the TCG free-runs from the last
    locked mark, one packet per 1e7 RTC ticks (SRC internal), until the first true second at or after the
    end of the outage.
    """
    if t0 % _NS:
        raise ValueError("a recording starts at a time-source on-time mark (whole second)")
    for o in outages:
        if o.start <= t0 < o.end:
            raise ValueError("the time source must be locked at the start of the recording")
    pk: list[TimePacket] = []
    s = t0
    oi = 0
    while s < t1:
        while oi < len(outages) and outages[oi].end <= s:
            oi += 1
        o = outages[oi] if oi < len(outages) else None
        if o is None or s < o.start:
            pk.append(TimePacket(clock.rtc_at(s), s // 1_000_000, EXTERNAL))
            s += _NS
            continue
        # free-run from the last locked mark (s - 1 s, which was < o.start)
        last = pk[-1]
        n = 1
        while True:
            r = last.rtc + n * RTC_HZ
            t_mark = clock.time_of(r)
            if t_mark >= o.end or t_mark >= t1:
                break
            pk.append(TimePacket(r, last.utc_ms + 1000 * n, INTERNAL))
            n += 1
        s = -(-o.end // _NS) * _NS  # first true second at or after relock
        oi += 1
    return tuple(pk)
