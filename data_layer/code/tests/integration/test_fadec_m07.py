"""M08 in closed loop with the REAL M07 engine, harmonised schedules (W2.1b; AD-46, AD-50, W2.1 entry gate 2).

Closed loop: `tests/engine_fadec_loop.py` (real M07 + real M08 kernels; TEST FIXTURE lanes with M12's sensor
lags). Every run starts from the closed-loop operating point at its PLA (`phalanx.fadec.trim.operating_point`,
W2.1 F1: an M07 trim with the M08 commands that hold it), so a steady check is not a settling transient.

Checks (default M08 configuration):
- SLS: ground idle (PLA 18) in the released 63-70 % N2 band and steady (no limit cycle) at idle and part
  power; throttle authority (N2 rises by >= 1 % per step, PLA 18-75); the N1 limit takes over at the
  harmonised onset (PLA 84 +/- 1, A-W2.1b-1);
- altitude (40,000 / 50,000 ft, M0.8): no runaway at idle, the 104.4 % corrected N1 cap holds at PLA 90;
- entry gate 2 (AD-50): the governed small-signal FF correlations stay positive below the N1-limited region;
  the test records the PLA where r(N2,FF) inverts (N1 limiter in control); B2 < 0 (FF lags N2) at PLA 60; the
  direct-Wf law is anti-correlated (negative control).

Sample sizes: SLS 6 PLA points x 20 s (last 10 s judged); altitude 2 x 2 points x 30 s; FF signs 3 keyed
shaft-load disturbance runs x 120 s after a 30 s settle (480 samples at 4 Hz each) per PLA, per law.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

import engine_fadec_loop as L
import fadec_fixture as fx
from phalanx.engine.module import EngineModule
from phalanx.engine.steady import TrimCondition
from phalanx.fadec import FadecConfig, load_fadec_params
from phalanx.fadec.codes import L_GOV_N2, L_N1
from phalanx.fadec.layout import O_LIMITER
from phalanx.fadec.trim import operating_point
from phalanx.validation.battery.filters import lowpass

pytestmark = pytest.mark.integration
CFG = FadecConfig.build(load_fadec_params())
SLS = TrimCondition()


@pytest.fixture(scope="module")
def eng():
    return EngineModule("eng")


def _settled(eng, pla, cond=SLS, *, secs=20, cfg=CFG):
    op = operating_point(eng.model, cfg, min(pla, 86.0), cond)
    return op, L.run(eng, op.engine, pla, n=secs * 240, condition=cond, cfg=cfg)


def test_sls_ground_idle_is_steady_in_band_and_the_throttle_has_authority(eng):
    tail = slice(-2400, None)
    n2 = []
    for pla in (18.0, 31.0, 45.0, 60.0, 75.0):
        _, r = _settled(eng, pla)
        wf = r.ch("wf")[tail]
        assert np.ptp(wf) / wf.mean() < 0.02, (pla, np.ptp(wf) / wf.mean())  # steady: no limit cycle
        assert set((r.cmdi[tail, 0, O_LIMITER] & 15).tolist()) <= {L_GOV_N2, L_N1}, pla
        n2.append(r.ch("n2")[tail].mean() / L.N2R)
    assert 0.63 <= n2[0] <= 0.70, n2[0]  # released ground-idle band (KSAS 2006; USAF IERA about 65 %)
    assert all(b - a >= 0.01 for a, b in itertools.pairwise(n2)), n2


def test_n1_limit_takes_over_at_the_harmonised_onset(eng):
    """A-W2.1b-1 anchor: N1 and T5 limits meet at PLA 84 on the SLS ISA line; the operating point is
    governed (N2) below it and N1-limited above it."""
    assert operating_point(eng.model, CFG, 82.0, SLS).regime == L_GOV_N2
    assert operating_point(eng.model, CFG, 86.0, SLS).regime == L_N1


@pytest.mark.parametrize("ft,mach", [(40000, 0.8), (50000, 0.8)])
def test_altitude_idle_does_not_run_away_and_the_corrected_cap_holds(eng, ft, mach):
    t, p = L.isa(ft * 0.3048)
    cond = TrimCondition(t_s=t, p_s=p, mach=mach)
    tail = slice(-1200, None)
    _, idle = _settled(eng, 31.0, cond, secs=30)
    assert idle.ch("n2")[tail].mean() / L.N2R < 0.80 and np.isfinite(idle.ch("wf")).all()
    _, mil = _settled(eng, 90.0, cond, secs=30)
    th1 = mil.ch("t2")[tail] / 288.15
    n1c = mil.ch("n1")[tail] / L.N1R / np.sqrt(th1)
    assert n1c.max() <= 1.044 * 1.005, n1c.max()


def _fast(x):
    return x - lowpass(x, 4.0, 0.2)


def _signs(eng, pla, cfg=CFG):
    """(B2 [s], r(N1,FF), r(N2,FF), main regulator) for 3 keyed shaft-load disturbance runs at `pla`."""
    settle, T = 30.0, 120.0
    n, k0 = int((settle + T) * 240), int(settle * 240)
    op = operating_point(eng.model, cfg, min(pla, 86.0), SLS)
    out = []
    for sortie in (1, 2, 3):
        w = np.zeros((n, 5))
        w[:, 3] = fx.ar1_disturbance(n, 1.0, 0.01, sortie=sortie, channel=3)  # shaft load
        r = L.run(eng, op.engine, pla, n=n, condition=SLS, cfg=cfg, w=w)
        ffm = fx.first_order(r.ch("wf"), 0.218, fx.DT)[k0::60]  # flowmeter (round-2 tau_FFs)
        n1, n2 = r.ch("n1")[k0::60], r.ch("n2")[k0::60]
        r1 = float(np.corrcoef(_fast(n1), _fast(ffm))[0, 1])
        r2 = float(np.corrcoef(_fast(n2), _fast(ffm))[0, 1])
        lim = int(np.argmax(np.bincount(r.cmdi[k0:, 0, O_LIMITER] & 15, minlength=12)))
        out.append((fx.b2_lag(ffm, n2, 4.0), r1, r2, lim))
    return out


@pytest.mark.parametrize("pla", [60.0, 70.0, 80.0])
def test_governed_ff_correlations_are_positive_below_the_n1_limited_region(eng, pla):
    """Entry gate 2 / AD-50: below the N1-limited region the N2 governor holds fuel and the fast-band
    correlations of the flowmeter with both speeds are positive (real data: +0.65 / +0.67)."""
    for b2, r1, r2, lim in _signs(eng, pla):
        assert lim == L_GOV_N2, lim
        assert r1 > 0.0 and r2 > 0.0, (pla, r1, r2)
        if pla == 60.0:
            assert b2 < 0.0, b2  # FF lags N2 (round-2 B2 -0.5 s)


def test_ff_n2_correlation_inverts_in_the_n1_limited_region(eng):
    """Records where the sign inverts: with the N1 limiter holding fuel (PLA 88), fuel moves against N2 (the
    limiter cuts fuel as the speeds rise), so r(N2,FF) < 0. W2.1b scan (n = 3 x 120 s per PLA): see the
    module docstring of tests/integration/test_fadec_limiters_m07.py and the W2.1b report."""
    for _, _, r2, lim in _signs(eng, 88.0):
        assert lim == L_N1, lim
        assert r2 < 0.0, r2


def test_direct_law_is_anti_correlated_on_the_real_engine(eng):
    for _, r1, r2, _ in _signs(eng, 60.0, CFG.with_cfg(fuel_law=0)):
        assert r1 < 0.0 and r2 < 0.0, (r1, r2)
