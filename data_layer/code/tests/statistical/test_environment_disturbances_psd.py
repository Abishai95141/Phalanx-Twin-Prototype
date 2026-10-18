"""W1.1 A3: AD-32 disturbance PSD and coherence reproduce the configured targets.

What must hold (docs/behavioural_targets.md): engines correlated but not in lockstep (cross-engine coherence
< 1, configurable), and channels within one engine only partly coupled (within-engine cross-channel
coherence < 1, configurable). Cases: common-only (target coherence 1), unit-only (0), mixed common + unit
with different spectra (frequency-dependent target), within-engine cross-channel via a unit-level factor,
for n_engines = 1, 2 and 4; plus every channel of the shipped placeholder configuration.

**Targets are continuous-time and analytic (E1 verifier §2, E1-HY item 5).** They never use the kernel's
discretised matrices (``DisturbanceBank.phi``/``lq``/``instance_psd``/``cross_psd``/``coherence``/``gain``):

- each factor's unit-variance **continuous-time autocovariance** in closed form, from the configured
  ``Factor`` fields only: OU ``exp(-|t|/tau)``; OU2 (two equal first-order stages) ``(1 + |t|/tau)
  exp(-|t|/tau)``; resonant (unit-variance damped oscillator) ``exp(-zeta w |t|) (cos(w_d t) +
  zeta/sqrt(1 - zeta^2) sin(w_d |t|))`` (critically/over-damped forms as well);
- the channel cross-covariance ``sum_i L_ij L_ik r_i(t)`` over the factor instances that load both channels
  (an aircraft-scope factor is one instance shared by every unit; a unit-scope factor one instance per
  unit), with the loadings taken from the ``Factor``s;
- the **expected Welch estimate** at every frequency bin: ``2/(fs sum w^2) sum_k r(k/fs) c_w(k)
  cos(2 pi m k / N)`` with ``c_w`` the Hann window's autocorrelation. Sampling the continuous
  autocovariance at the tick lags gives the sampled process's exact second moments, so this expectation
  contains the aliasing and the window leakage and nothing else: the only remaining difference between
  estimate and target is estimation noise. (Mean removal does not touch bins >= 2 of a Hann window; the
  first band starts at bin 3.)

Only the output **layout** (``bank.out_index``) is read from the module, to find the data columns.

Sample (stated before running): one run per case of n = 2**20 ticks at 240 Hz (4,369 s). Welch/coherence
with a Hann window, nperseg = 2**13 (df = 0.0293 Hz), 50 % overlap -> 255 segments. Comparison in 12
log-spaced bands, 0.06..30 Hz (band means of 1, 2, 4, 7, 11, 18, 31, 53, 87, 147, 247 and 413 bins).

**Thresholds and their justification (E1-HY item 5).**
- PSD: |ratio - 1| <= 5 SE with the exact standard error of a Welch band mean for a Gaussian process that
  is locally white over +-3 bins: SE^2 = sum_{m,m'} P_m P_m' rho(m - m') / (NSEG (sum P_m)^2), rho from the
  Hann window (same-segment and 50 %-overlap correlations, ``RHO``), P the target (``band_se``). The former
  rule (SE = sqrt(1.5 / (bins x 0.9 NSEG)) plus an additive 0.02) was off by -20 % (1 bin) to +12 % (wide
  bands) and its 0.02 floor more than doubled the tolerance in the high bands; with the exact expected
  estimate as target there is no bias to absorb, so the floor is gone.
  Monte Carlo check (E1-HY, scratch run, n = 30 independent root seeds x the mixed (4 channels) and the
  shipped (14 channels) configurations, 6,480 standardised band errors): SD(z) per band 0.81-1.11 and
  0.93-1.07, overall 0.98 and 1.00; |mean z| <= 0.22; max |z| 3.94; none beyond 5.
  The file makes about 720 band comparisons (about 42 PSD channels and 18 coherence pairs, 12 bands each);
  at 5 SE the family-wise false-alarm probability is about 720 x 5.7e-7 = 4e-4 (Bonferroni, Gaussian band
  means).
- Coherence: |est - target| <= 5 SE_c + bias, SE_c = sqrt(2) g (1 - g^2) x (flat-band relative SE) with
  g = sqrt(target), floored by the zero-coherence spread (Beta(1, K - 1), spread 1/K per bin, averaged over
  the band); bias = (1 - target)^2 / K (the positive bias of the magnitude-squared estimator); K = NSEG /
  rho(0), the overlap-corrected number of independent segments.

Negative controls: wrong coherence targets are rejected; a target built with each factor's tau doubled
(the E1 verifier's 2 x tau mutant, applied to the target instead of the kernel) is rejected with the
smallest violation many SE beyond the threshold.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
from scipy import signal

from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.time import NS_PER_S, TRUTH_DT_S, TRUTH_HZ
from phalanx.environment.config import load_env_config
from phalanx.environment.disturbances import (
    FORM_OU,
    FORM_OU2,
    FORM_RESONANT,
    GROUP_ENGINE,
    GROUP_HYD,
    N_ENGINE_CHANNELS,
    SCOPE_AIRCRAFT,
    SCOPE_UNIT,
    Factor,
)
from phalanx.environment.module import EnvironmentModule

N = 2**20
CHUNK = 2**16
NPERSEG = 2**13
FUEL, COMB, INLET, SHAFT, FAN, BLEED = 0, 1, 2, 3, 4, 5  # disturbances.ENGINE_CHANNELS (AD-46)
CFG = load_env_config()
Z_MAX = 5.0


def _eng(fid, scope, form, *, tau=0.0, omega=0.0, zeta=0.0, **loads):
    vec = [0.0] * 6
    for name, val in loads.items():
        vec[
            {"fuel": FUEL, "comb": COMB, "inlet": INLET, "shaft": SHAFT, "fan": FAN, "bleed": BLEED}[name]
        ] = val
    return Factor(fid, scope, GROUP_ENGINE, form, tau, omega, zeta, tuple(vec))


# --------------------------------------------------------------------- continuous-time analytic targets
def ct_autocov(f: Factor, lag_s: np.ndarray) -> np.ndarray:
    """Unit-variance autocovariance of the factor's continuous-time shaping filter (closed form, from the
    ``Factor`` fields only)."""
    t = np.abs(np.asarray(lag_s, dtype=np.float64))
    if f.form == FORM_OU:
        return np.exp(-t / f.tau_s)
    if f.form == FORM_OU2:
        return (1.0 + t / f.tau_s) * np.exp(-t / f.tau_s)
    if f.form == FORM_RESONANT:
        w, z = f.omega_rad_s, f.zeta
        if z < 1.0:
            wd = w * math.sqrt(1.0 - z * z)
            return np.exp(-z * w * t) * (np.cos(wd * t) + z / math.sqrt(1.0 - z * z) * np.sin(wd * t))
        if z == 1.0:
            return (1.0 + w * t) * np.exp(-w * t)
        s = math.sqrt(z * z - 1.0)
        l1, l2 = w * (z - s), w * (z + s)
        return (l2 * np.exp(-l1 * t) - l1 * np.exp(-l2 * t)) / (l2 - l1)
    raise ValueError(f.form)


_WIN = signal.get_window("hann", NPERSEG)
_CW = np.correlate(_WIN, _WIN, mode="full")[NPERSEG - 1 :]  # window autocorrelation, lags 0..N-1
_LAGS = np.arange(NPERSEG) / TRUTH_HZ
FREQ = np.fft.rfftfreq(NPERSEG, 1.0 / TRUTH_HZ)


def expected_welch(r_lags: np.ndarray) -> np.ndarray:
    """Expected one-sided Welch (Hann, density scaling) estimate on ``FREQ`` of a stationary process whose
    autocovariance at lags 0..N-1 ticks is ``r_lags``."""
    a = r_lags * _CW
    s = 2.0 * np.real(np.fft.rfft(a)) - a[0]  # sum over lags -(N-1)..N-1 of a(|k|) cos(2 pi m k / N)
    s = s / (TRUTH_HZ * float(np.sum(_WIN**2)))
    s[1:-1] *= 2.0  # one-sided: every bin but DC and Nyquist doubled (scipy.signal.welch convention)
    return s


class CtTargets:
    """Expected Welch auto/cross spectra of the configured factor model on ``FREQ``, built from the
    ``Factor`` list and the unit counts (layout from the module only)."""

    def __init__(self, factors, n_engines: int, n_hyd: int, out_index, tau_scale: float = 1.0):
        self.n_engines, self.n_hyd = n_engines, n_hyd
        self._unit_psd: dict[tuple[int, int], np.ndarray] = {}
        self._load: dict[int, dict[tuple[int, int], float]] = {}
        for f in factors:
            g = Factor(
                f.fid, f.scope, f.group, f.form, f.tau_s * tau_scale, f.omega_rad_s, f.zeta, f.loadings
            )
            psd = expected_welch(ct_autocov(g, _LAGS))
            n_units = n_engines if f.group == GROUP_ENGINE else n_hyd
            n_ch = N_ENGINE_CHANNELS if f.group == GROUP_ENGINE else 1
            for u in range(n_units):
                key = (f.fid, -1 if f.scope == SCOPE_AIRCRAFT else u)
                self._unit_psd[key] = psd
                for ch in range(n_ch):
                    if f.loadings[ch] != 0.0:
                        j = out_index(f.group, u, ch)
                        self._load.setdefault(j, {})[key] = float(f.loadings[ch])

    def cross(self, j: int, k: int) -> np.ndarray:
        lj, lk = self._load.get(j, {}), self._load.get(k, {})
        s = np.zeros_like(FREQ)
        for key in lj.keys() & lk.keys():
            s = s + lj[key] * lk[key] * self._unit_psd[key]
        return s

    def coherence(self, j: int, k: int) -> np.ndarray:
        """Target coherence per bin; channels without content give 0."""
        sjj, skk = self.cross(j, j), self.cross(k, k)
        den = sjj * skk
        return np.divide(self.cross(j, k) ** 2, den, out=np.zeros_like(den), where=den > 0)

    def variance(self, j: int) -> float:
        return float(sum(v * v for v in self._load.get(j, {}).values()))

    def coherence_at(self, j: int, k: int, f_hz) -> np.ndarray:
        return np.interp(np.atleast_1d(f_hz), FREQ, self.coherence(j, k))


def _run(factors, n_engines, root=0xA3):
    cfg = CFG.with_factors(tuple(factors))
    env = EnvironmentModule(
        "env", cfg, n_engines=n_engines, engine_serials=[f"S{k}" for k in range(n_engines)], cat_c_codes=()
    )
    rng = RngService(root, StreamRegistry(env.streams))
    env.bind(rng.scope(KeyPath.of(scenario="A3", tail="T1", sortie="S1")))
    st = env.init(env.params, env.keys)
    rows = []
    for k0 in range(0, N, CHUNK):
        t = (np.arange(k0, k0 + CHUNK, dtype=np.int64) * NS_PER_S) // TRUTH_HZ
        inp = {
            "alt": np.zeros(CHUNK),
            "hag": np.zeros(CHUNK),
            "tas": np.zeros(CHUNK),
            "phase": np.zeros(CHUNK, np.int64),
        }
        st, out = env.step_block(st, inp, t, TRUTH_DT_S)
        e = n_engines
        rows.append(
            np.concatenate([out["w_engine"].reshape(CHUNK, 5 * e), out["w_bleed_pto"], out["w_hyd"]], axis=1)
        )
    bank = env.bank
    ct = CtTargets(cfg.factors, n_engines, env.n_hyd, bank.out_index)
    return bank, ct, np.concatenate(rows)


EDGES = np.logspace(np.log10(0.06), np.log10(30.0), 13)
NSEG = (N - NPERSEG) // (NPERSEG // 2) + 1


def _window_correlations() -> np.ndarray:
    """rho(d) = correlation of Welch periodogram ordinates d bins apart for locally white noise, summed over
    the segment overlap: rho0(d) + 2 (1 - 1/NSEG) rho1(d), with rho0 = |W2(d)|^2 / (sum w^2)^2 (same
    segment) and rho1 the same for the products of 50 %-overlapping segments (exact for the Hann window)."""
    d = NPERSEG // 2
    s2 = float(np.sum(_WIN**2))
    rho0 = np.abs(np.fft.fft(_WIN**2)) ** 2 / s2**2
    p = np.zeros(NPERSEG)
    p[: NPERSEG - d] = _WIN[d:] * _WIN[: NPERSEG - d]
    rho1 = np.abs(np.fft.fft(p)) ** 2 / s2**2
    return (rho0 + 2.0 * (1.0 - 1.0 / NSEG) * rho1)[:4]  # zero beyond 3 bins for Hann (< 1e-3 at 3)


RHO = _window_correlations()  # [1.055, 0.484, 0.042, 0.0016] for the Hann window, 50 % overlap
K_SEG = NSEG / RHO[0]  # equivalent independent segments of one bin (overlap-corrected)


def _bands():
    for lo, hi in itertools.pairwise(EDGES):
        m = (FREQ >= lo) & (FREQ < hi)
        yield lo, hi, m, int(m.sum())


def band_se(tgt_band: np.ndarray) -> float:
    """Relative standard error of a Welch band mean whose expected bins are ``tgt_band``: sqrt(sum_{m,m'}
    P_m P_m' rho(m - m') / NSEG) / sum P_m (Gaussian process, locally white within +-3 bins). For a flat
    band of nb bins this is sqrt(c(nb) / (nb NSEG)) with c rising from 1.06 (nb = 1) to 2.11 (nb >= 100);
    weighting by the target accounts for the spectrum's slope inside wide bands."""
    p = np.asarray(tgt_band, dtype=np.float64)
    acc = RHO[0] * float(np.dot(p, p))
    for d in range(1, len(RHO)):
        acc += 2.0 * RHO[d] * float(np.dot(p[:-d], p[d:])) if p.size > d else 0.0
    return math.sqrt(acc / NSEG) / float(np.sum(p))


def psd_z(ct, x, j) -> list[tuple[float, float, float]]:
    """(lo, hi, z) per band: z = (ratio - 1) / SE of the Welch band mean against the analytic target."""
    f, p = signal.welch(x[:, j], fs=TRUTH_HZ, window="hann", nperseg=NPERSEG, noverlap=NPERSEG // 2)
    assert np.array_equal(f, FREQ)
    tgt = ct.cross(j, j)
    out = []
    for lo, hi, m, _nb in _bands():
        r = float(np.mean(p[m]) / np.mean(tgt[m]))
        out.append((lo, hi, (r - 1.0) / band_se(tgt[m])))
    return out


def check_psd(ct, x, j):
    return [(lo, hi, z) for lo, hi, z in psd_z(ct, x, j) if abs(z) > Z_MAX]


def check_coherence(ct, x, j, k, target_fn=None):
    f, c = signal.coherence(
        x[:, j], x[:, k], fs=TRUTH_HZ, window="hann", nperseg=NPERSEG, noverlap=NPERSEG // 2
    )
    assert np.array_equal(f, FREQ)
    tgt_all = target_fn(FREQ) if target_fn else ct.coherence(j, k)
    bad = []
    for lo, hi, m, nb in _bands():
        tgt = float(np.mean(tgt_all[m]))
        est = float(np.mean(c[m]))
        g = np.sqrt(max(tgt, 0.0))
        rel = band_se(np.ones(nb))  # flat-band relative SE: 1 / sqrt(effective independent ordinates)
        se = np.sqrt(2.0) * g * (1 - tgt) * rel
        se0 = math.sqrt(NSEG) * rel / K_SEG  # zero coherence: Beta(1, K-1) spread 1/K, averaged over the band
        bias = (1 - tgt) ** 2 / K_SEG
        if abs(est - tgt) > Z_MAX * max(se, se0) + bias:
            bad.append((lo, hi, est, tgt))
    return bad


@pytest.mark.statistical
def test_a3_bands_and_targets_are_well_formed():
    """Every band holds at least one bin, and the analytic expected-Welch target integrates exactly to the
    configured unit variance (OU, OU2, under- and over-damped resonant factors; Parseval over the one-sided
    grid: aliasing folds the tail above Nyquist back in, so nothing is lost)."""
    counts = [nb for *_, nb in _bands()]
    assert min(counts) >= 1 and sum(counts) > 1000, counts
    for f in (
        _eng(1, SCOPE_UNIT, FORM_OU, tau=0.1, fuel=1.0),
        _eng(2, SCOPE_UNIT, FORM_OU2, tau=0.2, fuel=1.0),
        _eng(3, SCOPE_UNIT, FORM_RESONANT, omega=12.0, zeta=0.3, fuel=1.0),
        _eng(4, SCOPE_UNIT, FORM_RESONANT, omega=5.0, zeta=1.4, fuel=1.0),
    ):
        s = expected_welch(ct_autocov(f, _LAGS))
        assert abs(np.sum(s) * (FREQ[1] - FREQ[0]) - 1.0) < 1e-9, f


@pytest.mark.statistical
def test_a3_common_only_gives_unit_coherence_across_engines():
    bank, ct, x = _run([_eng(1, SCOPE_AIRCRAFT, FORM_OU, tau=0.5, fuel=0.01)], 2)
    j0, j1 = bank.out_index(GROUP_ENGINE, 0, FUEL), bank.out_index(GROUP_ENGINE, 1, FUEL)
    assert np.array_equal(x[:, j0], x[:, j1])  # one shared realisation
    assert check_psd(ct, x, j0) == []
    assert np.allclose(ct.coherence_at(j0, j1, [0.1, 1.0, 10.0]), 1.0)


@pytest.mark.statistical
def test_a3_unit_only_gives_zero_coherence_across_engines():
    bank, ct, x = _run([_eng(1, SCOPE_UNIT, FORM_OU, tau=0.5, fuel=0.01)], 2)
    j0, j1 = bank.out_index(GROUP_ENGINE, 0, FUEL), bank.out_index(GROUP_ENGINE, 1, FUEL)
    assert check_psd(ct, x, j0) == [] and check_psd(ct, x, j1) == []
    assert np.allclose(ct.coherence_at(j0, j1, [0.1, 1.0]), 0.0)
    assert check_coherence(ct, x, j0, j1) == []


@pytest.fixture(scope="module")
def mixed():
    """Aircraft-common slow component + engine-specific fast component on fuel metering; a unit-level
    factor coupling fuel metering and shaft load inside each engine; a resonant shaft component."""
    fs = [
        _eng(1, SCOPE_AIRCRAFT, FORM_OU, tau=2.0, fuel=0.006),
        _eng(2, SCOPE_UNIT, FORM_OU2, tau=0.2, fuel=0.008),
        _eng(3, SCOPE_UNIT, FORM_OU, tau=0.5, fuel=0.004, shaft=0.006),
        _eng(4, SCOPE_UNIT, FORM_RESONANT, omega=12.0, zeta=0.3, shaft=0.005),
    ]
    return (*_run(fs, 2), fs)


@pytest.mark.statistical
def test_a3_mixed_cross_engine_coherence_matches_frequency_dependent_target(mixed):
    bank, ct, x, _ = mixed
    j0, j1 = bank.out_index(GROUP_ENGINE, 0, FUEL), bank.out_index(GROUP_ENGINE, 1, FUEL)
    coh = ct.coherence_at(j0, j1, [0.06, 0.3, 3.0])
    assert coh[0] > 0.3 and np.all(coh[1:] < 0.05)  # correlated at low frequency, never lockstep
    assert check_psd(ct, x, j0) == []
    assert check_coherence(ct, x, j0, j1) == []


@pytest.mark.statistical
def test_a3_within_engine_cross_channel_coherence_below_one(mixed):
    bank, ct, x, _ = mixed
    jf, js = bank.out_index(GROUP_ENGINE, 0, FUEL), bank.out_index(GROUP_ENGINE, 0, SHAFT)
    coh = ct.coherence_at(jf, js, [0.06, 1.0, 5.0])
    assert np.all(coh > 0.02) and np.all(coh < 0.9)
    assert check_psd(ct, x, js) == []
    assert check_coherence(ct, x, jf, js) == []
    # cross-engine shaft channels share nothing: zero target coherence
    js1 = bank.out_index(GROUP_ENGINE, 1, SHAFT)
    assert check_coherence(ct, x, js, js1) == []


@pytest.mark.statistical
def test_a3_negative_control_wrong_target_is_rejected(mixed):
    bank, ct, x, _ = mixed
    j0, j1 = bank.out_index(GROUP_ENGINE, 0, FUEL), bank.out_index(GROUP_ENGINE, 1, FUEL)
    assert check_coherence(ct, x, j0, j1, target_fn=lambda f: np.zeros_like(f)) != []
    assert check_coherence(ct, x, j0, j1, target_fn=lambda f: np.ones_like(f)) != []


@pytest.mark.statistical
def test_a3_negative_control_doubled_tau_target_fails_clearly(mixed):
    """The E1 verifier's 2 x tau mutant, seen from the target side: against a target whose every tau is
    doubled, the true data violate the 5-SE bar by a wide margin on both mixed channels (worst |z| >= 25,
    i.e. > 5x the threshold), so a kernel that realised 2 x tau would fail just as clearly against the true
    target (the kernel-side mutant run is in the E1-HY report)."""
    bank, _, x, fs = mixed
    wrong = CtTargets(fs, 2, bank.n_hyd, bank.out_index, tau_scale=2.0)
    for ch in (FUEL, SHAFT):
        j = bank.out_index(GROUP_ENGINE, 0, ch)
        worst = max(abs(z) for *_, z in psd_z(wrong, x, j))
        assert worst >= 5 * Z_MAX, (ch, worst)


@pytest.mark.statistical
def test_a3_single_engine_and_hydraulic_channels():
    fs = [
        _eng(1, SCOPE_AIRCRAFT, FORM_OU, tau=1.0, inlet=0.003, bleed=0.004),
        _eng(2, SCOPE_UNIT, FORM_OU, tau=0.3, inlet=0.002, comb=0.002),
        Factor(3, SCOPE_AIRCRAFT, GROUP_HYD, FORM_OU, 0.5, 0.0, 0.0, (1e-5,)),
        Factor(4, SCOPE_UNIT, GROUP_HYD, FORM_OU, 0.3, 0.0, 0.0, (2e-5,)),
    ]
    bank, ct, x = _run(fs, 1)
    n_out = x.shape[1]
    for j in range(n_out):
        if ct.variance(j) > 0:
            assert check_psd(ct, x, j) == [], j
    ji, jb = bank.out_index(GROUP_ENGINE, 0, INLET), bank.out_index(GROUP_ENGINE, 0, BLEED)
    jc = bank.out_index(GROUP_ENGINE, 0, COMB)
    assert check_coherence(ct, x, ji, jb) == [] and check_coherence(ct, x, ji, jc) == []
    h0, h1 = bank.out_index(GROUP_HYD, 0, 0), bank.out_index(GROUP_HYD, 1, 0)
    assert 0.0 < float(np.mean(ct.coherence_at(h0, h1, [0.1, 1.0]))) < 1.0
    assert check_coherence(ct, x, h0, h1) == []


@pytest.mark.statistical
def test_a3_shipped_placeholder_configuration_reproduces_its_targets():
    bank, ct, x = _run(CFG.factors, 2)
    for j in range(x.shape[1]):
        if ct.variance(j) > 0:
            assert check_psd(ct, x, j) == [], j
    j0, j1 = bank.out_index(GROUP_ENGINE, 0, INLET), bank.out_index(GROUP_ENGINE, 1, INLET)
    assert check_coherence(ct, x, j0, j1) == []


@pytest.mark.statistical
def test_a3_four_engine_proxy_topology_reproduces_targets():
    """AD-43 proxy (n_engines = 4, W2.4 identifies the values): with the shipped placeholder configuration
    every engine pair has the same configured cross-engine coherence (< 1) and each engine's channels keep
    their configured within-engine coherence. Same sample and bars as the other cases (n = 2**20 ticks)."""
    bank, ct, x = _run(CFG.factors, 4)
    for e in range(4):
        for c in (FUEL, INLET, SHAFT, FAN):
            j = bank.out_index(GROUP_ENGINE, e, c)
            if ct.variance(j) > 0:
                assert check_psd(ct, x, j) == [], (e, c)
    f = [0.06, 0.5, 5.0]
    for a, b in itertools.combinations(range(4), 2):
        ja, jb = bank.out_index(GROUP_ENGINE, a, FUEL), bank.out_index(GROUP_ENGINE, b, FUEL)
        assert np.all(ct.coherence_at(ja, jb, f) < 1.0)
        assert check_coherence(ct, x, ja, jb) == [], (a, b)
    jf, js = bank.out_index(GROUP_ENGINE, 3, FUEL), bank.out_index(GROUP_ENGINE, 3, SHAFT)
    if ct.variance(jf) > 0 and ct.variance(js) > 0:
        assert np.all(ct.coherence_at(jf, js, f) < 1.0)
        assert check_coherence(ct, x, jf, js) == []


@pytest.mark.statistical
def test_a3_fan_face_common_plus_engine_specific():
    """AD-46: the LP-specific fan_face column has an aircraft-common and an engine-specific component with
    different spectra, so its cross-engine coherence is frequency dependent and < 1; within an engine it is
    independent of the core channels unless a factor is shared (here a unit factor loads fan_face and shaft
    load: within-engine coherence < 1 at its configured target). n_engines = 2; same sample and bars."""
    fs = [
        _eng(1, SCOPE_AIRCRAFT, FORM_OU, tau=1.0, fan=0.002),
        _eng(2, SCOPE_UNIT, FORM_OU2, tau=0.2, fan=0.004),
        _eng(3, SCOPE_UNIT, FORM_OU, tau=0.5, fan=0.002, shaft=0.004),
        _eng(4, SCOPE_UNIT, FORM_OU, tau=0.3, fuel=0.005),
    ]
    bank, ct, x = _run(fs, 2)
    f0, f1 = bank.out_index(GROUP_ENGINE, 0, FAN), bank.out_index(GROUP_ENGINE, 1, FAN)
    coh = ct.coherence_at(f0, f1, [0.06, 0.3, 3.0])
    assert coh[0] > 0.05 and np.all(coh < 1.0) and coh[2] < coh[0]
    for j in (f0, f1):
        assert check_psd(ct, x, j) == []
    assert check_coherence(ct, x, f0, f1) == []
    js = bank.out_index(GROUP_ENGINE, 0, SHAFT)
    c_fs = ct.coherence_at(f0, js, [0.06, 1.0])
    assert np.all(c_fs > 0.02) and np.all(c_fs < 0.9)
    assert check_coherence(ct, x, f0, js) == []
    jf = bank.out_index(GROUP_ENGINE, 0, FUEL)  # no shared factor: zero target coherence
    assert float(np.max(ct.coherence_at(f0, jf, [0.1, 1.0]))) == 0.0
    assert check_coherence(ct, x, f0, jf) == []
