"""The orders gateway: the one door through which decisions enter the simulated fleet (AD-16, architecture
§11.1).

``submit`` validates each order and injects it into the world as an ``order.submit`` event at its issue time,
so the verdict is part of the logged order stream and replaying the order log reproduces the session (I1,
AD-16):

1. idempotency: an ``order_id`` already known to the world (or earlier in the same batch) is a no-op;
2. the issue instant must be "now" (orders are not issued in the past or the future of the session clock);
3. contract-schema validation of the ``orders.commands`` row plus the per-action parameter schema;
4. authority (issuer kind allowed for the action, ``configs/policies/authority.yaml``);
5. **information discipline (I5):** every evidence ``record_id`` must have been ingested by ``t_issued`` in
the decision-maker's observation set (``ObservationView.ingested`` semantics; indexed). An order citing
un-ingested evidence is rejected, which blocks look-ahead;
6. the order is applied at the first decision epoch at or after ``max(t_issued, t_effective)``.

Rejected orders still produce their ``orders.commands`` row and a REJECTED status with the reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from phalanx.core.events import Event
from phalanx.core.scheduler import System, World
from phalanx.dictionary.contract import Contract
from phalanx.health.protocol import plain_payload, read_payload

from .epochs import PRIO_ORDER_SUBMIT, DecisionCalendar
from .model import Order, check_parameters, contract_errors, order_row
from .rules import Authority


class ObservationSource(Protocol):
    def ingested(self, t: int, record_ids: Sequence[bytes]) -> np.ndarray: ...


@dataclass(frozen=True)
class SubmitResult:
    order_id: str
    verdict: str  # ACCEPTED, REJECTED (both logged), DUPLICATE or INVALID (no-op, nothing injected)
    reason: str | None
    t_apply: int | None  # kernel ns of the decision epoch at which the order applies


def logged_order_ids(order_log: Sequence[Event], m21_id: str) -> set[str]:
    """order_ids of every order.submit event in a world's order log (the idempotency memory survives
    snapshots because the order log is part of the world)."""
    out: set[str] = set()
    for ev in order_log:
        if ev.kind == "order.submit" and ev.target == m21_id:
            out.add(read_payload(ev.payload)["row"]["order_id"])
    return out


class OrderGateway:
    def __init__(
        self,
        *,
        contract: Contract,
        calendar: DecisionCalendar,
        authority: Authority,
        epoch_utc_ns: int,
        m21_id: str = "m21",
    ) -> None:
        self.contract = contract
        self.calendar = calendar
        self.authority = authority
        self.epoch = int(epoch_utc_ns)
        self.m21_id = m21_id

    def evaluate(
        self, order: Order, now_kernel: int, observations: ObservationSource | None
    ) -> tuple[str, str | None, int | None]:
        """(verdict, reason, t_apply kernel) for one order (no idempotency check)."""
        cerr = contract_errors(order, self.contract)
        if cerr:
            return "INVALID", "; ".join(cerr), None
        t_i = order.t_issued - self.epoch
        if t_i != now_kernel:
            return (
                "REJECTED",
                f"t_issued {order.t_issued} is not the session time {self.epoch + now_kernel}",
                None,
            )
        errs = check_parameters(order)
        if errs:
            return "REJECTED", "invalid order: " + "; ".join(errs), None
        if not self.authority.allowed(order.action, order.issuer_kind):
            return "REJECTED", f"issuer kind {order.issuer_kind} has no authority for {order.action}", None
        if order.evidence:
            if observations is None:
                return "REJECTED", "no observation set to check evidence against", None
            ok = observations.ingested(order.t_issued, list(order.evidence))
            if not bool(np.all(ok)):
                missing = [bytes(r).hex() for r, k in zip(order.evidence, ok, strict=True) if not k]
                return "REJECTED", "evidence not ingested by t_issued: " + ",".join(missing), None
        t_apply = self.calendar.next_epoch(max(order.t_effective - self.epoch, t_i))
        return "ACCEPTED", None, t_apply

    def submit(
        self,
        system: System,
        world: World,
        orders: Sequence[Order],
        observations: ObservationSource | None,
    ) -> tuple[World, list[SubmitResult]]:
        m21 = system.modules[self.m21_id]
        state = world.states[self.m21_id]
        seen: set[str] = logged_order_ids(world.order_log, self.m21_id)  # injected, maybe not yet dispatched
        events: list[Event] = []
        results: list[SubmitResult] = []
        for o in orders:
            if o.order_id in seen or m21.known(state, o.order_id):
                results.append(
                    SubmitResult(o.order_id, "DUPLICATE", "order_id already received (no-op)", None)
                )
                continue
            seen.add(o.order_id)
            verdict, reason, t_apply = self.evaluate(o, world.t_ns, observations)
            if verdict == "INVALID":  # not a contract-valid order record: never enters the world
                results.append(SubmitResult(o.order_id, "INVALID", reason, None))
                continue
            row = order_row(o, self.contract, dict_version=None, dict_hash=None)
            doc = {"row": row, "verdict": verdict, "reason": reason, "t_apply": t_apply}
            events.append(
                Event(
                    world.t_ns,
                    "order.submit",
                    self.m21_id,
                    plain_payload(doc),
                    priority=PRIO_ORDER_SUBMIT,
                    source="orders",
                )
            )
            results.append(SubmitResult(o.order_id, verdict, reason, t_apply))
        if events:
            world = system.inject(world, events)
        return world, results
