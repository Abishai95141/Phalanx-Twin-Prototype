"""W0.2 scheduler: wiring checks, block == per-step (A6), Gauss-Seidel / delay / rate-group / event
semantics, validation-mode guards.

Sample: the toy system for N = 2,400 truth steps (10 s of sim time): enough for ~500 sensor samples on the
50 Hz clock, ~800 controller ticks at 80 Hz, ~100 monitor ticks and several exceedance events.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.module import ContractError, ModuleBase, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import CausalityError, Connection, PurityError, System
from phalanx.core.snapshot import snapshot
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import truth_step_time_ns
from phalanx.core.toy import (
    ToyController,
    ToyMonitor,
    ToySensor,
    ToySpringDamper,
    build_toy_system,
    default_params,
)

N = 2400

CONFIGS = {
    "plain": {},
    "loop_fallback": {"controlled": True},
    "loop_fused": {"controlled": True, "fused": True},
    "loop_phase2": {"controlled": True, "ctrl_phase": 2},
    "events": {"monitored": True},
    "events_per_step": {"monitored": True, "monitor_block_events": False},
    "events_240hz": {"monitored": True, "monitor_divisor": 1},
    "all_fused": {"controlled": True, "monitored": True, "fused": True},
    "all_fallback": {"controlled": True, "monitored": True},
    "slow_block": {"sampled": True},
    "everything": {"controlled": True, "monitored": True, "fused": True, "sampled": True},
}


def _run(cfg, mode, n=N, **extra):
    s = build_toy_system(**cfg, **extra)
    w, tr = s.run(s.start(), n, mode=mode, record=s.output_ports())
    return s, w, tr


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("name", sorted(CONFIGS))
@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_block_execution_equals_per_step_bitwise(name, block_len):
    """A6: run(n) via step_block / fused groups / segment fallback == the per-step reference, bitwise."""
    cfg = CONFIGS[name]
    s_ref, w_ref, tr_ref = _run(cfg, "step")
    s_blk, w_blk, tr_blk = _run(cfg, "block", block_len=block_len)
    assert tr_blk.digest() == tr_ref.digest()
    assert snapshot(s_blk, w_blk) == snapshot(s_ref, w_ref)
    assert [(k, e.encode()) for k, e in tr_blk.dispatched] == [(k, e.encode()) for k, e in tr_ref.dispatched]
    # the run exercised what it claims to
    assert int(tr_ref.ports["sensor.y_n"].sum()) > 450
    if cfg.get("monitored"):
        assert len(tr_ref.dispatched) >= 4
    segs = s_blk.execution()["segments"]
    if cfg.get("controlled"):
        loop = next(sg for sg in segs if sg["members"] == ["ctrl", "truth"])
        assert (loop["fused"] is not None) == bool(cfg.get("fused"))
    else:
        assert next(sg for sg in segs if sg["members"] == ["truth"])["module_step_block"]


@pytest.mark.integration
def test_interleaved_modes_and_chunking_equal_one_reference_run():
    cfg = CONFIGS["all_fused"]
    s_ref, w_ref, tr_ref = _run(cfg, "step")
    s = build_toy_system(**cfg, block_len=64)
    w = s.start()
    parts = []
    for n, mode in [(500, "block"), (1, "step"), (699, "step"), (1200, "block")]:
        w, tr = s.run(w, n, mode=mode, record=s.output_ports())
        parts.append(tr)
    whole = parts[0]
    for p in parts[1:]:
        whole = whole.concat(p)
    assert whole.digest() == tr_ref.digest()
    assert snapshot(s, w) == snapshot(s_ref, w_ref)


@pytest.mark.integration
def test_sensor_and_controller_see_the_documented_frames():
    """Gauss-Seidel + one-frame-delay semantics, checked by exact reconstruction from the truth trace.

    Sensor sample n in step k: x_prev = x(t_k) (delayed edge), x_now = x(t_{k+1}) (truth ran earlier
    this step). Controller tick k: u = law(x(t_k), v(t_k)) (delayed back-edges).
    """
    s, w, tr = _run(CONFIGS["loop_fused"], "block")
    x = tr.ports["truth.x"]  # row k = x(t_{k+1})
    v = tr.ports["truth.v"]
    p = default_params()["truth"]
    x_at = np.concatenate([[p.value("x0")], x])  # x_at[k] = x(t_k)
    v_at = np.concatenate([[p.value("v0")], v])
    sensor = s.modules["sensor"]
    noise_stream = RngService(s.rng.root, StreamRegistry(sensor.streams)).scope(s.identity)
    noise = noise_stream.stream("toy", "measurement_noise", sensor="pos_a").draws(0, 600)
    sig = float(sensor.params.value("sigma_noise"))
    n = 0
    for k in range(N):
        t0, t1 = truth_step_time_ns(k), truth_step_time_ns(k + 1)
        cnt = int(tr.ports["sensor.y_n"][k])
        assert int(tr.ports["sensor.y_first"][k]) == n  # absolute index of slot 0
        for slot in range(cnt):
            ts = sensor.domain.sample_time_ns(n)
            assert t0 <= ts < t1 and tr.ports["sensor.y_t"][k, slot] == ts
            wgt = np.float64(ts - t0) / np.float64(t1 - t0)
            want = x_at[k] + wgt * (x_at[k + 1] - x_at[k]) + sig * noise[n]
            assert tr.ports["sensor.y"][k, slot] == want
            n += 1
        # unused slots are zero, never NaN
        assert np.all(tr.ports["sensor.y"][k, cnt:] == 0.0) and np.all(tr.ports["sensor.y_t"][k, cnt:] == 0)
    assert n == sensor.domain.first_index_at_or_after(truth_step_time_ns(N))
    ctrl = s.modules["ctrl"]
    u = tr.ports["ctrl.u"]
    for k in range(N):
        if k % 3 == 0:
            assert u[k] == ctrl.law(x_at[k], v_at[k])
        else:
            assert u[k] == u[k - 1]  # zero-order hold between 80 Hz ticks
    assert int(w.states["ctrl"]["n_updates"]) == N // 3


@pytest.mark.integration
@pytest.mark.parametrize("phase", [0, 1, 2])
def test_rate_group_phase(phase):
    _s, w, tr = _run({"controlled": True, "ctrl_phase": phase}, "block", n=300)
    changes = np.flatnonzero(np.diff(tr.ports["ctrl.u"])) + 1
    assert set((changes % 3).tolist()) == {phase}
    assert int(w.states["ctrl"]["n_updates"]) == len(range(phase, 300, 3))


@pytest.mark.integration
def test_event_dispatch_timing_and_same_time_chaining():
    _s, w, tr = _run(CONFIGS["all_fused"], "step")
    lat = int(default_params()["monitor"].value("latency"))
    count = tr.ports["counter.count"]
    exc = [(k, e) for k, e in tr.dispatched if e.kind == "exceedance"]
    aud = [(k, e) for k, e in tr.dispatched if e.kind == "audit"]
    assert len(exc) >= 3 and len(aud) == len(exc) // 3
    for k, e in exc:
        assert truth_step_time_ns(k - 1) < e.t_ns <= truth_step_time_ns(k)  # first step with t_k >= t_event
        emit_t = e.t_ns - lat
        assert (emit_t * 240) % (24 * 10**9) == 0  # emitted on a 10 Hz monitor tick
        assert count[k] == count[k - 1] + 1  # counter output refreshed at dispatch
    for (k, e), (kx, ex) in zip(aud, exc[2::3], strict=False):
        assert k == kx and e.t_ns == truth_step_time_ns(k) and e.seq > ex.seq  # same-step chain
    assert int(w.states["counter"]["audits"]) == len(aud)


@pytest.mark.integration
def test_causality_is_enforced():
    s = build_toy_system()
    w, _ = s.run(s.start(), 10)
    with pytest.raises(CausalityError):
        s.inject(w, [Event(truth_step_time_ns(9), "set_stiffness", "truth", {"value": 1.0})])
    bad = _build([_Bad("bad", "past")], [])  # a module that schedules an event 1 ns into the past
    with pytest.raises(CausalityError):
        bad.run(bad.start(), 5, mode="step")


@pytest.mark.integration
def test_inject_logs_orders():
    s = build_toy_system()
    w0 = s.start()
    w1 = s.inject(w0, [Event(0, "set_stiffness", "truth", {"value": 40.0})])
    assert len(w0.order_log) == 0 and len(w1.order_log) == 1 and w1.order_log[0].seq == 0
    assert s.order_log_hash(w1) != s.order_log_hash(w0)
    w2, tr = s.run(w1, 5, record=["truth.x"])
    assert float(w2.states["truth"]["stiffness"]) == 40.0 and tr.dispatched[0][0] == 0


# ------------------------------------------------------------------------------------------ wiring


def _toy_parts(controlled=False):
    ps = default_params()
    mods = []
    if controlled:
        mods.append(ToyController("ctrl", ps["ctrl"]))
    mods += [
        ToySpringDamper("truth", ps["truth"], controlled=controlled),
        ToySensor("sensor", ps["sensor"], identity={"sensor": "a"}),
    ]
    conns = [
        Connection("truth.x", "sensor.x_now"),
        Connection("truth.x", "sensor.x_prev", delayed=True, note="previous frame"),
    ]
    return mods, conns


def _build(mods, conns, **kw):
    return System(mods, conns, rng=RngService(7, StreamRegistry()), identity=KeyPath.of(scenario="w"), **kw)


@pytest.mark.integration
def test_wiring_errors_are_caught_at_build_time():
    mods, conns = _toy_parts()
    _build(mods, conns)
    cases = [
        (conns[:1], "not wired"),
        ([*conns, Connection("truth.v", "sensor.x_now")], "wired twice"),
        ([conns[0], Connection("truth.x", "sensor.x_prev", delayed=True)], "documented"),
        ([*conns, Connection("truth.q", "sensor.x_now")], "not an output"),
        ([*conns, Connection("nope.x", "sensor.x_now")], "unknown module"),
    ]
    for cs, msg in cases:
        mods, _ = _toy_parts()
        with pytest.raises(ContractError, match=msg):
            _build(mods, cs)
    mods, conns = _toy_parts(controlled=True)
    back = [
        *conns,
        Connection("truth.x", "ctrl.x"),
        Connection("truth.v", "ctrl.v", True, "d"),
        Connection("ctrl.u", "truth.u"),
    ]
    with pytest.raises(ContractError, match="Gauss-Seidel"):
        _build(mods, back)
    mods, conns = _toy_parts()
    with pytest.raises(ContractError, match="shape"):
        _build(mods, [Connection("sensor.y", "sensor.x_now"), conns[1]])


# ------------------------------------------------------------------------------------------ guards


class _Bad(ModuleBase):
    version = "1"
    ports_out = (Port("y", "m"),)
    state_schema = StateSchema("bad", 1, (Field("x", "<f8"),))

    def __init__(self, id, how):
        super().__init__(id, default_params()["counter"])
        self.how = how
        self.emits_events = how == "past"
        self.calls = 0

    def init(self, params, keys):
        return self.state_schema.make(x=0.0)

    def initial_outputs(self, state):
        return {"y": np.array(0.0)}

    def step(self, state, inputs, t, dt):
        self.calls += 1
        if self.how == "inplace":
            state["x"][...] = 1.0
            return state, {"y": np.array(1.0)}
        if self.how == "hidden":
            return {"x": np.array(float(self.calls))}, {"y": np.array(float(self.calls))}
        if self.how == "events":
            return {"x": state["x"]}, {"y": np.array(0.0)}, [Event(t, "x", self.id)]
        if self.how == "past":
            return {"x": state["x"]}, {"y": np.array(0.0)}, ([Event(t - 1, "x", self.id)] if t > 0 else [])
        if self.how == "shape":
            return {"x": state["x"]}, {"y": np.zeros(2)}
        if self.how == "missing":
            return {"x": state["x"]}, {}
        if self.how == "nan":  # NaN at a port boundary (the contract has no NaN)
            return {"x": state["x"]}, {"y": np.array(np.nan)}
        raise AssertionError


@pytest.mark.integration
@pytest.mark.parametrize(
    "how, exc, validate",
    [
        ("inplace", ValueError, True),  # read-only state views reject in-place mutation
        ("hidden", PurityError, True),  # double-call purity check exposes hidden state
        ("events", ContractError, False),  # events from a module not declared emits_events
        ("shape", ContractError, True),
        ("missing", ContractError, False),
        ("nan", ContractError, True),
    ],
)
def test_validation_guards(how, exc, validate):
    s = _build([_Bad("bad", how)], [], validate=validate, purity_check=validate)
    with pytest.raises(exc):
        s.run(s.start(), 3, mode="step")


@pytest.mark.integration
def test_event_emitting_module_block_path_requires_its_declaration():
    """An event-emitting module runs as a block only if it declares step_block_emits_events."""
    for block_events in (True, False):
        s = build_toy_system(monitored=True, monitor_block_events=block_events)
        seg = next(sg for sg in s.execution()["segments"] if sg["members"] == ["monitor"])
        assert seg["module_step_block"] is block_events and ToyMonitor.emits_events


class _Group:
    def __init__(self, gid, members):
        self.id, self.members = gid, tuple(members)

    def step_block(self, *a):  # pragma: no cover - never reached: the build must fail first
        raise AssertionError


@pytest.mark.integration
def test_fused_group_validation():
    mods, conns = _toy_parts(controlled=True)
    loop = [
        Connection("truth.x", "ctrl.x", True, "loop break"),
        Connection("truth.v", "ctrl.v", True, "loop break"),
        Connection("ctrl.u", "truth.u"),
    ]
    with pytest.raises(ContractError, match="splits the loop"):
        _build(mods, conns + loop, fused=[_Group("g", ["truth", "sensor"])])
    mods, conns = _toy_parts(controlled=True)
    with pytest.raises(ContractError, match="contiguous"):
        _build(mods, conns + loop, fused=[_Group("g", ["ctrl", "sensor"])])
    mods, conns = _toy_parts(controlled=True)
    ok = _build(mods, conns + loop, fused=[_Group("g", ["ctrl", "truth", "sensor"])])  # superset is fine
    assert ok.segments == (("ctrl", "truth", "sensor"),)
    ps = default_params()
    mods = [ToySpringDamper("truth", ps["truth"]), ToyMonitor("monitor", ps["monitor"], target="truth")]
    with pytest.raises(ContractError, match="emit events"):
        _build(mods, [Connection("truth.x", "monitor.x")], fused=[_Group("g", ["truth", "monitor"])])


@pytest.mark.integration
def test_slow_module_step_block_holds_between_ticks():
    """A 10 Hz phase-5 module run through its own step_block: values only change at k % 24 == 5."""
    s, w, tr = _run({"sampled": True}, "block", block_len=50)
    seg = next(sg for sg in s.execution()["segments"] if sg["members"] == ["sampler"])
    assert seg["module_step_block"] is True
    x, v = tr.ports["truth.x"], tr.ports["truth.v"]
    xs, xv = tr.ports["sampler.x_s"], tr.ports["sampler.xv"]
    ns = tr.ports["sampler.n_samples"]
    assert np.all(xs[:5] == 0.0) and np.all(ns[:5] == 0)  # nothing sampled yet: explicit count, no NaN
    assert ns[-1] == len(range(5, N, 24)) and np.all(np.diff(ns) >= 0)
    for k in range(5, N):
        if k % 24 == 5:
            assert xs[k] == x[k] and xv[k] == x[k] * v[k - 1]  # same-step x, previous-frame v
        else:
            assert xs[k] == xs[k - 1] and xv[k] == xv[k - 1]
    assert int(w.states["sampler"]["count"]) == len(range(5, N, 24))
