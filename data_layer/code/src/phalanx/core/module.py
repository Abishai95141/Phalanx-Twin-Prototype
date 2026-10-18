"""The module contract of architecture §5.5: ports, provenance-tagged parameter sets, the Module protocol.

```text
Module
  id, version
  ports_in / ports_out : [Port(name, unit, dtype, shape, rate_group)]
  params               : ParamSet (from M01, hashed)
  init(params, keys) -> State
  step(state, inputs, t, dt) -> (State, Outputs)            # continuous modules
  on_event(state, event, t) -> (State, [Event])             # discrete modules
  get_state(state) -> bytes  /  set_state(bytes) -> State   # complete, versioned
```

Kernel additions (reported as proposed decisions, see ``core/README.md``):
- ``initial_outputs(state) -> Outputs``: the module's outputs at ``t_0`` (seeds one-frame-delayed edges and
  the zero-order hold before a slower rate group first runs).
- optional ``step_block(state, inputs, t, dt)``: the same transition over many ticks at once (inputs and
  outputs carry a leading tick axis, ``t`` is an int64 array). Must be bitwise identical to repeated
  ``step`` (A6); compiled backends implement it.
- ``rate``: the module's :class:`RateGroup` (``None`` = event-only module); ``state_schema``; ``streams``
  (declared RNG streams); ``identity`` (instance identity such as ``serial`` or ``sensor``);
  ``emits_events`` (modules whose ``step`` may return events), ``step_block_emits_events`` (their
  ``step_block`` returns ``(t_emit_ns, Event)`` pairs too, so block mode can run them; otherwise per-step).

Purity rules: ``step``/``on_event``/``initial_outputs`` are pure functions of their arguments plus
immutable configuration (``params``, bound ``keys``). No module attribute may change after binding.
"""

from __future__ import annotations

import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

import numpy as np

from .canonical import PERSON_PARAMS, canonical_json, digest
from .events import Event
from .rng import Keys, Stream, StreamDecl
from .state import State, StateError, StateSchema, canonical_dtype, decode_tree, encode_tree
from .time import RG_240, ClockDomain, RateGroup
from .units import UnitError, check_unit_for_dtype, parse_unit

Outputs = dict[str, np.ndarray]
Inputs = Mapping[str, np.ndarray]

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]*$")
_PORT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_TAG_RE = re.compile(
    r"^\[?\s*(?:(DIRECT)(?:-(unnamed|part))?|(MEASURED)|(ASSUMPTION)|(TRANSFER)\s*:\s*(.+?))\s*\]?$"
)


class ContractError(ValueError):
    """A module, port or parameter violates the §5.5 contract."""


class EventNotHandledError(ContractError):
    pass


# ---------------------------------------------------------------------------------------------- evidence


@dataclass(frozen=True)
class EvidenceTag:
    """RULES.md rule 3 evidence tag: DIRECT[-unnamed|-part], TRANSFER: <donor>, MEASURED, ASSUMPTION."""

    kind: str
    qualifier: str = ""

    @classmethod
    def parse(cls, text: str | EvidenceTag) -> EvidenceTag:
        if isinstance(text, EvidenceTag):
            return text
        m = _TAG_RE.match(text.strip()) if isinstance(text, str) else None
        if not m:
            raise ContractError(
                f"evidence tag {text!r} must be DIRECT[-unnamed|-part], TRANSFER: <donor>, "
                "MEASURED or ASSUMPTION"
            )
        if m.group(1):
            return cls("DIRECT", m.group(2) or "")
        if m.group(3):
            return cls("MEASURED")
        if m.group(4):
            return cls("ASSUMPTION")
        return cls("TRANSFER", m.group(6).strip())

    def __str__(self) -> str:
        if self.kind == "TRANSFER":
            return f"TRANSFER: {self.qualifier}"
        if self.kind == "DIRECT" and self.qualifier:
            return f"DIRECT-{self.qualifier}"
        return self.kind


ParamValue = bool | int | float | str | Fraction | np.ndarray


def _param_value_bytes(v: Any) -> bytes:
    if isinstance(v, bool):
        return b"b" + (b"\x01" if v else b"\x00")
    if isinstance(v, int):
        return b"i" + str(v).encode()
    if isinstance(v, float):
        return b"f" + struct.pack("<d", v)
    if isinstance(v, Fraction):
        return b"q" + f"{v.numerator}/{v.denominator}".encode()
    if isinstance(v, str):
        return b"s" + v.encode()
    if isinstance(v, np.ndarray):
        return b"a" + encode_tree({"v": v}, kind="param_value", name="", version=1)
    raise ContractError(f"unsupported parameter value type {type(v).__name__}")


@dataclass(frozen=True)
class Param:
    """One parameter value with units and provenance (invariant I4: unlabelled PROXY = defect)."""

    value: ParamValue
    unit: str
    tag: EvidenceTag | str
    source: str
    proxy: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        v = self.value
        if isinstance(v, np.generic):
            v = v.item()
        if isinstance(v, list | tuple):
            v = np.array(v)
        if isinstance(v, np.ndarray):
            canonical_dtype(v.dtype)
            v = np.array(v, copy=True)
            v.flags.writeable = False
        elif not isinstance(v, bool | int | float | str | Fraction):
            raise ContractError(f"unsupported parameter value type {type(v).__name__}")
        object.__setattr__(self, "value", v)
        object.__setattr__(self, "tag", EvidenceTag.parse(self.tag))
        if not isinstance(self.source, str) or not self.source.strip():
            raise ContractError("every parameter needs a non-empty source (RULES.md rule 3)")
        try:
            si = parse_unit(self.unit)
        except UnitError as e:
            raise ContractError(str(e)) from e
        is_int = isinstance(v, int) and not isinstance(v, bool)
        if si.is_ns and not (is_int or (isinstance(v, np.ndarray) and v.dtype.kind in "iu")):
            raise ContractError("'ns' parameters must be integers (AD-35)")

    def encode(self, name: str) -> bytes:
        head = canonical_json(
            {
                "name": name,
                "unit": self.unit,
                "tag": str(self.tag),
                "source": self.source,
                "proxy": self.proxy,
                "note": self.note,
            }
        )
        return len(head).to_bytes(4, "little") + head + _param_value_bytes(self.value)


class ParamSet(Mapping[str, Param]):
    """Frozen, content-hashed parameter set (architecture §5.5; values come from M01 at integration)."""

    def __init__(self, name: str, params: Mapping[str, Param]) -> None:
        for k, p in params.items():
            if not _PORT_RE.match(k):
                raise ContractError(f"parameter name {k!r} must match {_PORT_RE.pattern}")
            if not isinstance(p, Param):
                raise ContractError(f"{k}: expected Param, got {type(p).__name__}")
        self._name = name
        self._params = MappingProxyType({k: params[k] for k in sorted(params)})
        blob = b"".join(
            len(b).to_bytes(8, "little") + b for b in (p.encode(k) for k, p in self._params.items())
        )
        self._hash = digest(canonical_json({"name": name}) + blob, PERSON_PARAMS)

    @property
    def name(self) -> str:
        return self._name

    @property
    def hash(self) -> str:
        return self._hash

    def __getitem__(self, key: str) -> Param:
        return self._params[key]

    def __iter__(self):
        return iter(self._params)

    def __len__(self) -> int:
        return len(self._params)

    def value(self, key: str) -> Any:
        return self._params[key].value

    def replace(self, **values: ParamValue) -> ParamSet:
        """A new set with some values changed (tags and sources kept; the hash changes)."""
        unknown = sorted(set(values) - set(self._params))
        if unknown:
            raise ContractError(f"unknown parameters {unknown}")
        new = dict(self._params)
        for k, v in values.items():
            old = new[k]
            new[k] = Param(v, old.unit, old.tag, old.source, old.proxy, old.note)
        return ParamSet(self._name, new)

    def proxies(self) -> list[str]:
        return [k for k, p in self._params.items() if p.proxy]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ParamSet) and other.hash == self.hash

    def __hash__(self) -> int:
        return int(self._hash[:16], 16)

    def __repr__(self) -> str:
        return f"ParamSet({self._name!r}, {len(self)} params, hash={self._hash[:12]})"


# ---------------------------------------------------------------------------------------------- ports


@dataclass(frozen=True)
class Port:
    """A typed module port: name, SI unit (pint), dtype, fixed shape and rate (architecture §5.5).

    ``rate`` documents when the value is produced; ``None`` means the owning module's rate group. A
    :class:`ClockDomain` documents data sampled on an LRU oscillator (values still change only when the
    module steps).
    """

    name: str
    unit: str
    dtype: str = "<f8"
    shape: tuple[int, ...] = ()
    rate: RateGroup | ClockDomain | None = None

    def __post_init__(self) -> None:
        if not _PORT_RE.match(self.name):
            raise ContractError(f"port name {self.name!r} must match {_PORT_RE.pattern}")
        dt = canonical_dtype(self.dtype)
        object.__setattr__(self, "dtype", dt.str)
        shape = tuple(int(s) for s in self.shape)
        if any(s < 0 for s in shape):
            raise ContractError(f"port {self.name}: negative dimension")
        object.__setattr__(self, "shape", shape)
        try:
            check_unit_for_dtype(self.unit, dt)
        except UnitError as e:
            raise ContractError(f"port {self.name}: {e}") from e

    @property
    def si(self):
        return parse_unit(self.unit)

    def describe(self) -> dict[str, Any]:
        rate: Any = None
        if isinstance(self.rate, RateGroup):
            rate = [self.rate.divisor, self.rate.phase]
        elif isinstance(self.rate, ClockDomain):
            rate = self.rate.describe()
        return {
            "name": self.name,
            "unit": self.unit,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "rate": rate,
        }

    def conforms(self, value: Any) -> str | None:
        a = np.asarray(value)
        if a.dtype.str != np.dtype(self.dtype).str and a.dtype != np.dtype(self.dtype):
            return f"dtype {a.dtype.str} != {self.dtype}"
        if a.shape != self.shape:
            return f"shape {a.shape} != {self.shape}"
        return None


# ---------------------------------------------------------------------------------------------- protocol

StepResult = tuple[State, Outputs] | tuple[State, Outputs, list[Event]]


@runtime_checkable
class Module(Protocol):
    """Structural type every kernel module satisfies (see module docstring)."""

    id: str
    version: str
    params: ParamSet
    ports_in: tuple[Port, ...]
    ports_out: tuple[Port, ...]
    rate: RateGroup | None
    state_schema: StateSchema
    streams: tuple[StreamDecl, ...]
    identity: Mapping[str, str | int]
    emits_events: bool

    def bind(self, keys: Keys) -> None: ...
    def init(self, params: ParamSet, keys: Keys) -> State: ...
    def initial_outputs(self, state: State) -> Outputs: ...
    def step(self, state: State, inputs: Inputs, t: int, dt: float) -> StepResult: ...
    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]: ...
    def get_state(self, state: State) -> bytes: ...
    def set_state(self, data: bytes) -> State: ...


class ModuleBase:
    """Convenience base implementing the boilerplate of the contract (state codec, ports, stream binding).

    Subclasses set the class attributes and implement ``init``, ``initial_outputs`` and ``step`` (and
    ``on_event`` / ``step_block`` when relevant).
    """

    version: str = "0.0.0"
    ports_in: tuple[Port, ...] = ()
    ports_out: tuple[Port, ...] = ()
    rate: RateGroup | None = RG_240
    state_schema: StateSchema = StateSchema("empty", 0, ())
    streams: tuple[StreamDecl, ...] = ()
    emits_events: bool = False
    #: step_block returns (state, outputs, [(t_emit_ns, Event), ...]); the module then runs as a block
    step_block_emits_events: bool = False

    def __init__(self, id: str, params: ParamSet, *, identity: Mapping[str, str | int] | None = None) -> None:
        if not _ID_RE.match(id):
            raise ContractError(f"module id {id!r} must match {_ID_RE.pattern}")
        if not isinstance(params, ParamSet):
            raise ContractError("params must be a ParamSet")
        self.id = id
        self.params = params
        self.identity: Mapping[str, str | int] = MappingProxyType(dict(identity or {}))
        self._keys: Keys | None = None
        names_in = [p.name for p in self.ports_in]
        names_out = [p.name for p in self.ports_out]
        if len(set(names_in)) != len(names_in) or len(set(names_out)) != len(names_out):
            raise ContractError(f"{id}: duplicate port names")
        for p in self.ports_in + self.ports_out:
            if isinstance(p.rate, RateGroup) and p.rate != self.rate:
                raise ContractError(f"{id}.{p.name}: port rate {p.rate} differs from module rate {self.rate}")

    # ------------------------------------------------------------------ binding (once, by the kernel)
    def bind(self, keys: Keys) -> None:
        if self._keys is not None and self._keys is not keys:
            raise ContractError(f"{self.id}: keys already bound")
        self._keys = keys

    @property
    def keys(self) -> Keys:
        if self._keys is None:
            raise ContractError(f"{self.id}: keys not bound (build a System first)")
        return self._keys

    def stream(self, component: str, **extra: str | int) -> Stream:
        """The declared stream ``component`` for this module's identity (plus ``extra`` identity).

        Memoised per (component, extra): a cache of a pure function of (root, key path), not state.
        """
        memo_key = (component, tuple(sorted(extra.items())))
        memo = self.__dict__.setdefault("_stream_memo", {})
        hit = memo.get(memo_key)
        if hit is not None:
            return hit
        for d in self.streams:
            if d.component == component:
                s = self.keys.stream(d.subsystem, d.component, **extra)
                memo[memo_key] = s
                return s
        raise ContractError(f"{self.id}: stream {component!r} not declared in {type(self).__name__}.streams")

    # ------------------------------------------------------------------ contract
    def init(self, params: ParamSet, keys: Keys) -> State:
        raise NotImplementedError

    def initial_outputs(self, state: State) -> Outputs:
        if self.ports_out:
            raise NotImplementedError(f"{self.id}: modules with outputs must implement initial_outputs")
        return {}

    def step(self, state: State, inputs: Inputs, t: int, dt: float) -> StepResult:
        raise NotImplementedError

    def on_event(self, state: State, event: Event, t: int) -> tuple[State, list[Event]]:
        raise EventNotHandledError(f"{self.id} does not handle events (got {event.kind!r})")

    def get_state(self, state: State) -> bytes:
        self.state_schema.validate(state)
        s = self.state_schema
        return encode_tree(state, kind="module_state", name=s.name, version=s.version)

    def set_state(self, data: bytes) -> State:
        d = decode_tree(data, kind="module_state")
        s = self.state_schema
        if (d.name, d.version) != (s.name, s.version):
            raise StateError(
                f"{self.id}: state is {d.name} v{d.version}, module expects {s.name} v{s.version}"
            )
        s.validate(d.tree)
        return d.tree

    # ------------------------------------------------------------------ helpers
    def port_in(self, name: str) -> Port:
        for p in self.ports_in:
            if p.name == name:
                return p
        raise ContractError(f"{self.id}: no input port {name!r}")

    def port_out(self, name: str) -> Port:
        for p in self.ports_out:
            if p.name == name:
                return p
        raise ContractError(f"{self.id}: no output port {name!r}")

    def describe(self) -> dict[str, Any]:
        rate = None if self.rate is None else [self.rate.divisor, self.rate.phase]
        return {
            "id": self.id,
            "class": f"{type(self).__module__}.{type(self).__qualname__}",
            "version": self.version,
            "rate": rate,
            "ports_in": [p.describe() for p in self.ports_in],
            "ports_out": [p.describe() for p in self.ports_out],
            "state_schema": self.state_schema.describe(),
            "params": {"name": self.params.name, "hash": self.params.hash},
            "identity": dict(self.identity),
            "streams": [d.describe() for d in self.streams],
            "emits_events": bool(self.emits_events),
            "has_step_block": callable(getattr(self, "step_block", None)),
        }


def module_describe(m: Module) -> dict[str, Any]:
    if isinstance(m, ModuleBase):
        return m.describe()
    rate = None if m.rate is None else [m.rate.divisor, m.rate.phase]
    return {
        "id": m.id,
        "class": f"{type(m).__module__}.{type(m).__qualname__}",
        "version": m.version,
        "rate": rate,
        "ports_in": [p.describe() for p in m.ports_in],
        "ports_out": [p.describe() for p in m.ports_out],
        "state_schema": m.state_schema.describe(),
        "params": {"name": m.params.name, "hash": m.params.hash},
        "identity": dict(m.identity),
        "streams": [d.describe() for d in m.streams],
        "emits_events": bool(m.emits_events),
        "has_step_block": callable(getattr(m, "step_block", None)),
    }


def tag_params(
    values: Mapping[str, tuple[ParamValue, str]], *, tag: str, source: str, proxy: bool = False
) -> dict[str, Param]:
    """Helper: build several Params sharing one tag/source (e.g. a test fixture's parameters)."""
    return {k: Param(v, u, tag, source, proxy) for k, (v, u) in values.items()}


__all__ = [
    "ContractError",
    "EventNotHandledError",
    "EvidenceTag",
    "Inputs",
    "Module",
    "ModuleBase",
    "Outputs",
    "Param",
    "ParamSet",
    "Port",
    "StepResult",
    "module_describe",
    "tag_params",
]
