"""Published ports of the M12 avionics extension (W1_interfaces.md §1 convention; AD-51, AD-42).

``PREFIX`` is ``avio``. Inputs bind catalogue truth signals (``af.*``, ``env.*``, ``util.bus_v``,
``util.probe_heat``, ``pilot.gear_cmd``) and the DFCC/ADC in-loop lanes (``lane.AD.*``, the M13 producer, on
the DFCC acquisition clock). Outputs are observation-layer signals, not truth-layer catalogue entries:
``RECORDED`` maps each ``rec_*`` port to the dictionary channel it supplies to the recorder (M13
``external=``); ``TRUTH`` maps the restricted truth companions; ``p0_from_hp`` is the FADEC's P0 altitude
signal (W2.2, M08 ``p0``). The ports do not depend on ``n_engines``.
"""

from __future__ import annotations

from phalanx.core.module import Port

from .channels import ALL, NUMERIC, rec_port, tru_port

PREFIX = "avio"
#: output port -> dictionary channel id of every recorded avionics channel (AD-42 convention)
RECORDED: dict[str, str] = {rec_port(c): c for c in ALL}
#: restricted truth companion port -> dictionary channel id (CIR truth_value only)
TRUTH: dict[str, str] = {tru_port(c): c for c in NUMERIC}


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    """(inputs, outputs, bindings) of the default (platform ``tejas``) avionics configuration."""
    if n_engines < 1:
        raise ValueError("n_engines must be >= 1")
    from phalanx.dictionary import load_dictionary
    from phalanx.utilities.layout import BUSES

    from .config import build_avionics_config
    from .module import input_bindings, input_ports, output_ports

    d = load_dictionary()
    cfg = build_avionics_config()
    units = {cid: d.eu_conversion(cid).si_units for cid in NUMERIC}
    return input_ports(cfg, len(BUSES)), output_ports(units), input_bindings()


# Cross-module event protocol (AD-44). The SMS events are PROPOSED catalogue additions (W2.2 report); no other
# module emits them yet, so they are listed here and not in configs/interfaces/w1_events.yaml.
MODULE_IDS = ("M12",)
EVENTS_OUT: dict[str, tuple[str, ...]] = {}
EVENTS_IN_PROPOSED: dict[str, tuple[str, ...]] = {
    "avio.sms_load": ("stations",),
    "avio.sms_release": ("station", "mode"),
}
EVENTS_IN: dict[str, tuple[str, ...]] = {}
