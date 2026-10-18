"""Battery protocol: bars, paired D_sim per arm, verdicts (port of round-2 `run_holdout.battery_all`).

The order of the comparisons is part of the protocol, because bootstrap draws are generated per draw key on
first use: D_tail ("partner", "holdout"), then D_temp ("late", "early"), then every arm's paired D_sim, which
reuses the "holdout" draws. With `Bootstrap(np.random.SeedSequence(20261015))` this reproduces the round-2
numbers exactly (same per-flight statistics in, same distances, CIs and verdicts out).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from phalanx.validation.battery.evaluate import (
    Bootstrap,
    Comparison,
    Group,
    TestResult,
    compare,
    group_values,
    summarise,
    verdicts,
)

__all__ = ["ArmResult", "BatteryReport", "run_battery"]


@dataclass(frozen=True, eq=False)
class ArmResult:
    """One synthetic arm: paired distances to the real holdout, per-test verdicts, descriptive group
    values."""

    d_sim: Comparison
    verdicts: Mapping[str, TestResult]
    group: Mapping[str, object]

    def verdict_counts(self) -> dict[str, int]:
        vs = [v.verdict for v in self.verdicts.values()]
        return {k: vs.count(k) for k in ("PASS", "FAIL", "INCONCLUSIVE")}


@dataclass(frozen=True, eq=False)
class BatteryReport:
    """Result of one battery run: bars, arms, sample sizes and the bootstrap seed used."""

    d_tail: Comparison
    d_temp: Comparison
    arms: Mapping[str, ArmResult]
    groups: Mapping[str, Mapping[str, object]]
    n_flights: Mapping[str, int]
    n_boot: int
    seed: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """JSON-ready summary in the layout of round-2 `battery.json` (plus sample sizes and seed)."""
        return {
            "D_tail": summarise(self.d_tail),
            "D_temp": summarise(self.d_temp),
            "arms": {
                lab: {
                    "D_sim": summarise(a.d_sim),
                    "verdicts": {t: v.to_dict() for t, v in a.verdicts.items()},
                    "group": dict(a.group),
                }
                for lab, a in self.arms.items()
            },
            "groups": {k: dict(v) for k, v in self.groups.items()},
            "n_flights": dict(self.n_flights),
            "n_boot": self.n_boot,
            "seed": dict(self.seed),
        }


def run_battery(
    holdout: Group,
    partner: Group,
    early: Sequence[int],
    late: Sequence[int],
    arms: Mapping[str, Group],
    boot: Bootstrap,
    *,
    require_equal_counts: bool = True,
) -> BatteryReport:
    """Run B1-B6 for every arm against the real-vs-real bars.

    Args:
        holdout: per-flight stats of the real holdout, aligned with its flight list.
        partner: per-flight stats of the D_tail partner group (another tail), equal count (section 2).
        early, late: indices into `holdout` of the temporal halves (median-date split) for D_temp.
        arms: label -> per-flight stats of each synthetic version, aligned with `holdout` (paired by flight).
        boot: the bootstrap; must be fresh, so that draws follow the round-2 request order.
        require_equal_counts: enforce the pre-registered equal flight counts per comparison.
    """
    if boot.draws:
        raise ValueError("run_battery needs a fresh Bootstrap (draw order is part of the protocol)")
    if require_equal_counts and (len(partner) != len(holdout) or len(early) != len(late)):
        raise ValueError(
            f"unequal flight counts: holdout {len(holdout)}, partner {len(partner)}, "
            f"early {len(early)}, late {len(late)} (pre-registration section 2)"
        )
    for lab, S in arms.items():
        if len(S) != len(holdout):
            raise ValueError(
                f"arm {lab!r} has {len(S)} flights, holdout has {len(holdout)} (paired by flight)"
            )
    SE = [holdout[i] for i in early]
    SL = [holdout[i] for i in late]
    tail = compare(partner, holdout, "partner", "holdout", False, boot, real_is_B=True)
    temp = compare(SL, SE, "late", "early", False, boot, real_is_B=True)
    out: dict[str, ArmResult] = {}
    for lab, S in arms.items():
        sim = compare(S, holdout, "holdout", "holdout", True, boot)
        out[lab] = ArmResult(d_sim=sim, verdicts=verdicts(sim, tail, temp), group=group_values(S))
    n = {"holdout": len(holdout), "partner": len(partner), "early": len(early), "late": len(late)}
    n.update({f"arm:{lab}": int(sum(s is not None for s in S)) for lab, S in arms.items()})
    return BatteryReport(
        d_tail=tail,
        d_temp=temp,
        arms=out,
        groups={"real_holdout": group_values(holdout), "real_partner": group_values(partner)},
        n_flights=n,
        n_boot=boot.nb,
        seed=dict(boot.source),
    )
