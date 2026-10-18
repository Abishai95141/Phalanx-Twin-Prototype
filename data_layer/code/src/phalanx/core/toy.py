"""Toy system for kernel tests and as a worked example of the module contract.

**This is a test fixture for the core kernel (W0.2), not a physics deliverable.** Its parameter values
are arbitrary and tagged ``[ASSUMPTION]`` with source "W0.2 kernel test fixture"; nothing downstream may
use them. It exists to exercise every kernel guarantee (A1-A9) on a small closed-loop, multi-rate,
multi-clock, event-emitting system:

- ``ToySpringDamper`` (a): mass-spring-damper truth, sub-stepped (symplectic Euler), driven by a keyed
  process-disturbance force (one N(0,1) draw per tick from stream ``toy.process_force``); its stiffness
  lives in state so an order (event ``set_stiffness``) can change it mid-run.
- ``ToySensor`` (b): samples truth position on its **own drifting clock domain** (default 50 Hz,
  +910 ppm, a non-divisor of 240 Hz), interpolating between truth frames on the AD-35 ns grid, plus keyed
  measurement noise indexed by *sample* number (stream ``toy.measurement_noise``).
- ``ToyController``: an 80 Hz PD loop closing on truth through documented one-frame delays (a forced
  segment; ``ToyLoopFused`` is its fused block implementation).
- ``ToySampler``: a 10 Hz (phase 5) module with its own ``step_block`` (slow-rate hold in block mode).
- ``ToyRenewal`` + ``ToyCounter`` (``build_usage_system``): an event-only, usage-mode system (event jump).
- ``ToyMonitor`` / ``ToyCounter``: a 10 Hz exceedance monitor that emits events, and an event-only module
  that counts them (and chains a same-time follow-up event every third count).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from .events import Event
from .module import Inputs, ModuleBase, Outputs, Param, ParamSet, Port
from .rng import DrawLedger, KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from .sampling import max_samples_per_step, sample_ports, samples_for_steps
from .scheduler import Connection, System, World
from .state import Field, State, StateSchema
from .time import (
    RG_240,
    ClockDomain,
    RateGroup,
    as_fraction,
    latest_truth_step,
    latest_truth_steps,
    truth_step_time_ns,
    truth_step_times_ns,
)

FIXTURE_SOURCE = "W0.2 kernel test fixture (not a physics deliverable)"


def _p(value, unit: str) -> Param:
    return Param(value, unit, "ASSUMPTION", FIXTURE_SOURCE)


def default_params() -> dict[str, ParamSet]:
    return {
        "truth": ParamSet(
            "toy.truth",
            {
                "mass": _p(2.0, "kg"),
                "damping": _p(0.6, "kg/s"),
                "stiffness": _p(30.0, "kg/s**2"),
                "sigma_force": _p(5.0, "N"),
                "n_sub": _p(4, "1"),
                "x0": _p(0.1, "m"),
                "v0": _p(0.0, "m/s"),
            },
        ),
        "sensor": ParamSet(
            "toy.sensor",
            {
                "f_nom": _p("50", "Hz"),
                "freq_offset": _p("0.000910", "1"),
                "phase": _p(1_234_567, "ns"),
                "sigma_noise": _p(0.002, "m"),
            },
        ),
        "ctrl": ParamSet("toy.ctrl", {"kp": _p(12.0, "kg/s**2"), "kd": _p(1.5, "kg/s")}),
        "monitor": ParamSet("toy.monitor", {"threshold": _p(0.04, "m"), "latency": _p(3_000_000, "ns")}),
        "counter": ParamSet("toy.counter", {"chain_every": _p(3, "1")}),
    }


# ------------------------------------------------------------------------------------------------- (a)


def _advance(x: float, v: float, k_s: float, m: float, c: float, f: float, h: float, n_sub: int):
    """Symplectic Euler, ``n_sub`` sub-steps of ``h`` (the one arithmetic path for step and step_block)."""
    for _ in range(n_sub):
        a = (f - c * v - k_s * x) / m
        v = v + h * a
        x = x + h * v
    return x, v


class ToySpringDamper(ModuleBase):
    """(a) Truth: m x'' + c x' + k x = sigma_f * w_k + u (test fixture)."""

    version = "1.0.0"
    rate = RG_240
    ports_out = (Port("x", "m"), Port("v", "m/s"))
    state_schema = StateSchema(
        "toy.truth",
        1,
        (Field("x", "<f8"), Field("v", "<f8"), Field("stiffness", "<f8"), Field("tick", "<i8")),
    )
    streams = (
        StreamDecl(
            "toy",
            "process_force",
            ("scenario", "tail", "sortie"),
            Variate.NORMAL,
            4096,
            "core.toy.truth",
            "per-tick process disturbance (test fixture)",
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, controlled: bool = False, **kw) -> None:
        if controlled:
            self.ports_in = (Port("u", "N"),)
        self.controlled = controlled
        super().__init__(id, params, **kw)
        self._m = float(params.value("mass"))
        self._c = float(params.value("damping"))
        self._sig = float(params.value("sigma_force"))
        self._nsub = int(params.value("n_sub"))

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(
            x=params.value("x0"), v=params.value("v0"), stiffness=params.value("stiffness"), tick=0
        )

    def initial_outputs(self, state: State) -> Outputs:
        return {"x": state["x"].copy(), "v": state["v"].copy()}

    def _one(self, x, v, k_s, u, w, dt):
        return _advance(x, v, k_s, self._m, self._c, self._sig * w + u, dt / self._nsub, self._nsub)

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        j = int(state["tick"])
        w = float(self.stream("process_force").draws(j, 1)[0])
        u = float(inputs["u"]) if self.controlled else 0.0
        x, v = self._one(float(state["x"]), float(state["v"]), float(state["stiffness"]), u, w, dt)
        new = {
            "x": np.array(x),
            "v": np.array(v),
            "stiffness": state["stiffness"].copy(),
            "tick": np.array(j + 1),
        }
        return new, {"x": np.array(x), "v": np.array(v)}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        n = t.size
        j0 = int(state["tick"])
        w = self.stream("process_force").draws(j0, n)
        u = inputs["u"] if self.controlled else np.zeros(n)
        x, v, k_s = float(state["x"]), float(state["v"]), float(state["stiffness"])
        xs, vs = np.empty(n), np.empty(n)
        for i in range(n):
            x, v = self._one(x, v, k_s, float(u[i]), float(w[i]), dt)
            xs[i], vs[i] = x, v
        new = {
            "x": np.array(x),
            "v": np.array(v),
            "stiffness": state["stiffness"].copy(),
            "tick": np.array(j0 + n),
        }
        return new, {"x": xs, "v": vs}

    def on_event(self, state: State, event: Event, t: int):
        if event.kind != "set_stiffness":
            return super().on_event(state, event, t)
        new = dict(state)
        new["stiffness"] = np.array(float(event.payload["value"]))
        return new, []


# ------------------------------------------------------------------------------------------------- (b)


class ToySensor(ModuleBase):
    """(b) Position sensor on its own oscillator, interpolating truth, with keyed noise per sample.

    Emits through the clock-domain **sample-buffer pattern** (``core/sampling.py``): ``y`` (capacity,),
    ``y_t`` sample instants, ``y_n`` valid count and ``y_first`` absolute index of slot 0. Unused slots
    are 0; there is no NaN anywhere. ``step`` and ``step_block`` share ``_emit`` (one arithmetic path).
    """

    version = "2.0.0"
    rate = RG_240
    ports_in = (Port("x_now", "m"), Port("x_prev", "m"))
    state_schema = StateSchema("toy.sensor", 1, (Field("n_next", "<i8"),))
    streams = (
        StreamDecl(
            "toy",
            "measurement_noise",
            ("scenario", "tail", "sortie", "sensor"),
            Variate.NORMAL,
            4096,
            "core.toy.sensor",
            "per-sample measurement noise (test fixture)",
        ),
    )

    def __init__(self, id: str, params: ParamSet, **kw) -> None:
        self.domain = ClockDomain(
            f"{id}.clock",
            as_fraction(params.value("f_nom")),
            as_fraction(params.value("freq_offset")) * 1_000_000,
            int(params.value("phase")),
        )
        self.capacity = max_samples_per_step(self.domain, self.rate.divisor)
        self.ports_out = sample_ports("y", "m", self.capacity, self.domain)
        super().__init__(id, params, **kw)
        self._sig = float(params.value("sigma_noise"))

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(n_next=self.domain.first_index_at_or_after(0))

    def initial_outputs(self, state: State) -> Outputs:
        c = self.capacity
        return {
            "y": np.zeros(c),
            "y_t": np.zeros(c, np.int64),
            "y_n": np.array(0, np.int64),
            "y_first": np.array(int(state["n_next"]), np.int64),
        }

    def _emit(self, n_next: int, t0: np.ndarray, t1: np.ndarray, x_prev: np.ndarray, x_now: np.ndarray):
        ss = samples_for_steps(self.domain, n_next, t0, t1)
        i = ss.step
        w = (ss.times - t0[i]).astype(np.float64) / (t1[i] - t0[i]).astype(np.float64)
        noise = self.stream("measurement_noise").draws(ss.first, ss.times.size)
        vals = x_prev[i] + w * (x_now[i] - x_prev[i]) + self._sig * noise
        y, yt = ss.pack(vals, self.capacity)
        out = {"y": y, "y_t": yt, "y_n": ss.count, "y_first": ss.first_of_step}
        return {"n_next": np.array(ss.next_index, np.int64)}, out

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        t0 = np.array([t], np.int64)
        t1 = np.array([truth_step_time_ns(latest_truth_step(t) + 1)], np.int64)
        x_prev = np.asarray(inputs["x_prev"]).reshape(1)
        x_now = np.asarray(inputs["x_now"]).reshape(1)
        new, out = self._emit(int(state["n_next"]), t0, t1, x_prev, x_now)
        return new, {k: np.array(v[0]) for k, v in out.items()}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        t1 = truth_step_times_ns(latest_truth_steps(t) + 1)
        return self._emit(int(state["n_next"]), t, t1, inputs["x_prev"], inputs["x_now"])


# ------------------------------------------------------------------------------------------------- loop


class ToyController(ModuleBase):
    """80 Hz PD controller closing on truth through one-frame delays (test fixture)."""

    version = "1.0.0"
    ports_in = (Port("x", "m"), Port("v", "m/s"))
    ports_out = (Port("u", "N"),)
    state_schema = StateSchema("toy.ctrl", 1, (Field("n_updates", "<i8"),))

    def __init__(self, id: str, params: ParamSet, *, phase: int = 0, **kw) -> None:
        self.rate = RateGroup(3, phase)
        super().__init__(id, params, **kw)
        self._kp = float(params.value("kp"))
        self._kd = float(params.value("kd"))

    def law(self, x: float, v: float) -> float:
        return -(self._kp * x + self._kd * v)

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(n_updates=0)

    def initial_outputs(self, state: State) -> Outputs:
        return {"u": np.array(0.0)}

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        u = self.law(float(inputs["x"]), float(inputs["v"]))
        return {"n_updates": np.array(int(state["n_updates"]) + 1)}, {"u": np.array(u)}


class ToyLoopFused:
    """Fused block implementation of the [controller, truth] loop (the per-step semantics, one call)."""

    def __init__(self, ctrl: ToyController, truth: ToySpringDamper) -> None:
        self.id = "toy_loop"
        self.members = (ctrl.id, truth.id)
        self.ctrl, self.truth = ctrl, truth

    def step_block(self, states, ext_inputs, held0, k, dt_truth):
        c, tr = self.ctrl, self.truth
        n = k.size
        cu = f"{c.id}.u"
        tx, tv = f"{tr.id}.x", f"{tr.id}.v"
        u = float(held0[cu])
        x, v = float(held0[tx]), float(held0[tv])
        xs_state, vs_state = float(states[tr.id]["x"]), float(states[tr.id]["v"])
        k_s = float(states[tr.id]["stiffness"])
        j0 = int(states[tr.id]["tick"])
        n_upd = int(states[c.id]["n_updates"])
        w = tr.stream("process_force").draws(j0, n)
        us, xs, vs = np.empty(n), np.empty(n), np.empty(n)
        for i in range(n):
            if c.rate.runs_at(int(k[i])):
                u = c.law(x, v)  # x, v: truth outputs at the start of the step (one-frame delay)
                n_upd += 1
            xs_state, vs_state = tr._one(xs_state, vs_state, k_s, u, float(w[i]), dt_truth)
            x, v = xs_state, vs_state
            us[i], xs[i], vs[i] = u, x, v
        states_out = {
            c.id: {"n_updates": np.array(n_upd)},
            tr.id: {
                "x": np.array(xs_state),
                "v": np.array(vs_state),
                "stiffness": states[tr.id]["stiffness"].copy(),
                "tick": np.array(j0 + n),
            },
        }
        return states_out, {cu: us, tx: xs, tv: vs}


# ------------------------------------------------------------------------------------------------- events


class ToyMonitor(ModuleBase):
    """Exceedance monitor with hysteresis (10 Hz by default); emits ``exceedance`` events (test fixture).

    ``block_events=True`` (default) makes its ``step_block`` return events stamped with their emission
    tick, so block mode runs it as a block; ``block_events=False`` keeps the per-step-only behaviour (the
    scheduler then runs it per step). ``step`` and ``step_block`` share ``_tick``.
    """

    version = "1.1.0"
    emits_events = True
    ports_in = (Port("x", "m"),)
    ports_out = (Port("latched", "1", "|b1"),)
    state_schema = StateSchema("toy.monitor", 1, (Field("latched", "|b1"), Field("n_exceed", "<i8")))

    def __init__(
        self,
        id: str,
        params: ParamSet,
        *,
        target: str = "counter",
        divisor: int = 24,
        block_events: bool = True,
        **kw,
    ) -> None:
        self.rate = RateGroup(divisor)
        self.step_block_emits_events = block_events
        super().__init__(id, params, **kw)
        self._thr = float(params.value("threshold"))
        self._lat = int(params.value("latency"))
        self._target = target

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(latched=False, n_exceed=0)

    def initial_outputs(self, state: State) -> Outputs:
        return {"latched": state["latched"].copy()}

    def _tick(self, x: float, latched: bool, n: int, t: int):
        ev = None
        if not latched and abs(x) > self._thr:
            latched, n = True, n + 1
            ev = Event(t + self._lat, "exceedance", self._target, {"x": x, "n": n}, source=self.id)
        elif latched and abs(x) < 0.5 * self._thr:
            latched = False
        return latched, n, ev

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        latched, n, ev = self._tick(float(inputs["x"]), bool(state["latched"]), int(state["n_exceed"]), t)
        new = {"latched": np.array(latched), "n_exceed": np.array(n)}
        return new, {"latched": np.array(latched)}, ([] if ev is None else [ev])

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        latched, n = bool(state["latched"]), int(state["n_exceed"])
        out = np.empty(t.size, dtype=np.bool_)
        events = []
        for j in range(t.size):
            latched, n, ev = self._tick(float(inputs["x"][j]), latched, n, int(t[j]))
            out[j] = latched
            if ev is not None:
                events.append((int(t[j]), ev))  # (emission tick time, event)
        new = {"latched": np.array(latched), "n_exceed": np.array(n)}
        return new, {"latched": out}, events


class ToyCounter(ModuleBase):
    """Event-only module: counts exceedances; every ``chain_every``-th one chains a same-time ``audit``."""

    version = "1.0.0"
    rate = None
    ports_out = (Port("count", "1", "<i8"),)
    state_schema = StateSchema(
        "toy.counter",
        1,
        (Field("count", "<i8"), Field("audits", "<i8"), Field("last_t", "<i8"), Field("sum_x", "<f8")),
    )

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(count=0, audits=0, last_t=-1, sum_x=0.0)

    def initial_outputs(self, state: State) -> Outputs:
        return {"count": state["count"].copy()}

    def on_event(self, state: State, event: Event, t: int):
        new = dict(state)
        out: list[Event] = []
        if event.kind == "exceedance":
            c = int(state["count"]) + 1
            new["count"] = np.array(c)
            new["last_t"] = np.array(t)
            new["sum_x"] = np.array(float(state["sum_x"]) + float(event.payload["x"]))
            if c % int(self.params.value("chain_every")) == 0:
                out.append(Event(t, "audit", self.id, {"count": c}, priority=1, source=self.id))
        elif event.kind == "audit":
            new["audits"] = np.array(int(state["audits"]) + 1)
        else:
            return super().on_event(state, event, t)
        return new, out


# ------------------------------------------------------------------------------------------------- slow rate


class ToySampler(ModuleBase):
    """10 Hz sampler (rate-group phase 5) with its own step_block: exercises the zero-order-hold expansion
    of slow modules and forward one-frame delays in block mode (test fixture)."""

    version = "1.0.0"
    rate = RateGroup(24, 5)
    ports_in = (Port("x", "m"), Port("v_prev", "m/s"))
    ports_out = (Port("x_s", "m"), Port("xv", "m**2/s"), Port("n_samples", "1", "<i8"))
    state_schema = StateSchema("toy.sampler", 1, (Field("count", "<i8"), Field("acc", "<f8")))

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(count=0, acc=0.0)

    def initial_outputs(self, state: State) -> Outputs:
        # before the first tick there is no sample: values 0 and n_samples = 0 (never NaN)
        return {"x_s": np.array(0.0), "xv": np.array(0.0), "n_samples": state["count"].copy()}

    def step(self, state: State, inputs: Inputs, t: int, dt: float):
        x, v = inputs["x"], inputs["v_prev"]
        new = {"count": state["count"] + 1, "acc": state["acc"] + x}
        return new, {"x_s": np.array(x, copy=True), "xv": x * v, "n_samples": new["count"].copy()}

    def step_block(self, state: State, inputs: Inputs, t: np.ndarray, dt: float):
        x, v = inputs["x"], inputs["v_prev"]
        acc = state["acc"]
        for xi in x:  # sequential, same rounding as repeated step
            acc = acc + xi
        c0 = int(state["count"])
        new = {"count": np.array(c0 + t.size), "acc": np.array(acc)}
        n = np.arange(c0 + 1, c0 + t.size + 1, dtype=np.int64)
        return new, {"x_s": np.array(x, copy=True), "xv": x * v, "n_samples": n}


# ------------------------------------------------------------------------------------------------- usage mode


class ToyRenewal(ModuleBase):
    """Event-only renewal process (usage-mode fixture): exponential inter-arrival times drawn from a keyed
    GENERATOR stream indexed by the renewal number (AD-37); each renewal notifies the counter."""

    version = "1.0.0"
    rate = None
    ports_out = (Port("n_renewals", "1", "<i8"), Port("last_interval", "s"))
    state_schema = StateSchema("toy.renewal", 1, (Field("n", "<i8"), Field("last_interval", "<f8")))
    streams = (
        StreamDecl(
            "toy",
            "renewal_interval",
            ("scenario", "tail"),
            Variate.GENERATOR,
            owner="core.toy.renewal",
            description="inter-arrival time per renewal number (test fixture)",
        ),
    )

    def __init__(self, id: str, params: ParamSet, *, target: str = "counter", **kw) -> None:
        super().__init__(id, params, **kw)
        self._mean = float(params.value("mean_interval"))
        self._target = target

    def init(self, params: ParamSet, keys) -> State:
        return self.state_schema.make(n=0, last_interval=0.0)

    def initial_outputs(self, state: State) -> Outputs:
        return {"n_renewals": state["n"].copy(), "last_interval": state["last_interval"].copy()}

    def on_event(self, state: State, event: Event, t: int):
        if event.kind != "renew":
            return super().on_event(state, event, t)
        n = int(state["n"])
        dt_s = float(self.stream("renewal_interval").generator(n).exponential(self._mean))
        # next renewal relative to this event's exact time (not the frame-quantised dispatch time)
        t_next = max(event.t_ns + round(dt_s * 1e9), t)
        new = {"n": np.array(n + 1), "last_interval": np.array(dt_s)}
        out = [
            Event(t_next, "renew", self.id, source=self.id),
            Event(t, "exceedance", self._target, {"x": dt_s}, source=self.id),
        ]
        return new, out


def build_usage_system(
    root: int = 0x5EED_0F_0123_4567_89AB_CDEF_0011_2233,
    *,
    mean_interval_s: float = 3 * 3600.0,
    event_jump: bool = True,
    validate: bool = False,
    purity_check: bool = False,
    block_len: int = 1024,
    ledger: DrawLedger | None = None,
) -> System:
    """An event-only (usage-mode) toy: renewal process + counter. Start it with :func:`start_usage`."""
    ps = default_params()
    renewal_ps = ParamSet("toy.renewal", {"mean_interval": _p(float(mean_interval_s), "s")})
    mods = [ToyRenewal("renewal", renewal_ps), ToyCounter("counter", ps["counter"])]
    return System(
        mods,
        [],
        rng=RngService(root, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="toy", tail="T1"),
        validate=validate,
        purity_check=purity_check,
        block_len=block_len,
        event_jump=event_jump,
        dict_hash="toy-no-dictionary",
    )


def start_usage(system: System) -> World:
    """Initial world with the first renewal scheduled at t = 0."""
    return system.inject(system.start(), [Event(0, "renew", "renewal", source="scenario")])


# ------------------------------------------------------------------------------------------------- factory


def build_toy_system(
    root: int = 0x5EED_0F_0123_4567_89AB_CDEF_0011_2233,
    *,
    scenario: str = "toy",
    tail: str = "T1",
    sortie: int = 1,
    controlled: bool = False,
    ctrl_phase: int = 0,
    monitored: bool = False,
    monitor_divisor: int = 24,
    monitor_block_events: bool = True,
    sampled: bool = False,
    fused: bool = False,
    validate: bool = False,
    purity_check: bool = False,
    block_len: int = 1024,
    ledger: DrawLedger | None = None,
    params: Mapping[str, ParamSet] | None = None,
    sensor_id: str = "pos_a",
    truth_cls: type[ToySpringDamper] | None = None,
) -> System:
    """Fresh modules + fresh RNG service for the toy system (call again for every branch / process)."""
    ps = default_params()
    ps.update(params or {})
    mods: list[ModuleBase] = []
    conns = []
    ctrl = None
    if controlled:
        ctrl = ToyController("ctrl", ps["ctrl"], phase=ctrl_phase)
        mods.append(ctrl)
    truth = (truth_cls or ToySpringDamper)("truth", ps["truth"], controlled=controlled)
    sensor = ToySensor("sensor", ps["sensor"], identity={"sensor": sensor_id})
    mods += [truth, sensor]
    conns += [
        Connection("truth.x", "sensor.x_now"),
        Connection("truth.x", "sensor.x_prev", delayed=True, note="previous truth frame, for interpolation"),
    ]
    if controlled:
        conns += [
            Connection(
                "truth.x", "ctrl.x", delayed=True, note="FCS-style loop break: controller sees last frame"
            ),
            Connection(
                "truth.v", "ctrl.v", delayed=True, note="FCS-style loop break: controller sees last frame"
            ),
            Connection("ctrl.u", "truth.u"),
        ]
    if monitored:
        mon = ToyMonitor("monitor", ps["monitor"], divisor=monitor_divisor, block_events=monitor_block_events)
        mods += [mon, ToyCounter("counter", ps["counter"])]
        conns.append(Connection("truth.x", "monitor.x"))
    if sampled:
        mods.append(ToySampler("sampler", ps["counter"]))
        conns += [
            Connection("truth.x", "sampler.x"),
            Connection(
                "truth.v", "sampler.v_prev", delayed=True, note="previous-frame velocity (test of delays)"
            ),
        ]
    rng = RngService(root, StreamRegistry(), ledger=ledger)
    groups = [ToyLoopFused(ctrl, truth)] if (fused and ctrl is not None) else []
    return System(
        mods,
        conns,
        rng=rng,
        identity=KeyPath.of(scenario=scenario, tail=tail, sortie=sortie),
        fused=groups,
        validate=validate,
        purity_check=purity_check,
        block_len=block_len,
        dict_hash="toy-no-dictionary",
    )


def set_stiffness_order(t_ns: int, value: float) -> Event:
    """An 'order' for fork tests: change the truth stiffness from ``t_ns`` (enters via the event queue)."""
    return Event(t_ns, "set_stiffness", "truth", {"value": float(value)}, source="orders")
