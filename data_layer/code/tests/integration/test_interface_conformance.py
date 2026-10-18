"""Interface cohesion gate: every published port binds to a producer that matches it exactly.

Catalogue: configs/interfaces/w1_ports.yaml (authoritative for the truth-layer signals of M02-M10; mirrors
docs/build_briefs/W1_interfaces.md §2). Convention (W1_interfaces.md §1): each package exposes
`phalanx.<pkg>.ports` with `PREFIX` and `ports(n_engines=1) -> (inputs, outputs, bindings)`. A producer's
signal key is f"{PREFIX}.{port.name}"; `bindings` maps an input port to the signal it reads; controller lanes
bind `lane.<channel_id>` (W1_interfaces.md §3) and resolve to M13's lane producers
(`phalanx.acquisition.ports.lane_bindings`).

E1-MF (MF2, U7) hardened the W1 gate, which checked only input rank and only M02-M10. It now covers all 16
`ports.py` modules (M02-M14 with the M12 avionics extension, M18, M21) in four configurations (`CONFIGS`):
the Tejas set at n_engines 1, 2 and 4, and the DASHlink proxy chain (n_engines 4). For each configuration it
checks:

1. **catalogue**: every catalogued output of M02-M10 is published with a pint-equivalent unit, the same dtype
   and a matching shape (fixed dims equal, `e` == n_engines, and every other symbol takes one value across
   all catalogued signals of the configuration); no private variants under a catalogued prefix; RECORDED
   channels against the dictionary (AD-42);
2. **bindings**: every input is bound; every binding resolves to a producer port of the configuration; the
   input's unit, dtype and **exact shape** equal the producer's; a lane binding names a dictionary channel
   with a matching SI unit and resolves to an M13 lane producer of that channel;
3. **clocks** (`clock_problems`; derived from AD-36 §8 and AD-42): a port that consumes a clock-domain sample
   buffer declares the producer's ClockDomain, and a port that declares a ClockDomain binds a producer on the
   same clock;
4. **proxy chain** (`PROXY`): a chain input bound to a signal whose producer is outside the chain is a
   labelled boundary signal (held by the harness), except the recorded flight condition the chain must
   replay itself (`REPLAY_REQUIRED`), which needs a producer in the chain. Replay producers that serve only
   part of a module's outputs (`Config.partial`: M06's replay of alt/tas/mach, W2.4a U4) are checked on what
   they publish; that module's other signals stay boundary signals.

Known problems owned by a later WP are listed in w1_ports.yaml `exceptions` (rule, signal pattern, consumer
modules, configurations, owning WP, source). The gate fails on any unlisted problem **and** on any listed
exception that no longer occurs (a stale entry must be removed, as with a strict xfail). Zero skips: a
missing `ports.py` is a failure, not a skip.

Negative controls (`test_gate_negative_control_*`) plant each kind of defect into a real configuration and
show the gate reports it.
"""

from __future__ import annotations

import fnmatch
import importlib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import Port
from phalanx.core.sampling import max_samples_per_step
from phalanx.core.time import ClockDomain
from phalanx.dictionary.yamlio import load_yaml

ROOT = Path(__file__).resolve().parents[2]
CAT = load_yaml(ROOT / "configs" / "interfaces" / "w1_ports.yaml")
#: catalogued truth-layer producers (w1_ports.yaml `modules`)
PKG = {
    "M02": "scenario",
    "M03": "environment",
    "M04": "pilot",
    "M05": "fcs",
    "M06": "airframe",
    "M07": "engine",
    "M08": "fadec",
    "M09": "utilities",
    "M10": "health",
}
#: every module that publishes a ports.py (E1-MF: all 15 are gated; W2.2: nested packages too, so the M12
#: avionics extension phalanx.sensors.avionics is gated as "M12A")
ALL_PKG = {
    **PKG,
    "M11": "faults",
    "M12": "sensors",
    "M12A": "sensors.avionics",
    "M13": "acquisition",
    "M14": "monitoring",
    "M18": "maintenance",
    "M21": "orders",
}
ALL_SIGNALS = {name: spec for m in CAT["modules"].values() for name, spec in m["out"].items()}
PREFIX = {name.split(".")[0] for name in ALL_SIGNALS}
RULES = (
    "unbound",
    "producer",
    "lane_producer",
    "lane_channel",
    "unit",
    "dtype",
    "shape",
    "clock",
    "catalogue",
    "duplicate",
)


# -------------------------------------------------------------------------------------------- configurations
@dataclass(frozen=True)
class Config:
    """A module set whose bindings must close. ``variants`` selects a module's alternative port set:
    ``replay`` = ``replay_ports(n_engines)`` (proxy drivers fed from a record), ``autothrottle`` = M08 with
    the proxy-mode autothrottle inputs (architecture §14.3)."""

    name: str
    n_engines: int
    modules: tuple[str, ...]
    variants: Mapping[str, str] = field(default_factory=dict)
    #: proxy only: signals the recorded flight supplies, which the chain must produce itself
    replay_required: frozenset[str] = frozenset()
    #: modules whose (replay) variant publishes only part of their catalogued outputs: catalogue-checked on
    #: what they publish; their unpublished signals are boundary signals of the chain (W2.4a U4)
    partial: frozenset[str] = frozenset()

    @property
    def chain(self) -> bool:
        return bool(self.replay_required)


#: DASHlink proxy chain (AD-43, architecture §14.3, W2.4a): recorded inputs drive M03/M04 replay producers
#: (PLA, altitude, Mach, TAT, A/T state; the flight phase segments the record), M08 governs with the A/T loop,
#: M07 is vectorised over 4 engines, M12/M13 produce the lanes. The M02 replay serves scenario.phase and the
#: M06 replay serves the recorded flight condition alt/tas/mach (W2.4a U4: phalanx.proxy.replay; a partial
#: publication of M06). Platform modules outside the chain (M05, M09, M10) and M06's other signals are a
#: labelled boundary, except the recorded flight condition below.
REPLAY_REQUIRED = frozenset(
    {
        "pilot.pla",
        "pilot.at_engage",
        "pilot.at_n1_cmd",
        "env.t_s",
        "env.p_s",
        "af.alt",
        "af.mach",
        "af.tas",
        "scenario.phase",
    }
)
PROXY = Config(
    "proxy",
    4,
    ("M02", "M03", "M04", "M06", "M07", "M08", "M12", "M13"),
    {"M02": "replay", "M03": "replay", "M04": "replay", "M06": "replay", "M08": "autothrottle"},
    REPLAY_REQUIRED,
    frozenset({"M06"}),
)
CONFIGS = {
    "e1": Config("e1", 1, tuple(ALL_PKG)),
    "e2": Config("e2", 2, tuple(ALL_PKG)),
    "e4": Config("e4", 4, tuple(ALL_PKG)),
    "proxy": PROXY,
}


@dataclass(frozen=True)
class Pub:
    """One module's published ports in one configuration."""

    mod: str
    prefix: str
    ins: tuple[Port, ...]
    outs: tuple[Port, ...]
    bindings: Mapping[str, str]
    recorded: Mapping[str, str]


@cache
def published(mod: str, n_engines: int, variant: str = "") -> Pub:
    m = importlib.import_module(f"phalanx.{ALL_PKG[mod]}.ports")  # a missing ports.py fails (no skip)
    if variant == "replay":
        ins, outs = m.replay_ports(n_engines)
        bindings: dict[str, str] = {}
    elif variant == "autothrottle":
        ins, outs, bindings = m.ports(n_engines, autothrottle=True)
    elif variant:
        raise ValueError(variant)
    else:
        ins, outs, bindings = m.ports(n_engines=n_engines)
    return Pub(mod, m.PREFIX, tuple(ins), tuple(outs), dict(bindings), dict(getattr(m, "RECORDED", {})))


def config_pubs(cfg: Config) -> dict[str, Pub]:
    return {m: published(m, cfg.n_engines, cfg.variants.get(m, "")) for m in cfg.modules}


@cache
def lane_producer_ports(n_engines: int) -> dict[str, str]:
    """``lane.<channel_id>`` -> M13 output port that carries it (``acquisition.ports.lane_bindings``)."""
    acq = importlib.import_module("phalanx.acquisition.ports")
    return {lane: port for lane, (_mid, port) in acq.lane_bindings(n_engines).items()}


# ---------------------------------------------------------------------------------------------- producers
@dataclass(frozen=True)
class Producer:
    mod: str
    port: Port
    #: a clock-domain sample buffer (core.sampling.sample_ports: value + `_t` / `_n` / `_first` companions)
    buffer: bool


@dataclass(frozen=True)
class Problem:
    rule: str
    consumer: str
    signal: str
    message: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.consumer} <- {self.signal}: {self.message}"


def producers(pubs: Mapping[str, Pub], lanes: Mapping[str, str]) -> tuple[dict[str, Producer], list[Problem]]:
    """Signal key -> producer port of the configuration (outputs by `<prefix>.<port>`; lanes from M13)."""
    out: dict[str, Producer] = {}
    problems: list[Problem] = []
    for mod, pub in pubs.items():
        names = {p.name for p in pub.outs}
        for p in pub.outs:
            key = f"{pub.prefix}.{p.name}"
            buf = {f"{p.name}_t", f"{p.name}_n", f"{p.name}_first"} <= names
            if key in out:
                problems.append(Problem("duplicate", mod, key, f"also produced by {out[key].mod}"))
            out[key] = Producer(mod, p, buf)
    if "M13" in pubs:
        acq = pubs["M13"]
        by_name = {p.name: p for p in acq.outs}
        for lane, port in lanes.items():
            out[lane] = out[f"{acq.prefix}.{port}"]
            if not out[lane].buffer:
                problems.append(Problem("clock", "M13", lane, f"lane port {port} is not a sample buffer"))
            if not isinstance(by_name[port].rate, ClockDomain):
                problems.append(Problem("clock", "M13", lane, f"lane port {port} declares no clock domain"))
    return out, problems


# ---------------------------------------------------------------------------------------------- unit helpers
def _ureg():
    from phalanx.core.units import ureg

    return ureg()


def _equiv(u1: str, u2: str) -> bool:
    reg = _ureg()
    a = reg.Quantity(1.0, "dimensionless" if u1 in ("1", "") else u1).to_base_units()
    b = reg.Quantity(1.0, "dimensionless" if u2 in ("1", "") else u2).to_base_units()
    return a.dimensionality == b.dimensionality and np.isclose(a.magnitude, b.magnitude)


def _dt(p) -> str:
    return np.dtype(p.dtype).name


def _clock_str(c) -> str:
    if isinstance(c, ClockDomain):
        return f"clock {c.name} ({c.f_nom_hz} Hz nominal, {c.offset_ppm} ppm, phase {c.phase_ns} ns)"
    return "rate group of the module" if c is None else repr(c)


# ---------------------------------------------------------------------------------------------- the rules
def clock_problems(port: Port, prod: Producer) -> list[str]:
    """Clock rule (AD-36 §8, AD-42; E1-MF U7).

    - AD-36 §8: truth modules run in rate groups (integer divisors of 240 Hz); a rate that does not divide
      240 Hz is a clock domain, and a module in it samples truth on its own oscillator. Port.rate None means
      the owning module's rate group (core.module.Port).
    - core.sampling: a clock-domain producer emits a fixed-capacity sample buffer (value, `_t`, `_n`,
      `_first`) whose slots are the domain's sample instants, capacity = max_samples_per_step(domain).
    - AD-42: the per-LRU acquisition clocks are defined by M13 and shared through acquisition_clock(); the
      controllers (M05, M08) and M15 must use them.

    Hence: (C1) a port bound to a sample buffer declares the producer's ClockDomain (equal name, nominal rate,
    offset and phase) and has its capacity; (C2) a port that declares a ClockDomain binds a producer on that
    same clock (a held truth value is not a sample buffer). Held clock-domain outputs (M08 commands, applied
    at the first truth frame after the compute instant) may be read by a rate-group consumer."""
    pc, cc = prod.port.rate, port.rate
    if prod.buffer:
        if not isinstance(pc, ClockDomain):
            return [f"producer sample buffer {prod.mod}.{prod.port.name} declares no clock domain"]
        if cc != pc:
            return [f"reads a sample buffer on {_clock_str(pc)} but declares {_clock_str(cc)}"]
        cap = max_samples_per_step(pc)
        if not port.shape or port.shape[0] != cap:
            return [f"buffer capacity {port.shape[:1]} != max_samples_per_step = {cap}"]
    elif isinstance(cc, ClockDomain) and cc != pc:
        return [f"declares {_clock_str(cc)} but the producer is on {_clock_str(pc)}"]
    return []


def lane_channel_problems(name: str, p: Port) -> list[str]:
    """`lane.<channel_id>`: a digitised controller lane from the in-loop path (W1_interfaces.md §3).
    The channel must exist in the dictionary, and the port carries the SI value of the digitised reading
    (core ports are SI). Its unit must be equivalent to the channel's `eu_conversion(...).si_units`."""
    from phalanx.dictionary import load_dictionary

    d = load_dictionary()
    cid = name.split(".", 1)[1]
    try:
        conv = d.eu_conversion(cid)
    except KeyError:
        return [f"channel {cid!r} is not in the dictionary"]
    except Exception as x:
        return [f"channel has no EU->SI conversion ({x})"]
    if not _equiv(p.unit, conv.si_units):
        return [f"port unit {p.unit!r} not equivalent to the channel's SI unit {conv.si_units!r}"]
    return []


def lane_problems(name: str, p: Port) -> list[str]:  # W1 name, kept for its unit test
    return [f"{name}: {m}" for m in lane_channel_problems(name, p)]


def binding_problems(
    cfg: Config, pubs: Mapping[str, Pub], prods: Mapping[str, Producer], owners: Mapping[str, str]
) -> tuple[list[Problem], list[str]]:
    """(problems, boundary signals) of every input binding of the configuration."""
    problems: list[Problem] = []
    boundary: list[str] = []
    for mod, pub in pubs.items():
        for p in pub.ins:
            sig = pub.bindings.get(p.name)
            if sig is None:
                problems.append(Problem("unbound", mod, f"{pub.prefix}:{p.name}", "input has no binding"))
                continue
            if sig.startswith("lane."):
                problems += [Problem("lane_channel", mod, sig, m) for m in lane_channel_problems(sig, p)]
            prod = prods.get(sig)
            if prod is None:
                owner = owners.get(sig)
                if (
                    cfg.chain
                    and owner is not None
                    and (owner not in cfg.modules or owner in cfg.partial)
                    and sig not in cfg.replay_required
                ):
                    boundary.append(f"{mod} <- {sig} (held at the proxy boundary; produced by {owner})")
                    continue
                rule = "lane_producer" if sig.startswith("lane.") else "producer"
                where = "no M13 lane producer" if rule == "lane_producer" else "no producer"
                problems.append(Problem(rule, mod, sig, f"{where} in configuration {cfg.name}"))
                continue
            q = prod.port
            if not _equiv(p.unit, q.unit):
                problems.append(Problem("unit", mod, sig, f"unit {p.unit!r} != producer {q.unit!r}"))
            if _dt(p) != _dt(q):
                problems.append(Problem("dtype", mod, sig, f"dtype {_dt(p)} != producer {_dt(q)}"))
            if tuple(p.shape) != tuple(q.shape):
                problems.append(
                    Problem(
                        "shape", mod, sig, f"shape {tuple(p.shape)} != producer {prod.mod} {tuple(q.shape)}"
                    )
                )
            problems += [Problem("clock", mod, sig, m) for m in clock_problems(p, prod)]
    return problems, boundary


def _shape_ok(cat_shape: list, shape: tuple, n_engines: int, symbols: dict, name: str) -> list[str]:
    if len(cat_shape) != len(shape):
        return [f"{name}: rank {len(shape)} != catalogue {cat_shape}"]
    out = []
    for c, s in zip(cat_shape, shape, strict=True):
        if isinstance(c, int):
            if c != s:
                out.append(f"{name}: shape {shape} != catalogue {cat_shape}")
        elif c == "e":
            if s != n_engines:
                out.append(f"{name}: shape {shape} != catalogue {cat_shape} (n_engines={n_engines})")
        else:
            seen = symbols.setdefault(c, (s, name))
            if seen[0] != s:
                out.append(f"{name}: symbol {c!r} = {s}, but {seen[1]} has {c!r} = {seen[0]}")
    return out


def output_problems(mod: str, outs: dict, n_engines: int, symbols: dict | None = None) -> list[str]:
    symbols = {} if symbols is None else symbols
    problems = []
    for name, spec in CAT["modules"][mod]["out"].items():
        p = outs.get(name)
        if p is None:
            problems.append(f"missing output {name}")
            continue
        if not _equiv(p.unit, spec["unit"]):
            problems.append(f"{name}: unit {p.unit!r} not equivalent to catalogue {spec['unit']!r}")
        if _dt(p) != spec["dtype"]:
            problems.append(f"{name}: dtype {_dt(p)} != {spec['dtype']}")
        problems += _shape_ok(spec["shape"], tuple(p.shape), n_engines, symbols, name)
    for name in outs:
        if name.split(".")[0] in PREFIX and name not in ALL_SIGNALS:
            problems.append(f"uncatalogued output {name} (interface change request needed)")
    return problems


def catalogue_problems(cfg: Config, pubs: Mapping[str, Pub]) -> list[Problem]:
    """Catalogued outputs of the configuration's M02-M10 producers (replay producers publish the same
    outputs). One symbol table per configuration: `h`, `k`, `buses`, ... take one value across all modules."""
    symbols: dict = {}
    out: list[Problem] = []
    for mod, pub in pubs.items():
        if mod not in PKG:
            continue
        outs = {f"{pub.prefix}.{p.name}": p for p in pub.outs if p.name not in pub.recorded}
        cat = {k: v for k, v in outs.items() if k in ALL_SIGNALS or k.split(".")[0] in PREFIX}
        msgs = output_problems(mod, cat, cfg.n_engines, symbols)
        if mod in cfg.partial:  # a partial replay publishes a subset: what it publishes must still match
            msgs = [m for m in msgs if not m.startswith("missing output")]
        out += [Problem("catalogue", mod, "-", m) for m in msgs]
    return out


# ---------------------------------------------------------------------------------------------- exceptions
EXCEPTION_KEYS = {"rule", "signal", "consumers", "configs", "owner", "source", "note"}


def exception_matches(exc: Mapping, cfg: str, pb: Problem) -> bool:
    return (
        cfg in exc["configs"]
        and pb.rule == exc["rule"]
        and pb.consumer in exc["consumers"]
        and fnmatch.fnmatchcase(pb.signal, exc["signal"])
    )


def gate(cfg: Config, *, pubs: Mapping[str, Pub] | None = None, exceptions=None) -> dict[str, list]:
    """Run the gate on one configuration: {'unexpected': [Problem], 'tracked': [(Problem, owner)],
    'stale': [exception], 'boundary': [str]}."""
    pubs = config_pubs(cfg) if pubs is None else pubs
    exceptions = (CAT.get("exceptions") or []) if exceptions is None else exceptions
    lanes = lane_producer_ports(cfg.n_engines) if "M13" in pubs else {}
    prods, problems = producers(pubs, lanes)
    # owners of every signal in the full (Tejas) module set at this engine count: tells boundary from missing
    full = {m: published(m, cfg.n_engines) for m in ALL_PKG}
    owners = {f"{p.prefix}.{q.name}": m for m, p in full.items() for q in p.outs}
    bp, boundary = binding_problems(cfg, pubs, prods, owners)
    problems += bp + catalogue_problems(cfg, pubs)
    unexpected, tracked, used = [], [], set()
    for pb in problems:
        hit = [i for i, e in enumerate(exceptions) if exception_matches(e, cfg.name, pb)]
        if hit:
            tracked.append((pb, exceptions[hit[0]]["owner"]))
            used.update(hit)
        else:
            unexpected.append(pb)
    stale = [e for i, e in enumerate(exceptions) if cfg.name in e["configs"] and i not in used]
    return {"unexpected": unexpected, "tracked": tracked, "stale": stale, "boundary": boundary}


# ---------------------------------------------------------------------------------------------- the gate
@pytest.mark.integration
def test_every_ports_module_is_gated():
    """All 16 published ports.py modules are in the gate, nested packages included (W2.2: a new one must be
    added here)."""
    base = ROOT / "src" / "phalanx"
    found = {".".join(p.parent.relative_to(base).parts) for p in base.rglob("ports.py")}
    assert found == set(ALL_PKG.values()), sorted(found ^ set(ALL_PKG.values()))
    assert len(ALL_PKG) == 16


@pytest.mark.integration
@pytest.mark.parametrize("cfg", sorted(CONFIGS))
def test_bindings_close_with_exact_shapes_and_clocks(cfg):
    """MF2: every binding of the configuration resolves to a producer with an equal unit, dtype, exact shape
    and clock, except the tracked exceptions; no tracked exception is stale."""
    r = gate(CONFIGS[cfg])
    msg = "\n".join(["UNEXPECTED:", *map(str, r["unexpected"]), "STALE EXCEPTIONS:", *map(str, r["stale"])])
    assert not r["unexpected"] and not r["stale"], msg
    if CONFIGS[cfg].chain:
        assert r["boundary"], "the proxy chain has no labelled boundary signals (configuration changed?)"


@pytest.mark.integration
def test_fcs_frame_clock_is_its_lane_producers_clock():
    """The tracked M05 clock exception covers only the port declaration (rate None): the DFCC frame clock
    M05 actually computes on (`build_fcs_config`, A-W1.6-21) is the clock of every M13 lane it binds."""
    from phalanx.fcs.module import Fcs

    clock = Fcs.from_registry("fcs").cfg.clock
    pubs = config_pubs(CONFIGS["e1"])
    prods, _ = producers(pubs, lane_producer_ports(1))
    lanes = [s for s in pubs["M05"].bindings.values() if s.startswith("lane.")]
    assert lanes
    bad = {s: _clock_str(prods[s].port.rate) for s in lanes if prods[s].port.rate != clock}
    assert not bad, (_clock_str(clock), bad)


@pytest.mark.integration
@pytest.mark.parametrize("n_engines", [1, 2, 4])
@pytest.mark.parametrize("mod", sorted(PKG))
def test_outputs_match_catalogue(mod, n_engines):
    pub = published(mod, n_engines)
    outs = {f"{pub.prefix}.{p.name}": p for p in pub.outs if p.name not in pub.recorded}
    problems = output_problems(mod, outs, n_engines)
    assert not problems, "\n".join(problems)


def recorded_problems(recorded: dict, outs_by_name: dict) -> list[str]:
    """`RECORDED = {output_port_name: dictionary channel_id}`: LRU-computed values (voted `.V` words, status,
    computed averages) a module supplies to the recorder (M13 `external=`; AD-42). Each must be a published
    output, a dictionary channel whose signal is `computed`, and carry its SI unit (`eu_conversion`)."""
    from phalanx.dictionary import load_dictionary

    d = load_dictionary()
    problems = []
    for pname, cid in recorded.items():
        p = outs_by_name.get(pname)
        if p is None:
            problems.append(f"RECORDED port {pname!r} is not a published output")
            continue
        try:
            ch = d.channel(cid)
        except KeyError:
            problems.append(f"RECORDED {pname!r}: channel {cid!r} not in the dictionary")
            continue
        if ch.get("signal") != "computed":
            problems.append(f"RECORDED {pname!r}: channel {cid} is not an LRU-computed signal")
        try:
            conv = d.eu_conversion(cid)
            if not _equiv(p.unit, conv.si_units):
                problems.append(f"RECORDED {pname!r}: unit {p.unit!r} != channel SI unit {conv.si_units!r}")
        except Exception:
            if not _equiv(p.unit, "1"):
                problems.append(
                    f"RECORDED {pname!r}: non-convertible channel {cid} needs a dimensionless port"
                )
    return problems


@pytest.mark.integration
@pytest.mark.parametrize("mod", sorted(ALL_PKG))
def test_recorded_computed_channels(mod):
    pub = published(mod, 1)
    problems = recorded_problems(dict(pub.recorded), {p.name: p for p in pub.outs})
    assert not problems, "\n".join(problems)


# ---------------------------------------------------------------------------------------------- catalogue
@pytest.mark.unit
def test_catalogue_is_well_formed():
    assert CAT["format"] == "phalanx.ports/1"
    reg = _ureg()
    seen = set()
    for mod, m in CAT["modules"].items():
        assert mod in PKG, mod
        for name, spec in m["out"].items():
            assert name not in seen, f"duplicate signal {name}"
            seen.add(name)
            assert set(spec) <= {"unit", "dtype", "shape", "rate", "proxy_only", "note"}, name
            assert spec["dtype"] in ("float64", "int64"), name
            assert spec["rate"] in ("truth", "dfcc", "fadec", "held", "event"), name
            reg.Unit("dimensionless" if spec["unit"] == "1" else spec["unit"])


@pytest.mark.unit
def test_exception_list_is_well_formed():
    """Each tracked exception names a gate rule, consumer modules, configurations and an owning WP. The list
    is empty since W2.2 phase B closed its last entry (the ENG.AB_LIT lane producer); it stays a list."""
    exc = CAT.get("exceptions")
    assert isinstance(exc, list)
    for e in exc:
        assert set(e) <= EXCEPTION_KEYS and {"rule", "signal", "consumers", "configs", "owner"} <= set(e), e
        assert e["rule"] in RULES, e
        assert set(e["consumers"]) <= set(ALL_PKG), e
        assert set(e["configs"]) <= set(CONFIGS), e
        assert str(e["owner"]).startswith("W"), e  # a work package, e.g. W2.1 or W2.4a-1
        assert e.get("source"), e


# ----------------------------------------------------------------------------------------- negative controls
def _planted(cfg: Config, mod: str, ins: tuple[Port, ...], bindings: dict[str, str]) -> dict[str, Pub]:
    """The configuration's real publications plus one planted consumer module ``mod`` (TEST FIXTURE)."""
    pubs = dict(config_pubs(cfg))
    pubs[mod] = Pub(mod, "planted", ins, (), bindings, {})
    return pubs


def _gate_planted(cfg: Config, pubs: Mapping[str, Pub]) -> list[Problem]:
    # the planted module is not a real module id: accept it as a consumer name in the problem list
    return gate(cfg, pubs=pubs)["unexpected"]


@pytest.mark.unit
def test_gate_negative_control_planted_shape_mismatch():
    """A planted (3,) consumer of M09's (4,) util.bus_v (the U1 defect) and a (4,) consumer of a (3,) signal
    are each reported as exact-shape mismatches (the W1 gate checked rank only and passed both)."""
    cfg = CONFIGS["e1"]
    bus = published("M09", 1)
    assert {p.name: p.shape for p in bus.outs}["bus_v"] == (4,)
    pubs = _planted(
        cfg,
        "MX",
        (Port("bus_v", "V", "<f8", (3,)), Port("wind", "m/s", "<f8", (4,))),
        {"bus_v": "util.bus_v", "wind": "env.wind_ned"},
    )
    got = [str(p) for p in _gate_planted(cfg, pubs) if p.consumer == "MX"]
    assert any("[shape] MX <- util.bus_v: shape (3,) != producer M09 (4,)" in g for g in got), got
    assert any("[shape] MX <- env.wind_ned: shape (4,) != producer M03 (3,)" in g for g in got), got
    assert len(got) == 2, got


@pytest.mark.unit
def test_gate_negative_control_planted_lane_without_producer():
    """A planted controller lane bound to a real dictionary channel that M13 does not produce (ENG.T5, the
    FADEC-computed average, not a lane) is reported; so is a lane naming no dictionary channel."""
    cfg = CONFIGS["e1"]
    assert "lane.ENG.T5" not in lane_producer_ports(1)
    pubs = _planted(
        cfg,
        "MX",
        (Port("t5", "K", "<f8", (1,)), Port("nope", "K", "<f8", (1,))),
        {"t5": "lane.ENG.T5", "nope": "lane.ENG.NOPE"},
    )
    got = [str(p) for p in _gate_planted(cfg, pubs) if p.consumer == "MX"]
    assert "[lane_producer] MX <- lane.ENG.T5: no M13 lane producer in configuration e1" in got, got
    assert any(g.startswith("[lane_channel] MX <- lane.ENG.NOPE: channel 'ENG.NOPE'") for g in got), got
    assert "[lane_producer] MX <- lane.ENG.NOPE: no M13 lane producer in configuration e1" in got, got


@pytest.mark.unit
def test_gate_negative_control_clock_unit_dtype_unbound_and_missing():
    """The other rules each fail on a planted defect: a sample buffer read without its clock, a clock
    declared on a held truth signal, unit, dtype, an unbound input and a signal nobody produces."""
    cfg = CONFIGS["e1"]
    fadec = {p.name: p for p in published("M08", 1).ins}
    lane = fadec["n2_a"]  # bound to lane.ENG.N2.A, declared on the FADEC clock
    assert isinstance(lane.rate, ClockDomain)
    pubs = _planted(
        cfg,
        "MX",
        (
            replace(lane, name="no_clock", rate=None),
            Port("n2", "rad/s", "<f8", (1,), lane.rate),  # a clock on a held truth signal (eng.n2)
            Port("ps3", "K", "<f8", (1,)),
            Port("pla", "rad", "<i8", (1,)),
            Port("loose", "1", "<f8", ()),
            Port("ghost", "1", "<f8", ()),
        ),
        {
            "no_clock": "lane.ENG.N2.A",
            "n2": "eng.n2",
            "ps3": "eng.ps3",
            "pla": "pilot.pla",
            "ghost": "eng.ghost",
        },
    )
    got = "\n".join(str(p) for p in _gate_planted(cfg, pubs) if p.consumer == "MX")
    for needle in (
        "[clock] MX <- lane.ENG.N2.A: reads a sample buffer on clock FADEC@60Hz",
        "[clock] MX <- eng.n2: declares clock FADEC@60Hz",
        "[unit] MX <- eng.ps3: unit 'K' != producer 'Pa'",
        "[dtype] MX <- pilot.pla: dtype int64 != producer float64",
        "[unbound] MX <- planted:loose: input has no binding",
        "[producer] MX <- eng.ghost: no producer in configuration e1",
    ):
        assert needle in got, got


@pytest.mark.unit
def test_gate_negative_control_stale_exception_and_proxy_replay():
    """A tracked exception that matches nothing is reported stale; in the proxy chain a recorded-flight
    signal with no chain producer is a problem, while an out-of-chain platform signal is a boundary."""
    cfg = CONFIGS["e1"]
    stale = {
        "rule": "shape",
        "signal": "util.bus_v",
        "consumers": ["M12"],
        "configs": ["e1"],
        "owner": "W9",
        "source": "planted",
    }
    r = gate(cfg, exceptions=[*CAT["exceptions"], stale])
    assert r["stale"] == [stale]
    # the chain without its M02/M06 replay producers (the pre-U4 chain): the recorded flight condition has
    # no producer, while out-of-chain platform signals are boundary signals
    pre_u4 = replace(
        PROXY,
        modules=tuple(m for m in PROXY.modules if m not in ("M02", "M06")),
        variants={k: v for k, v in PROXY.variants.items() if k not in ("M02", "M06")},
        partial=frozenset(),
    )
    r = gate(pre_u4, exceptions=[e for e in CAT["exceptions"] if "proxy" not in e["configs"]])
    got = {str(p) for p in r["unexpected"]}
    assert "[producer] M07 <- af.mach: no producer in configuration proxy" in got, got
    assert "[producer] M12 <- af.tas: no producer in configuration proxy" in got, got
    assert "[producer] M13 <- scenario.phase: no producer in configuration proxy" in got, got
    assert any("util.bleed_extract" in b for b in r["boundary"]), r["boundary"]
    # with them (U4) the recorded flight condition is produced in the chain, M06's other signals stay boundary
    r = gate(PROXY)
    assert not r["unexpected"], r["unexpected"]
    assert any(b.startswith("M12 <- af.") and "produced by M06" in b for b in r["boundary"]), r["boundary"]
    prods, _ = producers(config_pubs(PROXY), lane_producer_ports(4))
    assert {prods[s].mod for s in ("af.mach", "af.tas", "af.alt", "scenario.phase")} == {"M06", "M02"}


@pytest.mark.unit
def test_gate_negative_control_partial_replay_is_checked_on_what_it_publishes():
    """A partial replay producer is not excused from the catalogue on the signals it does publish: a wrong
    unit on the M06 replay's af.mach is reported; a full (non-partial) M06 with missing outputs is too."""
    pubs = dict(config_pubs(PROXY))
    m06 = pubs["M06"]
    bad = tuple(replace(q, unit="m/s") if q.name == "mach" else q for q in m06.outs)
    pubs["M06"] = replace(m06, outs=bad)
    got = "\n".join(str(p) for p in gate(PROXY, pubs=pubs)["unexpected"])
    assert "af.mach: unit 'm/s' not equivalent to catalogue '1'" in got, got
    full = replace(PROXY, partial=frozenset())
    got = "\n".join(str(p) for p in gate(full)["unexpected"])
    assert "missing output af.quat" in got, got


@pytest.mark.unit
def test_catalogue_check_catches_mismatches():
    """Negative control: a fake M07 port set with deliberate defects is rejected on every axis."""
    good = {
        n: Port(
            n.split(".", 1)[1],
            sp["unit"],
            "<f8" if sp["dtype"] == "float64" else "<i8",
            tuple(1 if d == "e" else (d if isinstance(d, int) else 3) for d in sp["shape"]),
        )
        for n, sp in CAT["modules"]["M07"]["out"].items()
    }
    assert output_problems("M07", good, 1) == []
    bad = dict(good)
    bad["eng.n2"] = Port("n2", "K", "<f8", (1,))  # wrong quantity (core already rejects non-SI like rpm)
    bad["eng.t5"] = Port("t5", "K", "<f8", (2,))  # wrong engine dimension
    del bad["eng.ps3"]  # missing
    bad["eng.private_x"] = Port("private_x", "1", "<f8", (1,))  # uncatalogued variant
    msgs = "\n".join(output_problems("M07", bad, 1))
    for needle in (
        "eng.n2: unit",
        "eng.t5: shape",
        "missing output eng.ps3",
        "uncatalogued output eng.private_x",
    ):
        assert needle in msgs, msgs
    sym = {}
    assert output_problems("M07", good, 1, sym) == [] and sym["bands"][0] == 3
    two = {"util.hyd_p": Port("hyd_p", "Pa", "<f8", (3,))}
    m = output_problems("M09", two, 1, {"h": (2, "env.w_hyd")})
    assert "util.hyd_p: symbol 'h' = 3, but env.w_hyd has 'h' = 2" in m, m


@pytest.mark.unit
def test_lane_binding_rules():
    assert lane_problems("lane.ENG.N2.A", Port("n2_lane_a", "rad/s", "<f8", (1,))) == []
    assert lane_problems("lane.ENG.N2.A", Port("n2_lane_a", "K", "<f8", (1,)))  # wrong quantity
    assert lane_problems("lane.ENG.NOPE", Port("x", "rad/s", "<f8", (1,)))  # unknown channel


@pytest.mark.unit
def test_recorded_mechanism_catches_mismatches():
    """Negative control for RECORDED: missing port, non-computed channel, wrong unit, unknown channel."""
    outs = {
        "n2_v": Port("n2_v", "rad/s", "<f8", (1,)),
        "t5_avg": Port("t5_avg", "K", "<f8", (1,)),
        "bad_unit": Port("bad_unit", "Pa", "<f8", (1,)),
    }
    assert recorded_problems({"n2_v": "ENG.N2.V", "t5_avg": "ENG.T5"}, outs) == []
    msgs = "\n".join(
        recorded_problems(
            {"missing": "ENG.N2.V", "n2_v": "ENG.N2.A", "bad_unit": "ENG.N1.V", "t5_avg": "ENG.NOPE"}, outs
        )
    )
    for needle in ("not a published output", "not an LRU-computed", "bad_unit", "not in the dictionary"):
        assert needle in msgs, msgs
