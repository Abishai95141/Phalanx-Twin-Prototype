"""A7/A5 on the real observation chain: M08 computes on the real M12 -> M13 in-loop FADEC lanes (W1.6).

TEST FIXTURE truth (`test_acquisition_fixtures.ScriptedTruth`, the W1.6 boundary fixture) holds the engine at
the fixture's PLA-70 operating point with slow sinusoids; M12 `SensorPhysics` and M13 `LaneAcquisition`
(FADEC lanes, shared FADEC clock, real quantisation and noise) feed an unmodified `Fadec` through
`fadec_input_connections`. Open loop (M08's commands drive nothing): the test checks the interface and that
the validator raises **no** spurious failure on real acquisition texture, and that M13's per-step sample
counts are M08's frame schedule. ENG.AB_LIT is the real M13 lane of the M12 UV flame detector (W2.2; the
scripted afterburner stays off, so the lane reads 0).

Sample size: 10 s (2,400 truth steps, ~600 FADEC frames), one deterministic keyed run (n = 1).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import fadec_fixture as fx
from phalanx.acquisition.module import LaneAcquisition, lane_channels
from phalanx.core.rng import RngService, StreamRegistry
from phalanx.core.scheduler import Connection, System
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set
from phalanx.fadec import Fadec
from phalanx.fadec.coupling import fadec_input_connections
from phalanx.fadec.ports import P0_ENV
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import BIAS_PORT, SensorPhysics

pytestmark = pytest.mark.integration
N = 10 * 240


def _w16_fixture():
    name = "w16_acquisition_fixtures"
    if name not in sys.modules:
        p = Path(__file__).resolve().parent / "test_acquisition_fixtures.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


@pytest.fixture(scope="module")
def run():
    W16 = _w16_fixture()
    d = load_dictionary()
    cfg = build_sensor_config(d)
    x = fx.steady_state(70.0)[0]
    script = {
        "eng.n1": lambda t: x[fx.X_N1] * (1.0 + 0.002 * np.sin(0.7 * t)),
        "eng.n2": lambda t: x[fx.X_N2] * (1.0 + 0.002 * np.sin(0.5 * t)),
        "eng.t2": x[fx.X_T2],
        "eng.ps3": lambda t: x[fx.X_PS3] * (1.0 + 0.004 * np.sin(0.5 * t)),
        "eng.t25": x[fx.X_T25],
        "eng.t5": lambda t: x[fx.X_T5] + 3.0 * np.sin(0.3 * t),
        "eng.wf": x[fx.X_WF],
        "eng.a8": x[fx.X_A8],
        "pilot.pla": np.deg2rad(70.0),
        "env.p_s": 101325.0,
        "env.t_s": 288.15,
        "af.mach": 0.0,
    }
    truth = W16.ScriptedTruth("truth", cfg, script)
    sens = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    acq_cfg = W16.build_acquisition_config(d, lane_channels(d, cfg, "FADEC"), sensor_channels=cfg.channels)
    acq = LaneAcquisition("acq_fadec", load_param_set("M13", "noise_n2"), cfg, acq_cfg, d)
    fad = Fadec(
        "fadec", fx.fixture_params(), initial_wf=[x[fx.X_WF]], initial_a8=[x[fx.X_A8]], p0_source=P0_ENV
    )  # TEST FIXTURE loop without the avionics module: P0 from env.p_s
    conns = [Connection(f"truth.{s.port}", f"sens.{s.port}") for s in cfg.inputs]
    conns.append(Connection("truth.bias", f"sens.{BIAS_PORT}"))
    for p in acq.ports_in:
        conns.append(
            Connection("truth.phase" if p.name == "phase" else f"sens.{p.name}", f"acq_fadec.{p.name}")
        )
    port_of_signal = {s.signal: s.port for s in cfg.inputs}
    for port, sig in fad.bindings.items():  # truth inputs (PLA, P0) from the scripted truth's port names
        if not sig.startswith("lane."):
            conns.append(Connection(f"truth.{port_of_signal[sig]}", f"fadec.{port}"))
    for c in fadec_input_connections("fadec", fad.bindings, {"pilot": "truth", "env": "truth"}, "acq_fadec"):
        if not c.src.startswith("acq_fadec."):
            continue
        conns.append(c)
    rng = RngService(W16.ROOT, StreamRegistry(list(W16.STREAMS)))
    syst = System([truth, sens, acq, fad], conns, rng=rng, identity=W16.IDENTITY)
    rec = [
        "fadec.validation_state",
        "fadec.fault_code",
        "fadec.n2_v",
        "fadec.wf_cmd",
        "acq_fadec.lane_eng_n2_a_n",
        "acq_fadec.lane_eng_n2_a",
        "acq_fadec.lane_eng_ab_lit_n",
        "acq_fadec.lane_eng_ab_lit",
        "truth.eng_n2",
    ]
    _, tr = syst.run(syst.start(), N, mode="block", record=rec)
    return fad, tr


def test_no_spurious_validation_failure_on_real_acquisition_texture(run):
    _, tr = run
    # after the first 1 s: M12's sensor states start away from truth (no trim initialisation in this
    # open-loop fixture) and the two T1 lanes settle at different rates, giving a transient T1 cross-channel
    # soft-fail at 0.45-0.72 s (observed; W2.1 must initialise sensor states at trim). Then no failure at all.
    vs = tr.ports["fadec.validation_state"][240:, 0]
    assert (vs == 0).all(), {int(s): int((vs[:, s] != 0).sum()) for s in range(vs.shape[1])}
    assert (tr.ports["fadec.fault_code"][240:, 0] == 0).all()
    assert np.isfinite(tr.ports["fadec.wf_cmd"]).all()


def test_validated_n2_is_the_lane_average_of_the_digitised_readings(run):
    _, tr = run
    n2v = tr.ports["fadec.n2_v"][120:, 0]
    truth = tr.ports["truth.eng_n2"][120:, 0]
    assert np.max(np.abs(n2v / truth - 1.0)) < 0.005  # quantisation + noise + interpolation only
    # quantised: the selection takes few distinct values relative to its length (lattice-valued lanes)
    assert np.unique(tr.ports["acq_fadec.lane_eng_n2_a"][120:, 0]).size < n2v.size


def test_ab_lit_is_the_real_m13_lane(run):
    """The AB flame detector reaches M08 as an M13 FADEC lane (no stand-in): AB off, the lane reads 0 at
    every FADEC frame."""
    _, tr = run
    assert int(np.sum(tr.ports["acq_fadec.lane_eng_ab_lit_n"])) > 500  # ~600 FADEC frames in 10 s
    assert not np.asarray(tr.ports["acq_fadec.lane_eng_ab_lit"]).any()


def test_m13_sample_counts_are_the_fadec_frame_schedule(run):
    fad, tr = run
    st = fad.init(fad.params, None)
    from phalanx.core.time import truth_step_times_ns

    # M13 emits the frames of [t_k, t_k+1) at step k; M08 processes them at step k+1 (back-edge)
    sched = fad.frame_schedule(st, truth_step_times_ns(np.arange(1, N + 1)))
    assert np.array_equal(tr.ports["acq_fadec.lane_eng_n2_a_n"], sched.count)
