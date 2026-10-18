"""A1 (open loop): M08 control-law structure frame by frame - ratio-unit law, schedules, fuel shut-off.

Scripted, consistent lane vectors from fixture steady states (TEST FIXTURE `FrameDriver`); a few frames each.
Regime-by-regime limiter selection in closed loop is in `tests/integration/test_fadec_limiters.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from fadec_fixture import FrameDriver, fixture_params, lanes_from_state, steady_state
from phalanx.fadec import FadecConfig
from phalanx.fadec.codes import IGN_MAIN, L_FUEL_OFF, L_GOV_N2, ST_RUNNING, ST_SHUTDOWN, ST_STARTING
from phalanx.fadec.layout import F_N1_LIM, F_PS3_FILT, I_START_STATE, P_LAYOUT

pytestmark = pytest.mark.unit
N1R = 13270 * 2 * np.pi / 60
N2R = 16810 * 2 * np.pi / 60


def _drv(pla=60.0, law=1, **over):
    params = fixture_params()
    if over:
        params = params.replace(**over)
    cfg = FadecConfig.build(params).with_cfg(fuel_law=law)
    x = steady_state(pla)[0]
    base = lanes_from_state(x, quantise=False)
    return FrameDriver(cfg, wf0=float(x[2]), a8_0=float(x[5])), base, x


def test_steady_mid_power_is_governed_by_the_n2_schedule():
    drv, base, x = _drv(60.0)
    for _ in range(30):
        drv.frame(base)
    assert drv.limiter == L_GOV_N2
    assert drv.wf == pytest.approx(float(x[2]), rel=2e-3)  # bootstrapped at the plant's own fuel flow


def test_ratio_unit_law_scales_fuel_with_ps3_and_direct_law_does_not():
    out = {}
    for law in (1, 0):
        drv, base, _ = _drv(60.0, law=law)
        for _ in range(30):
            drv.frame(base)
        wf0 = drv.wf
        stepped = base.copy()
        stepped[8:10] *= 1.10  # +10 % PS3 on both lanes, nothing else changes
        drv.frame(stepped)
        alpha = drv.cfg.p[P_LAYOUT.index["ps3_alpha"]]
        out[law] = (drv.wf / wf0 - 1.0, alpha, drv.fi(F_PS3_FILT) / base[8])
    rel, alpha, filt = out[1]
    assert filt == pytest.approx(1.0 + 0.10 * alpha, rel=1e-12)
    assert rel == pytest.approx(0.10 * alpha, rel=0.05)  # Wf = RU x filtered PS3
    assert abs(out[0][0]) < 0.1 * rel  # direct-Wf law: no PS3 path in the governed fuel


def test_fuel_shut_off_below_the_cutoff_and_start_state_machine():
    drv, base, _ = _drv(60.0)
    drv.frame(base, pla_deg=5.0)
    assert drv.wf == 0.0 and drv.limiter == L_FUEL_OFF and drv.ii(I_START_STATE) == ST_SHUTDOWN
    low = base.copy()
    low[2:4] = 0.30 * N2R  # 30 % N2: a start in progress
    drv.frame(low, pla_deg=18.0)
    assert drv.ii(I_START_STATE) == ST_STARTING and drv.wf > 0.0
    assert drv.outi[0, 0, 0] & IGN_MAIN  # ignition permissive 10-45 % N2
    low[2:4] = 0.50 * N2R
    drv.frame(low, pla_deg=18.0)
    assert not drv.outi[0, 0, 0] & IGN_MAIN  # above 45 %: igniters off
    low[2:4] = 0.65 * N2R
    drv.frame(low, pla_deg=18.0)
    assert drv.ii(I_START_STATE) == ST_RUNNING
    below = base.copy()
    below[2:4] = 0.05 * N2R
    drv2, _, _ = _drv(60.0)
    drv2.frame(below, pla_deg=18.0)
    assert drv2.wf == 0.0  # below the 10 % ignition permissive no fuel while starting


def test_n1_limit_is_the_lower_of_the_physical_limit_and_the_104p4_corrected_cap():
    for t1, expect in ((288.15, 1.02), (230.0, 1.044 * np.sqrt(230.0 / 288.15)), (330.0, 1.02)):
        drv, base, _ = _drv(87.0)
        b = base.copy()
        b[4:6] = t1
        drv.frame(b, pla_deg=87.0)
        assert drv.fi(F_N1_LIM) == pytest.approx(expect, rel=1e-12)


def test_nozzle_floor_follows_pla_below_irp_and_vg_follow_their_schedules():
    drv, base, _ = _drv(40.0)
    for _ in range(5):
        drv.frame(base, pla_deg=40.0)
    tb, p = drv.cfg.tables, drv.cfg.p
    floor = np.interp(np.deg2rad(40.0), tb.a8_pla_x, tb.a8_pla_y) * p[P_LAYOUT.index["a8_scale"]]
    assert drv.outf[0, 0, 2] == pytest.approx(floor, rel=1e-12)
    t1, t25 = drv.sel(2), drv.sel(3)
    n1c = drv.sel(0) / (np.sqrt(t1 / 288.15) * N1R)
    n2c25 = drv.sel(1) / (np.sqrt(t25 / 288.15) * N2R)
    assert drv.outf[0, 0, 3] == pytest.approx(np.interp(n1c, tb.fvg_x, tb.fvg_y), rel=1e-12)
    assert drv.outf[0, 0, 4] == pytest.approx(np.interp(n2c25, tb.cvg_x, tb.cvg_y), rel=1e-12)


def test_large_demand_steps_reach_the_accel_and_decel_schedules():
    drv, base, _ = _drv(60.0)
    for _ in range(10):
        drv.frame(base, pla_deg=60.0)
    seen = set()
    for _ in range(30):
        drv.frame(base, pla_deg=87.0)
        seen.add(drv.limiter & 15)
    assert 6 in seen  # ACCEL
    drv, base, _ = _drv(60.0)
    for _ in range(10):
        drv.frame(base, pla_deg=60.0)
    seen = set()
    for _ in range(30):
        drv.frame(base, pla_deg=18.0)
        seen.add(drv.limiter & 15)
    assert 7 in seen  # DECEL


def test_ifb_equilibrium_clamp_semantics():
    """The limiter integrator-feedback update with its equilibrium clamp (`kernel._ifb`, review mutant M25):
    an idle limiter on the safe side of its limit is clamped to its IFB equilibrium
    u_sel + (Ki/k_ifb - Kp) su e; in control, on the unsafe side, or without IFB it is the plain IFB
    integrator update."""
    from phalanx.fadec.kernel import _ifb

    kp, ki, kifb, su, dt, u_sel = 3.0, 3.0, 1.0, 2.0e-7, 1.0 / 60.0, 1.0e-6
    e = 0.1
    xi = 5.0e-6  # far above its equilibrium headroom
    u_reg = xi + kp * su * e
    plain = xi + dt * (ki * su * e - kifb * (u_reg - u_sel))
    bound = u_sel + (ki / kifb - kp) * su * e
    assert (
        _ifb(xi, kp, ki, kifb, su, e, u_reg, u_sel, dt, True, 1.0, False) == bound
    )  # idle, safe side: clamped
    assert (
        _ifb(xi, kp, ki, kifb, su, e, u_reg, u_sel, dt, False, 1.0, False) == plain
    )  # in control: not clamped
    assert _ifb(xi, kp, ki, kifb, su, -e, xi - kp * su * e, u_sel, dt, True, 1.0, False) == (
        xi + dt * (ki * su * -e - kifb * (xi - kp * su * e - u_sel))
    )  # unsafe side (past the limit): not clamped
    assert _ifb(xi, kp, ki, 0.0, su, e, u_reg, u_sel, dt, True, 1.0, False) == xi + dt * ki * su * e  # no IFB
    # MAX-group limiter (side -1) mirrors it: clamped from below when idle on its safe side
    lo = 1.0e-7
    x_max = _ifb(lo, kp, ki, kifb, su, -e, lo + kp * su * -e, u_sel, dt, True, -1.0, False)
    assert x_max == u_sel + (ki / kifb - kp) * su * -e
    # W2.1b hand-off (`track`): an idle limiter past its limit is clamped so its output does not exceed the
    # selected command (x <= u_sel - Kp su e), so it takes control bumplessly at the next frame
    xt = _ifb(xi, kp, ki, kifb, su, -e, xi - kp * su * e, u_sel, dt, True, 1.0, True)
    assert xt == u_sel - kp * su * -e
    assert xt + kp * su * -e == u_sel  # its output equals the selected command
    # not when it is in control, and not without IFB
    assert _ifb(xi, kp, ki, kifb, su, -e, xi - kp * su * e, u_sel, dt, False, 1.0, True) != xt
    assert (
        _ifb(xi, kp, ki, 0.0, su, -e, xi - kp * su * e, u_sel, dt, True, 1.0, True) == xi + dt * ki * su * -e
    )
