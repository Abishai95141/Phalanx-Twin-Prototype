"""ADC computation kernel: quadruplex air-data lanes -> voted and computed air data (AD-51; A-W2.2-6/7).

Inputs are the **digitised** ADC lanes the DFCC also computes on (M13 in-loop lanes ``lane.AD.PS.A`` ...,
SI, one sample per DFCC frame), so the computed air data carries the same transducer physics (M12: position
error, pneumatic lag, vane dynamics, TAT recovery and heater error) and the same acquisition texture (M13) as
the recorded lanes. Per DFCC frame:

1. **Vote** each quad signal by mid-value select (mean of the middle two; the M05 scheme) -> AD.PS.V, AD.PT.V,
   AD.AOA_VANE_L/R.V, AD.AOSS_VANE.V; a lane further than the monitor threshold from its vote clears its bit
   of that ADC channel's AD.VALID word.
2. **Undercarriage** (PROXY placement, A-W2.2-7): the physical gear-down increments of the static-source error
   (``gear_dk_ps`` x qc) and of the local AoA (``gear_dalpha_vane``) scale with the gear position (a ramp from
   the handle over ``gear_transit``) and are added to the voted readings here because the M12 static-source
   and vane physics have no gear term; the ADC removes ``1 - gear_resid`` of them once the gear discrete reads
   down and locked. Net: a transient error while the gear travels and a residual when down.
3. **Air-data algorithm** (Rajalakshmi DSJ 56(1) content): static-source position-error correction with the
   M12 static-source table at the indicated Mach; Mach (isentropic / Rayleigh pitot, fixed iteration count),
   ICAO pressure altitude, HBARO at the altimeter setting, CAS (sea-level reference), TAT corrected for the
   de-icing heater error when the heater flag is on and for the probe recovery (M12 tables), SAT, TAS, qbar,
   AoA from the two corrected vanes, beta from the AoSS vane, HDOT as a first-order filtered derivative.

Between DFCC frames every output holds. Truth columns (restricted, CIR ``truth_value``) come from the truth
ports (env, af).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .common import NJ, interp_clamped

(
    P_GEAR_DK_PS,
    P_GEAR_DALPHA,
    P_GEAR_RESID,
    P_GEAR_TRANSIT,
    P_HDOT_TAU,
    P_QNH,
    P_THR_P,
    P_THR_V,
    P_TAT_MIN,
    P_P0,
    P_T0,
    P_LAPSE,
    P_HTROP,
    P_RAIR,
    P_GAMMA,
    P_G0,
    P_RHO0,
    P_KU_AOA,
    P_KU_AOSS,
    P_DT_FRAME,
) = range(20)
N_P = 20

# lane columns of the input block
L_PS, L_PT, L_AOAL, L_AOAR, L_AOSS, L_TAT = 0, 4, 8, 12, 16, 20
N_LANES = 21
LANE_CHANNELS = (
    *(f"AD.PS.{c}" for c in "ABCD"),
    *(f"AD.PT.{c}" for c in "ABCD"),
    *(f"AD.AOA_VANE_L.{c}" for c in "ABCD"),
    *(f"AD.AOA_VANE_R.{c}" for c in "ABCD"),
    *(f"AD.AOSS_VANE.{c}" for c in "ABCD"),
    "AD.TAT",
)
# outputs (SI)
OUT_CHANNELS = (
    "AD.PS.V",
    "AD.PT.V",
    "AD.AOA_VANE_L.V",
    "AD.AOA_VANE_R.V",
    "AD.AOSS_VANE.V",
    "AD.HP",
    "AD.HBARO",
    "AD.HDOT",
    "AD.CAS",
    "AD.TAS",
    "AD.MACH",
    "AD.QBAR",
    "AD.SAT",
    "AD.AOA",
    "AD.BETA",
)
N_OUT = len(OUT_CHANNELS)
VALID_CHANNELS = ("AD.VALID.A", "AD.VALID.B", "AD.VALID.C", "AD.VALID.D")
# AD.VALID bit positions (dictionary bitfield)
B_PS, B_PT, B_DPA, B_DPB, B_AOAL, B_AOAR, B_AOSS, B_TAT, B_HEATER, B_BIT = range(10)
# float state
F_OUT = 0
F_GEAR = N_OUT
F_HP_PREV = N_OUT + 1
F_SAT_PREV = N_OUT + 2
F_HPT_PREV = N_OUT + 3
F_HDOT_T = N_OUT + 4
N_F = N_OUT + 5
I_TICK, I_PRIMED, I_VALID = 0, 1, 2  # valid words at 2..5
N_I = 6


@njit(**NJ)
def mid_value(a, b, c, d):
    """Mid-value select of four lanes: mean of the middle two (sorting network)."""
    lo1, hi1 = (a, b) if a <= b else (b, a)
    lo2, hi2 = (c, d) if c <= d else (d, c)
    m1 = lo1 if lo1 >= lo2 else lo2  # larger of the two lows
    m2 = hi1 if hi1 <= hi2 else hi2  # smaller of the two highs
    return 0.5 * (m1 + m2)


@njit(**NJ)
def mach_from_qc(qc, ps, g):
    """Mach from impact pressure ratio: isentropic subsonic, Rayleigh pitot (fixed 40 iterations) above 1."""
    if ps < 1.0:
        ps = 1.0
    if qc < 0.0:
        qc = 0.0
    ratio = qc / ps
    m2 = 2.0 / (g - 1.0) * ((ratio + 1.0) ** ((g - 1.0) / g) - 1.0)
    mach = math.sqrt(m2)
    if mach > 1.0:
        e1 = g / (g - 1.0)
        e2 = 1.0 / (g - 1.0)
        k = 1.0 / math.sqrt((0.5 * (g + 1.0)) ** e1 * ((g + 1.0) / (2.0 * g)) ** e2)
        c = (g - 1.0) / (2.0 * g)
        for _ in range(40):
            mach = k * math.sqrt((ratio + 1.0) * (1.0 - c / (mach * mach)) ** e2)
    return mach


@njit(**NJ)
def pressure_altitude(ps, p):
    """ICAO two-layer pressure altitude [m] of a static pressure [Pa]."""
    t0 = p[P_T0]
    lapse = p[P_LAPSE]
    expo = p[P_RAIR] * lapse / p[P_G0]
    p11 = p[P_P0] * (1.0 - lapse * p[P_HTROP] / t0) ** (1.0 / expo)
    if ps < 1.0:
        ps = 1.0
    if ps >= p11:
        return t0 / lapse * (1.0 - (ps / p[P_P0]) ** expo)
    t11 = t0 - lapse * p[P_HTROP]
    return p[P_HTROP] + p[P_RAIR] * t11 / p[P_G0] * math.log(p11 / ps)


@njit(**NJ)
def pressure_altitude_array(ps, p):
    """``pressure_altitude`` of each element of a 1-D static-pressure array (the INS baro reference)."""
    out = np.empty(ps.shape[0])
    for k in range(ps.shape[0]):
        out[k] = pressure_altitude(ps[k], p)
    return out


@njit(**NJ)
def static_pressure_at(hp, p):
    """ICAO two-layer static pressure [Pa] at a pressure altitude [m]: the inverse of ``pressure_altitude``.

    What a "P0 altitude signal" stands for: the F404 ECU's ambient-pressure input is the aircraft's pressure
    altitude (NASA CR-179568 Fig. 3, ECU inputs; research_notes f404_in20_engine_model.md) [TRANSFER:
    F404-400], so the FADEC's P0 is the standard-atmosphere pressure at the ADC's pressure altitude (W2.2)."""
    t0 = p[P_T0]
    lapse = p[P_LAPSE]
    expo = p[P_RAIR] * lapse / p[P_G0]
    if hp <= p[P_HTROP]:
        return p[P_P0] * (1.0 - lapse * hp / t0) ** (1.0 / expo)
    p11 = p[P_P0] * (1.0 - lapse * p[P_HTROP] / t0) ** (1.0 / expo)
    t11 = t0 - lapse * p[P_HTROP]
    return p11 * math.exp(-(hp - p[P_HTROP]) * p[P_G0] / (p[P_RAIR] * t11))


@njit(**NJ)
def static_pressure_at_array(hp, p):
    """``static_pressure_at`` of each element of a 1-D pressure-altitude array."""
    out = np.empty(hp.shape[0])
    for k in range(hp.shape[0]):
        out[k] = static_pressure_at(hp[k], p)
    return out


@njit(**NJ)
def total_pressure(ps, mach, g):
    """Pitot total pressure: isentropic subsonic; Rayleigh pitot for M >= 1."""
    if mach < 1.0:
        return ps * (1.0 + 0.5 * (g - 1.0) * mach * mach) ** (g / (g - 1.0))
    m2 = mach * mach
    gp1 = g + 1.0
    a = (gp1 * gp1 * m2 / (4.0 * g * m2 - 2.0 * (g - 1.0))) ** (g / (g - 1.0))
    return ps * a * (1.0 - g + 2.0 * g * m2) / (g + 1.0)


@njit(**NJ)
def adc_kernel(
    f, i, p, lanes, has, heat, gear_cmd, truth, pe_m, pe_k, vb_m, vb_b, sb_m, sb_b, rc_m, rc_r, dh_z, dh_e, dt
):
    """Advance L frames. Pure: returns (f, i, out[L, 15], valid[L, 4], tru[L, 15]).

    lanes: (L, 21) digitised ADC lane values (SI; meaningful where ``has``); has: (L,) int, a DFCC frame in
    this step; heat: (L,) heater flag; gear_cmd: (L,) gear handle (1 down). truth: (L, 7) frame-end
    [p_s, t_s, mach, tas, alpha, beta, qbar]. Tables: static position error (pe_m, pe_k), AoA vane bias
    (vb_m, vb_b), AoSS vane bias (sb_m, sb_b), TAT recovery (rc_m, rc_r), TAT heater error (dh_z, dh_e).
    """
    f = f.copy()
    i = i.copy()
    L = lanes.shape[0]
    out = np.empty((L, N_OUT))
    tru = np.empty((L, N_OUT))
    valid = np.empty((L, 4), dtype=np.int64)
    g = p[P_GAMMA]
    a0 = math.sqrt(g * p[P_RAIR] * p[P_T0])
    a_hdot = 1.0 - math.exp(-p[P_DT_FRAME] / p[P_HDOT_TAU])
    hp_qnh = pressure_altitude(p[P_QNH], p)
    for j in range(L):
        # ---- undercarriage position (PROXY ramp from the handle, A-W2.2-7)
        tgt = 1.0 if gear_cmd[j] == 1 else 0.0
        step = dt / p[P_GEAR_TRANSIT]
        if f[F_GEAR] < tgt:
            f[F_GEAR] = f[F_GEAR] + step
            if f[F_GEAR] > tgt:
                f[F_GEAR] = tgt
        elif f[F_GEAR] > tgt:
            f[F_GEAR] = f[F_GEAR] - step
            if f[F_GEAR] < tgt:
                f[F_GEAR] = tgt
        gpos = f[F_GEAR]
        gdl = 1.0 if gpos >= 1.0 else 0.0  # down-and-locked discrete
        # ---- truth (restricted)
        tr = truth[j]
        hp_t = pressure_altitude(tr[0], p)
        if i[I_PRIMED] == 0:
            f[F_HPT_PREV] = hp_t
        f[F_HDOT_T] = (hp_t - f[F_HPT_PREV]) / dt
        f[F_HPT_PREV] = hp_t
        tru[j, 0] = tr[0]
        tru[j, 1] = total_pressure(tr[0], tr[2], g)
        tru[j, 2] = tr[4]
        tru[j, 3] = tr[4]
        tru[j, 4] = tr[5]
        tru[j, 5] = hp_t
        tru[j, 6] = hp_t - hp_qnh
        tru[j, 7] = f[F_HDOT_T]
        tru[j, 8] = a0 * mach_from_qc(tru[j, 1] - tr[0], p[P_P0], g)
        tru[j, 9] = tr[3]
        tru[j, 10] = tr[2]
        tru[j, 11] = tr[6]
        tru[j, 12] = tr[1]
        tru[j, 13] = tr[4]
        tru[j, 14] = tr[5]
        if has[j] == 1:
            ln = lanes[j]
            ps_v = mid_value(ln[L_PS], ln[L_PS + 1], ln[L_PS + 2], ln[L_PS + 3])
            pt_v = mid_value(ln[L_PT], ln[L_PT + 1], ln[L_PT + 2], ln[L_PT + 3])
            al_v = mid_value(ln[L_AOAL], ln[L_AOAL + 1], ln[L_AOAL + 2], ln[L_AOAL + 3])
            ar_v = mid_value(ln[L_AOAR], ln[L_AOAR + 1], ln[L_AOAR + 2], ln[L_AOAR + 3])
            as_v = mid_value(ln[L_AOSS], ln[L_AOSS + 1], ln[L_AOSS + 2], ln[L_AOSS + 3])
            tat = ln[L_TAT]
            # lane monitors -> AD.VALID words (DPA/DPB not simulated: reported valid, PROXY A-W2.2-10)
            for ch in range(4):
                w = (1 << B_DPA) | (1 << B_DPB) | (1 << B_HEATER) | (1 << B_BIT)
                d = ln[L_PS + ch] - ps_v
                if -p[P_THR_P] <= d <= p[P_THR_P]:
                    w |= 1 << B_PS
                d = ln[L_PT + ch] - pt_v
                if -p[P_THR_P] <= d <= p[P_THR_P]:
                    w |= 1 << B_PT
                d = ln[L_AOAL + ch] - al_v
                if -p[P_THR_V] <= d <= p[P_THR_V]:
                    w |= 1 << B_AOAL
                d = ln[L_AOAR + ch] - ar_v
                if -p[P_THR_V] <= d <= p[P_THR_V]:
                    w |= 1 << B_AOAR
                d = ln[L_AOSS + ch] - as_v
                if -p[P_THR_V] <= d <= p[P_THR_V]:
                    w |= 1 << B_AOSS
                if tat >= p[P_TAT_MIN]:
                    w |= 1 << B_TAT
                i[I_VALID + ch] = w
            # physical gear-down increments (PROXY placement): static source and local flow at the vanes
            qc_raw = pt_v - ps_v
            if qc_raw < 0.0:
                qc_raw = 0.0
            ps_v = ps_v + p[P_GEAR_DK_PS] * qc_raw * gpos
            al_v = al_v + p[P_GEAR_DALPHA] * gpos
            ar_v = ar_v + p[P_GEAR_DALPHA] * gpos
            # air-data algorithm: position-error correction at the indicated Mach, gear correction
            qc_i = pt_v - ps_v
            m_i = mach_from_qc(qc_i, ps_v, g)
            ps_c = ps_v - interp_clamped(m_i, pe_m, pe_k) * qc_i
            ps_c = ps_c - (1.0 - p[P_GEAR_RESID]) * p[P_GEAR_DK_PS] * qc_i * gdl
            qc = pt_v - ps_c
            mach = mach_from_qc(qc, ps_c, g)
            hp = pressure_altitude(ps_c, p)
            if i[I_PRIMED] == 0:
                f[F_HP_PREV] = hp
            raw = (hp - f[F_HP_PREV]) / p[P_DT_FRAME]
            f[F_OUT + 7] = f[F_OUT + 7] + (raw - f[F_OUT + 7]) * a_hdot
            f[F_HP_PREV] = hp
            cas = a0 * mach_from_qc(qc, p[P_P0], g)
            r = interp_clamped(mach, rc_m, rc_r)
            if i[I_PRIMED] == 0:
                f[F_SAT_PREV] = tat / (1.0 + 0.5 * (g - 1.0) * r * mach * mach)
            tat_c = tat
            if heat[j] == 1:
                rho = ps_c / (p[P_RAIR] * f[F_SAT_PREV])
                tat_c = tat - interp_clamped(mach * rho / p[P_RHO0], dh_z, dh_e)
            sat = tat_c / (1.0 + 0.5 * (g - 1.0) * r * mach * mach)
            f[F_SAT_PREV] = sat
            gcorr = (1.0 - p[P_GEAR_RESID]) * p[P_GEAR_DALPHA] * gdl
            vb = interp_clamped(m_i, vb_m, vb_b)
            al = (al_v - vb - gcorr) / (1.0 + p[P_KU_AOA])
            ar = (ar_v - vb - gcorr) / (1.0 + p[P_KU_AOA])
            beta = (as_v - interp_clamped(m_i, sb_m, sb_b)) / (1.0 + p[P_KU_AOSS])
            f[F_OUT + 0] = ps_v
            f[F_OUT + 1] = pt_v
            f[F_OUT + 2] = al_v
            f[F_OUT + 3] = ar_v
            f[F_OUT + 4] = as_v
            f[F_OUT + 5] = hp
            f[F_OUT + 6] = hp - hp_qnh
            f[F_OUT + 8] = cas
            f[F_OUT + 9] = mach * math.sqrt(g * p[P_RAIR] * sat)
            f[F_OUT + 10] = mach
            f[F_OUT + 11] = 0.5 * g * ps_c * mach * mach
            f[F_OUT + 12] = sat
            f[F_OUT + 13] = 0.5 * (al + ar)
            f[F_OUT + 14] = beta
            i[I_PRIMED] = 1
        for k in range(N_OUT):
            out[j, k] = f[F_OUT + k]
        for ch in range(4):
            valid[j, ch] = i[I_VALID + ch]
        i[I_TICK] += 1
    return f, i, out, valid, tru


def adc_reference(
    f, i, p, lanes, has, heat, gear_cmd, truth, pe_m, pe_k, vb_m, vb_b, sb_m, sb_b, rc_m, rc_r, dh_z, dh_e, dt
):
    """NumPy reference: the same source uncompiled."""
    return adc_kernel.py_func(
        f,
        i,
        p,
        lanes,
        has,
        heat,
        gear_cmd,
        truth,
        pe_m,
        pe_k,
        vb_m,
        vb_b,
        sb_m,
        sb_b,
        rc_m,
        rc_r,
        dh_z,
        dh_e,
        dt,
    )


def adc_initial_state() -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(N_F), np.zeros(N_I, dtype=np.int64)
