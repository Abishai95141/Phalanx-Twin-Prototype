"""M13 idiosyncratic noise generator statistics (acceptance A3): sigma, ACF, PSD and tails vs configuration.

Configured values are the N1 proxy-derived ones (A-W1.6-22: tau_c 0.34 s from the 687-CAL lag-1 phi of about
0.48 at 4 Hz) and the heavy-tail mixture of report §8 component 4. The noise path is run through the real
kernel with a fine native grid (1e-9) so the output is the noise itself. n per test is stated with its
standard error.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import signal as sps
from scipy import stats

from phalanx.acquisition import kernel as K
from phalanx.acquisition.core import EVENT_STREAM, NOISE_STREAM
from phalanx.core.rng import KeyPath, RngService, StreamRegistry

pytestmark = pytest.mark.statistical
IDENT = KeyPath.of(scenario="W16", tail="KH2001", sortie="SRT0001")


def _run_noise(phi, tail_p, tail_k, n, sensor="NOISE.TEST"):
    """The kernel's noise path alone: a fine native grid (1e-9) so the output is the noise itself."""
    rng = RngService(0x1616, StreamRegistry([NOISE_STREAM, EVENT_STREAM]))
    keys = rng.scope(IDENT)
    z = keys.stream("acquisition", "noise", sensor=sensor).draws(0, n).reshape(n, 1)
    u = keys.stream("acquisition", "events", sensor=sensor).draws(0, K.N_U * n).reshape(n, 1, K.N_U)
    P = np.zeros((1, K.N_AP))
    P[0, K.AP_SCALE] = 1.0
    P[0, K.AP_QN] = 1e-9
    P[0, K.AP_SF] = 1e-9
    P[0, K.AP_SIGMA] = 1.0
    P[0, K.AP_PHI] = phi
    P[0, K.AP_SQ] = math.sqrt(1 - phi * phi)
    P[0, K.AP_TAILP] = tail_p
    P[0, K.AP_TAILK] = tail_k
    Q = np.zeros((1, K.N_AQ), dtype=np.int64)
    Q[0, K.AQ_CMIN] = -(10**15)
    Q[0, K.AQ_CMAX] = 10**15
    L = n  # one sample per frame
    t_start = np.arange(L, dtype=np.int64) * 10
    out = K.acq_kernel(
        np.zeros((1, K.N_AF)),
        np.zeros((1, K.N_AI), dtype=np.int64),
        P,
        Q,
        np.ones((1, K.N_PHASE)),
        np.zeros(K.N_PHASE, dtype=np.int64),
        np.zeros((L, 1)),
        np.zeros((L, 1)),
        t_start,
        t_start + 10,
        t_start,
        np.arange(L, dtype=np.int64),
        np.zeros(L),
        np.full(L, 5, dtype=np.int64),
        z,
        u,
        np.zeros((L, 1), dtype=np.int64),
    )
    return out[3][:, 0]


def test_noise_statistics_match_configuration():
    """A3 (generator): AR(1) at the N1 proxy-derived correlation (tau_c 0.34 s at 60 Hz, phi 0.952) with the
    heavy-tail mixture (p 0.002, k 3). n = 200,000 samples: effective n ~ n (1 - phi)/(1 + phi) = 4,900, so
    the sigma SE is ~1 % (tolerance 4 %); lag-1 ACF SE ~ 0.001 (tolerance 0.005); PSD vs the AR(1)
    spectrum."""
    phi = math.exp(-1.0 / (60.0 * 0.34))
    x = _run_noise(phi, 0.002, 3.0, 200_000)
    assert np.std(x) == pytest.approx(math.sqrt(1 + 0.002 * 8), rel=0.04)
    xc = x - x.mean()
    acf1 = float(xc[1:] @ xc[:-1] / (xc @ xc))
    acf20 = float(xc[20:] @ xc[:-20] / (xc @ xc))
    assert acf1 == pytest.approx(phi, abs=0.005)
    assert acf20 == pytest.approx(phi**20, abs=0.05)
    f, pxx = sps.welch(x, fs=60.0, nperseg=4096)
    w = 2 * np.pi * f / 60.0
    theo = (1 - phi * phi) / (1 - 2 * phi * np.cos(w) + phi * phi)
    lo, hi = (f > 0.05) & (f < 0.3), (f > 5) & (f < 25)
    ratio_meas = pxx[lo].mean() / pxx[hi].mean()
    ratio_theo = theo[lo].mean() / theo[hi].mean()
    assert ratio_meas == pytest.approx(ratio_theo, rel=0.25)


def test_noise_tails_match_the_mixture():
    """A3 (tails): white noise with the mixture p = 0.002, k = 3: excess kurtosis 3[(1 - p + p k^4)/
    (1 - p + p k^2)^2 - 1] = 0.371 and P(|x| > 4 sigma_eff) = 4.3e-4 (about 6x Gaussian). n = 400,000:
    kurtosis SE ~ 0.03 (tolerance 0.12); exceedance count expected 170, 4-sigma band 118-222."""
    p, k = 0.002, 3.0
    x = _run_noise(0.0, p, k, 400_000)
    s_eff = math.sqrt(1 - p + p * k * k)
    exp_kurt = 3 * ((1 - p + p * k**4) / (1 - p + p * k * k) ** 2 - 1)
    assert stats.kurtosis(x) == pytest.approx(exp_kurt, abs=0.12)
    pe = (1 - p) * 2 * stats.norm.sf(4 * s_eff) + p * 2 * stats.norm.sf(4 * s_eff / k)
    cnt = int(np.sum(np.abs(x) > 4 * s_eff))
    exp = pe * x.size
    assert abs(cnt - exp) < 4 * math.sqrt(exp)
    assert cnt > 3 * 2 * stats.norm.sf(4) * x.size  # well above the Gaussian rate


def test_noise_streams_are_independent_across_sensors():
    """n_indep is independent across sensors (architecture §7): lanes A and B of N1 draw from different keyed
    streams; correlation |r| < 4/sqrt(n) with n = 100,000; the same sensor id reproduces its stream
    exactly."""
    a = _run_noise(0.0, 0.0, 1.0, 100_000, "ENG.N1.A")
    b = _run_noise(0.0, 0.0, 1.0, 100_000, "ENG.N1.B")
    a2 = _run_noise(0.0, 0.0, 1.0, 100_000, "ENG.N1.A")
    assert abs(np.corrcoef(a, b)[0, 1]) < 4 / math.sqrt(a.size)
    np.testing.assert_array_equal(a, a2)
