"""W2.4a U3: per-engine FADEC lane path in M12/M13 for n_engines > 1 (E1 verifier report §4 U3).

M08 expects lane buffers of shape (capacity, n_engines); before W2.4a the M12/M13 lanes had no engine axis.
Now
M12 builds one sensor instance per engine for every channel whose truth input carries the engine axis
(``ENG.N1.A:E1`` ... ``:En``, reading element k), and M13's ``LaneAcquisition`` groups the instances of one
dictionary lane into a (capacity, n_engines) port bound as ``lane.<channel_id>``. Checks:

- every M08 lane binding resolves to an M13 lane producer with the same shape, unit and clock, for 1, 2 and 4
  engines (ENG.AB_LIT stays the tracked W2.1 exception);
- each engine's lane column is that engine's sensor reading (scripted per-engine truth), with independent
  per-instance noise (identical truth on every engine still gives different noisy N1 lanes);
- step == step_block bitwise and a fresh run reproduces the digest (determinism);
- the Tejas e = 1 path is bitwise unchanged against the pre-W2.4a source (golden digest, provenance below);
- negative controls: an engine instance set that does not cover every engine, and a non-zero engine index on
an
  engine-axis channel, are refused.

Sample: 2 s (480 truth steps, about 120 FADEC frames) of scripted truth per configuration: the smallest window
with every lane sampled many times and several noise draws per instance.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.module import LaneAcquisition, lane_port
from phalanx.acquisition.ports import lane_modules
from phalanx.core.module import ContractError, ModuleBase, ParamSet, Port
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import StateSchema
from phalanx.core.time import RG_240
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set
from phalanx.fadec.ports import LANE_PORTS, lane_shape
from phalanx.fadec.ports import ports as fadec_ports
from phalanx.sensors.config import (
    build_sensor_config,
    dictionary_id,
    engine_of,
    instance_id,
)
from phalanx.sensors.module import BIAS_PORT, SensorPhysics

pytestmark = pytest.mark.integration
LANES = tuple(cid for _n, cid, _u in LANE_PORTS if cid != "ENG.AB_LIT")
N = 480
#: digest of the e = 1 lane outputs of `_run(1)` computed with the pre-W2.4a source **after the W2.2
#: dictionary 0.1.2 migration** (wp/w2.2-datapath 3e697bf, extracted with `git archive 3e697bf src configs
#: docs/assumptions.md` and run with the same script): the instance machinery leaves the Tejas lane path
#: unchanged bitwise. The pre-W2.2 digest (main 43831ed / aebf19a: f41c75650b15...) differs only in the
#: eight converter-step lanes (N1, N2, PS3, T1 A/B), which W2.2 quantises at their dictionary converter_step
#: with the same EU noise (A-W1.6-22); every other lane port is bitwise identical (merge of main into W2.2,
#: 2026-10-15)
BASE_E1_DIGEST = "10fd5dee77c8562eab8af1a6f56b45cc4adc300ef24d5517fd2aee84b0742ae1"


class ScriptedEngines(ModuleBase):
    """TEST FIXTURE (module boundary): per-engine engine truth = engine-1 script x (1 + 0.004 k) for engine k,
    plus a zero sensor bias and the flight phase. Not M07."""

    version = "0"
    rate = RG_240
    state_schema = StateSchema("fixture.scripted_engines", 1, ())

    def __init__(self, id: str, cfg, n_engines: int, same: bool = False) -> None:
        self.cfg = cfg
        self.e = n_engines
        self.same = same
        self.ports_out = (
            *(Port(s.port, s.unit, "<f8", s.shape) for s in cfg.inputs),
            Port("bias", "1", "<f8", (cfg.n_ch,)),
            Port("phase", "1", "<i8", ()),
        )
        super().__init__(id, ParamSet("fixture.scripted_engines", {}))

    def init(self, params, keys):
        return {}

    def _vals(self, t: np.ndarray):
        ts = t.astype(np.float64) * 1e-9
        n = ts.size
        base = {
            "eng.n1": 1200.0 * (1.0 + 0.002 * np.sin(2.1 * ts)),
            "eng.n2": 1500.0 * (1.0 + 0.002 * np.sin(1.7 * ts)),
            "eng.t2": np.full(n, 288.15),
            "eng.ps3": 1.2e6 * (1.0 + 0.004 * np.sin(1.3 * ts)),
            "eng.t25": np.full(n, 400.0),
            "eng.t5": 950.0 + 3.0 * np.sin(0.9 * ts),
            "eng.w2": np.full(n, 60.0),
        }
        out = {}
        for s in self.cfg.inputs:
            v = base[s.signal]
            if s.shape:
                k = np.arange(s.shape[0])
                f = np.ones(s.shape[0]) if self.same else 1.0 + 0.004 * k
                out[s.port] = v[:, None] * f[None, :]
            else:
                out[s.port] = v
        out["bias"] = np.zeros((n, self.cfg.n_ch))
        out["phase"] = np.full(n, 5, dtype=np.int64)
        return out

    def initial_outputs(self, state):
        return {k: v[0] for k, v in self._vals(np.array([0], np.int64)).items()}

    def step_block(self, state, inputs, t, dt):
        return {}, self._vals(np.asarray(t, np.int64))

    def step(self, state, inputs, t, dt):
        return {}, {k: v[0] for k, v in self._vals(np.array([t], np.int64)).items()}


def _system(n_engines: int, *, same: bool = False):
    d = load_dictionary()
    cfg = build_sensor_config(d, n_engines=n_engines, channels=LANES)
    lanes = cfg.channels
    acq_cfg = build_acquisition_config(d, lanes, sensor_channels=cfg.channels)
    truth = ScriptedEngines("truth", cfg, n_engines, same=same)
    sens = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    acq = LaneAcquisition("acq", load_param_set("M13", "noise_n2"), cfg, acq_cfg, d)
    conns = [Connection(f"truth.{s.port}", f"sens.{s.port}") for s in cfg.inputs]
    conns.append(Connection("truth.bias", f"sens.{BIAS_PORT}"))
    for p in acq.ports_in:
        conns.append(Connection("truth.phase" if p.name == "phase" else f"sens.{p.name}", f"acq.{p.name}"))
    from phalanx.acquisition.core import STREAMS
    from phalanx.sensors.module import FAULT_STREAM

    rng = RngService(0x2404A, StreamRegistry([*STREAMS, FAULT_STREAM]))
    ident = KeyPath.of(scenario="u3", tail="T687", sortie=1)
    return System([truth, sens, acq], conns, rng=rng, identity=ident, block_len=97), acq, cfg


def _run(n_engines: int, *, mode: str = "block", same: bool = False):
    syst, acq, cfg = _system(n_engines, same=same)
    rec = [f"acq.{p.name}" for p in acq.ports_out]
    _, trace = syst.run(syst.start(), N, mode=mode, record=rec)
    return {k: np.asarray(trace.ports[k]) for k in rec}, acq, cfg


def _digest(out: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(out):
        h.update(k.encode())
        h.update(np.ascontiguousarray(out[k]).tobytes())
    return h.hexdigest()


@pytest.mark.parametrize("n_engines", [1, 2, 4])
def test_every_m08_lane_has_an_m13_producer(n_engines):
    """U3: each `lane.<id>` M08 binds is a value port of M13's FADEC lane module with M08's exact shape, the
    channel's SI unit and the shared FADEC clock; ENG.AB_LIT included since W2.2 (the M12 UV flame
    detector)."""
    fad_in, _, fad_b = fadec_ports(n_engines, autothrottle=True)
    acq = lane_modules(n_engines)["FADEC"]
    prod = {p.name: p for p in acq.ports_out}
    lb = acq.lane_bindings()
    missing = []
    for p in fad_in:
        sig = fad_b[p.name]
        if not sig.startswith("lane."):
            continue
        port = lb.get(sig)
        if port is None:
            missing.append(sig)
            continue
        q = prod[port]
        assert tuple(q.shape) == tuple(p.shape) == lane_shape(n_engines), (sig, q.shape, p.shape)
        assert q.unit == p.unit and q.rate == p.rate, sig
    assert missing == []


def test_engine_columns_follow_each_engines_truth():
    """Lane column k is engine k's reading: with engine k's truth scaled by (1 + 0.004 k), the mean T5 and N2
    lane values rise engine by engine by the scripted amount (within quantisation)."""
    out, _acq, _cfg = _run(4)
    for cid, scale_ref in (("ENG.N2.A", 1500.0), ("ENG.T5.HARNESS_A", None)):
        v = out[f"acq.{lane_port(cid)}"]
        n = out[f"acq.{lane_port(cid)}_n"]
        assert v.shape == (N, 1, 4)
        sel = n[:, None] == 1
        m = np.array([v[:, 0, k][sel[:, 0]][60:].mean() for k in range(4)])
        rel = m / m[0] - 1.0
        if scale_ref is not None:
            assert np.allclose(rel, 0.004 * np.arange(4), atol=2e-4), rel
        else:
            assert np.all(np.diff(m) > 2.0), m  # 0.4 % of ~950 K per engine


def test_instances_draw_independent_noise():
    """Identical truth on all four engines: the noisy N1 lanes (0.61 native steps of keyed AR(1) noise,
    A-W1.6-22) still differ between engines (independent per-instance streams), while the T5 harness lanes,
    whose idiosyncratic noise is zero (MEASURED, A-W1.6-23), agree exactly."""
    out, _, _ = _run(4, same=True)
    n1 = out[f"acq.{lane_port('ENG.N1.A')}"][:, 0, :]
    assert not np.array_equal(n1[:, 0], n1[:, 1]) and not np.array_equal(n1[:, 2], n1[:, 3])
    t5 = out[f"acq.{lane_port('ENG.T5.HARNESS_A')}"][:, 0, :]
    assert np.array_equal(t5[:, 0], t5[:, 3]) and np.array_equal(t5[:, 1], t5[:, 2])


@pytest.mark.determinism
def test_step_equals_block_and_fresh_run_reproduces():
    a, _, _ = _run(4, mode="block")
    b, _, _ = _run(4, mode="step")
    for k in a:
        assert np.array_equal(a[k], b[k]), k
    assert _digest(a) == _digest(_run(4)[0])


@pytest.mark.determinism
def test_tejas_single_engine_lane_path_unchanged():
    """The e = 1 lane outputs equal, bitwise, those of the pre-W2.4a source (digest computed on main 43831ed
    with the same script); the instance machinery is inactive for one engine (plain channel ids)."""
    out, _acq, cfg = _run(1)
    assert all(engine_of(c) < 0 for c in cfg.channels)
    assert all(out[f"acq.{lane_port(cid)}"].shape == (N, 1) for cid in LANES)
    assert _digest(out) == BASE_E1_DIGEST


def test_instance_ids_round_trip_and_negative_controls():
    assert instance_id("ENG.N1.A", 0) == "ENG.N1.A:E1"
    assert dictionary_id("ENG.N1.A:E3") == "ENG.N1.A" and engine_of("ENG.N1.A:E3") == 2
    assert dictionary_id("ENG.N1.A") == "ENG.N1.A" and engine_of("ENG.N1.A") == -1
    d = load_dictionary()
    cfg = build_sensor_config(d, n_engines=4, channels=LANES)
    # an instance set that does not cover every engine is refused by the lane module
    part = tuple(c for c in cfg.channels if engine_of(c) != 3)
    acq_cfg = build_acquisition_config(d, part, sensor_channels=cfg.channels)
    with pytest.raises(ContractError, match="do not cover"):
        LaneAcquisition("acq", load_param_set("M13", "noise_n2"), cfg, acq_cfg, d)
    # a non-zero engine index on an engine-axis channel has no per-engine meaning
    from phalanx.dictionary.params import params_dir
    from phalanx.dictionary.yamlio import load_yaml

    cmap = load_yaml(params_dir("tejas") / "M12" / "channel_map.yaml")
    bad = dict(cmap)
    bad["channels"] = dict(cmap["channels"])
    bad["channels"]["ENG.N1.A"] = {**cmap["channels"]["ENG.N1.A"], "index": 1}
    with pytest.raises(ContractError, match="engine index"):
        build_sensor_config(d, n_engines=2, channels=("ENG.N1.A",), channel_map=bad)


@pytest.mark.parametrize("n_engines", [1, 4])
def test_m10_sensor_bias_index_follows_m12_instances(n_engines):
    """M10's ``health.sensor_bias`` index map is M12's channel list at the same engine count (AD-42): one
    entry per engine instance, in the dictionary channel's SI unit; its published size equals M12's input."""
    from phalanx.health.layout import sensor_bias_channels
    from phalanx.health.ports import ports as health_ports
    from phalanx.sensors.ports import ports as sensor_ports

    d = load_dictionary()
    cfg = build_sensor_config(d, n_engines=n_engines)
    bc = sensor_bias_channels(d, cfg)
    assert tuple(b.channel_id for b in bc) == cfg.bias_index()
    assert all(b.si_units == u for b, u in zip(bc, cfg.si_units, strict=True))
    out = {p.name: p for p in health_ports(n_engines)[1]}
    ins = {p.name: p for p in sensor_ports(n_engines)[0]}
    assert out["sensor_bias"].shape == ins[BIAS_PORT].shape == (len(cfg.channels),)
    n_inst = sum(engine_of(c) >= 0 for c in cfg.channels)
    assert (n_inst > 0) == (n_engines > 1)  # instances exist only with more than one engine
