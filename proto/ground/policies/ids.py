"""Order ids (DEVELOPMENT §2.9): content-addressed, so a retried epoch never issues twice and a replay gives the same
id. ``phx:<rule>:<policy semver>:<epoch YYYYMMDDTHHMM>:<tail>:<action>:<blake2b-8 of canonical {parameters,
sorted evidence ids}>``, the epoch written in IST."""

from __future__ import annotations

import datetime as dt

from interfaces import NS, CandidateOrder

from policies.engine import policies

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def epoch_of(t: int) -> int:
    """The 08:00 IST epoch an order decided at ``t`` acts at (same IST day if t ≤ 08:00, else the next day)."""
    d = dt.datetime.fromtimestamp(t / NS, IST)
    e = d.replace(hour=8, minute=0, second=0, microsecond=0)
    if d > e:
        e += dt.timedelta(days=1)
    return int(e.timestamp()) * NS


def order_id(rule: str, semver: str, epoch: int, tail: str, action: str, parameters, evidence_hex) -> str:
    """The one implementation is S1's ``orders.order_id``; this wrapper returns just the id."""
    from orders import order_id as _order_id

    return _order_id(rule, semver, epoch, tail, action, parameters, list(evidence_hex))[0]


def candidate_order_id(c: CandidateOrder, t: int) -> str:
    """Id of a candidate decided at ``t``; the tail is the issue's (a base-level requisition keeps its issue tail)."""
    tail = c.target_tail_no or c.issue_id.split("-")[0]
    params = dict(c.parameters) if c.parameters is not None else None
    return order_id(c.rule, policies().semver[c.rule], epoch_of(t), tail, c.action, params,
                    [bytes(e).hex() for e in c.evidence])
