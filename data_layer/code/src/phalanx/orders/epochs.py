"""Decision epochs (architecture §11.1; report §14 "decision epochs are explicit and configurable").

Orders take effect only at decision epochs in simulation time: an order is applied at the first epoch at or
after ``max(t_issued, t_effective)``, never at its wall-clock arrival (AD-16). M18's own maintenance-control
review runs on the same calendar, so a reference policy acting through orders sees and acts at the same
instants as the built-in status quo (A3).

v1 epochs are daily local times (default: the 08:00 daily maintenance meeting, M21.yaml). Post-download epochs
are covered by the daily meeting in usage mode; a finer calendar is a configuration change.
"""

from __future__ import annotations

from dataclasses import dataclass

NS = 1_000_000_000
DAY_S = 86_400


def check_whole_second(t_ns: int, what: str = "time") -> int:
    if t_ns % NS:
        raise ValueError(f"{what} {t_ns} ns is not a whole second")
    return int(t_ns)


#: dispatch priorities at one instant (lower first): orders apply before the maintenance-control review, so an
#: order-issued action and the equivalent built-in decision act on the same pre-epoch state (A3).
PRIO_ORDER_SUBMIT = -30
PRIO_ORDER_APPLY = -20
PRIO_REVIEW = -10


@dataclass(frozen=True)
class DecisionCalendar:
    epoch_utc_ns: int
    tz_offset_s: int
    times_of_day_s: tuple[int, ...]

    def __post_init__(self) -> None:
        check_whole_second(self.epoch_utc_ns, "run epoch")
        if not self.times_of_day_s or any(not 0 <= x < DAY_S for x in self.times_of_day_s):
            raise ValueError("decision times must be seconds of the local day in [0, 86400)")
        if list(self.times_of_day_s) != sorted(set(self.times_of_day_s)):
            raise ValueError("decision times must be sorted and unique")

    def _local(self, t_ns: int) -> int:
        return (self.epoch_utc_ns + t_ns) // NS + self.tz_offset_s

    def next_epoch(self, t_ns: int) -> int:
        """First epoch time (kernel ns) at or after ``t_ns``."""
        loc = -((-(self.epoch_utc_ns + t_ns)) // NS) + self.tz_offset_s  # ceil to a whole second
        day = loc // DAY_S
        for d in (day, day + 1):
            for s in self.times_of_day_s:
                cand = d * DAY_S + s
                if cand >= loc:
                    return (cand - self.tz_offset_s) * NS - self.epoch_utc_ns
        raise AssertionError("unreachable")

    def epochs(self, t0_ns: int, t1_ns: int) -> list[int]:
        """All epochs in [t0, t1)."""
        out = []
        t = self.next_epoch(t0_ns)
        while t < t1_ns:
            out.append(t)
            t = self.next_epoch(t + NS)
        return out

    def is_epoch(self, t_ns: int) -> bool:
        return self.next_epoch(t_ns) == t_ns
