"""A2 (AD-31 as refined by AD-50): small-signal FF->N2 lead-lag and fast-band FF correlation signs, commanded-
step lead, bumpless transfers, A/T.

Plant and lanes are the labelled TEST FIXTURE (`tests/fadec_fixture.py`); M08 is the real kernel. Process
disturbances are identity-keyed AR(1) streams (tau 1 s, SD 1 %) entering the plant dynamics (AD-32).
Lead-lag uses the pre-registered round-2 B2 estimator (peak cross-correlation of first differences;
negative = FF lags N2), at 4 Hz on an FF-meter-lagged fuel flow (tau_FFs 0.218 s, the M12 role) as in the
real-data target (FF->N2 -0.50 s; A/T engaged -0.375 s, docs/behavioural_targets.md), and at 20 Hz on truth.
Mechanism (AD-50): the negative lag comes from ratio-unit (Wf/PS3) PS3-proportional metering with weak
small-signal governing - it survives governor gains of zero and stronger governing destroys it. On this
fixture
the 4 Hz value of -0.25 s comes from the FF meter lag (an ideal meter gives 0.00 s at 4 Hz; truth at 20 Hz is
-0.05..-0.15 s). Because a peak-lag estimator also returns a "lag" for an anti-correlation (the argmax of a
side-lobe), the fast-band correlation SIGN is asserted alongside the lag: r(N1,FF) and r(N2,FF) > 0 (real
+0.65 / +0.67).

Sample size: 120 s per run (28,800 truth steps; 480 samples at 4 Hz, 2,400 at 20 Hz), 3 disturbance keys
(sorties) per channel. Justification: a pilot over 60/120/180 s x 5 keys gave the same 4 Hz sign in 30/30 runs
(scratch probe, reported in the W1.3b report); 120 s keeps every test under ~10 s. The lag-vs-gain table is in
`tests/statistical/test_fadec_leadlag.py` (slow).
"""

from __future__ import annotations

import numpy as np
import pytest

from fadec_fixture import (
    X_N1,
    X_N2,
    X_WF,
    Scenario,
    ar1_disturbance,
    closed_loop,
    fast_band_r,
    fixture_params,
    leadlag,
    steady_state,
)
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import decode_active_limiter

pytestmark = pytest.mark.integration
N = 120 * 240
N1R = 13270 * 2 * np.pi / 60
N2R = 16810 * 2 * np.pi / 60


def _cfg(**p):
    cfg = FadecConfig.build(fixture_params())
    return cfg.with_p(**p) if p else cfg


def _dist(chan, sortie, n=N, sd=0.01):
    w = np.zeros((n, 1, 4))
    w[:, 0, chan] = ar1_disturbance(n, 1.0, sd, sortie=sortie, channel=chan)
    return w


@pytest.mark.parametrize("chan,name", [(3, "shaft_load"), (1, "combustor_eff")])
def test_small_signal_wf_lags_n2_under_spool_side_process_disturbance(chan, name):
    lags = []
    for sortie in (1, 2, 3):
        r = closed_loop(Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(chan, sortie)), cfg=_cfg())
        lags.append(leadlag(r))
    b2 = [b for _, b in lags]
    assert all(b < 0.0 for b in b2), (name, lags)  # measured FF lags N2: real-data sign (-0.50 s)
    # with idealised (unquantised) lanes the truth-level response lags too: the governing loop itself
    r = closed_loop(
        Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(chan, 1)), cfg=_cfg(), fine_lanes=True
    )
    truth, _ = leadlag(r)
    assert truth < 0.0, (name, truth)


@pytest.mark.parametrize("chan,name", [(3, "shaft_load"), (1, "combustor_eff")])
def test_fast_band_ff_correlations_are_positive_under_process_disturbance(chan, name):
    """B1 fast band (> 0.2 Hz, 4 Hz, FF-meter-lagged): r(N1,FF) > 0 and r(N2,FF) > 0 in every sortie (real
    652: +0.65 / +0.67, docs/behavioural_targets.md). Observed on the fixture: +0.78..+0.84 / +0.73..+0.79."""
    for sortie in (1, 2, 3):
        r = closed_loop(Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(chan, sortie)), cfg=_cfg())
        r_n1ff, r_n2ff, _ = fast_band_r(r)
        assert r_n1ff > 0.0 and r_n2ff > 0.0, (name, sortie, r_n1ff, r_n2ff)


def test_negative_lag_survives_zero_governor_gains():
    """AD-50 mechanism: with the governor's proportional, integral and large-signal gains at zero the lag is
    still negative and the correlation positive - the sign is carried by the ratio-unit PS3 path."""
    cfg = _cfg(gov_kp=0.0, gov_ki=0.0, gov_kl=0.0)
    r = closed_loop(Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(3, 1)), cfg=cfg)
    truth, b2 = leadlag(r)
    assert truth < 0.0 and b2 < 0.0, (truth, b2)
    assert fast_band_r(r)[1] > 0.0


def test_commanded_pla_steps_wf_leads_n2():
    t = np.arange(N) / 240.0
    pla = (60.0 + 5.0 * ((t % 20.0) < 10.0))[:, None]  # +-5 deg steps every 10 s, no disturbance
    r = closed_loop(Scenario(N, 1, pla_deg=pla), cfg=_cfg())
    truth, b2 = leadlag(r)
    assert truth > 0.0 and b2 > 0.0, (truth, b2)


def test_direct_wf_law_is_anti_correlated():
    """Negative control (A-W1.3b-2, AD-50): a C-MAPSS40k-style direct-Wf PI governor has no same-sign fuel
    path, so under process disturbance FF is ANTI-correlated with the speeds in the fast band. Its positive
    B2 "lag" (+1.25..+2.5 s) is the argmax of a side-lobe of that anti-correlation, not a lead."""
    cfg = _cfg().with_cfg(fuel_law=0)
    for sortie in (1, 2):
        r = closed_loop(Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(3, sortie)), cfg=cfg)
        r_n1ff, r_n2ff, _ = fast_band_r(r)
        assert r_n1ff < 0.0 and r_n2ff < 0.0, (r_n1ff, r_n2ff)


def test_fuel_metering_disturbance_leads_n2_whatever_the_law():
    """Where the disturbance enters decides the sign (AD-32 identification constraint for M03/W2.4): a
    fuel-metering disturbance is itself a fuel-flow change, so FF leads N2."""
    r = closed_loop(Scenario(N, 1, pla_deg=np.full((N, 1), 60.0), w=_dist(0, 1)), cfg=_cfg())
    truth, b2 = leadlag(r)
    assert truth > 0.0 and b2 > 0.0


def _ramp_run(anti_windup: int):
    n = 60 * 240
    t = np.arange(n) / 240.0
    pla = np.interp(t, [0.0, 5.0, 45.0, 60.0], [60.0, 60.0, 100.0, 100.0])[:, None]  # 1 deg/s through IRP
    cfg = _cfg().with_cfg(anti_windup=anti_windup)
    return closed_loop(Scenario(n, 1, pla_deg=pla), cfg=cfg)


def test_transitions_through_irp_are_continuous_and_bumpless():
    r = _ramp_run(1)
    wf = r.wf_cmd[:, 0]
    codes = r.limiter[:, 0] & 15
    switches = np.flatnonzero(np.diff(codes) != 0) + 1
    seen = {decode_active_limiter(c)[0] for c in codes}
    assert "GOV_N2" in seen and "N1_ISOCHRONOUS" in seen  # the governor hands over to the N1 limiter
    dwf = np.abs(np.diff(wf))  # dwf[k-1] = change applied at step k
    sw = set(int(k) for k in switches)
    assert len(sw) >= 1
    for k in sw:
        # bumpless: the change at a hand-over is no larger than the frame-to-frame changes around it (+-0.5 s)
        around = [dwf[j - 1] for j in range(max(1, k - 120), min(len(wf), k + 121)) if j not in sw]
        assert dwf[k - 1] <= 1.5 * max(around) + 1e-12, (k, dwf[k - 1], max(around))
    n1 = r.xs[1:, 0, X_N1] / N1R
    assert n1.max() < 1.02 + 0.02  # at most 2 % over the 102 % limit through the handover (fixture fan lag)
    assert abs(n1[-240:].mean() - 1.02) < 0.002  # then held isochronously at the limit


def test_bumpless_negative_control_without_anti_windup():
    """With anti-windup off the far limiters wind up, the N1 limiter takes over late and N1 overshoots."""
    ok = _ramp_run(1).xs[1:, 0, X_N1].max() / N1R
    bad = _ramp_run(0).xs[1:, 0, X_N1].max() / N1R
    assert bad > ok + 0.01, (ok, bad)


def test_autothrottle_tracks_n1_command_and_engages_bumplessly():
    n = 90 * 240
    x0 = steady_state(60.0)
    n1_0 = x0[0, X_N1] / N1R
    at_eng = np.zeros(n, np.int64)
    at_eng[10 * 240 :] = 1
    cmd = np.full((n, 1), n1_0)
    cmd[30 * 240 :, 0] = n1_0 + 0.03  # +3 % N1 command step at 30 s
    sc = Scenario(n, 1, pla_deg=np.full((n, 1), 60.0), at_engage=at_eng, at_n1_cmd=cmd)
    r = closed_loop(sc, cfg=_cfg().with_cfg(autothrottle=1), x0=x0)
    wf = r.wf_cmd[:, 0]
    k = 10 * 240
    assert abs(wf[k + 1] - wf[k - 1]) < 1e-3 * wf[k - 1]  # engagement is bumpless
    n1 = r.xs[1:, 0, X_N1] / N1R
    assert abs(n1[-240:].mean() - (n1_0 + 0.03)) < 0.005  # tracks the command within 0.5 % after 60 s
    # and the PLA is ignored while engaged: a different lever position gives the same engine
    sc2 = Scenario(n, 1, pla_deg=np.full((n, 1), 60.0), at_engage=at_eng, at_n1_cmd=cmd)
    sc2.pla_deg = sc2.pla_deg.copy()
    sc2.pla_deg[20 * 240 :, 0] = 70.0
    r2 = closed_loop(sc2, cfg=_cfg().with_cfg(autothrottle=1), x0=x0)
    np.testing.assert_array_equal(r2.xs[:, 0, X_N2], r.xs[:, 0, X_N2])


def test_two_engines_are_independent_under_unit_disturbances():
    n = 30 * 240
    w = np.zeros((n, 2, 4))
    w[:, 0, 3] = ar1_disturbance(n, 1.0, 0.01, sortie=1, serial="E1", channel=3)
    sc = Scenario(n, 2, pla_deg=np.full((n, 2), 60.0), w=w)
    r = closed_loop(sc, cfg=_cfg())
    quiet = closed_loop(Scenario(n, 2, pla_deg=np.full((n, 2), 60.0)), cfg=_cfg())
    np.testing.assert_array_equal(r.xs[:, 1], quiet.xs[:, 1])  # engine 2 untouched, bitwise
    assert np.std(np.diff(r.xs[1:, 0, X_N2])) > 10 * np.std(np.diff(quiet.xs[1:, 0, X_N2])) + 1e-12
    assert np.isfinite(r.xs[:, :, X_WF]).all()
