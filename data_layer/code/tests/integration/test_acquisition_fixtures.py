"""TEST FIXTURE (not a model, never imported by src/): a scripted truth source and an M12 + M13 chain builder.

``ScriptedTruth`` publishes every truth signal the M12 configuration reads, as deterministic functions of time
(steady values with slow sinusoids), plus ``health.sensor_bias`` and ``scenario.phase`` stand-ins. It replaces
M03-M10 at the module boundary so the observation chain can be tested alone (W1 rule: fixtures at the
boundary, labelled, under tests/). ``build_chain`` wires ScriptedTruth -> SensorPhysics -> LaneAcquisition
(FADEC and DFCC lanes) in a core ``System``.

This file holds no tests; other W1.6 test files load it with ``load_fixture()`` (by path, so it works from any
test directory).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import STREAMS
from phalanx.acquisition.module import LaneAcquisition, lane_channels, lane_port
from phalanx.core.module import ModuleBase, Param, ParamSet, Port
from phalanx.core.rng import DrawLedger, KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.core.state import StateSchema
from phalanx.core.time import RG_240, latest_truth_step, truth_step_time_ns
from phalanx.dictionary.params import load_param_set
from phalanx.sensors.config import SensorConfig
from phalanx.sensors.module import BIAS_PORT, SensorPhysics

IDENTITY = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")
ROOT = 0x5EED_0016

#: fixture truth: value or f(t_s) per catalogue signal (SI); anything not listed is 0
DEFAULT_SCRIPT: dict[str, Callable[[float], np.ndarray | float] | float] = {
    "eng.n1": lambda t: 1300.0 + 30.0 * np.sin(0.7 * t),
    "eng.n2": lambda t: 1700.0 + 20.0 * np.sin(0.5 * t),
    "eng.t2": 288.15,
    "eng.w2": 50.0,
    "eng.ps3": 2.0e6,
    "eng.t25": 400.0,
    "eng.t5": lambda t: 900.0 + 10.0 * np.sin(0.3 * t),
    "eng.p5": 2.0e5,
    "eng.oil_p": 3.0e5,
    "eng.oil_t": 350.0,
    "eng.wf": lambda t: 0.5 + 0.05 * np.sin(t),
    "eng.wf_ab": 0.0,
    "eng.a8": 0.2,
    "eng.vg_vsv": 0.1,
    "eng.vg_igv": 0.2,
    "pilot.pla": 0.8,
    "env.p_s": 50000.0,
    "env.t_s": 250.0,
    "env.rho": 0.7,
    "af.mach": 0.8,
    "af.tas": 250.0,
    "af.nz": 1.0,
    "af.alpha": lambda t: 0.05 + 0.01 * np.sin(2.0 * t),
    "af.beta": 0.0,
    "af.omega_body": lambda t: np.array([0.02 * np.sin(1.3 * t), 0.01, 0.0]),
    "af.f_spec_body": np.array([0.0, 0.0, -9.80665]),
    "fcs.surf_pos": lambda t: np.full(13, 0.02 * np.sin(1.1 * t)),
    "pilot.stick_pitch": 0.1,
    "pilot.stick_roll": 0.0,
    "pilot.pedal": 0.0,
    "util.hyd_p": np.full(2, 2.8e7),
    "util.hyd_t": np.full(2, 320.0),
    "util.fuel_mass": np.full(8, 300.0),
    "util.bus_v": np.array([28.0, 28.0, 28.0, 115.0]),  # M09 map: DC main/ess/emerg (28 V), AC main (V rms)
    "af.wheel_speed": np.zeros(2),
}


class ScriptedTruth(ModuleBase):
    """TEST FIXTURE: scripted truth signals for M12's inputs (outputs at the END of each step)."""

    version = "fixture"
    rate = RG_240
    state_schema = StateSchema("fixture.truth", 1, ())

    def __init__(
        self,
        id: str,
        cfg: SensorConfig,
        script: Mapping[str, object] | None = None,
        *,
        phase: int = 5,
        bias: np.ndarray | None = None,
    ) -> None:
        self.cfg = cfg
        self.script = {**DEFAULT_SCRIPT, **(script or {})}
        self.phase = int(phase)
        self.bias = np.zeros(cfg.n_ch) if bias is None else np.asarray(bias, dtype=np.float64)
        self.ports_out = (
            *(Port(s.port, s.unit, s.dtype, s.shape) for s in cfg.inputs),
            Port("bias", "1", "<f8", (cfg.n_ch,)),
            Port("phase", "1", "<i8", ()),
        )
        super().__init__(id, ParamSet("fixture", {"a": Param(1.0, "1", "ASSUMPTION", "TEST FIXTURE")}))

    def init(self, params, keys):
        return {}

    def values(self, t_ns: int) -> dict[str, np.ndarray]:
        ts = t_ns / 1e9
        out = {}
        for s in self.cfg.inputs:
            v = self.script.get(s.signal, 0.0)
            v = v(ts) if callable(v) else v
            a = np.broadcast_to(np.asarray(v, dtype=np.float64), s.shape).astype(s.dtype)  # e.g. eng.ab_state
            out[s.port] = a
        out["bias"] = self.bias.copy()
        out["phase"] = np.array(self.phase, dtype=np.int64)
        return out

    def initial_outputs(self, state):
        return self.values(0)

    def step(self, state, inputs, t, dt):
        return {}, self.values(truth_step_time_ns(latest_truth_step(t) + 1))


def build_chain(
    d,
    cfg: SensorConfig,
    *,
    controllers=("FADEC", "DFCC"),
    script=None,
    phase: int = 5,
    bias=None,
    compiled: bool = True,
    root: int = ROOT,
    identity: KeyPath = IDENTITY,
    ledger: DrawLedger | None = None,
    validate: bool = False,
    acq_params=None,
):
    """System [truth -> sens -> acq_<controller>...]; returns (system, rng, modules)."""
    truth = ScriptedTruth("truth", cfg, script, phase=phase, bias=bias)
    sens = SensorPhysics("sens", load_param_set("M12", "constants"), cfg, compiled=compiled)
    mods = {"truth": truth, "sens": sens}
    conns = [Connection(f"truth.{s.port}", f"sens.{s.port}") for s in cfg.inputs]
    conns.append(Connection("truth.bias", f"sens.{BIAS_PORT}"))
    for ctl in controllers:
        lanes = lane_channels(d, cfg, ctl)
        acq = build_acquisition_config(d, lanes, sensor_channels=cfg.channels, params=acq_params)
        m = LaneAcquisition(
            f"acq_{ctl.lower()}", load_param_set("M13", "noise_n2"), cfg, acq, d, compiled=compiled
        )
        mods[m.id] = m
        for p in m.ports_in:
            src = "truth.phase" if p.name == "phase" else f"sens.{p.name}"
            conns.append(Connection(src, f"{m.id}.{p.name}"))
    # the recording entry point draws from the acquisition streams too: declare them up front (W2.1 rule)
    rng = RngService(root, StreamRegistry(list(STREAMS)), ledger=ledger)
    system = System(
        list(mods.values()), conns, rng=rng, identity=identity, validate=validate, purity_check=validate
    )
    return system, rng, mods


def sensor_ports(mods) -> list[str]:
    return [f"sens.{p.name}" for p in mods["sens"].ports_out]


def lane_record_ports(m: LaneAcquisition) -> list[str]:
    return [f"{m.id}.{lane_port(c)}{s}" for c in m.acq.channels for s in ("", "_t", "_n", "_first", "_q")]


def lane_samples(trace_ports, module_id: str, cid: str) -> dict[int, tuple[float, int, int]]:
    """{absolute sample index: (SI value, t_sample ns, flags)} of one lane from a trace."""
    p = f"{module_id}.{lane_port(cid)}"
    v, t, n, first, q = (trace_ports[p + s] for s in ("", "_t", "_n", "_first", "_q"))
    out = {}
    for k in range(n.shape[0]):
        for s in range(int(n[k])):
            out[int(first[k]) + s] = (float(v[k, s]), int(t[k, s]), int(q[k, s]))
    return out
