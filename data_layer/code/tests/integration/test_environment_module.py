"""W1.1 A7 for M03: compiled kernel == NumPy reference bitwise (top-level ``py_func`` in process, and the
whole call tree under ``NUMBA_DISABLE_JIT=1`` in a subprocess); ``step`` == ``step_block`` for block lengths
1/7/1024; snapshot round trip mid-run; validation mode (read-only state, unit and finiteness checks, purity
double-calls). Global-RNG use is caught by the tests/conftest.py guard.

Sample: 2,400 ticks (10 s) of a TEST FIXTURE flight profile (climb through the shear layer and the
1000-2000 ft
turbulence transition, take-off phase code for Category C), n_engines = 2, gusts active.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.core.module import ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.snapshot import restore, snapshot
from phalanx.core.state import StateSchema
from phalanx.core.time import NS_PER_S, RG_240
from phalanx.environment.climatology import Ambient
from phalanx.environment.config import load_env_config
from phalanx.environment.module import EnvironmentModule, Gust

N = 2400
SRC = Path(__file__).resolve().parents[2] / "src"


class FlightFixture(ModuleBase):
    """TEST FIXTURE (not a model): a scripted altitude/airspeed/phase history feeding M03's inputs."""

    version = "0"
    rate = RG_240
    ports_out = (Port("alt", "m"), Port("hag", "m"), Port("tas", "m/s"), Port("phase", "1", "<i8"))
    state_schema = StateSchema("fixture.flight", 1, ())

    def __init__(self, id="af"):
        super().__init__(id, ParamSet("fixture", {}))

    def init(self, params, keys):
        return {}

    @staticmethod
    def _at(t):
        s = np.asarray(t, dtype=np.int64) / NS_PER_S
        alt = 380.0 + 70.0 * s**1.5
        tas = 60.0 + 12.0 * s
        phase = np.where(s < 4.0, 3, 4).astype(np.int64)
        return alt, tas, phase

    def initial_outputs(self, state):
        a, v, p = self._at(np.array([0]))
        return {
            "alt": np.array(a[0]),
            "hag": np.array(a[0] - 229.0),
            "tas": np.array(v[0]),
            "phase": np.array(p[0]),
        }

    def step_block(self, state, inputs, t, dt):
        a, v, p = self._at(np.asarray(t) + 1_000_000_000 // 240)
        return {}, {"alt": a, "hag": a - 229.0, "tas": v, "phase": p}

    def step(self, state, inputs, t, dt):
        _, o = self.step_block(state, inputs, np.array([t], np.int64), dt)
        return {}, {k: np.array(v[0]) for k, v in o.items()}


AMB = Ambient(42165, 229.0, 224.0, 313.0, 97430.0, 1330.0, 6.0, 1.2, 2, 0.0)
GUSTS = (Gust(2.0, 2, 4.0, 60.0), Gust(5.5, 0, -3.0, 120.0))


def build(compiled=True, block_len=1024, validate=False, root=0xE7, ledger=None):
    cfg = load_env_config()
    env = EnvironmentModule(
        "env",
        cfg,
        n_engines=2,
        engine_serials=("IN20-A", "IN20-B"),
        ambient=AMB,
        gusts=GUSTS,
        compiled=compiled,
    )
    af = FlightFixture()
    return System(
        [env, af],
        [
            Connection(
                "af.alt", "env.alt", delayed=True, note="airframe -> environment one-frame delay (§8)"
            ),
            Connection(
                "af.tas", "env.tas", delayed=True, note="airframe -> environment one-frame delay (§8)"
            ),
            Connection("af.phase", "env.phase", delayed=True, note="fixture stands in for scenario.phase"),
            Connection(
                "af.hag", "env.hag", delayed=True, note="airframe -> environment one-frame delay (§8)"
            ),
        ],
        rng=RngService(root, StreamRegistry(), ledger=ledger),
        identity=KeyPath.of(scenario="W11", tail="KH2011", sortie="KH2011-20261014-01"),
        block_len=block_len,
        validate=validate,
        purity_check=validate,
    )


def _digest(trace) -> str:
    h = hashlib.blake2b(digest_size=16)
    for k in sorted(trace.ports):
        h.update(k.encode())
        h.update(np.ascontiguousarray(trace.ports[k]).tobytes())
    return h.hexdigest()


@pytest.fixture(scope="module")
def reference_trace():
    s = build(compiled=False)
    _, tr = s.run(s.start(), N, mode="step", record=s.output_ports())
    return tr


@pytest.mark.integration
@pytest.mark.determinism
@pytest.mark.parametrize("block_len", [1, 7, 1024])
def test_compiled_block_equals_reference_step_bitwise(reference_trace, block_len):
    s = build(compiled=True, block_len=block_len)
    _, tr = s.run(s.start(), N, mode="block", record=s.output_ports())
    assert tr.digest() == reference_trace.digest()
    # the run exercised every branch: shear layer, Category C, gusts, turbulence transition band
    w = tr.ports["env.turb_vel_body"]
    assert np.all(np.isfinite(w)) and np.std(w[:, 2]) > 0
    assert np.ptp(tr.ports["env.p_s"]) > 1000.0


@pytest.mark.integration
@pytest.mark.determinism
def test_whole_call_tree_without_jit_matches_compiled():
    """NUMBA_DISABLE_JIT=1 runs every helper as plain Python (the full NumPy reference)."""
    s = build(compiled=True)
    _, tr = s.run(s.start(), 480, mode="block", record=s.output_ports())
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]);"
        "import test_environment_module as t;"
        "s = t.build(compiled=True);"
        "_, tr = s.run(s.start(), 480, mode='block', record=s.output_ports());"
        "print(t._digest(tr))"
    )
    env = dict(os.environ, NUMBA_DISABLE_JIT="1")
    out = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SRC), str(Path(__file__).parent)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == _digest(tr)


@pytest.mark.fork
def test_snapshot_round_trip_mid_run():
    ref = build()
    w_ref, _ = ref.run(ref.start(), N)
    s1 = build()
    w1, _ = s1.run(s1.start(), 1201)
    s2 = build()
    w2, _ = s2.run(restore(s2, snapshot(s1, w1)), N - 1201)
    assert snapshot(s2, w2) == snapshot(ref, w_ref)


@pytest.mark.integration
def test_validation_mode_equals_production(reference_trace):
    s = build(validate=True)
    _, tr = s.run(s.start(), 480, mode="block", record=s.output_ports())
    ref = {k: v[:480] for k, v in reference_trace.ports.items()}
    for k, v in tr.ports.items():
        assert np.array_equal(v, ref[k]), k


@pytest.mark.integration
def test_outputs_are_physical():
    s = build()
    _, tr = s.run(s.start(), N, record=s.output_ports())
    p = tr.ports
    t, ps, rho, a = p["env.t_s"], p["env.p_s"], p["env.rho"], p["env.a_sound"]
    q = p["env.q_spec"]
    r_moist = ps / (rho * t)
    assert np.all((r_moist > 287.0) & (r_moist < 287.0 * 1.02))  # dry gas constant times (1 + 0.608 q)
    assert np.all(np.diff(p["af.alt"]) > 0) and np.all(np.diff(ps) < 0)  # climbing: pressure falls
    assert np.all((q > 0) & (q < 0.02)) and np.all(a > 300)
    assert p["env.w_engine"].shape == (N, 2, 5) and p["env.w_hyd"].shape == (N, 2)
    assert np.std(p["env.w_engine"][:, :, 4]) > 0  # fan_face column (AD-46) is driven
    assert not np.array_equal(p["env.w_engine"][:, 0, 0], p["env.w_engine"][:, 1, 0])  # engines differ
