"""Orders: content-addressed ids, the human gate (approve / modify / reject / snooze / sign) and the outbox.

Id (DEVELOPMENT.md §2.9, same recipe as the film): ``phx:<rule>:<semver>:<epoch YYYYMMDDTHHMM IST>:<tail>:<action>:
<blake2b-8 of canonical JSON {parameters, sorted evidence ids}>``. The same decision on the same evidence in the
same epoch always gets the same id, so a retry can never issue twice (the data layer's gateway also rejects
duplicates).

Consent mode: an order leaves only if a person approved it before the freeze; HUMAN-authority orders also need a
named signature. Every human action is an event on the log.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field, replace
from typing import Any

from interfaces import NS, Authority, CandidateOrder
from lel import EventLog, canonical

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
#: actions only a person may issue (RULES.md rule 7) — read from the data layer's authority matrix
#: (policies/authority.yaml via policies.human_only); the data layer's gateway enforces it again
HUMAN_ONLY = {"CHANGE_MONITORING_CONFIG", "EMBODY_MODIFICATION"}


def human_only(action: str) -> bool:
    try:
        from policies import human_only as _h

        return _h(action)
    except Exception:  # noqa: BLE001 — policies package unavailable: the conservative built-in list
        return action in HUMAN_ONLY


def order_priority(c) -> str:
    try:
        from policies import priority

        return priority(c)
    except Exception:  # noqa: BLE001
        return "ROUTINE"
ISSUER = {Authority.AGENT: "PHALANX-PDM-AGENT", Authority.HUMAN: "HUMAN-ENGG-OFFICER"}


def order_id(rule: str, semver: str, epoch_t: int, tail: str, action: str, params: dict, evidence_hex: list[str]) -> tuple[str, str]:
    h = hashlib.blake2b(canonical({"parameters": params, "evidence": sorted(evidence_hex)}).encode(), digest_size=8).hexdigest()
    stamp = dt.datetime.fromtimestamp(epoch_t / NS, IST).strftime("%Y%m%dT%H%M")
    return f"phx:{rule}:{semver}:{stamp}:{tail}:{action}:{h}", h


@dataclass
class Draft:
    """One candidate order on today's board and what people did with it."""

    order_id: str
    candidate: CandidateOrder
    epoch_t: int  # the 08:00 IST epoch it is for
    state: str = "PROPOSED"  # PROPOSED | APPROVED | REJECTED | SNOOZED | NOT_ISSUED | SUBMITTED
    approved_by: str | None = None
    signed_by: str | None = None
    snooze_until: int | None = None
    note: str | None = None
    verdict: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def tail(self) -> str:
        """The tail world the order goes to: its target tail, else the issue's (a base-level requisition)."""
        return self.candidate.target_tail_no or self.candidate.issue_id.split("-")[0]

    @property
    def needs_signature(self) -> bool:
        return self.candidate.authority == Authority.HUMAN or human_only(self.candidate.action)

    @property
    def issuable(self) -> bool:
        return self.state == "APPROVED" and (not self.needs_signature or self.signed_by is not None)

    def command(self) -> dict[str, Any]:
        """The ``orders.commands`` row the runner submits at the epoch."""
        c = self.candidate
        kind = Authority.HUMAN if self.needs_signature else Authority.AGENT
        return {
            "order_id": self.order_id,
            "issuer_id": self.signed_by and f"HUMAN:{self.signed_by}" or ISSUER[kind],
            "issuer_kind": kind.value,
            "t_issued": self.epoch_t,
            "action": c.action,
            "parameters": dict(c.parameters),
            "priority": order_priority(c),
            "target_tail_no": c.target_tail_no,
            "target_base": c.target_base,
            "evidence": [e.hex() for e in c.evidence],
            "policy_version": c.policy_version,
        }


class OrderDesk:
    """Today's drafts and the human gate. One desk per epoch; every transition is logged."""

    def __init__(self, log: EventLog, epoch_t: int, *, clock=None, t_freeze: int | None = None) -> None:
        self.log, self.epoch_t = log, epoch_t
        self.clock = clock or (lambda: epoch_t)  # logical time of a human action (the board's session clock)
        self.t_freeze = t_freeze if t_freeze is not None else epoch_t
        self.drafts: dict[str, Draft] = {}
        self.frozen = False

    def propose(self, c: CandidateOrder, semver: str) -> Draft:
        tail = c.target_tail_no or c.issue_id.split("-")[0]
        oid, _ = order_id(c.rule, semver, self.epoch_t, tail, c.action, dict(c.parameters), [e.hex() for e in c.evidence])
        if oid not in self.drafts:
            self.drafts[oid] = Draft(oid, c, self.epoch_t)
        return self.drafts[oid]

    def _act(self, oid: str, typ: str, who: str, **changes: Any) -> Draft:
        if self.frozen:
            raise PermissionError("the board is frozen for this epoch")
        d = self.drafts[oid]
        for k, v in changes.items():
            setattr(d, k, v)
        t = self.clock()
        entry = {"order_id": oid, "by": who, **{k: v for k, v in changes.items() if k != "candidate"}}
        self.log.append(typ, f"order:{oid}", entry, t)
        d.history.append(entry | {"t": t})
        return d

    def approve(self, oid: str, who: str) -> Draft:
        return self._act(oid, "ORDER_APPROVED", who, state="APPROVED", approved_by=who)

    def reject(self, oid: str, who: str, reason: str) -> Draft:
        return self._act(oid, "ORDER_REJECTED", who, state="REJECTED", note=reason)

    def snooze(self, oid: str, who: str, until: int) -> Draft:
        return self._act(oid, "ORDER_SNOOZED", who, state="SNOOZED", snooze_until=until)

    def sign(self, oid: str, who: str) -> Draft:
        d = self.drafts[oid]
        if not d.needs_signature:
            raise ValueError("this order does not need a signature")
        return self._act(oid, "ORDER_SIGNED", who, signed_by=who)

    def modify(self, oid: str, who: str, parameters: dict[str, Any]) -> Draft:
        """A modified order is a different order: it gets its own id and starts unapproved."""
        d = self.drafts[oid]
        c = replace(d.candidate, parameters=parameters)
        semver = oid.split(":")[2]
        new = self.propose(c, semver)
        self._act(oid, "ORDER_MODIFIED", who, state="REJECTED", note=f"replaced by {new.order_id}")
        return new

    def freeze(self) -> list[Draft]:
        """07:45: lock the board. Returns the orders that will be submitted at 08:00."""
        out = [d for d in self.drafts.values() if d.issuable]
        for d in self.drafts.values():
            if d.state == "PROPOSED" or (d.state == "APPROVED" and not d.issuable):
                d.state = "NOT_ISSUED"
        self.frozen = True
        self.log.append("BOARD_FROZEN", f"epoch:{self.epoch_t}", {"issue": [d.order_id for d in out],
                        "not_issued": [d.order_id for d in self.drafts.values() if d.state == "NOT_ISSUED"]}, self.t_freeze)
        return out
