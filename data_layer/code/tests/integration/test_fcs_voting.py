"""A4: redundancy management - injected sensor-lane and channel faults vote out correctly; air-data loss
latches
the fixed-gain reversion; resets. Open loop on the M05 module (no airframe needed: lanes are scripted).

Each case runs 0.25-2 s of truth ticks (n = 1 deterministic scenario per case; timings checked to the frame).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.acquisition.module import lane_port
from phalanx.airframe.analysis import isa
from phalanx.core.events import Event
from phalanx.core.time import truth_step_times_ns
from phalanx.fcs.layout import (
    CCDL_FAIL,
    CH_DROPOUT,
    CH_FAILED,
    CH_RESET,
    FLAG_REVERSION,
    I_ADMIS,
    I_ADVALID,
    I_FLAGS,
    I_LAW,
    I_LFAIL,
    LAW_FIXED,
    LAW_SCHEDULED,
    MIS_AOA_VANE,
    SIG_POS0,
    SIG_PS,
    SIG_Q,
    SIG_SP,
    SUB_CCDL,
    SUBSYSTEMS,
)
from phalanx.fcs.module import Fcs, FcsIC
from phalanx.fcs.ports import VOTED_SIGNALS, lane_inputs

G0 = 9.80665
FRAME = 3  # ticks per DFCC frame


def _pt(ps, m):
    return ps * (1 + 0.2 * m * m) ** 3.5


def make(on_ground=False, mach=0.6, h=5000.0, alpha=0.05):
    surf = np.zeros(13)
    return Fcs.from_registry("fcs", FcsIC(surf=surf, alpha=alpha, mach=mach, hp=h, on_ground=on_ground))


def L(stem: str, lane: str) -> str:
    """Input port of lane ``lane`` (a..d) of the voted signal ``stem``."""
    meas = next(m for st, m, _, _ in VOTED_SIGNALS if st == stem)
    return lane_port(f"{meas}.{lane.upper()}")


def _vane_calibration() -> tuple[float, float, float, float]:
    """M05's nominal vane calibration (local = k1 angle + c0, A-W1.2-25): AoA k1, c0; AoSS k1, c0 (SI)."""
    from phalanx.fcs.layout import P_BC0, P_BK1, P_VC0, P_VK1

    p = make().cfg.p
    return float(p[P_VK1]), float(p[P_VC0]), float(p[P_BK1]), float(p[P_BC0])


def base_inputs(n, *, mach=0.6, h=5000.0, alpha=0.05, wow=0):
    ps = isa(h)[3]
    vk1, vc0, _bk1, bc0 = _vane_calibration()
    val = {
        "rsa_p": 0.0,
        "rsa_q": 0.0,
        "rsa_r": 0.0,
        "asa_nz": G0,
        "asa_ny": 0.0,
        "aoa_l": vk1 * alpha + vc0,  # the vanes read the local flow (A-W1.2-25)
        "aoa_r": vk1 * alpha + vc0,
        "aoss": bc0,
        "ps": ps,
        "pt": _pt(ps, mach),
    }
    d = {
        "airbrake_cmd": np.zeros(n, np.int64),
        "gear_cmd": np.zeros(n, np.int64),
        "hyd_dp_avail": np.full((n, 2), 2.8e7),
        "health_actuator": np.zeros((n, 13)),
        "alpha": np.full(n, alpha),
        "beta": np.zeros(n),
        "qbar": np.full(n, 0.7 * ps * mach * mach),
        "wow": np.tile([(int(wow) >> leg) & 1 for leg in range(3)], (n, 1)).astype(np.int64),  # bit field
    }
    for sig, _c, cid in lane_inputs():  # lane sample buffers (capacity 1); surfaces and inceptors at 0
        d[lane_port(cid)] = np.full((n, 1), val.get(VOTED_SIGNALS[sig][0], 0.0))
    return d


def run(mod, state, inputs, k0=0):
    n = inputs["wow"].shape[0]
    t = truth_step_times_ns(np.arange(k0, k0 + n, dtype=np.int64))
    return mod.step_block(state, inputs, t, 1.0 / 240.0)


@pytest.mark.integration
def test_hardover_lane_voted_out_after_persistence_and_vote_unaffected():
    """A q lane (B) hard-over to +0.5 rad/s from tick 30 (frame 10) fails after exactly 8 frames of mistrack;
    the
    mid-value vote never moves (mean of the middle two of four)."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(120)
    inp[L("rsa_q", "b")][30:] = 0.5
    st2, out = run(mod, st, inp)
    assert st2["i"][I_LFAIL + SIG_Q] == 0b0010
    # frame-by-frame: failed at the 8th consecutive mistrack frame (frames 10..17 -> latched in frame 17)
    s = mod.init(mod.params, None)
    for k in range(0, 120, FRAME):
        sub = {key: v[k : k + FRAME] for key, v in inp.items()}
        s, _ = run(mod, s, sub, k)
        frame = k // FRAME
        assert (s["i"][I_LFAIL + SIG_Q] != 0) == (frame >= 17), frame
    assert s["f"][mod_vote_index(SIG_Q)] == 0.0
    assert np.all(out["law_state"] == LAW_SCHEDULED)


def mod_vote_index(sig):
    from phalanx.fcs.layout import F_VOTE

    return F_VOTE + sig


@pytest.mark.integration
def test_drift_below_threshold_is_not_detected_and_biases_vote_partially():
    """A slow 0.04 rad/s bias on one q lane stays below the 3 deg/s mistrack threshold: never failed (the vote
    absorbs half of it through the middle-two mean - a realistic latent sensor fault)."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(480)
    inp[L("rsa_q", "c")][:] = 0.04
    st2, _ = run(mod, st, inp)
    assert st2["i"][I_LFAIL + SIG_Q] == 0
    assert st2["f"][mod_vote_index(SIG_Q)] == pytest.approx(0.0)  # middle two of (0,0,0,0.04) are 0, 0


@pytest.mark.integration
def test_second_and_third_failures():
    """Second hard-over (with three lanes left) is isolated by the median; a later A/D disagreement with two
    lanes
    left cannot be isolated, so the signal is lost (both lanes failed) and the last good vote is held."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(300)
    inp[L("rsa_q", "b")][0:] = 0.5
    inp[L("rsa_q", "c")][90:] = -0.5
    inp[L("rsa_q", "a")][180:] = 0.2
    inp[L("rsa_q", "d")][180:] = -0.2
    st2, _ = run(mod, st, inp)
    assert st2["i"][I_LFAIL + SIG_Q] == 0b1111
    assert st2["f"][mod_vote_index(SIG_Q)] == pytest.approx(0.0)


@pytest.mark.integration
def test_channel_failure_dropout_and_reset():
    """A CPU fault on channel C drops the channel at once (DROPOUT), is latched as FAILED after the CBIT
    persistence, and channel C's lanes leave the vote (a hard-over on lane C is then not even monitored). When
    the
    fault clears, a reset restores the channel and shows CHANNEL_RESET for 1 s; CCDL faults set CCDL_FAIL."""
    mod = make()
    st = mod.init(mod.params, None)
    ev = Event(
        0, "fcs.channel_fault", "fcs", {"channel": 2, "subsystem": SUBSYSTEMS.index("CPU"), "active": True}
    )
    st, _ = mod.on_event(st, ev, 0)
    inp = base_inputs(60)
    inp[L("rsa_q", "c")][:] = 1.0
    st, out = run(mod, st, inp)
    assert out["channel_status"][0, 2] & CH_DROPOUT
    assert out["channel_status"][-1, 2] & CH_FAILED
    assert st["i"][I_LFAIL + SIG_Q] == 0  # excluded, not voted out
    assert st["f"][mod_vote_index(SIG_Q)] == 0.0
    st, _ = mod.on_event(st, Event(0, "fcs.reset", "fcs"), 0)
    assert st["i"][I_LAW] == LAW_SCHEDULED
    st, out = run(mod, st, base_inputs(30), 60)
    assert out["channel_status"][-1, 2] & CH_FAILED  # critical fault still present: reset refused
    clear = Event(
        0, "fcs.channel_fault", "fcs", {"channel": 2, "subsystem": SUBSYSTEMS.index("CPU"), "active": False}
    )
    st, _ = mod.on_event(st, clear, 0)
    st, _ = mod.on_event(st, Event(0, "fcs.reset", "fcs"), 0)
    st, out = run(mod, st, base_inputs(300), 90)
    assert out["channel_status"][0, 2] == CH_RESET
    assert out["channel_status"][-1, 2] == 0  # RESET bit shown for 1 s (80 frames) only
    ccdl = Event(0, "fcs.channel_fault", "fcs", {"channel": 1, "subsystem": SUB_CCDL, "active": True})
    st, _ = mod.on_event(st, ccdl, 0)
    st, out = run(mod, st, base_inputs(30), 390)
    assert out["channel_status"][-1, 1] & CCDL_FAIL and not out["channel_status"][-1, 1] & CH_FAILED


@pytest.mark.integration
def test_vane_mistrack_latches_reversion_until_reset():
    """L/R AoA vanes disagreeing by 8 deg (> 5 deg) for 8 frames: both excluded, air data invalid, the law
    reverts
    to FIXED_GAIN (code 1) with REVERSION_LATCHED; AIRDATA_MISTRACK shows AOA_VANE_MISTRACK; a reset
    restores."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(90)
    vk1, vc0, _, _ = _vane_calibration()
    for lane in "abcd":  # the right vane reads the local flow of alpha + 8 deg
        inp[L("aoa_r", lane)][:] = vk1 * (0.05 + math.radians(8.0)) + vc0
    st, out = run(mod, st, inp)
    assert out["law_state"][-1] == LAW_FIXED and st["i"][I_ADVALID] == 0
    assert st["i"][I_FLAGS] & FLAG_REVERSION and st["i"][I_ADMIS] & MIS_AOA_VANE
    first = int(np.argmax(out["law_state"] == LAW_FIXED))
    assert first == 7 * FRAME  # latched in the 8th consecutive mistrack frame (frames 0..7)
    st, _ = mod.on_event(st, Event(0, "fcs.reset", "fcs"), 0)
    st, out = run(mod, st, base_inputs(30), 90)
    assert out["law_state"][-1] == LAW_SCHEDULED and st["i"][I_ADVALID] == 1


@pytest.mark.integration
def test_static_pressure_lane_failure_is_tolerated():
    """One static-pressure lane (ADC B) reads 50 mbar high: voted out, air data stays valid (no reversion)."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(90)
    inp[L("ps", "b")] = inp[L("ps", "b")] + 5000.0
    st, out = run(mod, st, inp)
    assert st["i"][I_LFAIL + SIG_PS] == 0b0010 and st["i"][I_ADVALID] == 1
    assert np.all(out["law_state"] == LAW_SCHEDULED)
    assert st["i"][I_ADMIS] & 0b0010  # ADC_B_EXCLUDED


@pytest.mark.integration
def test_stuck_stick_lane_voted_out_and_surface_position_lane_reported():
    """A stick-pitch lane (D) stuck at full aft is failed after 8 frames and the voted stick stays 0 (no pitch
    command reaches the law); a rudder position lane (A) reading 5 deg off is failed and reported as
    LVDT_SUM_FAIL_A (bit 4) in FCS.ACT.BIT.RUDDER, with CBIT_FAIL in AV.LRU.BIT.DFCC."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(60)
    inp[L("stick_pitch", "d")][:] = 1.0
    inp[L("pos_rudder", "a")][:] = math.radians(5.0)
    st, out = run(mod, st, inp)
    assert st["i"][I_LFAIL + SIG_SP] == 0b1000
    assert out["rec_fcs_stick_pitch_v"][-1] == 0.0
    assert np.all(np.abs(out["rec_fcs_voted_de"]) < 1e-9)
    assert out["rec_fcs_act_bit_rudder"][-1] == 1 << 4
    assert out["rec_av_lru_bit_dfcc"][-1] & 4
    assert out["rec_fcs_act_bit_elevon_lob"][-1] == 0


@pytest.mark.integration
def test_dual_lane_slat_position_disagreement_loses_the_signal():
    """Slat position transducers are duplex (lanes A, B): a persistent A/B disagreement cannot be isolated,
    both lanes are failed (LVDT_SUM_FAIL_A and _B) and the last good voted position is held."""
    mod = make()
    st = mod.init(mod.params, None)
    inp = base_inputs(60)
    inp[L("pos_slat_ob_l", "b")][:] = math.radians(10.0)
    st, out = run(mod, st, inp)
    assert st["i"][I_LFAIL + SIG_POS0 + 5] == 0b0011
    assert out["rec_fcs_act_bit_slat_ob_l"][-1] == 0b0011 << 4
    assert out["rec_fcs_slat_pos_ob_l_v"][-1] == pytest.approx(math.radians(5.0))  # held mean of 0 and 10 deg


def test_lane_inputs_cover_the_dfcc_lanes():
    """Every lane input is a DFCC in-loop lane of M13 (lane_channels); the only DFCC lane not consumed is the
    single-lane total air temperature (A-W1.2-28)."""
    from phalanx.acquisition.module import lane_channels
    from phalanx.dictionary import load_dictionary
    from phalanx.sensors.config import build_sensor_config

    d = load_dictionary()
    dfcc = set(lane_channels(d, build_sensor_config(d, n_engines=1), "DFCC"))
    mine = {cid for _s, _c, cid in lane_inputs()}
    assert mine <= dfcc
    assert dfcc - mine == {"AD.TAT"}
    assert len(mine) == 4 * 18 + 2 * 8
