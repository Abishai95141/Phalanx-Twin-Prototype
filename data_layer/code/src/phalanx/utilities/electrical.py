"""Average-value electrical network with source selection and MIL-STD-704F band classification (M09).

Evidence: note tejas_utility_systems.md KQ4 and Synthesis (b)-(d); MIL-STD-704F w/CHG-1 (Tables I and IV,
§§5.1, 5.3.2.3, 5.3.2.4) [TRANSFER]; HAL master box / TRU / battery display pages [DIRECT-part]; DRDO 5 kW
DC backup generator [DIRECT]; F-16 Holloman AIB (generators drop offline on spool-down) [TRANSFER].

Sources (state machine, per tick):
- **Main AC generator** on the AMAGB: online above ``gen_cutin`` N2 fraction, offline below ``gen_dropout``
  (hysteresis) or after a latched fault (M11 event). Constant-frequency 400 Hz [ASSUMPTION per note].
- **5 kW DC backup generator** (PMG-excited, autonomous): online above ``bk_cutin``/``bk_dropout``.
- **Battery** (45 Ah [DIRECT-part]): Thevenin model ``V = OCV(SOC) - V_p - R0(T, SOC) I`` with a 1-RC
  polarisation branch ``dV_p/dt = (R_p I - V_p) / tau_p``; resistances rise in the cold and as the cell
  empties (A-W1.4-21). Charged from the bus up to 50 A [DIRECT-part]. It also powers the JFS starter motor
  (back-EMF ``e_m = k_e n_jfs``).

Buses: AC main (115 V rms) and DC main are shed without the main generator; DC essential and DC emergency
move to the backup generator; on the battery alone the essential bus is shed and the battery carries the
emergency bus (and the JFS starter). Any change of the essential-bus source interrupts the essential and
emergency buses for ``xfer_ticks`` truth frames (<= 50 ms, 704F §5.1: voltage may sit between
zero and normal for up to 50 ms). Loads are constant-power and phase-dependent (ground/air, cold-weather
heaters), A-W1.4-22.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from ._num import JIT, clip, pos
from .layout import (
    F_BATT_Q,
    F_BATT_SOC,
    F_BATT_T,
    F_BATT_V,
    F_BATT_VP,
    I_BK_FAULT,
    I_BK_ON,
    I_ESS_SRC,
    I_GEN_FAULT,
    I_GEN_ON,
    I_XFER_LEFT,
    P_AC_V_DROOP,
    P_AC_V_NOM,
    P_AV_HEAT_FRAC,
    P_BATT_CAP_AH,
    P_BATT_HEAT_CAP,
    P_BATT_I_CHARGE,
    P_BATT_OCV_EMPTY,
    P_BATT_OCV_FULL,
    P_BATT_R0,
    P_BATT_R_SOC,
    P_BATT_R_TCOEF,
    P_BATT_RP,
    P_BATT_T_REF,
    P_BATT_TAU_P,
    P_BATT_UA,
    P_BK_CUTIN,
    P_BK_DROPOUT,
    P_BK_EFF,
    P_BK_R,
    P_BK_V_NL,
    P_GEN_CUTIN,
    P_GEN_DROPOUT,
    P_GEN_EFF,
    P_GEN_NOLOAD,
    P_JFS_RM,
    P_LOAD_AC_AIR,
    P_LOAD_AC_GROUND,
    P_LOAD_DCM_AIR,
    P_LOAD_DCM_GROUND,
    P_LOAD_EMERG,
    P_LOAD_ESS,
    P_LOAD_HEATER,
    P_LOAD_HEATER_RAMP,
    P_LOAD_HEATER_T,
    P_LOAD_PROBE_HEAT,
    P_LOAD_V_REF,
    P_TRU_EFF,
    P_TRU_R,
    P_TRU_V_NL,
)

SRC_NONE, SRC_TRU, SRC_BACKUP, SRC_BATT = 0, 1, 2, 3
# MIL-STD-704F classification codes (classify_dc28 / classify_ac400)
PQ_NORMAL, PQ_EMERGENCY, PQ_STARTING, PQ_TRANSFER, PQ_OUT = 0, 1, 2, 3, 4


@njit(**JIT)
def battery_ocv(p, soc):
    """Open-circuit voltage (V), linear in SOC between the empty and full values [ASSUMPTION A-W1.4-21]."""
    return p[P_BATT_OCV_EMPTY] + (p[P_BATT_OCV_FULL] - p[P_BATT_OCV_EMPTY]) * clip(soc, 0.0, 1.0)


@njit(**JIT)
def battery_r(p, base, t):
    """Battery resistance (Ohm) at temperature t: base * exp(k (T_ref - T)); higher when cold."""
    return base * np.exp(p[P_BATT_R_TCOEF] * (p[P_BATT_T_REF] - t))


@njit(**JIT)
def cp_source_voltage(v0, r, pw):
    """Terminal voltage of a Thevenin source (v0, r) feeding a constant-power load pw (upper root).

    Beyond the maximum-power point the load collapses the source to v0 / 2.
    """
    disc = v0 * v0 - 4.0 * r * pw
    if disc.real <= 0.0:
        return v0 / 2.0
    return (v0 + np.sqrt(disc)) / 2.0


@njit(**JIT)
def electrical_step(f, i, p, n2f, airborne, t_bay, motor_on, e_m, fade, n_xfer, dt):
    """One tick of the electrical network. Mutates f, i.

    Returns (v_ac, v_dcmain, v_ess, v_emerg, gen_shaft_W, bk_shaft_W, motor_current_A, avionics_heat_W,
    probe_heat) where probe_heat is the air-data/TAT probe heater discrete (1 = on).
    """
    zero = f[F_BATT_SOC] - f[F_BATT_SOC]
    gen_on = i[I_GEN_ON]
    if i[I_GEN_FAULT] == 1:
        gen_on = 0
    elif gen_on == 1 and n2f.real < p[P_GEN_DROPOUT].real:
        gen_on = 0
    elif gen_on == 0 and n2f.real >= p[P_GEN_CUTIN].real:
        gen_on = 1
    bk_on = i[I_BK_ON]
    if i[I_BK_FAULT] == 1:
        bk_on = 0
    elif bk_on == 1 and n2f.real < p[P_BK_DROPOUT].real:
        bk_on = 0
    elif bk_on == 0 and n2f.real >= p[P_BK_CUTIN].real:
        bk_on = 1
    src = SRC_TRU if gen_on == 1 else (SRC_BACKUP if bk_on == 1 else SRC_BATT)
    if src != i[I_ESS_SRC] and i[I_ESS_SRC] != SRC_NONE:
        i[I_XFER_LEFT] = n_xfer
    i[I_ESS_SRC] = src
    i[I_GEN_ON] = gen_on
    i[I_BK_ON] = bk_on
    interrupted = i[I_XFER_LEFT] > 0

    heater = p[P_LOAD_HEATER] * clip((p[P_LOAD_HEATER_T] - t_bay) / p[P_LOAD_HEATER_RAMP], 0.0, 1.0)
    # air-data / TAT probe heaters: on the AC bus, on whenever airborne, and on the ground when cold
    probe_heat = 1 if (gen_on == 1 and (airborne > 0.5 or t_bay.real < p[P_LOAD_HEATER_T].real)) else 0
    p_ac = (p[P_LOAD_AC_GROUND] + airborne * (p[P_LOAD_AC_AIR] - p[P_LOAD_AC_GROUND]) + heater) * gen_on
    p_ac = p_ac + p[P_LOAD_PROBE_HEAT] * probe_heat
    p_dcm = (p[P_LOAD_DCM_GROUND] + airborne * (p[P_LOAD_DCM_AIR] - p[P_LOAD_DCM_GROUND])) * gen_on
    ess_on = 0.0 if interrupted else 1.0
    p_ess = p[P_LOAD_ESS] * ess_on
    p_emg = p[P_LOAD_EMERG] * ess_on

    soc = f[F_BATT_SOC]
    tb = f[F_BATT_T]
    vp = f[F_BATT_VP]
    soc_f = 1.0 + p[P_BATT_R_SOC] * (1.0 - clip(soc, 0.0, 1.0))  # resistance rises as the cell empties
    r0 = battery_r(p, p[P_BATT_R0], tb) * soc_f
    rp = battery_r(p, p[P_BATT_RP], tb) * soc_f
    e1 = battery_ocv(p, soc) - vp
    rm = p[P_JFS_RM]
    i_max = p[P_BATT_I_CHARGE]

    v_ac = zero
    v_main = zero
    gen_shaft = zero
    bk_shaft = zero
    i_m = zero
    if src == SRC_TRU:
        v_dc = cp_source_voltage(p[P_TRU_V_NL], p[P_TRU_R], p_dcm + p_ess + p_emg)
        i_ch = zero if motor_on else clip((v_dc - e1) / r0, 0.0, i_max)
        v_dc = v_dc - p[P_TRU_R] * i_ch
        p_tru_out = p_dcm + p_ess + p_emg + v_dc * i_ch
        p_gen_el = p_ac + p_tru_out / p[P_TRU_EFF]
        gen_shaft = p_gen_el / p[P_GEN_EFF] + p[P_GEN_NOLOAD]
        v_ac = p[P_AC_V_NOM] - p[P_AC_V_DROOP] * p_gen_el
        v_main = v_dc
        v_bus = v_dc
        i_bus = -i_ch
    elif src == SRC_BACKUP:
        v_bk = cp_source_voltage(p[P_BK_V_NL], p[P_BK_R], p_ess + p_emg)
        i_ch = zero if motor_on else clip((v_bk - e1) / r0, 0.0, i_max)
        v_bk = v_bk - p[P_BK_R] * i_ch
        bk_shaft = (p_ess + p_emg + v_bk * i_ch) / p[P_BK_EFF]
        v_bus = v_bk
        i_bus = -i_ch
    else:
        v_bus = zero  # set below from the battery terminal
        i_bus = zero
    # (an unloaded, online backup machine's windage is neglected; it is inside the AMAGB loss term)
    # battery branch: on the battery alone the essential bus is shed and the emergency bus is a resistive load
    # (rated power at the 28 V reference: no constant-power collapse while the starter drags the battery
    # down);
    # the starter motor always draws on the battery.
    g_l = p_emg / (p[P_LOAD_V_REF] * p[P_LOAD_V_REF]) if src == SRC_BATT else zero
    if motor_on:
        vb = (e1 + r0 * e_m / rm) / (1.0 + r0 * g_l + r0 / rm)
        i_m = pos((vb - e_m) / rm)
        if i_m.real <= 0.0:  # back-EMF above terminal voltage: motor unloaded
            vb = e1 / (1.0 + r0 * g_l)
        i_b = i_m + g_l * vb
    elif src == SRC_BATT:
        vb = e1 / (1.0 + r0 * g_l)
        i_b = g_l * vb
    else:
        i_b = i_bus
        vb = e1 - r0 * i_b
    if src == SRC_BATT:
        v_bus = vb
    v_ess = zero if (interrupted or src == SRC_BATT) else v_bus
    v_emg = zero if interrupted else v_bus
    if i[I_XFER_LEFT] > 0:
        i[I_XFER_LEFT] = i[I_XFER_LEFT] - 1

    cap_c = p[P_BATT_CAP_AH] * (1.0 - fade)  # P_BATT_CAP_AH is in coulombs (A h converted to SI on load)
    f[F_BATT_SOC] = soc - dt * i_b / cap_c
    f[F_BATT_VP] = vp + dt * (rp * i_b - vp) / p[P_BATT_TAU_P]
    f[F_BATT_T] = tb + dt * (i_b * i_b * r0 + vp * i_b - p[P_BATT_UA] * (tb - t_bay)) / p[P_BATT_HEAT_CAP]
    f[F_BATT_Q] = f[F_BATT_Q] + dt * i_b
    f[F_BATT_V] = vb
    av_heat = p[P_AV_HEAT_FRAC] * (p_ac + p_dcm + (p_ess if src != SRC_BATT else zero) + p_emg)
    return v_ac, v_main, v_ess, v_emg, gen_shaft, bk_shaft, i_m, av_heat, probe_heat


def classify_dc28(
    v: float, bands: dict, *, emergency: bool = False, starting: bool = False, transfer: bool = False
) -> int:
    """MIL-STD-704F 28 V DC classification of a steady-state bus voltage.

    ``bands`` holds the 704F limits from the M09 ``power_quality`` parameter set (Table IV normal 22.0-29.0 V;
    §5.3.2.3 emergency 16-29 V; §5.3.2.4 electric starting 12-29 V). ``transfer=True`` marks a bus inside a
    source-transfer interruption (§5.1, at most 50 ms), which is a normal function.
    """
    if transfer:
        return PQ_TRANSFER
    if bands["dc_normal_lo"] <= v <= bands["dc_normal_hi"]:
        return PQ_NORMAL
    if starting and bands["dc_start_lo"] <= v <= bands["dc_normal_hi"]:
        return PQ_STARTING
    if emergency and bands["dc_emerg_lo"] <= v <= bands["dc_normal_hi"]:
        return PQ_EMERGENCY
    return PQ_OUT


def classify_ac400(v_rms: float, f_hz: float, bands: dict, *, transfer: bool = False) -> int:
    """MIL-STD-704F 400 Hz AC classification (Table I: 108.0-118.0 V rms, 393-407 Hz). Abnormal-band figures
    (704F figure 4/6) are not machine-readable in the evidence copy, so anything outside normal is PQ_OUT."""
    if transfer:
        return PQ_TRANSFER
    ok_v = bands["ac_normal_lo"] <= v_rms <= bands["ac_normal_hi"]
    ok_f = bands["ac_f_lo"] <= f_hz <= bands["ac_f_hi"]
    return PQ_NORMAL if (ok_v and ok_f) else PQ_OUT
