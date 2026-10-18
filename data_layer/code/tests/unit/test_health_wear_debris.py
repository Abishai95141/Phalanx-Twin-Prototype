"""M10 healthy-wear oil-debris process (W2.5, C25; A-W2.5-1): per-serial gamma rate (Bennett QFDA Fe mean and
2 sigma), gamma-process increments per engine-operating second, filter debris only (oil Fe keeps its normal
SOAP slope), mechanism-level CRN, belief forks keep the healthy part.

Samples (stated before running): the rate-draw moments on 20,000 draws of one keyed generator (the mean's
99 % CI half-width is then 2.6 % of the mean for the gamma shape 0.32); module behaviour on 1 engine and 10
sorties per test (deterministic keyed draws); the CRN check on 50 serials."""

from __future__ import annotations

import numpy as np
import pytest

from phalanx.core.events import Event
from phalanx.core.rng import KeyPath, RngService, StreamRegistry
from phalanx.core.scheduler import System
from phalanx.dictionary import load_dictionary
from phalanx.health import HealthConfig, HealthModule, SortieUsage, load_health_params, sensor_bias_channels
from phalanx.health import processes as pr
from phalanx.health.module import ENG_F, ENG_I

pytestmark = pytest.mark.unit
D = load_dictionary()
P = load_health_params()
DAY = 86_400 * 10**9
SEC = 10**9


def _gen(i: int) -> np.random.Generator:
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(2025, spawn_key=(i,))))


def test_gamma_rate_draw_has_the_fleet_mean_and_sd():
    mean, sd = 0.4747, 1.6813 / 2.0
    x = np.array([pr.gamma_rate_draw(g, mean, sd) for g in [_gen(0)] for _ in range(20_000)])
    assert np.all(x > 0.0)
    se = sd / np.sqrt(x.size)
    assert abs(x.mean() - mean) <= 2.576 * se, x.mean()
    assert abs(x.std() / sd - 1.0) <= 0.08, x.std()  # sd of a gamma shape 0.32: heavy tail, wider band
    assert pr.gamma_rate_draw(_gen(1), 0.0, sd) == 0.0
    assert pr.gamma_rate_draw(_gen(1), mean, 0.0) == mean
    with pytest.raises(ValueError):
        pr.gamma_rate_draw(_gen(1), -1.0, sd)


def _usage(k: int, n: int = 1, eot: float = 3600.0) -> SortieUsage:
    def one(v: float) -> tuple[float, ...]:
        return (v,) * n

    return SortieUsage(
        sortie_id=f"KH2011-W{k}",
        flight_time_s=eot,
        eot_s=one(eot),
        tamp_s=one(300.0),
        type1=one(1.0),
        type3=one(3.0),
        type4=one(3.0),
        eftc=one(1.1),
        src_h=one(0.05),
        ps3_full=one(1.0),
        ps3_partial=one(3.0),
        ab_lights=one(2.0),
        starts=one(1.0),
        landings=1.0,
    )


def _fly(params, n_engines: int = 1, n_sorties: int = 10, eot: float = 3600.0):
    ser = tuple(f"IN20-{k:04d}" for k in range(n_engines))
    m = HealthModule("health", params, config=HealthConfig(ser, sensor_bias_channels(D)))
    sysm = System(
        [m], [], rng=RngService(0xDEB, StreamRegistry()), identity=KeyPath.of(scenario="WD", tail="KH2011")
    )
    w0 = sysm.start()
    evs = [
        Event((k + 1) * DAY, "health.sortie", "health", _usage(k, n_engines, eot).to_payload())
        for k in range(n_sorties)
    ]
    w = sysm.inject(w0, evs)
    w, _ = sysm.run(w, (n_sorties * DAY) // (SEC // 240) + 2 - w.k)
    return m, w0, w


def test_healthy_engine_sheds_filter_debris_but_oil_fe_keeps_the_normal_slope():
    _, w0, w = _fly(P)
    f0, f = w0.states["health"]["eng_f"][0], w.states["health"]["eng_f"][0]
    assert w.states["health"]["eng_i"][0, ENG_I.index["spall_on"]] == 0
    d = f[ENG_F.index["debris"]] - f0[ENG_F.index["debris"]]
    assert d > 0.0 and d == pytest.approx(f[ENG_F.index["debris_wear"]])
    # oil Fe of a healthy engine is exactly the normal SOAP slope times EOT (no double counting of wear)
    want = float(P.value("oil_fe_slope")) * 10 * 3600.0
    assert f[ENG_F.index["oil_fe"]] - f0[ENG_F.index["oil_fe"]] == pytest.approx(want, rel=1e-12)
    # the unit's rate is a build state, constant over the sorties
    assert f[ENG_F.index["wear_debris_rate"]] == f0[ENG_F.index["wear_debris_rate"]] > 0.0


def test_zero_rate_is_flat_and_the_mechanism_draws_are_separate():
    """A1 (zero rate -> flat) and mechanism-level CRN: switching the healthy-wear process off changes no
    other build or wear draw of any serial (it has its own generator indices)."""
    off = P.replace(wear_debris_mean=0.0)
    _, _, w_on = _fly(P, n_engines=50, n_sorties=3)
    _, _, w_off = _fly(off, n_engines=50, n_sorties=3)
    a, b = w_on.states["health"]["eng_f"], w_off.states["health"]["eng_f"]
    assert np.all(b[:, ENG_F.index["debris_wear"]] == 0.0)
    assert np.all(b[:, ENG_F.index["wear_debris_rate"]] == 0.0)
    keep = [j for n, j in ENG_F.index.items() if n not in ("debris", "debris_wear", "wear_debris_rate")]
    assert np.array_equal(a[:, keep], b[:, keep])
    assert np.array_equal(w_on.states["health"]["bias_drift"], w_off.states["health"]["bias_drift"])


def test_belief_fork_removes_spall_debris_but_keeps_healthy_wear():
    m, _, w = _fly(P, n_sorties=3)
    st = {k: np.array(v, copy=True) for k, v in w.states["health"].items()}
    f = st["eng_f"][0]
    f[ENG_F.index["spall_len"]] = 1.0e-3
    f[ENG_F.index["debris"]] += 5.0e-6  # spall debris on top of the healthy wear
    st["eng_i"][0, ENG_I.index["spall_on"]] = 1
    serial = m.belief_items(st)[0]
    out = m.with_belief(st, {serial: {"u_s": 10.0, "th_s": 1.0e9}}, keep_faults=False)
    g = out["eng_f"][0]
    assert g[ENG_F.index["spall_len"]] == 0.0
    assert g[ENG_F.index["debris"]] == g[ENG_F.index["debris_wear"]] > 0.0
