"""A5: the M08 signal-validation template and its deliberately injectable failure modes (W1.3b).

Open-loop: the compiled kernel is driven one FADEC frame at a time with scripted lane vectors built from a
fixture steady state at PLA 60 deg, SLS (`fadec_fixture.FrameDriver`, a TEST FIXTURE). Every rule is checked
at its
exact frame count (persistence n, heal after 10 good frames) and every failure mode against the nominal
validator on the same input. Sample: one deterministic scripted sequence per rule (no randomness except where
the
'skew + noise' mode needs lane noise, from a fixed-seed Philox generator); 40-1,800 frames per test.
"""

from __future__ import annotations

import numpy as np
import pytest

from fadec_fixture import FrameDriver, fixture_params, has_code, lanes_from_state, steady_state
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import (
    ACC_AB_INHIBIT,
    ACC_ACT_SAFE,
    ACC_N2_REDUCED,
    ACC_REVERSION,
    S_N1,
    S_N2,
    S_PS3,
    S_T1,
    S_T5,
    S_T25,
    V_FAILED,
    V_OK,
    V_SUBSTITUTED,
    V_SUSPECT,
    decode_active_limiter,
)
from phalanx.fadec.layout import F_N2C_DEM, F_XMOD, I_ACC, I_AN_CNT

pytestmark = pytest.mark.unit
N1R = 13270 * 2 * np.pi / 60
N2R = 16810 * 2 * np.pi / 60
PSI = 6894.757293168361


def _setup(pla=60.0, **param_overrides):
    # the template under test includes the analytical check: enabled explicitly here (default off until an
    # M07-derived on-board model exists, AD-50)
    param_overrides.setdefault("vm_analytic", 1)
    params = fixture_params().replace(**param_overrides)
    cfg = FadecConfig.build(params)
    x = steady_state(pla)[0]
    base = lanes_from_state(x, quantise=False)
    drv = FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5]))
    return drv, base


def _run(drv, lanes_seq, pla=60.0):
    out = []
    for ln in lanes_seq:
        drv.frame(ln, pla_deg=pla)
        out.append((drv.faults, [drv.vstate(s) for s in range(6)], [drv.sel(s) for s in range(6)]))
    return out


def test_range_check_needs_n_consecutive_frames_and_heals_after_10_good_frames():
    drv, base = _setup()
    _run(drv, [base] * 5)
    bad = base.copy()
    bad[2] = 1.10 * N2R  # N2 lane A at the span top (a saturated reading)
    r = _run(drv, [bad] * 3)
    assert not any(has_code(m, "ENG-003") for m, _, _ in r)  # 3 frames: not yet
    r = _run(drv, [bad])
    assert has_code(r[0][0], "ENG-003")  # 4th consecutive frame: lane A failed
    assert r[0][1][S_N2] == V_SUSPECT and r[0][2][S_N2] == base[3]  # the other lane is used
    r = _run(drv, [base] * 11)
    # the first frame back is a rate excursion (1.10 -> 0.78 in one frame), so it is not a good frame;
    # the next 10 are: healed exactly on the 10th good frame
    assert all(has_code(m, "ENG-003") for m, _, _ in r[:10])
    assert not has_code(r[10][0], "ENG-003")
    # negative: a 3-frame excursion never fails the lane
    drv2, base2 = _setup()
    _run(drv2, [base2] * 5)
    r = _run(drv2, [bad] * 3 + [base2] * 5)
    assert not any(has_code(m, "ENG-003") for m, _, _ in r)


def test_rate_check_fails_after_four_frames_over_the_physical_bound():
    drv, base = _setup()
    _run(drv, [base] * 5)
    step = 0.04 * N1R  # 4 % per frame = 2.4/s > 1.5/s bound
    seq = []
    for k in range(1, 4):
        ln = base.copy()
        ln[0] = base[0] + k * step
        seq.append(ln)
    r = _run(drv, seq)
    assert not any(has_code(m, "ENG-001") for m, _, _ in r)
    ln = base.copy()
    ln[0] = base[0] + 4 * step
    r = _run(drv, [ln])
    assert has_code(r[0][0], "ENG-001")


def test_cross_channel_averages_when_agreeing_and_uses_the_safer_value_when_not():
    drv, base = _setup()
    r = _run(drv, [base] * 3)
    assert r[-1][1][S_N2] == V_OK and r[-1][2][S_N2] == 0.5 * (base[2] + base[3])
    off = base.copy()
    off[3] = base[3] + 0.03 * N2R  # lane B 3 % high (tolerance 2 %)
    off[4] = base[4] - 6.0  # T1 lane A 6 K low (tolerance 3 K)
    # the first frame of the offset is a lane-rate transient, which the rate term of the tolerance absorbs;
    # the disagreement then has to persist for 4 frames
    r = _run(drv, [off] * 4)
    assert all(v[S_N2] == V_OK for _, v, _ in r)
    assert r[-1][2][S_N2] == 0.5 * (off[2] + off[3])  # still averaged inside the persistence
    r = _run(drv, [off])
    assert has_code(r[0][0], "ENG-032") and has_code(r[0][0], "ENG-033")
    assert r[0][1][S_N2] == V_SUSPECT and r[0][2][S_N2] == off[3]  # N2: higher is safer
    assert r[0][1][S_T1] == V_SUSPECT and r[0][2][S_T1] == off[4]  # T1: lower is safer
    r = _run(drv, [base] * 10)
    assert r[8][1][S_N2] == V_SUSPECT and r[9][1][S_N2] == V_OK  # heal after 10 good frames


def test_both_lanes_lost_hold_then_substitute_and_accommodate():
    drv, base = _setup()
    _run(drv, [base] * 5)
    bad = base.copy()
    bad[2] = bad[3] = 1.12 * N2R
    r = _run(drv, [bad] * 3)  # inside the range persistence the (agreeing) bad lanes are still accepted
    last_accepted = r[-1][2][S_N2]
    assert last_accepted == 0.5 * (bad[2] + bad[3])
    r = _run(drv, [bad])
    assert r[-1][1][S_N2] == V_FAILED and r[-1][2][S_N2] == last_accepted  # hold
    assert has_code(r[-1][0], "ENG-052")
    acc = drv.ii(I_ACC)
    assert acc & ACC_N2_REDUCED and acc & ACC_AB_INHIBIT
    r = _run(drv, [bad] * 6)  # hold 0.1 s = 6 frames in all, then substitute
    states = [v[S_N2] for _, v, _ in r]
    assert V_FAILED in states and states[-1] == V_SUBSTITUTED
    assert drv.sel(S_N2) == pytest.approx(drv.fi(F_XMOD + S_N2))


def test_analytical_check_25_steady_45_transient_and_heals_after_10_good_frames():
    drv, base = _setup()
    _run(drv, [base] * 5)
    b24 = base.copy()
    b24[10:12] *= 1.24  # T5 common-mode +24 %: inside 25 %
    r = _run(drv, [b24] * 40)
    assert all(v[S_T5] == V_OK for _, v, _ in r)
    drv, base = _setup()
    _run(drv, [base] * 5)
    b30 = base.copy()
    b30[10:12] *= 1.30
    r = _run(drv, [b30] * 30)
    assert all(v[S_T5] == V_OK for _, v, _ in r[:29]) and r[29][1][S_T5] == V_SUBSTITUTED  # 0.5 s = 30 frames
    assert has_code(r[29][0], "ENG-046")
    r = _run(drv, [base] * 10)
    assert r[8][1][S_T5] == V_SUBSTITUTED and r[9][1][S_T5] == V_OK
    # transient (PLA moving > 5 deg/s): 30 % passes (45 % tolerance), 50 % fails
    for factor, expect_fail in ((1.30, False), (1.50, True)):
        drv, base = _setup()
        _run(drv, [base] * 5)
        b = base.copy()
        b[10:12] *= factor
        states = []
        for k in range(40):
            drv.frame(b, pla_deg=60.0 + 0.2 * k)  # 12 deg/s
            states.append(drv.vstate(S_T5))
        assert (V_SUBSTITUTED in states) is expect_fail


def test_slow_common_mode_drift_is_absorbed_by_the_adaptive_model():
    """Exposes the PROXY on-board model (A-W1.3b-7): a drift slower than the trims is never flagged, while the
    same
    error applied as a step is (the 'trapped static' class of fault in report §9)."""
    drv, base = _setup()
    _run(drv, [base] * 5)
    for k in range(1, 2401):  # +40 % over 40 s
        b = base.copy()
        b[10:12] *= 1.0 + 0.4 * k / 2400
        drv.frame(b)
        assert drv.vstate(S_T5) == V_OK
    drv, base = _setup()
    _run(drv, [base] * 5)
    b = base.copy()
    b[10:12] *= 1.4
    assert V_SUBSTITUTED in [v[S_T5] for _, v, _ in _run(drv, [b] * 40)]


def test_failure_mode_tolerance_too_wide_delays_or_misses_detection():
    for scale, detects in ((1.0, True), (2.0, False)):
        drv, base = _setup(vm_tol_scale=scale)
        _run(drv, [base] * 5)
        b = base.copy()
        b[10:12] *= 1.30  # 30 % common-mode T5 error: analytical check
        r = _run(drv, [b] * 40)
        assert (V_SUBSTITUTED in [v[S_T5] for _, v, _ in r]) is detects
        drv, base = _setup(vm_tol_scale=scale)
        _run(drv, [base] * 5)
        b = base.copy()
        b[3] = base[3] + 0.03 * N2R  # 3 % N2 lane disagreement: cross-channel check
        r = _run(drv, [b] * 40)
        assert any(has_code(m, "ENG-032") for m, _, _ in r) is detects


def test_failure_mode_scaling_wrap_accepts_a_failed_sensor():
    """T25 (single lane) fails high beyond its span: nominal -> range fail in 4 frames; with the wrap defect
    the reading re-enters the span and is accepted as valid until the analytical check catches it."""
    bad_value = 273.15 + 300.0  # 300 degC, beyond the 280 degC span top
    for wrap, first_flag_max in ((0, 4), (1, None)):
        drv, base = _setup(vm_wrap=wrap)
        _run(drv, [base] * 5)
        b = base.copy()
        b[6] = bad_value
        r = _run(drv, [b] * 25)
        flagged = [k for k, (_, v, _) in enumerate(r) if v[S_T25] != V_OK]
        if first_flag_max is not None:
            assert flagged and flagged[0] + 1 <= first_flag_max
        else:
            assert flagged == []  # accepted for 25 frames
            assert r[-1][2][S_T25] < 273.15  # ... as a wrapped, wrong value


def test_failure_mode_persistence_too_long_loses_a_fast_fault():
    for scale, detects in ((1.0, True), (10.0, False)):
        drv, base = _setup(vm_persist_scale=scale)
        _run(drv, [base] * 5)
        bad = base.copy()
        bad[2] = 1.10 * N2R
        r = _run(drv, [bad] * 18 + [base] * 5)  # a 0.3 s fault
        assert any(has_code(m, "ENG-003") for m, _, _ in r) is detects


def test_failure_mode_skew_plus_noise_gives_false_failures_in_transients():
    g = np.random.Generator(np.random.Philox(1302))  # fixed test input
    counts = {}
    for skew in (0, 8):
        drv, base = _setup(vm_skew_frames=skew)
        _run(drv, [base] * 10)
        false = 0
        for k in range(120):  # PS3 rising 100 psi/s on both lanes, +-0.5 psi independent noise
            b = base.copy()
            ramp = 100.0 * PSI * k / 60.0
            b[8] = base[8] + ramp + 0.5 * PSI * g.standard_normal()
            b[9] = base[9] + ramp + 0.5 * PSI * g.standard_normal()
            drv.frame(b, pla_deg=60.0 + 0.1 * k)
            false += has_code(drv.faults, "ENG-035")
        counts[skew] = false
    assert counts[0] == 0 and counts[8] > 0


def test_failure_mode_common_mode_fault_defeats_voting():
    drv, base = _setup()
    _run(drv, [base] * 5)
    cm = base.copy()
    cm[2:4] *= 1.10  # +10 % on both N2 lanes
    r = _run(drv, [cm] * 60)
    assert all(v[S_N2] == V_OK for _, v, _ in r)  # agreeing lanes, inside 25 %: accepted
    assert r[-1][2][S_N2] == pytest.approx(1.10 * base[2])
    drv, base = _setup()
    _run(drv, [base] * 5)
    single = base.copy()
    single[2] *= 1.10  # the same error on one lane only is caught by the cross-channel check
    assert any(has_code(m, "ENG-032") for m, _, _ in _run(drv, [single] * 10))
    # with the analytical check disabled even a gross common-mode error passes
    drv, base = _setup(vm_analytic=0)
    _run(drv, [base] * 5)
    gross = base.copy()
    gross[10:12] *= 1.35  # still inside the harness span, so only the analytical check could catch it
    assert all(v[S_T5] == V_OK for _, v, _ in _run(drv, [gross] * 60))


def test_accommodation_changes_the_plant_commands():
    # T5 harnesses open (full scale high): AB inhibited, nozzle forced to the safe position, T5 loop off
    drv, base = _setup(pla=87.0)
    _run(drv, [base] * 5, pla=87.0)
    bad = base.copy()
    bad[10:12] = 273.15 + 871.0
    _run(drv, [bad] * 12, pla=110.0)
    acc = drv.ii(I_ACC)
    assert acc & ACC_ACT_SAFE and acc & ACC_AB_INHIBIT
    assert drv.outi[0, 0, 1] == 0  # ab_enable stays 0 with PLA in the AB range
    floor = np.interp(np.deg2rad(110.0), drv.cfg.tables.a8_pla_x, drv.cfg.tables.a8_pla_y) * 1.087
    assert drv.outf[0, 0, 2] == pytest.approx(floor * 1.10, rel=1e-9)
    # N1 lost: the N2 limit drops by 1,000 rpm (103 % -> ~97 %). Ramp N2 to 99 % (inside the nominal limit) at
    # PLA 87 with a high-power T25 so the governor asks for more fuel: only the accommodated engine is
    # N2-limited.
    hi = lanes_from_state(steady_state(87.0, n2c=0.99)[0], quantise=False)  # a consistent high-power point
    wf_end = {}
    for fail_n1 in (True, False):
        drv, base = _setup(pla=70.0)
        _run(drv, [base] * 5, pla=70.0)
        codes = []
        for k in range(1, 181):
            w = min(k / 120.0, 1.0)
            b = base + w * (hi - base)  # every lane moves along the steady line (no analytical disagreement)
            if fail_n1:
                b[0] = b[1] = 1.2 * N1R
            else:
                # N1 lanes ramp a third of the way only (analytical check off): open loop, the full ramp
                # crosses the N1 limit (with the W2.1b rate anticipation) and takes the nominal engine down
                # to the decel schedule too, masking the N2 accommodation
                b[0:2] = base[0:2] + w / 3.0 * (hi[0:2] - base[0:2])
            drv.frame(b, pla_deg=87.0)
            codes.append(decode_active_limiter(drv.limiter)[0])
        assert bool(drv.ii(I_ACC) & ACC_N2_REDUCED) is fail_n1
        # open loop the lanes cannot respond, so the accommodated N2 limiter keeps cutting fuel down to the
        # decel
        # schedule; the nominal engine is never N2-limited and ends on accel/governor
        assert ("N2_MAX" in codes) is fail_n1
        wf_end[fail_n1] = drv.wf
    assert wf_end[True] < 0.95 * wf_end[False]


def test_second_like_failure_reverts_to_part_power():
    drv, base = _setup(pla=80.0)
    _run(drv, [base] * 5, pla=80.0)
    b = base.copy()
    b[0] = b[1] = 1.2 * N1R
    b[2] = b[3] = 1.2 * N2R
    _run(drv, [b] * 8, pla=80.0)
    assert drv.ii(I_ACC) & ACC_REVERSION and has_code(drv.faults, "ENG-508")
    assert drv.fi(F_N2C_DEM) <= 0.72 + 1e-12


def test_more_than_three_substitutions_are_refused():
    drv, base = _setup()
    _run(drv, [base] * 5)
    b = base.copy()
    b[2] = b[3] = 1.2 * N2R  # N2
    b[4] = b[5] = 273.15 + 160.0  # T1
    b[6] = 273.15 + 300.0  # T25
    b[8] = b[9] = 0.0  # PS3
    _run(drv, [b] * 20)
    states = [drv.vstate(s) for s in (S_N2, S_T1, S_T25, S_PS3)]
    assert states.count(V_SUBSTITUTED) == 3 and states.count(V_FAILED) == 1
    assert drv.ii(I_ACC) & ACC_REVERSION


def test_validator_counters_live_in_state():
    drv, base = _setup()
    _run(drv, [base] * 5)
    b = base.copy()
    b[10:12] *= 1.30
    _run(drv, [b] * 7)
    assert drv.ii(I_AN_CNT + S_T5) == 7 and drv.vstate(S_N1) == V_OK
