"""The one event log: every transition of the ground side is an append-only, hash-chained event in SQLite.

``hash = blake2b-256(prev_hash ‖ seq ‖ type ‖ canonical_json(payload))`` with ``prev_hash`` of the first event
= 64 zeros. The model registry, issue history and provenance are queries over this table (DEVELOPMENT.md §2.10).
The API process is the single writer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GENESIS = "00" * 32
TYPES = {
    "RUN_STARTED", "SNAPSHOT_SEALED", "ENGINE_RUN", "MODEL_REGISTERED", "GATE_RESULT", "ISSUE_STATE_CHANGED",
    "POLICY_EVALUATED", "FORK_RESULT", "BOARD_FROZEN", "ORDER_APPROVED", "ORDER_MODIFIED", "ORDER_REJECTED",
    "ORDER_SNOOZED", "ORDER_SIGNED", "ORDER_SUBMITTED", "GATEWAY_VERDICT", "ORDER_STATUS", "OUTCOME_LABELLED",
    "STEP_DONE", "CHAIN_VERIFIED", "RELEASE_ADMITTED", "EVIDENCE_LINKED", "FINDING", "ISSUE_TRIAGED",
    "RECOMMENDATION_PROPOSED", "FORK_DROPPED",
}


def canonical(obj: Any) -> str:
    def default(o):
        if isinstance(o, bytes):
            return o.hex()
        if isinstance(o, set | frozenset | tuple):
            return sorted(o) if isinstance(o, set | frozenset) else list(o)
        raise TypeError(f"not JSON-serialisable: {type(o)}")

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default)


def chain_hash(prev: str, seq: int, typ: str, payload_json: str) -> str:
    h = hashlib.blake2b(digest_size=32)
    h.update(bytes.fromhex(prev))
    h.update(f"|{seq}|{typ}|".encode())
    h.update(payload_json.encode())
    return h.hexdigest()


@dataclass(frozen=True)
class Event:
    seq: int
    t_logical: int  # UTC ns of the epoch the event belongs to
    t_wall: float
    type: str
    subject: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, t_logical INTEGER NOT NULL, "
            "t_wall REAL NOT NULL, type TEXT NOT NULL, subject TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "prev_hash TEXT NOT NULL, hash TEXT NOT NULL UNIQUE)"
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS events_subject ON events(subject)")
        self.db.execute("CREATE INDEX IF NOT EXISTS events_type ON events(type)")

    def head(self) -> tuple[int, str]:
        row = self.db.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return (0, GENESIS) if row is None else (int(row[0]), str(row[1]))

    def append(self, typ: str, subject: str, payload: dict[str, Any], t_logical: int) -> Event:
        if typ not in TYPES:
            raise ValueError(f"unknown event type {typ}")
        body = canonical(payload)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            seq, prev = self.head()
            seq += 1
            h = chain_hash(prev, seq, typ, body)
            wall = time.time()
            self.db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (seq, int(t_logical), wall, typ, subject, body, prev, h),
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Event(seq, int(t_logical), wall, typ, subject, json.loads(body), prev, h)

    def events(self, *, subject: str | None = None, type: str | None = None, since_seq: int = 0) -> Iterator[Event]:
        q, args = "SELECT * FROM events WHERE seq > ?", [since_seq]
        if subject is not None:
            q += " AND subject = ?"
            args.append(subject)
        if type is not None:
            q += " AND type = ?"
            args.append(type)
        for r in self.db.execute(q + " ORDER BY seq", args):
            yield Event(int(r[0]), int(r[1]), float(r[2]), r[3], r[4], json.loads(r[5]), r[6], r[7])

    def verify(self) -> dict[str, Any]:
        """Recompute the whole chain. Returns ok, events checked and the first broken seq (if any)."""
        prev, n = GENESIS, 0
        for r in self.db.execute("SELECT seq, type, payload_json, prev_hash, hash FROM events ORDER BY seq"):
            n += 1
            seq, typ, body, p, h = int(r[0]), r[1], r[2], r[3], r[4]
            if p != prev or chain_hash(prev, seq, typ, body) != h or seq != n:
                return {"ok": False, "events": n, "broken_at": seq}
            prev = h
        return {"ok": True, "events": n, "head": prev}
