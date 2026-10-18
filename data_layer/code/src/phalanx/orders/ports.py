"""M21 published ports (W1 interface convention, ``W1_interfaces.md`` §1).

The in-simulation order registry (``OrdersModule``) is event-only: orders arrive as ``order.submit`` events
injected by the gateway (logged in the world's order log) and leave as ``order.exec`` events to M18; status
flows back as ``order.progress``. No truth-layer ports, so no ``w1_ports.yaml`` entry.
"""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "orders"


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    del n_engines
    return (), (), {}


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py
MODULE_IDS = ("M21",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "order.exec": ("order",),
}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "order.progress": ("order_id", "status", "reason", "result_record_ids"),
    # AD-49: the RecordSink terminates M02's daily flying task (read back from the dispatch log by M22)
    "kpi.plan": ("t_utc", "date", "planned_sorties", "planned_fh"),
}
