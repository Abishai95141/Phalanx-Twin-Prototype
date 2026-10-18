"""Acceptance A2: abnormal-degradation onset statistics are N-CMAPSS-like (Arias Chao et al. 2021 form,
research note faults_and_degradation.md §5):

1. the per-serial onset threshold is Gaussian (material variability) - KS test, n = 400 serials;
2. onset happens at the first flight whose cumulative usage energy crosses the threshold, so longer flights
   reach onset in fewer flights (N-CMAPSS: long-flight unit 19 cycles vs short-flight unit 36) - n = 12
   serials x 2 flight lengths through the module;
3. after onset the loss follows A(exp(a (t/τ)^b) - 1) with a ~ U(0.001, 0.003), b ~ U(1.4, 1.6) per serial,
   recovered by fitting module trajectories - n = 6 serials, 60 post-onset flights each.

The threshold mean is lowered with ParamSet.replace so onsets happen within tens of flights (the law, not the
fighter scale, is under test)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params
from phalanx.health.module import ENG_F, ENG_I

DAY = 86_400 * 10**9
P = load_health_params().replace(onset_energy_mean=20.0 * 3600.0)


def bound(serial: str, params=P):
    m = HealthModule("health", params, config=HealthConfig((serial,), ()))
    sysm = System(
        [m], [], rng=RngService(0xA2A2, StreamRegistry()), identity=KeyPath.of(scenario="S1", tail="KH2011")
    )
    return m, sysm


@pytest.mark.statistical
def test_onset_threshold_is_gaussian_per_serial():
    m, sysm = bound("E0")
    w = sysm.start()
    st = {k: np.array(v, copy=True) for k, v in w.states["health"].items()}
    thr, a, b = [], [], []
    for k in range(400):
        st["eng_serial"][0] = f"E{k}"
        m._build_engine(st, 0)
        f = st["eng_f"][0]
        thr.append(f[ENG_F.index["onset_threshold"]])
        a.append(f[ENG_F.index["onset_a"]])
        b.append(f[ENG_F.index["onset_b"]])
    thr = np.array(thr)
    mu, cv = P.value("onset_energy_mean"), P.value("onset_energy_cv")
    assert stats.kstest(thr, stats.norm(loc=float(mu), scale=float(cv * mu)).cdf).pvalue > 0.01
    assert 0.001 <= min(a) and max(a) <= 0.003 and 1.4 <= min(b) and max(b) <= 1.6
    assert stats.kstest((np.array(a) - 0.001) / 0.002, stats.uniform().cdf).pvalue > 0.01


def fly(serial: str, eot_s: float, n: int, params=P):
    _m, sysm = bound(serial, params)
    evs = [
        Event(
            (k + 1) * DAY,
            "health.sortie",
            "health",
            SortieUsage(
                sortie_id=f"S{k}",
                flight_time_s=eot_s * 0.8,
                eot_s=(eot_s,),
                tamp_s=(0.1 * eot_s,),
                type1=(1.0,),
                type3=(5.0,),
                type4=(5.0,),
                eftc=(1.0,),
                src_h=(0.05,),
                ps3_full=(0.0,),
                ps3_partial=(1.0,),
                ab_lights=(4.0,),
                starts=(1.0,),
            ).to_payload(),
        )
        for k in range(n)
    ]
    w = sysm.inject(sysm.start(), evs)
    traj = []  # traj[i] = state after sortie i+1
    for k in range(n):
        # run up to and including the dispatch step of sortie k (events at (k+1) days)
        w, _ = sysm.run(w, (k + 1) * 240 * 86_400 + 1 - w.k)
        st = w.states["health"]
        assert int(st["clock"][0]) == k + 1
        traj.append(
            (int(st["eng_i"][0][ENG_I.index["onset"]]), float(st["eng_f"][0][ENG_F.index["abn_hpt"]]))
        )
    return w.states["health"], traj


@pytest.mark.statistical
def test_onset_at_first_crossing_and_earlier_for_long_flights():
    w_tamp = P.value("onset_tamp_weight")
    onsets = {}
    for eot in (1800.0, 5400.0):
        e_flight = eot * (1.0 + w_tamp * 0.1)
        res = []
        for k in range(12):
            st, traj = fly(f"E{k}", eot, 50)
            thr = st["eng_f"][0][ENG_F.index["onset_threshold"]]
            first = next((i + 1 for i, (o, _) in enumerate(traj) if o), None)
            energy, expected = (
                0.0,
                None,
            )  # first flight whose cumulative energy (same float sums) >= threshold
            for i in range(50):
                energy += e_flight
                if energy >= thr:
                    expected = i + 1
                    break
            assert first == expected
            res.append(first or 51)
        onsets[eot] = np.mean(res)
    assert onsets[5400.0] < onsets[1800.0]  # long flights: earlier onset in flights


@pytest.mark.statistical
def test_post_onset_trajectory_recovers_ncmapss_parameters():
    tau, amp = P.value("onset_tau"), P.value("onset_amplitude")
    for k in range(6):
        st, traj = fly(f"F{k}", 7200.0, 70)
        loss = np.array([x for o, x in traj if o])
        t = np.arange(1, loss.size + 1, dtype=float)
        y = np.log(np.log1p(loss / amp))  # = ln a + b ln(t/τ)
        slope, intercept = np.polyfit(np.log(t / tau), y, 1)
        a_true = st["eng_f"][0][ENG_F.index["onset_a"]]
        b_true = st["eng_f"][0][ENG_F.index["onset_b"]]
        assert slope == pytest.approx(b_true, abs=1e-9) and math.exp(intercept) == pytest.approx(
            a_true, rel=1e-9
        )
        assert 1.4 <= slope <= 1.6 and 0.001 <= math.exp(intercept) <= 0.003
        assert np.all(np.diff(loss) > 0)
