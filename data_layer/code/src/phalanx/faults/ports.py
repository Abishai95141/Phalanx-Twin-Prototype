"""Published ports and cross-module events of M11 (W1 interface convention; AD-42, AD-44).

M11 is event-only and has no ports: every fault reaches its state owner as an event. Cross-module kinds are
declared below for ``tests/integration/test_event_protocol.py`` (catalogue
``configs/interfaces/w1_events.yaml``). Its events to M10 (``health.fault``), M14 (``monitor.lru_condition``)
and the physics modules (``<prefix>.fault``) are W1.5/W1-internal names.
"""

from __future__ import annotations

from phalanx.core.module import Port

from .sensor_faults import SENSOR_FAULT_KEYS

PREFIX = "faults"


def ports(n_engines: int = 1, dictionary=None) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of M11: none."""
    del n_engines, dictionary
    return (), (), {}


MODULE_IDS = ("M11",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "truth.fault": ("fault_id", "tail", "pos", "serial", "mode", "symptom", "grounding"),
    "truth.fault_clear": ("fault_id",),
    "truth.incident": ("tail", "kind", "positions"),
    "util.fault": ("tail", "mode"),
    "fcs.channel_fault": ("tail", "channel", "subsystem", "active"),
    "fcs.actuator_fault": ("tail", "surface", "mode", "active", "channel"),
    "fcs.wow_fault": ("tail", "leg", "value", "active"),
    "sensor_fault": SENSOR_FAULT_KEYS,
    "eng.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear"),
    "fadec.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear"),
    "af.fault_inject": ("tail", "mode", "param", "instance", "engine", "clear", "leg"),
    # AD-49: start-failure route to M02 (target "ops")
    "ops.start_failure": ("tail_no", "sortie_id", "mode"),
}
#: AD-48.2: M11 follows the sortie (telemetry mode) from M02's take-off and sortie-done events; the handler
#: reads sortie_id, tail_no, t_takeoff, t_landing and the drivers / flight_hours (the rest is accepted)
EVENTS_IN: dict[str, tuple[str, ...]] = {
    # W2.5: engine start; preflight (start-failure) modes are drawn here (A-W2.1c-6)
    "ops.power_up": ("tail_no", "sortie_id", "engine_starts", "cold_soak"),
    "ops.takeoff": (
        "sortie_id",
        "tail_no",
        "t_takeoff",
        "t_landing",
        "ab_lights",
        "engine_starts",
        "landings",
        "dust_index",
    ),
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
}
