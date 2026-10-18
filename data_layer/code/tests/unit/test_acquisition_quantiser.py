"""M13 double quantiser and saturation (acceptance A2; AD-05). G1 diagnostic against the measured grids.

Proxy grids ([MEASURED] 687-CAL, used only here): N1/N2 native 0.04 % on the 0.03125 % recorder lattice with
native offset phi0 = 1.04 LSB; EGT native 0.8 degC on the 0.5 degC lattice with phi0 = 0.04875 LSB
(`analysis/settling_experiment/results/native_step_cal.json`, round-2 `frozen/S/mb.json`).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import build_acquisition_config
from phalanx.dictionary import load_dictionary
from phalanx.sensors.config import build_sensor_config
from phalanx.validation.guards import g1_distance

pytestmark = pytest.mark.unit
REPO = Path(__file__).resolve().parents[2]
NATIVE_CAL = REPO / "analysis" / "settling_experiment" / "results" / "native_step_cal.json"

#: proxy (DASHlink) grids, EU: (native step, recorder LSB, native offset in EU, residue period, never-used)
PROXY = {
    "N1": (0.04, 0.03125, 1.04 * 0.03125, 32, {3, 8, 12, 17, 21, 26, 31}),
    "N2": (0.04, 0.03125, 1.04 * 0.03125, 32, {3, 8, 12, 17, 21, 26, 31}),
    "EGT": (0.8, 0.5, 0.04875 * 0.5, 8, {1, 4, 7}),
}


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


def codes(x, qn, on, sf, hasrec=1):
    return np.array([K.quantise_code(v, qn, on, sf, 0.0, hasrec, -(10**9), 10**9)[0] for v in x])


def residue_usage(c, period):
    h = np.bincount(np.mod(c, period), minlength=period).astype(float)
    return h / h.sum()


@pytest.mark.parametrize("fam", ["N1", "N2", "EGT"])
def test_g1_reproduces_never_used_residues(fam):
    """A dense slow sweep through the double quantiser uses exactly the residues the real recorder used;
    a single lattice uses all of them. G1 (total-variation distance of residue usage) vs the measured usage of
    687-CAL: < 0.06 for the double quantiser, > 0.15 for the single lattice (round 2: 0.01-0.02 vs 0.19-0.27).
    n = 200,000 sweep points (every code visited thousands of times)."""
    qn, lsb, on, period, unused = PROXY[fam]
    lo, hi = (90.0, 100.0) if fam != "EGT" else (500.0, 700.0)
    x = np.linspace(lo, hi, 200_001)
    c2 = codes(x, qn, on, lsb)
    c1 = np.rint(x / lsb).astype(np.int64)
    u2, u1 = residue_usage(c2, period), residue_usage(c1, period)
    assert set(np.flatnonzero(u2 == 0)) == unused
    assert not np.any(u1 == 0)
    meas = json.loads(NATIVE_CAL.read_text())["channels"]
    # measured usage of the four engine positions as counts (1e6 samples each), G1 via the validation guard
    real = {
        fam: np.array(
            [np.rint(1e6 * np.array(meas[f"{fam}_{k}"]["residue_usage_mod_P"])) for k in (1, 2, 3, 4)]
        )
    }
    syn2 = {fam: np.tile(np.bincount(np.mod(c2, period), minlength=period), (4, 1))}
    syn1 = {fam: np.tile(np.bincount(np.mod(c1, period), minlength=period), (4, 1))}
    tv2 = g1_distance([syn2], [real], families=(fam,))[fam]["tv_distance"]
    tv1 = g1_distance([syn1], [real], families=(fam,))[fam]["tv_distance"]
    assert tv2 < 0.06
    assert tv1 > 0.15


def test_values_lie_on_the_dictionary_lattice(d):
    """Every Tejas sensor channel: the acquired value is code x final step exactly (recorder LSB when the
    channel has a recorder word, else its converter step if the dictionary gives one -- the FADEC lanes since
    the W2.2 migration -- else its native step), from the dictionary, never a free float."""
    sens = build_sensor_config(d)
    acq = build_acquisition_config(d, sens.channels, sensor_channels=sens.channels)
    for c, cid in enumerate(acq.channels):
        ch = d.channel(cid)
        step = ch["recorder_lsb"] if ch["recorder_lsb"] is not None else ch["native_step"]
        step = 1.0 if step is None else step  # a discrete word (W2.2 word path): integer codes, step 1
        assert acq.P[c, K.AP_SF] == float(step)
        assert acq.Q[c, K.AQ_HASREC] == int(ch["recorder_lsb"] is not None)
        lo, hi = ch["range"]["min"], ch["range"]["max"]
        assert acq.Q[c, K.AQ_CMIN] * step >= lo - 1e-9 * max(1, abs(lo))
        assert acq.Q[c, K.AQ_CMAX] * step <= hi + 1e-9 * max(1, abs(hi))
        assert (acq.Q[c, K.AQ_CMIN] - 1) * step < lo and (acq.Q[c, K.AQ_CMAX] + 1) * step > hi


def test_saturation_clamps_to_range_and_flags():
    """Values beyond full scale saturate at the range code and set OUT_OF_RANGE; in-range values do not."""
    c, sat = K.quantise_code(150.0, 0.03125, 0.0, 0.03125, 0.0, 0, 0, 3520)
    assert (c, sat) == (3520, 1)
    c, sat = K.quantise_code(-1.0, 0.03125, 0.0, 0.03125, 0.0, 0, 0, 3520)
    assert (c, sat) == (0, 1)
    c, sat = K.quantise_code(50.0, 0.03125, 0.0, 0.03125, 0.0, 0, 0, 3520)
    assert (c, sat) == (1600, 0)


def test_double_quantiser_composes_native_then_recorder():
    """y = L rint((q_n rint((x - o)/q_n) + o)/L): checked against the round-2 M-B formula on random inputs."""
    g = np.random.Generator(np.random.Philox(np.random.SeedSequence(16, spawn_key=(7,))))
    x = g.uniform(90, 100, 5000)
    qn, lsb, on = 0.04, 0.03125, 1.04 * 0.03125
    ours = codes(x, qn, on, lsb) * lsb
    r = qn / lsb
    phi0 = on / lsb
    xn = lsb * (r * np.rint((x / lsb - phi0) / r) + phi0)
    ref = lsb * np.rint(xn / lsb)
    np.testing.assert_allclose(ours, ref, rtol=0, atol=1e-9)
