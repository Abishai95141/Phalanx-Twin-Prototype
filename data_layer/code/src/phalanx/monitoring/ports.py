"""Published ports of M14 (AD-42: LRU-computed recorded channels are supplied by their owning module).

M14 is event-only and has no input ports (CIR, controller reports and LRU conditions arrive as events; see
``phalanx.monitoring.module``). Its held outputs are the CWS words, each a dictionary channel the recorder
(M13) logs via ``external=``: ``RECORDED`` maps port name -> channel id. Values are the dimensionless bitfield
words of the dictionary encodings (``phalanx.monitoring.cws``).
"""

from __future__ import annotations

from phalanx.core.module import Port

from .cws import CWS_PORTS

PREFIX = "monitor"
#: output port -> dictionary channel id (``signal: computed``, ``acq_lru: CWS``)
RECORDED: dict[str, str] = dict(CWS_PORTS)


def ports(n_engines: int = 1, dictionary=None) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of M14 (independent of ``n_engines``)."""
    return (), tuple(Port(p, "1", "<i8", ()) for p in CWS_PORTS), {}


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml); checked by
# tests/integration/test_event_protocol.py. Its other inputs (monitor.*) are W1.5/W2.1-internal hooks.
MODULE_IDS = ("M14",)
#: M08 FADEC fault/caution payload (the handler reads engine, code, set, lane and t_frame_ns)
FADEC_KEYS = ("engine", "code", "set", "sensor", "lane", "description", "t_frame_ns", "frame")
EVENTS_OUT: dict[str, tuple[str, ...]] = {
    "obs.event": ("topic", "row"),
    # AD-49: the cockpit alerts the pilot reacts to (``pilot_target`` = M04)
    "pilot.fire_warning": ("tail", "code"),
    "pilot.fcs_caution": ("tail", "code"),
}
#: AD-48.2: M02's sortie lifecycle (M14 reads sortie_id, tail_no, flight_hours, landings, engine_starts and
#: chute_streamed; the rest is accepted)
TAKEOFF_KEYS = (
    "sortie_id",
    "tail_no",
    "t_takeoff",
    "t_landing",
    "ab_lights",
    "engine_starts",
    "landings",
    "dust_index",
)
SORTIE_DONE_KEYS = (
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
)
#: ``ops.power_up`` (W2.5; catalogued, M02 emission planned for W2.1a): power-up at engine start, PBIT runs
POWER_UP_KEYS = ("tail_no", "sortie_id", "engine_starts", "cold_soak")  # M14 reads the first two
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "ops.power_up": POWER_UP_KEYS,
    "ops.takeoff": TAKEOFF_KEYS,
    "ops.sortie_done": SORTIE_DONE_KEYS,
    "fadec.fault": FADEC_KEYS,
    "fadec.caution": FADEC_KEYS,
    "mx.action": ("tail", "pos", "action", "serial", "sw_config_id"),
    "mx.monitoring": ("tail", "filter_codes_add", "filter_codes_remove"),
}
