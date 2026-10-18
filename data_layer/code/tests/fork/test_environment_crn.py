"""W1.1 A4 for M03: streams bitwise reproducible per identity key; forks with different orders share the
exogenous draws (CRN audit, invariant I8); a re-fitted engine brings its own serial's stream and leaves the
other engine's draws untouched.

Sample: the integration fixture flight; parent run 1,200 ticks (5 s), suffix 1,200 ticks; every stream is
consumed 1,200 times in the suffix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamRegistry, crn_audit
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.time import truth_step_time_ns
from phalanx.environment.climatology import Ambient
from phalanx.environment.config import load_env_config
from phalanx.environment.module import PLAN_EVENT, EnvironmentModule

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from test_environment_module import AMB, GUSTS, FlightFixture

K, N = 1200, 2400


def build(*, serials=("IN20-A", "IN20-B"), sortie="KH2011-20261014-01", tail="KH2011", ledger=None):
    env = EnvironmentModule(
        "env", load_env_config(), n_engines=2, engine_serials=serials, ambient=AMB, gusts=GUSTS
    )
    return System(
        [env, FlightFixture()],
        [
            Connection("af.alt", "env.alt", delayed=True, note="airframe -> environment one-frame delay"),
            Connection("af.hag", "env.hag", delayed=True, note="airframe -> environment one-frame delay"),
            Connection("af.tas", "env.tas", delayed=True, note="airframe -> environment one-frame delay"),
            Connection("af.phase", "env.phase", delayed=True, note="fixture stands in for scenario.phase"),
        ],
        rng=RngService(0xC4, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="W11", tail=tail, sortie=sortie),
    )


def _run(s, n=N):
    _, tr = s.run(s.start(), n, record=s.output_ports())
    return tr


@pytest.mark.fork
def test_same_identity_reproduces_bitwise_and_other_identities_differ():
    a, b = _run(build()), _run(build())
    assert a.digest() == b.digest()
    c = _run(build(sortie="KH2011-20261014-02"))
    d = _run(build(tail="KH2012"))
    for other in (c, d):
        assert not np.array_equal(a.ports["env.turb_vel_body"], other.ports["env.turb_vel_body"])
        assert not np.array_equal(a.ports["env.w_engine"], other.ports["env.w_engine"])
    # the deterministic atmosphere does not depend on the stream identity
    assert np.array_equal(a.ports["env.p_s"], c.ports["env.p_s"])


@pytest.mark.fork
def test_refitted_engine_brings_its_own_stream():
    """Engine 2 replaced (new serial): engine 1's unit-specific disturbances and the aircraft-common ones are
    unchanged; engine 2's unit-specific part changes."""
    cfg = load_env_config()
    a = _run(build())
    b = _run(build(serials=("IN20-A", "IN20-C")))
    env = EnvironmentModule("env", cfg, n_engines=2)
    bank = env.bank
    common = [i for i, it in enumerate(bank.instances) if it.unit < 0 and it.factor.group == 0]
    unit1 = [i for i, it in enumerate(bank.instances) if it.unit == 0 and it.factor.group == 0]
    wa, wb = a.ports["env.w_engine"], b.ports["env.w_engine"]
    # engine 1 identical (its unit factors + aircraft-common factors)
    assert np.array_equal(wa[:, 0, :], wb[:, 0, :]) and common and unit1
    assert not np.array_equal(wa[:, 1, :], wb[:, 1, :])
    assert np.array_equal(a.ports["env.turb_vel_body"], b.ports["env.turb_vel_body"])


def _branch(snap, orders=(), ledger=None):
    s = build(ledger=ledger)
    w = restore(s, snap)
    if orders:
        w = s.inject(w, list(orders))
    _w2, tr = s.run(w, N - K, record=s.output_ports())
    return tr


@pytest.mark.fork
def test_crn_audit_divergent_plan_order_shares_exogenous_draws():
    s = build()
    w, _ = s.run(s.start(), K)
    snap = snapshot(s, w)
    hot = Ambient(42165, 229.0, 224.0, 320.0, 97000.0, 2000.0, 9.0, 2.0, 3, 0.0)
    order = Event(truth_step_time_ns(K), PLAN_EVENT, "env", {"ambient": hot.vector()})
    la, lb = DrawLedger(), DrawLedger()
    ta = _branch(snap, (), la)
    tb = _branch(snap, (order,), lb)
    assert not np.array_equal(ta.ports["env.t_s"], tb.ports["env.t_s"])  # the order had an effect
    assert not np.array_equal(ta.ports["env.turb_vel_body"], tb.ports["env.turb_vel_body"])  # severe class
    rep = crn_audit(la, lb)
    assert rep.ok, rep
    names = {p.split("component=s:")[1].split("#")[0] for p in rep.identical}
    assert "gust" in names and {"f01", "f03", "f06"} <= names
    # identical suffixes give identical branches
    assert _branch(snap, (order,)).digest() == tb.digest()


@pytest.mark.fork
def test_negative_control_state_dependent_index_breaks_crn():
    """If M03 indexed draws by anything other than the absolute tick (here: shifted by one, as a
    state-dependent index would), the CRN audit fails: the audit can detect the defect it guards."""

    # direct check on the stream layer: shifting the index changes the consumed draw set
    la, lb = DrawLedger(), DrawLedger()
    for led, shift in ((la, 0), (lb, 1)):
        rng = RngService(0xC4, StreamRegistry(), ledger=led)
        env = EnvironmentModule("env", load_env_config(), n_engines=1)
        for d in env.streams:
            rng.registry.declare(d)
        env.bind(rng.scope(KeyPath.of(scenario="W11", tail="T", sortie="S")))
        env._noise(10 + shift, 5)
    assert not crn_audit(la, lb).ok
