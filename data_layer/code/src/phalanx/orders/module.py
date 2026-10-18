"""M21 in-simulation order registry (event-only core module) and the record sink.

``OrdersModule`` receives every submitted order as an ``order.submit`` event (injected by the gateway, so it
is in the world's order log: a run is f(seed, config, dictionary, order log), AD-16). It is idempotent on
``order_id``, publishes the ``orders.commands`` row and the ``orders.status`` lifecycle (status_seq 0, 1,
...), and forwards accepted orders to M18 at their decision epoch. M18 reports QUEUED / IN_WORK / COMPLETED /
REJECTED back with ``order.progress``.

``RecordSink`` is the terminal of every ``rec.<topic>`` and ``kpi.*`` event: the session reads records from
the kernel's dispatch log, so record volume never grows module state.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from phalanx.core.canonical import canonical_json
from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, Param, ParamSet
from phalanx.core.state import Field, State, StateSchema
from phalanx.health.protocol import plain_payload, read_payload
from phalanx.maintenance.docstate import Cow, encode_doc
from phalanx.maintenance.records import ORDERS_COMMANDS, ORDERS_STATUS, contract_v0, orders_status_row
from phalanx.maintenance.timebase import check_whole_second

from .epochs import PRIO_ORDER_APPLY

ORDERS_SCHEMA = StateSchema(
    "orders.registry", 1, (Field("doc_orders", "|u1", (None,)), Field("n_orders", "<i8"))
)
SINK_SCHEMA = StateSchema("ops.sink", 1, (Field("n_seen", "<i8"),))


class OrdersModule(ModuleBase):
    version = "1.0.0"
    rate = None
    state_schema = ORDERS_SCHEMA

    def __init__(
        self,
        id: str,
        *,
        epoch_utc_ns: int,
        dict_version: str,
        dict_hash: str,
        m18: str = "m18",
        sink: str = "sink",
    ) -> None:
        params = ParamSet(
            "tejas.M21.module",
            {
                "cfg_routing": Param(
                    canonical_json({"m18": m18, "sink": sink}).decode(),
                    "1",
                    "ASSUMPTION",
                    "M21 routing: every order goes to M18, which forwards programme orders to M02",
                ),
                "cfg_epoch_utc": Param(
                    int(epoch_utc_ns), "ns", "ASSUMPTION", "run epoch (M02 scenario.epoch_utc_ns)"
                ),
                "cfg_dict": Param(
                    f"{dict_version}:{dict_hash}", "1", "DIRECT", "M01 dictionary version and hash"
                ),
            },
        )
        super().__init__(id, params)
        self.epoch = check_whole_second(epoch_utc_ns, "run epoch")
        self.m18 = m18
        self.sink = sink
        self.dict_version = dict_version
        self.dict_hash = dict_hash
        self.contract = contract_v0()

    def init(self, params: ParamSet, keys) -> State:
        return {"doc_orders": encode_doc({}), "n_orders": np.array(0, dtype=np.int64)}

    def initial_outputs(self, state: State) -> dict[str, np.ndarray]:
        return {}

    def known(self, state: State, order_id: str) -> bool:
        return order_id in json.loads(np.asarray(state["doc_orders"]).tobytes().decode("ascii"))

    def _emit_rec(self, out: list[Event], t: int, topic: str, row: dict[str, Any]) -> None:
        out.append(Event(t, f"rec.{topic}", self.sink, plain_payload({"row": row}), source=self.id))

    def _status(
        self, out: list[Event], t: int, oid: str, seq: int, status: str, reason: str | None, rids: list[str]
    ) -> None:
        row = orders_status_row(
            self.contract,
            dict_version=self.dict_version,
            dict_hash=self.dict_hash,
            order_id=oid,
            status_seq=seq,
            status=status,
            t_status=self.epoch + t,
            reason=reason,
            result_record_ids=rids,
        )
        self._emit_rec(out, t, ORDERS_STATUS, row)

    def on_event(self, state: State, event: Event, t: int):
        doc = read_payload(event.payload)
        cow = Cow(state)
        reg = cow.doc("doc_orders")
        out: list[Event] = []
        now = event.t_ns
        if event.kind == "order.submit":
            row = doc["row"]
            oid = row["order_id"]
            if oid in reg:  # idempotent: re-sending an order_id is a no-op
                return state, []
            accepted = doc["verdict"] == "ACCEPTED"
            reg[oid] = {"seq": 1, "done": not accepted, "action": row["action"]}
            cow.touch("doc_orders")
            cow.put("n_orders", np.array(int(state["n_orders"]) + 1, dtype=np.int64))
            self._emit_rec(out, now, ORDERS_COMMANDS, row)
            self._status(out, now, oid, 0, doc["verdict"], doc.get("reason"), [])
            if accepted:
                out.append(
                    Event(
                        int(doc["t_apply"]),
                        "order.exec",
                        self.m18,
                        plain_payload({"order": row}),
                        priority=PRIO_ORDER_APPLY,
                        source=self.id,
                    )
                )
        elif event.kind == "order.progress":
            oid = doc["order_id"]
            e = reg.get(oid)
            if e is None or e["done"]:
                return state, []
            self._status(
                out,
                now,
                oid,
                int(e["seq"]),
                doc["status"],
                doc.get("reason"),
                list(doc.get("result_record_ids") or []),
            )
            e["seq"] = int(e["seq"]) + 1
            e["done"] = doc["status"] in ("COMPLETED", "REJECTED")
            cow.touch("doc_orders")
        else:
            return super().on_event(state, event, t)
        return cow.commit(), out


class RecordSink(ModuleBase):
    """Terminal for ``rec.<topic>`` and ``kpi.*`` events (read back from the dispatch log by the session)."""

    version = "1.0.0"
    rate = None
    state_schema = SINK_SCHEMA

    def __init__(self, id: str = "sink") -> None:
        super().__init__(id, ParamSet("ops.sink", {}))

    def init(self, params: ParamSet, keys) -> State:
        return {"n_seen": np.array(0, dtype=np.int64)}

    def initial_outputs(self, state: State) -> dict[str, np.ndarray]:
        return {}

    def on_event(self, state: State, event: Event, t: int):
        if not (event.kind.startswith("rec.") or event.kind.startswith("kpi.")):
            return super().on_event(state, event, t)
        return state, []
