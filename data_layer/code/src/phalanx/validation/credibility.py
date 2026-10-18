"""NASA-STD-7009B credibility card (stub: data structure and Markdown renderer; filled per release in W3.3).

Evidence (`research_notes/Virtual fighter telemetry layer research/validation_and_calibration.md` §1, §5;
report §0, §15):
- [DIRECT] M&S capability factors [M&S 48]: Data Pedigree, Verification, Validation, Development Technical
  Review, Process/Product Management (7009B §4.2.1.8, Table 7).
- [DIRECT] Validation levels (7009B App. E, Table 9): 4 = real-world system (RWS) in its operating
  environment; 3 = RWS in a representative environment; 2 = measurements from a representative system;
  1 = conceptual validation only; 0 = insufficient evidence. Levels are discrete, with no partial credit.
- [DIRECT] Validation against a representative or proxy system caps the Validation factor at Level 2.
  Phalanx validates against DASHlink airliner data (proxy) and published fighter sources, so **Level 2 is the
  ceiling** until real Tejas / F404-IN20 data exist; platform-dependent levels and fault signatures sit at
  Level 1-2 with SME sign-off.
- [DIRECT] The domain of validation [M&S 18] must state which regimes and channels each referent covers.
- [ASSUMPTION] (A-W0.5-6) Report per factor and per channel x regime, never as a single realism score
(validation notes §6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = [
    "FACTORS",
    "PROXY_VALIDATION_CEILING",
    "VALIDATION_LEVELS",
    "CredibilityCard",
    "CredibilityEntry",
    "DomainOfValidation",
    "FactorAssessment",
    "render_markdown",
]

#: M&S capability factors of NASA-STD-7009B [M&S 48].
FACTORS: tuple[str, ...] = (
    "Data Pedigree",
    "Verification",
    "Validation",
    "Development Technical Review",
    "Process/Product Management",
)
#: NASA-STD-7009B Table 9 validation levels (short form).
VALIDATION_LEVELS: Mapping[int, str] = {
    0: "insufficient evidence",
    1: "conceptual validation only",
    2: "measurements from a representative system",
    3: "real-world system in a representative environment",
    4: "real-world system in its operating environment",
}
#: Ceiling for every Validation entry while the referent is proxy data (DASHlink) or published sources.
PROXY_VALIDATION_CEILING = 2
CEILING_STATEMENT = (
    "Credibility ceiling: NASA-STD-7009B Validation Level 2. Every comparison uses a representative (proxy) "
    "system, the DASHlink airliner recorder data, or published fighter sources; no real Tejas or F404-IN20 "
    "data were available. Levels 3-4 need real-system data."
)


@dataclass(frozen=True)
class FactorAssessment:
    """Level of one 7009B factor for one channel x regime, with its evidence."""

    factor: str
    level: int
    evidence: Sequence[str] = field(default_factory=tuple)
    note: str = ""

    def __post_init__(self) -> None:
        if self.factor not in FACTORS:
            raise ValueError(f"unknown 7009B factor {self.factor!r}")
        if self.level not in VALIDATION_LEVELS:
            raise ValueError(f"level must be 0..4, got {self.level}")


@dataclass(frozen=True)
class CredibilityEntry:
    """Factor levels for one channel (or channel group) in one regime.

    `property_class` is "P" (platform-independent: sensor laws, texture, corrected relations) or "D"
    (platform-dependent: absolute levels, fault signatures), per the proxy-validation matrix.
    """

    channel: str
    regime: str
    property_class: str
    factors: Sequence[FactorAssessment]
    battery_tests: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.property_class not in ("P", "D"):
            raise ValueError("property_class must be 'P' or 'D'")
        names = [f.factor for f in self.factors]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate factor in {self.channel}/{self.regime}")


@dataclass(frozen=True)
class DomainOfValidation:
    """[M&S 18] What the referents actually cover."""

    platform: str
    referents: Sequence[str]
    regimes: Sequence[str]
    channels: Sequence[str]
    envelope: Mapping[str, tuple[float, float]] = field(default_factory=dict)
    exclusions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class CredibilityCard:
    """Credibility card of one release (architecture §14.4)."""

    release: str
    intended_use: str
    domain: DomainOfValidation
    entries: Sequence[CredibilityEntry]
    real_system_data: bool = False
    ceiling_statement: str = CEILING_STATEMENT
    open_issues: Sequence[str] = field(default_factory=tuple)

    @property
    def validation_ceiling(self) -> int:
        """Level 2 while the referents are proxies; up to 4 only with real Tejas / F404-IN20 data."""
        return 4 if self.real_system_data else PROXY_VALIDATION_CEILING

    def __post_init__(self) -> None:
        for e in self.entries:
            for f in e.factors:
                if f.factor == "Validation" and f.level > self.validation_ceiling:
                    raise ValueError(
                        f"{e.channel}/{e.regime}: Validation level {f.level} exceeds the ceiling "
                        f"{self.validation_ceiling} (proxy referent)"
                    )


def _cell(entry: CredibilityEntry, factor: str) -> str:
    for f in entry.factors:
        if f.factor == factor:
            return str(f.level)
    return "-"


def render_markdown(card: CredibilityCard) -> str:
    """Render the card as Markdown: ceiling first, then domain, the factor table and open issues."""
    d = card.domain
    lines = [
        f"# Credibility card: {card.release}",
        "",
        f"**{card.ceiling_statement}**",
        "",
        f"**Intended use:** {card.intended_use}",
        "",
        "## Domain of validation",
        "",
        f"- Platform: {d.platform}",
        f"- Referents: {', '.join(d.referents)}",
        f"- Regimes: {', '.join(d.regimes)}",
        f"- Channels: {', '.join(d.channels)}",
    ]
    for k, (lo, hi) in d.envelope.items():
        lines.append(f"- Envelope {k}: {lo} to {hi}")
    for x in d.exclusions:
        lines.append(f"- Not covered: {x}")
    lines += [
        "",
        "## Factor levels per channel and regime",
        "",
        "Levels 0-4 (NASA-STD-7009B Table 9 for Validation). "
        "P = platform-independent, D = platform-dependent.",
        "",
        "| Channel | Regime | Class | " + " | ".join(FACTORS) + " | Battery tests |",
        "|---|---|---|" + "---|" * len(FACTORS) + "---|",
    ]
    for e in card.entries:
        cells = " | ".join(_cell(e, f) for f in FACTORS)
        tests = ", ".join(e.battery_tests) or "-"
        lines.append(f"| {e.channel} | {e.regime} | {e.property_class} | {cells} | {tests} |")
    ev = [(e, f) for e in card.entries for f in e.factors if f.evidence or f.note]
    if ev:
        lines += ["", "## Evidence", ""]
        for e, f in ev:
            src = "; ".join(f.evidence)
            note = f" - {f.note}" if f.note else ""
            lines.append(f"- {e.channel} / {e.regime} / {f.factor} = {f.level}: {src}{note}")
    lines += ["", "## Open issues", ""]
    lines += [f"- {x}" for x in card.open_issues] or ["- none recorded"]
    return "\n".join(lines) + "\n"
