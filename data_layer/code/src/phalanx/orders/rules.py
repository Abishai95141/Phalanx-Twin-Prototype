"""Order authority and airworthiness rules (architecture §11.1; report §14 "M21 checks authority and
airworthiness").

M21 owns the rules; M18 owns the technical-log state they are evaluated on. M18 calls :func:`airworthiness`
when it executes an order, so the check sees the authoritative tech log at the decision epoch, never a stale
copy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from phalanx.core.module import EvidenceTag
from phalanx.dictionary.yamlio import load_yaml

AUTHORITY_FORMAT = "phalanx.authority/1"


@dataclass(frozen=True)
class Authority:
    default_issuers: frozenset[str]
    actions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def allowed(self, action: str, issuer_kind: str) -> bool:
        spec = self.actions.get(action)
        issuers = frozenset(spec["issuers"]) if spec and "issuers" in spec else self.default_issuers
        return issuer_kind in issuers

    def max_extension_fraction(self, action: str) -> float | None:
        spec = self.actions.get(action) or {}
        v = spec.get("max_extension_fraction")
        return None if v is None else float(v)


def load_authority(path: Path | None = None) -> Authority:
    path = path or Path(__file__).resolve().parents[3] / "configs" / "policies" / "authority.yaml"
    doc = load_yaml(path)
    if not isinstance(doc, Mapping) or doc.get("format") != AUTHORITY_FORMAT:
        raise ValueError(f"{path.name}: format must be {AUTHORITY_FORMAT}")
    EvidenceTag.parse(doc["evidence"]["tag"])
    for a, spec in (doc.get("actions") or {}).items():
        EvidenceTag.parse(spec["evidence"]["tag"])
        if not spec["evidence"].get("source"):
            raise ValueError(f"{a}: evidence source required")
    return Authority(frozenset(doc["default_issuers"]), dict(doc.get("actions") or {}))


@dataclass(frozen=True)
class TechLogFacts:
    """What the airworthiness rule needs about one tail (from M18's tech log)."""

    tail_no: str
    mission_capable: bool
    open_grounding_jobs: tuple[str, ...]  # grounding defects / inspections not closed (excluding order holds)
    on_hold: bool


def airworthiness(action: str, facts: TechLogFacts | None, params: Mapping[str, Any]) -> str | None:
    """Reason to reject an order on airworthiness grounds, or None.

    - RELEASE: no release with open grounding defects (architecture §11.1).
    - ASSIGN_SORTIE: only a mission-capable tail may be assigned.
    - DEFER is checked by M18 against the job itself (a grounding defect cannot be deferred).
    """
    if facts is None:
        return None
    if action == "RELEASE" and facts.open_grounding_jobs:
        return "open grounding defect(s): " + ",".join(sorted(facts.open_grounding_jobs))
    if action == "ASSIGN_SORTIE" and not facts.mission_capable:
        return f"tail {facts.tail_no} is not mission capable"
    return None
