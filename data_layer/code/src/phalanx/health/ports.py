"""Published ports of M10 (W1_interfaces.md §1; catalogue ``configs/interfaces/w1_ports.yaml`` module M10).

M10 is event-only: it has no input ports (usage drivers, faults and maintenance arrive as events; see
``phalanx.health.module``). Its four held outputs are the catalogued ``health.*`` signals.
"""

from __future__ import annotations

from phalanx.core.module import Port

from .layout import ACTUATORS, ENGINE_DELTAS, sensor_bias_channels, utility_entries
from .usage import SUMMARY_KEYS

PREFIX = "health"


def ports(n_engines: int = 1, dictionary=None) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of M10 for ``n_engines``.

    ``health.sensor_bias`` has one entry per M12 sensor channel in M12's order (AD-42:
    ``SensorConfig.bias_index()``, via :func:`phalanx.health.layout.sensor_bias_channels`; at n_engines > 1
    M12 has one instance of each engine-indexed channel per engine); each entry is in
    that channel's SI unit, so the port is declared dimensionless with the per-index units documented in the
    index map (catalogue note).
    """
    if dictionary is None:
        from phalanx.dictionary import load_dictionary

        dictionary = load_dictionary()
    sensor_config = None
    if n_engines > 1:  # M12 measures every engine (one channel instance per engine, W2.4a-1 U3)
        from phalanx.sensors.config import build_sensor_config

        sensor_config = build_sensor_config(dictionary, n_engines=n_engines)
    nch = len(sensor_bias_channels(dictionary, sensor_config))
    outputs = (
        Port("engine", "1", "<f8", (n_engines, len(ENGINE_DELTAS))),
        Port("utility", "1", "<f8", (len(utility_entries(n_engines)),)),
        Port("sensor_bias", "1", "<f8", (nch,)),
        Port("actuator", "1", "<f8", (len(ACTUATORS),)),
    )
    return (), outputs, {}


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml); checked by
# tests/integration/test_event_protocol.py. M10 produces no catalogued kind (its events to M11 and M14 are
# W1.5-internal: faults.*, monitor.*).
MODULE_IDS = ("M10",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    # AD-48.2: the airborne sortie opens at take-off (the handler reads sortie_id and tail_no)
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
    "usage.sortie_summary": (*SUMMARY_KEYS, "usage", "chute_streamed"),
    "cfg.install": ("tail", "pos", "serial", "cls"),
    "cfg.remove": ("tail", "pos", "serial"),
    "mx.action": ("tail", "pos", "action", "job_no"),
    "mx.repaired": ("serial", "level"),
}
