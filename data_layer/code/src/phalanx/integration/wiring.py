"""Connections derived from the published ``ports.py`` bindings (W2.1 deliverable 1; never hand-wired).

Every package publishes ``ports(n_engines) -> (inputs, outputs, bindings)`` with ``bindings`` = input port ->
catalogue signal (``<prefix>.<port>``) or controller lane (``lane.<channel_id>``) (``W1_interfaces.md`` §1).
:func:`connections` turns the bindings of a module set into core ``Connection`` objects:

- a catalogue signal resolves to the module whose ``PREFIX`` is the signal's prefix and whose output port is
  the signal's name; a lane resolves to the M13 lane module that publishes it
  (``LaneAcquisition.lane_bindings``);
- an input whose producer comes later in the Gauss-Seidel order (architecture §8) is a **one-frame
  delay**; each such back-edge must be one of :data:`BACK_EDGES` (documented reason), otherwise the build
  fails;
- a binding with no producer is an error unless it is a **tracked exception** of the conformance gate
  (``configs/interfaces/w1_ports.yaml`` ``exceptions``) and the caller supplies a labelled boundary source
  for it.

The result is checked against the bindings (every input bound exactly once, unit/dtype/shape by the core
``System``), so a change of any ``ports.py`` changes the wiring and nothing else has to be edited.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from phalanx.core.module import ContractError, Module
from phalanx.core.scheduler import Connection

ROOT = Path(__file__).resolve().parents[3]
PORTS_CATALOGUE = ROOT / "configs" / "interfaces" / "w1_ports.yaml"

#: documented one-frame delays (architecture §8 "loops are broken with documented one-frame delays"): key =
#: (producer prefix, consumer prefix); the note is stored in the Connection and hashed into the config.
BACK_EDGES: dict[tuple[str, str], str] = {
    ("af", "env"): (
        "airframe -> environment back-edge (architecture §8, W2.1 brief): M03 evaluates the atmosphere, "
        "shear and "
        "turbulence scales at the previous frame's altitude, height above ground and airspeed"
    ),
    ("af", "pilot"): (
        "airframe -> pilot back-edge (W2.1 brief; M04 ports.py): the pilot reacts to the previous frame's "
        "aircraft "
        "state (his own 0.1-0.2 s delay is modelled inside M04)"
    ),
    ("eng", "pilot"): (
        "engine -> pilot back-edge (W2.1 brief; M04 ports.py): start logic reads the previous frame's N2"
    ),
    ("fcs", "af"): (
        "FCS -> airframe back-edge (PD-W2.1a-1: the DFCC runs after its lanes): M06 integrates frame k with "
        "the "
        "surface positions at its start t_k (actuator bandwidth 9 Hz vs the 4.17 ms frame)"
    ),
    ("fcs", "util"): (
        "FCS -> utilities back-edge (PD-W2.1a-1): hydraulic flow demand of the actuators at the frame start"
    ),
    ("fcs", "sens"): (
        "FCS -> sensors back-edge (W2.1 brief: fcs.surf_pos -> M12 -> M13 position lanes): the surface "
        "LVDTs read "
        "the positions of the previous frame"
    ),
    ("af", "eng"): (
        "airframe -> engine back-edge: inlet Mach number of the previous frame (M07 inlet recovery and ram)"
    ),
    ("util", "eng"): (
        "utilities -> engine back-edge: bleed extraction, PTO power and fuel inlet temperature of the "
        "previous "
        "frame (M09 is downstream of M07 because N2 is its master variable)"
    ),
    ("util", "af"): (
        "utilities -> airframe back-edge: mass, CG and inertia of the previous frame (fuel burn changes "
        "them by "
        "< 1e-6 per frame)"
    ),
    ("acq", "fadec"): (
        "FADEC lane back-edge (M08 W1.3b coupling contract, fadec/coupling.py LANE_EDGE_NOTE): frames in "
        "[t_k, t_k+1) digitised at step k are processed by M08 at step k+1; commands apply from t_k+1 "
        "(architecture §8, A-W1.3b-1)"
    ),
    ("avio", "fadec"): (
        "air-data P0 back-edge (W2.2 f1b3bc9: M08 p0 <- avio.p0_from_hp on Tejas): M08 reads the avionics "
        "ADC's P0 altitude signal of the previous frame (the ADC computes on the DFCC clock after the truth "
        "loop; P0 changes by < 1e-4 per 4.17 ms frame)"
    ),
}


@dataclass(frozen=True)
class Source:
    """The producer of a signal: module id and output port."""

    module: str
    port: str


@dataclass(frozen=True)
class TrackedException:
    """A conformance-gate exception (``w1_ports.yaml`` ``exceptions``) that applies to this configuration."""

    rule: str
    signal: str
    consumers: tuple[str, ...]
    owner: str
    source: str

    def matches(self, rule: str, consumer_mid: str, signal: str) -> bool:
        return (
            rule == self.rule and consumer_mid in self.consumers and fnmatch.fnmatchcase(signal, self.signal)
        )


def tracked_exceptions(config: str = "e1") -> tuple[TrackedException, ...]:
    """Exceptions of the hardened conformance gate that apply to configuration ``config`` (e1 = Tejas, 1
    engine)."""
    from phalanx.dictionary.yamlio import load_yaml

    cat = load_yaml(PORTS_CATALOGUE)
    out = []
    for e in cat.get("exceptions") or []:
        if config in e["configs"]:
            out.append(
                TrackedException(e["rule"], e["signal"], tuple(e["consumers"]), str(e["owner"]), e["source"])
            )
    return tuple(out)


def producer_table(
    modules: Sequence[Module],
    prefix_of: Mapping[str, str],
    lane_ports: Mapping[str, Mapping[str, str]],
) -> dict[str, Source]:
    """Signal key -> producing (module, port).

    Args:
        modules: the System's modules.
        prefix_of: module id -> its package ``PREFIX`` (catalogue key prefix).
        lane_ports: lane module id -> {``lane.<channel_id>``: value port} (``LaneAcquisition.lane_bindings``).
    """
    out: dict[str, Source] = {}
    for m in modules:
        pre = prefix_of.get(m.id)
        if pre is None:
            continue
        for p in m.ports_out:
            key = f"{pre}.{p.name}"
            if key in out:
                raise ContractError(f"signal {key} produced twice ({out[key].module} and {m.id})")
            out[key] = Source(m.id, p.name)
        for lane, port in lane_ports.get(m.id, {}).items():
            if lane in out:
                raise ContractError(f"lane {lane} produced twice ({out[lane].module} and {m.id})")
            out[lane] = Source(m.id, port)
    return out


def connections(
    modules: Sequence[Module],
    bindings: Mapping[str, Mapping[str, str]],
    prefix_of: Mapping[str, str],
    lane_ports: Mapping[str, Mapping[str, str]],
    *,
    m_id: Mapping[str, str],
    exceptions: Sequence[TrackedException] = (),
    boundary: Mapping[str, Source] | None = None,
) -> tuple[list[Connection], list[tuple[str, str, TrackedException]]]:
    """All connections of a module set from its bindings (module docstring).

    Args:
        bindings: module id -> {input port: signal} (the package ``ports()`` bindings).
        m_id: module id -> architecture module number (``M05``...), for matching tracked exceptions.
        exceptions: tracked gate exceptions that apply; ``boundary`` gives the labelled source used for each
            excepted signal (signal -> Source).
    Returns:
        (connections, used exceptions as (consumer.port, signal, exception)).
    """
    boundary = dict(boundary or {})
    order = {m.id: k for k, m in enumerate(modules)}
    prods = producer_table(modules, prefix_of, lane_ports)
    out: list[Connection] = []
    used: list[tuple[str, str, TrackedException]] = []
    for m in modules:
        b = bindings.get(m.id, {})
        names = [p.name for p in m.ports_in]
        if sorted(b) != sorted(names):
            raise ContractError(
                f"{m.id}: bindings {sorted(set(b) ^ set(names))} do not match its input ports one to one"
            )
        for port in names:
            sig = b[port]
            src = prods.get(sig)
            if src is None:
                rule = "lane_producer" if sig.startswith("lane.") else "producer"
                exc = next((e for e in exceptions if e.matches(rule, m_id.get(m.id, ""), sig)), None)
                if exc is None:
                    raise ContractError(f"{m.id}.{port} <- {sig}: no producer (and not a tracked exception)")
                if sig not in boundary:
                    raise ContractError(
                        f"{m.id}.{port} <- {sig}: tracked exception ({exc.owner}) needs a labelled boundary "
                        "source"
                    )
                src = boundary[sig]
                used.append((f"{m.id}.{port}", sig, exc))
            if src.module not in order:
                raise ContractError(f"{m.id}.{port} <- {sig}: producer {src.module} is not in the System")
            back = order[src.module] >= order[m.id]
            note = ""
            if back:
                pre_p = prefix_of.get(src.module, src.module)
                pre_c = prefix_of.get(m.id, m.id)
                note = BACK_EDGES.get((pre_p, pre_c), "")
                if not note:
                    raise ContractError(
                        f"{src.module}.{src.port} -> {m.id}.{port} goes against the Gauss-Seidel order and "
                        f"is not a documented one-frame delay (add ({pre_p!r}, {pre_c!r}) to BACK_EDGES "
                        "with its reason)"
                    )
            out.append(Connection(f"{src.module}.{src.port}", f"{m.id}.{port}", back, note))
    return out, used


__all__ = [
    "BACK_EDGES",
    "PORTS_CATALOGUE",
    "Source",
    "TrackedException",
    "connections",
    "producer_table",
    "tracked_exceptions",
]
