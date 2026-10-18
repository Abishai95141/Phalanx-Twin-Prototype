"""Closed-loop operations session (M21 + M22 plumbing): kernel world, record log, observation set, gateway.

``OpsSession`` advances a usage-mode world in simulation time, reads every record the modules emitted from the
kernel's dispatch log, keeps the **truth** rows in an append-only :class:`RecordLog` (restricted: KPIs,
labels, validation), applies the post-truth data-quality defects (M18 ``DefectInjector``) and publishes the
**consumer** view to the decision-maker's observation set (``MemoryObservations``, and optionally a
``ParquetStore``). Orders enter through the :class:`~phalanx.orders.gateway.OrderGateway` at the current
session time.

Information discipline (I5): observations hold only consumer-visible topics with their ingest times; a policy
reads them through ``as_of(t)``; truth rows never leave the record log.

A session is a pure function of (root seed, builder configuration, dictionary, order log): ``snapshot``
captures the world (core snapshot, AD-36) plus the record and observation prefixes; ``OpsSession.restore``
continues it bit for bit (A5/A7).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from phalanx.core.canonical import PERSON_SNAPSHOT, canonical_json, digest
from phalanx.core.rng import DrawLedger
from phalanx.core.scheduler import Trace
from phalanx.core.snapshot import restore as core_restore
from phalanx.core.snapshot import snapshot as core_snapshot
from phalanx.core.snapshot import snapshot_id
from phalanx.core.time import latest_truth_step, truth_step_time_ns
from phalanx.dictionary.contract import Contract
from phalanx.health.protocol import read_payload
from phalanx.maintenance.records import LABELS, MAINT, contract_v0, rows_to_table
from phalanx.orders.gateway import OrderGateway, SubmitResult
from phalanx.orders.model import Order
from phalanx.orders.rules import Authority, load_authority
from phalanx.streaming.memory_view import MemoryObservations
from phalanx.streaming.parquet_store import ParquetStore

from .builder import WorldBuilder

PERSON_LOG = b"phx.opslog.v1"


class RecordLog:
    """Append-only rows per topic (JSON-document form) with a content digest of everything appended.

    The digest is a per-topic hash chain over rows in emission order, so it does not depend on how the run was
    cut into ``run_until`` segments (a replay with other stopping points has the same digest).
    ``fork`` is copy-on-write: the child shares the row dicts and continues the parent's chains.
    """

    def __init__(self) -> None:
        self._rows: dict[str, list[dict[str, Any]]] = {}
        self._hints: dict[str, list[dict[str, Any] | None]] = {}
        self._chains: dict[str, bytes] = {}

    def append(
        self, topic: str, rows: Sequence[dict[str, Any]], hints: Sequence[dict[str, Any] | None] | None = None
    ) -> None:
        if not rows:
            return
        self._rows.setdefault(topic, []).extend(rows)
        self._hints.setdefault(topic, []).extend(hints if hints is not None else [None] * len(rows))
        chain = self._chains.get(topic, b"")
        for r in rows:
            body = json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            chain = hashlib.blake2b(chain + body.encode("ascii"), digest_size=32, person=PERSON_LOG).digest()
        self._chains[topic] = chain

    def rows(self, topic: str) -> list[dict[str, Any]]:
        return list(self._rows.get(topic, []))

    def hints(self, topic: str) -> list[dict[str, Any] | None]:
        return list(self._hints.get(topic, []))

    def topics(self) -> list[str]:
        return sorted(self._rows)

    @property
    def digest(self) -> str:
        return digest(canonical_json({t: self._chains[t].hex() for t in sorted(self._chains)}), PERSON_LOG)

    def fork(self) -> RecordLog:
        child = RecordLog()
        child._rows = {k: list(v) for k, v in self._rows.items()}
        child._hints = {k: list(v) for k, v in self._hints.items()}
        child._chains = dict(self._chains)
        return child


@dataclass(frozen=True)
class SessionSnapshot:
    """A content-hashed decision-epoch snapshot (world + record and observation prefixes)."""

    core: bytes
    t: int
    root: int
    log: RecordLog = field(repr=False)
    obs: MemoryObservations | None = field(repr=False)
    parent: str = ""

    @property
    def id(self) -> str:
        return digest(
            canonical_json(
                {"core": snapshot_id(self.core), "log": self.log.digest, "t": self.t, "parent": self.parent}
            ),
            PERSON_SNAPSHOT,
        )


def _step_at_or_after(t_ns: int) -> int:
    return 0 if t_ns <= 0 else latest_truth_step(t_ns - 1) + 1


class OpsSession:
    """A live, deterministic closed-loop operations session (usage mode)."""

    def __init__(
        self,
        builder: WorldBuilder,
        root: int,
        *,
        observe: bool = True,
        store: ParquetStore | None = None,
        defects: Any | None = None,
        ledger: DrawLedger | None = None,
        authority: Authority | None = None,
        contract: Contract | None = None,
        _snapshot: SessionSnapshot | None = None,
        _strict: bool = True,
    ) -> None:
        self.builder = builder
        self.root = int(root)
        self.contract = contract or contract_v0()
        self.system = builder.build(self.root, ledger=ledger)
        self.store = store
        self.defects = defects
        self.gateway = OrderGateway(
            contract=self.contract,
            calendar=builder.calendar,
            authority=authority or load_authority(),
            epoch_utc_ns=builder.epoch_utc_ns,
            m21_id=builder.ids.m21,
        )
        self.parent = ""
        if _snapshot is None:
            self.world = self.system.inject(self.system.start(), builder.initial_events())
            self.log = RecordLog()
            self.obs = MemoryObservations(self.contract) if observe else None
        else:
            self.world = core_restore(self.system, _snapshot.core, strict=_strict)
            self.log = _snapshot.log.fork()
            self.obs = (
                _snapshot.obs.fork()
                if (observe and _snapshot.obs is not None)
                else (MemoryObservations(self.contract) if observe else None)
            )
            self.parent = _snapshot.id
        self.submissions: list[SubmitResult] = []

    # ---- time ----------------------------------------------------------------------------------------------
    @property
    def t(self) -> int:
        """Current kernel time (ns): every event before it has been processed, none at or after it."""
        return self.world.t_ns

    @property
    def t_utc(self) -> int:
        return self.builder.epoch_utc_ns + self.t

    def run_until(self, t_kernel: int) -> None:
        """Advance to the step boundary at ``t_kernel`` (events at exactly ``t_kernel`` are not yet
        processed)."""
        k = _step_at_or_after(int(t_kernel))
        if truth_step_time_ns(k) != int(t_kernel):
            raise ValueError("operations sessions stop on whole-second boundaries (exact truth frames)")
        n = k - self.world.k
        if n < 0:
            raise ValueError(f"cannot run backwards: session at {self.t}, asked {t_kernel}")
        if n == 0:
            return
        self.world, trace = self.system.run(self.world, n)
        self._collect(trace)

    # ---- records -------------------------------------------------------------------------------------------
    def _collect(self, trace: Trace) -> None:
        by_topic: dict[str, list[dict[str, Any]]] = {}
        hints: dict[str, list[dict[str, Any] | None]] = {}
        for _, ev in trace.dispatched:
            if ev.target != self.builder.ids.sink:
                continue
            doc = read_payload(ev.payload)  # AD-48.1 plain keys (phalanx.health.protocol)
            if ev.kind.startswith("rec."):
                topic = ev.kind[4:]
                by_topic.setdefault(topic, []).append(doc["row"])
                hints.setdefault(topic, []).append(doc.get("hints"))
            else:  # kpi.* bookkeeping events (scenario plan, cancellations): not contract topics
                by_topic.setdefault(ev.kind, []).append(doc)
                hints.setdefault(ev.kind, []).append(None)
        for topic in sorted(by_topic):
            self._ingest(topic, by_topic[topic], hints[topic])

    def _ingest(self, topic: str, rows: list[dict[str, Any]], hints: list[dict[str, Any] | None]) -> None:
        self.log.append(topic, rows, hints)
        if topic not in self.contract.topics:
            return
        if topic == LABELS:
            table = rows_to_table(self.contract, topic, rows)
            if self.store is not None:
                self.store.write(topic, table)
            return
        observed, manifest = rows, []
        if topic == MAINT and self.defects is not None:
            observed, manifest = self.defects.apply(rows, hints)
        table = rows_to_table(self.contract, topic, observed) if observed else None
        if table is not None and self.obs is not None:
            self.obs.append(topic, table)
        if table is not None and self.store is not None:
            self.store.write(topic, table)
        if manifest:
            self.log.append(LABELS, manifest)
            if self.store is not None:
                self.store.write(LABELS, rows_to_table(self.contract, LABELS, manifest))

    def records(self, topic: str) -> list[dict[str, Any]]:
        """Truth rows of ``topic`` emitted so far (restricted: KPIs and validation only)."""
        return self.log.rows(topic)

    # ---- orders --------------------------------------------------------------------------------------------
    def submit(self, orders: Iterable[Order]) -> list[SubmitResult]:
        self.world, res = self.gateway.submit(self.system, self.world, list(orders), self.obs)
        self.submissions.extend(res)
        return res

    # ---- snapshots -----------------------------------------------------------------------------------------
    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            core=core_snapshot(self.system, self.world, parent=self.parent),
            t=self.t,
            root=self.root,
            log=self.log.fork(),
            obs=self.obs.fork() if self.obs is not None else None,
            parent=self.parent,
        )

    @classmethod
    def restore(
        cls,
        builder: WorldBuilder,
        snap: SessionSnapshot,
        *,
        root: int | None = None,
        observe: bool = True,
        defects: Any | None = None,
        ledger: DrawLedger | None = None,
        store: ParquetStore | None = None,
    ) -> OpsSession:
        """Continue from ``snap``. Same root = strict restore (bitwise continuation); another root = an
        ensemble member (same state, different exogenous future)."""
        r = snap.root if root is None else int(root)
        return cls(
            builder,
            r,
            observe=observe,
            defects=defects,
            ledger=ledger,
            store=store,
            _snapshot=snap,
            _strict=r == snap.root,
        )
