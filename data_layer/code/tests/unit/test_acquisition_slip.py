"""M13 analog slip windows (acceptance A4; AD-06, architecture §8).

Missingness comes only from the clock-domain mechanism: the converter and the reader run on two
``core.time.ClockDomain`` oscillators offset by Delta, so collision windows recur every 1/(f Delta); inside a
window a read returns the bottom-of-scale sentinel with probability p_in; outside, never. Digital words
(frequency counts, computed words) and controller LRUs (no converter clock) show no sentinels. No NaN
anywhere.

Run: Tejas defaults (utility EU, 10 Hz slow channels, Delta_conv 910 ppm -> beat period 110 s, w = 2 ms,
p_in 0.25) over n = 600 s (5 beat periods, 6,000 samples per channel), processed in 10 blocks.
"""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import build_acquisition_config
from phalanx.acquisition.core import STREAMS, AcquisitionCore, collision_mask
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import truth_step_times_ns
from phalanx.dictionary import load_dictionary

pytestmark = pytest.mark.unit
IDENT = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")
CH = ("HYD.SYS1.T", "ELEC.DCBUS.V.MAIN", "BRK.WHEEL_SPEED.SPEED_L", "ENG.PS3.A")


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def run600(d):
    acq = build_acquisition_config(d, CH, sensor_channels=CH)
    keys = RngService(0x16, StreamRegistry(list(STREAMS))).scope(IDENT)
    core = AcquisitionCore(acq, lambda comp, cid: keys.stream("acquisition", comp, sensor=cid))
    st = core.init_state()
    vals = np.array([320.0, 28.0, 50.0, 2.0e6])  # mid-range SI truth
    out: dict[str, list] = {c: [] for c in CH}
    for b in range(10):
        k = np.arange(b * 14400, (b + 1) * 14400, dtype=np.int64)
        ts, te = truth_step_times_ns(k), truth_step_times_ns(k + 1)
        S = np.tile(vals, (k.size, 1))
        st, doms = core.process(st, S, S, ts, te, np.full(k.size, 5))
        for ds in doms:
            for j, c in enumerate(ds.channels):
                out[CH[c]].append((ds.times, ds.value[:, j], ds.flags[:, j], ds.validity[:, j], ds.domain))
    res = {}
    for c, parts in out.items():
        res[c] = (*tuple(np.concatenate([p[i] for p in parts]) for i in range(4)), parts[0][4])
    return acq, res


def test_sentinels_only_on_analog_paths_of_slipping_lrus(d, run600):
    acq, res = run600
    for c in ("HYD.SYS1.T", "ELEC.DCBUS.V.MAIN"):
        assert d.channel(c)["signal"] == "analog"
        assert np.any(res[c][2] & K.FLAG_SENTINEL)
    assert d.channel("BRK.WHEEL_SPEED.SPEED_L")["signal"] == "frequency"  # digital count on the same LRU
    assert not np.any(res["BRK.WHEEL_SPEED.SPEED_L"][2] & K.FLAG_SENTINEL)
    assert acq.domains[res["ENG.PS3.A"][4]].slip is None  # FADEC: no converter clock
    assert not np.any(res["ENG.PS3.A"][2] & K.FLAG_SENTINEL)


def test_sentinel_is_bottom_of_scale_and_never_nan(d, run600):
    _acq, res = run600
    for c in CH:
        _t, v, f, _vv, _ = res[c]
        assert np.all(np.isfinite(v))
        sent = (f & K.FLAG_SENTINEL) != 0
        if sent.any():
            assert np.all(v[sent] == d.channel(c)["range"]["min"])


def test_no_independent_dropout_and_in_window_probability(d, run600):
    """Every sentinel lies inside a collision window (exact clock arithmetic); inside, the loss probability is
    p_in = 0.25 within a 4-sigma binomial band."""
    acq, res = run600
    c = acq.index("HYD.SYS1.T")
    dom = acq.domains[int(acq.domain_of[c])]
    t, _v, f, _, _ = res["HYD.SYS1.T"]
    coll = collision_mask(dom, t, acq.slot_phase_ns[[c]])[:, 0] == 1
    sent = (f & K.FLAG_SENTINEL) != 0
    assert not np.any(sent & ~coll)
    n_in = int(coll.sum())
    assert n_in > 50
    p = acq.P[c, K.AP_PIN]
    assert abs(sent[coll].sum() - p * n_in) < 4 * np.sqrt(n_in * p * (1 - p))


def test_slip_period_is_one_over_f_delta(d, run600):
    """Collision windows recur with period 1/|f_conv - f_read| = 1/(f Delta) (A4): measured from the start of
    each window run, within one sample period. Two channels of one LRU have phase-related windows (fixed
    slot offset), as round 1 measured (P3)."""
    acq, res = run600
    starts = {}
    for name in ("HYD.SYS1.T", "ELEC.DCBUS.V.MAIN"):
        c = acq.index(name)
        dom = acq.domains[int(acq.domain_of[c])]
        t = res[name][0]
        coll = collision_mask(dom, t, acq.slot_phase_ns[[c]])[:, 0]
        s = t[1:][np.diff(coll) == 1]
        f_read = float(dom.clock.f_actual_hz)
        f_conv = float(dom.slip.converter.f_actual_hz)
        period = 1.0 / abs(f_conv - f_read)
        assert period == pytest.approx(1.0 / (10.0 * 910e-6), rel=0.01)
        np.testing.assert_allclose(np.diff(s) / 1e9, period, atol=1.0 / f_read)
        starts[name] = s
    assert len(starts["HYD.SYS1.T"]) >= 4
    off = (starts["ELEC.DCBUS.V.MAIN"][:4] - starts["HYD.SYS1.T"][:4]) / 1e9
    assert np.ptp(off) <= 2.0 / 10.0  # fixed phase relation between the two channels' bursts


def test_disabling_slip_removes_all_sentinels(d):
    """Negative control: with the utility EU's slip disabled the same run has no sentinel at all (the
    sentinels above come only from the clock mechanism, AD-06)."""
    from phalanx.dictionary.params import load_params

    p = load_params("M13")
    p["clock_bheem_eu"] = p["clock_bheem_eu"].replace(slip_enabled=0.0)
    acq = build_acquisition_config(d, CH[:1], sensor_channels=CH[:1], params=p)
    keys = RngService(0x16, StreamRegistry(list(STREAMS))).scope(IDENT)
    core = AcquisitionCore(acq, lambda comp, cid: keys.stream("acquisition", comp, sensor=cid))
    k = np.arange(0, 240 * 300, dtype=np.int64)
    S = np.full((k.size, 1), 320.0)
    _, (ds,) = core.process(
        core.init_state(), S, S, truth_step_times_ns(k), truth_step_times_ns(k + 1), np.full(k.size, 5)
    )
    assert not np.any(ds.flags & K.FLAG_SENTINEL)
