"""W0.2 A4 (I8) and A5 at system level: forks, common random numbers, and non-perturbation by new consumers.

Sample: toy system with loop + monitor + events; snapshot at k = 1,200, suffix of 1,200 steps (5 s): every
stream is consumed several hundred times in the suffix (truth: 1,200 draws, sensor: ~250 samples).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.module import ModuleBase, Port
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamDecl, StreamRegistry, Variate, crn_audit
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import Field, StateSchema
from phalanx.core.time import truth_step_time_ns
from phalanx.core.toy import (
    ToySensor,
    ToySpringDamper,
    build_toy_system,
    default_params,
    set_stiffness_order,
)

K, N = 1200, 2400
CFG = {"controlled": True, "monitored": True, "fused": True}


@pytest.fixture(scope="module")
def parent_snapshot():
    s = build_toy_system(**CFG)
    w, _ = s.run(s.start(), K)
    return snapshot(s, w)


def _branch(snap, orders=(), ledger=None, mode="block", **kw):
    s = build_toy_system(**CFG, ledger=ledger, **kw)
    w = restore(s, snap)
    if orders:
        w = s.inject(w, list(orders))
    w2, tr = s.run(w, N - K, mode=mode, record=s.output_ports())
    return s, w2, tr


@pytest.mark.fork
def test_identical_suffixes_give_identical_branches(parent_snapshot):
    order = set_stiffness_order(truth_step_time_ns(K), 60.0)  # at the fork boundary (t = 5 s)
    for orders in ((), (order,)):
        sa, wa, ta = _branch(parent_snapshot, orders)
        sb, wb, tb = _branch(parent_snapshot, orders, mode="step")
        assert snapshot(sa, wa) == snapshot(sb, wb)
        assert ta.digest() == tb.digest()


@pytest.mark.fork
def test_crn_audit_divergent_orders_share_the_exogenous_future(parent_snapshot):
    """Branch C gets an order (stiffness doubled at the fork); its trajectory changes, its draws do not."""
    la, lc = DrawLedger(), DrawLedger()
    _, _wa, ta = _branch(parent_snapshot, (), la)
    _, _wc, tc = _branch(parent_snapshot, (set_stiffness_order(truth_step_time_ns(K), 60.0),), lc)
    assert not np.array_equal(ta.ports["truth.x"], tc.ports["truth.x"])  # the order had an effect
    assert not np.array_equal(ta.ports["sensor.y"], tc.ports["sensor.y"])
    rep = crn_audit(la, lc)
    assert rep.ok, rep
    assert len(rep.identical) == 2  # both exogenous streams (process force, measurement noise) audited
    assert {p.split("component=s:")[1].split("#")[0] for p in rep.identical} == {
        "process_force",
        "measurement_noise",
    }


class _LeakyTruth(ToySpringDamper):
    """Negative control: draws its disturbance at an index that depends on its own state (a CRN bug)."""

    def step(self, state, inputs, t, dt):
        j = int(state["tick"]) * 2 + (1 if float(state["x"]) > 0 else 0)
        w = float(self.stream("process_force").draws(j, 1)[0])
        u = float(inputs["u"]) if self.controlled else 0.0
        x, v = self._one(float(state["x"]), float(state["v"]), float(state["stiffness"]), u, w, dt)
        new = {
            "x": np.array(x),
            "v": np.array(v),
            "stiffness": state["stiffness"].copy(),
            "tick": state["tick"] + 1,
        }
        return new, {"x": np.array(x), "v": np.array(v)}

    step_block = None  # force the per-step path


def _leaky_system(ledger):
    ps = default_params()
    truth = _LeakyTruth("truth", ps["truth"])
    sensor = ToySensor("sensor", ps["sensor"], identity={"sensor": "pos_a"})
    conns = [
        Connection("truth.x", "sensor.x_now"),
        Connection("truth.x", "sensor.x_prev", delayed=True, note="previous frame"),
    ]
    rng = RngService(0xBEEF, StreamRegistry(), ledger=ledger)
    return System([truth, sensor], conns, rng=rng, identity=KeyPath.of(scenario="toy", tail="T1", sortie=1))


@pytest.mark.fork
def test_crn_audit_catches_state_dependent_draws():
    s0 = _leaky_system(None)
    w0, _ = s0.run(s0.start(), K, mode="step")
    snap = snapshot(s0, w0)
    ledgers = []
    for value in (None, 300.0):
        led = DrawLedger()
        s = _leaky_system(led)
        w = restore(s, snap)
        if value is not None:
            w = s.inject(w, [set_stiffness_order(w.t_ns, value)])
        s.run(w, N - K, mode="step")
        ledgers.append(led)
    rep = crn_audit(*ledgers)
    assert not rep.ok
    assert any("process_force" in p for p in rep.consumption_differs)
    assert any("measurement_noise" in p for p in rep.identical)  # the well-behaved stream still passes


class _Gust(ModuleBase):
    """A new consumer of a new stream, placed *first* in the order and wired to nothing (A5)."""

    version = "1"
    ports_out = (Port("g", "m/s"),)
    state_schema = StateSchema("gust", 1, (Field("tick", "<i8"),))
    streams = (StreamDecl("toy_extra", "gust", ("scenario", "tail", "sortie"), Variate.NORMAL, 64),)

    def init(self, params, keys):
        return self.state_schema.make(tick=0)

    def initial_outputs(self, state):
        return {"g": np.array(0.0)}

    def step(self, state, inputs, t, dt):
        j = int(state["tick"])
        g = float(self.stream("gust").draws(j, 3).sum())
        return {"tick": np.array(j + 1)}, {"g": np.array(g)}


@pytest.mark.fork
def test_adding_streams_and_consumers_leaves_existing_outputs_unchanged():
    base = build_toy_system()
    _, tr0 = base.run(base.start(), N, record=["truth.x", "sensor.y"])

    ps = default_params()
    gust = _Gust("gust", ps["counter"])
    truth = ToySpringDamper("truth", ps["truth"])
    sensor = ToySensor("sensor", ps["sensor"], identity={"sensor": "pos_a"})
    second = ToySensor("sensor_b", ps["sensor"].replace(phase=777), identity={"sensor": "pos_b"})
    s = System(
        [gust, truth, sensor, second],
        [
            Connection("truth.x", "sensor.x_now"),
            Connection("truth.x", "sensor.x_prev", delayed=True, note="previous frame"),
            Connection("truth.x", "sensor_b.x_now"),
            Connection("truth.x", "sensor_b.x_prev", delayed=True, note="previous frame"),
        ],
        rng=RngService(base.rng.root, StreamRegistry()),
        identity=base.identity,
    )
    _w, tr1 = s.run(s.start(), N, record=["truth.x", "sensor.y", "sensor_b.y", "gust.g"])
    assert np.array_equal(tr1.ports["truth.x"], tr0.ports["truth.x"])
    assert np.array_equal(tr1.ports["sensor.y"], tr0.ports["sensor.y"])
    assert not np.array_equal(tr1.ports["sensor_b.y"], tr0.ports["sensor.y"])
    assert len(s.rng.registry) == 3 and s.config_hash != base.config_hash
