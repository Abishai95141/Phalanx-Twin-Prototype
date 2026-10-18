"""Unit tests of the per-flight battery estimators on constructed signals with known answers."""

from __future__ import annotations

import pickle

import numpy as np
import pytest

from phalanx.validation.battery import BatteryConfig, flight_stats, flight_stats_many
from phalanx.validation.battery.config import A_GRID, LAG_PAIRS, STEP_RESP
from phalanx.validation.battery.evaluate import b5_group
from phalanx.validation.battery.stats import (
    _lag,
    airborne_mask,
    b1_stats,
    b4_granger,
    b5_moments,
    b6_stats,
    find_steps,
)
from phalanx.validation.flightdata import DASHLINK_UNITS, FlightRecord
from phalanx.validation.testing import REFERENCE_TAIL, control_flight

pytestmark = pytest.mark.unit
CFG = BatteryConfig()


def _gen(*key: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(99, spawn_key=key)))


def _record(Y: dict[str, np.ndarray], n: int, theta=None, delta=None, phase=None, pla=None) -> FlightRecord:
    return FlightRecord(
        flight_id="t",
        rate_hz=4.0,
        outputs=Y,
        pla=np.full((4, n), 60.0) if pla is None else pla,
        theta=np.ones(n) if theta is None else theta,
        delta=np.ones(n) if delta is None else delta,
        phase=np.full(n, 5) if phase is None else phase,
        units=DASHLINK_UNITS,
    )


def test_lag_sign_and_size():
    """B2 convention: positive lag = the second channel lags the first; resolution 1 sample = 0.25 s."""
    x = _gen(1).standard_normal(4000)
    for k in (0, 1, 3, 7):
        y = np.r_[np.zeros(k), x[: x.size - k]]
        assert _lag(x, y, 40, 4.0) == pytest.approx(k / 4.0)
        assert _lag(y, x, 40, 4.0) == pytest.approx(-k / 4.0)


def test_lag_window_is_plus_minus_10_s():
    x = _gen(2).standard_normal(4000)
    y = np.r_[np.zeros(60), x[:-60]]  # 15 s: outside the pre-registered +-10 s window
    assert abs(_lag(x, y, CFG.lag_samples, 4.0)) <= 10.0
    assert CFG.lag_samples == 40


def test_airborne_rule_is_strictly_above_25_percent():
    n = 10
    N1 = np.full((4, n), 30.0)
    N1[2, 3] = 25.0  # exactly 25 % on one engine -> not airborne
    Y = {"N1": N1}
    m = airborne_mask(Y, CFG)
    assert m.sum() == n - 1 and not m[3]


def test_b1_needs_600_airborne_samples():
    g = _gen(3)
    n = 1200
    Y = {f: 50 + g.standard_normal((4, n)) for f in ("N1", "N2", "EGT", "FF")}
    assert b1_stats(Y, CFG) is not None
    Y["N1"][:, 599:] = 10.0  # only 599 airborne samples left
    assert b1_stats(Y, CFG) is None


def test_b1_separates_slow_and_fast_coupling():
    """Two channels sharing only a slow component are correlated in the slow band, not in the fast band."""
    g = _gen(4)
    n = 4000
    t = np.arange(n) / 4.0
    slow = 5 * np.sin(2 * np.pi * t / 200.0)
    Y = {f: 60 + slow + g.standard_normal((4, n)) for f in ("N1", "N2", "EGT", "FF")}
    s, f = b1_stats(Y, CFG)
    assert s.shape == f.shape == (120,)
    assert np.median(s) > 0.9 and abs(np.median(f)) < 0.1


def test_find_steps_detects_clean_step_and_rejects_noisy_pre_window():
    pla = np.full(800, 40.0)
    pla[400:] = 50.0
    steps = find_steps(pla)
    assert len(steps) == 1
    j, pm, qm = steps[0]
    assert j == 400 and pm == 40.0 and qm == 50.0
    noisy = pla.copy()
    noisy[370:400] = 40.0 + 1.5 * (np.arange(30) % 2)  # PLA range 1.5 deg > 1 deg in the 10 s before
    assert find_steps(noisy) == []


def test_b3_steps_recover_first_order_time_constant():
    """FOPDT fit on an exact first-order response returns its tau, with the right response/direction codes."""
    n, tau = 2000, 2.0
    t = np.arange(n) / 4.0
    pla = np.full((4, n), 40.0)
    pla[:, 1000:] = 60.0
    resp = np.where(t >= 250.0, 1 - np.exp(-(t - 250.0) / tau), 0.0)
    Y = {
        "N1": 60 + 20 * resp + np.zeros((4, 1)),
        "N2": 70 + 10 * resp + np.zeros((4, 1)),
        "EGT": 500 + 100 * resp + np.zeros((4, 1)),
        "FF": 2000 + 800 * resp + np.zeros((4, 1)),
    }
    st = flight_stats(_record(Y, n, pla=pla), CFG).b3_steps
    assert st.shape == (12, 3)  # 4 engines x (N1, FF, EGT), one accel step each
    assert set(st[:, 0].astype(int)) == {STEP_RESP.index(g) for g in ("N1", "FF", "EGT")}
    assert np.all(st[:, 1] == 0)  # accel
    np.testing.assert_allclose(st[:, 2], tau, rtol=1e-3)


def test_b4_granger_direction():
    """FF drives N2 with a one-sample lag: log F(FF->N2) is far larger than log F(N2->FF)."""
    g = _gen(5)
    n = 3000
    e = g.standard_normal((4, n))
    dff = e[0]
    dn2 = np.r_[0.0, 0.8 * dff[:-1]] + 0.3 * e[1]
    Y = {
        "FF": np.tile(2000 + np.cumsum(dff), (4, 1)),
        "N2": np.tile(80 + np.cumsum(dn2), (4, 1)),
        "N1": np.tile(60 + 1e-3 * np.cumsum(e[2]), (4, 1)),
        "EGT": np.tile(500 + np.cumsum(e[3]), (4, 1)),
    }
    logF = b4_granger(Y, CFG)
    pairs = [f"{c}->{t}" for t in ("FF", "N2", "N1", "EGT") for c in ("FF", "N2", "N1", "EGT") if c != t]
    assert logF[pairs.index("FF->N2")] > logF[pairs.index("N2->FF")] + 3


def test_b5_recovers_egt_exponent_and_zero_scatter():
    """EGT_K = q(N1c) * theta^0.6 exactly -> a = 0.60; FFc an exact cubic in N2c -> scatter ~ 0."""
    g = _gen(6)
    n = 3000
    theta = 0.75 + 0.25 * g.random(n)
    delta = 0.3 + 0.7 * g.random(n)
    sq = np.sqrt(theta)
    n1c = 60 + 30 * g.random((4, n))
    n2c = 75 + 20 * g.random((4, n))
    egt_k = (600 + 3 * (n1c - 70) + 0.05 * (n1c - 70) ** 2) * theta**0.6
    ffc = 1000 + 50 * (n2c - 85) + 2 * (n2c - 85) ** 2
    Y = {"N1": n1c * sq, "N2": n2c * sq, "EGT": egt_k - 273.15, "FF": ffc * delta * sq}
    m = b5_moments(Y, theta, delta, CFG)
    scatter, a = b5_group([m, m])
    assert a == pytest.approx(0.60)
    assert scatter < 1e-6
    assert A_GRID[0] == 0.0 and A_GRID[-1] == 1.2 and A_GRID.size == 121


def test_b5_group_sums_like_round2_regardless_of_scalar_type():
    """Regression: round 2 summed 0-d arrays with plain '+'. Python >= 3.12 `sum()` of floats is compensated,
    which changed B5 (i) at ~1e-11 before `_seqsum`. Float and 0-d-array moments must give identical
    results."""
    rec = control_flight(0, REFERENCE_TAIL, "real")
    ms = [b5_moments({f: np.asarray(rec.outputs[f]) for f in rec.outputs}, rec.theta, rec.delta, CFG)] * 7
    as_arrays = []
    for mf, me in ms:
        mf2 = type(mf)(XtX=mf.XtX, Xty=mf.Xty, yy=np.asarray(mf.yy), sy=np.asarray(mf.sy), n=mf.n)
        as_arrays.append((mf2, me))
    assert b5_group(ms) == b5_group(as_arrays)


def test_b6_missing_phase_is_nan():
    g = _gen(7)
    n = 2000
    ph = np.full(n, 5)
    ph[:39] = 4  # only 39 airborne samples in phase 4
    Y = {f: 60 + g.standard_normal((4, n)) for f in ("N1", "N2", "EGT", "FF")}
    out = b6_stats(Y, ph, CFG)
    assert out.shape == (7, 16, 3)
    assert np.all(np.isnan(out[3])) and np.all(np.isfinite(out[4]))


def test_flight_stats_shapes_and_determinism():
    rec = control_flight(1, REFERENCE_TAIL, "real")
    a, b = flight_stats(rec), flight_stats(rec)
    assert a.b1_fast.shape == (120,) and a.b2.shape == (4 * len(LAG_PAIRS),)
    assert a.b3_coh.shape == (4, 4, 3) and a.b4.shape == (12,) and a.b6.shape == (7, 16, 3)
    for k in ("b1_fast", "b1_slow", "b2", "b3_coh", "b3_lgain", "b3_steps", "b4", "b6"):
        np.testing.assert_array_equal(a.get(k), b.get(k))


def test_flight_stats_many_is_order_preserving_and_worker_independent():
    recs = [control_flight(i, REFERENCE_TAIL, "real") for i in range(3)]
    assert pickle.loads(pickle.dumps(recs[0])).flight_id == recs[0].flight_id
    one = flight_stats_many(recs, max_workers=1)
    par = flight_stats_many(recs, max_workers=3)
    for x, y in zip(one, par, strict=True):
        assert x.flight_id == y.flight_id
        np.testing.assert_array_equal(x.b1_fast, y.b1_fast)
        np.testing.assert_array_equal(x.b3_steps, y.b3_steps)
