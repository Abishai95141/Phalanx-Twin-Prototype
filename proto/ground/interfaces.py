"""Shared interfaces of the ground side (our system). Every lane codes against these; change them only in S1.

Hard rules (RULES.md): read only through ``AsOfStore.as_of(t, …)`` (``t_ingest ≤ t``); never import the
``phalanx`` data layer or ``proto/eval``; never open ``_restricted_labels/``; key fleet records by
(``tail_no``, ``record_id``) and serials by (``tail_no``, ``serial_no``); decisions leave only as orders.

Times are UTC nanoseconds (int) everywhere, as in the contract. Display in IST happens in the API layer.
The JSON the screens read keeps the ``window.PHX_*`` shapes of ``proto/web/assets/data*.js`` — those files are
the reference shapes for ``/api`` responses.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

import pyarrow as pa

NS = 10**9
DAY = 86_400 * NS


# ---- sources and labels ----------------------------------------------------------------------------------
class Source(StrEnum):
    """Where a record or a derived value comes from. Shown next to every value on the screens."""

    FLEET = "fleet"  # live simulated fleet (the data layer's tail worlds, stepped by the runner)
    TRAIN = "train"  # simulated fleet history: extra-seed training worlds
    OVERLAY = "overlay"  # generated engine trend (overlay v0.1)


SOURCE_LABEL = {
    Source.FLEET: "Simulated fleet",
    Source.TRAIN: "Simulated fleet history",
    Source.OVERLAY: "Generated engine trend (overlay v0.1)",
}


# ---- the only read path ----------------------------------------------------------------------------------
class AsOfStore(Protocol):
    def as_of(
        self,
        t: int,
        topic: str,
        *,
        tail_no: str | None = None,
        source: Source = Source.FLEET,
        world_seed: int | None = None,
    ) -> pa.Table:
        """Rows of ``topic`` with ``t_ingest ≤ t``: deduplicated by (``tail_no``, ``record_id``) keeping the
        earliest ingest; SENTINEL values masked to null; ``validity != NORMAL`` values null; OUT_OF_RANGE kept.
        Columns are the contract's, read by name, plus ``_source``."""
        ...

    def snapshot_id(self, t: int) -> str:
        """Content hash of the set of part files that hold rows ingested by ``t`` (seals an epoch)."""
        ...


# ---- twin state -------------------------------------------------------------------------------------------
class Availability(StrEnum):
    FMC = "FMC"
    PMC = "PMC"
    NMCM = "NMCM"
    NMCS = "NMCS"
    NMCD = "NMCD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Belief:
    """One model output about a serial or an issue, always with its provenance."""

    name: str  # e.g. "p_confirmed", "p_rtok_if_removed", "removal_risk_30d", "egt_margin_c"
    value: float | None  # None = INSUFFICIENT_EVIDENCE
    lo: float | None = None
    hi: float | None = None
    n: int | None = None  # sample size behind it
    model_id: str = ""
    model_version: str = ""
    source: Source = Source.FLEET
    note: str = ""


@dataclass(frozen=True)
class Installed:
    position: str
    serial_no: str
    part_no: str | None
    since: int | None
    inferred: bool = False  # True when the install record is not yet ingested (position taken from a job)


@dataclass(frozen=True)
class AlarmStat:
    code: str
    count: int
    last_seen: int
    consecutive_sorties: int
    severity: str


@dataclass(frozen=True)
class TailState:
    tail_no: str
    base: str | None
    as_of: int
    snapshot_id: str
    last_ingest: int | None
    status: Availability
    status_since: int | None
    down_reason: str | None  # "part" | "work" | "decision" | "inspection" | None
    sorties: int
    flight_hours: float
    landings: int
    sorties_30d: int
    flight_hours_30d: float
    installed: tuple[Installed, ...]
    open_jobs: tuple[str, ...]
    open_demands: tuple[str, ...]
    alarms: tuple[AlarmStat, ...]
    issue_ids: tuple[str, ...]


@dataclass(frozen=True)
class SerialHistoryEntry:
    tail_no: str
    position: str | None
    installed: int | None
    removed: int | None
    job_no: str | None
    finding: str | None  # RTOK | CONFIRMED | BCM | None


@dataclass(frozen=True)
class SerialState:
    tail_no: str  # world scope in the preview: serials are keyed (tail_no, serial_no)
    serial_no: str
    part_no: str | None
    klass: str | None
    history: tuple[SerialHistoryEntry, ...]
    hours_since_install: float | None
    cycles_since_install: float | None
    beliefs: tuple[Belief, ...]


@dataclass(frozen=True)
class FleetState:
    as_of: int
    snapshot_id: str
    tails: Mapping[str, TailState]
    kpis_30d: Mapping[str, float]  # mc, fmc, tnmcm, tnmcs, nmcd (share of possessed time)
    kpis_all: Mapping[str, float]
    mc_daily: Sequence[tuple[str, float]]  # (IST date, MC share)
    funnel: Mapping[str, int]  # alert_rows, issues, open, decisions


# ---- engines, issues, orders -----------------------------------------------------------------------------
class Tier(StrEnum):
    DESC = "DESC"
    DIAG = "DIAG"
    PRED = "PRED"
    PRESC = "PRESC"


@dataclass(frozen=True)
class Finding:
    """One engine output that triage or a screen can cite."""

    engine: str
    tier: Tier
    tail_no: str | None
    subject: str  # code, serial, part number or issue id
    beliefs: tuple[Belief, ...]
    evidence: tuple[bytes, ...]  # record ids, all with t_ingest ≤ the snapshot
    reason: str  # one human-readable sentence, built from a template


class IssueState(StrEnum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MONITORING = "MONITORING"
    SHELVED = "SHELVED"
    SUPPRESSED_BY_DESIGN = "SUPPRESSED_BY_DESIGN"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ORDERED = "ORDERED"
    IN_WORK = "IN_WORK"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


@dataclass(frozen=True)
class Issue:
    issue_id: str  # deterministic: f"{tail_no}-{code}" or a group id
    tail_no: str | None  # None for fleet-level groups
    code: str
    title: str
    severity: str
    first: int
    last: int
    n_alerts: int
    state: IssueState
    band: str | None = None  # P1 … P4, or None = monitor
    consequence: int | None = None  # C 0–3
    urgency: int | None = None  # U 0–3
    basis: str = ""  # gate or lookup that set the band
    rank_value: float | None = None  # expected NMC-days avoided
    confidence: str = ""  # high | med | low
    findings: tuple[Finding, ...] = ()


class Authority(StrEnum):
    AGENT = "AGENT"
    HUMAN = "HUMAN"


@dataclass(frozen=True)
class CandidateOrder:
    issue_id: str
    rule: str  # policy id, e.g. "P-DEC-01"
    row: str  # decision-table row that fired
    policy_version: str
    action: str  # data-layer order action, e.g. "TROUBLESHOOT"
    parameters: Mapping[str, Any]
    target_tail_no: str | None
    target_base: str | None
    authority: Authority
    mode: str  # "consent" in the prototype
    evidence: tuple[bytes, ...]
    rationale: str


@dataclass(frozen=True)
class IssuedOrder:
    order_id: str  # phx:<rule>:<semver>:<epoch YYYYMMDDTHHMM>:<tail>:<action>:<blake2b-8>
    candidate: CandidateOrder
    t_issued: int
    approved_by: str | None
    signed_by: str | None  # required when authority is HUMAN


@dataclass(frozen=True)
class Verdict:
    order_id: str
    verdict: str  # ACCEPTED | REJECTED | DUPLICATE | INVALID (the data layer's gateway)
    reason: str | None
    t_apply_utc: int | None


# ---- runner HTTP API (fleet side, port 8710) ---------------------------------------------------------------
@dataclass(frozen=True)
class StepRequest:
    to: int  # UTC ns; the runner processes every event at or before it, then publishes
    orders: Mapping[str, Sequence[Mapping[str, Any]]] = field(default_factory=dict)  # tail -> orders.commands rows


@dataclass(frozen=True)
class StepResult:
    t_from: int | None
    t_to: int
    rows: Mapping[str, Mapping[str, int]]  # tail -> topic -> rows published
    verdicts: Mapping[str, Sequence[Verdict]]
    wall_s: float
