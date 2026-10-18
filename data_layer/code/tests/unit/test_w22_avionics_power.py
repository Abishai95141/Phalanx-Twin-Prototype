"""W2.2 M12 avionics: the electrical supply path from ``util.bus_v`` (AD-51, A-W2.2-1).

The coupling is physical: each LRU reads the voltage of its bus (M09 map), rides through interruptions shorter
than its hold-up and drops out after it. An in-flight INS/GPS power loss leaves the navigation outputs frozen
with unchanged status words (navigation invalid **without a flag**, report l.741, F-16 EGI AIB); on the
ground a power cycle re-aligns with the ALIGN mode word (flagged). Sample sizes: one sortie (identity
IDENTITY) per scenario, 3-256 s at 240 Hz; the behaviour is deterministic given the draws, so n = 1 answers
each question.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from phalanx.dictionary.params import load_params
from phalanx.sensors.avionics import ins as N
from phalanx.sensors.avionics.config import build_avionics_config


def _fixture():
    name = "w22_avionics_fixture"
    if name not in sys.modules:
        p = Path(__file__).resolve().parents[1] / "integration" / "test_w22_avionics_fixture.py"
        spec = importlib.util.spec_from_file_location(name, p)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


FX = _fixture()
CFG = build_avionics_config()
INS_BUS, AHRS_BUS, RADALT_BUS = CFG.bus["INGPS"], CFG.bus["AHRS"], CFG.bus["RADALT"]
NAV = ("rec_nav_ins_lat", "rec_nav_ins_lon", "rec_nav_ins_hdg_true", "rec_nav_ins_roll", "rec_nav_ins_vn")
STATUS = ("rec_nav_gps_status_ins_mode", "rec_nav_gps_status_gps_fix", "rec_nav_gps_status_fom")
HOLD_FRAMES = int(np.ceil(CFG.ins_p[N.P_HOLD] * 240.0))  # frames below v_dropout before the LRU drops out


def _dip(truth, bus: int, k0: int, frames: int, volts: float = 0.0):
    out = dict(truth)
    v = np.array(truth["util.bus_v"], copy=True)
    v[k0 : k0 + frames, bus] = volts
    out["util.bus_v"] = v
    return out


@pytest.mark.unit
@pytest.mark.parametrize("frames", [HOLD_FRAMES - 1, HOLD_FRAMES])
def test_interruption_shorter_than_hold_up_rides_through(frames):
    """A dip of hold-up - 1 frames (45.8 ms < 50 ms) keeps every LRU powered and the INS live; one more
    frame drops the INS/GPS out (MIL-STD-704F transfer interrupts are <= 50 ms)."""
    n, k0 = 2400, 1200
    truth = _dip(FX.default_truth(n), INS_BUS, k0, frames)
    _, o = FX.run_direct(FX.make_module(), truth, n)
    lost = frames >= HOLD_FRAMES
    assert bool(np.any(o["powered_ingps"] == 0)) is lost
    lat = o["rec_nav_ins_lat"]
    frozen = np.all(lat[k0 + frames :] == lat[k0 + frames])
    assert bool(frozen) is lost
    assert np.all(o["powered_ahrs"] == 1) and np.all(o["powered_radalt"] == 1)


@pytest.mark.unit
def test_in_flight_loss_freezes_navigation_without_a_flag():
    """INS bus at 0 V for 2 s from t = 5 s in flight, a 30 deg turn from t = 8 s. The INS outputs and status
    words freeze at their pre-loss values for the rest of the sortie (also after the power returns), while
    truth moves on: the navigation error grows to the distance flown (no flag tells the consumer). The AHRS
    on another bus keeps tracking the turn."""
    n = 240 * 20
    k_loss = 240 * 5
    truth = _dip(FX.default_truth(n, bank_deg={(8.0, 18.0): 30.0}), INS_BUS, k_loss, 480)
    _, o = FX.run_direct(FX.make_module(), truth, n)
    pw = o["powered_ingps"]
    k_off = int(np.argmax(pw == 0))
    assert k_off == k_loss + HOLD_FRAMES - 1 and np.all(pw[k_loss + 480 :] == 1)
    for p in NAV + STATUS:
        held = o[p][k_off:]
        assert np.all(held == held[0]), p
        assert held[0] == o[p][k_off - 1], f"{p}: the frozen value is the last live value"
    assert o["rec_nav_gps_status_ins_mode"][-1] == N.MODE_HYBRID  # no ALIGN / INERTIAL flag
    assert o["rec_nav_gps_status_gps_fix"][-1] == N.FIX_3D
    # error before the loss: aided-class; at the end: the distance flown since the freeze
    r = FX.R_EARTH + 3000.0
    err_before = abs(o["rec_nav_ins_lat"][k_off - 1] - o["tru_nav_ins_lat"][k_off - 1]) * r
    pos_t = truth["af.pos_geo"]
    flown = np.hypot(
        (pos_t[-1, 0] - pos_t[k_off, 0]) * r, (pos_t[-1, 1] - pos_t[k_off, 1]) * r * np.cos(pos_t[k_off, 0])
    )
    err_end = np.hypot(
        (o["rec_nav_ins_lat"][-1] - o["tru_nav_ins_lat"][-1]) * r,
        (o["rec_nav_ins_lon"][-1] - o["tru_nav_ins_lon"][-1]) * r * np.cos(pos_t[-1, 0]),
    )
    assert err_before < 150.0
    assert abs(err_end - flown) < 150.0 and flown > 2500.0
    # the AHRS (bus AHRS_BUS) is unaffected and follows the 30 deg bank
    roll_err = np.abs(o["rec_nav_ahrs_roll"] - o["tru_nav_ahrs_roll"])
    assert np.all(o["powered_ahrs"] == 1)
    assert np.degrees(o["rec_nav_ahrs_roll"][240 * 13]) == pytest.approx(30.0, abs=1.0)
    assert np.degrees(roll_err.max()) < 1.0


@pytest.mark.unit
def test_ground_power_cycle_realigns_with_a_flag():
    """On the ground (weight on wheels, stationary) a 1 s INS bus loss at t = 10 s restarts the INS: ALIGN for
    ``t_align`` (outputs held, mode word flagged), GPS re-acquired after ``t_gps_reacq``, then NAV_HYBRID with
    fresh turn-on errors (power-on draw 1). n = 256 s at 240 Hz."""
    t_align = float(CFG.ins_p[N.P_T_ALIGN])
    t_reacq = float(CFG.ins_p[N.P_T_REACQ])
    n = int(240 * (11 + t_align + 5))
    truth = _dip(FX.default_truth(n, speed=0.0, on_ground=True, hag=1.5), INS_BUS, 2400, 240)
    m = FX.make_module()
    s1, o1 = FX.run_direct(m, truth, 2400)
    s, o2 = FX.run_direct(m, truth, n - 2400, block=4800, state=s1, k0=2400)
    o = {k: np.concatenate([o1[k], o2[k]]) for k in o1}
    k_on = 2400 + 240  # first frame back at 28 V
    mode = o["rec_nav_gps_status_ins_mode"]
    fix = o["rec_nav_gps_status_gps_fix"]
    assert np.all(mode[:2400] == N.MODE_HYBRID)
    align = mode[k_on:]
    k_nav = int(np.argmax(align == N.MODE_HYBRID))
    assert np.all(align[:k_nav] == N.MODE_ALIGN)
    assert k_nav / 240.0 == pytest.approx(t_align, abs=2.0 / 240.0)
    k_fix = int(np.argmax(fix[k_on:] == N.FIX_3D))
    assert k_fix / 240.0 == pytest.approx(t_reacq, abs=2.0 / 240.0)
    lat = o["rec_nav_ins_lat"][k_on : k_on + k_nav]
    assert np.all(lat == lat[0])  # held while aligning
    assert int(s["ins_i"][N.I_NPOWER]) == 1  # one restart: the second power-on draw
    bg = slice(N.F_BG0, N.F_BG0 + 3)
    assert np.all(s["ins_f"][bg] != s1["ins_f"][bg])  # fresh turn-on gyro biases


@pytest.mark.unit
@pytest.mark.parametrize("bus", [0, 1, 2])
def test_each_lru_follows_its_own_bus(bus):
    """A 1 s loss of one bus in flight drops exactly the LRUs fed from it (A-W2.2-1 allocation)."""
    n = 240 * 4
    truth = _dip(FX.default_truth(n, hag=300.0), bus, 480, 240)
    _, o = FX.run_direct(FX.make_module(), truth, n)
    for lru, port in (
        ("INGPS", "powered_ingps"),
        ("AHRS", "powered_ahrs"),
        ("RADALT", "powered_radalt"),
        ("SMS", "powered_sms"),
    ):
        assert bool(np.any(o[port] == 0)) is (CFG.bus[lru] == bus), lru


@pytest.mark.unit
@pytest.mark.parametrize(("v_dropout", "lost"), [(16.0, False), (18.0, True)])
def test_dropout_voltage_is_the_swept_parameter(v_dropout, lost):
    """A 17 V sag for 1 s (inside MIL-STD-704F abnormal limits) is ridden through at the nominal 16 V dropout
    and drops the INS at the sweep's upper end (18 V): the coupling reads M12_AVIONICS.yaml
    power.v_dropout."""
    params = load_params("M12_AVIONICS")
    params["power"] = params["power"].replace(v_dropout=v_dropout)
    cfg = build_avionics_config(params=params)
    n = 240 * 3
    truth = _dip(FX.default_truth(n), INS_BUS, 240, 240, volts=17.0)
    _, o = FX.run_direct(FX.make_module(config=cfg), truth, n)
    assert bool(np.any(o["powered_ingps"] == 0)) is lost
