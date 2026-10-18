"""SCIR-style availability: states, precedence, 15-minute binning and the KPI arithmetic (architecture §10).

Availability is **computed from job states, never asserted** (AD-20). Each tail has an instantaneous
mission-capability state derived from its open jobs; NAMP SCIR bins status into 15-minute increments of the
highest degraded priority, NMCD > NMCS > NMCM-U > NMCM-S > PMCS > PMCM > FMC [TRANSFER: NAMP 4790.2E §9.2].

MC% = (EIS - (NMCD + NMCS + NMCM)) / EIS; FMC% additionally subtracts PMCS and PMCM (NAMP §9.2 worked example:
12 aircraft, EIS 7,680 h, MC 62.5 %, FMC 30.0 %). IAF "serviceability %" (airworthy fraction; CAG 38/2015) is
mapped to MC% [ASSUMPTION A-W1.8-15: serviceable = mission capable].

This module is the **reference** implementation (pure functions over timelines). The incremental binning
inside the M18 module must agree with :func:`bin_states` exactly (property test).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

STATES: tuple[str, ...] = ("FMC", "PMCM", "PMCS", "NMCM_S", "NMCM_U", "NMCS", "NMCD")
RANK = {s: i for i, s in enumerate(STATES)}
FMC, PMCM, PMCS, NMCM_S, NMCM_U, NMCS, NMCD = range(7)
MC_CODES = frozenset({FMC, PMCM, PMCS})
NMC_CODES = frozenset({NMCM_S, NMCM_U, NMCS, NMCD})


def worse(a: int, b: int) -> int:
    """The more degraded of two state codes (SCIR precedence)."""
    return a if a >= b else b


@dataclass(frozen=True)
class TailFlags:
    """Job-derived facts about one tail at one instant (inputs to :func:`instantaneous_state`)."""

    at_depot: bool = False  # aircraft-level depot maintenance (HAL R&O)
    grounding_awp: bool = False  # a grounding job awaiting parts
    grounding_unscheduled: bool = False  # a grounding unscheduled job (open, awaiting maintenance, in work)
    grounding_scheduled: bool = False  # scheduled servicing / inspection in progress, or an order hold
    partial_awp: bool = False  # a non-grounding job awaiting parts
    partial_open: bool = False  # a non-grounding open or deferred job


def instantaneous_state(f: TailFlags) -> int:
    if f.at_depot:
        return NMCD
    if f.grounding_awp:
        return NMCS
    if f.grounding_unscheduled:
        return NMCM_U
    if f.grounding_scheduled:
        return NMCM_S
    if f.partial_awp:
        return PMCS
    if f.partial_open:
        return PMCM
    return FMC


def bin_states(
    changes: Sequence[tuple[int, int]], t0: int, t1: int, width: int, *, initial: int = FMC
) -> list[tuple[int, int]]:
    """Reference binning: the state of every bin overlapping [t0, t1), as (bin_start, state).

    Definition [A-W1.8-15]: the state of bin [b, b+w) is the most degraded of (the state carried into the bin)
    and every state entered by a change at b <= t < b+w (zero-duration states count: SCIR "highest degraded
    priority"). The incremental binning in the M18 module implements the same rule.

    Args: changes: (t, state) instantaneous state changes, sorted by time. t0, t1: window (absolute ns); bins
    are aligned to multiples of ``width``. initial: state before the first change.
    """
    out: list[tuple[int, int]] = []
    b = (t0 // width) * width
    i = 0
    cur = initial
    n = len(changes)
    while i < n and changes[i][0] < b:
        cur = changes[i][1]
        i += 1
    while b < t1:
        e = b + width
        worst = cur
        while i < n and changes[i][0] < e:
            cur = changes[i][1]
            worst = worse(worst, cur)
            i += 1
        out.append((b, worst))
        b = e
    return out


def occupancy(
    binned: Iterable[tuple[int, int]], width: int, *, t0: int | None = None, t1: int | None = None
) -> list[int]:
    """Seconds-weighted occupancy per state code from binned states (bins clipped to [t0, t1))."""
    occ = [0] * len(STATES)
    for b, s in binned:
        lo = b if t0 is None else max(b, t0)
        hi = b + width if t1 is None else min(b + width, t1)
        if hi > lo:
            occ[s] += hi - lo
    return occ


@dataclass(frozen=True)
class AvailabilityKpis:
    eis: int  # equipment-in-service time (ns, summed over tails)
    occupancy: tuple[int, ...]  # ns per state code

    @property
    def mc(self) -> float:
        nmc = sum(self.occupancy[c] for c in NMC_CODES)
        return (self.eis - nmc) / self.eis if self.eis else 0.0

    @property
    def fmc(self) -> float:
        return self.occupancy[FMC] / self.eis if self.eis else 0.0

    def fraction(self, state: str) -> float:
        return self.occupancy[RANK[state]] / self.eis if self.eis else 0.0


def kpis_from_occupancy(per_tail: Iterable[Sequence[int]]) -> AvailabilityKpis:
    tot = [0] * len(STATES)
    for occ in per_tail:
        for i, v in enumerate(occ):
            tot[i] += int(v)
    return AvailabilityKpis(eis=sum(tot), occupancy=tuple(tot))
