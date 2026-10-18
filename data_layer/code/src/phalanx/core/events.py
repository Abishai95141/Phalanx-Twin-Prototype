"""Simulation-time event queue for discrete modules (architecture §5.5, §11; invariants I1, I2).

- Ordering key: ``(t_ns, priority, seq)``. ``seq`` is the queue's own insertion counter, so ties in time
  and priority resolve by insertion order. Lower ``priority`` dispatches first. Nothing is ordered by wall
  clock, object identity or builtin ``hash()`` (research note: "deterministic tie-breaking for same-time
  events", modelling_methodology.md §Determinism [TRANSFER]).
- Payloads are flat trees of NumPy arrays (same rules as module state), so events encode canonically.
- The queue serialises to canonical bytes (events sorted by key, plus ``next_seq``); restoring rebuilds an
  equivalent queue that pops in the same order and continues the same ``seq`` numbering.
"""

from __future__ import annotations

import heapq
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np

from .canonical import PERSON_EVENTS, canonical_json, digest, length_prefixed
from .state import StateError, decode_tree, encode_tree

QUEUE_FORMAT_VERSION = 1
_KIND_RE = re.compile(r"^[a-z][a-z0-9_.]*$")
_TARGET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]*$")


class EventError(ValueError):
    pass


def _normalise_payload(payload: Mapping[str, Any] | None) -> Mapping[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for k in sorted(payload or {}):
        v = (payload or {})[k]
        if isinstance(v, str):
            a = np.array(v, dtype=f"<U{max(1, len(v))}")
        elif isinstance(v, bool):
            a = np.array(v, dtype=np.bool_)
        elif isinstance(v, int):
            a = np.array(v, dtype=np.int64)
        elif isinstance(v, float):
            a = np.array(v, dtype=np.float64)
        else:
            a = np.array(v, copy=True)
        if a.dtype.kind == "O":
            raise EventError(f"payload field {k!r}: object arrays are not allowed")
        a.flags.writeable = False
        out[k] = a
    return MappingProxyType(out)


@dataclass(frozen=True, eq=False)
class Event:
    """A discrete event. ``seq`` is assigned by :meth:`EventQueue.push` (-1 = not yet queued)."""

    t_ns: int
    kind: str
    target: str
    payload: Mapping[str, np.ndarray] = field(default_factory=dict)
    priority: int = 0
    seq: int = -1
    source: str = "external"

    def __post_init__(self) -> None:
        for name in ("t_ns", "priority", "seq"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int | np.integer):
                raise EventError(f"{name} must be an int")
            object.__setattr__(self, name, int(v))
        if self.t_ns < 0:
            raise EventError("t_ns must be >= 0")
        if not _KIND_RE.match(self.kind):
            raise EventError(f"event kind {self.kind!r} must match {_KIND_RE.pattern}")
        if not _TARGET_RE.match(self.target):
            raise EventError(f"event target {self.target!r} must be a module id")
        object.__setattr__(self, "payload", _normalise_payload(self.payload))

    @property
    def key(self) -> tuple[int, int, int]:
        return (self.t_ns, self.priority, self.seq)

    def with_seq(self, seq: int) -> Event:
        return Event(self.t_ns, self.kind, self.target, dict(self.payload), self.priority, seq, self.source)

    def header(self) -> dict[str, Any]:
        return {
            "t_ns": self.t_ns,
            "priority": self.priority,
            "seq": self.seq,
            "kind": self.kind,
            "target": self.target,
            "source": self.source,
        }

    def encode(self) -> bytes:
        h = canonical_json(self.header())
        p = encode_tree(dict(self.payload), kind="event_payload", name=self.kind, version=1)
        return length_prefixed([h, p])

    @classmethod
    def decode(cls, data: bytes) -> Event:
        hlen = int.from_bytes(data[:8], "little")
        h = json.loads(data[8 : 8 + hlen].decode("ascii"))
        plen = int.from_bytes(data[8 + hlen : 16 + hlen], "little")
        p = decode_tree(data[16 + hlen : 16 + hlen + plen], kind="event_payload").tree
        if 16 + hlen + plen != len(data):
            raise EventError("trailing bytes in event encoding")
        return cls(h["t_ns"], h["kind"], h["target"], p, h["priority"], h["seq"], h["source"])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Event) and self.encode() == other.encode()

    def __hash__(self) -> int:  # consistent with __eq__; in-process use only (never persisted)
        return int(digest(self.encode(), PERSON_EVENTS, 8), 16)

    def __repr__(self) -> str:
        pay = {k: np.asarray(v).tolist() for k, v in self.payload.items()}
        return (
            f"Event(t_ns={self.t_ns}, kind={self.kind!r}, target={self.target!r}, "
            f"prio={self.priority}, seq={self.seq}, payload={pay})"
        )


class EventQueue:
    """Deterministic priority queue keyed by ``(t_ns, priority, seq)``."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, int, Event]] = []
        self._next_seq = 0

    @property
    def next_seq(self) -> int:
        return self._next_seq

    def push(self, event: Event) -> Event:
        """Stamp ``event`` with the next insertion sequence number; enqueue and return the stamped copy."""
        ev = event.with_seq(self._next_seq)
        self._next_seq += 1
        heapq.heappush(self._heap, (ev.t_ns, ev.priority, ev.seq, ev))
        return ev

    def push_all(self, events: Iterable[Event]) -> list[Event]:
        return [self.push(e) for e in events]

    def peek(self) -> Event | None:
        return self._heap[0][3] if self._heap else None

    def next_time(self) -> int | None:
        return self._heap[0][0] if self._heap else None

    def pop(self) -> Event:
        if not self._heap:
            raise EventError("pop from an empty event queue")
        return heapq.heappop(self._heap)[3]

    def pop_due(self, t_ns: int) -> Event | None:
        """Pop the earliest event if its time is ``<= t_ns``."""
        if self._heap and self._heap[0][0] <= t_ns:
            return heapq.heappop(self._heap)[3]
        return None

    def __len__(self) -> int:
        return len(self._heap)

    def pending(self) -> list[Event]:
        return [e for *_, e in sorted(self._heap, key=lambda x: x[:3])]

    def copy(self) -> EventQueue:
        q = EventQueue()
        q._heap = list(self._heap)
        q._next_seq = self._next_seq
        return q

    # --------------------------------------------------------------------------------- state round trip
    def get_state(self) -> bytes:
        evs = self.pending()
        header = canonical_json({"format": QUEUE_FORMAT_VERSION, "next_seq": self._next_seq, "n": len(evs)})
        return b"PHXQ" + length_prefixed([header, *(e.encode() for e in evs)])

    @classmethod
    def from_state(cls, data: bytes) -> EventQueue:
        if data[:4] != b"PHXQ":
            raise StateError("not an event-queue encoding")
        pos = 4
        parts: list[bytes] = []
        while pos < len(data):
            n = int.from_bytes(data[pos : pos + 8], "little")
            parts.append(data[pos + 8 : pos + 8 + n])
            pos += 8 + n
        header = json.loads(parts[0].decode("ascii"))
        if header["format"] != QUEUE_FORMAT_VERSION or header["n"] != len(parts) - 1:
            raise StateError("event-queue header mismatch")
        q = cls()
        evs = [Event.decode(p) for p in parts[1:]]
        q._heap = [(e.t_ns, e.priority, e.seq, e) for e in evs]  # sorted list is a valid heap
        heapq.heapify(q._heap)
        q._next_seq = int(header["next_seq"])
        if any(e.seq >= q._next_seq or e.seq < 0 for e in evs):
            raise StateError("event seq numbers inconsistent with next_seq")
        if q.get_state() != data:
            raise StateError("event-queue bytes are not canonical")
        return q

    def digest(self) -> str:
        return digest(self.get_state(), PERSON_EVENTS)


def event_log_digest(events: Iterable[Event]) -> str:
    """Hash of an ordered event log (e.g. the order log injected into a run)."""
    return digest(length_prefixed([e.encode() for e in events]), PERSON_EVENTS)
