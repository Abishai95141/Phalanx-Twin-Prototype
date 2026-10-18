"""Layer 1 hard constraints (architecture 07 Part B), checked on every candidate and every issued order.

- Authority: the action's issuers come from ``authority.yaml`` (a copy of the data layer's matrix; a test keeps the
  two equal). HUMAN-only actions — modifications, software loads, monitoring-config changes, servicing deferrals —
  must carry HUMAN authority and a named signature before they are issued.
- No automatic grounding: an AGENT never proposes GROUND.
- Evidence: every cited record must exist and be ingested at or before the decision time.
- One open order per (tail, action, target).
- Servicing extension at most the matrix's ``max_extension_fraction`` (20 %).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path

import yaml
from interfaces import Authority, CandidateOrder, IssuedOrder

from policies.engine import canon

HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def authority_matrix() -> dict:
    doc = yaml.safe_load((HERE / "authority.yaml").read_text())
    if doc.get("format") != "phalanx.authority/1":
        raise ValueError("authority.yaml: unexpected format")
    return doc


def issuers(action: str) -> frozenset[str]:
    doc = authority_matrix()
    spec = (doc.get("actions") or {}).get(action)
    return frozenset(spec["issuers"]) if spec and "issuers" in spec else frozenset(doc["default_issuers"])


def human_only(action: str) -> bool:
    return "AGENT" not in issuers(action)


def authority_of(action: str) -> Authority:
    return Authority.HUMAN if human_only(action) else Authority.AGENT


def target(c: CandidateOrder) -> str:
    return canon(dict(c.parameters or {}))


def violations(c: CandidateOrder, t: int, ingest_of: Callable[[str | None, bytes], int | None]) -> list[str]:
    out = []
    if human_only(c.action) and c.authority != Authority.HUMAN:
        out.append(f"{c.action} is HUMAN-only")
    if c.authority.value not in issuers(c.action):
        out.append(f"{c.authority.value} may not issue {c.action}")
    if c.action == "GROUND" and c.authority == Authority.AGENT:
        out.append("no automatic grounding")
    if not c.evidence:
        out.append("no evidence")
    tail = c.target_tail_no or c.issue_id.split("-")[0]  # a base-level order cites its issue's tail records
    for e in c.evidence:
        ti = ingest_of(tail, e)
        if ti is None:
            out.append(f"evidence {bytes(e).hex()} not in the store")
        elif ti > t:
            out.append(f"evidence {bytes(e).hex()} ingested after the decision time")
    if c.action == "DEFER_SERVICING":
        cap = (authority_matrix()["actions"].get("DEFER_SERVICING") or {}).get("max_extension_fraction")
        ext = float((c.parameters or {}).get("extension_fraction", 0.0))
        if cap is not None and ext > float(cap):
            out.append(f"servicing extension {ext:.0%} above {float(cap):.0%}")
    return out


def check(cands: Iterable[CandidateOrder], t: int, ingest_of: Callable[[str | None, bytes], int | None],
          open_orders: Iterable[tuple[str | None, str, str]] = ()) -> tuple[list[CandidateOrder], list[tuple[CandidateOrder, str]]]:
    """Keep the candidates that pass every invariant, in order; the first of several on the same (tail, action,
    target) wins. ``open_orders``: (tail, action, target) of orders already issued and not completed."""
    seen = set(open_orders)
    kept, rejected = [], []
    for c in cands:
        v = violations(c, t, ingest_of)
        key = (c.target_tail_no or c.issue_id.split("-")[0], c.action, target(c))
        if key in seen:
            v.append("an open order already exists for this (tail, action, target)")
        if v:
            rejected.append((c, "; ".join(v)))
            continue
        seen.add(key)
        kept.append(c)
    return kept, rejected


def issue_violations(o: IssuedOrder) -> list[str]:
    """Checks at issue time: HUMAN-only orders need a named signature; nothing is issued without approval."""
    out = []
    if o.candidate.authority == Authority.HUMAN and not o.signed_by:
        out.append(f"{o.candidate.action} needs a HUMAN signature")
    if o.candidate.mode == "consent" and not (o.approved_by or o.signed_by):
        out.append("consent mode: not approved before the freeze")
    return out
