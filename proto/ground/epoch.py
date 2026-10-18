"""The daily decision cycle (DEVELOPMENT.md §2.8): SNAPSHOT → ENGINES → BOARD_OPEN → FROZEN → SUBMITTED → next day.

Logical time: every event carries its own time on the epoch's day — 06:00 snapshot, 06:04 engines, the board's
session clock while people decide (06:05 + elapsed time, never past 07:44), 07:45 freeze, 08:00 orders, and the data
layer's own status times for outcomes. Nothing waits for the wall clock; ``advance()`` runs the rest of the day.

The engines/triage/policies step is pluggable (``board_builder``) so the loop runs end to end before every engine
exists: with no builder the board is empty and the fleet follows the station routine (status quo).
"""

from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from interfaces import DAY, NS, CandidateOrder, Issue
from lel import EventLog
from orders import OrderDesk
from store import Store
from twin import Twin

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SNAPSHOT_H, FREEZE_H, ORDERS_H = 6, (7, 45), 8
MIN = 60 * NS

#: (store, twin, t) -> (board issues, [(candidate order, policy semver)], optional funnel {alert_rows, issues, open, days})
BoardBuilder = Callable[[Store, Twin, int], tuple]
#: (store, twin, t) -> {issue_id: {policy: Evaluation(version, row, output, input, trace, trace_hash)}}
EvaluationsFn = Callable[[Store, Twin, int], dict]


def at(t_day: int, h: int, m: int = 0) -> int:
    d = dt.datetime.fromtimestamp(t_day / NS, IST).date()
    return int(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=IST).timestamp()) * NS


@dataclass
class EpochState:
    t_snapshot: int  # 06:00 IST
    t_orders: int  # 08:00 IST
    state: str = "SNAPSHOT"
    snapshot_id: str = ""
    issues: list[Issue] = field(default_factory=list)
    desk: OrderDesk | None = None
    verdicts: dict[str, Any] = field(default_factory=dict)
    load: dict[str, Any] = field(default_factory=dict)  # funnel counts from triage
    timeline: list[tuple[str, str]] = field(default_factory=list)  # (IST hh:mm, label)
    opened_wall: float = field(default_factory=time.time)

    @property
    def t_engines(self) -> int:
        return self.t_snapshot + 4 * MIN

    @property
    def t_board(self) -> int:
        return self.t_snapshot + 5 * MIN

    @property
    def t_freeze(self) -> int:
        return at(self.t_snapshot, *FREEZE_H)

    def clock_now(self) -> int:
        """The board's session clock: 06:05 when it opens, then real elapsed time, held below the 07:45 freeze;
        07:45 once frozen and 08:00 once the orders are out."""
        if self.state == "FROZEN":
            return self.t_freeze
        if self.state == "SUBMITTED":
            return self.t_orders
        elapsed = int((time.time() - self.opened_wall) * NS)
        return min(self.t_board + elapsed, self.t_freeze - MIN)


class Loop:
    def __init__(self, store: Store, twin: Twin, log: EventLog, runner_url: str = "http://127.0.0.1:8710",
                 board_builder: BoardBuilder | None = None, evaluations: EvaluationsFn | None = None) -> None:
        self.store, self.twin, self.log = store, twin, log
        self.runner = httpx.Client(base_url=runner_url, timeout=httpx.Timeout(1800.0))
        self.board_builder = board_builder
        self.evaluations = evaluations
        self.current: EpochState | None = None
        self.previous: EpochState | None = None  # the last submitted epoch (its orders and verdicts)

    # ---- steps -----------------------------------------------------------------------------------------
    def open(self, t_snapshot: int) -> EpochState:
        """06:00: seal the snapshot, run the engines, open the board."""
        self.store.refresh()
        self.twin.invalidate()
        ep = EpochState(t_snapshot=t_snapshot, t_orders=at(t_snapshot, ORDERS_H))
        ep.snapshot_id = self.store.snapshot_id(t_snapshot)
        subject = f"epoch:{ep.t_orders}"
        # reopening after an API restart: the epoch is already on the log — don't log it twice, restore decisions
        reopening = any(e.payload.get("snapshot_id") == ep.snapshot_id
                        for e in self.log.events(subject=subject, type="SNAPSHOT_SEALED"))
        log = (lambda *a, **k: None) if reopening else self.log.append
        log("SNAPSHOT_SEALED", subject, {"snapshot_id": ep.snapshot_id, "t": t_snapshot, "epoch": ep.t_orders}, t_snapshot)
        ep.timeline.append(("06:00", "Snapshot sealed"))
        ep.desk = OrderDesk(self.log, ep.t_orders, clock=ep.clock_now, t_freeze=ep.t_freeze)
        gate = {"files": sum(len(v) for v in self.store.files.values()), "rejected": len(self.store.rejected),
                "contract": "phalanx.ground_decoder_contract 0.2.0", "epoch": ep.t_orders}
        log("RELEASE_ADMITTED", subject, gate, t_snapshot)
        self._order_outcomes(t_snapshot)
        if self.board_builder is not None:
            built = self.board_builder(self.store, self.twin, t_snapshot)
            issues, candidates = built[0], built[1]
            ep.load = dict(built[2]) if len(built) > 2 else {}
            ep.issues = list(issues)
            evals = {}
            if self.evaluations is not None:
                try:
                    evals = self.evaluations(self.store, self.twin, t_snapshot) or {}
                except Exception:  # noqa: BLE001 — the board stands without the trace events
                    evals = {}
            for iss in ep.issues:
                log("ISSUE_TRIAGED", f"issue:{iss.issue_id}", {
                    "issue_id": iss.issue_id, "epoch": ep.t_orders, "band": iss.band, "C": iss.consequence,
                    "U": iss.urgency, "basis": iss.basis, "state": iss.state.value, "findings": [
                        {"engine": f.engine, "reason": f.reason, "beliefs": [b.__dict__ for b in f.beliefs]} for f in iss.findings]},
                    ep.t_engines)
                for name, ev in (evals.get(iss.issue_id) or {}).items():
                    log("POLICY_EVALUATED", f"issue:{iss.issue_id}", {
                        "issue_id": iss.issue_id, "epoch": ep.t_orders, "policy": name, "version": ev.version,
                        "row": ev.row, "input": ev.input, "output": ev.output, "trace_hash": ev.trace_hash}, ep.t_engines)
            for c, semver in candidates:
                d = ep.desk.propose(c, semver)
                ingested = self._ingested(c.evidence, t_snapshot)
                log("EVIDENCE_LINKED", f"order:{d.order_id}", {
                    "record_ids": [e.hex() for e in c.evidence], "all_ingested_by_snapshot": ingested}, ep.t_engines)
                log("RECOMMENDATION_PROPOSED", f"order:{d.order_id}", {
                    "issue_id": c.issue_id, "rule": c.rule, "row": c.row, "policy_version": c.policy_version,
                    "action": c.action, "parameters": dict(c.parameters), "authority": c.authority.value,
                    "mode": c.mode, "rationale": c.rationale}, ep.t_engines)
            log("ENGINE_RUN", subject, {"issues": len(ep.issues), "candidates": len(ep.desk.drafts)}, ep.t_engines)
        if reopening:
            self._restore(ep)
        ep.timeline.append(("06:04", "Engines done"))
        ep.state = "BOARD_OPEN"
        ep.opened_wall = time.time()
        ep.timeline.append(("06:05", "Board open"))
        self.current = ep
        return ep

    def _order_outcomes(self, t: int) -> None:
        """Statuses of our issued orders that the data layer reported by ``t`` (``orders.status``), each logged once
        at its own status time: the outcome side of the loop (QUEUED → IN_WORK → COMPLETED, with result records)."""
        st = self.store.df(t, "orders.status")
        if not len(st):
            return
        st = st[st.order_id.astype(str).str.startswith("phx:")]
        seen = {(e.payload.get("order_id"), e.payload.get("status_seq")) for e in self.log.events(type="ORDER_STATUS")}
        for r in st.sort_values(["t_status", "status_seq"]).itertuples():
            key = (r.order_id, int(r.status_seq))
            if key in seen:
                continue
            res = [bytes(x).hex() for x in (r.result_record_ids if r.result_record_ids is not None else [])]
            self.log.append("ORDER_STATUS", f"order:{r.order_id}", {
                "order_id": r.order_id, "status_seq": int(r.status_seq), "status": r.status,
                "reason": r.reason if isinstance(r.reason, str) else None, "t_status": int(r.t_status),
                "result_record_ids": res}, int(r.t_status))
            seen.add(key)

    def _restore(self, ep: EpochState) -> None:
        """Re-apply the human decisions already on the log for this epoch's orders (no new events). Order ids carry
        their epoch, so the events of this desk's orders are exactly this epoch's decisions."""
        for e in self.log.events():
            if not e.subject.startswith("order:"):
                continue
            d = ep.desk.drafts.get(e.subject.split(":", 1)[1])
            if d is None:
                continue
            p = e.payload
            if e.type == "ORDER_APPROVED":
                d.state, d.approved_by = "APPROVED", p.get("by")
            elif e.type == "ORDER_REJECTED":
                d.state, d.note = "REJECTED", p.get("note")
            elif e.type == "ORDER_SNOOZED":
                d.state, d.snooze_until = "SNOOZED", p.get("snooze_until")
            elif e.type == "ORDER_SIGNED":
                d.signed_by = p.get("by")
            elif e.type == "FORK_DROPPED":
                d.state, d.note = "DROPPED", p.get("reason")
            else:
                continue
            d.history.append(p | {"t": e.t_logical})

    def _ingested(self, evidence: Sequence[bytes], t: int) -> bool:
        """Every cited record id is in the as-of store by ``t`` (the data layer's gateway checks it again)."""
        if not evidence:
            return True
        have: set[str] = set()
        for topic in ("events.bit_faults", "events.cautions", "maint.records"):
            d = self.store.df(t, topic)
            if len(d):
                have |= set(d.rid)
        return all(e.hex() in have for e in evidence)

    def freeze(self) -> list[dict[str, Any]]:
        ep = self._ep("BOARD_OPEN")
        out = [d.command() for d in ep.desk.freeze()]
        ep.state = "FROZEN"
        ep.timeline.append(("07:45", "Board frozen"))
        return out

    def submit_and_step(self) -> dict[str, Any]:
        """08:00: hand the frozen orders to the runner, which submits them through the data layer's gateway at
        the epoch and runs every tail to the next 06:00. Then the next epoch opens."""
        ep = self._ep("FROZEN")
        by_tail: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for d in ep.desk.drafts.values():
            if d.issuable:
                by_tail[d.tail].append(d.command())
                d.state = "SUBMITTED"
        n = sum(len(v) for v in by_tail.values())
        self.log.append("ORDER_SUBMITTED", f"epoch:{ep.t_orders}",
                        {"orders": [o["order_id"] for v in by_tail.values() for o in v]}, ep.t_orders)
        nxt = ep.t_snapshot + DAY
        r = self.runner.post("/step", json={"to": nxt, "orders": by_tail})
        r.raise_for_status()
        res = r.json()
        for tail, vs in res.get("verdicts", {}).items():
            for v in vs:
                ep.verdicts[v["order_id"]] = v
                if v["order_id"] in ep.desk.drafts:
                    ep.desk.drafts[v["order_id"]].verdict = v
                self.log.append("GATEWAY_VERDICT", f"order:{v['order_id']}", {"tail": tail, **v}, ep.t_orders)
        ep.state = "SUBMITTED"
        ep.timeline.append(("08:00", f"{n} orders issued"))
        self.log.append("STEP_DONE", f"epoch:{ep.t_orders}", {"to": nxt, "rows": res.get("rows", {}),
                        "wall_s": res.get("wall_s"), "overlay": res.get("overlay")}, ep.t_orders)
        self.previous = ep
        return {"submitted": n, "verdicts": ep.verdicts, "next": self.open(nxt)}

    def advance(self) -> dict[str, Any]:
        """One whole cycle with whatever has been decided on the board."""
        if self.current is None:
            raise RuntimeError("no epoch open")
        if self.current.state == "BOARD_OPEN":
            self.freeze()
        return self.submit_and_step()

    def _ep(self, expect: str) -> EpochState:
        if self.current is None or self.current.state != expect:
            raise RuntimeError(f"epoch is {None if self.current is None else self.current.state}, expected {expect}")
        return self.current
