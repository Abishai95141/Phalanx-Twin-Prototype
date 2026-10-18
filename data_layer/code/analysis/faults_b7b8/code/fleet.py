"""Usage-mode operations world for B8 (W2.5): the real M02 (operations mode), M18, M21 and record sink, and the
real M10 / M11 / M14 of the tail, one tail per world (independent replicate worlds; per-tail identities, so the
worlds share no draw).

One tail per world because M18 addresses one health/monitoring module id for the whole fleet and the per-tail
router is W2.6's (M10/M11/M14 ignore other tails' events): one-tail worlds need no router and keep the real
modules unmodified. Fleet-level statistics pool the replicate worlds.

M11 runs stochastic (all catalogue onset processes; telemetry-mode physics edges off is not applicable: usage
mode realises the physics edges, PD-W1.5-1), M14 in the regime under test.
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from phalanx.core.events import Event  # noqa: E402
from phalanx.dictionary import load_dictionary  # noqa: E402
from phalanx.environment.config import load_env_config  # noqa: E402
from phalanx.faults import FaultConfig, FaultInjector, load_catalogue, load_fault_params, load_graph  # noqa: E402
from phalanx.fork.builder import OpsIds, OpsOnlyBuilder  # noqa: E402
from phalanx.fork.session import OpsSession  # noqa: E402
from phalanx.health import HealthConfig, HealthModule, load_health_params, sensor_bias_channels  # noqa: E402
from phalanx.maintenance.world import FleetSpec, OpsTargets  # noqa: E402
from phalanx.monitoring import (  # noqa: E402
    MonitoringConfig,
    MonitoringModule,
    load_code_table,
    load_monitoring_params,
)
from phalanx.scenario.config import FleetScenario, load_fleet_scenario, load_scenario_params  # noqa: E402
from phalanx.scenario.module import EV_DAY, OpsLink, ScenarioModule  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NS = 10**9
DAY = 86_400 * NS
IDS = OpsIds()


@dataclass
class OneTailWorld:
    """WorldBuilder (``phalanx.fork.builder`` protocol) of one tail; ``k`` picks the tail of the scenario's
    first squadron (and its installed engine serial)."""

    k: int
    days: int
    regime: str = "immature"
    start: dt.date = dt.date(2026, 1, 5)
    scenario: str = "w25b8"
    ids: OpsIds = field(default_factory=OpsIds)
    m14_usage_mode: bool = False  # DEVIATIONS D7: M14 with every code as a test (A-W1.5-26 usage-mode detection)

    def __post_init__(self) -> None:
        full = load_fleet_scenario(ROOT / "configs" / "scenarios" / "tejas_two_squadrons.yaml")
        sq = full.squadrons[0]
        tails = sq.tails + full.squadrons[1].tails
        sers = sq.engine_serials + full.squadrons[1].engine_serials
        self.tail, self.serial = tails[self.k], sers[self.k]
        one = type(sq)(sq.sid, sq.role, sq.base, (self.tail,), (self.serial,))
        self.fleet = FleetScenario(f"{self.scenario}-{self.tail}", self.start, self.days, (one,))
        self.epoch_utc_ns = self.fleet.epoch_utc_ns
        d = load_dictionary()
        tail, serial, regime, usage_mode = self.tail, self.serial, self.regime, self.m14_usage_mode
        targets = OpsTargets(m21=IDS.m21, sink=IDS.sink, scenario="m02", health="m10", monitoring="m14")
        link = OpsLink(m18=IDS.m18, health="m10", kpi=IDS.sink)
        params, env = load_scenario_params(), load_env_config()
        bias = sensor_bias_channels(d)
        codes = load_code_table(d, load_monitoring_params())
        epoch = self.epoch_utc_ns
        fleet = self.fleet

        def m02():
            return ScenarioModule("m02", params, env, fleet=fleet, ops=link)

        def m10():
            cfg = HealthConfig((serial,), bias, "m11", monitor_target="m14", tail_no=tail)
            return HealthModule("m10", load_health_params(), config=cfg, identity={"tail": tail})

        def m11():
            cfg = FaultConfig(
                load_catalogue(),
                load_graph(),
                {"health": "m10", "monitoring": "m14", "maintenance": IDS.m18, "ops": "m02"},
                (serial,),
                bias,
                realise_physics_edges=True,
                stochastic=True,
                tail_no=tail,
            )
            return FaultInjector("m11", load_fault_params(), config=cfg, identity={"tail": tail})

        def m14():
            cfg = MonitoringConfig.from_dictionary(
                d,
                codes,
                (serial,),
                regime=regime,
                tail_no=tail,
                epoch_utc_ns=epoch,
                obs_target=IDS.m18,
                usage_mode=usage_mode,
            )
            return MonitoringModule("m14", load_monitoring_params(), config=cfg, identity={"tail": tail})

        self._ops = OpsOnlyBuilder(
            FleetSpec.from_scenario(self.fleet),
            epoch,
            scenario=f"{self.scenario}-{regime}",
            targets=targets,
            ids=IDS,
            extra=(m02, m10, m11, m14),
        )
        self.calendar = self._ops.calendar
        self.dict_version, self.dict_hash = self._ops.dict_version, self._ops.dict_hash

    def build(self, root, *, ledger=None):
        return self._ops.build(root, ledger=ledger)

    def initial_events(self) -> list[Event]:
        return [*self._ops.initial_events(), Event(0, EV_DAY, "m02", {"day": 0}, source="session")]


def run_world(k: int, days: int, regime: str, root: int, *, m14_usage_mode: bool = False) -> OpsSession:
    s = OpsSession(OneTailWorld(k, days, regime, m14_usage_mode=m14_usage_mode), root)
    s.run_until(days * DAY)
    return s
