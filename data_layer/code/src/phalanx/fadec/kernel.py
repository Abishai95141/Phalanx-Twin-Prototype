"""M08 FADEC kernel (AD-22): signal validation + MIN/MAX control law + protection logic, one FADEC frame at a
time.

`_block` advances every engine of one M08 instance over L truth steps, running `nfr[j]` FADEC frames in step j
(frames whose instants fall in [t_{j-1}, t_j), see `coupling.py`). It is a pure function: fresh copies of the
state are returned, inputs are never mutated. The NumPy reference is the same source text executed with the
identity decorator (`reference.kernel_reference()`, what `NUMBA_DISABLE_JIT=1` would run, helpers included),
so
compiled and reference share one arithmetic path; a test asserts they agree bitwise.

Complex-step safety (AD-22, AD-34): every comparison and branch uses `.real`; no `abs`/`min`/`max` on values
that
carry derivatives; table look-ups choose their interval on the real part; output arrays take the state dtype.
The
same kernel therefore runs on complex128 state/parameters to differentiate through the loop gains.

Arithmetic primitives are + - * / and `np.sqrt` only (correctly rounded in both NumPy and Numba), so the
compiled
kernel and the reference are bitwise equal on this platform. Units: SI throughout (rad/s, K, Pa, kg/s, m^2,
rad);
speeds are also used as fractions of the dictionary 100 % speeds (`n1_ref`, `n2_ref`).

Structure [evidence in `configs/tejas/params/M08.yaml`; architecture §6 M08; report §3, §9]:
1. Signal validation per sensor (N1, N2, T1, T25, PS3, T5): range (n frames), rate (4 frames), cross-channel
   (average when agreeing, safer lane + soft-fail when not, other lane when one is lost), analytical
   comparison with
   an on-board model (25 % steady / 45 % transient, 0.5 s persistence, heal after 10 good frames), hold and
   substitution, injectable validator failure modes, accommodation.
2. Core fuel: N2 governor below IRP (N2c scheduled on PLA, corrected to T25), N1 isochronous governor vs T1
with
   the 104.4 % corrected cap, N2-max, T5, PS3-max limiters, accel Wf/PS3 in a MIN select; decel Wf/PS3 and
   PS3-min in
   a MAX select; integrator-feedback anti-windup (bumpless); ratio-unit law Wf = RU x PS3 (or direct Wf).
3. Nozzle: A8 floor scheduled on PLA, opened by a T5 loop (A8 holds T5 = f(T1, P0) at and above IRP); AB
pre-open.
4. VG schedules (FVG on N1c, CVG on N2c25), AB sequence (permission, pre-open, ignition, light-off fuel,
ratio-unit
   ramp, 2.5 s no-light, retries, lockout, blowout), start/run state, ignition, flameout detection and
   auto-relight,
   hung-start monitor, sub-idle, stall, over-temperature and overspeed monitors -> fault bits.
5. Proxy-mode autothrottle: an outer PI loop on measured N1 sets the corrected-N2 demand.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from .codes import (
    AB_LIGHTING,
    AB_LIT,
    AB_LOCKOUT,
    AB_OFF,
    AB_PREOPEN,
    AB_RETRY_WAIT,
    ACC_AB_INHIBIT,
    ACC_ACT_SAFE,
    ACC_N2_REDUCED,
    ACC_REVERSION,
    B_AB_BLOWOUT,
    B_AB_LOCKOUT,
    B_AB_NOLIGHT,
    B_FLAMEOUT,
    B_HUNG_START,
    B_N1_OVERSPEED,
    B_N2_OVERSPEED,
    B_OVERTEMP,
    B_REVERSION,
    B_STALL,
    B_SUBIDLE,
    IGN_AB,
    IGN_MAIN,
    L_ACCEL,
    L_DECEL,
    L_FUEL_OFF,
    L_GOV_N2,
    L_N1,
    L_N2MAX,
    L_PS3MAX,
    L_PS3MIN,
    L_START_NDOT,
    L_T5,
    L_WFMAX,
    L_WFMIN,
    NOZZLE_T5_BIT,
    NS,
    S_N1,
    S_N2,
    S_PS3,
    S_T1,
    S_T5,
    S_T25,
    ST_RUNNING,
    ST_SHUTDOWN,
    ST_STARTING,
    V_FAILED,
    V_OK,
    V_SUBSTITUTED,
    V_SUSPECT,
)
from .layout import (
    C_AB_BLOWOUT,
    C_AB_MAX_RETRIES,
    C_AB_NOLIGHT,
    C_AB_PREOPEN,
    C_AB_RETRY,
    C_ANALYTIC,
    C_ANTI_WINDUP,
    C_AT_FLOOR_LEVER,
    C_AUTOTHROTTLE,
    C_EDGE_HOLD,
    C_FO_CONFIRM,
    C_FO_DETECT,
    C_FUEL_LAW,
    C_HANDOFF,
    C_HEAL,
    C_HS_TIMEOUT,
    C_HS_WINDOW,
    C_LANE_HEAL,
    C_MAX_SUBST,
    C_N_AN,
    C_N_HOLD,
    C_N_RANGE,
    C_N_RATE,
    C_N_XC,
    C_NL0,
    C_OS_FRAMES,
    C_OT_FRAMES,
    C_SI_FRAMES,
    C_SKEW,
    C_STALL_HOLD,
    C_WRAP,
    F_A8_CMD,
    F_AB_RU,
    F_CVG_CMD,
    F_FLT_A8_GAIN,
    F_FLT_PLA_HOLD,
    F_FLT_PLA_VAL,
    F_FLT_RU_BIAS,
    F_FLT_WF_GAIN,
    F_FVG_CMD,
    F_HIST_B,
    F_HOLD,
    F_LANE_PREV,
    F_N1_LIM,
    F_N1_PREV,
    F_N1DOT,
    F_N2_PREV,
    F_N2C_AT,
    F_N2C_DEM,
    F_N2DOT,
    F_PLA_PREV,
    F_PS3_FILT,
    F_PS3_PREV,
    F_PS3DOT,
    F_SEL,
    F_T5_TGT,
    F_TRIM,
    F_U_SEL,
    F_WF_AB_CMD,
    F_WF_CMD,
    F_XI_A8,
    F_XI_GOV,
    F_XI_N1,
    F_XI_N2M,
    F_XI_P3N,
    F_XI_P3X,
    F_XI_T5F,
    F_XMOD,
    HO_N1,
    HO_N2MAX,
    HO_PS3MAX,
    HO_PS3MIN,
    HO_T5,
    I_AB_CNT,
    I_AB_ENABLE,
    I_AB_EVENT,
    I_AB_LOST,
    I_AB_RETRY,
    I_AB_STATE,
    I_ACC,
    I_AN_CNT,
    I_AN_FAIL,
    I_AN_GOOD,
    I_AT_PREV,
    I_CNT_GOOD,
    I_CNT_RATE,
    I_CNT_RNG,
    I_FAULTS,
    I_FO_CNT,
    I_FO_LATCH,
    I_FO_OK,
    I_FRAME,
    I_FUEL_CODE,
    I_HAS_LANE,
    I_HOLD_CNT,
    I_HS_CNT,
    I_HS_ON,
    I_IGN,
    I_INIT,
    I_LANE_FAIL,
    I_NOZ_CODE,
    I_OS1_CNT,
    I_OS2_CNT,
    I_OT_CNT,
    I_SI_CNT,
    I_SKEW_POS,
    I_STALL_CNT,
    I_START_CNT,
    I_START_STATE,
    I_SUB_MODE,
    I_VSTATE,
    I_XC_CNT,
    I_XC_FAIL,
    I_XC_GOOD,
    NOF,
    NOI,
    O_A8,
    O_AB_EN,
    O_CVG,
    O_FAULTS,
    O_FVG,
    O_IGN,
    O_LIMITER,
    O_SEL,
    O_VSTATE,
    O_WF,
    O_WF_AB,
    P_A8_KI,
    P_A8_KP,
    P_A8_MAX,
    P_A8_MIN,
    P_A8_PREOPEN,
    P_A8_SAFE,
    P_A8_SCALE,
    P_AB_PERM_N1,
    P_AB_RU_LIGHT,
    P_AB_RU_RATE,
    P_ACC_K,
    P_AN_TOL_STEADY,
    P_AN_TOL_TRANSIENT,
    P_AT_KI,
    P_AT_KP,
    P_AT_RATE,
    P_DEC_K,
    P_FO_DELTA_MIN,
    P_FO_DEM_MARGIN,
    P_FO_HYST,
    P_FO_N2DOT,
    P_FO_T5_MIN,
    P_GOV_EDZ,
    P_GOV_KFF,
    P_GOV_KI,
    P_GOV_KL,
    P_GOV_KP,
    P_HS_DEADBAND,
    P_HS_PLA_HI,
    P_HS_PLA_LO,
    P_IGN_HI,
    P_IGN_LO,
    P_K_IFB,
    P_N1_GS_K,
    P_N1_GS_MAX,
    P_N1_GS_PEXP,
    P_N1_GS_PMAX,
    P_N1_GS_T0,
    P_N1_KI,
    P_N1_KP,
    P_N1_LEAD,
    P_N1_OS,
    P_N1_REF,
    P_N1C_CAP,
    P_N1DOT_ALPHA,
    P_N2_MAX,
    P_N2_OS,
    P_N2_REDUCE,
    P_N2_REF,
    P_N2_RUN,
    P_N2_SUBIDLE,
    P_N2C_PART,
    P_N2DOT_ALPHA,
    P_N2M_KI,
    P_N2M_KP,
    P_ND_KI,
    P_ND_KP,
    P_ND_SCHED,
    P_P_STD,
    P_PLA_AB_MIN,
    P_PLA_CUTOFF,
    P_PLA_GI,
    P_PLA_IRP,
    P_PS3_ALPHA,
    P_PS3_LEAD,
    P_PS3_MAX,
    P_PS3_MIN,
    P_PS3DOT_ALPHA,
    P_PS3N_KI,
    P_PS3N_KP,
    P_PS3X_KI,
    P_PS3X_KP,
    P_STALL_DROP,
    P_T5_FUEL_MARGIN,
    P_T5_LIM_P0_K,
    P_T5_OT,
    P_T5_RESET,
    P_T5_START_LIM,
    P_T5F_KI,
    P_T5F_KP,
    P_T_STD,
    P_TRANS_N2DOT,
    P_TRANS_PLA_RATE,
    P_TRIM_ALPHA,
    P_VM_TOL_SCALE,
    P_WF_MAX,
    P_WF_MIN,
    P_XC_RATE_K,
    SKEW_MAX,
)
from .ports import AB_LIT_SLOT

_JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}
#: True only when `reference.py` executes this same source text with the identity decorator (NumPy reference)
_REFERENCE = bool(globals().get("_REFERENCE_MODE", False))


def _jit(fn):
    """`@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)`; identity in reference mode."""
    return fn if _REFERENCE else njit(**_JIT)(fn)


@_jit
def _at_floor(mode, dem_lever, dem_min):
    """Lower clamp of the autothrottle demand. Mode 0 (default, the Tejas/W1.3b law): the schedule's lowest
    demand. Mode 1 (proxy option ``at_floor_lever``, W2.4a-2): the demand of the lever M08 is fed, when
    higher - the proxy feeds the pre-mapped idle-stop lever while the A/T is engaged, so the floor is the
    flight idle at the flight condition (the MEASURED fuel-control law, ``phalanx.proxy.demand``)."""
    if mode == 1 and dem_lever.real > dem_min.real:
        return dem_lever
    return dem_min + 0.0 * dem_lever


@_jit
def _lk(x, y, v):
    """Piecewise-linear look-up with end clamping; interval chosen on ``v.real`` (complex-step safe)."""
    n = x.shape[0]
    vr = v.real
    if vr <= x[0]:
        return y[0] + 0.0 * v
    if vr >= x[n - 1]:
        return y[n - 1] + 0.0 * v
    i = 0
    while x[i + 1] < vr:
        i += 1
    return y[i] + (v - x[i]) / (x[i + 1] - x[i]) * (y[i + 1] - y[i])


@_jit
def _ifb(xi, kp, ki, kifb, su, e, u_reg, u_sel, dt, idle, side, track):
    """Limiter integrator with integrator feedback (C-MAPSS40k IFB): dxi/dt = Ki*su*e - k_ifb*(u_reg - u_sel).

    A limiter that is not in control and still on the safe side of its limit (side * e >= 0; side = +1 for the
    MIN group, -1 for the MAX group) is also clamped to its IFB equilibrium, u_reg <= u_sel + (Ki/k_ifb)*su*e
    (mirrored for side = -1), so a fast approach to the limit is not delayed by the IFB lag.

    ``track`` (W2.1 entry gate 4, the bumpless hand-off): a limiter that is past its limit (side * e < 0)
    while another regulator is in control (the second of two limits binding at once, e.g. PS3 crossing its
    maximum while the N1 limiter holds fuel) is clamped so that its output does not exceed the selected
    command, u_reg <= u_sel (x <= u_sel - Kp*su*e; mirrored for side = -1). Its own PI then takes control at
    the next frame from exactly the selected command: no step, and no 1/k_ifb lag while the variable rides
    past its limit (the W1.3b IFB followed the falling command with that lag and the second limiter never took
    over). The equilibrium clamp is not used past the limit: its headroom (Ki/k_ifb)*su*e is negative there
    and would take over with a step. k_ifb = 0 (no anti-windup) disables both clamps.
    """
    x = xi + dt * (ki * su * e - kifb * (u_reg - u_sel))
    if kifb.real > 0.0 and idle:
        if side * e.real >= 0.0:
            bound = u_sel + (ki / kifb - kp) * su * e
            if side * (x - bound).real > 0.0:
                x = bound + 0.0 * x
        elif track:
            bound = u_sel - kp * su * e
            if side * (x - bound).real > 0.0:
                x = bound + 0.0 * x
    return x


@_jit
def _wrap(v, lo, hi):
    """Failure mode 'scaling wrap-around': a reading beyond [lo, hi] re-enters the span modulo its width."""
    span = hi - lo
    if span <= 0.0:
        return v
    k = np.floor((v.real - lo) / span)
    return v - k * span


@_jit
def _lane_check(fe, ie, slot, v, lo, hi, rmax, dt, n_range, n_rate, heal, floor_ok):
    """Range and rate checks of one lane with persistence and healing. Returns (lane ok, frame rate).

    ``floor_ok``: a reading at the span floor is in range (both lanes of the sensor saturated there; see the
    edge hold in ``_frame``)."""
    r = (v - fe[F_LANE_PREV + slot]) / dt
    if (v.real <= lo and not floor_ok) or v.real >= hi:
        ie[I_CNT_RNG + slot] += 1
    else:
        ie[I_CNT_RNG + slot] = 0
    if abs(r.real) > rmax:
        ie[I_CNT_RATE + slot] += 1
    else:
        ie[I_CNT_RATE + slot] = 0
    if ie[I_CNT_RNG + slot] >= n_range or ie[I_CNT_RATE + slot] >= n_rate:
        ie[I_LANE_FAIL + slot] = 1
        ie[I_CNT_GOOD + slot] = 0
    elif ie[I_LANE_FAIL + slot] == 1:
        if ie[I_CNT_RNG + slot] == 0 and ie[I_CNT_RATE + slot] == 0:
            ie[I_CNT_GOOD + slot] += 1
        else:
            ie[I_CNT_GOOD + slot] = 0
        if ie[I_CNT_GOOD + slot] >= heal:
            ie[I_LANE_FAIL + slot] = 0
            ie[I_CNT_GOOD + slot] = 0
    fe[F_LANE_PREV + slot] = v
    return ie[I_LANE_FAIL + slot] == 0, r


@_jit
def _model_bases(fe, p, tb, p0):
    """On-board model base values (PROXY, A-W1.3b-7) from the previous frame's validated values, untrimmed."""
    t1 = fe[F_SEL + S_T1]
    t25 = fe[F_SEL + S_T25]
    sth1 = np.sqrt(t1 / p[P_T_STD])
    n1c = fe[F_SEL + S_N1] / (sth1 * p[P_N1_REF])
    n2c = fe[F_SEL + S_N2] / (sth1 * p[P_N2_REF])  # engine-inlet corrected N2/sqrt(theta1)
    b0 = _lk(tb.obm_n1_x, tb.obm_n1_y, n2c) * sth1 * p[P_N1_REF]
    b1 = _lk(tb.obm_n2_x, tb.obm_n2_y, n1c) * sth1 * p[P_N2_REF]
    r25 = _lk(tb.obm_t25_x, tb.obm_t25_y, n1c)
    b2 = t25 / r25
    b3 = t1 * r25
    b4 = p0 * _lk(tb.obm_pr3_x, tb.obm_pr3_y, n2c)
    b5 = t1 * _lk(tb.obm_t5_x, tb.obm_t5_y, n2c)
    return b0, b1, b2, b3, b4, b5


@_jit
def _bootstrap(fe, ie, p, tb, ln, pla, p0, cfg):
    """First frame: seed lane history, validated values, model trims and integrators (bumpless start)."""
    for s in range(NS):
        nl = cfg[C_NL0 + s]
        a = ln[2 * s]
        x = a
        if nl == 2:
            x = 0.5 * (a + ln[2 * s + 1])
        fe[F_SEL + s] = x
        fe[F_HOLD + s] = x
        for j in range(nl):
            fe[F_LANE_PREV + 2 * s + j] = ln[2 * s + j]
        for j in range(SKEW_MAX):
            fe[F_HIST_B + s * SKEW_MAX + j] = ln[2 * s + nl - 1]
    b = _model_bases(fe, p, tb, p0)
    for s in range(NS):
        bs = b[0]
        if s == 1:
            bs = b[1]
        elif s == 2:
            bs = b[2]
        elif s == 3:
            bs = b[3]
        elif s == 4:
            bs = b[4]
        elif s == 5:
            bs = b[5]
        if bs.real > 0.0:
            fe[F_TRIM + s] = fe[F_SEL + s] / bs
        else:
            fe[F_TRIM + s] = 1.0 + 0.0 * bs
    fe[F_N2_PREV] = fe[F_SEL + S_N2]
    fe[F_N1_PREV] = fe[F_SEL + S_N1]
    fe[F_N1DOT] = 0.0 * fe[F_N1DOT]
    fe[F_PS3_PREV] = fe[F_SEL + S_PS3]
    fe[F_PS3DOT] = 0.0 * fe[F_PS3DOT]
    fe[F_PS3_FILT] = fe[F_SEL + S_PS3]
    fe[F_PLA_PREV] = pla
    fe[F_N2DOT] = 0.0 * fe[F_N2DOT]
    mult = 1.0 + 0.0 * fe[F_SEL + S_PS3]
    if cfg[C_FUEL_LAW] == 1:
        mult = fe[F_SEL + S_PS3]
    u0 = fe[F_WF_CMD] / mult
    d0 = _lk(tb.n2c_pla_x, tb.n2c_pla_y, pla)
    rff0 = 0.0 * u0
    if cfg[C_FUEL_LAW] == 1:
        rff0 = p[P_GOV_KFF] * _lk(tb.ruff_x, tb.ruff_y, d0) + 0.0 * u0
    fe[F_U_SEL] = u0
    fe[F_XI_GOV] = u0 - rff0
    fe[F_XI_N1] = u0
    fe[F_XI_N2M] = u0
    fe[F_XI_T5F] = u0
    fe[F_XI_P3X] = u0
    fe[F_XI_P3N] = u0
    fe[F_XI_A8] = fe[F_A8_CMD]
    fe[F_N2C_DEM] = d0
    fe[F_N2C_AT] = d0
    ie[I_INIT] = 1


@_jit
def _frame(fe, ie, p, tb, ln, pla, p0, at_eng, at_cmd, dt, cfg):
    """One FADEC frame for one engine; updates ``fe`` (float state row) and ``ie`` (int row) in place."""
    if ie[I_INIT] == 0:
        _bootstrap(fe, ie, p, tb, ln, pla, p0, cfg)
    n1r = p[P_N1_REF]
    n2r = p[P_N2_REF]
    tol_scale = p[P_VM_TOL_SCALE]
    heal = cfg[C_HEAL]
    skew = cfg[C_SKEW]
    if skew > SKEW_MAX - 1:
        skew = SKEW_MAX - 1
    pos = ie[I_SKEW_POS]

    # ---------------------------------------------------------------- transient flag (previous-frame N2 rate)
    pla_rate = (pla - fe[F_PLA_PREV]) / dt
    transient = abs(fe[F_N2DOT].real) > p[P_TRANS_N2DOT].real or abs(pla_rate.real) > p[P_TRANS_PLA_RATE].real

    # ---------------------------------------------------------------- on-board model (previous validated
    # values)
    b = _model_bases(fe, p, tb, p0)

    # ---------------------------------------------------------------- signal validation
    ps3_was_meas = ie[I_VSTATE + S_PS3] <= V_SUSPECT  # previous frame's PS3 was a measurement
    nsub = 0
    # the on-board model is a running-engine model: no analytical comparison during starts (A-W1.3b-7)
    # ... nor while a compressor stall or a flameout/relight is declared (the engine is far off the steady
    # line; A-W1.3b-8)
    analytic_on = (
        cfg[C_ANALYTIC] == 1
        and ie[I_START_STATE] == ST_RUNNING
        and ie[I_STALL_CNT] == 0
        and ie[I_FO_LATCH] == 0
    )
    refused = False
    for s in range(NS):
        nl = cfg[C_NL0 + s]
        lo = tb.v_lo[s]
        hi = tb.v_hi[s]
        rmax = tb.v_rate[s]
        va = ln[2 * s]
        vb = ln[2 * s + nl - 1]
        if cfg[C_WRAP] == 1:
            va = _wrap(va, lo, hi)
            vb = _wrap(vb, lo, hi)
        # span-floor hold (W2.1 entry gate 3): an inlet colder than the span bottom (ENG.T1 -54 degC vs the
        # -56.5 degC stratosphere) pins BOTH lanes at the floor. That is saturation, not an open circuit (an
        # open reads the floor on one lane while the other reads on), so for the sensors in the edge_hold mask
        # the pinned pair stays valid and the law holds the floor value instead of substituting the on-board
        # model (whose T1 gave N1c 1.065)
        edge = 1.0e-6 * (hi - lo)
        floor_ok = (
            ((cfg[C_EDGE_HOLD] >> s) & 1) == 1
            and nl == 2
            and va.real <= lo + edge
            and vb.real <= lo + edge
            and va.real >= lo - edge
            and vb.real >= lo - edge
        )
        oka, ra = _lane_check(
            fe, ie, 2 * s, va, lo, hi, rmax, dt, cfg[C_N_RANGE], cfg[C_N_RATE], cfg[C_LANE_HEAL], floor_ok
        )
        okb = oka
        rb = ra
        if nl == 2:
            okb, rb = _lane_check(
                fe, ie, 2 * s + 1, vb, lo, hi, rmax, dt, cfg[C_N_RANGE], cfg[C_N_RATE], cfg[C_LANE_HEAL],
                floor_ok,
            )  # fmt: skip
        # lane-B history for the skew failure mode
        fe[F_HIST_B + s * SKEW_MAX + pos] = vb
        jb = pos - skew
        if jb < 0:
            jb += SKEW_MAX
        vb_cmp = fe[F_HIST_B + s * SKEW_MAX + jb]

        xb = b[0]
        if s == 1:
            xb = b[1]
        elif s == 2:
            xb = b[2]
        elif s == 3:
            xb = b[3]
        elif s == 4:
            xb = b[4]
        elif s == 5:
            xb = b[5]
        xm = xb * fe[F_TRIM + s]
        fe[F_XMOD + s] = xm

        have = True
        state = V_OK
        x = va
        if nl == 2 and oka and okb:
            d = abs((va - vb_cmp).real)
            rr = abs(ra.real)
            if abs(rb.real) > rr:
                rr = abs(rb.real)
            tol = tb.v_xc[s] * tol_scale + p[P_XC_RATE_K] * rr
            if d > tol.real:
                ie[I_XC_CNT + s] += 1
                ie[I_XC_GOOD + s] = 0
            else:
                ie[I_XC_CNT + s] = 0
                if ie[I_XC_FAIL + s] == 1:
                    ie[I_XC_GOOD + s] += 1
                    if ie[I_XC_GOOD + s] >= heal:
                        ie[I_XC_FAIL + s] = 0
                        ie[I_XC_GOOD + s] = 0
            if ie[I_XC_CNT + s] >= cfg[C_N_XC]:
                ie[I_XC_FAIL + s] = 1
            if ie[I_XC_FAIL + s] == 1:
                state = V_SUSPECT
                if tb.v_safe[s] * (va - vb).real >= 0.0:
                    x = va
                else:
                    x = vb
            else:
                x = 0.5 * (va + vb)
        elif nl == 2 and (oka or okb):
            state = V_SUSPECT
            ie[I_XC_CNT + s] = 0
            ie[I_XC_FAIL + s] = 0
            ie[I_XC_GOOD + s] = 0
            x = va if oka else vb
        elif nl == 1 and oka:
            x = va
        else:
            have = False
            ie[I_XC_CNT + s] = 0
            ie[I_XC_FAIL + s] = 0
            ie[I_XC_GOOD + s] = 0

        if have:
            ie[I_HOLD_CNT + s] = 0
            ie[I_HAS_LANE + s] = 1
            if analytic_on and xm.real > 0.0:
                rel = abs((x - xm).real) / xm.real
                tol_an = p[P_AN_TOL_STEADY]
                if transient:
                    tol_an = p[P_AN_TOL_TRANSIENT]
                if rel > (tol_an * tol_scale).real:
                    ie[I_AN_CNT + s] += 1
                    ie[I_AN_GOOD + s] = 0
                else:
                    ie[I_AN_CNT + s] = 0
                    if ie[I_AN_FAIL + s] == 1:
                        ie[I_AN_GOOD + s] += 1
                        if ie[I_AN_GOOD + s] >= heal:
                            ie[I_AN_FAIL + s] = 0
                            ie[I_AN_GOOD + s] = 0
                if ie[I_AN_CNT + s] >= cfg[C_N_AN]:
                    ie[I_AN_FAIL + s] = 1
            else:
                ie[I_AN_CNT + s] = 0
                ie[I_AN_FAIL + s] = 0
                ie[I_AN_GOOD + s] = 0
            if ie[I_AN_FAIL + s] == 1:
                if nsub < cfg[C_MAX_SUBST]:
                    x = xm
                    state = V_SUBSTITUTED
                    nsub += 1
                else:
                    x = fe[F_HOLD + s]
                    state = V_FAILED
                    refused = True
        else:
            ie[I_HAS_LANE + s] = 0
            ie[I_AN_CNT + s] = 0
            ie[I_AN_FAIL + s] = 0
            ie[I_AN_GOOD + s] = 0
            ie[I_HOLD_CNT + s] += 1
            if ie[I_HOLD_CNT + s] <= cfg[C_N_HOLD]:
                x = fe[F_HOLD + s]
                state = V_FAILED
            elif nsub < cfg[C_MAX_SUBST]:
                x = xm
                state = V_SUBSTITUTED
                nsub += 1
            else:
                x = fe[F_HOLD + s]
                state = V_FAILED
                refused = True

        if state == V_OK or state == V_SUSPECT:
            fe[F_HOLD + s] = x
        # adaptive trim of the on-board model (only on healthy, steady, agreeing data)
        if state == V_OK and (not transient) and ie[I_AN_CNT + s] == 0 and xb.real > 0.0:
            fe[F_TRIM + s] = fe[F_TRIM + s] + p[P_TRIM_ALPHA] * (x / xb - fe[F_TRIM + s])
        fe[F_SEL + s] = x
        ie[I_VSTATE + s] = state
    pos += 1
    if pos >= SKEW_MAX:
        pos = 0
    ie[I_SKEW_POS] = pos

    # ---------------------------------------------------------------- accommodation (plant-changing)
    acc = 0
    if ie[I_VSTATE + S_N1] >= V_FAILED or ie[I_VSTATE + S_N2] >= V_FAILED:
        acc |= ACC_N2_REDUCED | ACC_AB_INHIBIT
    if ie[I_VSTATE + S_T5] >= V_FAILED:
        acc |= ACC_AB_INHIBIT | ACC_ACT_SAFE
    if ie[I_VSTATE + S_PS3] >= V_FAILED:
        acc |= ACC_AB_INHIBIT
    if refused or (ie[I_HAS_LANE + S_N1] == 0 and ie[I_HAS_LANE + S_N2] == 0):
        acc |= ACC_REVERSION | ACC_AB_INHIBIT
    ie[I_ACC] = acc

    # ---------------------------------------------------------------- validated quantities
    N1 = fe[F_SEL + S_N1]
    N2 = fe[F_SEL + S_N2]
    T1 = fe[F_SEL + S_T1]
    T25 = fe[F_SEL + S_T25]
    PS3 = fe[F_SEL + S_PS3]
    T5 = fe[F_SEL + S_T5]
    sth1 = np.sqrt(T1 / p[P_T_STD])
    sth25 = np.sqrt(T25 / p[P_T_STD])
    n1 = N1 / n1r
    n2 = N2 / n2r
    n1c = n1 / sth1
    n2c = n2 / sth1  # N2/sqrt(theta1): RU schedules and on-board model
    n2c25 = n2 / sth25  # N2/sqrt(theta25): governed core speed (N2 trimmed by T2.5) and CVG
    raw = (N2 - fe[F_N2_PREV]) / (n2r * dt)
    n2dot = fe[F_N2DOT] + p[P_N2DOT_ALPHA] * (raw - fe[F_N2DOT])
    fe[F_N2DOT] = n2dot
    raw1 = (N1 - fe[F_N1_PREV]) / (n1r * dt)
    n1dot = fe[F_N1DOT] + p[P_N1DOT_ALPHA] * (raw1 - fe[F_N1DOT])
    fe[F_N1DOT] = n1dot
    # PS3 rate (Pa/s) for the rate anticipation of the PS3-max limiter (own filter, ps3dot_tau)
    raw3 = (PS3 - fe[F_PS3_PREV]) / dt
    ps3dot = fe[F_PS3DOT] + p[P_PS3DOT_ALPHA] * (raw3 - fe[F_PS3DOT])
    fe[F_PS3DOT] = ps3dot

    # ---------------------------------------------------------------- start / run state
    # run speed is judged on corrected N2 (N2/sqrt(theta1)), like sub-idle: a cold-day idle is a running
    # engine
    fuel_req = pla.real >= p[P_PLA_CUTOFF].real
    ss = ie[I_START_STATE]
    if not fuel_req:
        ss = ST_SHUTDOWN
    elif ss == ST_SHUTDOWN:
        ss = ST_RUNNING if n2c.real >= p[P_N2_RUN].real else ST_STARTING
    elif ss == ST_STARTING and n2c.real >= p[P_N2_RUN].real:
        ss = ST_RUNNING
    ie[I_START_STATE] = ss
    if ss == ST_STARTING:
        ie[I_START_CNT] += 1
    else:
        ie[I_START_CNT] = 0
    fuel_on = fuel_req and (ss == ST_RUNNING or n2.real >= p[P_IGN_LO].real)

    # ---------------------------------------------------------------- flameout detection and auto-relight
    t5ref = T1 * _lk(tb.fo_x, tb.fo_y, pla)
    # never below the bottom of the measurable T5 span (+ margin): a harness reading pinned at the span floor
    # is below the reference (A-W1.3b-8)
    if t5ref.real < p[P_FO_T5_MIN].real:
        t5ref = p[P_FO_T5_MIN] + 0.0 * t5ref
    # T5-based monitors use a measured T5 only (a held or model-substituted T5 cannot show a flameout or an
    # over-temperature; A-W1.3b-8)
    t5_meas = ie[I_VSTATE + S_T5] <= V_SUSPECT
    # the core must also be falling below the speed the governor asked for on the previous frame: a throttle
    # chop decelerates the core towards a lower demand, a flameout takes it through the demand (A-W1.3b-8)
    below_dem = n2c25.real < (fe[F_N2C_DEM] - p[P_FO_DEM_MARGIN]).real
    # altitude schedule of the deceleration threshold (W2.1 entry gate 1): a flamed-out core runs down at a
    # rate set by the compressor work it still does, which scales with the inlet pressure (delta), so the
    # threshold is fo_n2dot x delta0 (P0 / P_std, floored at fo_delta_min). With the SLS threshold at altitude
    # the -3 %/s rate and the 5 % demand gate never overlapped on M07 (idle flameouts at 20-40 kft went
    # undetected)
    dlt0 = p0 / p[P_P_STD]
    if dlt0.real < p[P_FO_DELTA_MIN].real:
        dlt0 = p[P_FO_DELTA_MIN] + 0.0 * dlt0
    fo_rate = p[P_FO_N2DOT] * dlt0
    if ss == ST_RUNNING and fuel_on:
        if ie[I_FO_LATCH] == 0:
            if t5_meas and below_dem and T5.real < t5ref.real and n2dot.real < fo_rate.real:
                ie[I_FO_CNT] += 1
            else:
                ie[I_FO_CNT] = 0
            if ie[I_FO_CNT] >= cfg[C_FO_DETECT]:
                ie[I_FO_LATCH] = 1
                ie[I_FO_CNT] = 0
                ie[I_FO_OK] = 0
        else:
            # relit, confirmed by either (a) T5 back above the reference (+ hysteresis) with the core back at
            # run speed or still accelerating (a lit core stagnating below run speed is a hung relight), or
            # (b) the core back at the governed speed and not falling (N2 recovery, W2.1 entry gate 1: at low
            # power, notably idle at altitude, the harness reads its span floor, below any reference, so a
            # T5-only confirmation never completes)
            n2_ok = n2c.real >= p[P_N2_RUN].real or n2dot.real > p[P_HS_DEADBAND].real
            t5_back = t5_meas and T5.real > (t5ref * (1.0 + p[P_FO_HYST])).real and n2_ok
            n2_back = (not below_dem) and n2c.real >= p[P_N2_RUN].real and n2dot.real > -p[P_HS_DEADBAND].real
            if t5_back or n2_back:
                ie[I_FO_OK] += 1
            else:
                ie[I_FO_OK] = 0
            if ie[I_FO_OK] >= cfg[C_FO_CONFIRM]:
                ie[I_FO_LATCH] = 0
                ie[I_FO_OK] = 0
    else:
        ie[I_FO_LATCH] = 0
        ie[I_FO_CNT] = 0
        ie[I_FO_OK] = 0

    # ---------------------------------------------------------------- hung-start monitor (NASA rule,
    # TM-101702)
    armed = fuel_on and (ss == ST_STARTING or ie[I_FO_LATCH] == 1) and n2c.real < p[P_N2_RUN].real
    if armed:
        if n2dot.real <= p[P_HS_DEADBAND].real:
            ie[I_HS_CNT] += 1
        else:
            ie[I_HS_CNT] = 0
        # NASA rule: N2 < 60 % not rising for 1 s with PLA between 14 and 24 deg, or < 60 % for 35 s starting
        pla_band = pla.real >= p[P_HS_PLA_LO].real and pla.real <= p[P_HS_PLA_HI].real
        if (pla_band and ie[I_HS_CNT] >= cfg[C_HS_WINDOW]) or (
            ss == ST_STARTING and ie[I_START_CNT] >= cfg[C_HS_TIMEOUT]
        ):
            ie[I_HS_ON] = 1
    else:
        ie[I_HS_CNT] = 0
        ie[I_HS_ON] = 0

    # ---------------------------------------------------------------- sub-idle, stall, over-temperature,
    # overspeed
    # sub-idle on corrected core speed (N2/sqrt(theta1)): a cold-day idle is not sub-idle (A-W1.3b-8)
    if ss == ST_RUNNING and fuel_on and pla.real >= p[P_PLA_GI].real and n2c.real < p[P_N2_SUBIDLE].real:
        ie[I_SI_CNT] += 1
    else:
        ie[I_SI_CNT] = 0
    ps3p = fe[F_PS3_PREV]
    # on measured PS3 only (this and the previous frame): a switch to/from a held or substituted PS3 is not a
    # stall
    ps3_meas = ps3_was_meas and ie[I_VSTATE + S_PS3] <= V_SUSPECT
    if (
        ss == ST_RUNNING
        and ps3_meas
        and ps3p.real > 0.0
        and ((ps3p - PS3) / ps3p).real > p[P_STALL_DROP].real
    ):
        ie[I_STALL_CNT] = cfg[C_STALL_HOLD]
    elif ie[I_STALL_CNT] > 0:
        ie[I_STALL_CNT] -= 1
    if t5_meas and T5.real > p[P_T5_OT].real:
        ie[I_OT_CNT] += 1
    else:
        ie[I_OT_CNT] = 0
    if n1.real > p[P_N1_OS].real:
        ie[I_OS1_CNT] += 1
    else:
        ie[I_OS1_CNT] = 0
    if n2.real > p[P_N2_OS].real:
        ie[I_OS2_CNT] += 1
    else:
        ie[I_OS2_CNT] = 0

    # ---------------------------------------------------------------- corrected-N2 demand (PLA schedule or
    # A/T)
    dem_pla = _lk(tb.n2c_pla_x, tb.n2c_pla_y, pla)
    nlast = tb.n2c_pla_y.shape[0] - 1
    if cfg[C_AUTOTHROTTLE] == 1 and at_eng == 1:
        e_at = at_cmd - n1
        if ie[I_AT_PREV] == 0:
            fe[F_N2C_AT] = fe[F_N2C_DEM] - p[P_AT_KP] * e_at
        dem = fe[F_N2C_AT] + p[P_AT_KP] * e_at
        dprev = fe[F_N2C_DEM]
        lim = p[P_AT_RATE] * dt
        if (dem - dprev).real > lim.real:
            dem = dprev + lim
        elif (dem - dprev).real < -lim.real:
            dem = dprev - lim
        lo = _at_floor(cfg[C_AT_FLOOR_LEVER], dem_pla, tb.n2c_pla_y[0])
        if dem.real > tb.n2c_pla_y[nlast]:
            dem = tb.n2c_pla_y[nlast] + 0.0 * dem
        elif dem.real < lo.real:
            dem = lo + 0.0 * dem
        # back-calculated integrator: the unlimited output equals the limited one next frame
        fe[F_N2C_AT] = dem - p[P_AT_KP] * e_at + p[P_AT_KI] * e_at * dt
        ie[I_AT_PREV] = 1
    else:
        dem = dem_pla
        fe[F_N2C_AT] = dem
        ie[I_AT_PREV] = 0
    if (acc & ACC_REVERSION) != 0 and dem.real > p[P_N2C_PART].real:
        dem = p[P_N2C_PART] + 0.0 * dem
    fe[F_N2C_DEM] = dem

    # ---------------------------------------------------------------- core fuel: MIN/MAX selection
    rr = _lk(tb.ru_x, tb.ru_y, n2c) * (1.0 + fe[F_FLT_RU_BIAS])  # (+ fuel_schedule_bias fault)
    law_ru = cfg[C_FUEL_LAW] == 1
    # ratio units -> fuel flow through a filtered PS3 (MFC bellows / FADEC input filter; limiters use raw PS3)
    ps3f = fe[F_PS3_FILT] + p[P_PS3_ALPHA] * (PS3 - fe[F_PS3_FILT])
    fe[F_PS3_FILT] = ps3f
    to_wf = ps3f
    if not law_ru:
        to_wf = 1.0 + 0.0 * PS3
    su = rr * (ps3f / to_wf)  # reference fuel scale in native units (RU for law 1, kg/s for law 0)
    # demand feed-forward in ratio units (part of the ratio-unit law; the direct-Wf law 0 is a pure PI
    # governor,
    # C-MAPSS40k style, so its small-signal fuel carries no PS3 path except through the accel/decel limits)
    rff = 0.0 * su
    if law_ru:
        rff = p[P_GOV_KFF] * _lk(tb.ruff_x, tb.ruff_y, dem) + 0.0 * su
    e_gov = (dem * sth25 * n2r - N2) / n2r
    n1lim = _lk(tb.n1lim_x, tb.n1lim_y, T1)
    cap = p[P_N1C_CAP] * sth1
    if cap.real < n1lim.real:
        n1lim = cap
    fe[F_N1_LIM] = n1lim
    e_n1 = n1lim - (n1 + p[P_N1_LEAD] * n1dot)  # rate anticipation of the fan lag
    # N1 regulator gain scheduled on inlet temperature (W2.1 entry gate 4): 1 up to n1_gs_t0, rising by
    # n1_gs_k per K above it, capped at n1_gs_max. The M07 N1 loop has its least gain margin on cold, dense
    # days and the most on hot days, where the N1 limit meets the T5/nozzle loop and needs the bandwidth
    g_n1 = 1.0 + 0.0 * T1
    if T1.real > p[P_N1_GS_T0].real:
        g_n1 = 1.0 + p[P_N1_GS_K] * (T1 - p[P_N1_GS_T0])
        if g_n1.real > p[P_N1_GS_MAX].real:
            g_n1 = p[P_N1_GS_MAX] + 0.0 * g_n1
    # ... and on ambient pressure (C-MAPSS schedules on P2): (P_std / P0)^n1_gs_pexp, capped at n1_gs_pmax;
    # the spools respond more slowly in thin air, where the loop has the most margin
    if p[P_N1_GS_PEXP].real > 0.0:
        d0 = p0 / p[P_P_STD]
        if d0.real < p[P_FO_DELTA_MIN].real:
            d0 = p[P_FO_DELTA_MIN] + 0.0 * d0
        g_p = d0 ** (-p[P_N1_GS_PEXP])
        if g_p.real > p[P_N1_GS_PMAX].real:
            g_p = p[P_N1_GS_PMAX] + 0.0 * g_p
        g_n1 = g_n1 * g_p
    kp_n1 = p[P_N1_KP] * g_n1
    ki_n1 = p[P_N1_KI] * g_n1
    n2max = p[P_N2_MAX] + 0.0 * n2
    if (acc & ACC_N2_REDUCED) != 0:
        n2max = n2max - p[P_N2_REDUCE] / n2r
    e_n2m = n2max - n2
    t5lim = _lk(tb.t5lim_x, tb.t5lim_y, T1) + p[P_T5_LIM_P0_K] * (p[P_P_STD] - p0)
    t5_fuel_tgt = t5lim + p[P_T5_FUEL_MARGIN]
    # sub-idle start/relight (DEEC-style airstart logic, A-W1.3b-18): entered when starting or relighting
    # below
    # run speed and kept until run speed is reached (the relight may be confirmed earlier). Fuel then holds a
    # scheduled N2 rate once light-off is seen (T5 above the flameout reference), trimmed by a start T5 limit;
    # before light-off the governor output is held. The above-idle Wf/PS3 accel schedule does not apply.
    sub = (
        fuel_on
        and n2c.real < p[P_N2_RUN].real
        and (ss == ST_STARTING or ie[I_FO_LATCH] == 1 or ie[I_SUB_MODE] == 1)
    )
    lit_sub = t5_meas and T5.real > (t5ref * (1.0 + p[P_FO_HYST])).real
    if sub and p[P_T5_START_LIM].real < t5_fuel_tgt.real:
        t5_fuel_tgt = p[P_T5_START_LIM] + 0.0 * t5_fuel_tgt
    e_t5 = (t5_fuel_tgt - T5) / t5lim
    # rate anticipation (W2.1 entry gate 4): an acceleration into the PS3 limit is cut ps3_lead seconds ahead
    # of the crossing (the spool keeps accelerating after a fuel cut; without it PS3 overshot by up to 5.8 %)
    e_p3x = (p[P_PS3_MAX] - (PS3 + p[P_PS3_LEAD] * ps3dot)) / p[P_PS3_MAX]
    # optional PS3 minimum (default off, A-W1.3b-5/AD-50): a floor on the governor branch only, below IRP, on
    # a
    # running engine and not during a declared stall; the MIN protection limiters still bound it
    p3n_on = (
        p[P_PS3_MIN].real > 0.0
        and ss == ST_RUNNING
        and ie[I_STALL_CNT] == 0
        and pla.real < p[P_PLA_IRP].real
        and not sub
    )
    e_p3n = -1.0 + 0.0 * PS3
    if p[P_PS3_MIN].real > 0.0:
        e_p3n = (p[P_PS3_MIN] - PS3) / p[P_PS3_MIN]

    # large-signal path: extra gain on the part of the error outside a dead zone (small signals see gov_kp
    # only)
    edz = p[P_GOV_EDZ]
    e_big = 0.0 * e_gov
    if e_gov.real > edz.real:
        e_big = e_gov - edz
    elif e_gov.real < -edz.real:
        e_big = e_gov + edz
    # small-signal PI gains scheduled on corrected core speed (W2.3a, A-W2.3-3): near ground idle the
    # installed engine's steady Wf/PS3 falls as N2 rises, so constant-ratio-unit fuelling is barely damped
    # there and the governor's proportional ratio-unit gain must exceed that slope (1 where the line rises:
    # AD-57's Kp)
    gk = _lk(tb.govk_x, tb.govk_y, n2c)
    kp_g = p[P_GOV_KP] * gk
    ki_g = p[P_GOV_KI] * gk
    u_gov = fe[F_XI_GOV] + rff + kp_g * su * e_gov + p[P_GOV_KL] * su * e_big
    gcode = L_GOV_N2
    e_nd = 0.0 * e_gov
    if sub:
        if ie[I_SUB_MODE] == 0:  # bumpless entry: hold the last selected output
            fe[F_XI_GOV] = fe[F_U_SEL] + 0.0 * fe[F_XI_GOV]
        e_nd = (p[P_ND_SCHED] - n2dot) / p[P_ND_SCHED]
        u_gov = fe[F_XI_GOV] + 0.0 * su
        if lit_sub:
            u_gov = u_gov + p[P_ND_KP] * su * e_nd
        gcode = L_START_NDOT
    elif ie[I_SUB_MODE] == 1:  # hand-over to the N2 governor: integrator re-initialised to the last output
        fe[F_XI_GOV] = fe[F_U_SEL] - rff  # (feed-forward + integrator continuous; the error terms then act)
        u_gov = fe[F_XI_GOV] + rff + kp_g * su * e_gov + p[P_GOV_KL] * su * e_big
    ie[I_SUB_MODE] = 1 if sub else 0
    u_acc = p[P_ACC_K] * su
    u_dec = p[P_DEC_K] * su
    # MIN/MAX selection (C-MAPSS40k structure, f404 notes Q4). Anti-windup (cfg anti_windup = 1):
    # - the governor is positional (feed-forward + PI + large-signal term) and integrates only while in
    #   control, so its feed-forward survives accel/decel-limited transients;
    # - every limiter is a positional PI with integrator feedback (C-MAPSS40k IFB):
    #       dxi_j/dt = Ki_j * su * e_j - k_ifb * (u_j - u_sel)
    #   a limiter not in control settles (Ki_j / k_ifb) * su * e_j above the selected output: far limiters
    #   keep large headroom (measurement steps cannot grab control); the one approaching its limit takes
    #   over as its error reaches zero; the selection of continuous candidates is continuous (bumpless).
    # anti_windup = 0 is the negative control: no integrator feedback, the governor always integrates.
    aw = cfg[C_ANTI_WINDUP] == 1
    u_n1 = fe[F_XI_N1] + kp_n1 * su * e_n1
    u_n2m = fe[F_XI_N2M] + p[P_N2M_KP] * su * e_n2m
    u_t5 = fe[F_XI_T5F] + p[P_T5F_KP] * su * e_t5
    u_p3x = fe[F_XI_P3X] + p[P_PS3X_KP] * su * e_p3x
    u_p3n = fe[F_XI_P3N] + p[P_PS3N_KP] * su * e_p3n
    u = u_gov
    code = gcode
    if p3n_on and u_p3n.real > u.real:  # governor branch only (AD-50)
        u = u_p3n
        code = L_PS3MIN
    if u_n1.real < u.real:
        u = u_n1
        code = L_N1
    if u_n2m.real < u.real:
        u = u_n2m
        code = L_N2MAX
    if u_t5.real < u.real:
        u = u_t5
        code = L_T5
    if u_p3x.real < u.real:
        u = u_p3x
        code = L_PS3MAX
    if not sub and u_acc.real < u.real:
        u = u_acc
        code = L_ACCEL
    if u_dec.real > u.real:
        u = u_dec
        code = L_DECEL
    wf = u * to_wf
    if wf.real < p[P_WF_MIN].real:
        wf = p[P_WF_MIN] + 0.0 * wf
        code = L_WFMIN
    if wf.real > p[P_WF_MAX].real:
        wf = p[P_WF_MAX] + 0.0 * wf
        code = L_WFMAX
    if not fuel_on:
        wf = 0.0 * wf
        code = L_FUEL_OFF
    u_sel = wf / to_wf
    kifb = p[P_K_IFB] if aw else 0.0
    ho = cfg[C_HANDOFF]
    if sub:
        if lit_sub and (code == L_START_NDOT or not aw):
            fe[F_XI_GOV] = fe[F_XI_GOV] + dt * p[P_ND_KI] * su * e_nd
    elif code == L_GOV_N2 or not aw:
        fe[F_XI_GOV] = fe[F_XI_GOV] + dt * ki_g * su * e_gov
    fe[F_XI_N1] = _ifb(
        fe[F_XI_N1], kp_n1, ki_n1, kifb, su, e_n1, u_n1, u_sel, dt, code != L_N1, 1.0,
        (ho & HO_N1) != 0,
    )  # fmt: skip
    fe[F_XI_N2M] = _ifb(
        fe[F_XI_N2M], p[P_N2M_KP], p[P_N2M_KI], kifb, su, e_n2m, u_n2m, u_sel, dt, code != L_N2MAX, 1.0,
        (ho & HO_N2MAX) != 0,
    )  # fmt: skip
    fe[F_XI_T5F] = _ifb(
        fe[F_XI_T5F], p[P_T5F_KP], p[P_T5F_KI], kifb, su, e_t5, u_t5, u_sel, dt, code != L_T5, 1.0,
        (ho & HO_T5) != 0,
    )  # fmt: skip
    fe[F_XI_P3X] = _ifb(
        fe[F_XI_P3X], p[P_PS3X_KP], p[P_PS3X_KI], kifb, su, e_p3x, u_p3x, u_sel, dt, code != L_PS3MAX, 1.0,
        (ho & HO_PS3MAX) != 0,
    )  # fmt: skip
    fe[F_XI_P3N] = _ifb(
        fe[F_XI_P3N], p[P_PS3N_KP], p[P_PS3N_KI], kifb, su, e_p3n, u_p3n, u_sel, dt, code != L_PS3MIN, -1.0,
        (ho & HO_PS3MIN) != 0,
    )  # fmt: skip
    fe[F_U_SEL] = u_sel
    fe[F_WF_CMD] = wf
    ie[I_FUEL_CODE] = code

    # ---------------------------------------------------------------- afterburner sequence
    ab = ie[I_AB_STATE]
    lit = ln[AB_LIT_SLOT].real >= 0.5
    req = ss == ST_RUNNING and ie[I_FO_LATCH] == 0 and (acc & ACC_AB_INHIBIT) == 0
    perm = n1.real >= (n1lim - p[P_AB_PERM_N1]).real
    ab_event = 0
    if pla.real < p[P_PLA_AB_MIN].real:
        ab = AB_OFF
        ie[I_AB_RETRY] = 0
        ie[I_AB_CNT] = 0
    elif ab == AB_LOCKOUT:
        pass
    elif not req:
        ab = AB_OFF
        ie[I_AB_CNT] = 0
    elif ab == AB_OFF:
        if perm:
            ab = AB_PREOPEN
            ie[I_AB_CNT] = 0
    elif ab == AB_RETRY_WAIT:
        ie[I_AB_CNT] += 1
        if ie[I_AB_CNT] >= cfg[C_AB_RETRY]:
            ab = AB_PREOPEN
            ie[I_AB_CNT] = 0
    if ab == AB_PREOPEN or ab == AB_LIGHTING:
        ie[I_AB_CNT] += 1
        if lit:
            ab = AB_LIT
            ie[I_AB_LOST] = 0
            fe[F_AB_RU] = p[P_AB_RU_LIGHT] + 0.0 * fe[F_AB_RU]
        elif ie[I_AB_CNT] >= cfg[C_AB_NOLIGHT]:
            ab_event = 1
            ie[I_AB_RETRY] += 1
            ie[I_AB_CNT] = 0
            ab = AB_LOCKOUT if ie[I_AB_RETRY] > cfg[C_AB_MAX_RETRIES] else AB_RETRY_WAIT
        elif ie[I_AB_CNT] >= cfg[C_AB_PREOPEN]:
            ab = AB_LIGHTING
    elif ab == AB_LIT:
        if lit:
            ie[I_AB_LOST] = 0
        else:
            ie[I_AB_LOST] += 1
        if ie[I_AB_LOST] >= cfg[C_AB_BLOWOUT]:
            ab_event = 2
            ie[I_AB_RETRY] += 1
            ie[I_AB_CNT] = 0
            ab = AB_LOCKOUT if ie[I_AB_RETRY] > cfg[C_AB_MAX_RETRIES] else AB_RETRY_WAIT
    if ab_event != 0:
        ie[I_AB_EVENT] = ab_event
    elif ab == AB_PREOPEN or ab == AB_OFF:
        ie[I_AB_EVENT] = 0
    ie[I_AB_STATE] = ab
    ab_en = 0
    if ab == AB_LIGHTING:
        fe[F_AB_RU] = p[P_AB_RU_LIGHT] + 0.0 * fe[F_AB_RU]
        ab_en = 1
    elif ab == AB_LIT:
        tgt = _lk(tb.ab_ru_x, tb.ab_ru_y, pla)
        step = p[P_AB_RU_RATE] * dt
        cur = fe[F_AB_RU]
        if (tgt - cur).real > step.real:
            cur = cur + step
        else:
            cur = tgt
        fe[F_AB_RU] = cur
        ab_en = 1
    else:
        fe[F_AB_RU] = 0.0 * fe[F_AB_RU]
    fe[F_WF_AB_CMD] = fe[F_AB_RU] * ps3f
    ie[I_AB_ENABLE] = ab_en

    # ---------------------------------------------------------------- nozzle (A8): floor on PLA, opened by
    # the T5 loop
    floor = _lk(tb.a8_pla_x, tb.a8_pla_y, pla) * p[P_A8_SCALE]
    if ab == AB_PREOPEN or ab == AB_LIGHTING:
        floor = floor * (1.0 + p[P_A8_PREOPEN])
    t5_tgt = t5lim
    if ab == AB_LIGHTING:
        t5_tgt = t5lim - p[P_T5_RESET]
    fe[F_T5_TGT] = t5_tgt
    e_a = (T5 - t5_tgt) / t5_tgt
    g_a = 1.0 + fe[F_FLT_A8_GAIN]  # nozzle_loop_gain_margin fault (1 when healthy)
    u_a = fe[F_XI_A8] + p[P_A8_KP] * g_a * floor * e_a
    a8 = floor
    noz = 0
    if u_a.real > floor.real:
        a8 = u_a
        noz = 1
    if (acc & ACC_ACT_SAFE) != 0:
        a8 = floor * (1.0 + p[P_A8_SAFE])
        noz = 0
    a8lo = p[P_A8_MIN] * p[P_A8_SCALE]
    a8hi = p[P_A8_MAX] * p[P_A8_SCALE]
    if a8.real < a8lo.real:
        a8 = a8lo + 0.0 * a8
    if a8.real > a8hi.real:
        a8 = a8hi + 0.0 * a8
    kifb_a = p[P_K_IFB] if cfg[C_ANTI_WINDUP] == 1 else 0.0
    fe[F_XI_A8] = fe[F_XI_A8] + dt * (p[P_A8_KI] * g_a * floor * e_a - kifb_a * (u_a - a8))
    fe[F_A8_CMD] = a8
    ie[I_NOZ_CODE] = noz

    # ---------------------------------------------------------------- variable geometry
    fe[F_FVG_CMD] = _lk(tb.fvg_x, tb.fvg_y, n1c)
    fe[F_CVG_CMD] = _lk(tb.cvg_x, tb.cvg_y, n2c25)

    # ---------------------------------------------------------------- ignition
    ign = 0
    if fuel_on and ss == ST_STARTING and n2.real >= p[P_IGN_LO].real and n2.real < p[P_IGN_HI].real:
        ign |= IGN_MAIN
    if ie[I_FO_LATCH] == 1:
        ign |= IGN_MAIN
    if ab == AB_PREOPEN or ab == AB_LIGHTING:
        ign |= IGN_AB
    ie[I_IGN] = ign

    # ---------------------------------------------------------------- fault bits
    mask = 0
    for s in range(NS):
        nl = cfg[C_NL0 + s]
        if ie[I_LANE_FAIL + 2 * s] == 1:
            mask |= 1 << s
        if nl == 2 and ie[I_LANE_FAIL + 2 * s + 1] == 1:
            mask |= 1 << (6 + s)
        if ie[I_XC_FAIL + s] == 1:
            mask |= 1 << (12 + s)
        if ie[I_AN_FAIL + s] == 1:
            mask |= 1 << (18 + s)
        if ie[I_HAS_LANE + s] == 0:
            mask |= 1 << (24 + s)
    if ie[I_FO_LATCH] == 1:
        mask |= 1 << B_FLAMEOUT
    if ie[I_HS_ON] == 1:
        mask |= 1 << B_HUNG_START
    if ie[I_STALL_CNT] > 0:
        mask |= 1 << B_STALL
    if ie[I_SI_CNT] >= cfg[C_SI_FRAMES]:
        mask |= 1 << B_SUBIDLE
    if ie[I_AB_EVENT] == 1:
        mask |= 1 << B_AB_NOLIGHT
    if ab == AB_LOCKOUT:
        mask |= 1 << B_AB_LOCKOUT
    if ie[I_AB_EVENT] == 2:
        mask |= 1 << B_AB_BLOWOUT
    if (acc & ACC_REVERSION) != 0:
        mask |= 1 << B_REVERSION
    if ie[I_OT_CNT] >= cfg[C_OT_FRAMES]:
        mask |= 1 << B_OVERTEMP
    if ie[I_OS1_CNT] >= cfg[C_OS_FRAMES]:
        mask |= 1 << B_N1_OVERSPEED
    if ie[I_OS2_CNT] >= cfg[C_OS_FRAMES]:
        mask |= 1 << B_N2_OVERSPEED
    ie[I_FAULTS] = mask

    # ---------------------------------------------------------------- memory
    fe[F_N2_PREV] = N2
    fe[F_N1_PREV] = N1
    fe[F_PS3_PREV] = PS3
    fe[F_PLA_PREV] = pla
    ie[I_FRAME] += 1


@_jit
def _block(f, i, p, tb, cfg, dt, pla, p0, at_eng, at_cmd, lanes, nfr):
    """Advance all engines over L truth steps (pure).

    f [E, NF], i [E, NI]: state. p [NP]: parameters. tb: Tables. cfg [NC]: int config. dt: nominal frame
    period [s].
    pla [L, E] rad; p0 [L] Pa; at_eng [L] int; at_cmd [L, E]; lanes [L, cap, E, 13] SI; nfr [L] frames per
    step.
    Returns (f', i', outf [L, E, NOF], outi [L, E, NOI]) with the held outputs at the end of each step.
    """
    f2 = f.copy()
    i2 = i.copy()
    n_steps = nfr.shape[0]
    n_eng = f.shape[0]
    outf = np.empty((n_steps, n_eng, NOF), dtype=f2.dtype)
    outi = np.empty((n_steps, n_eng, NOI), dtype=np.int64)
    for j in range(n_steps):
        for e in range(n_eng):
            fe = f2[e]
            ie = i2[e]
            pla_je = pla[j, e]
            if fe[F_FLT_PLA_HOLD].real > 0.5:  # throttle binding fault: the PLA input does not move
                pla_je = fe[F_FLT_PLA_VAL].real
            for s in range(nfr[j]):
                _frame(fe, ie, p, tb, lanes[j, s, e], pla_je, p0[j], at_eng[j], at_cmd[j, e], dt, cfg)
            # fuel-metering demand to the FMV (+ fuel_overmetering fault: the metering unit delivers more
            # than the law commands; the law's own command stays in the state)
            outf[j, e, O_WF] = fe[F_WF_CMD] * (1.0 + fe[F_FLT_WF_GAIN])
            outf[j, e, O_WF_AB] = fe[F_WF_AB_CMD]
            outf[j, e, O_A8] = fe[F_A8_CMD]
            outf[j, e, O_FVG] = fe[F_FVG_CMD]
            outf[j, e, O_CVG] = fe[F_CVG_CMD]
            for s in range(NS):
                outf[j, e, O_SEL + s] = fe[F_SEL + s]
            outi[j, e, O_IGN] = ie[I_IGN]
            outi[j, e, O_AB_EN] = ie[I_AB_ENABLE]
            limiter = ie[I_FUEL_CODE]
            if ie[I_NOZ_CODE] == 1:
                limiter += NOZZLE_T5_BIT
            outi[j, e, O_LIMITER] = limiter
            for s in range(NS):
                outi[j, e, O_VSTATE + s] = ie[I_VSTATE + s]
            outi[j, e, O_FAULTS] = ie[I_FAULTS]
    return f2, i2, outf, outi


#: the compiled kernel (W2.1 fused groups call this directly; see `coupling.py`)
fadec_block = _block

__all__ = ["fadec_block"]
