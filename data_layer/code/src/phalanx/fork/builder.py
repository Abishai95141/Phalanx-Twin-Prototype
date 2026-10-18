"""What a usage-mode fleet must provide to the session and fork service (M22), and the operations-only world.

A ``WorldBuilder`` builds the same event-only ``System`` for any root seed (ensemble forks rebuild it with a
derived root; restores rebuild it with the parent's root). W1 runs the operations modules (M18, M21, sink)
with W1-local test fixtures standing in for M02/M10/M11/M14 (``tests/fork/test_fork_fixture_fleet.py``); W2.6
supplies a builder with the real modules. :class:`OpsOnlyBuilder` is the operations layer alone, driven by
injected events (integration tests, record replays).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from phalanx.core.events import Event
from phalanx.core.module import Module
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.maintenance.config import M18Config, load_m18_config
from phalanx.maintenance.world import FleetSpec, InternalPolicy, MaintenanceWorld, OpsTargets
from phalanx.orders.epochs import DecisionCalendar
from phalanx.orders.module import OrdersModule, RecordSink
from phalanx.orders.params import M21Config, load_m21_config


@dataclass(frozen=True)
class OpsIds:
    m18: str = "m18"
    m21: str = "m21"
    sink: str = "sink"


class WorldBuilder(Protocol):
    scenario: str
    epoch_utc_ns: int
    calendar: DecisionCalendar
    ids: OpsIds
    dict_version: str
    dict_hash: str

    def build(self, root: int, *, ledger: DrawLedger | None = None) -> System: ...

    def initial_events(self) -> list[Event]: ...


def dictionary_identity() -> tuple[str, str]:
    d = load_dictionary()
    return d.dict_version, d.dict_hash


@dataclass
class OpsOnlyBuilder:
    """M18 + M21 + record sink; neighbours (scenario, health) are absent unless ``extra`` modules provide
    them."""

    fleet: FleetSpec
    epoch_utc_ns: int
    scenario: str = "ops"
    m18_cfg: M18Config | None = None
    m21_cfg: M21Config | None = None
    internal: InternalPolicy = field(default_factory=InternalPolicy)
    targets: OpsTargets | None = None
    ids: OpsIds = field(default_factory=OpsIds)
    extra: Sequence[Callable[[], Module]] = ()  # factories: every build needs fresh module objects

    def __post_init__(self) -> None:
        self.m18_cfg = self.m18_cfg or load_m18_config()
        self.m21_cfg = self.m21_cfg or load_m21_config()
        self.dict_version, self.dict_hash = dictionary_identity()
        self.calendar = self.m21_cfg.calendar(self.epoch_utc_ns, self.m18_cfg.tz_offset_s)
        self.targets = self.targets or OpsTargets(m21=self.ids.m21, sink=self.ids.sink)

    def modules(self) -> list[Module]:
        assert self.m18_cfg is not None and self.targets is not None
        m18 = MaintenanceWorld(
            self.ids.m18,
            self.m18_cfg,
            self.fleet,
            epoch_utc_ns=self.epoch_utc_ns,
            calendar=self.calendar,
            dict_version=self.dict_version,
            dict_hash=self.dict_hash,
            targets=self.targets,
            internal=self.internal,
        )
        m21 = OrdersModule(
            self.ids.m21,
            epoch_utc_ns=self.epoch_utc_ns,
            dict_version=self.dict_version,
            dict_hash=self.dict_hash,
            m18=self.ids.m18,
            sink=self.ids.sink,
        )
        return [*(f() for f in self.extra), m18, m21, RecordSink(self.ids.sink)]

    def build(self, root: int, *, ledger: DrawLedger | None = None) -> System:
        return System(
            self.modules(),
            [],
            rng=RngService(root, StreamRegistry(), ledger=ledger),
            identity=KeyPath.of(scenario=self.scenario),
            dict_hash=self.dict_hash,
        )

    def initial_events(self) -> list[Event]:
        return [Event(0, "m18.start", self.ids.m18, {}, priority=-100, source="session")]  # AD-48.1
