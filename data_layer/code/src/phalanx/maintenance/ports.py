"""M18 published ports (W1 interface convention, ``W1_interfaces.md`` §1).

M18 is an event-only operations-layer module: it has no truth-layer ports (usage mode has no 240 Hz signals to
read, and event-only modules receive no port inputs). It exchanges events with M02, M10/M11, M14 and M21 (the
operations event protocol in ``src/phalanx/maintenance/README.md``) and publishes contract records through the
record sink. Nothing here needs a ``configs/interfaces/w1_ports.yaml`` entry.
"""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "maint"


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    del n_engines  # the operations layer is per fleet, not per engine
    return (), (), {}


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py
MODULE_IDS = ("M18",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "ops.offer": ("day", "tails", "restrict"),
    "ops.launch_denied": ("sortie_id", "tail_no", "reason"),
    "ops.assign": ("tail_no", "order_id"),
    "ops.restrict": ("tail_no",),
    "cfg.install": ("tail", "pos", "serial", "cls"),
    "cfg.remove": ("tail", "pos", "serial"),
    "mx.action": ("tail", "action"),
    "mx.repaired": ("serial", "level"),
    "mx.monitoring": ("tail",),
    "order.progress": ("order_id", "status", "reason", "result_record_ids"),
}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "ops.offer_request": ("day", "reply_to"),
    "ops.launch": ("sortie_id", "tail_no", "reply_to"),
    "ops.ground_abort": ("tail_no", "sortie_id"),
    "ops.sortie_done": (
        "sortie_id",
        "tail_no",
        "t_takeoff",
        "t_landing",
        "flight_hours",
        "landings",
        "engine_cycles",
        "engine_starts",
        "chute_streamed",
        "mission_type",
        "crew_id",
        "aborted",
    ),
    "obs.event": ("topic", "row"),
    "truth.fault": ("fault_id", "tail", "pos", "serial", "mode", "symptom", "grounding"),
    "truth.fault_clear": ("fault_id",),
    "truth.incident": ("tail", "kind", "positions"),
    "order.exec": ("order",),
    "m18.disruption": ("cls", "factor", "t0", "t1"),
}
