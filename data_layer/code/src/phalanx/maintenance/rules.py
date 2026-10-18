"""Status-quo maintenance-control decision rules as pure functions over a :class:`FleetView`.

The same function decides for M18's built-in maintenance control (open loop, view built from the tech log) and
for the reference ``StatusQuoPolicy`` acting through the orders channel (closed loop, view rebuilt from
contract records ``as_of`` the decision epoch). Identical views give identical decisions, which is what
acceptance A3 tests ("the status-quo policy reproduces the open-loop KPIs").

The view holds only maintenance-system knowledge (tech-log state that the records publish): never hidden
truth.

Cannibalisation rule (status quo, IAF-style Maintenance Control) [ASSUMPTION A-W1.8-13]:
- a recipient is a grounding job awaiting parts (AOG demand) for at least ``min_awp_s``;
- a donor is another tail at the same base that is already not mission capable (and not at depot), with the
  part class installed and no open defect against that part number ("known good");
- recipients are served oldest first; the donor that has been down longest is robbed first; each donor gives
  at most one part per epoch. [TRANSFER: GAO-02-86 (CANN to meet readiness from aircraft already down); NAMP
  CANN WOs only from Maintenance Control.]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .scir import NMC_CODES, NMCD


@dataclass(frozen=True)
class TailView:
    tail_no: str
    base: str
    state: int  # instantaneous SCIR state code (scir.STATES index)
    nmc_since: int  # kernel/abs ns of the last MC -> NMC transition (-1 when mission capable)
    installed: Mapping[str, int] = field(default_factory=dict)  # part_no -> installed count
    open_part_nos: frozenset[str] = frozenset()  # part numbers with an open defect on this tail


@dataclass(frozen=True)
class AwpJob:
    job_no: str
    tail_no: str
    base: str
    part_no: str
    t_awp: int  # when the job entered AWAITING_PARTS


@dataclass(frozen=True)
class FleetView:
    t: int
    tails: Mapping[str, TailView]
    awp: Sequence[AwpJob]


def cann_plan(view: FleetView, min_awp_s_ns: int) -> list[tuple[str, str]]:
    """Cannibalisation decisions at one epoch: [(recipient job_no, donor tail_no)] in execution order."""
    out: list[tuple[str, str]] = []
    used: set[str] = set()
    for job in sorted(view.awp, key=lambda j: (j.t_awp, j.job_no)):
        if view.t - job.t_awp < min_awp_s_ns:
            continue
        cands = []
        for tn in sorted(view.tails):
            tv = view.tails[tn]
            if tn == job.tail_no or tn in used or tv.base != job.base:
                continue
            if tv.state not in NMC_CODES or tv.state == NMCD:
                continue
            if tv.installed.get(job.part_no, 0) < 1 or job.part_no in tv.open_part_nos:
                continue
            cands.append((tv.nmc_since, tn))
        if cands:
            _, donor = min(cands)
            used.add(donor)
            used.add(job.tail_no)
            out.append((job.job_no, donor))
    return out
