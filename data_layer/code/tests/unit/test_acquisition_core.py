"""M13 shared acquisition path: sampling modes, block-length independence, compiled = reference (A8)."""

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
from phalanx.sensors.config import build_sensor_config

pytestmark = pytest.mark.unit
IDENT = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


def make_core(d, channels, params=None):
    acq = build_acquisition_config(d, channels, sensor_channels=channels, params=params)
    keys = RngService(0x16, StreamRegistry(list(STREAMS))).scope(IDENT)
    return acq, AcquisitionCore(acq, lambda comp, cid: keys.stream("acquisition", comp, sensor=cid))


def frames(k0, L):
    k = np.arange(k0, k0 + L, dtype=np.int64)
    return truth_step_times_ns(k), truth_step_times_ns(k + 1)


def test_count_mode_is_interval_average(d):
    """Frequency sensors are read by period counting (A-W1.6-29): on a ramp the reading is the signal at the
    middle of the acquisition interval, not at its end (N2 lane, 60 Hz, noise off; n = 480 frames)."""
    p = load_params("M13")
    p["noise_n2"] = p["noise_n2"].replace(sigma_eu=0.0)  # N2 lane noise is in EU (W2.2 migration)
    _acq, core = make_core(d, ("ENG.N2.A",), p)
    pct = d.eu_to_si("ENG.N2.A", 1.0)
    q = float(d.channel("ENG.N2.A")["native_step"])  # the FADEC converter step (dictionary 0.1.3)
    rate = 10.0  # %/s: 0.167 % (5 word LSB, 25 converter steps) per acquisition interval
    ts, te = frames(0, 480)
    S = (80.0 + rate * te / 1e9).reshape(-1, 1) * pct
    _, (ds,) = core.process(core.init_state(), S, S, ts, te, np.full(480, 5))
    t = ds.times / 1e9
    mid = 80.0 + rate * 0.5 * (t[1:] + t[:-1])
    np.testing.assert_allclose(ds.value[1:, 0], np.rint(mid / q) * q, atol=1e-9)
    end = 80.0 + rate * t[1:]
    assert np.mean(np.abs(ds.value[1:, 0] - end)) > 2 * 0.03125  # the end value is visibly different


def test_point_mode_interpolates_at_the_tick(d):
    """Analog channels read the frame-interpolated signal at the LRU tick (A-W0.2-2): PS3 lane, linear
    truth."""
    p = load_params("M13")
    p["noise_fadec_ps3"] = p["noise_fadec_ps3"].replace(sigma_eu=0.0)  # PS3 lane noise in EU (W2.2)
    _acq, core = make_core(d, ("ENG.PS3.A",), p)
    ts, te = frames(0, 480)
    psi = d.eu_to_si("ENG.PS3.A", 1.0)
    q = float(d.channel("ENG.PS3.A")["native_step"])  # the FADEC converter step (dictionary 0.1.3)
    S = (100.0 + 50.0 * te / 1e9).reshape(-1, 1) * psi
    _, (ds,) = core.process(core.init_state(), S, S, ts, te, np.full(480, 5))
    x = 100.0 + 50.0 * ds.times / 1e9
    ok = ds.times >= te[0]
    np.testing.assert_allclose(ds.value[ok, 0], np.rint(x[ok] / q) * q, atol=1e-9)


@pytest.fixture(scope="module")
def all_channels(d):
    sens = build_sensor_config(d)
    acq, core = make_core(d, sens.channels)
    L = 2400
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(16, spawn_key=(3,))))
    lo = np.array([d.eu_to_si(c, d.channel(c)["range"]["min"]) for c in acq.channels])
    hi = np.array([d.eu_to_si(c, d.channel(c)["range"]["max"]) for c in acq.channels])
    base = lo + (hi - lo) * g.uniform(0.2, 0.8, size=lo.size)
    S = base + (hi - lo) * 0.01 * np.sin(np.arange(L)[:, None] / 37.0 + np.arange(lo.size))
    return acq, core, S


def _run(core, S, blocks, kernel=K.acq_kernel):
    st = core.init_state()
    outs = []
    k0 = 0
    for L in blocks:
        ts, te = frames(k0, L)
        st, doms = core.process(st, S[k0 : k0 + L], S[k0 : k0 + L], ts, te, np.full(L, 5), kernel=kernel)
        outs.append(doms)
        k0 += L
    merged = {}
    for doms in outs:
        for ds in doms:
            for j, c in enumerate(ds.channels):
                merged.setdefault(c, []).append(
                    np.column_stack([ds.sample_index, ds.times, ds.code[:, j], ds.flags[:, j]])
                )
    return st, {c: np.concatenate(v) for c, v in merged.items()}


@pytest.mark.parametrize("blocks", [[2400], [1] * 240 + [2160], [7] * 342 + [6], [240] * 10])
def test_block_length_independence(all_channels, blocks):
    """Every Tejas sensor channel, noise and artefacts on: the samples (index, instant, code, flags) and the
    final state do not depend on how the frames are blocked (n = 2,400 frames, 132 channels)."""
    _acq, core, S = all_channels
    st_ref, ref = _run(core, S, [2400])
    st, out = _run(core, S, blocks)
    for c in ref:
        np.testing.assert_array_equal(out[c], ref[c])
    for k in st_ref:
        np.testing.assert_array_equal(st[k], st_ref[k])


def test_compiled_equals_reference_bitwise(all_channels):
    """A8: the compiled acquisition kernel equals its NumPy reference (py_func) bitwise (n = 480 frames)."""
    _acq, core, S = all_channels
    a = _run(core, S[:480], [480])
    b = _run(core, S[:480], [480], kernel=K.acq_kernel.py_func)
    for c in a[1]:
        np.testing.assert_array_equal(a[1][c], b[1][c])


def test_no_nan_for_any_channel(all_channels):
    acq, core, S = all_channels
    st, out = _run(core, S, [2400])
    for c, arr in out.items():
        assert np.all(np.isfinite(arr)), acq.channels[c]
    for v in st.values():
        assert np.all(np.isfinite(v))
