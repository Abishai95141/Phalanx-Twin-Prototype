"""A3: injected-fault responses reproduce the released cascades qualitatively (architecture §6 M08, §14).

Templates (texture_and_fault_gap_closure.md Q6, report §9):
- pop stall [TRANSFER: F404-400, NASA TM-104328]: PS3 ~85 -> 10-15 psia in one sample, ~75 psia within
  0.3 s, baseline in ~3 s, no pilot action;
- mechanical stall [TRANSFER: F110-GE-100, F-16C 88-0433 UTTR AIB]: N falls while T5 rises; stall code +2 s,
  over-temperature +4 s, T5 signal fail (secondary sensor failure) +10 s, flameout/sub-idle +13 s;
- AB no-light [TRANSFER: F100 DEEC, NASA TM-86745]: declared 2.5 s after the request, up to 3 retries;
- hung relight [TRANSFER: F100/F-16 recorder trace]: N2 flat at ~35 % while T5 climbs.

The plant is the labelled TEST FIXTURE (`tests/fadec_fixture.py`); its fault trajectories (efficiency loss,
PS3 collapse, the stagnation T5 rise, the AB that never lights, the flame kill) are scripted to the
template; what is tested is M08's response: which codes it raises, when (against the plant/lane events), in
which order, and what it does not raise. Timing windows are qualitative (the template's own resolution is
~1 s). The sub-idle persistence (10 s) was set from the same F110 trace, so the +13 s check is a consistency
check, not an independent validation (A-W1.3b-8).

Sample size: one deterministic run per cascade (n = 1 each; no randomness - the cascades are deterministic
functions of the scripted faults), 12-30 s at 240 Hz.
"""

from __future__ import annotations

import numpy as np
import pytest

import fadec_fixture as fx
from fadec_fixture import (
    X_ABLIT,
    X_LIT,
    X_N2,
    X_T5,
    Scenario,
    closed_loop,
    steady_state,
)
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import (
    IGN_MAIN,
    L_ACCEL,
    L_GOV_N2,
    L_START_NDOT,
    L_T5,
    ST_RUNNING,
    active_codes,
)
from phalanx.fadec.layout import C_LAYOUT, F_WF_CMD, I_START_STATE, O_AB_EN, O_IGN, O_WF_AB

pytestmark = pytest.mark.integration
HZ = 240
N2R = 16810 * 2 * np.pi / 60
PSI = 6894.757293168361
FRAME = 1.0 / 60.0
STEP = 1.0 / HZ


def _cfg():
    return FadecConfig.build(fx.fixture_params())


def _codes_by_step(r):
    return [set(active_codes(int(m))) for m in r.faults[:, 0]]


def _first(codes, code, t0=0.0, after=0.0):
    """Time (s, relative to t0) of the first step >= after (absolute s) with `code` active, or None."""
    for k, c in enumerate(codes):
        if k / HZ >= after and code in c:
            return k / HZ - t0
    return None


def _onsets(codes, code):
    out, prev = [], False
    for k, c in enumerate(codes):
        on = code in c
        if on and not prev:
            out.append(k / HZ)
        prev = on
    return out


# ------------------------------------------------------------------ pop stall
def test_pop_stall_is_flagged_within_a_frame_and_rides_through_without_lane_failures():
    """35,000 ft, M 0.3, IRP (the TM-104328 departures). The FADEC flags the stall on the first frame after
    the collapse, keeps both PS3 lanes (rate-check persistence), suspends the analytical check during the
    declared stall, cuts fuel through the ratio-unit law (Wf = RU x PS3) and recovers without flameout."""
    t_amb, p_amb, mach = 218.8, 23842.0, 0.3
    T, ts = 12.0, 5.0
    n = int(T * HZ)
    t = np.arange(n) / HZ
    ps3f = np.interp(t, [0, ts, ts + STEP, ts + 0.3, ts + 3.0, T], [1, 1, 0.14, 0.88, 1.0, 1.0])[:, None]
    sc = Scenario(
        n, 1, pla_deg=np.full((n, 1), 90.0), ps3_factor=ps3f,
        t_amb=np.full(n, t_amb), p_amb=np.full(n, p_amb), mach=np.full(n, mach),
    )  # fmt: skip
    r = closed_loop(sc, cfg=_cfg(), x0=steady_state(84.0, t_amb=t_amb, p_amb=p_amb, mach=mach))
    codes = _codes_by_step(r)
    k0 = int(ts * HZ)
    ps3_before = r.xs[k0, 0, 13] / PSI  # X_PS3_OUT
    assert 80.0 < ps3_before < 120.0  # the template's ~85 psia class at altitude
    t_code = _first(codes, "ENG-501", t0=ts)
    assert t_code is not None and 0.0 < t_code <= FRAME + 2 * STEP  # first frame after the collapse
    allc = set().union(*codes)
    # PS3 lane A/B, cross-channel, analytical, signal fail
    ps3_codes = {"ENG-007", "ENG-008", "ENG-035", "ENG-045", "ENG-055"}
    assert not allc & ps3_codes, allc
    assert not allc & {"ENG-502", "ENG-504", "ENG-506"}  # no flameout, hung start or sub-idle
    # code held 3 s (stall_hold) after the single detection, then cleared
    t_off = next(k / HZ for k in range(k0, n) if "ENG-501" not in codes[k] and k / HZ > ts + t_code)
    assert abs((t_off - ts - t_code) - 3.0) <= 2 * FRAME
    # ratio-unit law: fuel follows PS3 down (inherent stall-recovery cutback) and recovers
    wf = r.wf_cmd[:, 0]
    assert wf[k0 : k0 + HZ].min() < 0.5 * wf[k0 - 1]
    assert abs(wf[k0 + 3 * HZ] / wf[k0 - 1] - 1.0) < 0.10  # recovering (N1 loop re-trims after the dip)
    assert abs(wf[-1] / wf[k0 - 1] - 1.0) < 0.02
    n2 = r.xs[1:, 0, X_N2]
    assert n2[k0 : k0 + 4 * HZ].min() > 0.97 * n2[k0 - 1]  # self-recovering: small speed dip


# ------------------------------------------------------------------ mechanical stall -> stagnation
#: scripted stagnation T5 rise (K added to the fixture's gas T5) at onset-relative knots; derived offline so
#: that the thermocouple T5 sits between the 850 degC over-temperature threshold and the 871 degC harness
#: span top from ~+3 s to the injected harness failure (the template's "T5 rises")
_T5_KNOTS = np.array(
    [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5]
)
_T5_ADD = np.array([0, -17, 30, 91, 115, 71, 22, 9, 13, 18, 23, 29, 36, 42, 48, 62, 62, 62], dtype=float)


def _mechanical_stall(t0=8.0, T=26.0):
    n = int(T * HZ)
    t = np.arange(n) / HZ
    # blade damage from t0 (N begins to drop), stall at +2 s: PS3 collapses in one sample, stagnates at 50 %
    eff = np.interp(t, [0, t0, t0 + 2.0, t0 + 2.0 + STEP, t0 + 5.0, T], [0, 0, 0.05, 0.5, 0.9, 0.9])
    ps3f = np.interp(t, [0, t0 + 2.0, t0 + 2.0 + STEP, t0 + 2.3, T], [1, 1, 0.15, 0.5, 0.5])
    t5add = np.interp(t, np.r_[0.0, t0 + _T5_KNOTS, T], np.r_[0.0, _T5_ADD, _T5_ADD[-1]])
    # secondary sensor failure: both T5 harnesses read off-scale high from +9.9 s
    fm = np.zeros((n, 1, 12), np.int64)
    fv = np.zeros((n, 1, 12))
    k_sf = int((t0 + 9.9) * HZ)
    fm[k_sf:, 0, 10:12] = 1
    fv[k_sf:, 0, 10:12] = 1300.0
    sc = Scenario(
        n, 1, pla_deg=np.full((n, 1), 90.0), eff_loss=eff[:, None], ps3_factor=ps3f[:, None],
        t5_add=t5add[:, None], force_mask=fm, force_val=fv,
    )  # fmt: skip
    return closed_loop(sc, cfg=_cfg(), x0=steady_state(84.0)), t0


@pytest.fixture(scope="module")
def mech():
    return _mechanical_stall()


def test_mechanical_stall_codes_follow_the_released_order_and_timing(mech):
    r, t0 = mech
    codes = _codes_by_step(r)
    t_stall = _first(codes, "ENG-501", t0, after=t0)
    t_ot = _first(codes, "ENG-701", t0, after=t0)
    t_sf = _first(codes, "ENG-056", t0, after=t0)  # T5 signal fail (no valid harness)
    t_si = _first(codes, "ENG-506", t0, after=t0)
    timeline = {"stall": t_stall, "overtemp": t_ot, "t5_signal_fail": t_sf, "sub_idle": t_si}
    assert None not in timeline.values(), timeline
    assert t_stall < t_ot < t_sf < t_si, timeline
    # template +2 / +4 / +10 / +13 s (resolution ~1 s)
    assert 1.9 <= t_stall <= 2.2, timeline
    assert 3.0 <= t_ot <= 5.0, timeline
    assert 9.9 <= t_sf <= 10.5, timeline
    assert 12.0 <= t_si <= 15.0, timeline
    # no flameout code before sub-idle: T5 stayed hot (stagnation is not a flameout)
    t_fo = _first(codes, "ENG-502", t0, after=t0)
    assert t_fo is None or t_fo > t_si
    assert _first(codes, "ENG-504", t0, after=t0) is None  # no hung start
    # the plant did what the template says: N falls while T5 rises
    k1, k9 = int((t0 + 1.0) * HZ), int((t0 + 9.0) * HZ)
    assert r.xs[k9, 0, X_N2] < 0.6 * r.xs[k1, 0, X_N2]
    assert r.xs[k9, 0, X_T5] > r.xs[k1, 0, X_T5]


def test_mechanical_stall_code_times_are_the_monitor_persistences(mech):
    """Each code comes from its monitor: over-temperature = 1 s (ot_time) after the measured T5 first
    exceeds 850 degC; sub-idle = 10 s (si_time) after corrected N2 last fell below 60 %; analytical checks
    are suspended while the stall code is held."""
    r, _ = mech
    codes = _codes_by_step(r)
    t5 = r.sel[:, 0, 5]
    k_hot = int(np.argmax(t5 > 273.15 + 850.0))
    k_ot = next(k for k, c in enumerate(codes) if "ENG-701" in c)
    assert abs((k_ot - k_hot) / HZ - 1.0) <= 2 * FRAME
    t1 = np.maximum(r.sel[:, 0, 2], 1.0)  # step 0 precedes the first frame (no selection yet)
    n2c = r.sel[:, 0, 1] / N2R / np.sqrt(t1 / 288.15)
    k_si = next(k for k, c in enumerate(codes) if "ENG-506" in c)
    below = n2c[:k_si] < 0.60
    k_cross = k_si - int(np.argmin(below[::-1]))  # start of the last continuous run below 60 %
    assert abs((k_si - k_cross) / HZ - 10.0) <= 2 * FRAME
    for c in codes:
        if "ENG-501" in c:
            assert not {f"ENG-04{s}" for s in range(1, 7)} & c  # no analytical failure while stalled


# ------------------------------------------------------------------ AB no-light, retries, lockout
def _ab_run(ab_fault: int, T=32.0, t_req=8.0):
    n = int(T * HZ)
    t = np.arange(n) / HZ
    pla = np.where(t >= t_req, 110.0, 90.0)[:, None]
    sc = Scenario(n, 1, pla_deg=pla, ab_fault=np.array([ab_fault]))
    return closed_loop(sc, cfg=_cfg(), x0=steady_state(84.0)), t_req


def test_ab_no_light_declared_2p5_s_after_the_request_then_three_retries_and_lockout():
    r, t_req = _ab_run(1)
    codes = _codes_by_step(r)
    nolight = [t - t_req for t in _onsets(codes, "ENG-503")]
    lockout = [t - t_req for t in _onsets(codes, "ENG-509")]
    # the engine is at IRP when the AB is selected (N1 within 3 % of its limit), so the request is immediate
    assert len(nolight) == 4, nolight  # first attempt + 3 retries
    assert abs(nolight[0] - 2.5) <= FRAME + STEP
    # exact: the code is raised on the ab_nolight-th FADEC frame counted from the request frame (2.5 s = 150
    # frames at 60 Hz), neither one frame early nor one late
    k_req = int(t_req * HZ)
    k_code = next(k for k, c in enumerate(codes) if "ENG-503" in c)
    n_frames = int(r.nfr[k_req : k_code + 1].sum())
    assert n_frames == int(_cfg().cfg[C_LAYOUT.index["ab_nolight"]]) == 150, n_frames
    gaps = np.diff(nolight)
    assert np.all(np.abs(gaps - (2.4 + 2.5)) <= 2 * FRAME), gaps  # retry wait 2.4 s + 2.5 s attempt
    assert len(lockout) == 1 and abs(lockout[0] - nolight[-1]) <= STEP
    k_lock = int((t_req + lockout[0]) * HZ) + 1
    assert not r.cmdi[k_lock:, 0, O_AB_EN].any() and not r.cmdf[k_lock:, 0, O_WF_AB].any()
    assert not r.xs[:, 0, X_ABLIT].any()


def test_ab_lights_normally_without_a_no_light_code():
    r, t_req = _ab_run(0, T=14.0)
    codes = _codes_by_step(r)
    assert not set().union(*codes) & {"ENG-503", "ENG-509", "ENG-510"}
    k_lit = int(np.argmax(r.xs[1:, 0, X_ABLIT] > 0.5))
    assert 0.0 < k_lit / HZ - t_req < 2.5  # fixture light-off 0.6 s after pre-open (0.2 s)
    assert r.cmdi[-1, 0, O_AB_EN] == 1


# ------------------------------------------------------------------ flameout, relight, hung relight
def _relight(eff_after: float, T=26.0, t_fo=2.0, pla=40.0):
    n = int(T * HZ)
    t = np.arange(n) / HZ
    kill = ((t >= t_fo) & (t < t_fo + 0.1)).astype(float)[:, None]
    eff = np.where(t >= t_fo, eff_after, 0.0)[:, None]
    sc = Scenario(n, 1, pla_deg=np.full((n, 1), pla), kill=kill, eff_loss=eff)
    return closed_loop(sc, cfg=_cfg(), x0=steady_state(pla)), t_fo


def test_part_power_flameout_is_detected_and_relit():
    """Cruise-power flameout at SLS: detected (T5 below its span-floored reference, N2 decelerating through
    the governed demand), igniters on, relight, confirmation once T5 is back and the core accelerates; the
    sub-idle N2-rate governor (A-W1.3b-18; PS3 min off) brings the core back to run speed at its scheduled
    2 %/s. The hung-start 1-s rule never fires: PLA 40 is outside its 14-24 deg band."""
    r, t_fo = _relight(0.0)
    codes = _codes_by_step(r)
    assert not any("ENG-504" in c for c in codes)
    t_det = _first(codes, "ENG-502", t_fo, after=t_fo)
    assert t_det is not None and t_det < 1.0
    k_det = int((t_fo + t_det) * HZ)
    assert r.cmdi[k_det, 0, O_IGN] & IGN_MAIN
    k_lit = k_det + int(np.argmax(r.xs[k_det + 1 :, 0, X_LIT] > 0.5))
    assert (k_lit - k_det) / HZ < 2.5
    assert "ENG-502" not in codes[-1] and "ENG-506" not in codes[-1]
    assert not (r.cmdi[-1, 0, O_IGN] & IGN_MAIN)
    assert r.xs[-1, 0, X_N2] / N2R > 0.68
    # after light-off the core accelerates at the scheduled N2 rate (2 %/s) while in the sub-idle mode
    n2 = r.xs[1:, 0, X_N2] / N2R
    k_a = k_lit + 3 * HZ
    k_b = k_a + 4 * HZ
    assert n2[k_b] < 0.6 and abs((n2[k_b] - n2[k_a]) / 4.0 - 0.02) < 0.005


def test_hung_relight_is_flagged_while_n2_hangs_below_60pct_with_t5_hot():
    """F100 hung-relight class at idle PLA (18 deg, inside the rule's 14-24 deg band): the relit core cannot
    accelerate (scripted 90 % efficiency loss) even with the start T5 limit holding fuel at its trim. The NASA
    hung-start rule (N2 < 60 % and not rising for 1 s, relight in progress) holds ENG-504 while N2 hangs."""
    r, t_fo = _relight(0.9, T=20.0, pla=18.0)
    codes = _codes_by_step(r)
    k_lit = int(np.argmax(r.xs[1:, 0, X_LIT][int(t_fo * HZ) + 24 :] > 0.5)) + int(t_fo * HZ) + 24
    n2 = r.xs[1:, 0, X_N2] / N2R
    t5 = r.xs[1:, 0, X_T5]
    # the hung window: 6-10 s after light-off, N2 flat within 1 % for 4 s, below 60 %
    k_a, k_b = k_lit + 6 * HZ, k_lit + 10 * HZ
    assert n2[k_a:k_b].max() < 0.6 and np.ptp(n2[k_a:k_b]) < 0.01
    assert t5[k_a:k_b].min() > 900.0  # hot while hung (template: FTIT climbs)
    assert all("ENG-504" in codes[k] for k in range(k_a, k_b))
    assert all("ENG-502" in codes[k] for k in range(k_a, k_b))  # relight not confirmed while hung


def test_cold_day_ground_idle_is_not_sub_idle():
    """Run speed and sub-idle are judged on corrected N2 (A-W1.3b-8): at -40 degC a healthy ground idle has
    physical N2 below 60 % but corrected N2 above it. It must count as a running engine (no endless start, no
    hung-start code) and must not raise ENG-506 (review mutant M24: a physical-N2 monitor does). 40 s run
    (beyond
    the 10 s sub-idle persistence and the 35 s hung-start timeout)."""
    n = 40 * HZ
    sc = Scenario(n, 1, pla_deg=np.full((n, 1), 18.0), t_amb=np.full(n, 233.15))
    r = closed_loop(sc, cfg=_cfg(), x0=steady_state(18.0, t_amb=233.15))
    n2 = r.xs[1:, 0, X_N2] / N2R
    assert n2[-HZ:].max() < 0.60  # physically below the threshold: the test is meaningful
    codes = _codes_by_step(r)
    assert not any(("ENG-506" in c) or ("ENG-504" in c) for c in codes)
    assert (r.limiter[-HZ:, 0] & 15 == 1).all()  # governed on the N2 schedule, not in the start mode


# ------------------------------------------------------------------ sub-idle start/relight mode (A-W1.3b-18)
def _sub_steps(r):
    return np.flatnonzero((r.limiter[:, 0] & 15) == L_START_NDOT)


def test_fuel_ratio_is_held_until_light_off_is_detected():
    """Before light-off is detected (T5 above the flameout reference + 5 %) the sub-idle governor holds its
    ratio-unit output: Wf follows PS3 at a constant Wf/PS3. Light-off is then seen on the T5 rise and the
    N2-rate governor accelerates the core (review mutant N6: 'light-off always seen' would act on the
    decaying, dark core)."""
    r, _ = _relight(0.0, T=14.0)
    sub = _sub_steps(r)
    k0 = int(sub[0])
    t5_lightoff = 1.05 * (
        273.15 + 381.0
    )  # flameout reference at SLS, PLA 40: the 381 degC span floor (fo_t5_min)
    k_lo = k0 + int(np.argmax(r.sel[k0:, 0, 5] > t5_lightoff))
    assert k_lo - k0 > HZ  # a dark phase of more than 1 s (decay, relight, thermocouple lag)
    ru = r.wf_cmd[k0 + 24 : k_lo, 0] / r.sel[k0 + 24 : k_lo, 0, 4]  # Wf / PS3 (PS3 input filter: skip 0.1 s)
    assert ru.max() / ru.min() < 1.1, (ru.min(), ru.max())
    n2 = r.xs[1:, 0, X_N2] / N2R  # after light-off the rate governor accelerates the core (2 %/s scheduled)
    assert (n2[k_lo + 3 * HZ] - n2[k_lo + HZ]) / 2.0 > 0.01


#: truth-side allowance of the run-speed hand-over check: lane resolution + validation filter lag (0.2 % N2)
HANDOVER_TOL = 0.002


def test_sub_idle_hand_over_lands_on_the_accel_schedule_then_settles_on_the_governor():
    """Specified hand-over (A-W1.3b-18): at run speed the N2 governor's integrator is re-initialised to the
    last output minus its feed-forward, so feed-forward + integrator are continuous and the error terms act.
    At PLA 40 the demand is far above, so the selection lands on the accel Wf/PS3 schedule - one fuel step up
    to it (about 0.02 kg/s, several times the preceding frame steps) - and the governor then settles without a
    feed-forward excess (review mutant N3, feed-forward counted twice, overshoots).

    The hand-over criterion is on M08's validated N2 lane reading, not on the truth this test sees, so the
    truth is allowed ``HANDOVER_TOL`` = 0.002 (0.2 % N2) on both sides of the 0.60 run speed: the lane's
    resolution plus the validation input filter's lag at the sub-idle acceleration. Dictionary 0.1.3 made the
    FADEC lanes' native step the converter step (span / 2^14, finer than the bus word; the fixture quantiser
    reads it), and the hand-over moved by one step: truth 0.6003 on the last sub-idle step (measured, W2.2),
    inside the allowance; a mis-set threshold (mutant n2_run + 0.02) is far outside it."""
    r, _ = _relight(0.0, T=40.0)
    k = int(_sub_steps(r)[-1]) + 1  # first step after the sub-idle mode
    n2 = r.xs[1:, 0, X_N2] / N2R
    # handed over at corrected run speed (SLS: physical = corrected), within the lane-reading allowance
    assert n2[k - 1] < 0.6 + HANDOVER_TOL and 0.6 <= n2[k] + HANDOVER_TOL
    lim = r.limiter[:, 0] & 15
    assert (lim[k : k + HZ // 2] == L_ACCEL).all()
    dwf = np.diff(r.wf_cmd[:, 0])
    step, prior = dwf[k - 1], np.abs(dwf[k - 121 : k - 1]).max()
    assert 0.0 < step < 0.03 and step > 3.0 * prior, (step, prior)
    assert set(lim[-2 * HZ :].tolist()) == {L_GOV_N2}
    n2_ss = steady_state(40.0)[0, X_N2] / N2R
    assert n2[k:].max() < 1.015 * n2_ss, (n2[k:].max(), n2_ss)
    assert abs(n2[-HZ:].mean() / n2_ss - 1.0) < 0.002


def test_start_t5_limit_binds_in_a_hot_relight():
    """Hot relight (scripted +280 K hot-section T5 offset from the flameout, e.g. a degraded turbine): in the
    sub-idle mode the T5 fuel limiter takes over at the 760 degC start limit (not the 850 degC running limit),
    holds the measured T5 there while the core still accelerates, and the relight completes (review mutant N2,
    start limit never applied, lets the start run hotter)."""
    T, t_fo = 40.0, 2.0
    n = int(T * HZ)
    t = np.arange(n) / HZ
    kill = ((t >= t_fo) & (t < t_fo + 0.1)).astype(float)[:, None]
    t5a = np.where(t >= t_fo, 280.0, 0.0)[:, None]
    sc = Scenario(n, 1, pla_deg=np.full((n, 1), 40.0), kill=kill, t5_add=t5a)
    r = closed_loop(sc, cfg=_cfg(), x0=steady_state(40.0))
    sub = _sub_steps(r)
    lim = r.limiter[:, 0] & 15
    in_sub = slice(int(sub[0]), int(sub[-1]) + 1)
    assert (lim[in_sub] == L_T5).sum() > 2 * HZ  # the start T5 limit held fuel for more than 2 s
    t5 = r.sel[in_sub, 0, 5] - 273.15
    assert t5.max() < 760.0 + 5.0, t5.max()
    assert r.xs[-1, 0, X_N2] / N2R > 0.65  # and the relight still completed


def test_cold_day_start_completes_on_corrected_run_speed():
    """A lit start in progress at -40 degC (physical N2 50 %, fuel ratio 20 % above its equilibrium; the lit
    T5 is below the harness floor at this cold sub-idle point, so light-off is not seen and the ratio is
    held): the start completes when CORRECTED N2 reaches 60 % (physical ~54 %), hands over to the governor and
    settles at the cold-day idle (physical N2 ~59.9 %) without a hung-start code (review mutant N4: run speed
    on physical N2 keeps it in the start mode)."""
    ta, n = 233.15, 40 * HZ
    sth = np.sqrt(ta / 288.15)
    x0 = steady_state(18.0, t_amb=ta, n2c=0.50 / sth)
    f, i = fx.initial_fadec_state(_cfg(), x0)
    f[:, F_WF_CMD] *= 1.2
    sc = Scenario(n, 1, pla_deg=np.full((n, 1), 18.0), t_amb=np.full(n, ta))
    r = closed_loop(sc, cfg=_cfg(), x0=x0, state=(f, i))
    sub = _sub_steps(r)
    k = int(sub[-1]) + 1
    n2 = r.xs[1:, 0, X_N2] / N2R
    assert k < 5 * HZ  # the start completed within 5 s
    assert abs(n2[k] / sth - 0.60) < 0.005 and n2[k] < 0.57, (n2[k], n2[k] / sth)
    assert set((r.limiter[-2 * HZ :, 0] & 15).tolist()) == {L_GOV_N2}
    assert n2[-1] < 0.60  # physically below 60 % at the end: the corrected criterion is what completed it
    assert not any("ENG-504" in c for c in _codes_by_step(r))
    # the start state machine is RUNNING right after the hand-over, while physical N2 is still well below 60 %
    k_chk = k + HZ // 4
    assert n2[: k_chk + 1].max() < 0.58
    r_early = closed_loop(Scenario(k_chk, 1, pla_deg=np.full((k_chk, 1), 18.0), t_amb=np.full(k_chk, ta)),
                          cfg=_cfg(), x0=x0, state=(f, i))  # fmt: skip
    assert int(r_early.i[0, I_START_STATE]) == ST_RUNNING
    assert not any("ENG-504" in c for c in _codes_by_step(r))
