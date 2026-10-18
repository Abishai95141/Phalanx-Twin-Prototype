"""M07 small-signal stochastic structure (acceptance A6; AD-46; docs/behavioural_targets.md B1/B2 structure).

Setup: closed loop with the labelled TEST FIXTURE N2 governor (P + I, 60 Hz) at 90 % N2 demand, driven by the
TEST FIXTURE M03-like disturbances (AD-32/AD-46 channels [fuel_metering, combustor_eff, inlet_recovery,
shaft_load, fan_face]; AR(1) corner 2 Hz). Every run: 240 s at 240 Hz after a 10 s settle (57,600 ticks).

Estimators:
- B1 (the battery's own): 4 Hz record (every 60th tick, as a recorder word), fast = x - zero-phase
  Butterworth-4 low-pass at FC_PRIMARY = 0.2 Hz (``phalanx.validation.battery.filters.lowpass``); 960 samples,
  effective n about 2 x 1.8 Hz x 240 s = 864, so SE(r) <= (1 - r^2) / sqrt(864) <= 0.034;
- coherence: Welch segments of 4,096 at 240 Hz (28 segments with 50 % overlap; bias about 1/28 = 0.04).

The behavioural targets are proxy magnitudes; for the Tejas configuration they are structural, so the
assertions are structural:
- AD-46: the real fast-band N1-N2 correlation 0.47 lies inside the range the disturbance channels can produce
  under closed-loop governing (one mix above it, one mix below it; r is continuous in the variance mix);
  without the LP-specific fan_face path it cannot be reached (0.74 is the four-channel minimum region), and a
  fan_face that loses its LP signature (k_eta_fan_face 0.6) cannot reach it either (negative control);
- the fixture A6 mix with fan_face is less coupled than the four-channel mix;
- within-engine coherence N1-N2, T5-N2 and FF-N2 falls clearly below 1 at high frequency (1-5 Hz);
- with independent per-engine disturbances, cross-engine fast-band correlation is clearly below 1;
- negative controls: one deterministic input gives coherence ~1, common-only disturbances give
  cross-engine correlation ~1 (the round-2 over-coupling, behavioural_targets.md B1).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

from phalanx.core.rng import KeyPath, RngService, StreamDecl, StreamRegistry, Variate
from phalanx.engine.layout import U_WF
from phalanx.engine.sim import input_block, simulate, state_from_x
from phalanx.validation.battery.config import FC_PRIMARY
from phalanx.validation.battery.filters import lowpass


def _fixtures():
    path = Path(__file__).resolve().parents[1] / "integration" / "test_engine_fixtures.py"
    spec = importlib.util.spec_from_file_location("engine_fixtures_s", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_fixtures_s"] = mod
    spec.loader.exec_module(mod)
    return mod


fx = _fixtures()
Y = fx.Y
FS = 240.0
SETTLE = 240 * 10
N = 240 * 240
PAIRS = (("n1", "n2"), ("t5", "n2"), ("wf", "n2"))
N_EFF_B1 = 864
R_REAL_N1_N2 = 0.47  # docs/behavioural_targets.md B1 (DASHlink within-engine fast band)
SIGMA_FOUR = (0.004, 0.003, 0.003, 0.004, 0.0)  # the four original channels (fixture A6 levels)
SIGMA_LP = (0.0, 0.0, 0.0, 0.0017, 0.0036)  # fan_face-dominant mix (near the linear minimum, k_eta 0.2)


def _fast(x: np.ndarray) -> np.ndarray:
    b, a = signal.butter(4, 0.2 / (FS / 2), "highpass")  # 240 Hz fast band: above 0.2 Hz
    return signal.filtfilt(b, a, x - x.mean())


def _fast_b1(x: np.ndarray) -> np.ndarray:
    x4 = x[::60]
    return x4 - lowpass(x4, 4.0, FC_PRIMARY)


def _r_b1(y: np.ndarray, a: str, b: str) -> float:
    return float(np.corrcoef(_fast_b1(y[:, Y[a]]), _fast_b1(y[:, Y[b]]))[0, 1])


def _se(r: float) -> float:
    return (1.0 - r * r) / np.sqrt(N_EFF_B1)


def _band_coherence(x, y, band=(1.0, 5.0)) -> float:
    f, c = signal.coherence(x, y, fs=FS, nperseg=4096)
    sel = (f >= band[0]) & (f < band[1])
    return float(c[sel].mean())


@pytest.fixture(scope="module")
def sch():
    return fx.FixtureSchedules(fx.fixture_model())


def _governed(sch, sigma=None, common_frac=0.3, n_engines=2):
    kw = {} if sigma is None else {"sigma": sigma}
    w = fx.DisturbanceFixture(common_frac=common_frac, **kw).series(SETTLE + N, n_engines)
    gov = fx.GovernorFixture(kp=2.0, ki=1.0)
    r = fx.run_closed_loop(sch, gov, 0.9, SETTLE + N, n_engines=n_engines, w_engine=w)
    return r.y[SETTLE:]


@pytest.fixture(scope="module")
def run_independent(sch):
    return _governed(sch)


@pytest.fixture(scope="module")
def run_four(sch):
    return _governed(sch, SIGMA_FOUR, n_engines=1)[:, 0]


@pytest.mark.statistical
def test_ad46_real_n1_n2_coupling_is_inside_the_achievable_range(sch, run_four, record_property):
    """AD-46: under closed-loop governing the four original channels give a fast-band (B1) r(N1,N2) above the
    real 0.47 and a fan_face-dominant mix gives one below it (each by > 3 SE), so 0.47 is achievable."""
    y_lp = _governed(sch, SIGMA_LP, n_engines=1)[:, 0]
    r_hi, r_lo = _r_b1(run_four, "n1", "n2"), _r_b1(y_lp, "n1", "n2")
    record_property("b1_r_n1_n2_four_channels", round(r_hi, 3))
    record_property("b1_r_n1_n2_fan_face_mix", round(r_lo, 3))
    assert r_lo + 3 * _se(r_lo) < R_REAL_N1_N2 < r_hi - 3 * _se(r_hi), (r_lo, r_hi)


@pytest.mark.statistical
def test_ad46_negative_control_fan_face_without_lp_signature(sch, record_property):
    """Negative control: with k_eta_fan_face = 0.6 the fan flow and efficiency effects on N1 cancel and the
    channel moves N1 with N2; the same LP mix then stays above 0.47, so the AD-46 check can fail."""
    m = sch.model.with_p(k_eta_fan_face=0.6)
    y = _governed(fx.FixtureSchedules(m), SIGMA_LP, n_engines=1)[:, 0]
    r = _r_b1(y, "n1", "n2")
    record_property("b1_r_n1_n2_fan_face_mix_k06", round(r, 3))
    assert r - 3 * _se(r) > R_REAL_N1_N2, r


@pytest.mark.statistical
def test_a6_fan_face_path_reduces_within_engine_coupling(run_independent, run_four, record_property):
    """A6/AD-46 structure: the fixture A6 mix (the four channels plus fan_face 0.4 %) has a lower B1
    r(N1,N2) on both engines than the four-channel mix, by more than 4 SE of the difference."""
    r4 = _r_b1(run_four, "n1", "n2")
    for e in (0, 1):
        r = _r_b1(run_independent[:, e], "n1", "n2")
        record_property(f"b1_r_n1_n2_a6_e{e}", round(r, 3))
        assert r < r4 - 4 * np.hypot(_se(r), _se(r4)), (e, r, r4)


@pytest.mark.statistical
def test_within_engine_coherence_below_one_at_high_frequency(run_independent, record_property):
    """A6: coherence of N1, T5 and FF with N2 in 1-5 Hz is clearly below 1 (< 0.9) on both engines. The
    coherence in four bands (0.05-0.2, 0.2-1, 1-5, 5-20 Hz) is recorded for the report (vs frequency)."""
    for e in (0, 1):
        for a, b in PAIRS:
            c = _band_coherence(run_independent[:, e, Y[a]], run_independent[:, e, Y[b]])
            record_property(f"coh_{a}_{b}_e{e}_1_5Hz", round(c, 3))
            assert c < 0.9, (e, a, b, c)
            for lo, hi in ((0.05, 0.2), (0.2, 1.0), (5.0, 20.0)):
                cb = _band_coherence(run_independent[:, e, Y[a]], run_independent[:, e, Y[b]], (lo, hi))
                record_property(f"coh_{a}_{b}_e{e}_{lo}_{hi}Hz", round(cb, 3))


@pytest.mark.statistical
def test_cross_engine_correlation_below_one(run_independent, record_property):
    """A6/B1 structure: independent per-engine disturbances (common share 0.3) give fast-band cross-engine
    correlations clearly below 1 (< 0.8) for N1, N2, T5 and FF."""
    for k in ("n1", "n2", "t5", "wf"):
        r = np.corrcoef(_fast(run_independent[:, 0, Y[k]]), _fast(run_independent[:, 1, Y[k]]))[0, 1]
        record_property(f"xeng_corr_fast_{k}", round(float(r), 3))
        assert r < 0.8, (k, r)
    for a, b in (("n1", "n2"), ("n1", "t5"), ("n1", "wf"), ("n2", "wf")):  # within engine, reported (B1)
        record_property(f"within_b1_{a}_{b}", round(_r_b1(run_independent[:, 0], a, b), 3))


@pytest.mark.statistical
def test_negative_control_common_disturbance_locks_engines(sch):
    """Negative control: with aircraft-common disturbances only (share 1.0) the two identical engines move in
    lockstep (cross-engine fast-band correlation > 0.99): the check above can fail."""
    y = _governed(sch, common_frac=1.0)
    r = np.corrcoef(_fast(y[:, 0, Y["n2"]]), _fast(y[:, 1, Y["n2"]]))[0, 1]
    assert r > 0.99, r


@pytest.mark.statistical
def test_negative_control_single_deterministic_input_gives_unit_coherence(sch):
    """Negative control: open loop, no disturbances, one broadband fuel-command input -> a single-input system
    whose N1-N2 coherence in 1-5 Hz is ~1 (> 0.98): the deterministic over-coupling the test must detect."""
    m = sch.model
    x = sch.x_at(0.9)
    rng = RngService(0xC0DE, StreamRegistry([StreamDecl("test", "wf_noise", ("scenario",), Variate.NORMAL)]))
    z = rng.scope(KeyPath.of(scenario="m07_a6")).stream("test", "wf_noise").draws(0, N)
    b, a = signal.butter(2, 8.0 / (FS / 2))
    wf = sch.wf_ff(0.9) * (1.0 + 0.01 * signal.lfilter(b, a, z))
    u, ui = input_block(N, 1, _base(sch, 0.9), wf_cmd=wf)
    y = simulate(m, state_from_x(m, x), u, ui).y[:, 0, :]
    c = _band_coherence(y[:, Y["n1"]], y[:, Y["n2"]])
    assert c > 0.98, c


def _base(sch, n2):
    from phalanx.engine.steady import design_inputs

    u = design_inputs(sch.model)
    u[2] = sch.a8(n2)
    x = sch.x_at(n2)
    u[3], u[4] = x[10], x[11]
    u[U_WF] = sch.wf_ff(n2)
    return u


@pytest.mark.statistical
def test_report_lead_lag_ff_n2(run_independent, record_property):
    """Reported (M08's A2 owns the sign test): fast-band FF->N2 peak cross-correlation lag (positive = N2
    lags). Structural check only: the peak is within +-1 s."""
    a = _fast(run_independent[:, 0, Y["wf"]])
    b = _fast(run_independent[:, 0, Y["n2"]])
    lags = np.arange(-240, 241)
    cc = [float(np.dot(a[max(0, -k) : a.size - max(0, k)], b[max(0, k) : b.size - max(0, -k)])) for k in lags]
    lag = lags[int(np.argmax(np.abs(cc)))] / FS
    record_property("ff_n2_peak_lag_s", lag)
    assert abs(lag) <= 1.0
