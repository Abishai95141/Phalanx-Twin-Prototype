"""M13 acquisition artefacts: glitch words, validity gating, deadband, episodic freeze (architecture §7, M13).

Rates are raised far above the Tejas defaults in these tests so each mechanism shows in a short run; the
mechanism, not the rate, is under test (rates are A-W1.6-25/26 assumptions with sweeps). Every artefact the
acquiring hardware cannot detect (freeze, glitch) leaves no quality flag (A-W1.6-31).
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import STREAMS, AcquisitionCore
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params

pytestmark = pytest.mark.unit
IDENT = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


def make_core(d, channels, params=None):
    acq = build_acquisition_config(d, channels, sensor_channels=channels, params=params)
    keys = RngService(0x16, StreamRegistry(list(STREAMS))).scope(IDENT)
    return acq, AcquisitionCore(acq, lambda comp, cid: keys.stream("acquisition", comp, sensor=cid))


def process(core, S_of_t, L, *, phase=5, k0=0, state=None):
    k = np.arange(k0, k0 + L, dtype=np.int64)
    ts, te = truth_step_times_ns(k), truth_step_times_ns(k + 1)
    S = np.asarray(S_of_t(te / 1e9), dtype=np.float64).reshape(L, -1)
    st = core.init_state() if state is None else state
    return core.process(st, S, S, ts, te, np.full(L, phase))


def test_glitch_words_are_top_of_scale_and_unflagged(d):
    """Glitch rate raised to 10 per second on PS3 lane A (60 Hz, p = 1/6 per sample): glitches read the
    top-of-scale code with no flag; n = 3,600 samples gives 600 +- 4 sigma (98)."""
    p = load_params("M13")
    p["glitch_default"] = p["glitch_default"].replace(rate=10.0)
    acq, core = make_core(d, ("ENG.PS3.A",), p)
    _, (ds,) = process(core, lambda t: np.full_like(t, 2.0e6), 14400)
    top = acq.Q[0, K.AQ_CMAX] * acq.P[0, K.AP_SF]
    g = ds.value[:, 0] == top
    assert abs(int(g.sum()) - ds.times.size / 6) < 4 * np.sqrt(ds.times.size / 6 * 5 / 6)
    assert np.all(ds.flags[g, 0] == 0) and np.all(ds.validity[:, 0] == K.V_NORMAL)


def test_speed_gate(d):
    """N2 below 816 rpm (4.854 %, -400 alternator range) reads 0 with NO_COMPUTED_DATA + GATED; above the
    threshold it reads normally."""
    _acq, core = make_core(d, ("ENG.N2.A",))
    rad_per_pct = d.eu_to_si("ENG.N2.A", 1.0)
    _, (ds,) = process(core, lambda t: np.where(t < 1.0, 3.0, 20.0) * rad_per_pct, 480)
    lo = ds.times < 0.99e9
    hi = ds.times > 1.05e9
    assert np.all(ds.value[lo, 0] == 0.0) and np.all(ds.validity[lo, 0] == K.V_NCD)
    assert np.all(ds.flags[lo, 0] & K.FLAG_GATED)
    assert np.all(np.abs(ds.value[hi, 0] - 20.0) < 0.2) and np.all(ds.validity[hi, 0] == K.V_NORMAL)
    assert not np.any(ds.flags[hi, 0])


def test_deadband_backlash(d):
    """PLA transducer backlash of 1 deg (A-W1.6-27 sweep end): on a sinusoidal lever the reading trails the
    input by half the width while moving, and holds through each reversal until the input has moved one
    full width (n = 2,880 frames, 12 s)."""
    p = load_params("M13")
    p["deadband_pla"] = p["deadband_pla"].replace(width_eu=1.0)
    p["noise_fadec_pla"] = p["noise_fadec_pla"].replace(sigma_eu=0.0)  # PLA lane noise is in EU (W2.2)
    _acq, core = make_core(d, ("ENG.PLA.A",), p)
    deg = np.pi / 180
    _, (ds,) = process(core, lambda t: (45.0 + 5.0 * np.sin(2 * np.pi * 0.25 * t)) * deg, 2880)
    x = 45.0 + 5.0 * np.sin(2 * np.pi * 0.25 * ds.times / 1e9)
    y = ds.value[:, 0]
    # the reading is quantised after the backlash, at the FADEC converter step (dictionary 0.1.2 migration)
    q = float(d.channel("ENG.PLA.A")["native_step"])  # the FADEC converter step (dictionary 0.1.3)
    # truth frames are 1/240 s apart and the sample interpolates linearly between them: a sinusoid's chord
    # error A w^2 dt^2 / 8 (2.7e-5 deg) was hidden by the 0.088 deg word step before the migration
    interp = 5.0 * (2 * np.pi * 0.25) ** 2 * (1 / 240) ** 2 / 8
    assert np.all(np.abs(y - x) <= 0.5 + q / 2 + interp + 1e-9)  # never further than w/2 from the input
    # once the lever has moved more than one full width since the last reversal, y trails by exactly w/2
    moved, last, sgn = 0.0, x[0], 0.0
    for j in range(1, x.size):
        s_ = np.sign(x[j] - x[j - 1])
        if s_ != sgn:
            sgn, last = s_, x[j - 1]
        if abs(x[j] - last) > 1.0 + q:
            assert abs(y[j] - (x[j] - 0.5 * sgn)) <= q / 2 + interp + 1e-9
            moved += 1
    assert moved > 400  # most of the 720 samples are in steady motion


def test_freeze_holds_and_is_unflagged(d):
    """Episodic freeze on a T5 harness at 0.05 starts per airborne second: the code holds for >= 30 s while
    the truth ramps, with no flag and NORMAL validity; on the ground (phase TAXI) no freeze starts. n = 3
    min."""
    p = load_params("M13")
    p["freeze_egt"] = p["freeze_egt"].replace(rate=180.0)
    _acq, core = make_core(d, ("ENG.T5.HARNESS_A",), p)
    ramp = lambda t: 800.0 + 0.5 * t  # noqa: E731  (K, 0.5 K/s: one 1 degC step every 2 s)
    _, (ds,) = process(core, ramp, 240 * 180)
    y = ds.value[:, 0]
    runs, start = [], 0
    for j in range(1, y.size + 1):
        if j == y.size or y[j] != y[start]:
            runs.append(j - start)
            start = j
    assert max(runs) >= 30 * 60  # a freeze of at least 30 s at 60 Hz
    assert np.all(ds.flags[:, 0] == 0) and np.all(ds.validity[:, 0] == K.V_NORMAL)
    _, (gnd,) = process(core, ramp, 240 * 180, phase=2)
    yg = gnd.value[:, 0]
    longest = max(np.diff(np.flatnonzero(np.diff(yg) != 0)))
    assert longest < 3 * 60  # only the 2-s quantiser staircase on the ground


def test_saturation_flag_from_the_pipeline(d):
    """A reading beyond full scale (oil temperature 200 degC > 150 degC range) saturates at the range code
    with OUT_OF_RANGE (the ADC knows its own full scale)."""
    _acq, core = make_core(d, ("ENG.OIL_T",))
    _, (ds,) = process(core, lambda t: np.full_like(t, 473.15), 240)
    hi = d.channel("ENG.OIL_T")["range"]["max"]
    assert np.all(ds.value[:, 0] <= hi) and np.all(ds.flags[:, 0] == K.FLAG_OUT_OF_RANGE)
