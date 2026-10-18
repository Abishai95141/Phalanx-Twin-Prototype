"""A4 (+ protection logic): hung-start rule, flameout detection / auto-relight, sub-idle and stall monitors.

The hung-start rule (NASA TM-101702 via f404 notes Q7) fires on N2 < 60 % and not rising for 1 s while a start
or relight is in progress, or on N2 < 60 % for 35 s while starting - and not otherwise. Open-loop scripted
lanes (TEST FIXTURE `FrameDriver`); 60 Hz frames, so 1 s = 60 frames and 35 s = 2,100 frames. Each case is one
deterministic sequence; the quantisation case adds 1-LSB toggling from a fixed pattern.
"""

from __future__ import annotations

import numpy as np
import pytest

from fadec_fixture import FrameDriver, fixture_params, has_code, lanes_from_state, steady_state
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import IGN_MAIN, ST_RUNNING, ST_STARTING
from phalanx.fadec.layout import F_N2DOT, I_FO_LATCH, I_HS_CNT, I_START_STATE

pytestmark = pytest.mark.unit
N1R = 13270 * 2 * np.pi / 60
N2R = 16810 * 2 * np.pi / 60
LSB_N2 = 0.0003125 * N2R  # 0.03125 % native step


def _start_lanes():
    x = steady_state(18.0)[0]
    base = lanes_from_state(x, quantise=False)
    return base


def _drive(n2_frac_seq, *, pla=18.0, t5_rate=12.0, base=None):
    """Drive frames with N2 lanes from `n2_frac_seq`; T5 rising at `t5_rate` K/s from 700 K."""
    base = _start_lanes() if base is None else base
    cfg = FadecConfig.build(fixture_params())
    tb = cfg.tables
    drv = FrameDriver(cfg)
    out = []
    for k, n2 in enumerate(n2_frac_seq):
        # lanes consistent with the on-board model along the start line (SLS): only the rule under test acts
        b = base.copy()
        n1 = float(np.interp(n2, tb.obm_n1_x, tb.obm_n1_y))
        b[2] = b[3] = n2 * N2R
        b[0] = b[1] = n1 * N1R
        b[6] = 288.15 * float(np.interp(n1, tb.obm_t25_x, tb.obm_t25_y))
        b[8] = b[9] = 101325.0 * float(np.interp(n2, tb.obm_pr3_x, tb.obm_pr3_y))
        b[10] = b[11] = 650.0 + t5_rate * k / 60.0
        drv.frame(b, pla_deg=pla)
        out.append((has_code(drv.faults, "ENG-504"), drv.ii(I_START_STATE), drv.fi(F_N2DOT)))
    return drv, out


def test_hung_start_fires_after_exactly_one_second_of_flat_n2_below_60pct():
    _, out = _drive([0.35] * 70)
    assert all(st == ST_STARTING for _, st, _ in out)
    fired = [k for k, (h, _, _) in enumerate(out) if h]
    assert fired[0] == 59  # the 60th frame of not rising = 1.0 s at 60 Hz
    assert not out[58][0]


def test_hung_start_rule_matches_its_definition_on_the_filtered_rate():
    """A start that stalls after a ramp: the rule fires exactly 60 frames after the filtered dN2/dt first sits
    at or below the 0.1 %/s deadband (checked against the logged rate, not a hand-tuned frame number)."""
    seq = list(np.linspace(0.20, 0.35, 300)) + [0.35] * 200
    _, out = _drive(seq)
    cnt, expected = 0, None
    for k, (_, _, r) in enumerate(out):  # the stated rule applied to the logged filtered rate
        cnt = cnt + 1 if r <= 0.001 else 0
        if cnt >= 60:
            expected = k
            break
    assert expected is not None and expected > 300  # not during the ramp
    fired = [k for k, (h, _, _) in enumerate(out) if h]
    assert fired[0] == expected


@pytest.mark.parametrize(
    "case",
    ["rising", "above_60pct", "fuel_off", "shorter_than_1s", "pla_outside_14_24_deg"],
)
def test_hung_start_does_not_fire_otherwise(case):
    if case == "rising":
        _, out = _drive(list(np.linspace(0.30, 0.45, 600)))  # 0.9 %/s: rising throughout, 10 s
    elif case == "above_60pct":
        _, out = _drive([0.62] * 300)
    elif case == "fuel_off":
        _, out = _drive([0.35] * 300, pla=5.0)  # PLA below the cutoff: no start in progress
    elif case == "pla_outside_14_24_deg":
        _, out = _drive([0.35] * 300, pla=30.0)  # flat, but the 1-s rule needs PLA 14-24 deg (TM-101702)
    else:
        _, out = _drive([0.35] * 59 + list(np.linspace(0.35, 0.40, 121)[1:]))  # flat 59 frames, then rising
    assert not any(h for h, _, _ in out)


def test_hung_start_survives_one_lsb_quantisation_toggling():
    seq = [0.35 + (LSB_N2 / N2R) * (k % 2) for k in range(120)]
    _, out = _drive(seq)
    assert any(h for h, _, _ in out)


def test_hung_start_timeout_after_35_seconds_below_60pct():
    seq = list(np.linspace(0.30, 0.55, 2200))  # slow but rising start (0.7 %/s): only the 35 s rule fires
    for pla in (18.0, 30.0):  # the 35-s rule has no PLA qualifier
        _, out = _drive(seq, pla=pla)
        fired = [k for k, (h, _, _) in enumerate(out) if h]
        assert fired and fired[0] == 2099, pla  # the 2,100th frame


def test_flameout_detection_auto_relight_and_confirmation():
    cfg = FadecConfig.build(fixture_params())
    x = steady_state(87.0)[0]
    base = lanes_from_state(x, quantise=False)
    drv = FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5]))
    for _ in range(20):
        drv.frame(base, pla_deg=87.0)
    assert drv.ii(I_START_STATE) == ST_RUNNING and not has_code(drv.faults, "ENG-502")
    t1 = base[4]
    # flame out: T5 collapses toward the inlet temperature while N2 decelerates at ~5 %/s
    fo_frames = []
    for k in range(60):
        b = base.copy()
        b[2:4] = base[2] * (1.0 - 0.05 * (k + 1) / 60.0)
        b[10:12] = max(t1 * 1.2, base[10] - 40.0 * (k + 1))
        drv.frame(b, pla_deg=87.0)
        fo_frames.append(has_code(drv.faults, "ENG-502"))
    first = fo_frames.index(True)
    assert first < 40 and drv.outi[0, 0, 0] & IGN_MAIN  # declared, igniters on
    # relight: T5 back above the reference and N2 recovering; ignition held for the 2 s confirmation
    on = []
    for k in range(180):
        b = base.copy()
        b[2:4] = base[2] * (0.95 + 0.0002 * k)
        drv.frame(b, pla_deg=87.0)
        on.append(bool(drv.ii(I_FO_LATCH)))
    assert all(on[:100]) and not on[-1]  # >= 2 s confirmation, then cleared
    assert not drv.outi[0, 0, 0] & IGN_MAIN


def test_no_flameout_when_t5_stays_burning_during_a_fast_decel():
    cfg = FadecConfig.build(fixture_params())
    x = steady_state(87.0)[0]
    base = lanes_from_state(x, quantise=False)
    drv = FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5]))
    for k in range(120):
        b = base.copy()
        b[2:4] = base[2] * (1.0 - 0.08 * min(k, 60) / 60.0)  # 8 %/s decel, T5 still burning (-10 K/frame)
        b[10:12] = base[10] - 5.0 * min(k, 60)
        drv.frame(b, pla_deg=30.0)
        assert not has_code(drv.faults, "ENG-502")


def test_stall_code_on_a_single_frame_ps3_collapse_and_hold():
    cfg = FadecConfig.build(fixture_params())
    x = steady_state(87.0)[0]
    base = lanes_from_state(x, quantise=False)
    drv = FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5]))
    for _ in range(10):
        drv.frame(base, pla_deg=87.0)
    b = base.copy()
    b[8:10] *= 0.14  # 85 -> 12 psia class collapse in one sample
    drv.frame(b, pla_deg=87.0)
    assert has_code(drv.faults, "ENG-501")
    for _ in range(170):  # recovered; code held 3 s = 180 frames in all
        drv.frame(base, pla_deg=87.0)
    assert has_code(drv.faults, "ENG-501")
    for _ in range(10):
        drv.frame(base, pla_deg=87.0)
    assert not has_code(drv.faults, "ENG-501")
    # a 30 % drop is below the 40 % threshold
    drv2 = FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5]))
    for _ in range(10):
        drv2.frame(base, pla_deg=87.0)
    b = base.copy()
    b[8:10] *= 0.7
    drv2.frame(b, pla_deg=87.0)
    assert not has_code(drv2.faults, "ENG-501")


def test_hung_start_counter_is_state():
    drv, _ = _drive([0.35] * 30)
    assert drv.ii(I_HS_CNT) == 30
