"""Runtime event-protocol validator (W2.1 deliverable 3; AD-44, AD-48.1).

``test_event_protocol.py`` checks what modules *declare*; E1 showed declarations miss real payloads (M18 MOD
``mx.action`` without ``pos``; mutant m06b renaming ``tail`` -> ``tail_no`` survived ``make check``). This
module checks every event the scheduler actually **dispatches**:

- an event between two different modules (``event.source`` -> ``event.target``) must use a kind catalogued in
  ``configs/interfaces/w1_events.yaml``; its producer and consumer must be the catalogued module numbers; its
  payload must carry every catalogued key as a **plain top-level key** (AD-48.1; a ``{"doc": ...}`` payload
  is a violation, whatever it contains);
- an uncatalogued cross-module kind is a violation unless it belongs to a documented package-internal
  protocol (:data:`INTERNAL_PROTOCOLS`, with its source) or to a **tracked exception** (:data:`TRACKED`, an
  owning work package and the catalogue change that closes it). A test fails on a stale tracked exception;
- a self-event (source == target) is module-internal and free (AD-44);
- events from outside the System (``System.inject``: orders and harness bootstrap; the recorder's CIR feed)
  are checked like module events with the harness as producer (:data:`HARNESS_SOURCES`).

Hook: :class:`ValidatingEventQueue` replaces the world's ``EventQueue``; ``pop_due`` (the scheduler's dispatch
step) validates each event before it is delivered. Snapshot bytes and the config hash are unchanged (the queue
serialises exactly like the base class), so validation is an execution option: on in every test, off in
production for speed.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from phalanx.core.events import Event, EventQueue

ROOT = Path(__file__).resolve().parents[3]
EVENTS_CATALOGUE = ROOT / "configs" / "interfaces" / "w1_events.yaml"

#: event sources that are not System modules: name -> architecture number used for the producer check
HARNESS_SOURCES: dict[str, str] = {
    "external": "HARNESS",  # System.inject: bootstrap events of the run and orders (logged in the order log)
    "harness": "HARNESS",
    "recorder": "M13",  # the M13 recorder's CIR feed to M14 (monitor.observe), outside the scheduler (AD-42)
}


@dataclass(frozen=True)
class InternalProtocol:
    """A documented package-internal event protocol between named modules (not catalogued by design)."""

    kinds: str  # fnmatch pattern of event kinds
    producers: tuple[str, ...]
    consumers: tuple[str, ...]
    source: str


#: W1.5 names its M10/M11/M14 events internal to the health/faults/monitoring group (faults/README.md
#: "W1.5/W2.1-internal", health/README.md "W1.5-internal events", monitoring/ports.py "monitor.* are
#: W1.5/W2.1-internal hooks"); the harness drives their sortie lifecycle until AD-48.2 (ops.takeoff) lands.
INTERNAL_PROTOCOLS: tuple[InternalProtocol, ...] = (
    InternalProtocol(
        "health.*", ("M11",), ("M10",), "faults/README.md: M11 -> M10 health.fault is W1.5-internal"
    ),
    InternalProtocol(
        "faults.*", ("M10", "HARNESS"), ("M11",), "faults/README.md: M11 consumes no catalogued kind"
    ),
    InternalProtocol(
        "monitor.*",
        ("M10", "M11", "M13", "HARNESS"),
        ("M14",),
        "monitoring/ports.py: monitor.* are W1.5/W2.1-internal hooks; io.cir_chunk_payload is the M13 -> M14 "
        "CIR feed",
    ),
    InternalProtocol(
        "scenario.sortie_start",
        ("HARNESS",),
        ("M02",),
        "scenario/module.py: the harness injects ScenarioModule.initial_events()",
    ),
)


@dataclass(frozen=True)
class TrackedEvent:
    """An uncatalogued cross-module kind with an owner (stale-checked by the tests, like w1_ports
    exceptions)."""

    kind: str
    producers: tuple[str, ...]
    consumers: tuple[str, ...]
    owner: str
    source: str


#: none since W2.1c catalogued ``scenario.sortie_plan`` (AD-49); the mechanism stays for the next gap
TRACKED: tuple[TrackedEvent, ...] = ()


@dataclass(frozen=True)
class Violation:
    t_ns: int
    kind: str
    source: str
    target: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.kind} {self.source}->{self.target} @ {self.t_ns} ns: {self.message}"


class EventProtocolError(AssertionError):
    """A dispatched event violates the catalogued protocol (raised in strict mode)."""


@dataclass
class EventValidator:
    """Checks dispatched events (module docstring). ``m_of``: module id -> architecture number (M02...)."""

    m_of: Mapping[str, str]
    strict: bool = True
    catalogue: Mapping[str, Any] | None = None
    internal: tuple[InternalProtocol, ...] = INTERNAL_PROTOCOLS
    tracked: tuple[TrackedEvent, ...] = TRACKED
    violations: list[Violation] = field(default_factory=list)
    seen: dict[tuple[str, str, str], int] = field(default_factory=dict)  # (kind, producer M, consumer M) -> n
    tracked_hits: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.catalogue is None:
            from phalanx.dictionary.yamlio import load_yaml

            self.catalogue = load_yaml(EVENTS_CATALOGUE)["events"]

    def producer_of(self, ev: Event) -> str | None:
        if ev.source in self.m_of:
            return self.m_of[ev.source]
        return HARNESS_SOURCES.get(ev.source)

    def check(self, ev: Event) -> list[Violation]:
        """Violations of one dispatched event (also recorded; raises in strict mode)."""
        out: list[Violation] = []
        if ev.source == ev.target:
            return out  # module-internal self-event (AD-44: internal names are free)

        def bad(rule: str, msg: str) -> None:
            out.append(Violation(ev.t_ns, ev.kind, ev.source, ev.target, rule, msg))

        prod = self.producer_of(ev)
        cons = self.m_of.get(ev.target)
        if prod is None:
            bad(
                "source",
                f"unknown event source {ev.source!r} (not a module of the System nor a harness source)",
            )
        if cons is None:
            bad("target", f"unknown target {ev.target!r}")
        if out:
            return self._done(out)
        if prod == cons and prod != "HARNESS":
            return out  # two instances of one architecture module (e.g. the M13 lane modules): internal
        self.seen[(ev.kind, prod, cons)] = self.seen.get((ev.kind, prod, cons), 0) + 1
        spec = self.catalogue.get(ev.kind)
        if spec is None:
            if any(
                fnmatch.fnmatchcase(ev.kind, ip.kinds) and prod in ip.producers and cons in ip.consumers
                for ip in self.internal
            ):
                return out
            tr = next(
                (
                    x
                    for x in self.tracked
                    if x.kind == ev.kind and prod in x.producers and cons in x.consumers
                ),
                None,
            )
            if tr is not None:
                self.tracked_hits[tr.kind] = self.tracked_hits.get(tr.kind, 0) + 1
                return out
            bad(
                "uncatalogued",
                f"{prod} -> {cons}: kind is not in w1_events.yaml and not a documented protocol",
            )
            return self._done(out)
        if prod != "HARNESS" and spec["producer"] != prod:
            bad("producer", f"catalogued producer is {spec['producer']}, sent by {prod} ({ev.source})")
        if cons not in spec["consumers"]:
            bad("consumer", f"{cons} ({ev.target}) is not a catalogued consumer {spec['consumers']}")
        keys = set(ev.payload)
        if keys == {"doc"} and "doc" not in spec["payload"]:
            bad("encoding", "payload is {'doc': ...}; AD-48.1 requires plain top-level keys")
        missing = [k for k in spec["payload"] if k not in keys]
        if missing:
            bad("payload", f"missing catalogued keys {missing} (has {sorted(keys)})")
        return self._done(out)

    def _done(self, out: list[Violation]) -> list[Violation]:
        if out:
            self.violations.extend(out)
            if self.strict:
                raise EventProtocolError("\n".join(map(str, out)))
        return out


class ValidatingEventQueue(EventQueue):
    """``EventQueue`` whose dispatch (``pop_due``) validates each event. Serialises like the base class."""

    def __init__(self, validator: EventValidator) -> None:
        super().__init__()
        self.validator = validator

    @classmethod
    def wrap(cls, queue: EventQueue, validator: EventValidator) -> ValidatingEventQueue:
        q = cls(validator)
        q._heap = list(queue._heap)
        q._next_seq = queue._next_seq
        return q

    def pop_due(self, t_ns: int) -> Event | None:
        ev = super().pop_due(t_ns)
        if ev is not None:
            self.validator.check(ev)
        return ev

    def copy(self) -> ValidatingEventQueue:
        return ValidatingEventQueue.wrap(self, self.validator)


def validating(world, validator: EventValidator):
    """A copy of ``world`` whose event queue validates every dispatched event."""
    w = world.copy()
    w.queue = ValidatingEventQueue.wrap(world.queue, validator)
    return w


def payload_plain(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Payload values as Python scalars/lists (diagnostics)."""
    return {k: np.asarray(v).tolist() for k, v in payload.items()}


__all__ = [
    "EVENTS_CATALOGUE",
    "HARNESS_SOURCES",
    "INTERNAL_PROTOCOLS",
    "TRACKED",
    "EventProtocolError",
    "EventValidator",
    "InternalProtocol",
    "TrackedEvent",
    "ValidatingEventQueue",
    "Violation",
    "payload_plain",
    "validating",
]
