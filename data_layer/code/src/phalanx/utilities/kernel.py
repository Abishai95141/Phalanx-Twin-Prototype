"""The fused M09 truth kernel (AD-22): one ``@njit`` block function over flat state, parameters, inputs.

Per 240 Hz tick, in this order (couplings inside a tick use values already computed this tick, otherwise the
start-of-tick state; no algebraic loop is solved iteratively):

1. AMAGB/PTO speeds from N2 (fixed ratio; report §3 edge "N2 -> AMAGB, pump and generator speeds");
2. electrical network (source selection, transfer interruption, battery incl. the JFS starter motor);
3. JFS start sequencer (motor current from step 2; delivers power into the engine through the PTO);
4. both hydraulic systems (``nsub`` sub-steps; fuel-cooled HX uses the tank-fuel temperature and Wf);
5. fuel: slosh, burn/interconnect/transfer, tank-fuel temperature; then mass properties;
6. ECS (bleed extraction from ``eng.bleed_*``, avionics heat from step 2);
7. brakes, tyres; 8. fire zone; 9. AMAGB loss/oil temperature and the per-engine PTO power sum.

``kernel_reference`` is the same source uncompiled (``py_func``): the outer loop runs as Python and calls the
compiled leaf kernels. The fully uncompiled reference is the same module run with ``NUMBA_DISABLE_JIT=1``
(``tests/integration/test_utilities_kernel.py`` checks both bitwise against the compiled kernel).
"""

from __future__ import annotations

import numpy as np
from numba import njit

from ._num import JIT, clip, pos
from .ecs import ecs_step
from .electrical import electrical_step
from .fire import fire_step
from .fuel import fuel_step, mass_properties, slosh_step
from .hydraulics import hyd_system
from .jfs import JFS_COAST, OUT_OK, jfs_step, motor_emf, motor_on
from .landing import landing_step
from .layout import (
    B_AC,
    B_DCM,
    B_EMG,
    B_ESS,
    C_BRK_SYS,
    C_GEN_ENG,
    C_JFS_ENG,
    C_NE,
    C_NSUB,
    C_PUMP_ENG0,
    C_PUMP_ENG1,
    C_XFER_TICKS,
    F_BATT_SOC,
    F_BRK_DW,
    F_BRK_T,
    F_ECS_PCAB,
    F_ECS_TAV,
    F_ECS_TCAB,
    F_FUEL_M,
    F_FUEL_T,
    F_GB_T,
    F_HYD_P,
    F_HYD_T,
    F_HYD_VRES,
    F_LAST_TAS,
    F_TYRE_DW,
    H_AMAGB,
    H_BATT_FADE,
    H_BRAKE_WEAR,
    H_CAB_LEAK,
    H_COMP_DRIFT,
    H_EXT_LEAK,
    H_FILTER,
    H_HX_FOUL,
    H_JFS_DRAG,
    H_JFS_PWR,
    H_PRECHARGE,
    H_PUMP_LEAK,
    H_SYS_LEAK,
    H_TYRE_WEAR,
    H_XFER_LOSS,
    I_BK_FAULT,
    I_CHUTE,
    I_GEN_ON,
    I_JFS_MODE,
    I_JFS_OUTCOME,
    I_TICK,
    N_HYD,
    N_TANKS,
    N_WHEEL,
    NO_FIXED,
    NOE,
    NOI,
    NU_FIXED,
    O_AMAGB_W,
    O_BATT_AH,
    O_BATT_SOC,
    O_BRK_P,
    O_BRK_T,
    O_BRK_W,
    O_BUS_V,
    O_CAB_ALT,
    O_CG,
    O_ECS_P,
    O_ECS_T,
    O_FUEL_M,
    O_HYD_DP,
    O_HYD_LVL,
    O_HYD_P,
    O_HYD_T,
    O_INERTIA,
    O_MASS,
    O_TYRE_W,
    OE_BLEED,
    OE_FUEL_IN,
    OE_PTO,
    OI_BATT_LOW,
    OI_BK_BITE,
    OI_CHUTE,
    OI_GEN_ON,
    OI_GEN_OUT,
    OI_JFS,
    OI_PROBE_HEAT,
    P_BATT_CAP_AH,
    P_BATT_LOW_WARN_AH,
    P_FUEL_CP,
    P_G0,
    P_GAMMA_AIR,
    P_GB_HEAT_CAP,
    P_GB_LOSS_RATED,
    P_GB_UA,
    P_HYD_P_RET,
    P_HYD_RES_V,
    P_ISA_LAPSE,
    P_ISA_P0,
    P_ISA_T0,
    P_N2_100PCT,
    P_PTO_RATED_SPEED,
    P_PTO_RATIO,
    P_R_AIR,
    U_FSPEC,
    U_HEALTH,
    U_HYD_DEM,
    U_MACH,
    U_P_S,
    U_PBRK,
    U_RHO,
    U_T_S,
    U_TAS,
    U_W_HYD,
    U_WHEEL,
    U_WOW,
    UE_N2,
    UE_P3,
    UE_T3,
    UE_WBP,
    UE_WF,
    UE_WFAB,
)

JFS_STATE_COAST_FAIL = 5  # util.jfs_state code: spooling down after a failed or aborted start


@njit(**JIT)
def utilities_kernel(f, i, p, u, cfg, u_ign, dt):
    """Advance L = u.shape[0] ticks. Pure: returns fresh (f, i, out[L, NO], outi[L, NOI]).

    f: float64 (or complex128) state; i: int64 state; p: flat parameters (same dtype family as f);
    u: float64 inputs [L, NU_FIXED + 6 * n_engines]; cfg: int64 configuration; u_ign: the keyed uniform
    draw of the current JFS start attempt; dt: truth step (s).
    """
    f = f.copy()
    i = i.copy()
    n = u.shape[0]
    ne = cfg[C_NE]
    nsub = cfg[C_NSUB]
    nxfer = cfg[C_XFER_TICKS]
    out = np.empty((n, NO_FIXED + NOE * ne), dtype=f.dtype)
    outi = np.empty((n, NOI), dtype=np.int64)
    mp = np.empty(13, dtype=f.dtype)
    wpto = np.empty(ne, dtype=f.dtype)
    pto = np.empty(ne, dtype=f.dtype)
    bleed = np.empty(ne, dtype=f.dtype)
    n2 = np.empty(ne, dtype=np.float64)
    p3 = np.empty(ne, dtype=np.float64)
    t3 = np.empty(ne, dtype=np.float64)
    wbp = np.empty(ne, dtype=np.float64)
    pbrk = np.empty(N_WHEEL, dtype=np.float64)
    wheel = np.empty(N_WHEEL, dtype=np.float64)
    wear0 = np.empty(N_WHEEL, dtype=np.float64)
    tyre0 = np.empty(N_WHEEL, dtype=np.float64)
    brk_p = np.empty(N_WHEEL, dtype=f.dtype)
    w_rated = p[P_PTO_RATED_SPEED]
    brk_sys = cfg[C_BRK_SYS]
    # cabin altitude (ISA troposphere inverse) exponent R L / g0
    alt_exp = p[P_R_AIR] * p[P_ISA_LAPSE] / p[P_G0]
    for j in range(n):
        row = u[j]
        wf_tot = 0.0
        t_case = 0.0
        for e in range(ne):
            n2[e] = row[NU_FIXED + UE_N2 * ne + e]
            p3[e] = row[NU_FIXED + UE_P3 * ne + e]
            t3[e] = row[NU_FIXED + UE_T3 * ne + e]
            wbp[e] = row[NU_FIXED + UE_WBP * ne + e]
            wf_tot = wf_tot + row[NU_FIXED + UE_WF * ne + e] + row[NU_FIXED + UE_WFAB * ne + e]
            t_case = t_case + t3[e] / ne
            wpto[e] = p[P_PTO_RATIO] * n2[e]
        for w in range(N_WHEEL):
            pbrk[w] = row[U_PBRK + w]
            wheel[w] = row[U_WHEEL + w]
            wear0[w] = row[U_HEALTH + H_BRAKE_WEAR + w]
            tyre0[w] = row[U_HEALTH + H_TYRE_WEAR + w]
        t_s = row[U_T_S]
        p_s = row[U_P_S]
        rho = row[U_RHO]
        tas = row[U_TAS]
        mach = row[U_MACH]
        t_rec = t_s * (1.0 + (p[P_GAMMA_AIR] - 1.0) / 2.0 * mach * mach)
        airborne = 1.0 if (row[U_WOW] < 0.5 and row[U_WOW + 1] < 0.5 and row[U_WOW + 2] < 0.5) else 0.0
        gen_e = cfg[C_GEN_ENG]
        jfs_e = cfg[C_JFS_ENG]
        n2f = n2[gen_e] / p[P_N2_100PCT]

        # 2. electrical (starter motor on the battery)
        mon = motor_on(f, i, p)
        emf = motor_emf(f, p)
        v_ac, v_main, v_ess, v_emg, gen_shaft, bk_shaft, i_m, av_heat, probe_heat = electrical_step(
            f, i, p, n2f, airborne, t_rec, mon, emf, row[U_HEALTH + H_BATT_FADE], nxfer, dt
        )
        # 3. JFS
        p_jfs = jfs_step(
            f,
            i,
            p,
            i_m,
            n2[jfs_e],
            wpto[jfs_e],
            p_s,
            t_s,
            t_rec,
            u_ign,
            row[U_HEALTH + H_JFS_PWR],
            row[U_HEALTH + H_JFS_DRAG],
            dt,
        )
        # 4. hydraulics (each fuel-cooled HX takes half of the engine fuel flow)
        t_fuel = f[F_FUEL_T]
        wf_hx = wf_tot / N_HYD
        shaft0, q_hx0, _d0 = hyd_system(
            f,
            p,
            0,
            wpto[cfg[C_PUMP_ENG0]],
            row[U_HYD_DEM] + row[U_W_HYD],
            wf_hx,
            t_fuel,
            t_rec,
            p_s,
            row[U_HEALTH + H_PUMP_LEAK],
            row[U_HEALTH + H_SYS_LEAK],
            row[U_HEALTH + H_EXT_LEAK],
            row[U_HEALTH + H_COMP_DRIFT],
            row[U_HEALTH + H_FILTER],
            row[U_HEALTH + H_PRECHARGE],
            dt,
            nsub,
        )
        shaft1, q_hx1, _d1 = hyd_system(
            f,
            p,
            1,
            wpto[cfg[C_PUMP_ENG1]],
            row[U_HYD_DEM + 1] + row[U_W_HYD + 1],
            wf_hx,
            t_fuel,
            t_rec,
            p_s,
            row[U_HEALTH + H_PUMP_LEAK + 1],
            row[U_HEALTH + H_SYS_LEAK + 1],
            row[U_HEALTH + H_EXT_LEAK + 1],
            row[U_HEALTH + H_COMP_DRIFT + 1],
            row[U_HEALTH + H_FILTER + 1],
            row[U_HEALTH + H_PRECHARGE + 1],
            dt,
            nsub,
        )
        # engine fuel inlet temperature: tank fuel + the heat the hydraulic HXs put into the engine-bound flow
        c_wf = wf_tot * p[P_FUEL_CP]
        t_fuel_in = t_fuel + (q_hx0 + q_hx1) / c_wf if c_wf.real > 1e-9 else t_fuel + 0.0 * q_hx0
        # 5. fuel and mass properties
        slosh_step(f, p, row[U_FSPEC], row[U_FSPEC + 2], dt)
        fuel_step(f, i, p, wf_tot, t_rec, row[U_HEALTH + H_XFER_LOSS], dt)
        mass_properties(f, p, mp)
        # 6. ECS
        tb, tphx, tto, pb, pphx, _pc = ecs_step(
            f,
            p,
            ne,
            p3,
            t3,
            wbp,
            p_s,
            t_rec,
            rho,
            tas,
            row[U_HEALTH + H_HX_FOUL],
            row[U_HEALTH + H_CAB_LEAK],
            av_heat,
            bleed,
            dt,
        )
        # 7. brakes and tyres; 8. fire zone
        landing_step(
            f,
            i,
            p,
            pbrk,
            wheel,
            row[U_WOW + 1],
            row[U_WOW + 2],
            tas,
            mp[0],
            t_s,
            wear0,
            tyre0,
            f[F_HYD_P + brk_sys],
            brk_p,
            dt,
        )
        fire_step(f, i, p, t_case, t_rec, rho, tas, dt)
        # 9. AMAGB losses, oil temperature and PTO power per engine
        for e in range(ne):
            r = pos(wpto[e]) / w_rated
            pto[e] = p[P_GB_LOSS_RATED] * r * r * (1.0 + row[U_HEALTH + H_AMAGB])
        p_gb = pto[gen_e]
        f[F_GB_T] = f[F_GB_T] + dt * (p_gb - p[P_GB_UA] * (f[F_GB_T] - t_rec)) / p[P_GB_HEAT_CAP]
        pto[cfg[C_PUMP_ENG0]] = pto[cfg[C_PUMP_ENG0]] + shaft0
        pto[cfg[C_PUMP_ENG1]] = pto[cfg[C_PUMP_ENG1]] + shaft1
        pto[gen_e] = pto[gen_e] + gen_shaft + bk_shaft
        pto[jfs_e] = pto[jfs_e] - p_jfs
        f[F_LAST_TAS] = tas + 0.0 * f[F_LAST_TAS]
        i[I_TICK] = i[I_TICK] + 1

        # outputs
        for h in range(N_HYD):
            out[j, O_HYD_P + h] = f[F_HYD_P + h]
            out[j, O_HYD_DP + h] = pos(f[F_HYD_P + h] - p[P_HYD_P_RET])
            out[j, O_HYD_T + h] = f[F_HYD_T + h]
        for k in range(N_TANKS):
            out[j, O_FUEL_M + k] = f[F_FUEL_M + k]
        out[j, O_MASS] = mp[0]
        for a in range(3):
            out[j, O_CG + a] = mp[1 + a]
        for a in range(9):
            out[j, O_INERTIA + a] = mp[4 + a]
        out[j, O_BUS_V + B_DCM] = v_main
        out[j, O_BUS_V + B_ESS] = v_ess
        out[j, O_BUS_V + B_EMG] = v_emg
        out[j, O_BUS_V + B_AC] = v_ac
        out[j, O_BATT_SOC] = f[F_BATT_SOC]
        # recorded LRU-computed channels (AD-42): battery display (integrates current from the 'full' mark of
        # the rated capacity, so capacity fade is invisible to it), cabin altitude (CPCS, ISA), AMAGB input
        # speed
        fade = row[U_HEALTH + H_BATT_FADE]
        ah_disp = p[P_BATT_CAP_AH] - p[P_BATT_CAP_AH] * (1.0 - fade) * (1.0 - f[F_BATT_SOC])
        out[j, O_BATT_AH] = ah_disp
        out[j, O_CAB_ALT] = p[P_ISA_T0] / p[P_ISA_LAPSE] * (1.0 - (f[F_ECS_PCAB] / p[P_ISA_P0]) ** alt_exp)
        out[j, O_AMAGB_W] = wpto[gen_e]
        for h in range(N_HYD):
            out[j, O_HYD_LVL + h] = clip(f[F_HYD_VRES + h] / p[P_HYD_RES_V], 0.0, 1.0)
        for w in range(N_WHEEL):
            out[j, O_BRK_P + w] = brk_p[w]
        out[j, O_ECS_T] = tb
        out[j, O_ECS_T + 1] = tphx
        out[j, O_ECS_T + 2] = tto
        out[j, O_ECS_T + 3] = f[F_ECS_TCAB]
        out[j, O_ECS_T + 4] = f[F_ECS_TAV]
        out[j, O_ECS_P] = pb
        out[j, O_ECS_P + 1] = pphx
        out[j, O_ECS_P + 2] = f[F_ECS_PCAB]
        out[j, O_ECS_P + 3] = f[F_ECS_PCAB]
        out[j, O_ECS_P + 4] = f[F_ECS_PCAB]
        for w in range(N_WHEEL):
            out[j, O_BRK_T + w] = f[F_BRK_T + w]
            out[j, O_BRK_W + w] = wear0[w] + f[F_BRK_DW + w]
            out[j, O_TYRE_W + w] = tyre0[w] + f[F_TYRE_DW + w]
        for e in range(ne):
            out[j, NO_FIXED + OE_BLEED * ne + e] = bleed[e]
            out[j, NO_FIXED + OE_PTO * ne + e] = pto[e]
            out[j, NO_FIXED + OE_FUEL_IN * ne + e] = t_fuel_in
        outi[j, OI_GEN_ON] = i[I_GEN_ON]
        outi[j, OI_GEN_OUT] = 1 - i[I_GEN_ON]
        outi[j, OI_PROBE_HEAT] = probe_heat
        outi[j, OI_BATT_LOW] = 1 if ah_disp.real < p[P_BATT_LOW_WARN_AH].real else 0
        outi[j, OI_BK_BITE] = i[I_BK_FAULT]
        outi[j, OI_CHUTE] = i[I_CHUTE]  # util.chute_state (AD-47): changed only by events
        mode = i[I_JFS_MODE]
        if mode == JFS_COAST and i[I_JFS_OUTCOME] != OUT_OK:
            mode = JFS_STATE_COAST_FAIL
        outi[j, OI_JFS] = mode
    return f, i, out, outi


def kernel_reference(f, i, p, u, cfg, u_ign, dt):
    """The NumPy reference: the same source uncompiled (outer loop in Python; see the module docstring)."""
    return utilities_kernel.py_func(f, i, p, u, cfg, u_ign, dt)
