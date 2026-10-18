"""M05 kernel (AD-22): quadruplex DFCC replica on the DFCC acquisition clock (80 Hz) inside the 240 Hz truth
loop, plus the 13 hydraulic actuators.

``fcs_kernel(f, i, p, tab, u[L, N_U], fr[L], off[L], dt, tf, n_sub_act, crit_mask)`` advances ``L`` truth
ticks; ``step`` is ``step_block`` with ``L = 1`` and the NumPy reference is ``fcs_kernel.py_func``.

The frame schedule is computed outside the kernel from the shared DFCC clock domain
(``module.frame_schedule``, exact integer arithmetic, AD-42): ``fr[j]`` = 1 if a DFCC sample instant falls
in tick ``j`` (then the lane slots of ``u[j]`` hold that sample), ``off[j]`` = ticks from ``j`` to the first
truth frame at or after the sample instant + the computation delay (8 ms -> 2 ticks on the phase-0 clock:
8.33 ms; AD-36, §8). Per tick:

1. if ``fr[j]``: one DFCC frame (``_dfcc_frame``, frame period ``tf``) reads the lanes and discretes of this
   tick and computes the 13 surface commands; they become *pending* with apply tick ``tick + off[j]``.
2. if ``tick == apply_tick``: the pending commands become the applied commands.
3. the actuators integrate over the tick (``actuator_tick``) with the applied commands, the hydraulic
   pressures, the true hinge loads and the actuator health.

DFCC frame (``tejas_airframe_aero_fcs.md`` Q3; report §1 Flight control row):

- **Redundancy management:** channels with FAILED, DROPOUT or CCDL_FAIL status contribute no lanes; each
  voted signal (rate and acceleration sensors, air data, inceptors, surface positions; quad or dual) is voted
  by mid-value select over its installed usable lanes (mean of the middle two of 4, median of 3, mean of 2); a
  lane that disagrees with the vote by more than ``thr_abs + thr_rel |vote|`` for ``n`` consecutive frames is
  failed (latched); with two lanes left a persistent disagreement fails the signal (cannot isolate). A failed
  surface-position lane is reported as LVDT_SUM_FAIL of that lane in FCS.ACT.BIT (A-W1.2-24).
- **Air data:** Mach (subsonic and Rayleigh-pitot inversion), qbar and pressure altitude (ICAO) from the voted
  pressures; alpha from the two vanes (local-flow calibration, L/R mistrack monitor), beta from the AoSS vane.
  Loss of air data latches the fixed-gain reversion until a reset.
- **Mode logic:** WoW (main-gear discretes, with stuck-switch faults) with persistence -> GROUND law
  (integrators reset, direct stick); no airspeed interlock by default (a false WoW selects the ground law in
  flight: TRANSFER, F-35A AIB); pilot spin mode; fixed-gain reversion with undercarriage-dependent gains;
  scheduled law otherwise.
- **Scheduled law:** pitch q/Nz blend (PI on the blended error; q and Nz-at-the-ASA feedback) with gains
  interpolated on Mach and pressure altitude; the g and AoA limiters clip the command (V-based rate limit,
  AoA allowance with lead and a Mach-scheduled time constant); stability-axis roll-rate command (PI) with the
  published +/-18 deg, 45 deg/s differential limits; yaw: beta and washed-out stability-axis yaw-rate
  feedback, Mach-scheduled ARI, pedal; slats scheduled on alpha and Mach; open-loop airbrakes.
- **CBIT:** per-channel subsystem fault words (23 subsystems) detected after a persistence and latched; status
  word per the dictionary FCS.CH.STATUS bit field. PBIT/MBIT run as timed state machines on the ground.

PROXY items (registered, A-W1.2-29): no beta-dot or inertial-coupling feed-forward, no Kalman attitude
estimate, no structural notch filters, no autopilot/ALSR; PBIT/MBIT do not exercise the surfaces.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
from numba import njit

from phalanx.airframe.geodesy import NJ, sin_cos

from .actuators import actuator_tick
from .layout import (
    ACT_LVDT_SHIFT,
    BIT_FAIL,
    BIT_PASS,
    BIT_RUNNING,
    CCDL_FAIL,
    CH_DROPOUT,
    CH_FAILED,
    CH_RESET,
    F_ALPHA,
    F_BETA,
    F_CMD,
    F_DA,
    F_DE,
    F_DR,
    F_HP,
    F_MACH,
    F_PEND,
    F_PFP,
    F_PFR,
    F_POS,
    F_QBAR,
    F_VEL,
    F_VOTE,
    F_WO,
    F_ZP,
    F_ZR,
    FLAG_AOA_LIM,
    FLAG_G_LIM,
    FLAG_REVERSION,
    G_B,
    G_FF,
    G_I,
    G_IR,
    G_N,
    G_PR,
    G_Q,
    G_R,
    I_ACTBIT,
    I_ACTCNT,
    I_ADMIS,
    I_ADVALID,
    I_APPLY,
    I_CBCNT,
    I_CBIT,
    I_CHFLT,
    I_CHST,
    I_FLAGS,
    I_FRAMES,
    I_GROUND,
    I_JAM,
    I_LAW,
    I_LFAIL,
    I_MBIT,
    I_MBITT,
    I_MCNT,
    I_PBIT,
    I_PBITT,
    I_REVLATCH,
    I_RSTCNT,
    I_SERVO,
    I_SPIN,
    I_TICK,
    I_VANECNT,
    I_WOWCNT,
    I_WOWF,
    I_WOWV,
    LAW_FIXED,
    LAW_GROUND,
    LAW_SCHEDULED,
    LAW_SPIN,
    LRU_BIT_FAIL,
    LRU_CBIT_FAIL,
    LRU_IBIT_RUN,
    LRU_PBIT_FAIL,
    MIS_AOA_VANE,
    MIS_AOSS,
    MIS_PRESSURE,
    MON_ABS,
    MON_N,
    MON_REL,
    N_OUT,
    O_CHST,
    O_FLOW,
    O_LAW,
    O_POS,
    O_RATE,
    O_REC,
    P_ABOPEN,
    P_ALEAD,
    P_ALIMN,
    P_BC0,
    P_BK1,
    P_BM0,
    P_BM1,
    P_DAMAX,
    P_DARATE,
    P_DEMAX,
    P_DPMIN,
    P_DPR,
    P_DRMAX,
    P_DRRATE,
    P_G0,
    P_GAMMA,
    P_GNYF,
    P_HTROP,
    P_KGP,
    P_KGQ,
    P_KGR,
    P_KGY,
    P_KPED,
    P_LAPSE,
    P_NCBIT,
    P_NREF,
    P_NVANE,
    P_NWOW,
    P_NZMAXF,
    P_NZMIN,
    P_P0,
    P_PMAXF,
    P_QMAX,
    P_QREF,
    P_RAIR,
    P_SA0,
    P_SA1,
    P_SLIB,
    P_SLMB,
    P_SLOB,
    P_SM0,
    P_SM1,
    P_SREV,
    P_T0,
    P_TPFP,
    P_TPFR,
    P_TWO,
    P_VANEMIS,
    P_VC0,
    P_VK1,
    P_WOWIL,
    P_WOWQ,
    R_ACTBIT,
    R_ADMIS,
    R_ASA_NY,
    R_CHST,
    R_CMD,
    R_FLAGS,
    R_LAW,
    R_LRUBIT,
    R_POSV,
    R_RSA_P,
    R_RSA_R,
    R_STICK,
    R_VDE,
    R_VNZ,
    R_VQ,
    S_ALIM,
    S_ARI,
    S_NZMAX,
    S_PMAX,
    S_TALPHA,
    SIG_AL,
    SIG_AOSS,
    SIG_AR,
    SIG_NY,
    SIG_NZ,
    SIG_P,
    SIG_PED,
    SIG_PS,
    SIG_PT,
    SIG_Q,
    SIG_R,
    SIG_SP,
    SIG_SR,
    U_AB,
    U_ALPHA,
    U_BETA,
    U_DPAV,
    U_GEAR,
    U_HEALTH,
    U_LANES,
    U_QBAR,
    U_WOW,
)
from .ports import N_SIG, N_SURF, SIG_POS0


class FcsTables(NamedTuple):
    gbp_m: np.ndarray  # (nm,) Mach breakpoints of the gain schedule
    gbp_h: np.ndarray  # (nh,) pressure-altitude breakpoints, m
    gains: np.ndarray  # (nm, nh, N_G)
    fixed: np.ndarray  # (2, N_G): fixed-gain reversion sets [gear up, gear down]
    sbp: np.ndarray  # (ns,) Mach breakpoints of the limiter / ARI schedule
    sched: np.ndarray  # (ns, N_S)
    mon: np.ndarray  # (N_SIG, 3) monitor thresholds and persistence
    lmask: np.ndarray  # (N_SIG,) int64 installed-lane bit masks
    atab: np.ndarray  # (13, actuator columns)
    htab: np.ndarray  # (13, hinge columns)


@njit(**NJ)
def _bracket(bp, x):
    n = bp.shape[0]
    if x <= bp[0]:
        return 0, 0.0
    if x >= bp[n - 1]:
        return n - 2, 1.0
    k = 0
    while bp[k + 1] < x:
        k += 1
    return k, (x - bp[k]) / (bp[k + 1] - bp[k])


@njit(**NJ)
def _sched(tab, mach, col):
    k, w = _bracket(tab.sbp, mach)
    return tab.sched[k, col] + w * (tab.sched[k + 1, col] - tab.sched[k, col])


@njit(**NJ)
def _gains(tab, mach, hp, out):
    km, wm = _bracket(tab.gbp_m, mach)
    kh, wh = _bracket(tab.gbp_h, hp)
    g = tab.gains
    for c in range(out.shape[0]):
        a = g[km, kh, c] + wh * (g[km, kh + 1, c] - g[km, kh, c])
        b = g[km + 1, kh, c] + wh * (g[km + 1, kh + 1, c] - g[km + 1, kh, c])
        out[c] = a + wm * (b - a)


@njit(**NJ)
def _clip(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


@njit(**NJ)
def _vote(u, base, usable, buf):
    """Mid-value select over the usable lanes (bit mask). Returns (vote, n_usable)."""
    n = 0
    for c in range(4):
        if (usable >> c) & 1:
            v = u[base + c]
            k = n
            while k > 0 and buf[k - 1] > v:  # insertion sort
                buf[k] = buf[k - 1]
                k -= 1
            buf[k] = v
            n += 1
    if n == 4:
        return 0.5 * (buf[1] + buf[2]), 4
    if n == 3:
        return buf[1], 3
    if n == 2:
        return 0.5 * (buf[0] + buf[1]), 2
    if n == 1:
        return buf[0], 1
    return 0.0, 0


@njit(**NJ)
def _monitor(f, i, u, sig, avail, mon, lmask, buf):
    """Vote one signal and update its lane monitors. Returns the number of lanes used in the vote."""
    base = U_LANES + 4 * sig
    usable = avail & (~i[I_LFAIL + sig]) & lmask[sig]
    v, n = _vote(u, base, usable, buf)
    if n == 0:
        return 0  # signal lost: keep the previous voted value
    thr = mon[sig, MON_ABS] + mon[sig, MON_REL] * abs(v)
    npers = int(mon[sig, MON_N])
    if n >= 3:
        for c in range(4):
            if (usable >> c) & 1:
                ci = I_MCNT + 4 * sig + c
                if abs(u[base + c] - v) > thr:
                    i[ci] += 1
                    if i[ci] >= npers:
                        i[I_LFAIL + sig] |= 1 << c
                        i[ci] = 0
                else:
                    i[ci] = 0
    elif n == 2:
        a = -1
        b = -1
        for c in range(4):
            if (usable >> c) & 1:
                if a < 0:
                    a = c
                else:
                    b = c
        ci = I_MCNT + 4 * sig + a
        if abs(u[base + a] - u[base + b]) > thr:
            i[ci] += 1
            if i[ci] >= npers:  # two-lane disagreement cannot be isolated: the signal is lost
                i[I_LFAIL + sig] |= (1 << a) | (1 << b)
                i[ci] = 0
        else:
            i[ci] = 0
    else:
        for c in range(4):
            i[I_MCNT + 4 * sig + c] = 0
    f[F_VOTE + sig] = v
    return n


@njit(**NJ)
def _air_data(f, p):
    """Mach, qbar and pressure altitude from the voted static and total pressures (ICAO, Rayleigh pitot)."""
    ps = f[F_VOTE + SIG_PS]
    pt = f[F_VOTE + SIG_PT]
    if ps < 1.0:
        ps = 1.0
    qc = pt - ps
    if qc < 0.0:
        qc = 0.0
    ratio = qc / ps
    g = p[P_GAMMA]
    m2 = 2.0 / (g - 1.0) * ((ratio + 1.0) ** ((g - 1.0) / g) - 1.0)
    mach = math.sqrt(m2)
    if (
        mach > 1.0
    ):  # Rayleigh pitot formula, fixed-point iteration (fixed count: deterministic, < 1e-9 at M1.05)
        e1 = g / (g - 1.0)
        e2 = 1.0 / (g - 1.0)
        k = 1.0 / math.sqrt((0.5 * (g + 1.0)) ** e1 * ((g + 1.0) / (2.0 * g)) ** e2)
        c = (g - 1.0) / (2.0 * g)
        for _ in range(40):
            mach = k * math.sqrt((ratio + 1.0) * (1.0 - c / (mach * mach)) ** e2)
    qbar = 0.5 * g * ps * mach * mach
    t0 = p[P_T0]
    lapse = p[P_LAPSE]
    expo = p[P_RAIR] * lapse / p[P_G0]
    p11 = p[P_P0] * (1.0 - lapse * p[P_HTROP] / t0) ** (1.0 / expo)
    if ps >= p11:
        hp = t0 / lapse * (1.0 - (ps / p[P_P0]) ** expo)
    else:
        t11 = t0 - lapse * p[P_HTROP]
        hp = p[P_HTROP] + p[P_RAIR] * t11 / p[P_G0] * math.log(p11 / ps)
    f[F_MACH] = mach
    f[F_QBAR] = qbar
    f[F_HP] = hp


@njit(**NJ)
def _channels(i, p, crit_mask):
    """CBIT over the injected channel faults; returns the bit mask of channels whose lanes may be used."""
    avail = 0
    ncbit = int(p[P_NCBIT])
    for c in range(4):
        flt = i[I_CHFLT + c]
        st = i[I_CHST + c]
        if flt != 0:
            i[I_CBCNT + c] += 1
        else:
            i[I_CBCNT + c] = 0
        if (flt & crit_mask) != 0:
            st |= CH_DROPOUT  # the channel disengages at once; latched until a reset
        if i[I_CBCNT + c] >= ncbit:
            i[I_CBIT + c] |= flt
        if (i[I_CBIT + c] & crit_mask) != 0:
            st |= CH_FAILED
        if (i[I_CBIT + c] >> 9) & 1:  # SUB_CCDL
            st |= CCDL_FAIL
        if i[I_RSTCNT + c] > 0:
            i[I_RSTCNT + c] -= 1
            if i[I_RSTCNT + c] == 0:
                st &= ~CH_RESET
        i[I_CHST + c] = st
        if (st & (CH_FAILED | CH_DROPOUT | CCDL_FAIL)) == 0:
            avail |= 1 << c
    return avail


@njit(**NJ)
def _actuator_bit(i, p):
    ncbit = int(p[P_NCBIT])
    for s in range(N_SURF):
        flt = i[I_SERVO + s]
        if flt != 0:
            i[I_ACTCNT + s] += 1
            if i[I_ACTCNT + s] >= ncbit:
                i[I_ACTBIT + s] |= flt & 15  # SERVO_FAIL_A..D bits 0-3
        else:
            i[I_ACTCNT + s] = 0


@njit(**NJ)
def _bit_state_machines(i, p):
    any_fault = 0
    for c in range(4):
        any_fault |= i[I_CHFLT + c]
    for s in range(N_SURF):
        any_fault |= i[I_SERVO + s] | i[I_JAM + s]
    for st_i, tm_i in ((I_PBIT, I_PBITT), (I_MBIT, I_MBITT)):
        if i[st_i] == BIT_RUNNING:
            if i[I_GROUND] == 0:  # aborted when airborne
                i[st_i] = BIT_FAIL
                continue
            i[tm_i] -= 1
            if i[tm_i] <= 0:
                if any_fault != 0:
                    i[st_i] = BIT_FAIL
                    for c in range(4):
                        i[I_CBIT + c] |= i[I_CHFLT + c]  # BIT finds latent faults without persistence
                    for s in range(N_SURF):
                        i[I_ACTBIT + s] |= i[I_SERVO + s] & 15
                else:
                    i[st_i] = BIT_PASS


@njit(**NJ)
def _dfcc_frame(f, i, p, tab, u, tf, crit_mask, gbuf, buf, cmd):
    """One 80 Hz DFCC frame: redundancy management, air data, mode logic, control laws -> ``cmd`` (13)."""
    avail = _channels(i, p, crit_mask)
    _actuator_bit(i, p)
    n_sig = np.zeros(N_SIG, dtype=np.int64)
    for s in range(N_SIG):
        n_sig[s] = _monitor(f, i, u, s, avail, tab.mon, tab.lmask, buf)
    # ---- air data ------------------------------------------------------------------------------------
    mis = 0
    for c in range(4):
        if ((i[I_LFAIL + SIG_PS] | i[I_LFAIL + SIG_PT]) >> c) & 1:
            mis |= 1 << c
    if i[I_LFAIL + SIG_PS] != 0 or i[I_LFAIL + SIG_PT] != 0:
        mis |= MIS_PRESSURE
    press_ok = n_sig[SIG_PS] > 0 and n_sig[SIG_PT] > 0
    if press_ok:
        _air_data(f, p)
    al = (f[F_VOTE + SIG_AL] - p[P_VC0]) / p[P_VK1]
    ar = (f[F_VOTE + SIG_AR] - p[P_VC0]) / p[P_VK1]
    vane_ok = True
    if n_sig[SIG_AL] > 0 and n_sig[SIG_AR] > 0:
        if abs(al - ar) > p[P_VANEMIS]:
            i[I_VANECNT] += 1
        else:
            i[I_VANECNT] = 0
        if i[I_VANECNT] >= int(p[P_NVANE]):
            i[I_LFAIL + SIG_AL] = 15  # cannot tell which vane is wrong: both excluded (latched)
            i[I_LFAIL + SIG_AR] = 15
            n_sig[SIG_AL] = 0
            n_sig[SIG_AR] = 0
        f[F_ALPHA] = 0.5 * (al + ar)
    elif n_sig[SIG_AL] > 0:
        f[F_ALPHA] = al
    elif n_sig[SIG_AR] > 0:
        f[F_ALPHA] = ar
    if n_sig[SIG_AL] == 0 and n_sig[SIG_AR] == 0:
        vane_ok = False
    if i[I_LFAIL + SIG_AL] != 0 or i[I_LFAIL + SIG_AR] != 0:
        mis |= MIS_AOA_VANE
    if n_sig[SIG_AOSS] > 0:
        f[F_BETA] = (f[F_VOTE + SIG_AOSS] - p[P_BC0]) / p[P_BK1]
    if i[I_LFAIL + SIG_AOSS] != 0:
        mis |= MIS_AOSS
    i[I_ADMIS] = mis
    ad_ok = press_ok and vane_ok and n_sig[SIG_AOSS] > 0
    i[I_ADVALID] = 1 if ad_ok else 0
    if not ad_ok:
        i[I_REVLATCH] = 1
    # ---- mode logic --------------------------------------------------------------------------------
    bits = 0
    for leg in range(3):
        if u[U_WOW + leg] > 0.5:
            bits |= 1 << leg
    bits = (bits & ~i[I_WOWF]) | (i[I_WOWV] & i[I_WOWF])  # stuck switches
    if (bits & 6) != 0:
        if i[I_WOWCNT] < int(p[P_NWOW]):
            i[I_WOWCNT] += 1
    else:
        i[I_WOWCNT] = 0
    ground = i[I_WOWCNT] >= int(p[P_NWOW])
    if ground and p[P_WOWIL] > 0.5 and ad_ok and f[F_QBAR] > p[P_WOWQ]:
        ground = False  # optional airspeed interlock (off by default)
    i[I_GROUND] = 1 if ground else 0
    old_law = i[I_LAW]
    if i[I_SPIN] != 0 and not ground:
        law = LAW_SPIN
    elif ground:
        law = LAW_GROUND
    elif i[I_REVLATCH] != 0:
        law = LAW_FIXED
    else:
        law = LAW_SCHEDULED
    if law != old_law and (law == LAW_GROUND or law == LAW_SPIN or old_law == LAW_GROUND):
        f[F_ZP] = 0.0
        f[F_ZR] = 0.0
    i[I_LAW] = law
    flags = FLAG_REVERSION if i[I_REVLATCH] != 0 else 0
    # ---- signals ------------------------------------------------------------------------------------
    g0 = p[P_G0]
    q_m = f[F_VOTE + SIG_Q]
    p_m = f[F_VOTE + SIG_P]
    r_m = f[F_VOTE + SIG_R]
    dnz = f[F_VOTE + SIG_NZ] / g0 - 1.0
    ny = f[F_VOTE + SIG_NY] / g0
    sp_in = f[F_VOTE + SIG_SP]
    sr_in = f[F_VOTE + SIG_SR]
    ped = f[F_VOTE + SIG_PED]
    f[F_PFP] += (sp_in - f[F_PFP]) * tf / (p[P_TPFP] + tf)
    f[F_PFR] += (sr_in - f[F_PFR]) * tf / (p[P_TPFR] + tf)
    de_max = p[P_DEMAX]
    if law == LAW_GROUND or law == LAW_SPIN:
        k_e = p[P_KGP] if law == LAW_GROUND else 1.0
        k_r = p[P_KGR] if law == LAW_GROUND else 1.0
        k_y = p[P_KGY] if law == LAW_GROUND else 1.0
        de = -sp_in * de_max * k_e + (p[P_KGQ] * q_m if law == LAW_GROUND else 0.0)
        da = sr_in * p[P_DAMAX] * k_r
        dr = ped * p[P_DRMAX] * k_y
        sigma = 0.0
    else:
        sched = law == LAW_SCHEDULED
        mach = f[F_MACH] if sched else 0.0
        if sched:
            _gains(tab, f[F_MACH], f[F_HP], gbuf)
            nzmax = _sched(tab, mach, S_NZMAX)
            pmax = _sched(tab, mach, S_PMAX)
            ari = _sched(tab, mach, S_ARI)
            a_est = f[F_ALPHA]
            if mach <= p[P_BM0]:
                w = 0.0
            elif mach >= p[P_BM1]:
                w = 1.0
            else:
                w = (mach - p[P_BM0]) / (p[P_BM1] - p[P_BM0])
        else:
            k = 1 if u[U_GEAR] > 0.5 else 0
            for c in range(gbuf.shape[0]):
                gbuf[c] = tab.fixed[k, c]
            nzmax = p[P_NZMAXF]
            pmax = p[P_PMAXF]
            ari = 0.0
            a_est = 0.0
            w = 0.0
        # pitch: q / Nz blend, PI. The limiters clip the command (no extra feedback paths into the law).
        s = f[F_PFP]
        nzmin = p[P_NZMIN]
        dnz_c = s * (nzmax - 1.0) if s >= 0.0 else s * (1.0 - nzmin)
        q_c = s * p[P_QMAX]
        if sched:
            hp = f[F_HP]
            t_isa = p[P_T0] - p[P_LAPSE] * (hp if hp < p[P_HTROP] else p[P_HTROP])
            v_est = mach * math.sqrt(p[P_GAMMA] * p[P_RAIR] * t_isa)
            if v_est < 1.0:
                v_est = 1.0
            # g limit of the rate command: q within (nz_lim - 1) g / V (ISA-temperature TAS estimate)
            q_hi = (nzmax - 1.0) * g0 / v_est
            q_lo = (nzmin - 1.0) * g0 / v_est
            if q_c > q_hi or q_c < q_lo:
                q_c = _clip(q_c, q_lo, q_hi)
                flags |= FLAG_G_LIM
            # AoA limit: the pitch-rate allowance that brings the predicted AoA (alpha + lead q) to the
            # scheduled limit in t_alpha; in the Nz regime the same allowance as a normal-acceleration command
            alim = _sched(tab, mach, S_ALIM)
            t_al = _sched(tab, mach, S_TALPHA)
            q_al = (alim - a_est - p[P_ALEAD] * q_m) / t_al
            if q_c > q_al:
                q_c = q_al
                flags |= FLAG_AOA_LIM
            dn_al = v_est / g0 * q_al
            if dnz_c > dn_al:
                dnz_c = dn_al
                flags |= FLAG_AOA_LIM
            # the negative side (W2.1a-2, carefree both ways): the same one-sided allowance on the predicted
            # AoA below alpha_min, so full forward stick cannot push the aircraft out of its aero envelope
            q_aln = (p[P_ALIMN] - a_est - p[P_ALEAD] * q_m) / t_al
            if q_c < q_aln:
                q_c = q_aln
                flags |= FLAG_AOA_LIM
            dn_aln = v_est / g0 * q_aln
            if dnz_c < dn_aln:
                dnz_c = dn_aln
                flags |= FLAG_AOA_LIM
        else:  # fixed-gain reversion: no air data, so only the inertial g limit on the rate command
            if dnz > nzmax - 1.0 and q_c > 0.0:
                q_c = 0.0
                flags |= FLAG_G_LIM
        nref = p[P_NREF]
        qref = p[P_QREF]
        y_ce = w * dnz_c / nref + (1.0 - w) * q_c / qref
        y = w * dnz / nref + (1.0 - w) * q_m / qref
        e = y_ce - y
        de = gbuf[G_N] * dnz + gbuf[G_Q] * q_m + gbuf[G_I] * f[F_ZP] + gbuf[G_FF] * y_ce
        if not ((de > de_max and gbuf[G_I] * e > 0.0) or (de < -de_max and gbuf[G_I] * e < 0.0)):
            f[F_ZP] += tf * e
        # roll: stability-axis roll-rate command, PI
        sa, ca = sin_cos(a_est)
        p_s = p_m * ca + r_m * sa
        e_r = f[F_PFR] * pmax - p_s
        da = gbuf[G_PR] * e_r + gbuf[G_IR] * f[F_ZR]
        da_lim = p[P_DAMAX]
        if not ((da > da_lim and gbuf[G_IR] * e_r > 0.0) or (da < -da_lim and gbuf[G_IR] * e_r < 0.0)):
            f[F_ZR] += tf * e_r
        # yaw: beta (or lateral acceleration in reversion), washed-out stability-axis yaw rate, ARI, pedal
        r_s = r_m * ca - p_m * sa
        f[F_WO] += (r_s - f[F_WO]) * tf / (p[P_TWO] + tf)
        r_wo = r_s - f[F_WO]
        if sched:
            dr = gbuf[G_B] * f[F_BETA] + gbuf[G_R] * r_wo + ari * da + p[P_KPED] * ped * p[P_DRMAX]
        else:
            dr = p[P_GNYF] * ny + gbuf[G_R] * r_wo + p[P_KPED] * ped * p[P_DRMAX]
        # slats: alpha and Mach schedule; fixed position in reversion
        if sched:
            sg = _clip((a_est - p[P_SA0]) / (p[P_SA1] - p[P_SA0]), 0.0, 1.0)
            mf = _clip((mach - p[P_SM0]) / (p[P_SM1] - p[P_SM0]), 0.0, 1.0)
            sigma = sg * (1.0 - mf * mf * (3.0 - 2.0 * mf))
        else:
            sigma = p[P_SREV]
    # ---- command-path limits ----------------------------------------------------------------------------
    de = _clip(de, -de_max, de_max)
    room = de_max - abs(de)
    da_lim = p[P_DAMAX] if p[P_DAMAX] < room else room
    da = _clip(da, -da_lim, da_lim)
    step = p[P_DARATE] * tf
    da = _clip(da, f[F_DA] - step, f[F_DA] + step)
    dr = _clip(dr, -p[P_DRMAX], p[P_DRMAX])
    step = p[P_DRRATE] * tf
    dr = _clip(dr, f[F_DR] - step, f[F_DR] + step)
    f[F_DA] = da
    f[F_DR] = dr
    f[F_DE] = de
    i[I_FLAGS] = flags
    cmd[0] = de + da
    cmd[1] = de + da
    cmd[2] = de - da
    cmd[3] = de - da
    cmd[4] = dr
    cmd[5] = sigma * p[P_SLOB]
    cmd[6] = sigma * p[P_SLMB]
    cmd[7] = sigma * p[P_SLIB]
    cmd[8] = sigma * p[P_SLIB]
    cmd[9] = sigma * p[P_SLMB]
    cmd[10] = sigma * p[P_SLOB]
    ab = p[P_ABOPEN] if u[U_AB] > 0.5 else 0.0
    cmd[11] = ab
    cmd[12] = ab
    for s in range(N_SURF):  # never command past the mechanical stops
        cmd[s] = _clip(cmd[s], tab.atab[s, 0], tab.atab[s, 1])
    _bit_state_machines(i, p)
    i[I_FRAMES] += 1


@njit(**NJ)
def _recorded(f, i, orow):
    """The recorded computed channels (ports.REC_CHANNELS order) from the state, held between frames."""
    o = O_REC
    for s in range(N_SURF):
        orow[o + R_POSV + s] = f[F_VOTE + SIG_POS0 + s]
    orow[o + R_STICK] = f[F_VOTE + SIG_SP]
    orow[o + R_STICK + 1] = f[F_VOTE + SIG_SR]
    orow[o + R_STICK + 2] = f[F_VOTE + SIG_PED]
    orow[o + R_RSA_P] = f[F_VOTE + SIG_P]
    orow[o + R_RSA_R] = f[F_VOTE + SIG_R]
    orow[o + R_ASA_NY] = f[F_VOTE + SIG_NY]
    orow[o + R_VQ] = f[F_VOTE + SIG_Q]
    orow[o + R_VNZ] = f[F_VOTE + SIG_NZ]
    orow[o + R_VDE] = 0.25 * (
        f[F_VOTE + SIG_POS0] + f[F_VOTE + SIG_POS0 + 1] + f[F_VOTE + SIG_POS0 + 2] + f[F_VOTE + SIG_POS0 + 3]
    )
    for s in range(5):
        orow[o + R_CMD + s] = f[F_CMD + s]
    orow[o + R_LAW] = i[I_LAW]
    orow[o + R_FLAGS] = i[I_FLAGS]
    lru = 0
    cbit = 0
    for c in range(4):
        st = i[I_CHST + c]
        orow[o + R_CHST + c] = st
        if (st & (CH_FAILED | CH_DROPOUT)) != 0:
            lru |= LRU_BIT_FAIL
        cbit |= i[I_CBIT + c]
    for s in range(N_SURF):
        w = i[I_ACTBIT + s] | ((i[I_LFAIL + SIG_POS0 + s] & 15) << ACT_LVDT_SHIFT)
        orow[o + R_ACTBIT + s] = w
        cbit |= w
    for s in range(N_SIG):
        cbit |= i[I_LFAIL + s]
    orow[o + R_ADMIS] = i[I_ADMIS]
    if i[I_MBIT] == BIT_FAIL:
        lru |= LRU_BIT_FAIL
    if i[I_PBIT] == BIT_FAIL:
        lru |= LRU_PBIT_FAIL
    if cbit != 0:
        lru |= LRU_CBIT_FAIL
    if i[I_PBIT] == BIT_RUNNING or i[I_MBIT] == BIT_RUNNING:
        lru |= LRU_IBIT_RUN
    orow[o + R_LRUBIT] = lru


@njit(**NJ)
def fcs_kernel(f, i, p, tab, u, fr, off, dt, tf, n_sub_act, crit_mask):
    """Advance ``L = u.shape[0]`` truth ticks. Pure: returns new ``f``, ``i`` and ``out[L, N_OUT]``."""
    f = f.copy()
    i = i.copy()
    n = u.shape[0]
    out = np.empty((n, N_OUT), dtype=np.float64)
    gbuf = np.empty(8, dtype=np.float64)
    buf = np.empty(4, dtype=np.float64)
    cmd = np.empty(N_SURF, dtype=np.float64)
    jam = np.empty(N_SURF, dtype=np.int64)
    for j in range(n):
        uj = u[j]
        if fr[j] > 0:
            _dfcc_frame(f, i, p, tab, uj, tf, crit_mask, gbuf, buf, cmd)
            for s in range(N_SURF):
                f[F_PEND + s] = cmd[s]
            i[I_APPLY] = i[I_TICK] + off[j]
        if i[I_APPLY] == i[I_TICK]:
            for s in range(N_SURF):
                f[F_CMD + s] = f[F_PEND + s]
            i[I_APPLY] = -1
        for s in range(N_SURF):
            jam[s] = i[I_JAM + s]
        pos, vel, rate, flow = actuator_tick(
            f[F_POS : F_POS + N_SURF],
            f[F_VEL : F_VEL + N_SURF],
            f[F_CMD : F_CMD + N_SURF],
            uj[U_DPAV : U_DPAV + 2],
            uj[U_ALPHA],
            uj[U_BETA],
            uj[U_QBAR],
            uj[U_HEALTH : U_HEALTH + N_SURF],
            jam,
            tab.atab,
            tab.htab,
            p[P_DPR],
            p[P_DPMIN],
            dt,
            n_sub_act,
        )
        for s in range(N_SURF):
            f[F_POS + s] = pos[s]
            f[F_VEL + s] = vel[s]
            out[j, O_POS + s] = pos[s]
            out[j, O_RATE + s] = rate[s]
        out[j, O_FLOW] = flow[0]
        out[j, O_FLOW + 1] = flow[1]
        out[j, O_LAW] = i[I_LAW]
        for c in range(4):
            out[j, O_CHST + c] = i[I_CHST + c]
        _recorded(f, i, out[j])
        i[I_TICK] += 1
    return f, i, out


def kernel_reference(f, i, p, tab, u, fr, off, dt, tf, n_sub_act, crit_mask):
    """NumPy reference: the same source, uncompiled (identical to ``NUMBA_DISABLE_JIT=1``)."""
    return fcs_kernel.py_func(f, i, p, tab, u, fr, off, dt, tf, n_sub_act, crit_mask)


__all__ = ["FcsTables", "fcs_kernel", "kernel_reference"]
_ = (LAW_SCHEDULED, F_QBAR)
