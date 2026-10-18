"""Deterministic selection of M02-planned sorties for telemetry runs (RULES.md rule 1: fixed seed, saved
list).

The M02 planner (usage mode) plans a fleet's days with keyed streams (``scenario`` key, root seed), so the
list of sorties in plan order is a pure function of (fleet scenario, start date, days, scenario key, root).
Telemetry runs and tests select from it by position: "the first n flying sorties in plan order".
"""

from __future__ import annotations

import datetime as dt
from functools import cache
from pathlib import Path

from phalanx.core.rng import KeyPath, RngService, StreamRegistry

ROOT = Path(__file__).resolve().parents[3]
TEJAS_FLEET = ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml"
#: the fleet sample of the realised-usage gates (tests/statistical/test_scenario_realised_usage_gates.py)
GATE_START = dt.date(2026, 1, 5)
GATE_SCENARIO = "gate"
GATE_ROOT = 0xA5


def flying_sorties(fleet, start: dt.date, days: int, *, scenario: str, root: int, platform: str = "tejas"):
    """Every planned sortie with flight time (ground runs excluded), in plan order
    (``Planner.plans_between``)."""
    from phalanx.environment.config import load_env_config
    from phalanx.scenario.config import load_scenario_params
    from phalanx.scenario.generator import Planner
    from phalanx.scenario.streams import STREAMS

    rng = RngService(int(root), StreamRegistry(list(STREAMS)))
    pl = Planner(
        load_scenario_params(platform),
        load_env_config(platform),
        fleet,
        rng.scope(KeyPath.of(scenario=scenario)),
    )
    plans = pl.plans_between(start, int(days))
    return [p for p in plans if p.summary is not None and p.summary.flight_s > 0]


@cache
def gate_sorties(days: int = 3):
    """The first days of the realised-usage gate sample (two-squadron fleet, scenario 'gate', root 0xA5)."""
    from phalanx.scenario.config import load_fleet_scenario

    return tuple(
        flying_sorties(
            load_fleet_scenario(TEJAS_FLEET), GATE_START, days, scenario=GATE_SCENARIO, root=GATE_ROOT
        )
    )


__all__ = ["GATE_ROOT", "GATE_SCENARIO", "GATE_START", "TEJAS_FLEET", "flying_sorties", "gate_sorties"]
