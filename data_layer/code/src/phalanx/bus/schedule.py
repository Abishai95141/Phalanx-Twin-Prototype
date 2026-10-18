"""MIL-STD-1553B bus-controller schedule (architecture §6 M15, §8; rule R-RATE-AV).

The BC (the OAC on the avionics buses, ``buses.yaml``) runs a cyclic executive on its own oscillator:

- **minor frame** = one tick of the BC oscillator at the AV50 rate (50 Hz, rule R-RATE-AV);
- a message of rate group g is polled every ``d = f_minor / f_g`` minor frames (AV50: 1, AV25: 2, AV12.5: 4,
  AV6.25: 8, SLOW1: 50), in the minor frames with ``m mod d == phase``; the schedule repeats every
  ``H = lcm(d)`` minor frames (200 = 4 s here);
- sub-rate messages are spread over the phases to balance the minor-frame load (greedy, deterministic:
  least-loaded phase, ties to the smallest phase), which is how cyclic BC schedules are built
  [TRANSFER: Alta 1553 tutorial and Bloomy technical brief, data_pathway_and_formats.md Q2 "BC scheduling"];
- inside a minor frame the BC sends its messages back to back, fastest group first, then by RT/SA: a
  message starts when the previous one ends plus the BC inter-message gap.

Word timing (MIL-STD-1553B, DIRECT): 1 Mbit/s, 20 bit times (20 us) per word; an RT answers 4-12 us after
the command ("response time"); broadcast messages have no status response. Durations here use each RT's
own response time (a per-unit draw, ``clocks.STREAMS``), so offsets are exact per sortie.

Bus loading (the M15 acceptance criterion "<= 50 %", good practice per the Alta tutorial) is the fraction
of the hyper-period the bus is busy, including gaps.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .icd import BusIcd, Message1553

__all__ = ["GAP_TO_DEAD_NS", "WORD_NS", "BcSchedule", "build_schedule", "message_duration_ns"]

WORD_NS = 20_000  # 20 bit times at 1 Mbit/s (MIL-STD-1553B)
#: response time is measured mid-parity bit to mid-sync, so the dead bus time is 2 us less (MIL-STD-1553B;
#: data_pathway_and_formats.md Q2); the Ch10 GAP1 field uses the same definition (IRIG 106 §10.6.4.2).
GAP_TO_DEAD_NS = 2_000


def message_duration_ns(m: Message1553, response_ns: int) -> int:
    """First bit of the command word to the last bit of the last word (response_ns = GAP1 definition)."""
    if m.has_status:
        return WORD_NS * (1 + 1 + m.data_words) + int(response_ns) - GAP_TO_DEAD_NS
    return WORD_NS * (1 + m.data_words)


@dataclass(frozen=True)
class BcSchedule:
    """The cyclic schedule of one bus.

    Arrays (one row per poll slot of the hyper-period, sorted by frame then offset):
    ``msg`` (index into ``messages``), ``frame_mod`` (minor frame within the hyper-period) and ``offset_ns``
    (command start after the minor-frame tick).
    """

    bus: str
    minor_hz: Fraction
    hyper: int
    messages: tuple[Message1553, ...]
    divisor: np.ndarray  # per message
    phase: np.ndarray  # per message
    duration_ns: np.ndarray  # per message
    response_ns: np.ndarray  # per message (GAP1 definition; 0 for broadcast)
    msg: np.ndarray
    frame_mod: np.ndarray
    offset_ns: np.ndarray
    gap_ns: int
    frame_start_ns: int

    @property
    def minor_ns(self) -> float:
        return 1e9 / float(self.minor_hz)

    def frame_busy_ns(self) -> np.ndarray:
        """Busy time (messages plus inter-message gaps) per minor frame of the hyper-period."""
        busy = np.zeros(self.hyper, dtype=np.int64)
        np.add.at(busy, self.frame_mod, self.duration_ns[self.msg] + self.gap_ns)
        return busy

    def loading(self) -> float:
        """Mean bus loading over the hyper-period (0..1)."""
        if self.hyper == 0:
            return 0.0
        return float(self.frame_busy_ns().sum()) / (self.hyper * self.minor_ns)

    def peak_frame_loading(self) -> float:
        return float(self.frame_busy_ns().max(initial=0)) / self.minor_ns


def build_schedule(
    icd: BusIcd,
    bus: str,
    *,
    minor_hz: float | Fraction,
    group_hz: Mapping[str, float],
    response_ns: Mapping[int, int],
    gap_ns: int,
    frame_start_ns: int,
) -> BcSchedule:
    """The BC schedule of ``bus``.

    Args:
        minor_hz: minor-frame rate (the AV50 group rate).
        group_hz: rate of each bus group (dictionary ``rate_groups``).
        response_ns: RT address -> response time (ns) for this sortie's installed units.
        gap_ns: BC inter-message gap; frame_start_ns: first command after the minor-frame tick.
    """
    msgs = icd.messages_on(bus)
    minor = Fraction(minor_hz).limit_denominator(10**6)
    div = []
    for m in msgs:
        d = minor / Fraction(group_hz[m.group]).limit_denominator(10**6)
        if d.denominator != 1:
            raise ValueError(f"{m.msg_id}: group {m.group} is not an integer sub-rate of the minor frame")
        div.append(int(d))
    divisor = np.array(div, dtype=np.int64)
    hyper = math.lcm(*div) if div else 0
    resp = np.array([int(response_ns.get(m.rt, 0)) if m.has_status else 0 for m in msgs], dtype=np.int64)
    dur = np.array([message_duration_ns(m, int(r)) for m, r in zip(msgs, resp, strict=True)], dtype=np.int64)
    phase = np.zeros(len(msgs), dtype=np.int64)
    load = np.zeros(max(hyper, 1), dtype=np.int64)
    frames = np.arange(max(hyper, 1))
    for i in range(len(msgs)):  # icd order: fastest group first
        d = int(divisor[i])
        best, best_key = 0, None
        for p in range(d):
            sel = load[frames % d == p]
            key = (int(sel.max()), int(sel.sum()), p)
            if best_key is None or key < best_key:
                best, best_key = p, key
        phase[i] = best
        load[frames % d == best] += dur[i] + gap_ns
    rows_msg, rows_frame, rows_off = [], [], []
    for f in range(hyper):
        t = frame_start_ns
        for i in range(len(msgs)):
            if f % int(divisor[i]) == int(phase[i]):
                rows_msg.append(i)
                rows_frame.append(f)
                rows_off.append(t)
                t += int(dur[i]) + gap_ns
    sched = BcSchedule(
        bus=bus,
        minor_hz=minor,
        hyper=hyper,
        messages=msgs,
        divisor=divisor,
        phase=phase,
        duration_ns=dur,
        response_ns=resp,
        msg=np.array(rows_msg, dtype=np.int64),
        frame_mod=np.array(rows_frame, dtype=np.int64),
        offset_ns=np.array(rows_off, dtype=np.int64),
        gap_ns=int(gap_ns),
        frame_start_ns=int(frame_start_ns),
    )
    if hyper and sched.peak_frame_loading() >= 1.0:
        raise ValueError(f"{bus}: a minor frame overflows ({sched.peak_frame_loading():.2f} of the frame)")
    return sched
