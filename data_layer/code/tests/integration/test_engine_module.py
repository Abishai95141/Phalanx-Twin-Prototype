"""M07 as a core module in a System: validation mode, step == block, snapshot/restore, keyed draws (A7,
AD-36).

Samples: 1,440 ticks (6 s) per configuration, n_engines 1 and 2; snapshot at k = 1201 (not a multiple of the
60 Hz FADEC frame nor of the block length) with an AB light-off attempt pending.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import StateSchema
from phalanx.core.time import RG_240
from phalanx.engine.design import build_engine_model
from phalanx.engine.layout import I_NAB, U_NAMES
from phalanx.engine.module import EngineModule
from phalanx.engine.ports import ports

N = 1440


class EngineInputsFixture(ModuleBase):
    """TEST FIXTURE: time-dependent engine inputs (pure function of the tick time; not M08/M03/M09)."""

    version = "0"
    rate = RG_240
    state_schema = StateSchema("engine_inputs_fixture", 1, ())

    def __init__(self, id: str, eng: EngineModule, ab_on_ns: int = 2 * 10**9, quiet: bool = False) -> None:
        ins, _, _ = ports(eng.n_engines)
        self.ports_out = tuple(Port(p.name, p.unit, p.dtype, p.shape) for p in ins)
        super().__init__(id, ParamSet("engine_inputs_fixture", {}))
        self.e = eng.n_engines
        self.u = eng._init_u
        self.ab_on = ab_on_ns
        self.quiet = quiet  # quiet: exactly the module's initial inputs (no disturbance, bleed, PTO, AB)

    def init(self, params, keys):
        return {}

    def _vals(self, t: np.ndarray) -> dict[str, np.ndarray]:
        n, e = t.size, self.e
        ts = t.astype(np.float64) * 1e-9
        w = np.zeros((n, e, 5))
        w[:, 0, 0] = 0.005 * np.sin(2 * np.pi * 1.3 * ts)
        if e > 1:
            w[:, 1, 3] = 0.004 * np.cos(2 * np.pi * 0.7 * ts)
        ab = (t >= self.ab_on).astype(np.int64)
        k = 0.0 if self.quiet else 1.0
        w = w * k
        ab = ab * int(k)
        return {
            "wf_cmd": np.full((n, e), self.u[0]),
            "wf_ab_cmd": np.where(ab[:, None] == 1, 0.6, 0.0) * np.ones((n, e)),
            "a8_cmd": np.full((n, e), self.u[2]),
            "vg_cmd": np.broadcast_to(self.u[3:5], (n, e, 2)).copy(),
            "ignition": np.zeros((n, e), np.int64),
            "ab_enable": np.repeat(ab[:, None], e, axis=1),
            "t_s": np.full(n, 288.15),
            "p_s": np.full(n, 101325.0),
            "q_spec": np.full(n, 0.002 * k),
            "mach": np.zeros(n),
            "w_engine": w,
            "bleed_extract": np.full((n, e), 0.3 * k),
            "pto_power": np.full((n, e), 20e3 * k),
            "fuel_inlet_t": np.full((n, e), self.u[U_NAMES.index("t_fuel")]),
            "health": np.zeros((n, e, 10)),
        }

    def initial_outputs(self, state):
        return {k: v[0] for k, v in self._vals(np.array([0], np.int64)).items()}

    def step_block(self, state, inputs, t, dt):
        return {}, self._vals(np.asarray(t, np.int64))

    def step(self, state, inputs, t, dt):
        return {}, {k: v[0] for k, v in self._vals(np.array([t], np.int64)).items()}


@pytest.fixture(scope="module")
def model():
    return build_engine_model()


def _system(model, n_engines=1, *, validate=False, block_len=240, sortie=1, compiled=True, quiet=False):
    eng = EngineModule("eng", model, n_engines=n_engines, compiled=compiled)
    fx = EngineInputsFixture("cmd", eng, quiet=quiet)
    conns = [Connection(f"cmd.{p.name}", f"eng.{p.name}") for p in eng.ports_in]
    return System(
        [fx, eng], conns, rng=RngService(0x0707, StreamRegistry()),
        identity=KeyPath.of(scenario="w13a", tail="T1", sortie=sortie), validate=validate,
        purity_check=validate, block_len=block_len,
    )  # fmt: skip


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("n_engines", [1, 2])
def test_validation_mode_and_step_equals_block(model, n_engines):
    """AD-36: step_block == repeated step bitwise (block lengths 7 and 240 vs per-step), and validation mode
    (read-only state/inputs, schema, units, finiteness, purity double-calls) gives the identical trace."""
    ref = _system(model, n_engines)
    _, t_ref = ref.run(ref.start(), N, mode="step", record=ref.output_ports())
    for bl in (7, 240):
        s = _system(model, n_engines, block_len=bl)
        _, t = s.run(s.start(), N, mode="block", record=s.output_ports())
        assert t.digest() == t_ref.digest(), bl
    v = _system(model, n_engines, validate=True)
    _, tv = v.run(v.start(), 480, mode="block", record=v.output_ports())
    _, t480 = ref.run(ref.start(), 480, mode="step", record=ref.output_ports())
    assert tv.digest() == t480.digest()
    ab = t_ref.ports["eng.ab_state"]
    assert ab.max() == 2  # the AB lit during the run (light-off draw consumed)


@pytest.mark.integration
@pytest.mark.fork
def test_snapshot_restore_continues_bitwise(model):
    """A7: snapshot at k = 1201 with an AB attempt pending, restore into a fresh system, continue: identical
    final snapshot to an uninterrupted run (state, held ports, RNG identity)."""
    s_ref = _system(model, 2)
    w_ref, _ = s_ref.run(s_ref.start(), N)
    s1 = _system(model, 2)
    w1, _ = s1.run(s1.start(), 1201)
    s2 = _system(model, 2, block_len=7)
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), N - 1201)
    assert snapshot(s2, w2) == snapshot(s_ref, w_ref)


@pytest.mark.integration
def test_lightoff_draws_are_keyed_by_identity(model):
    """AD-37: the light-off delay draw is keyed (scenario, tail, serial, sortie) and indexed by the attempt
    counter in state: same identity -> same delays; another sortie -> different delays; the two engines of
    one aircraft draw independently (different serials)."""

    def delays(sortie):
        s = _system(model, 2, sortie=sortie)
        w, _ = s.run(s.start(), 600)
        st = w.states["eng"]
        assert np.all(st["i"][:, I_NAB] == 1)
        return st["f"][:, 17].copy()  # ab_delay

    a, b, c = delays(1), delays(1), delays(2)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert a[0] != a[1]


@pytest.mark.integration
def test_initial_outputs_match_first_steady_step(model):
    """Held ports at t0 equal the module's own outputs after one step at the steady initial point (the
    fixture feeds exactly the initial inputs): the module starts in equilibrium, to 1e-9 relative."""
    s = _system(model, 1, quiet=True)
    w = s.start()
    eng = s.modules["eng"]
    io = eng.initial_outputs(w.states["eng"])
    _, tr = s.run(w, 1, mode="step", record=s.output_ports())
    for k in ("n1", "n2", "t5", "ps3", "thrust"):
        assert abs(io[k][0] - tr.ports[f"eng.{k}"][0][0]) < 1e-9 * abs(io[k][0]), k
