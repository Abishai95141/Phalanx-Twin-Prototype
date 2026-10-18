"""W1.1 A2: generated turbulence PSD vs the analytic forming-filter spectra (von Kármán and Dryden).

Sample (minimal sufficient, stated before running): one run per model of n = 2**20 ticks at 240 Hz
(4,369 s) at 3,000 m (above 2,000 ft AGL: isotropic sigma_hi = 2.2 m/s, configured L), TAS 200 m/s,
moderate class. Welch, Hann window, nperseg = 2**16 (df = 0.0037 Hz), 50 % overlap -> 31 segments.
The PSD is compared in 16 log-spaced bands between 0.01 and 20 Hz (band mean of the estimate over band mean
of the target). Relative SE of a band ratio ~ sqrt(1.5 / (bins x 0.9 x segments)) (Hann-correlated bins);
pass if |ratio - 1| <= 5 SE + 0.02 (the 0.02 covers Tustin warping, which is < 2 % below 10 Hz, unit test).
The target is the implemented discretised filter |H_d|^2; its deviation from the irrational von Kármán
spectrum is bounded separately (< 5 % for 0.01 <= L w / V <= 10, unit test). The variance is checked
against sigma^2 with its own CI (effective n from the correlation time L / V).
Negative control: a 20 % gain error on the target is detected in the same bands.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from scipy import signal

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import NS_PER_S, TRUTH_DT_S, TRUTH_HZ
from phalanx.environment.climatology import Ambient
from phalanx.environment.config import load_env_config
from phalanx.environment.module import EnvironmentModule
from phalanx.environment.turbulence import MODEL_DRYDEN, MODEL_VON_KARMAN, psd_filter_discrete

N = 2**20
CHUNK = 2**16
NPERSEG = 2**16
V = 200.0
ALT = 3000.0


def _run(model: int, root: int = 0xA2):
    cfg = load_env_config().with_turbulence(model=model)
    amb = Ambient(0, 0.0, 0.0, 288.15, 101325.0, 500.0, 0.0, 0.0, 2, 0.0)
    env = EnvironmentModule("env", cfg, n_engines=1, ambient=amb, cat_c_codes=())
    rng = RngService(root, StreamRegistry(env.streams))
    env.bind(rng.scope(KeyPath.of(scenario="A2", tail="T1", sortie="S1")))
    st = env.init(env.params, env.keys)
    tv, tr = [], []
    for k0 in range(0, N, CHUNK):
        t = ((np.arange(k0, k0 + CHUNK, dtype=np.int64) * NS_PER_S) // TRUTH_HZ).astype(np.int64)
        inp = {
            "alt": np.full(CHUNK, ALT),
            "hag": np.full(CHUNK, ALT),
            "tas": np.full(CHUNK, V),
            "phase": np.full(CHUNK, 5, np.int64),
        }
        st, out = env.step_block(st, inp, t, TRUTH_DT_S)
        tv.append(out["turb_vel_body"])
        tr.append(out["turb_rate_body"])
    return cfg, np.concatenate(tv), np.concatenate(tr)


def _band_ratios(x, target_fn):
    f, p = signal.welch(x, fs=TRUTH_HZ, window="hann", nperseg=NPERSEG, noverlap=NPERSEG // 2)
    nseg = (x.size - NPERSEG) // (NPERSEG // 2) + 1
    edges = np.logspace(np.log10(0.01), np.log10(20.0), 17)
    out = []
    for lo, hi in itertools.pairwise(edges):
        m = (f >= lo) & (f < hi)
        nb = int(m.sum())
        se = np.sqrt(1.5 / (nb * 0.9 * nseg))
        out.append((lo, hi, float(np.mean(p[m]) / np.mean(target_fn(f[m]))), se))
    return out


@pytest.fixture(scope="module", params=[MODEL_VON_KARMAN, MODEL_DRYDEN], ids=["von_karman", "dryden"])
def run(request):
    return request.param, *_run(request.param)


@pytest.mark.statistical
def test_a2_gust_psd_matches_forming_filter(run):
    model, cfg, tv, tr = run
    sig, length = cfg.turbulence.sigma_hi[2], cfg.turbulence.l_hi
    for axis in (0, 1, 2):
        target = lambda f, a=axis: psd_filter_discrete(model, a, sig, length, V, f, TRUTH_DT_S)  # noqa: E731
        for lo, hi, ratio, se in _band_ratios(tv[:, axis], target):
            assert abs(ratio - 1) <= 5 * se + 0.02, (model, axis, lo, hi, ratio, se)
    # roll gust (uses sigma_w, L_w)
    target_p = lambda f: psd_filter_discrete(model, 3, sig, length, V, f, TRUTH_DT_S)  # noqa: E731
    for lo, hi, ratio, se in _band_ratios(tr[:, 0], target_p):
        assert abs(ratio - 1) <= 5 * se + 0.02, (model, "p", lo, hi, ratio, se)


@pytest.mark.statistical
def test_a2_gust_variance_matches_sigma(run):
    """Var(u_g) = sigma^2 within its CI: n_eff ~ T / (2 L / V)."""
    model, cfg, tv, _ = run
    sig, length = cfg.turbulence.sigma_hi[2], cfg.turbulence.l_hi
    n_eff = N * TRUTH_DT_S / (2 * length / V)
    se = np.sqrt(2.0 / n_eff)
    for axis in (0, 1, 2):
        r = np.var(tv[:, axis]) / sig**2
        assert abs(r - 1) <= 4 * se, (model, axis, r, se)


@pytest.mark.statistical
def test_a2_negative_control_detects_a_gain_error(run):
    model, cfg, tv, _ = run
    sig, length = cfg.turbulence.sigma_hi[2], cfg.turbulence.l_hi
    wrong = lambda f: 1.2 * psd_filter_discrete(model, 0, sig, length, V, f, TRUTH_DT_S)  # noqa: E731
    bad = [abs(r - 1) > 5 * se + 0.02 for _, _, r, se in _band_ratios(tv[:, 0], wrong)]
    assert sum(bad) >= 8  # the high-resolution bands all flag it
