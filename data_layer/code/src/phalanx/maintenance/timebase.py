"""Operations-layer time helpers: whole-second times, local days, working-time calendars, availability bins.

All operations-layer (M18/M21/M22) event times are **whole seconds** on the kernel clock (multiples of 1e9
ns), so they fall exactly on a 240 Hz truth frame (k = 240 s) and usage-mode dispatch is exact (AD-35;
A-W0.2-3 has no effect). Contract times are ``epoch_utc_ns + t`` (AD-38); the run epoch must itself be a whole
second. [ASSUMPTION A-W1.8-14: 1 s resolution for maintenance and order times; real records use minutes.]
"""

from __future__ import annotations

from dataclasses import dataclass

NS = 1_000_000_000
HOUR_S = 3_600
DAY_S = 86_400


def to_s(seconds: float) -> int:
    """Seconds -> whole seconds (round half to even; deterministic)."""
    return round(float(seconds))


def ns(seconds: int) -> int:
    return int(seconds) * NS


def check_whole_second(t_ns: int, what: str = "time") -> int:
    if t_ns % NS:
        raise ValueError(f"{what} {t_ns} ns is not a whole second (operations-layer times are whole seconds)")
    return int(t_ns)


@dataclass(frozen=True)
class WorkCalendar:
    """Local working window per day (e.g. 06:00-22:00 IST); times in kernel ns (whole seconds).

    ``add_work(t, d)`` returns the end of ``d`` working seconds started at ``t``; work outside the window is
    paused overnight. A 24 h window means continuous work.
    """

    epoch_utc_ns: int
    tz_offset_s: int
    start_s: int
    end_s: int

    def __post_init__(self) -> None:
        check_whole_second(self.epoch_utc_ns, "run epoch")
        if not (0 <= self.start_s < self.end_s <= DAY_S):
            raise ValueError("working window must satisfy 0 <= start < end <= 24 h")

    @property
    def continuous(self) -> bool:
        return self.start_s == 0 and self.end_s == DAY_S

    def local_s(self, t_ns: int) -> int:
        """Local wall-clock seconds since the Unix epoch at kernel time ``t_ns``."""
        return (self.epoch_utc_ns + t_ns) // NS + self.tz_offset_s

    def local_day(self, t_ns: int) -> int:
        return self.local_s(t_ns) // DAY_S

    def kernel_ns_of_local(self, local_s: int) -> int:
        return (local_s - self.tz_offset_s) * NS - self.epoch_utc_ns

    def next_local_time(self, t_ns: int, second_of_day: int) -> int:
        """First kernel time >= t whose local time of day is ``second_of_day``."""
        loc = self.local_s(t_ns)
        day = loc // DAY_S
        cand = day * DAY_S + second_of_day
        if cand < loc:
            cand += DAY_S
        return max(self.kernel_ns_of_local(cand), t_ns)

    def add_work(self, t_ns: int, work_s: int) -> int:
        check_whole_second(t_ns)
        if work_s <= 0:
            return t_ns
        if self.continuous:
            return t_ns + work_s * NS
        loc = self.local_s(t_ns)
        left = int(work_s)
        while True:
            day = loc // DAY_S
            sod = loc - day * DAY_S
            if sod < self.start_s:
                loc = day * DAY_S + self.start_s
                continue
            if sod >= self.end_s:
                loc = (day + 1) * DAY_S + self.start_s
                continue
            room = self.end_s - sod
            if left <= room:
                loc += left
                return self.kernel_ns_of_local(loc)
            left -= room
            loc = (day + 1) * DAY_S + self.start_s

    def working_seconds(self, t0_ns: int, t1_ns: int) -> int:
        """Working seconds inside [t0, t1)."""
        if t1_ns <= t0_ns:
            return 0
        if self.continuous:
            return (t1_ns - t0_ns) // NS
        a, b = self.local_s(t0_ns), self.local_s(t1_ns)
        total = 0
        day = a // DAY_S
        while day * DAY_S < b:
            w0, w1 = day * DAY_S + self.start_s, day * DAY_S + self.end_s
            lo, hi = max(a, w0), min(b, w1)
            if hi > lo:
                total += hi - lo
            day += 1
        return total


def bin_start(abs_ns: int, width_ns: int) -> int:
    """Start (absolute UTC ns) of the availability bin containing ``abs_ns`` (bins aligned to the Unix
    epoch)."""
    return (abs_ns // width_ns) * width_ns
