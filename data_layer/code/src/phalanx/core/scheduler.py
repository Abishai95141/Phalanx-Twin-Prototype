"""The 240 Hz truth kernel: fixed-step Gauss-Seidel scheduling, rate groups, events, block execution.

Normative sources: architecture §8 (240 Hz truth step; fixed Gauss-Seidel order; loops broken with
documented one-frame delays), §5.5 (module contract), §11 (orders as events at decision epochs), §13
(compiled hot loops; two tiers), AD-11, AD-35; report §7 ("Separate the truth integrator from LRU
sampling"); research note modelling_methodology.md §Scheduling [TRANSFER: JSBSim/HARV/MAPSS practice].

Semantics (the reference interpreter, ``mode="step"``), for truth step ``k`` at ``t_k`` ns:

1. **Dispatch**: every queued event with ``t_ns <= t_k`` is delivered in ``(t_ns, priority, seq)`` order
   via ``on_event(state, event, t_k)``. Events it returns with ``t_ns == t_k`` are delivered in the same
   phase; ``t_ns < t_k`` is a causality error. Event-only modules (``rate is None``) refresh their outputs
   from ``initial_outputs(state)`` after each event.
2. **Step**: modules run in the fixed list order (Gauss-Seidel). A module runs at ``k`` if its rate group
   runs at ``k`` (``k % divisor == phase``) with ``dt = divisor/240`` s. An input wired from an *earlier*
   module sees that module's output from this step. A ``delayed`` connection sees the producer's output as
   it was at the start of step ``k`` (a one-frame delay). Connections from a later module (or a module to
   itself) **must** be declared delayed and documented (``note``): that is how loops are broken.
3. Outputs are held (zero-order hold) until the module next runs. Events returned by ``step`` must have
   ``t_ns >= t_k`` and are dispatched at the first later step whose time is ``>= t_ns``. Dispatch is
   quantised to the truth frame [ASSUMPTION A-W0.2-3]; event timestamps themselves stay exact.

Block execution (``mode="block"``) runs whole blocks of steps segment by segment and must be — and is
tested to be — bitwise identical to the reference interpreter (A6). Segments are the modules in order,
except that every delayed back-edge forces the modules it spans into one segment (a loop cannot be
split). A segment runs a fused ``step_block`` if one is registered, a module's own ``step_block`` if it
is a single module that has one (and does not emit events), and otherwise the per-step interpreter
restricted to the segment. Blocks end at the next pending event's dispatch step; if a block emits an
event that would be dispatched inside it, the block is rolled back and re-run up to that step. A system
with no continuous module (usage mode) jumps from one dispatch step to the next (``event_jump``), which is
identical to stepping because nothing runs in between.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from .canonical import PERSON_CONFIG, PERSON_TRACE, canonical_json, digest, length_prefixed
from .events import Event, EventQueue, event_log_digest
from .module import ContractError, Module, Outputs, module_describe
from .rng import RNG_MAPPING_VERSION, KeyPath, RngService
from .state import State, StateError, encode_tree, freeze, trees_equal
from .time import TRUTH_DT_S, latest_truth_step, truth_step_time_ns, truth_step_times_ns
from .units import UnitMismatchError, strip_quantity, units_compatible

MAX_DISPATCH_PER_STEP = 100_000


class SchedulerError(RuntimeError):
    pass


class CausalityError(SchedulerError):
    """An event was scheduled in the past."""


class PurityError(SchedulerError):
    """A module returned different results for identical arguments (hidden state or nondeterminism)."""


@dataclass(frozen=True)
class Connection:
    """Wire ``src`` ("module.port", an output) to ``dst`` ("module.port", an input).

    ``delayed=True`` makes it a one-frame delay (the value at the start of the step); it is mandatory
    for back-edges and self-edges, and ``note`` must document why (architecture §8).
    """

    src: str
    dst: str
    delayed: bool = False
    note: str = ""

    def describe(self) -> dict[str, Any]:
        """Semantic configuration (hashed into ``config_hash``): modules, params, wiring, identity, RNG."""
        return {"src": self.src, "dst": self.dst, "delayed": self.delayed, "note": self.note}


@runtime_checkable
class FusedGroup(Protocol):
    """A compiled implementation of a contiguous run of modules (typically a closed loop).

    ``step_block(states, ext_inputs, held0, k, dt_truth) -> (states, outputs)``:
    - ``states``: member id -> State at the block start;
    - ``ext_inputs``: "member.port" -> (n, *shape) value seen at each block step for inputs wired from
      outside the group (delays already applied);
    - ``held0``: "member.port" -> the members' held outputs at the block start;
    - ``k``: int64 (n,) global step indices; ``dt_truth`` = 1/240 s;
    returns new member states and "member.port" -> (n, *shape) held output after each step. Must equal the
    per-step reference bitwise.
    """

    id: str
    members: tuple[str, ...]

    def step_block(
        self,
        states: Mapping[str, State],
        ext_inputs: Mapping[str, np.ndarray],
        held0: Mapping[str, np.ndarray],
        k: np.ndarray,
        dt_truth: float,
    ) -> tuple[dict[str, State], dict[str, np.ndarray]]: ...


@dataclass
class World:
    """Complete simulation state at a step boundary (before step ``k``'s dispatch phase)."""

    k: int
    states: dict[str, State]
    held: dict[str, np.ndarray]
    queue: EventQueue
    order_log: tuple[Event, ...] = ()

    @property
    def t_ns(self) -> int:
        return truth_step_time_ns(self.k)

    def copy(self) -> World:
        return World(self.k, dict(self.states), dict(self.held), self.queue.copy(), self.order_log)


@dataclass
class Trace:
    """Per-step record of selected ports (value held after each step) and of dispatched events."""

    k0: int
    ports: dict[str, np.ndarray] = field(default_factory=dict)
    dispatched: list[tuple[int, Event]] = field(default_factory=list)

    def digest(self) -> str:
        tree = {name.replace(".", "/"): arr for name, arr in self.ports.items()}
        body = encode_tree(tree, kind="trace", name="trace", version=1)
        ev = length_prefixed([k.to_bytes(8, "little") + e.encode() for k, e in self.dispatched])
        return digest(self.k0.to_bytes(8, "little") + body + ev, PERSON_TRACE)

    def concat(self, other: Trace) -> Trace:
        if sorted(self.ports) != sorted(other.ports):
            raise ValueError("traces record different ports")
        n = next(iter(self.ports.values())).shape[0] if self.ports else 0
        if self.ports and other.k0 != self.k0 + n:
            raise ValueError("traces are not contiguous")
        return Trace(
            self.k0,
            {p: np.concatenate([self.ports[p], other.ports[p]]) for p in self.ports},
            self.dispatched + other.dispatched,
        )


def _split(ref: str) -> tuple[str, str]:
    if ref.count(".") < 1:
        raise ContractError(f"port reference {ref!r} must be 'module.port'")
    mod, port = ref.rsplit(".", 1)
    return mod, port


def _check_finite(where: str, value: Any) -> None:
    """Validation mode: no NaN or inf at a port boundary (the contract has no NaN; sentinels instead)."""
    a = np.asarray(value)
    if a.dtype.kind in "fc" and not np.all(np.isfinite(a)):
        raise ContractError(f"{where}: non-finite value at a port boundary (NaN/inf are not allowed)")


def _first_step_at_or_after(t_ns: int) -> int:
    return 0 if t_ns <= 0 else latest_truth_step(t_ns - 1) + 1


def _dispatch_step(k_emit: int, ev: Event) -> int:
    """Step at which an event emitted during step ``k_emit`` is dispatched (never earlier than k_emit + 1)."""
    return max(k_emit + 1, _first_step_at_or_after(ev.t_ns))


@dataclass(frozen=True)
class _Edge:
    src_mod: str
    src_port: str
    dst_mod: str
    dst_port: str
    delayed: bool

    @property
    def src(self) -> str:
        return f"{self.src_mod}.{self.src_port}"

    @property
    def dst(self) -> str:
        return f"{self.dst_mod}.{self.dst_port}"


@dataclass(frozen=True)
class _Segment:
    members: tuple[str, ...]
    fused: FusedGroup | None
    use_module_block: bool


class System:
    """A wired set of modules plus its RNG service: builds, runs, and (with ``snapshot.py``) snapshots."""

    def __init__(
        self,
        modules: Sequence[Module],
        connections: Sequence[Connection],
        *,
        rng: RngService,
        identity: KeyPath,
        fused: Sequence[FusedGroup] = (),
        dict_hash: str = "",
        validate: bool = False,
        purity_check: bool = False,
        block_len: int = 1024,
        event_jump: bool = True,
    ) -> None:
        if any(k in ("subsystem", "component") for k in identity.kinds):
            raise ContractError("system identity must not contain stream names")
        self.rng = rng
        self.identity = identity
        self.dict_hash = dict_hash
        self.validate = validate
        self.purity_check = purity_check and validate
        if block_len < 1:
            raise ValueError("block_len must be >= 1")
        self.block_len = block_len
        self.event_jump = event_jump

        ids = [m.id for m in modules]
        if len(set(ids)) != len(ids):
            raise ContractError(f"duplicate module ids in {ids}")
        self.order: tuple[str, ...] = tuple(ids)
        self.modules: dict[str, Module] = {m.id: m for m in modules}
        #: no continuous module at all: block-mode runs jump from event to event (usage mode)
        self.event_only = all(m.rate is None for m in modules)
        self._idx = {mid: i for i, mid in enumerate(self.order)}

        # streams and keys
        for m in modules:
            for d in m.streams:
                rng.registry.declare(d)
        for m in modules:
            m.bind(rng.scope(identity.extend(**dict(m.identity))))

        self._edges = self._wire(connections)
        self._in_edges: dict[str, list[_Edge]] = {mid: [] for mid in self.order}
        for e in self._edges:
            self._in_edges[e.dst_mod].append(e)
        self._segments = self._partition(fused)
        self.config_hash = digest(canonical_json(self.describe()), PERSON_CONFIG)

    # ------------------------------------------------------------------------------------------ build
    def _wire(self, connections: Sequence[Connection]) -> tuple[_Edge, ...]:
        edges: list[_Edge] = []
        fed: dict[str, str] = {}
        for c in connections:
            sm, sp = _split(c.src)
            dm, dp = _split(c.dst)
            for mid in (sm, dm):
                if mid not in self.modules:
                    raise ContractError(f"connection {c.src} -> {c.dst}: unknown module {mid!r}")
            src_port = next((p for p in self.modules[sm].ports_out if p.name == sp), None)
            dst_port = next((p for p in self.modules[dm].ports_in if p.name == dp), None)
            if src_port is None:
                raise ContractError(f"{c.src} is not an output port")
            if dst_port is None:
                raise ContractError(f"{c.dst} is not an input port")
            if c.dst in fed:
                raise ContractError(f"input {c.dst} is wired twice ({fed[c.dst]} and {c.src})")
            fed[c.dst] = c.src
            if np.dtype(src_port.dtype) != np.dtype(dst_port.dtype):
                raise ContractError(f"{c.src} -> {c.dst}: dtype {src_port.dtype} != {dst_port.dtype}")
            if src_port.shape != dst_port.shape:
                raise ContractError(f"{c.src} -> {c.dst}: shape {src_port.shape} != {dst_port.shape}")
            if not units_compatible(src_port.unit, dst_port.unit):
                raise UnitMismatchError(
                    f"{c.src} [{src_port.unit}] -> {c.dst} [{dst_port.unit}]: unit mismatch"
                )
            back = self._idx[sm] >= self._idx[dm]
            if back and not c.delayed:
                raise ContractError(
                    f"{c.src} -> {c.dst} goes against the Gauss-Seidel order: "
                    "declare it delayed (one-frame delay)"
                )
            if c.delayed and not c.note.strip():
                raise ContractError(f"{c.src} -> {c.dst}: a one-frame delay must be documented (note=...)")
            edges.append(_Edge(sm, sp, dm, dp, c.delayed))
        for mid in self.order:
            for p in self.modules[mid].ports_in:
                if f"{mid}.{p.name}" not in fed:
                    raise ContractError(f"input {mid}.{p.name} is not wired")
        return tuple(sorted(edges, key=lambda e: (self._idx[e.dst_mod], e.dst_port)))

    def _partition(self, fused: Sequence[FusedGroup]) -> tuple[_Segment, ...]:
        n = len(self.order)
        forced = []
        for e in self._edges:
            i, j = self._idx[e.dst_mod], self._idx[e.src_mod]
            if e.delayed and j >= i:
                forced.append((i, j))
        # merge overlapping ranges
        forced.sort()
        merged: list[list[int]] = []
        for a, b in forced:
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        fused_by_range: dict[tuple[int, int], FusedGroup] = {}
        for g in fused:
            idx = [self._idx.get(m, -1) for m in g.members]
            if -1 in idx or idx != list(range(idx[0], idx[0] + len(idx))):
                raise ContractError(
                    f"fused group {g.id}: members {g.members} must be contiguous in the order"
                )
            if any(self.modules[m].emits_events for m in g.members) and not getattr(g, "emits_events", False):
                raise ContractError(
                    f"fused group {g.id}: members emit events, so the group must declare emits_events = True "
                    "and return them from step_block"
                )
            fused_by_range[(idx[0], idx[-1])] = g
        # combine forced ranges with fused ranges (a fused range must contain whole forced ranges)
        ranges = [tuple(r) for r in merged]
        for (a, b), g in fused_by_range.items():
            for fa, fb in list(ranges):
                overlap = not (fb < a or fa > b)
                if overlap and not (a <= fa and fb <= b):
                    raise ContractError(
                        f"fused group {g.id} splits the loop spanning {self.order[fa : fb + 1]}"
                    )
            ranges = [r for r in ranges if not (a <= r[0] and r[1] <= b)] + [(a, b)]
        ranges.sort()
        for (_a1, b1), (a2, _b2) in itertools.pairwise(ranges):
            if a2 <= b1:
                raise ContractError("fused groups overlap")
        segs: list[_Segment] = []
        i = 0
        while i < n:
            r = next((r for r in ranges if r[0] == i), None)
            if r is None:
                mid = self.order[i]
                m = self.modules[mid]
                use_block = (
                    callable(getattr(m, "step_block", None))
                    and m.rate is not None
                    and (not m.emits_events or bool(getattr(m, "step_block_emits_events", False)))
                )
                segs.append(_Segment((mid,), None, use_block))
                i += 1
            else:
                segs.append(_Segment(self.order[r[0] : r[1] + 1], fused_by_range.get(r), False))
                i = r[1] + 1
        return tuple(segs)

    def describe(self) -> dict[str, Any]:
        """Semantic configuration (hashed into ``config_hash``): modules, params, wiring, identity, RNG."""
        return {
            "identity": self.identity.canonical(),
            "order": list(self.order),
            "modules": [module_describe(self.modules[m]) for m in self.order],
            "connections": sorted(
                ({"src": e.src, "dst": e.dst, "delayed": e.delayed} for e in self._edges),
                key=lambda d: (d["dst"], d["src"]),
            ),
            "rng_mapping_version": RNG_MAPPING_VERSION,  # stream declarations are in each module entry
        }

    def execution(self) -> dict[str, Any]:
        """Execution strategy (not part of the config hash: it must not change results)."""
        return {
            "block_len": self.block_len,
            "validate": self.validate,
            "purity_check": self.purity_check,
            "event_only": self.event_only,
            "event_jump": self.event_jump and self.event_only,
            "segments": [
                {
                    "members": list(s.members),
                    "fused": None if s.fused is None else s.fused.id,
                    "module_step_block": s.use_module_block,
                }
                for s in self._segments
            ],
        }

    @property
    def segments(self) -> tuple[tuple[str, ...], ...]:
        return tuple(s.members for s in self._segments)

    def output_ports(self) -> list[str]:
        return [f"{mid}.{p.name}" for mid in self.order for p in self.modules[mid].ports_out]

    # ------------------------------------------------------------------------------------------ start
    def start(self) -> World:
        states: dict[str, State] = {}
        held: dict[str, np.ndarray] = {}
        for mid in self.order:
            m = self.modules[mid]
            st = m.init(m.params, m.keys)
            if self.validate:
                m.state_schema.validate(st)
            states[mid] = st
            held.update(self._held_from(m, m.initial_outputs(st), "initial_outputs"))
        return World(0, states, held, EventQueue(), ())

    def _held_from(self, m: Module, outputs: Outputs, where: str) -> dict[str, np.ndarray]:
        names = {p.name for p in m.ports_out}
        if set(outputs) != names:
            raise ContractError(f"{m.id}.{where} returned {sorted(outputs)}, ports are {sorted(names)}")
        out = {}
        for p in m.ports_out:
            v = outputs[p.name]
            if self.validate:
                v = strip_quantity(v, p.unit, f"{m.id}.{p.name}")
                prob = p.conforms(v)
                if prob is not None:
                    raise ContractError(f"{m.id}.{p.name} ({where}): {prob}")
                _check_finite(f"{m.id}.{p.name} ({where})", v)
            out[f"{m.id}.{p.name}"] = np.asarray(v)
        return out

    def inject(self, world: World, events: Sequence[Event]) -> World:
        """Externally scheduled events (e.g. orders from M21). Logged in ``world.order_log``."""
        w = world.copy()
        logged = []
        for ev in events:
            if ev.target not in self.modules:
                raise ContractError(f"event target {ev.target!r} is not a module")
            if ev.t_ns < w.t_ns:
                raise CausalityError(f"cannot inject an event at {ev.t_ns} ns before now ({w.t_ns} ns)")
            logged.append(w.queue.push(ev))
        w.order_log = (*world.order_log, *logged)
        return w

    def order_log_hash(self, world: World) -> str:
        return event_log_digest(world.order_log)

    # ------------------------------------------------------------------------------------------ run
    def run(
        self, world: World, n_steps: int, *, mode: str = "block", record: Sequence[str] = ()
    ) -> tuple[World, Trace]:
        """Advance ``n_steps`` truth steps. Returns a new world (the input is not modified) and a trace."""
        if n_steps < 0:
            raise ValueError("n_steps must be >= 0")
        for r in record:
            if r not in world.held:
                raise ContractError(f"cannot record {r!r}: not an output port")
        w = world.copy()
        trace = Trace(w.k)
        rows: dict[str, list[np.ndarray]] = {r: [] for r in record}
        end = w.k + n_steps
        if mode == "step":
            while w.k < end:
                self._dispatch(w, trace)
                emitted: list[tuple[int, int, int, Event]] = []
                self._step_all(w, emitted)
                for *_, ev in sorted(emitted, key=lambda x: x[:3]):
                    w.queue.push(ev)
                for r in record:
                    rows[r].append(w.held[r])
                w.k += 1
            for r in record:
                trace.ports[r] = (
                    np.stack(rows[r]) if rows[r] else np.empty((0, *world.held[r].shape), world.held[r].dtype)
                )
        elif mode == "block" and self.event_only and self.event_jump:
            # Usage mode: nothing runs between dispatches, so jump to the next dispatch step. Held values
            # only change at dispatch, so the trace rows are the held values repeated (== stepping).
            while w.k < end:
                self._dispatch(w, trace)
                nxt = w.queue.next_time()
                k_stop = end if nxt is None else min(end, max(w.k + 1, _first_step_at_or_after(nxt)))
                for r in record:
                    rows[r].append(np.broadcast_to(w.held[r], (k_stop - w.k, *w.held[r].shape)))
                w.k = k_stop
            for r in record:
                trace.ports[r] = (
                    np.concatenate(rows[r])
                    if rows[r]
                    else np.empty((0, *world.held[r].shape), world.held[r].dtype)
                )
        elif mode == "block":
            predicted: list[int] = []  # dispatch steps seen in a discarded pass (a speed hint only)
            while w.k < end:
                self._dispatch(w, trace)
                k_stop = min(end, w.k + self.block_len)
                nxt = w.queue.next_time()
                if nxt is not None:
                    k_stop = min(k_stop, max(w.k + 1, _first_step_at_or_after(nxt)))
                predicted = [kp for kp in predicted if kp > w.k]
                if predicted:
                    k_stop = min(k_stop, predicted[0])
                saved = w.copy()
                seqs, emitted = self._run_block(w, k_stop)
                cut = self._block_cut(emitted, k_stop)
                if cut is not None:
                    # an emitted event is due inside the block: per-step semantics would dispatch it there,
                    # so discard the pass and re-run only up to that step (bitwise identical to stepping)
                    predicted = sorted({_dispatch_step(ke, ev) for ke, _, _, ev in emitted} - {cut})
                    w = saved
                    k_stop = cut
                    seqs, emitted = self._run_block(w, k_stop)
                for *_, ev in sorted(emitted, key=lambda x: x[:3]):
                    w.queue.push(ev)
                for r in record:
                    rows[r].append(seqs[r])
                w.k = k_stop
            for r in record:
                trace.ports[r] = (
                    np.concatenate(rows[r])
                    if rows[r]
                    else np.empty((0, *world.held[r].shape), world.held[r].dtype)
                )
        else:
            raise ValueError("mode must be 'block' or 'step'")
        return w, trace

    # ------------------------------------------------------------------------------------------ events
    def _block_cut(self, emitted: list, k_stop: int) -> int | None:
        """First dispatch step of an emitted event that falls inside the block ``[.., k_stop)``, or None.

        Any such event forces a cut there, whatever its target: the target's state (and every module that
        depends on it) must see the dispatch at exactly that step, as in per-step execution.
        """
        kd = min((_dispatch_step(ke, ev) for ke, _, _, ev in emitted), default=None)
        return kd if kd is not None and kd < k_stop else None

    def _dispatch(self, w: World, trace: Trace) -> None:
        t = w.t_ns
        count = 0
        while True:
            ev = w.queue.pop_due(t)
            if ev is None:
                return
            count += 1
            if count > MAX_DISPATCH_PER_STEP:
                raise SchedulerError(f"more than {MAX_DISPATCH_PER_STEP} events at step {w.k}: livelock?")
            m = self.modules.get(ev.target)
            if m is None:
                raise ContractError(f"event target {ev.target!r} is not a module")
            st = w.states[m.id]
            if self.validate:
                st = freeze(st)
            new_state, new_events = m.on_event(st, ev, t)
            if self.purity_check:
                s2, e2 = m.on_event(st, ev, t)
                if not trees_equal(new_state, s2) or [e.encode() for e in new_events] != [
                    e.encode() for e in e2
                ]:
                    raise PurityError(f"{m.id}.on_event gave different results for identical arguments")
            if self.validate:
                m.state_schema.validate(new_state)
            w.states[m.id] = new_state
            if m.rate is None:
                w.held.update(self._held_from(m, m.initial_outputs(new_state), "initial_outputs"))
            trace.dispatched.append((w.k, ev))
            for ne in new_events:
                self._check_event(ne, t, m.id)
                w.queue.push(ne)

    def _check_event(self, ev: Event, t: int, src: str) -> None:
        if not isinstance(ev, Event):
            raise ContractError(f"{src} returned a non-Event {type(ev).__name__}")
        if ev.t_ns < t:
            raise CausalityError(f"{src} scheduled {ev.kind!r} at {ev.t_ns} ns, before now ({t} ns)")
        if ev.target not in self.modules:
            raise ContractError(f"{src} targeted unknown module {ev.target!r}")

    # ------------------------------------------------------------------------------------------ stepping
    def _call_step(
        self, m: Module, state: State, inputs: dict[str, np.ndarray], k: int, emitted: list
    ) -> tuple[State, dict[str, np.ndarray]]:
        """One module step (the only place ``step`` is called). Returns (new state, held outputs)."""
        t = truth_step_time_ns(k)
        dt = m.rate.dt_s  # type: ignore[union-attr]
        if self.validate:
            state = freeze(state)
            inputs = freeze(inputs)
        res = m.step(state, inputs, t, dt)
        if self.purity_check:
            res2 = m.step(state, inputs, t, dt)
            if not (trees_equal(res[0], res2[0]) and trees_equal(res[1], res2[1])):
                raise PurityError(f"{m.id}.step gave different results for identical arguments at k={k}")
        if not isinstance(res, tuple) or len(res) not in (2, 3):
            raise ContractError(f"{m.id}.step must return (state, outputs[, events])")
        new_state, outputs = res[0], res[1]
        if self.validate:
            try:
                m.state_schema.validate(new_state)
            except StateError as e:
                raise ContractError(f"{m.id}.step at k={k}: {e}") from e
        if len(res) == 3:
            if not m.emits_events:
                raise ContractError(f"{m.id} returned events from step but emits_events is False")
            for pos, ev in enumerate(res[2]):
                self._check_event(ev, t, m.id)
                emitted.append((k, self._idx[m.id], pos, ev))
        return new_state, self._held_from(m, outputs, f"step at k={k}")

    def _gather(self, mid: str, now: Mapping[str, np.ndarray], start: Mapping[str, np.ndarray]) -> dict:
        return {e.dst_port: (start[e.src] if e.delayed else now[e.src]) for e in self._in_edges[mid]}

    def _step_all(self, w: World, emitted: list) -> None:
        held_start = dict(w.held)
        for mid in self.order:
            m = self.modules[mid]
            if m.rate is None or not m.rate.runs_at(w.k):
                continue
            inputs = self._gather(mid, w.held, held_start)
            w.states[mid], outs = self._call_step(m, w.states[mid], inputs, w.k, emitted)
            w.held.update(outs)

    # ------------------------------------------------------------------------------------------ blocks
    def _run_block(self, w: World, k1: int) -> tuple[dict[str, np.ndarray], list]:
        """Run steps [w.k, k1) segment by segment; update ``w`` states/held in place; return sequences."""
        k0 = w.k
        n = k1 - k0
        ks = np.arange(k0, k1, dtype=np.int64)
        seqs: dict[str, np.ndarray] = {}
        held0 = dict(w.held)
        emitted: list[tuple[int, int, int, Event]] = []

        def seq_of(src: str, delayed: bool) -> np.ndarray:
            s = seqs[src]
            if not delayed:
                return s
            return np.concatenate([held0[src][None], s[:-1]]) if n > 0 else s

        for seg in self._segments:
            members = seg.members
            mset = set(members)
            if seg.fused is not None:
                ext = {
                    e.dst: seq_of(e.src, e.delayed)
                    for mid in members
                    for e in self._in_edges[mid]
                    if e.src_mod not in mset
                }
                states_in = {
                    mid: (freeze(w.states[mid]) if self.validate else w.states[mid]) for mid in members
                }
                if self.validate:
                    ext = freeze(ext)
                h0 = {
                    f"{mid}.{p.name}": held0[f"{mid}.{p.name}"]
                    for mid in members
                    for p in self.modules[mid].ports_out
                }
                res = seg.fused.step_block(states_in, ext, h0, ks, TRUTH_DT_S)
                new_states, outs = res[0], res[1]
                if self.purity_check:
                    r2 = seg.fused.step_block(states_in, ext, h0, ks, TRUTH_DT_S)
                    same = all(trees_equal(new_states[m], r2[0][m]) for m in members) and trees_equal(
                        outs, r2[1]
                    )
                    if not same or _events_bytes(res) != _events_bytes(r2):
                        raise PurityError(f"fused {seg.fused.id}.step_block is not a pure function")
                if len(res) == 3:
                    if not getattr(seg.fused, "emits_events", False):
                        raise ContractError(f"fused {seg.fused.id} returned events but emits_events is False")
                    for pos, (t_emit, mid_e, ev) in enumerate(res[2]):
                        if mid_e not in mset or not self.modules[mid_e].emits_events:
                            raise ContractError(f"fused {seg.fused.id}: {mid_e!r} cannot emit events")
                        self._collect_block_event(ev, int(t_emit), ks, mid_e, pos, emitted)
                for mid in members:
                    m = self.modules[mid]
                    if self.validate:
                        m.state_schema.validate(new_states[mid])
                    w.states[mid] = new_states[mid]
                    for p in m.ports_out:
                        name = f"{mid}.{p.name}"
                        arr = np.asarray(outs[name])
                        if self.validate:
                            if arr.shape != (n, *p.shape) or arr.dtype != np.dtype(p.dtype):
                                raise ContractError(
                                    f"fused {seg.fused.id}: {name} has {arr.dtype}{arr.shape}"
                                )
                            _check_finite(f"fused {seg.fused.id}: {name}", arr)
                        seqs[name] = arr
                        if n:
                            w.held[name] = arr[-1].copy()
                continue
            if len(members) == 1:
                mid = members[0]
                m = self.modules[mid]
                if m.rate is None:
                    for p in m.ports_out:
                        name = f"{mid}.{p.name}"
                        seqs[name] = np.broadcast_to(held0[name], (n, *p.shape))
                    continue
                if seg.use_module_block:
                    self._module_block(m, w, ks, seq_of, seqs, held0, emitted)
                    continue
            self._segment_per_step(members, w, ks, seq_of, seqs, held0, emitted)
        return seqs, emitted

    def _collect_block_event(
        self, ev: Event, t_emit: int, ks: np.ndarray, mid: str, pos: int, emitted
    ) -> None:
        """Validate an event returned by a block call and record it with its emission step."""
        k_emit = latest_truth_step(t_emit)
        if not (ks.size and int(ks[0]) <= k_emit <= int(ks[-1])) or truth_step_time_ns(k_emit) != t_emit:
            raise ContractError(f"{mid}: event emission time {t_emit} ns is not a step time inside the block")
        m = self.modules[mid]
        if m.rate is None or not m.rate.runs_at(k_emit):
            raise ContractError(f"{mid}: event emitted at step {k_emit}, where the module does not run")
        self._check_event(ev, t_emit, mid)
        emitted.append((k_emit, self._idx[mid], pos, ev))

    def _module_block(self, m: Module, w: World, ks: np.ndarray, seq_of, seqs, held0, emitted) -> None:
        n = ks.size
        ticks = m.rate.ticks(int(ks[0]), int(ks[-1]) + 1) if n else np.empty(0, np.int64)  # type: ignore[union-attr]
        j = ticks - (int(ks[0]) if n else 0)
        inputs = {e.dst_port: seq_of(e.src, e.delayed)[j] for e in self._in_edges[m.id]}
        if ticks.size:
            st = freeze(w.states[m.id]) if self.validate else w.states[m.id]
            if self.validate:
                inputs = freeze(inputs)
            tt = truth_step_times_ns(ticks)
            res = m.step_block(st, inputs, tt, m.rate.dt_s)  # type: ignore[attr-defined,union-attr]
            new_state, outs = res[0], res[1]
            if self.purity_check:
                r2 = m.step_block(st, inputs, tt, m.rate.dt_s)  # type: ignore[attr-defined,union-attr]
                if not (trees_equal(new_state, r2[0]) and trees_equal(outs, r2[1])) or _events_bytes(
                    res
                ) != _events_bytes(r2):
                    raise PurityError(f"{m.id}.step_block gave different results for identical arguments")
            if len(res) == 3:
                if not m.emits_events:
                    raise ContractError(f"{m.id} returned events from step_block but emits_events is False")
                for pos, (t_emit, ev) in enumerate(res[2]):
                    self._collect_block_event(ev, int(t_emit), ks, m.id, pos, emitted)
            if self.validate:
                m.state_schema.validate(new_state)
            w.states[m.id] = new_state
        else:
            outs = {p.name: np.empty((0, *p.shape), np.dtype(p.dtype)) for p in m.ports_out}
        # zero-order hold expansion: step i holds the output of the last tick <= i
        last = np.searchsorted(j, np.arange(n), side="right") - 1
        for p in m.ports_out:
            name = f"{m.id}.{p.name}"
            o = np.asarray(outs[p.name])
            if self.validate:
                if o.shape != (ticks.size, *p.shape) or o.dtype != np.dtype(p.dtype):
                    raise ContractError(f"{m.id}.step_block: {p.name} has {o.dtype}{o.shape}")
                _check_finite(f"{m.id}.step_block: {p.name}", o)
            full = np.concatenate([held0[name][None], o])
            seqs[name] = full[last + 1]
            if n:
                w.held[name] = seqs[name][-1].copy()

    def _segment_per_step(self, members, w: World, ks: np.ndarray, seq_of, seqs, held0, emitted) -> None:
        n = ks.size
        mset = set(members)
        k0 = int(ks[0]) if n else w.k
        ext = {
            (mid, e.dst_port): seq_of(e.src, e.delayed)
            for mid in members
            for e in self._in_edges[mid]
            if e.src_mod not in mset
        }
        local = {
            f"{mid}.{p.name}": held0[f"{mid}.{p.name}"]
            for mid in members
            for p in self.modules[mid].ports_out
        }
        rows = {name: [] for name in local}
        for i in range(n):
            k = k0 + i
            start = dict(local)
            for mid in members:
                m = self.modules[mid]
                if m.rate is None or not m.rate.runs_at(k):
                    continue
                inputs = {}
                for e in self._in_edges[mid]:
                    if e.src_mod in mset:
                        inputs[e.dst_port] = start[e.src] if e.delayed else local[e.src]
                    else:
                        inputs[e.dst_port] = ext[(mid, e.dst_port)][i]
                w.states[mid], outs = self._call_step(m, w.states[mid], inputs, k, emitted)
                local.update(outs)
            for name in rows:
                rows[name].append(local[name])
        for name, r in rows.items():
            shape = held0[name].shape
            seqs[name] = np.stack(r) if r else np.empty((0, *shape), held0[name].dtype)
            if n:
                w.held[name] = local[name]


def _events_bytes(res: tuple) -> list:
    """Comparable form of the events part of a step/step_block result (purity check)."""
    if len(res) < 3:
        return []
    return [tuple(x.encode() if isinstance(x, Event) else x for x in item) for item in res[2]]


def describe_world(world: World) -> dict[str, Any]:
    return {
        "k": world.k,
        "t_ns": world.t_ns,
        "pending_events": len(world.queue),
        "orders": len(world.order_log),
    }
