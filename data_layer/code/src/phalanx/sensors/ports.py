"""Published ports of M12 (W1_interfaces.md §1 convention): ``PREFIX`` and ``ports(n_engines)``.

Inputs are W1 catalogue truth signals (bindings = catalogue keys) plus ``health.sensor_bias``. Outputs are the
sensor readings ``s_<group>`` and true measurands ``x_<group>`` per SI unit group; they are observation-layer
signals consumed by M13 (W1.6) only, so they are not in the truth-layer catalogue (``configs/interfaces/
w1_ports.yaml`` covers M02-M10). Their index maps are ``build_sensor_config(...).groups``.
"""

from __future__ import annotations

from phalanx.core.module import Port

PREFIX = "sens"


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of the default (platform ``tejas``) M12 configuration."""
    from phalanx.dictionary import load_dictionary

    from .config import build_sensor_config
    from .module import input_bindings, input_ports, output_ports

    cfg = build_sensor_config(load_dictionary(), n_engines=n_engines)
    return input_ports(cfg), output_ports(cfg), input_bindings(cfg)


# Cross-module event protocol (AD-44, configs/interfaces/w1_events.yaml);
# checked by tests/integration/test_event_protocol.py
MODULE_IDS = ("M12",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN: dict[str, tuple[str, ...]] = {
    "sensor_fault": ("channel", "mode", "value", "rate", "duty", "probe"),
}
