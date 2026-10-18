"""Published ports of M13's in-loop entry point (W1_interfaces.md §1 convention).

``ports(n_engines)`` returns the union of the two controller lane modules of the default (``tejas``)
configuration: FADEC lanes (FADEC clock domain, 60 Hz nominal) and DFCC lanes (80 Hz, incl. the ADC air-data
lanes). Inputs read M12 outputs (``sens.s_<group>``) and ``scenario.phase``; outputs are the lane sample
buffers. ``lane_bindings()`` maps every ``lane.<channel_id>`` a controller may bind to the value port that
carries it. The recording entry point has no ports: it consumes M12 frames and emits CIR
(``record.AcquisitionRecorder``).
"""

from __future__ import annotations

from phalanx.core.module import Param, ParamSet, Port

PREFIX = "acq"
CONTROLLERS = ("FADEC", "DFCC")


def lane_modules(n_engines: int = 1):
    """The default in-loop lane modules, one per controller: {controller: LaneAcquisition} (unbound)."""
    from phalanx.dictionary import load_dictionary
    from phalanx.sensors.config import build_sensor_config

    from .config import build_acquisition_config
    from .module import LaneAcquisition, lane_channels

    d = load_dictionary()
    sens = build_sensor_config(d, n_engines=n_engines)
    ps = ParamSet("acquisition.ports", {"v": Param(1.0, "1", "ASSUMPTION", "port listing only")})
    out = {}
    for ctl in CONTROLLERS:
        lanes = lane_channels(d, sens, ctl)
        acq = build_acquisition_config(d, lanes, sensor_channels=sens.channels)
        out[ctl] = LaneAcquisition(f"acq_{ctl.lower()}", ps, sens, acq, d)
    return out


def ports(n_engines: int = 1) -> tuple[tuple[Port, ...], tuple[Port, ...], dict[str, str]]:
    mods = lane_modules(n_engines)
    ins: dict[str, Port] = {}
    outs: list[Port] = []
    bindings: dict[str, str] = {}
    for m in mods.values():
        for p in m.ports_in:
            ins.setdefault(p.name, p)
        outs.extend(m.ports_out)
        bindings.update(m.bindings())
    return tuple(ins.values()), tuple(outs), bindings


def lane_bindings(n_engines: int = 1) -> dict[str, tuple[str, str]]:
    """``lane.<channel_id>`` -> (lane module id, value port)."""
    out = {}
    for m in lane_modules(n_engines).values():
        for lane, port in m.lane_bindings().items():
            out[lane] = (m.id, port)
    return out
