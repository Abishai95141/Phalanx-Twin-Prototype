"""Credibility-card stub: Level-2 ceiling enforced for proxy referents; Markdown renders every entry."""

from __future__ import annotations

import pytest

from phalanx.validation.credibility import (
    FACTORS,
    CredibilityCard,
    CredibilityEntry,
    DomainOfValidation,
    FactorAssessment,
    render_markdown,
)

pytestmark = pytest.mark.unit
DOM = DomainOfValidation(
    platform="DASHlink proxy (four-engine airliner)",
    referents=("Tail 652 archive 8", "Tail 687 archive 1"),
    regimes=("climb", "cruise", "approach"),
    channels=("N1", "N2", "EGT", "FF"),
    envelope={"ALT_ft": (0.0, 41000.0)},
    exclusions=("fighter manoeuvre regimes", "afterburner"),
)


def _entry(level: int) -> CredibilityEntry:
    return CredibilityEntry(
        channel="EGT",
        regime="cruise",
        property_class="P",
        factors=(
            FactorAssessment("Validation", level, evidence=("battery B5 vs D_tail",)),
            FactorAssessment("Verification", 3, note="golden reproduction"),
        ),
        battery_tests=("B1", "B5"),
    )


def test_proxy_card_caps_validation_at_level_2():
    card = CredibilityCard(
        release="v0.0.1", intended_use="PdM benchmarking", domain=DOM, entries=(_entry(2),)
    )
    assert card.validation_ceiling == 2
    with pytest.raises(ValueError, match="ceiling"):
        CredibilityCard(release="v", intended_use="u", domain=DOM, entries=(_entry(3),))
    real = CredibilityCard(
        release="v", intended_use="u", domain=DOM, entries=(_entry(3),), real_system_data=True
    )
    assert real.validation_ceiling == 4


def test_factor_and_level_validation():
    assert FACTORS[2] == "Validation" and len(FACTORS) == 5
    with pytest.raises(ValueError):
        FactorAssessment("Realism", 2)
    with pytest.raises(ValueError):
        FactorAssessment("Validation", 5)
    with pytest.raises(ValueError):
        CredibilityEntry("N1", "cruise", "X", ())
    with pytest.raises(ValueError, match="duplicate"):
        CredibilityEntry(
            "N1", "cruise", "P", (FactorAssessment("Validation", 1), FactorAssessment("Validation", 2))
        )


def test_markdown_states_ceiling_domain_and_entries():
    card = CredibilityCard(
        release="v0.0.1",
        intended_use="PdM benchmarking",
        domain=DOM,
        entries=(_entry(2),),
        open_issues=("archive-2 gate not yet run",),
    )
    md = render_markdown(card)
    assert md.startswith("# Credibility card: v0.0.1")
    assert "Validation Level 2" in md and "proxy" in md
    assert "| EGT | cruise | P | - | 3 | 2 | - | - | B1, B5 |" in md
    assert "Not covered: afterburner" in md and "archive-2 gate not yet run" in md
    assert "battery B5 vs D_tail" in md
