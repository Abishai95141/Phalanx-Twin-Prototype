"""W2.2 (coordinator priority): the ENG.AB_LIT lane producer, M12 UV flame detector -> M13 FADEC lane.

M12 class ``uv_flame_detector`` (**PROXY** A-W2.2-15): source ``discrete`` on M07 ``eng.ab_state`` (1 while
the afterburner flame is established, code LIT; not during the lighting sequence), a first-order detector
response and the FADEC's input comparator. M13 acquires the discrete through the word path (A-W2.2-12) on the
FADEC clock and publishes it as ``lane.ENG.AB_LIT``, the lane M08's light-off and blow-out logic reads (the
tracked conformance exception is closed).

Sample: TEST FIXTURE ``eng.ab_state`` scripts of 3 s (720 truth frames: off, lighting, lit, off), n = 1 run
per check; the PROXY check repeats the light-off at 6 instants (n = 6).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.acquisition import kernel as AK
from phalanx.acquisition.config import acquisition_clock, build_acquisition_config
from phalanx.acquisition.core import STREAMS as ACQ_STREAMS
from phalanx.acquisition.module import lane_channels
from phalanx.acquisition.ports import lane_bindings
from phalanx.acquisition.record import AcquisitionRecorder
from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_param_set, load_params
from phalanx.engine.layout import AB_LIGHTING, AB_LIT, AB_OFF
from phalanx.sensors import kernel as K
from phalanx.sensors.config import build_sensor_config
from phalanx.sensors.module import BIAS_PORT, FAULT_STREAM, SENSOR_FAULT_EVENT, SensorPhysics

pytestmark = pytest.mark.integration
D = load_dictionary()
DT = 1.0 / 240.0
CID = "ENG.AB_LIT"
P = load_params("M12")["uv_flame_detector"]
TAU = float(P.value("tau"))
TRIP = float(P.value("trip"))


def delay(tau: float) -> int:
    """Truth frames from the frame the flame state changes to the comparator crossing: the first-order element
    (first-order-hold solution, the input ramping over the change frame) is at c a^n from its new level n
    frames later, c = (tau/dt)(1 - a), a = exp(-dt/tau); it crosses the mid-scale trip once c a^n <= 1 - trip
    (about tau ln 2 after the mid-ramp instant)."""
    a = math.exp(-DT / tau)
    c = (tau / DT) * (1.0 - a)
    return math.ceil(math.log((1.0 - TRIP) / c) / math.log(a))


DELAY = delay(TAU)
IDENT = KeyPath.of(scenario="W22ABLIT", tail="KH2001", sortie="S1")


def script(lighting=120, lit=240, out=600, n=720) -> np.ndarray:
    """eng.ab_state per truth frame (TEST FIXTURE): off, lighting from ``lighting``, lit from ``lit``, off
    from ``out``."""
    s = np.full(n, AB_OFF, dtype=np.int64)
    s[lighting:lit] = AB_LIGHTING
    s[lit:out] = AB_LIT
    return s


def sensor():
    cfg = build_sensor_config(D, channels=(CID,))
    m = SensorPhysics("sens", load_param_set("M12", "constants"), cfg)
    m.bind(RngService(0x22AB, StreamRegistry([FAULT_STREAM])).scope(IDENT))
    return m


def run(m, states, *, state=None, k0=0, bias=0.0):
    st = m.init(m.params, m.keys) if state is None else state
    n = states.size
    inputs = {"eng_ab_state": states.reshape(n, 1).astype(np.int64), BIAS_PORT: np.full((n, 1), bias)}
    st, out = m.step_block(st, inputs, truth_step_times_ns(np.arange(k0, k0 + n, dtype=np.int64)), DT)
    return st, out["s_1"][:, 0], out["x_1"][:, 0]


def fault(m, st, **payload):
    st, _ = m.on_event(st, Event(0, SENSOR_FAULT_EVENT, "sens", {"channel": CID, **payload}), 0)
    return st


# ---- M12 ---------------------------------------------------------------------------------------------------
def test_ab_lit_is_a_uv_flame_detector_discrete():
    cfg = build_sensor_config(D)
    c = cfg.channel_index(CID)
    assert cfg.classes[c] == "uv_flame_detector"
    (inp,) = [s for s in cfg.inputs if s.signal == "eng.ab_state"]
    assert inp.dtype == "<i8" and inp.unit == "1"  # M07's integer state code, as catalogued
    assert int(cfg.ch_i[c, K.IC_DISC]) == 1 and cfg.ch_p[c, K.PC_TRIP] == float(P.value("trip"))
    e = cfg.elements_of(CID)[0]
    assert int(cfg.el_i[e, K.IE_SRC]) == K.SRC_DISCRETE and int(cfg.el_i[e, K.IE_DYN]) == K.DYN_LAG1
    # the stimulus level sits between M07's codes: the established flame (LIT), not the lighting sequence
    assert AB_LIGHTING < cfg.el_p[e, K.PE_LEVEL] <= AB_LIT
    ch = D.channel(CID)
    assert dict(ch["range"]) == {"min": 0, "max": 1} and ch["native_step"] is None  # a word (0.1.3)
    assert ch["encoding"]["type"] == "bitfield" and ch["acq_lru"] == "FADEC"


def test_light_off_and_blow_out_are_detected_after_the_detector_response():
    """No detection during the lighting sequence; detection DELAY frames after light-off; drop-out DELAY
    frames after the flame goes out; the output is a clean 0/1 and the truth label is the flame state."""
    m = sensor()
    s = script()
    _st, y, x = run(m, s)
    assert set(np.unique(y).tolist()) <= {0.0, 1.0} and DELAY >= 1
    on = np.flatnonzero(y)
    assert on[0] == 240 + DELAY and on[-1] == 600 + DELAY - 1 and on.size == 360
    assert not y[: 240 + DELAY].any()  # igniters and pilot flame (lighting) are not detected
    assert np.array_equal(x, (s == AB_LIT).astype(float))


def test_detection_delay_is_deterministic_proxy():
    """PROXY A-W2.2-15 exposed: the light-off detection delay is the same number of frames wherever the
    light-off falls (n = 6). A photon-counting UV tube has a random detection time; this model has none."""
    delays = set()
    for k0 in (60, 61, 97, 150, 211, 300):
        m = sensor()
        _st, y, _x = run(m, script(lighting=k0 - 30, lit=k0, out=k0 + 200, n=k0 + 240))
        delays.add(int(np.flatnonzero(y)[0]) - k0)
    assert delays == {DELAY}


def test_detector_failure_modes():
    """M11 sensor-fault modes on the detector signal (before the comparator): open = never sees the flame
    (no-light); slow x10 = light-off seen 10 x later; stuck lit = blow-out not seen; a sensitivity loss
    (bias -0.6) = never trips."""
    s = script()
    m = sensor()
    st = fault(m, m.init(m.params, m.keys), mode="open")
    assert not run(m, s, state=st)[1].any()
    m = sensor()
    st = fault(m, m.init(m.params, m.keys), mode="slow", value=10.0)
    y = run(m, s, state=st)[1]
    assert np.flatnonzero(y)[0] - 240 == delay(10 * TAU) > 9 * DELAY
    m = sensor()
    st, y0, _ = run(m, s[:400])  # lit
    st = fault(m, st, mode="stuck")
    y1 = run(m, s[400:], state=st, k0=400)[1]
    assert y0[-1] == 1.0 and (y1 == 1.0).all()  # the flame went out at 600 but the detector still reads lit
    m = sensor()
    assert not run(m, s, bias=-0.6)[1].any()


# ---- M13: the FADEC lane
# ------------------------------------------------------------------------------------
def test_m13_fadec_lane_is_the_held_detector_output():
    """lane.ENG.AB_LIT is an M13 FADEC lane (the word path on the FADEC 60 Hz clock), and every lane sample is
    the detector output the M12 frame published last (n = 720 frames, ~180 lane samples)."""
    sens = build_sensor_config(D)
    assert CID in lane_channels(D, sens, "FADEC")
    assert lane_bindings(1)[f"lane.{CID}"][0] == "acq_fadec"
    acq = build_acquisition_config(D, (CID,), sensor_channels=sens.channels)
    assert int(acq.Q[0, AK.AQ_MODE]) == AK.MODE_HOLD
    assert acq.domains[0].lru == "FADEC" and acq.domains[0].clock == acquisition_clock("FADEC", 60.0)
    m = sensor()
    s = script()
    _st, y, x = run(m, s)
    one = build_acquisition_config(D, (CID,), sensor_channels=(CID,))
    rec = AcquisitionRecorder(one, RngService(0x22AB, StreamRegistry(list(ACQ_STREAMS))).scope(IDENT))
    _st2, recs = rec.process(rec.init_state(), 0, y[:, None], x[:, None], np.full(s.size, 5))
    r = recs[CID]
    t = r.cat("t_sample", np.int64)
    v = r.cat("value", np.float64)
    bounds = truth_step_times_ns(np.arange(s.size + 1))
    j = np.searchsorted(bounds, t, side="right") - 1
    assert v.size >= 175 and np.array_equal(v, y[np.maximum(j - 1, 0)])
    assert set(np.unique(v).tolist()) == {0.0, 1.0}
