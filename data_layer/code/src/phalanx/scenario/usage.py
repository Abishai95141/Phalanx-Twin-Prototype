"""Engine usage counting from a power-lever history (R§4 usage gates; AD-28 acceptance).

Definitions [TRANSFER: MIL-HDBK-1783B Table XI; RTO-TR-028 App. 1 (Maletta, GE)]:
- Type I (LCF): engine start -> IRP or above -> shutdown;
- Type III (FTC): idle -> IRP or above -> idle;
- Type IV (CIC): cruise -> IRP or above -> cruise;
- TAC = Type I + Type III / 4 + Type IV / 40;
- AB lights: entries into the afterburner range; time at/above IRP and in AB.

Counting [ASSUMPTION A-W1.1-28]: the PLA history is mapped onto four levels with 2 deg hysteresis -
OFF (< 10 deg, engine cut-off), IDLE (<= 37 deg: up to flight idle 31 deg + 6 deg), CRUISE, MAX (>= 87 deg,
IRP) - using the F404 PLA map [DIRECT: TM-4240 / TM-100159 for the HARV F404: flight idle 31 deg, IRP 87 deg,
minimum AB ~94 deg, maximum AB 130 deg; parameter_inventory.csv ENG.PLA]. Full cycles are extracted by
ASTM E1049 four-point rainflow on the closed level history (rotated to start at its maximum), then classified
by (valley, peak): (OFF, MAX) Type I, (IDLE, MAX) Type III, (CRUISE, MAX) Type IV.

The same function counts a planned PLA schedule (usage mode) and a realised PLA history (telemetry mode),
so the two can be compared (W2.1).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PLA_OFF_DEG, PLA_GI_DEG, PLA_FI_DEG, PLA_IRP_DEG, PLA_MIN_AB_DEG, PLA_MAX_AB_DEG = (
    0.0,
    18.0,
    31.0,
    87.0,
    94.0,
    130.0,
)
OFF, IDLE, CRUISE, MAX = 0, 1, 2, 3


@dataclass(frozen=True)
class Thresholds:
    """Level thresholds (deg) and hysteresis for usage counting [ASSUMPTION A-W1.1-28]."""

    off_hi: float = 10.0
    idle_hi: float = 37.0
    irp: float = PLA_IRP_DEG
    ab: float = PLA_MIN_AB_DEG
    hyst: float = 2.0


@dataclass(frozen=True)
class UsageCounts:
    type1: int
    type3: int
    type4: int
    ab_lights: int
    irp_s: float
    ab_s: float

    @property
    def tac(self) -> float:
        return self.type1 + self.type3 / 4.0 + self.type4 / 40.0


DEFAULT_THRESHOLDS = Thresholds()


def levels(pla_deg: np.ndarray, th: Thresholds = DEFAULT_THRESHOLDS) -> np.ndarray:
    """Level sequence with hysteresis. Up: OFF->IDLE at off_hi + hyst, IDLE->CRUISE at idle_hi + hyst,
    CRUISE->MAX at exactly IRP. Down: a level is left when the PLA falls below its lower boundary - hyst."""
    pla = np.asarray(pla_deg, dtype=float)
    bounds = (th.off_hi, th.idle_hi, th.irp)
    up = (th.off_hi + th.hyst, th.idle_hi + th.hyst, th.irp)
    out = np.empty(pla.size, dtype=np.int64)
    if pla.size == 0:
        return out
    cur = int(np.searchsorted(np.array(bounds), pla[0], side="right"))
    for k, p in enumerate(pla):
        while cur < 3 and p >= up[cur]:
            cur += 1
        while cur > 0 and p < bounds[cur - 1] - th.hyst:
            cur -= 1
        out[k] = cur
    return out


def _reversals(seq: list[int]) -> list[int]:
    comp = [seq[0]]
    for v in seq[1:]:
        if v != comp[-1]:
            comp.append(v)
    if len(comp) < 3:
        return comp
    rev = [comp[0]]
    for a, b, c in zip(comp, comp[1:], comp[2:], strict=False):
        if (b - a) * (c - b) < 0:
            rev.append(b)
    rev.append(comp[-1])
    return rev


def rainflow_cycles(level_seq: np.ndarray) -> list[tuple[int, int]]:
    """Full cycles (valley, peak) of a level history, treated as closed (ASTM E1049 four-point method on
    the history rotated to start and end at its maximum)."""
    seq = [int(x) for x in np.asarray(level_seq)]
    if not seq:
        return []
    rev = _reversals(seq)
    if len(rev) < 2:
        return []
    if rev[0] != rev[-1]:
        rev = [*rev, rev[0]]
    imax = int(np.argmax(rev))
    closed = rev[imax:] + rev[1 : imax + 1]
    closed = _reversals(closed)
    cycles: list[tuple[int, int]] = []
    stack: list[int] = []
    for v in closed:
        stack.append(v)
        while len(stack) >= 4:
            s1, s2, s3, s4 = stack[-4], stack[-3], stack[-2], stack[-1]
            r_in = abs(s3 - s2)
            if r_in <= abs(s2 - s1) and r_in <= abs(s4 - s3):
                cycles.append((min(s2, s3), max(s2, s3)))
                del stack[-3:-1]
            else:
                break
    # residue of a closed history rotated to its maximum: [max, ..., max] -> remaining pairs are full cycles
    while len(stack) >= 3:
        a, b = stack[-2], stack[-1]
        cycles.append((min(a, b), max(a, b)))
        del stack[-2:]
    return cycles


def count_usage(pla_deg: np.ndarray, dt_s: float, th: Thresholds = DEFAULT_THRESHOLDS) -> UsageCounts:
    """Usage counters of a PLA history sampled every ``dt_s`` seconds (see module docstring)."""
    pla = np.asarray(pla_deg, dtype=float)
    if pla.size == 0:
        return UsageCounts(0, 0, 0, 0, 0.0, 0.0)
    lev = levels(pla, th)
    t1 = t3 = t4 = 0
    for lo, hi in rainflow_cycles(lev):
        if hi == MAX:
            if lo == OFF:
                t1 += 1
            elif lo == IDLE:
                t3 += 1
            elif lo == CRUISE:
                t4 += 1
    in_ab = pla[0] >= th.ab
    lights = 0
    for p in pla[1:]:
        if not in_ab and p >= th.ab:
            in_ab = True
            lights += 1
        elif in_ab and p < th.ab - th.hyst:
            in_ab = False
    return UsageCounts(
        type1=t1,
        type3=t3,
        type4=t4,
        ab_lights=lights,
        irp_s=float(np.count_nonzero(pla >= th.irp) * dt_s),
        ab_s=float(np.count_nonzero(pla >= th.ab) * dt_s),
    )


__all__ = [
    "CRUISE",
    "IDLE",
    "MAX",
    "OFF",
    "PLA_FI_DEG",
    "PLA_GI_DEG",
    "PLA_IRP_DEG",
    "PLA_MAX_AB_DEG",
    "PLA_MIN_AB_DEG",
    "Thresholds",
    "UsageCounts",
    "count_usage",
    "levels",
    "rainflow_cycles",
]
