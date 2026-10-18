"""Acceptance A5: event-rate Poisson tests per regime and the persistence of false alarms across flights.

Targets (report §9, architecture §6 M14 [TRANSFER]):
- immature: 0.1-1 FH between false alarms (aircraft level) -> rate in [1, 10] per FH;
- mature: ≥ 50 FH between false alarms (rate ≤ 0.02 per FH) and ≤ 1 per 1,000 flights for gas-path EHM;
- 10-18 % of false-alarm episodes persist ≥ 3 flights (67-81 % last one flight);
- a software load raises the code rate (≈ x10).

Samples and CIs (exact Poisson / binomial, 95 %):
- module-level healthy fleets, telemetry mode, 1.5 h sorties: immature 20 tails x 12 sorties = 360 FH;
  mature 40 tails x 10 sorties = 600 FH; burst 20 tails x 5 sorties per arm;
- calibration-model fleets (``phalanx.monitoring.calibrate``, the same kernel and parameters): EHM 8,000
  flights (0 events would bound the rate at 3.7e-4 per flight); persistence 2,000 units x 40 flights.
Per-tail heterogeneity (unit offsets) makes counts overdispersed relative to Poisson [TRANSFER: RADC], so the
module-level CIs are optimistic; the bands checked are wide enough that this does not decide the verdicts."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.monitoring import MonitoringConfig, MonitoringModule, load_code_table, load_monitoring_params
from phalanx.monitoring.calibrate import episode_lengths, simulate_test_fleet
from phalanx.monitoring.module import KIND_BIT

D = load_dictionary()
P = load_monitoring_params()
CODES = load_code_table(D, P)
SEC = 10**9
SORTIE_S = 5400.0
N_TESTS = sum(c.src == "internal" for c in CODES.codes)


def fleet(regime, n_tails, n_sorties, *, sw_load=False, root=0xF1EE7):
    """Per-tail outbox of healthy flights (no faults, no CIR): every BIT record is a false alarm."""
    out = []
    for tail in range(n_tails):
        cfg = MonitoringConfig.from_dictionary(D, CODES, ("E1",), regime=regime)
        m = MonitoringModule("monitoring", P, config=cfg)
        sysm = System(
            [m],
            [],
            rng=RngService(root, StreamRegistry()),
            identity=KeyPath.of(scenario="REG", tail=f"T{tail}"),
        )
        evs = [Event(0, "monitor.sw_load", "monitoring", {"sw_config_id": "SW2"})] if sw_load else []
        for k in range(n_sorties):
            t = k * 6 * 3600 * SEC + 1
            evs += [
                Event(t, "monitor.sortie_start", "monitoring", {"sortie_id": f"T{tail}-{k}"}),
                Event(
                    t + int(SORTIE_S) * SEC,
                    "monitor.sortie_end",
                    "monitoring",
                    {"flight_time_s": np.array(SORTIE_S)},
                ),
            ]
        w = sysm.inject(sysm.start(), evs)
        w, _ = sysm.run(w, n_sorties * 6 * 3600 * 240 + 4)
        out.append(w.states["monitoring"])
    return out


@pytest.fixture(scope="module")
def immature_fleet():
    return fleet("immature", 20, 12)


def n_false_alarms(states):
    return sum(int(np.count_nonzero(st["o_kind"] == KIND_BIT)) for st in states)


def poisson_ci(k, alpha=0.05):
    lo = 0.0 if k == 0 else stats.chi2.ppf(alpha / 2, 2 * k) / 2
    hi = stats.chi2.ppf(1 - alpha / 2, 2 * k + 2) / 2
    return lo, hi


@pytest.mark.statistical
def test_immature_regime_rate_in_band(immature_fleet):
    states = immature_fleet
    fh = 20 * 12 * SORTIE_S / 3600.0
    k = n_false_alarms(states)
    lo, hi = poisson_ci(k)
    assert 1.0 <= lo / fh and hi / fh <= 10.0, (k, fh, lo / fh, hi / fh)


@pytest.mark.statistical
def test_mature_regime_rate_below_requirement():
    states = fleet("mature", 40, 10)
    fh = 40 * 10 * SORTIE_S / 3600.0
    k = n_false_alarms(states)
    _, hi = poisson_ci(k)
    assert hi / fh <= 0.02, (k, fh, hi / fh)  # ≥ 50 FH between false alarms at 95 % confidence


@pytest.mark.statistical
def test_gas_path_ehm_below_one_per_1000_flights():
    """ECM-501 runs on the mature thresholds with per-engine baseline-corrected offsets ('ehm') in every
    regime: n = 8,000 engine-flights (200 engines x 40 flights). Negative control: without the baseline
    correction (raw unit offsets) marginal engines alarm repeatedly and the requirement fails."""
    alarms = simulate_test_fleet(P, regime="ehm", n_units=200, n_flights=40, entropy=501)
    k = int(alarms.sum())
    _, hi = poisson_ci(k)
    assert hi / alarms.size <= 1e-3, (k, alarms.size)
    raw = simulate_test_fleet(P, regime="mature", n_units=200, n_flights=40, entropy=501)
    assert raw.sum() > k


@pytest.mark.statistical
def test_false_alarm_persistence_3_flights(immature_fleet):
    """Calibration model, n = 2,000 units x 40 flights (immature): 10-18 % of episodes last ≥ 3 flights and
    67-81 % last one flight (RADC Cat II); the module-level fleet agrees within its sampling error."""
    ep = episode_lengths(simulate_test_fleet(P, regime="immature", n_units=2000, n_flights=40, entropy=17))
    f3 = float(np.mean(ep >= 3))
    f1 = float(np.mean(ep == 1))
    assert 0.10 <= f3 <= 0.18, (f3, ep.size)
    assert 0.67 <= f1 <= 0.81, f1
    # module-level episodes per (tail, code), n = 20 tails x 12 sorties (episodes censored at the window ends)
    states = immature_fleet
    eps = []
    for st in states:
        bit = st["o_kind"] == KIND_BIT
        for code in np.unique(st["o_code"][bit]):
            flights = sorted({int(s.split("-")[1]) for s in st["o_sortie"][bit & (st["o_code"] == code)]})
            alarms = np.zeros((1, 12), bool)
            alarms[0, flights] = True
            eps += episode_lengths(alarms).tolist()
    eps = np.array(eps)
    m3 = float(np.mean(eps >= 3))
    lo, hi = stats.binomtest(int(np.sum(eps >= 3)), eps.size).proportion_ci(0.99)
    assert lo <= 0.18 and hi >= 0.10, (m3, eps.size)


@pytest.mark.statistical
def test_module_matches_calibration_model(immature_fleet):
    """Per-test, per-flight false-alarm probability of the module (20 tails x 12 sorties x 33 tests) equals
    the calibration model's (2,000 x 40) within the module's 99 % binomial CI widened for tail heterogeneity
    (x2)."""
    states = immature_fleet
    k = sum(
        int(np.count_nonzero((st["o_kind"] == KIND_BIT) & (st["o_mech"] == 1))) for st in states
    )  # CBIT only
    n = 20 * 12 * N_TESTS
    p_model = float(simulate_test_fleet(P, regime="immature", n_units=2000, n_flights=40, entropy=17).mean())
    se = np.sqrt(p_model * (1 - p_model) / n)
    assert abs(k / n - p_model) <= 2 * 2.576 * se + 0.2 * p_model, (k / n, p_model)


@pytest.mark.statistical
def test_software_load_burst_raises_rate():
    """A software load lowers the threshold by burst_dk (code burst ≈ x10, DOT&E F-35 [TRANSFER]): calibration
    model, mature regime, n = 2,000 units x 20 flights per arm (same draws); the rate ratio lies in [5, 20]
    (95 % CI of a Poisson ratio by the conditional binomial). Module level: the reduction decays linearly to
    zero over burst_flights sorties."""
    dk = float(P.value("burst_dk"))
    base = int(simulate_test_fleet(P, regime="mature", n_units=2000, n_flights=20, entropy=9).sum())
    burst = int(
        simulate_test_fleet(P, regime="mature", n_units=2000, n_flights=20, entropy=9, k_offset=dk).sum()
    )
    ci = stats.binomtest(burst, burst + base).proportion_ci(0.95)
    lo, hi = ci.low / (1 - ci.low), ci.high / (1 - ci.high)
    assert lo <= 20.0 and hi >= 5.0 and burst / max(base, 1) >= 5.0, (base, burst)
    cfg = MonitoringConfig.from_dictionary(D, CODES, ("E1",), regime="mature")
    m = MonitoringModule("monitoring", P, config=cfg)
    sysm = System(
        [m], [], rng=RngService(1, StreamRegistry()), identity=KeyPath.of(scenario="REG", tail="T0")
    )
    evs = [Event(0, "monitor.sw_load", "monitoring", {"sw_config_id": "SW2"})]
    for k in range(12):
        t = k * 6 * 3600 * SEC + 1
        evs += [
            Event(t, "monitor.sortie_start", "monitoring", {"sortie_id": f"T0-{k}"}),
            Event(t + 60 * SEC, "monitor.sortie_end", "monitoring", {"flight_time_s": np.array(60.0)}),
        ]
    w = sysm.inject(sysm.start(), evs)
    seen = []
    for k in range(12):
        w, _ = sysm.run(w, (k * 6 * 3600 + 30) * 240 + 2 - w.k)
        seen.append(m._burst_dk(w.states["monitoring"]))
    n_b = int(P.value("burst_flights"))
    assert seen[:n_b] == pytest.approx([dk * (n_b - j) / n_b for j in range(n_b)]) and seen[n_b:] == [
        0.0,
        0.0,
    ]
