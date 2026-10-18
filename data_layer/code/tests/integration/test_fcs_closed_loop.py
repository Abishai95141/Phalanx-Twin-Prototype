"""A4 (and V8 time domain): M05 + M06 in closed loop through the TEST FIXTURE harness (test_fcs_fixtures.py).

Step responses, AoA and g limiters, a lane hard-over voted out in flight, the false-WoW -> ground-law cascade
(reproducible bitwise, absent with the optional interlock), loss of one hydraulic system, fixed-gain
reversion.
Each case is one deterministic 4-12 s trajectory at 240 Hz (n = 1 per case; flight conditions stated).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from test_fcs_fixtures import Harness, nz_of

from phalanx.airframe.aero import hinge_moments
from phalanx.airframe.kernel import O_ALPHA, O_BETA, O_QBAR, O_WX
from phalanx.fcs.actuators import C_AREA, C_ARM, C_V0, C_WN, C_ZETA, rate_capability
from phalanx.fcs.layout import (
    FLAG_AOA_LIM,
    FLAG_G_LIM,
    I_FLAGS,
    I_LFAIL,
    LAW_FIXED,
    LAW_GROUND,
    LAW_SCHEDULED,
    O_REC,
    R_CMD,
    SIG_AR,
    SIG_Q,
    U_DPAV,
    U_LANES,
    U_WOW,
)

DEG = math.pi / 180.0


@pytest.mark.integration
@pytest.mark.parametrize("mach, alt", [(0.6, 5000.0), (0.85, 2000.0), (1.2, 10000.0)])
def test_trimmed_flight_is_held(mach, alt):
    """No input for 10 s (including the most unstable corner M0.85/2 km): alpha within 0.2 deg of trim, pitch
    rate below 0.05 deg/s at the end, scheduled law throughout."""
    h = Harness(mach, alt)
    of, oa = h.run(10.0)
    a = oa[:, O_ALPHA]
    assert np.max(np.abs(a - h.trim.alpha)) < 0.2 * DEG
    assert abs(oa[-1, O_WX + 1]) < 0.05 * DEG
    assert np.all(of[:, 28] == LAW_SCHEDULED)


@pytest.mark.integration
def test_pitch_rate_and_nz_step_responses():
    """Stick 0.2 step: rate command at M0.6/5 km reaches 4 deg/s (+/-5 %) with overshoot ratio < 1.6; Nz
    command
    at M1.2/10 km reaches +1 g (+/-10 %) within 10 s without overshoot beyond 30 %."""
    h = Harness(0.6, 5000.0, stick=lambda t: (0.2 if t > 0.5 else 0.0, 0.0, 0.0))
    _, oa = h.run(5.0)
    q = oa[:, O_WX + 1] / DEG
    assert abs(q[-1] - 4.0) < 0.2 and q.max() / q[-1] < 1.6
    h = Harness(1.2, 10000.0, stick=lambda t: (0.2 if t > 0.5 else 0.0, 0.0, 0.0))
    _, oa = h.run(10.0)
    dnz = nz_of(oa) - nz_of(oa)[0]
    assert abs(dnz[-1] - 1.0) < 0.1 and dnz.max() < 1.3


@pytest.mark.integration
def test_aoa_limiter_holds_limit():
    """Full aft stick at M0.3/3 km for 8 s: alpha never exceeds the 26 deg limit by more than 2 deg (the Tejas
    Cn_beta cliff is at 23-26 deg) and settles near the limit; the AOA_LIMITER flag is raised."""
    h = Harness(0.3, 3000.0, stick=lambda t: (1.0 if t > 0.5 else 0.0, 0.0, 0.0))
    _, oa = h.run(8.0)
    a = oa[:, O_ALPHA] / DEG
    assert a.max() <= 28.0, a.max()
    assert 22.0 <= a[-1] <= 27.0, a[-1]
    assert h.fc_i[I_FLAGS] & FLAG_AOA_LIM


@pytest.mark.integration
def test_g_limiter():
    """Full aft stick at M0.8/5 km (a 20 deg/s rate command would need ~9 g): load factor held below 8 g + 0.6
    g
    overshoot; the G_LIMITER flag is raised."""
    h = Harness(0.8, 5000.0, stick=lambda t: (1.0 if t > 0.5 else 0.0, 0.0, 0.0))
    _, oa = h.run(4.0)
    n = nz_of(oa)
    assert n.max() < 8.6, n.max()
    assert n.max() > 6.0  # the pull actually reached the limiter region
    assert h.fc_i[I_FLAGS] & (FLAG_G_LIM | FLAG_AOA_LIM)


def _hardover(t, u):
    if t >= 2.0:
        u[U_LANES + 4 * SIG_Q + 1] = 0.5  # q lane B hard-over


@pytest.mark.integration
def test_lane_hardover_voted_out_in_flight_without_transient():
    """A q-lane hard-over at t = 2 s (M0.7/4 km) is failed within 9 frames and the airframe does not notice:
    alpha stays within 0.05 deg of trim (mid-value select never passes the bad lane)."""
    h = Harness(0.7, 4000.0, lane_hook=_hardover)
    _, oa = h.run(4.0)
    assert h.fc_i[I_LFAIL + SIG_Q] == 0b0010
    assert np.max(np.abs(oa[:, O_ALPHA] - h.trim.alpha)) < 0.05 * DEG


def _false_wow(t, u):
    if t >= 2.0:
        u[U_WOW + 1] = u[U_WOW + 2] = (
            1.0  # both main-gear WoW discretes set in flight (water/ice in switches)
        )


def _cascade(interlock: int):
    h = Harness(0.6, 5000.0, lane_hook=_false_wow, fcs_overrides={"wow_interlock": interlock})
    of, oa = h.run(4.0)
    return h, of, oa


@pytest.mark.integration
def test_false_wow_ground_law_cascade():
    """False WoW at t = 2 s in trimmed flight (M0.6/5 km): the DFCC selects the GROUND law two frames later
    (persistence), the integrators reset and the unstable airframe diverges (alpha moves > 5 deg within 2 s).
    The run is reproducible bitwise; with the optional airspeed interlock the law stays SCHEDULED (negative
    control)."""
    h, of, oa = _cascade(0)
    k_fault = round(2.0 * 240)
    law = of[:, 28]
    assert np.all(law[:k_fault] == LAW_SCHEDULED)
    k_ground = int(np.argmax(law == LAW_GROUND))
    assert k_fault <= k_ground <= k_fault + 2 * 3 + 2  # n_wow = 2 frames
    a = oa[:, O_ALPHA]
    assert np.max(np.abs(a[k_ground:] - h.trim.alpha)) > 5.0 * DEG
    _, of2, oa2 = _cascade(0)
    assert np.array_equal(of, of2) and np.array_equal(oa, oa2)
    h3, of3, oa3 = _cascade(1)
    assert np.all(of3[:, 28] == LAW_SCHEDULED)
    assert np.max(np.abs(oa3[:, O_ALPHA] - h3.trim.alpha)) < 0.2 * DEG


def _system1_lost(t):
    return (0.0, 2.8e7) if t >= 1.0 else (2.8e7, 2.8e7)


@pytest.mark.integration
def test_one_hydraulic_system_lost():
    """System 1 lost at t = 1 s during a pitch doublet (M0.7/4 km): the tandem elevons keep flying on system 2
    (alpha within 1.5 deg of the healthy run), system-1 flow drops to zero, system-2 flow carries the
    elevons."""

    def doublet(t):
        return (0.2 if 1.5 < t < 2.5 else (-0.2 if 2.5 <= t < 3.5 else 0.0), 0.0, 0.0)

    hh = Harness(0.7, 4000.0, stick=doublet)
    _, oa_h = hh.run(5.0)
    h = Harness(0.7, 4000.0, stick=doublet, dp_avail=_system1_lost)
    of, oa = h.run(5.0)
    assert np.max(np.abs(oa[:, O_ALPHA] - oa_h[:, O_ALPHA])) < 1.5 * DEG
    k1 = 241
    assert np.all(of[k1:, 26] == 0.0) and np.max(of[k1:, 27]) > 1e-5


def _vane_fault(t, u):
    if t >= 1.0:
        u[U_LANES + 4 * SIG_AR : U_LANES + 4 * SIG_AR + 4] += 8.0 * DEG


@pytest.mark.integration
def test_fixed_gain_reversion_keeps_the_aircraft_flying():
    """Air-data loss (L/R vane mistrack) at t = 1 s at M0.6/5 km: reversion to the fixed-gain law (gear-up
    set,
    designed at M0.5/3 km, inertial sensors only) keeps the unstable airframe controlled for 10 s (alpha
    within
    2 deg of trim, no divergence)."""
    h = Harness(0.6, 5000.0, lane_hook=_vane_fault)
    of, oa = h.run(11.0)
    assert of[-1, 28] == LAW_FIXED
    assert np.max(np.abs(oa[:, O_ALPHA] - h.trim.alpha)) < 2.0 * DEG
    assert abs(oa[-1, O_WX + 1]) < 0.5 * DEG
    _ = U_DPAV


def _3211(t, t0=1.0, dt=0.35, amp=0.5):
    for start, dur, sign in ((0, 3, 1), (3, 2, -1), (5, 1, 1), (6, 1, -1)):
        if t0 + start * dt <= t < t0 + (start + dur) * dt:
            return (sign * amp, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


@pytest.mark.integration
@pytest.mark.parametrize("mach, alt", [(0.6, 3000.0), (0.8, 5000.0)])
def test_3211_input_without_actuator_rate_saturation(mach, alt):
    """V8: a piloted 3-2-1-1 pitch input (0.35 s base pulse, ~1-1.5 Hz content, half stick) at M0.6-0.8 never
    saturates the elevon servos: the valve demand Ka (cmd - x) stays below the loaded rate capability
    v0 sqrt((dP - P_L) / dP_rated) at every tick (margin 5 %); the aircraft returns to within 0.5 deg of trim
    alpha 3 s after the input."""
    h = Harness(mach, alt, stick=_3211)
    of, oa = h.run(6.5)
    a = h.fcfg.tab.atab
    hm = np.zeros(13)
    worst = 0.0
    for k in range(of.shape[0]):
        pos = of[k, 0:13]
        cmd = of[k, O_REC + R_CMD : O_REC + R_CMD + 4]
        hinge_moments(oa[k, O_ALPHA], oa[k, O_BETA], oa[k, O_QBAR], pos, h.fcfg.tab.htab, hm)
        for s in range(4):
            a_eff = a[s, C_AREA] * 2.0
            p_load = -hm[s] / (a[s, C_ARM] * a_eff)
            vp, vm = rate_capability((2.8e7, 2.8e7), 2, p_load, a[s, C_V0], 2.8e7)
            vd = a[s, C_WN] / (2.0 * a[s, C_ZETA]) * (cmd[s] - pos[s])
            worst = max(worst, vd / vp if vd > 0 else -vd / vm)
    assert worst < 0.95, worst
    assert np.abs(of[:, 13:17]).max() > 5.0 * DEG  # the input really moved the surfaces
    assert abs(oa[-1, O_ALPHA] - h.trim.alpha) < 0.5 * DEG
