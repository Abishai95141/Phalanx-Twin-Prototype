"""Block-mode event emission: ``step_block`` (and fused groups) return events stamped with their emission
step; the scheduler orders and dispatches them exactly as per-step execution would.

Rule under test: any emitted event whose dispatch step falls inside the current block **cuts the block**
there (the pass is discarded and re-run up to that step), whatever the target. Targets in a later segment
(FADEC -> M14), in an earlier segment the block depends on (-> truth) and in the same segment (-> self)
are all bitwise identical to stepping; negative controls show the cut is load-bearing for the latter two.

Sample: toy truth + sensor + an emitter firing every 37 ticks (65 events in N = 2,400 steps), block
lengths 1/7/64/1,024.
"""

from __future__ import annotations

import numpy as np
import pytest

import phalanx.core.scheduler as sched
from phalanx.core.events import Event
from phalanx.core.module import ModuleBase, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import RG_240
from phalanx.core.toy import ToyCounter, ToySensor, ToySpringDamper, default_params

N = 2400
EVERY = 37
LAT = 1_000_000  # 1 ms: dispatched at the next step


class _Emitter(ModuleBase):
    """Every EVERY ticks emits an event to ``target``; handles 'bump' events itself (state it depends on)."""

    version = "1"
    rate = RG_240
    emits_events = True
    ports_in = (Port("x", "m"),)
    ports_out = (Port("y", "m"),)
    state_schema = StateSchema("emitter", 1, (Field("tick", "<i8"), Field("bumps", "<i8")))

    def __init__(self, id, target, kind, block_events=True):
        super().__init__(id, default_params()["counter"])
        self.target, self.kind = target, kind
        self.step_block_emits_events = block_events

    def init(self, params, keys):
        return self.state_schema.make(tick=0, bumps=0)

    def initial_outputs(self, state):
        return {"y": np.array(0.0)}

    def _tick(self, x, tick, bumps, t):
        y = x + 1e-3 * bumps  # the output depends on events received (same-segment dependency)
        ev = None
        if tick % EVERY == EVERY - 1:
            if self.kind == "set_stiffness":
                payload = {"value": 30.0 + 0.5 * (tick // EVERY) + 0.1 * bumps}
            elif self.kind == "bump":
                payload = {}
            else:
                payload = {"x": y, "n": tick}
            ev = Event(t + LAT, self.kind, self.target, payload, source=self.id)
        return y, tick + 1, ev

    def step(self, state, inputs, t, dt):
        y, tick, ev = self._tick(float(inputs["x"]), int(state["tick"]), int(state["bumps"]), t)
        new = {"tick": np.array(tick), "bumps": state["bumps"].copy()}
        return new, {"y": np.array(y)}, ([] if ev is None else [ev])

    def step_block(self, state, inputs, t, dt):
        tick, bumps = int(state["tick"]), int(state["bumps"])
        ys, events = np.empty(t.size), []
        for j in range(t.size):
            ys[j], tick, ev = self._tick(float(inputs["x"][j]), tick, bumps, int(t[j]))
            if ev is not None:
                events.append((int(t[j]), ev))
        return {"tick": np.array(tick), "bumps": np.array(bumps)}, {"y": ys}, events

    def on_event(self, state, event, t):
        if event.kind != "bump":
            return super().on_event(state, event, t)
        return {"tick": state["tick"].copy(), "bumps": state["bumps"] + 1}, []


class _FusedEmitter:
    """A fused group of one event-emitting module (exercises the fused-group event path)."""

    emits_events = True

    def __init__(self, em):
        self.id, self.members, self.em = "fused_emitter", (em.id,), em

    def step_block(self, states, ext, held0, k, dt):
        t = sched.truth_step_times_ns(np.asarray(k, dtype=np.int64))
        new, out, evs = self.em.step_block(states[self.em.id], {"x": ext[f"{self.em.id}.x"]}, t, dt)
        return {self.em.id: new}, {f"{self.em.id}.y": out["y"]}, [(te, self.em.id, ev) for te, ev in evs]


def _system(target, kind, *, block_len=1024, block_events=True, fused=False, validate=False):
    ps = default_params()
    truth = ToySpringDamper("truth", ps["truth"])
    sensor = ToySensor("sensor", ps["sensor"], identity={"sensor": "pos_a"})
    em = _Emitter("emitter", target, kind, block_events)
    counter = ToyCounter("counter", ps["counter"])
    conns = [
        Connection("truth.x", "sensor.x_now"),
        Connection("truth.x", "sensor.x_prev", delayed=True, note="previous frame"),
        Connection("truth.x", "emitter.x"),
    ]
    return System(
        [truth, sensor, em, counter],
        conns,
        rng=RngService(0xE7E7, StreamRegistry()),
        identity=KeyPath.of(scenario="ev", tail="T1", sortie=1),
        fused=[_FusedEmitter(em)] if fused else [],
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


CASES = {
    "later_segment": ("counter", "exceedance"),  # FADEC -> M14 shape
    "earlier_segment": ("truth", "set_stiffness"),  # target state the rest of the block depends on
    "same_segment": ("emitter", "bump"),  # the emitter itself
}


def _go(case, mode, **kw):
    s = _system(*CASES[case], **kw)
    w, tr = s.run(s.start(), N, mode=mode, record=s.output_ports())
    return s, w, tr


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("block_len", [1, 7, 64, 1024])
@pytest.mark.parametrize("fused", [False, True])
def test_block_events_equal_per_step_bitwise(case, block_len, fused):
    s_ref, w_ref, t_ref = _go(case, "step")
    s, w, t = _go(case, "block", block_len=block_len, fused=fused)
    assert len(t_ref.dispatched) >= N // EVERY
    assert [(k, e.encode()) for k, e in t.dispatched] == [(k, e.encode()) for k, e in t_ref.dispatched]
    assert t.digest() == t_ref.digest()
    assert snapshot(s, w) == snapshot(s_ref, w_ref)
    seg = next(sg for sg in s.execution()["segments"] if sg["members"] == ["emitter"])
    assert seg["module_step_block"] or seg["fused"] == "fused_emitter"  # really ran as a block


@pytest.mark.integration
def test_block_events_validation_mode_and_mid_block_snapshot():
    s_ref, w_ref, t_ref = _go("earlier_segment", "step")
    k_cut = 2 * EVERY + 5  # inside a block, after two emissions, with one dispatched mid-way
    s1 = _system(*CASES["earlier_segment"], validate=True)
    w1, t1 = s1.run(s1.start(), k_cut, mode="block", record=s1.output_ports())
    s2 = _system(*CASES["earlier_segment"])
    w2, t2 = s2.run(restore(s2, snapshot(s1, w1)), N - k_cut, mode="block", record=s2.output_ports())
    assert snapshot(s2, w2) == snapshot(s_ref, w_ref)
    assert t1.concat(t2).digest() == t_ref.digest()


@pytest.mark.integration
@pytest.mark.parametrize("case", ["earlier_segment", "same_segment"])
def test_negative_control_without_the_cut_results_diverge(case, monkeypatch):
    """If the scheduler did not cut the block at an in-block dispatch step, the target would see the event
    late (at the block end) and the run would differ from per-step execution."""
    _, _w_ref, t_ref = _go(case, "step")
    monkeypatch.setattr(sched.System, "_block_cut", lambda self, emitted, k_stop: None)
    _s, _w, t = _go(case, "block", block_len=1024)
    assert t.digest() != t_ref.digest()


@pytest.mark.integration
def test_later_segment_target_cost_of_cuts_is_bounded(monkeypatch):
    """Cuts happen once per in-block dispatch; with the prediction hint the next block ends at the next
    dispatch step, so most blocks need no discarded pass."""
    calls = []
    real = sched.System._run_block

    def spy(self, w, k1):
        calls.append((w.k, k1))
        return real(self, w, k1)

    monkeypatch.setattr(sched.System, "_run_block", spy)
    _s, _w, t = _go("later_segment", "block", block_len=1024)
    n_dispatch_steps = len({k for k, _ in t.dispatched})
    passes = len(calls)
    discarded = passes - len({c[0] for c in calls})  # a start step visited twice = one discarded pass
    assert discarded <= 3 and passes <= n_dispatch_steps + 5


@pytest.mark.integration
def test_block_events_contract_errors():
    s = _system("counter", "exceedance", block_events=True)
    em = s.modules["emitter"]

    def bad_time(state, inputs, t, dt):
        new, out, evs = _Emitter.step_block(em, state, inputs, t, dt)
        return new, out, [(te + 1, ev) for te, ev in evs]  # not a step time

    em.step_block = bad_time
    with pytest.raises(sched.ContractError, match="not a step time"):
        s.run(s.start(), 200, mode="block")
