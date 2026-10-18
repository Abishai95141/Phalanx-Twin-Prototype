"""M07 compiled kernel: 0-D component-level F404-IN20 model with inter-component volume dynamics (AD-09,
AD-22).

Structure (architecture §6 M07; method template [TRANSFER: F100 TM X-3261 / TP-1034 volume-dynamics
real-time model], maps and thermodynamics per ``maps.py`` / ``thermo.py``):

    inlet -> fan -> V21 (fan exit + bypass duct) -> {HPC, bypass duct} ;  HPC -> V3 (HPC exit + combustor)
    -> HPT (NGV choked flow sets W41; combustor energy-storage lag on T41) -> V45 -> LPT -> V5 (LPT exit
    duct) -> core flow law -> V6 (mixer static + AB) <- bypass flow law <- V21 ; V6 -> AB -> nozzle (A8).

Continuous states (``layout.X_NAMES``): two rotor speeds, five volume pressures, T41, five actuators, two
metal temperatures (heat soak, tip clearance) and the oil temperature. Process disturbances ``env.w_engine``
(AD-32) enter the **dynamics**: fuel metering (metered flow), combustor efficiency (heat release), inlet
recovery (P2) and HP-shaft load (torque balance). They never enter an output directly.

Discrete processes (evaluated once per 240 Hz tick on the end-of-tick state): afterburner light-off state
machine (keyed light-off-delay draw per attempt), main-burner lean blow-out (with persistence) / relight,
and a surge event model (PROXY A-W1.3a-9: margin-triggered fan and HPC delivery collapse and recovery; no
Greitzer post-stall dynamics).

Numerics: each 240 Hz tick holds inputs constant and integrates Heun (RK2) sub-steps, at least ``n_sub`` and
enough that the stiffest volume mode (the ``lam_est`` estimate from the tick-start evaluation) satisfies
hs * lam_est <= ``stab_hlam``; a tick whose Heun-minus-Euler error estimate on the volume pressures exceeds
``int_tol`` is recomputed from the same start with twice the sub-steps, up to ``n_sub_max`` (deterministic and
state-based; resolves stiff surge and mixer-flow events). ``step`` is ``step_block`` with L = 1 (bitwise
identical by construction). The NumPy reference is the same source run uncompiled (``NUMBA_DISABLE_JIT=1``);
``engine_kernel.py_func`` runs the outer loop uncompiled. Complex-step safe: comparisons on ``.real``; no
``abs``/``min``/``max`` on derivative-carrying values.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numba import njit

from .layout import (
    A_ABHEAT,
    A_BEYOND,
    A_BPR,
    A_CLEAR,
    A_ETAFAN,
    A_ETAHPC,
    A_ETAHPT,
    A_ETALPT,
    A_FAR4,
    A_FG,
    A_FN,
    A_LAM,
    A_N1C,
    A_N2C,
    A_OILP,
    A_P2,
    A_P4,
    A_P5,
    A_P7,
    A_P25,
    A_PRFAN,
    A_PRHPC,
    A_PRHPT,
    A_PRLPT,
    A_PS3,
    A_PWEXT,
    A_PWFAN,
    A_PWHPC,
    A_PWHPT,
    A_PWLPT,
    A_QSOAK,
    A_SMFAN,
    A_SMHPC,
    A_T2,
    A_T3,
    A_T4,
    A_T5,
    A_T6,
    A_T7,
    A_T21,
    A_T25,
    A_T41AD,
    A_T45,
    A_V0,
    A_VIB0,
    A_VIB1,
    A_VIB2,
    A_W2,
    A_W2C,
    A_W5MIX,
    A_W8,
    A_W13,
    A_W25,
    A_W41,
    A_WBLEED,
    A_WFL,
    A_WLPT,
    A_WROT,
    AB_LIGHTING,
    AB_LIT,
    AB_OFF,
    F_AB_DELAY,
    F_AB_TIMER,
    F_FLAME_TIMER,
    F_FLT0,
    F_SURGE_TIMER,
    FLT_AB_BLOCK,
    FLT_BLEED,
    FLT_BLEED_FRAC,
    FLT_COMB,
    FLT_NOZ_LEAK,
    FLT_OIL_CRIT,
    FLT_OIL_LEVEL,
    FLT_OIL_RATE,
    FLT_OIL_SEIZE,
    FLT_RUN_N2,
    FLT_SM,
    FLT_SM_N2,
    FLT_TQ_HP,
    FLT_TQ_LP,
    FLT_UA_LOSS,
    FLT_VIB1,
    FLT_VIB2,
    FLT_VIBBB,
    FLT_WF_BIAS,
    FLT_WF_CAP,
    I_AB,
    I_BUFPOS,
    I_FLAME,
    I_NAB,
    I_NSURGE,
    I_SURGE,
    I_TICK,
    INL_P2,
    INL_PS,
    INL_T2,
    INL_TS,
    INL_V0,
    INL_WAR,
    INL_WFL,
    NAUX,
    NFLT,
    NINL,
    NX,
    NY,
    NYI,
    P_A3,
    P_A8MAX,
    P_A8MIN,
    P_A8RATE,
    P_AB_BT,
    P_AB_NP,
    P_AB_PREF,
    P_AB_SIGMA,
    P_AB_T1REF,
    P_AB_TREF,
    P_CCASE,
    P_CD8,
    P_CFG,
    P_CMET,
    P_CNGV,
    P_COIL,
    P_DPAB,
    P_DPB,
    P_DPCD,
    P_EPS5,
    P_EPS13,
    P_ETAAB,
    P_ETAB,
    P_ETAM,
    P_FARLBO,
    P_FARLIGHT,
    P_FROT,
    P_FST,
    P_GCLR_C,
    P_GCLR_M,
    P_GCLR_W,
    P_GTURB,
    P_HAMET,
    P_IHP,
    P_ILP,
    P_INTTOL,
    P_K5,
    P_K13,
    P_KECVG,
    P_KEFF,
    P_KEFVG,
    P_KETACLR,
    P_KRAY,
    P_KWCVG,
    P_KWFVG,
    P_LHV,
    P_ME_A,
    P_ME_B,
    P_N1CDES,
    P_N1DES,
    P_N2CDES,
    P_N2DES,
    P_N2OILK,
    P_NLBO,
    P_NSUBMAX,
    P_OILVISC,
    P_P3LIGHT,
    P_PACC,
    P_PLBO,
    P_POILREG,
    P_PRCH_HPT,
    P_PRCH_LPT,
    P_QOIL,
    P_R6MIX,
    P_SEFF_FAN,
    P_SEFF_HPC,
    P_SEFF_HPT,
    P_SEFF_LPT,
    P_SMTRIG,
    P_SNC_FAN,
    P_SNC_HPC,
    P_SNP_HPT,
    P_SNP_LPT,
    P_SPR_FAN,
    P_SPR_HPC,
    P_SPR_HPT,
    P_SPR_LPT,
    P_STAB,
    P_STALL_SLOPE,
    P_SURGE_CMIN,
    P_SURGE_EFF,
    P_SURGE_TREC,
    P_SWC_FAN,
    P_SWC_HPC,
    P_SWP_HPT,
    P_SWP_LPT,
    P_TAUA8,
    P_TAUCASE,
    P_TAUCOMB,
    P_TAUFMV,
    P_TAUVG,
    P_TAUWFAB,
    P_TCREF,
    P_TIGN,
    P_TLBO,
    P_TMREF,
    P_TOILREF,
    P_UAOIL_AIR,
    P_UAOIL_FUEL,
    P_V3,
    P_V5,
    P_V6,
    P_V21,
    P_V45,
    P_VGMAX,
    P_VGMIN,
    P_VGRATE,
    P_VGSAT,
    P_VIBEXP,
    P_VIBK1,
    P_VIBK2,
    P_VIBK3,
    P_W2DES,
    P_W41DES,
    P_WC3DES,
    P_WC6DES,
    P_WFAB_MIN,
    P_WFDES,
    P_WFMINFL,
    PTO_W_FLOOR,
    U_A8,
    U_BLEED,
    U_H0,
    U_MACH,
    U_PS,
    U_PTO,
    U_Q,
    U_TFUEL,
    U_TS,
    U_VG1,
    U_WCE,
    U_WF,
    U_WFAB,
    U_WFF,
    U_WFM_D,
    U_WIR,
    U_WSL,
    UI_ABEN,
    UI_IGN,
    X_A8,
    X_N1,
    X_N2,
    X_P3,
    X_P5,
    X_P6,
    X_P21,
    X_P45,
    X_T41,
    X_TC,
    X_TM,
    X_TOIL,
    X_VG1,
    X_VG2,
    X_WFAB,
    X_WFM,
    Y_A8,
    Y_BLP3,
    Y_BLT3,
    Y_FN,
    Y_N1,
    Y_N2,
    Y_OILP,
    Y_OILT,
    Y_P2,
    Y_P5,
    Y_PS3,
    Y_SM,
    Y_T2,
    Y_T3,
    Y_T5,
    Y_T25,
    Y_VG1,
    Y_VG2,
    Y_VIB0,
    Y_VIB1,
    Y_VIB2,
    Y_W2,
    Y_WF,
    Y_WFAB,
    YI_AB,
    YI_FLAME,
)
from .maps import compressor_lookup, flow_function, interp1, turbine_lookup, turbine_unchoke
from .thermo import compress, expand, gamma_of, gas_r, h_cp, phi_cp, t_from_h, t_from_phi

_JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}
# Integer powers are written as explicit products: Numba compiles x ** 2 to x * x while Python/NumPy
# call libm pow, which differs by 1 ULP on darwin and would break kernel == reference bitwise (A7).

T_STD = 288.15  # K, corrected-parameter reference temperature (TM-100159 convention)
P_STD = 101325.0  # Pa, corrected-parameter reference pressure
RPM_PER_RADS = 60.0 / (2.0 * np.pi)
N_FLOOR = 10.0  # rad/s, numerical floor on rotor speeds (sub-idle regime is not modelled; A-W1.3a-3)
P_FLOOR = 2000.0  # Pa, numerical floor on volume pressures
T_FLOOR = 150.0  # K
T_CEIL = 3500.0  # K, numerical ceiling (stoichiometric cap keeps T41 well below)


class EngineTables(NamedTuple):
    """Tables fed to the kernel (AD-22: tables as a NamedTuple of arrays)."""

    thermo: np.ndarray  # (3, 2, 10) basis coefficients, thermo.basis_coefficients
    fan_nc: np.ndarray
    fan_wc: np.ndarray
    fan_pr: np.ndarray
    fan_eff: np.ndarray
    hpc_nc: np.ndarray
    hpc_wc: np.ndarray
    hpc_pr: np.ndarray
    hpc_eff: np.ndarray
    hpt_np: np.ndarray
    hpt_pr: np.ndarray
    hpt_wp: np.ndarray
    hpt_eff: np.ndarray
    lpt_np: np.ndarray
    lpt_pr: np.ndarray
    lpt_wp: np.ndarray
    lpt_eff: np.ndarray
    fvg_x: np.ndarray  # reference FVG schedule: corrected fan speed (fraction of design)
    fvg_y: np.ndarray  # rad
    cvg_x: np.ndarray  # reference CVG schedule: corrected core speed (fraction of design)
    cvg_y: np.ndarray  # rad


# --------------------------------------------------------------------------------------------- inlet


@njit(**_JIT)
def inlet(ts, ps, q, mach, w_ir, p, tb, inl):
    """Engine-face total conditions (once per tick). MIL-E-5008B ram recovery above M1 [TRANSFER: standard].

    ``w_ir`` is the inlet-recovery process disturbance (fractional, AD-32)."""
    B = tb.thermo
    war = q / (1.0 - q)
    R0 = gas_r(0.0 * war, war, B)
    g0 = gamma_of(ts, 0.0 * war, war, B)
    v0 = mach * np.sqrt(g0 * R0 * ts)
    h0, cp0 = h_cp(ts, 0.0 * war, war, B)
    t2 = t_from_h(h0 + 0.5 * v0 * v0, 0.0 * war, war, B, ts + 0.5 * v0 * v0 / cp0)
    phi0, _ = phi_cp(ts, 0.0 * war, war, B)
    phi2, _ = phi_cp(t2, 0.0 * war, war, B)
    sigma = 1.0 + 0.0 * mach
    if mach.real > 1.0:
        sigma = 1.0 - p[P_ME_A] * (mach - 1.0) ** p[P_ME_B]
    p2 = ps * np.exp((phi2 - phi0) / R0) * sigma * (1.0 + w_ir)
    inl[INL_T2] = t2
    inl[INL_P2] = p2
    inl[INL_WAR] = war
    inl[INL_V0] = v0
    inl[INL_PS] = ps
    inl[INL_TS] = ts


# --------------------------------------------------------------------------------------------- dynamics


@njit(**_JIT)
def _vg_dev(d, sat):
    """Off-schedule VG angle with smooth saturation at +-sat (the linear sensitivities are anchored on small
    mis-rigs; A-W1.3a-12). Analytic for real d (complex-step safe)."""
    q = d / sat
    return d / np.sqrt(1.0 + q * q)


@njit(**_JIT)
def deriv(x, ab_state, flame, surge, surge_timer, inl, ue, p, tb, dx, aux, flt):
    """Continuous dynamics dx/dt = f(x, u, disturbances, health, faults) for one engine; fills ``aux``.

    ``flt`` is the effective fault-perturbation slice of the float state (``layout.FLT_NAMES``, written by the
    ``eng.fault_inject`` handler; all zero and a full oil charge on a healthy engine)."""
    B = tb.thermo
    # ---- guarded states (numerical floors on the real part; inactive in normal operation)
    n1 = x[X_N1]
    if n1.real < N_FLOOR:
        n1 = N_FLOOR + 0.0 * n1
    n2 = x[X_N2]
    if n2.real < N_FLOOR:
        n2 = N_FLOOR + 0.0 * n2
    p21 = x[X_P21]
    if p21.real < P_FLOOR:
        p21 = P_FLOOR + 0.0 * p21
    p3 = x[X_P3]
    if p3.real < P_FLOOR:
        p3 = P_FLOOR + 0.0 * p3
    p45 = x[X_P45]
    if p45.real < P_FLOOR:
        p45 = P_FLOOR + 0.0 * p45
    p5 = x[X_P5]
    if p5.real < P_FLOOR:
        p5 = P_FLOOR + 0.0 * p5
    p6 = x[X_P6]
    if p6.real < P_FLOOR:
        p6 = P_FLOOR + 0.0 * p6
    t41 = x[X_T41]
    if t41.real < T_FLOOR:
        t41 = T_FLOOR + 0.0 * t41
    if t41.real > T_CEIL:
        t41 = T_CEIL + 0.0 * t41
    t2 = inl[INL_T2]
    p2 = inl[INL_P2]
    war = inl[INL_WAR]
    z0 = 0.0 * war
    h = ue[U_H0:]
    # ---- fan
    th2 = t2 / T_STD
    n1c = n1 * RPM_PER_RADS / np.sqrt(th2)
    n1c_frac = n1c / p[P_N1CDES]
    pr_fan = p21 / p2
    wcm, em, prst, _ = compressor_lookup(
        n1c / p[P_SNC_FAN],
        (pr_fan - 1.0) / p[P_SPR_FAN] + 1.0,
        tb.fan_nc,
        tb.fan_wc,
        tb.fan_pr,
        tb.fan_eff,
        p[P_STALL_SLOPE],
    )
    dvg1 = _vg_dev(x[X_VG1] - interp1(tb.fvg_x, tb.fvg_y, n1c_frac), p[P_VGSAT])
    # fan-face distortion process disturbance (AD-46, LP-spool-specific path): w_fan_face > 0 lowers the fan
    # flow capacity by that fraction and the fan efficiency by k_eta_fan_face times it
    wff = ue[U_WFF]
    w2c = wcm * p[P_SWC_FAN] * (1.0 - p[P_KWFVG] * dvg1) * (1.0 + h[1]) * (1.0 - wff)
    eta_fan = em * p[P_SEFF_FAN] * (1.0 - p[P_KEFVG] * dvg1 * dvg1) * (1.0 + h[0]) * (1.0 - p[P_KEFF] * wff)
    w2 = w2c * (p2 / P_STD) / np.sqrt(th2)
    cs = 1.0 + 0.0 * w2
    if surge == 1:
        # PROXY surge event (A-W1.3a-9): compressor delivery (fan and HPC) collapses to c_min and recovers
        # quadratically by t_rec
        frac = surge_timer / p[P_SURGE_TREC]
        if frac.real > 1.0:
            frac = 1.0 + 0.0 * frac
        cs = p[P_SURGE_CMIN] + (1.0 - p[P_SURGE_CMIN]) * frac * frac
        w2 = w2 * cs
    t21, dh_fan = compress(t2, pr_fan, eta_fan, z0, war, B)
    sm_fan = (1.0 + (prst - 1.0) * p[P_SPR_FAN]) / pr_fan - 1.0
    pw_fan = w2 * dh_fan
    # ---- HPC
    p25 = p21 * (1.0 - p[P_DPCD])
    t25 = t21
    th25 = t25 / T_STD
    n2c = n2 * RPM_PER_RADS / np.sqrt(th25)
    n2c_frac = n2c / p[P_N2CDES]
    pr_hpc = p3 / p25
    wcm2, em2, prst2, beyond = compressor_lookup(
        n2c / p[P_SNC_HPC],
        (pr_hpc - 1.0) / p[P_SPR_HPC] + 1.0,
        tb.hpc_nc,
        tb.hpc_wc,
        tb.hpc_pr,
        tb.hpc_eff,
        p[P_STALL_SLOPE],
    )
    dvg2 = _vg_dev(x[X_VG2] - interp1(tb.cvg_x, tb.cvg_y, n2c_frac), p[P_VGSAT])
    w25c = wcm2 * p[P_SWC_HPC] * (1.0 - p[P_KWCVG] * dvg2) * (1.0 + h[3])
    eta_hpc = em2 * p[P_SEFF_HPC] * (1.0 - p[P_KECVG] * dvg2 * dvg2) * (1.0 + h[2])
    w25 = w25c * (p25 / P_STD) / np.sqrt(th25)
    if surge == 1:
        w25 = w25 * cs
        eta_hpc = eta_hpc * (1.0 - (1.0 - p[P_SURGE_EFF]) * (1.0 - cs) / (1.0 - p[P_SURGE_CMIN]))
    t3, dh_hpc = compress(t25, pr_hpc, eta_hpc, z0, war, B)
    sm_hpc = (1.0 + (prst2 - 1.0) * p[P_SPR_HPC]) / pr_hpc - 1.0
    pw_hpc = w25 * dh_hpc
    h3, _ = h_cp(t3, z0, war, B)
    r_air = gas_r(z0, war, B)
    # ---- bleeds and cooling (+ a bleed-leak / mis-scheduled-bleed fault)
    wbl = ue[U_BLEED] + flt[FLT_BLEED] + flt[FLT_BLEED_FRAC] * w25
    if wbl.real < 0.0:
        wbl = 0.0 * wbl
    if wbl.real > 0.15 * w25.real:
        wbl = 0.15 * w25
    wrot = p[P_FROT] * w25
    # ---- combustor + HPT (NGV-choked flow sets W41 from the T41 state)
    wc3 = w25 * np.sqrt(t3) / p3
    q3 = wc3 / p[P_WC3DES]
    p4 = p3 * (1.0 - p[P_DPB] * q3 * q3)
    n2rpm = n2 * RPM_PER_RADS
    pr_hpt = p4 / p45
    wp_m, eh_m = turbine_lookup(
        n2rpm / np.sqrt(t41) / p[P_SNP_HPT],
        (pr_hpt - 1.0) / p[P_SPR_HPT] + 1.0,
        tb.hpt_np,
        tb.hpt_pr,
        tb.hpt_wp,
        tb.hpt_eff,
    )
    w41 = (
        wp_m
        * p[P_SWP_HPT]
        * turbine_unchoke(pr_hpt, p[P_PRCH_HPT], p[P_GTURB])
        * (1.0 + h[5])
        * p4
        / np.sqrt(t41)
    )
    wf_c = inl[INL_WFL]
    if wf_c.real < 0.0:
        wf_c = 0.0 * wf_c
    below_run = n2.real < flt[FLT_RUN_N2].real  # start faults act below run speed only
    if below_run:
        wf_c = wf_c * (1.0 + flt[FLT_WF_BIAS])  # hot start: over-fuelling
    w_air41 = w41 - wf_c
    if w_air41.real < 1e-3:
        w_air41 = 1e-3 + 0.0 * w_air41
    w_comb = w_air41 / (1.0 + p[P_CNGV])
    lit = 1.0 if flame == 1 else 0.0
    # fuel that can burn is limited by the combustor oxygen (stoichiometric cap; composition never rich)
    wf_b = wf_c
    wf_st = p[P_FST] * w_comb / (1.0 + war)
    if wf_b.real > wf_st.real:
        wf_b = wf_st
    f41 = lit * wf_b * (1.0 + war) / w_air41
    far4 = wf_c * (1.0 + war) / w_comb
    eta_b = p[P_ETAB] * (1.0 + h[8]) * (1.0 + ue[U_WCE]) * lit
    if below_run:
        eta_b = eta_b * (1.0 - flt[FLT_COMB])  # hung start: combustion-efficiency loss
    h41_ad = (w_air41 * h3 + eta_b * wf_b * p[P_LHV]) / w41
    t41_ad = t_from_h(h41_ad, f41, war, B, t41)
    # tip clearance (fraction of blade height, relative to the design steady state)
    clear = (
        p[P_GCLR_C] * (x[X_TC] - p[P_TCREF])
        - p[P_GCLR_M] * (x[X_TM] - p[P_TMREF])
        - p[P_GCLR_W] * (n2 * n2 - p[P_N2DES] * p[P_N2DES]) / (p[P_N2DES] * p[P_N2DES])
    )
    eta_hpt = eh_m * p[P_SEFF_HPT] * (1.0 + h[4]) * (1.0 - p[P_KETACLR] * clear)
    t45a, dh_hpt = expand(t41, pr_hpt, eta_hpt, f41, war, B)
    pw_hpt = w41 * dh_hpt
    # heat soak: gas -> hot-section rotor metal (MAPSS TMPC analogue)
    t_gas = 0.5 * (t41 + t45a)
    wr = w41 / p[P_W41DES]
    if wr.real < 1e-3:
        wr = 1e-3 + 0.0 * wr
    ha = p[P_HAMET] * wr**0.8
    q_soak = ha * (t_gas - x[X_TM])
    # station 45: rotor/LPT cooling air mixes in, heat-soak flux removed
    w45 = w41 + wrot
    h45a, _ = h_cp(t45a, f41, war, B)
    h45 = (w41 * h45a + wrot * h3 - q_soak) / w45
    f45 = lit * wf_b * (1.0 + war) / (w_air41 + wrot)
    t45 = t_from_h(h45, f45, war, B, t45a)
    # ---- LPT (discharges into the LPT-exit duct volume V5)
    pr_lpt = p45 / p5
    n1rpm = n1 * RPM_PER_RADS
    wp_l, el_m = turbine_lookup(
        n1rpm / np.sqrt(t45) / p[P_SNP_LPT],
        (pr_lpt - 1.0) / p[P_SPR_LPT] + 1.0,
        tb.lpt_np,
        tb.lpt_pr,
        tb.lpt_wp,
        tb.lpt_eff,
    )
    wlpt = (
        wp_l
        * p[P_SWP_LPT]
        * turbine_unchoke(pr_lpt, p[P_PRCH_LPT], p[P_GTURB])
        * (1.0 + h[7])
        * p45
        / np.sqrt(t45)
    )
    eta_lpt = el_m * p[P_SEFF_LPT] * (1.0 + h[6])
    t5, dh_lpt = expand(t45, pr_lpt, eta_lpt, f45, war, B)
    pw_lpt = wlpt * dh_lpt
    # ---- mixer static-pressure match (A-W1.3a-5): the core stream (from V5) and the bypass stream (from V21)
    # each reach the mixer static pressure P6 through a duct-and-dynamic-head flow law calibrated at design
    r5 = gas_r(f45, war, B)
    rho5 = p5 / (r5 * t5)
    dp5 = p5 - p6
    w5m = p[P_K5] * np.sqrt(rho5) * dp5 / (dp5 * dp5 + p[P_EPS5] * p[P_EPS5]) ** 0.25
    rho21 = p21 / (r_air * t21)
    dp13 = p21 - p6
    w13 = p[P_K13] * np.sqrt(rho21) * dp13 / (dp13 * dp13 + p[P_EPS13] * p[P_EPS13]) ** 0.25
    w6 = w5m + w13
    # mixing uses the forward parts of both streams (reverse flow only occurs in abnormal transients)
    w5f = w5m
    if w5f.real < 1e-3:
        w5f = 1e-3 + 0.0 * w5f
    w13f = w13
    if w13f.real < 1e-3:
        w13f = 1e-3 + 0.0 * w13f
    h5, _ = h_cp(t5, f45, war, B)
    h21, _ = h_cp(t21, z0, war, B)
    h6 = (w5f * h5 + w13f * h21) / (w5f + w13f)
    w5_dry = w5f / (1.0 + f45 + war)
    w6_dry = w5_dry + w13f / (1.0 + war)
    f6 = f45 * w5_dry / w6_dry
    t6 = t_from_h(h6, f6, war, B, (w5f * t5 + w13f * t21) / (w5f + w13f))
    # ---- afterburner
    wfab = x[X_WFAB]
    if wfab.real < 0.0:
        wfab = 0.0 * wfab
    ab_lit = 1.0 if ab_state == AB_LIT else 0.0
    wfab_b = wfab  # AB fuel that can burn: limited by the oxygen left after core combustion
    wfab_st = (p[P_FST] - f6) * w6_dry
    if wfab_b.real > wfab_st.real:
        wfab_b = wfab_st
    ab_heat = ab_lit * p[P_ETAAB] * wfab_b * p[P_LHV]
    w6f = w5f + w13f
    h7 = (w6f * h6 + ab_heat) / (w6f + wfab)
    f7 = f6 + ab_lit * wfab_b / w6_dry
    t7 = t_from_h(h7, f7, war, B, t6 + ab_heat / ((w6f + wfab) * 1250.0))
    wc6 = w6 * np.sqrt(t6) / p6
    q6 = wc6 / p[P_WC6DES]
    wq6 = q6 * q6
    p6t = p6 * (1.0 + p[P_R6MIX] * wq6)  # mixed-out total (mixer static + mixed dynamic head)
    p7 = p6t * (1.0 - p[P_DPAB] * wq6 - p[P_KRAY] * (t7 / t6 - 1.0))
    # ---- nozzle (variable convergent-divergent, fully expanded, gross-thrust coefficient)
    r7 = gas_r(f7, war, B)
    g7 = gamma_of(t7, f7, war, B)
    ps0 = inl[INL_PS]
    leak = flt[FLT_NOZ_LEAK]  # liner burn-through: a leak area beside the throat that makes no thrust
    a8e = x[X_A8] * p[P_CD8] * (1.0 + h[9]) * (1.0 + leak)
    pr8 = p7 / ps0
    if pr8.real < 1.0 + 1e-9:
        pr8 = 1.0 + 1e-9 + 0.0 * pr8
    w8 = a8e * p7 * flow_function(pr8, g7) / np.sqrt(r7 * t7)
    phi7, _ = phi_cp(t7, f7, war, B)
    t9 = t_from_phi(phi7 - r7 * np.log(pr8), f7, war, B, t7 * pr8 ** (-(g7 - 1.0) / g7))
    h9, _ = h_cp(t9, f7, war, B)
    dh9 = h7 - h9
    if dh9.real < 0.0:
        dh9 = 0.0 * dh9
    fg = p[P_CFG] * w8 * np.sqrt(2.0 * dh9) / (1.0 + leak)
    v0 = inl[INL_V0]
    fn = fg - w2 * v0
    # ---- volume (mass) dynamics, quasi-steady volume temperatures (A-W1.3a-6)
    dx[X_P21] = r_air * t21 / p[P_V21] * (w2 - w25 - w13)
    dx[X_P3] = r_air * t3 / p[P_V3] * (w25 + wf_c - wbl - wrot - w41)
    dx[X_P45] = gas_r(f45, war, B) * t45 / p[P_V45] * (w41 + wrot - wlpt)
    dx[X_P5] = r5 * t5 / p[P_V5] * (wlpt - w5m)
    dx[X_P6] = gas_r(f6, war, B) * t6 / p[P_V6] * (w6 + wfab - w8)
    dx[X_T41] = (t41_ad - t41) / p[P_TAUCOMB]
    # ---- rotor dynamics. The shaft-load disturbance multiplies the HP-spool HPC + accessory load torque
    # (AD-32; 1 % is about 200 kW at MIL). PTO power (util.pto_power, negative = starter drive) enters as the
    # torque P / (N2 + PTO_W_FLOOR), the M09 start-drive convention, so a starter can turn a stopped spool.
    n2r = n2 / p[P_N2DES]
    pw_acc = p[P_PACC] * n2r * n2r
    q_pto = ue[U_PTO] / (n2 + PTO_W_FLOOR)
    pw_ext = pw_acc + q_pto * n2
    # oil-charge loss (fault): below the critical charge the bearings load up towards seizure
    oil_frac = 1.0 + 0.0 * x[X_TOIL]
    seize = 0.0 * x[X_TOIL]
    if flt[FLT_OIL_CRIT].real > 0.0 and flt[FLT_OIL_LEVEL].real < flt[FLT_OIL_CRIT].real:
        oil_frac = flt[FLT_OIL_LEVEL] / flt[FLT_OIL_CRIT]
        if oil_frac.real < 0.0:
            oil_frac = 0.0 * oil_frac
        seize = flt[FLT_OIL_SEIZE] * (1.0 - oil_frac)
    dx[X_N1] = (p[P_ETAM] * pw_lpt - pw_fan * (1.0 + flt[FLT_TQ_LP])) / (p[P_ILP] * n1)
    load_hp = 1.0 + ue[U_WSL] + flt[FLT_TQ_HP] + seize
    dx[X_N2] = ((p[P_ETAM] * pw_hpt - (pw_hpc + pw_acc) * load_hp) / n2 - q_pto) / p[P_IHP]
    # ---- actuators (first order with rate and position limits; limits act on the real part)
    wf_cmd = ue[U_WF]
    if wf_cmd.real < 0.0:
        wf_cmd = 0.0 * wf_cmd
    if flt[FLT_WF_CAP].real > 0.0 and wf_cmd.real > flt[FLT_WF_CAP].real:
        wf_cmd = flt[FLT_WF_CAP] + 0.0 * wf_cmd  # partly closed shut-off valve
    dx[X_WFM] = (wf_cmd - x[X_WFM]) / p[P_TAUFMV]
    a8t = ue[U_A8]
    if a8t.real < p[P_A8MIN].real:
        a8t = p[P_A8MIN] + 0.0 * a8t
    if a8t.real > p[P_A8MAX].real:
        a8t = p[P_A8MAX] + 0.0 * a8t
    ra = (a8t - x[X_A8]) / p[P_TAUA8]
    if ra.real > p[P_A8RATE].real:
        ra = p[P_A8RATE] + 0.0 * ra
    if ra.real < -p[P_A8RATE].real:
        ra = -p[P_A8RATE] + 0.0 * ra
    dx[X_A8] = ra
    for jj in range(2):
        vt = ue[U_VG1 + jj]
        if vt.real < p[P_VGMIN].real:
            vt = p[P_VGMIN] + 0.0 * vt
        if vt.real > p[P_VGMAX].real:
            vt = p[P_VGMAX] + 0.0 * vt
        rv = (vt - x[X_VG1 + jj]) / p[P_TAUVG]
        if rv.real > p[P_VGRATE].real:
            rv = p[P_VGRATE] + 0.0 * rv
        if rv.real < -p[P_VGRATE].real:
            rv = -p[P_VGRATE] + 0.0 * rv
        dx[X_VG1 + jj] = rv
    wfab_t = ue[U_WFAB]
    if ab_state == AB_OFF or wfab_t.real < 0.0:
        wfab_t = 0.0 * wfab_t
    dx[X_WFAB] = (wfab_t - x[X_WFAB]) / p[P_TAUWFAB]
    # ---- metal temperatures
    dx[X_TM] = q_soak / p[P_CMET]
    tc_t = t3 + p[P_CCASE] * (t41 - t3)
    dx[X_TC] = (tc_t - x[X_TC]) / p[P_TAUCASE]
    # ---- lube oil (lumped node; fuel-oil cooler effectiveness rises with fuel flow)
    wfr = wf_c / p[P_WFDES]
    if wfr.real < 1e-6:
        wfr = 1e-6 + 0.0 * wfr
    ua = (p[P_UAOIL_AIR] + p[P_UAOIL_FUEL] * wfr**0.8) * (1.0 - flt[FLT_UA_LOSS])
    n2o = n2 / p[P_N2DES]
    q_oil = p[P_QOIL] * n2o * n2o
    t_sink = ue[U_TFUEL]  # engine fuel inlet temperature (util.fuel_inlet_t, M09)
    dx[X_TOIL] = (q_oil - ua * (x[X_TOIL] - t_sink)) / p[P_COIL]
    oil_p = (
        p[P_POILREG]
        * (1.0 - np.exp(-(n2 / p[P_N2DES]) / p[P_N2OILK]))
        * (p[P_TOILREF] / x[X_TOIL]) ** p[P_OILVISC]
        * oil_frac
    )
    # ---- diagnostics
    aux[A_T2] = t2
    aux[A_P2] = p2
    aux[A_W2] = w2
    aux[A_W2C] = w2c
    aux[A_N1C] = n1c
    aux[A_T21] = t21
    aux[A_PRFAN] = pr_fan
    aux[A_ETAFAN] = eta_fan
    aux[A_SMFAN] = sm_fan
    aux[A_PWFAN] = pw_fan
    aux[A_T25] = t25
    aux[A_P25] = p25
    aux[A_W25] = w25
    aux[A_N2C] = n2c
    aux[A_PRHPC] = pr_hpc
    aux[A_ETAHPC] = eta_hpc
    aux[A_SMHPC] = sm_hpc
    aux[A_BEYOND] = beyond
    aux[A_T3] = t3
    g3 = w25 / p[P_A3]
    aux[A_PS3] = p3 - g3 * g3 * r_air * t3 / (2.0 * p3)
    aux[A_PWHPC] = pw_hpc
    aux[A_WBLEED] = wbl
    aux[A_WROT] = wrot
    aux[A_P4] = p4
    aux[A_W41] = w41
    aux[A_T4] = t41_ad  # replaced by the true T4 in output evaluations (see eval_t4)
    aux[A_FAR4] = far4
    aux[A_T41AD] = t41_ad
    aux[A_PRHPT] = pr_hpt
    aux[A_ETAHPT] = eta_hpt
    aux[A_PWHPT] = pw_hpt
    aux[A_T45] = t45
    aux[A_WLPT] = wlpt
    aux[A_PRLPT] = pr_lpt
    aux[A_ETALPT] = eta_lpt
    aux[A_PWLPT] = pw_lpt
    aux[A_T5] = t5
    aux[A_P5] = p5
    aux[A_W13] = w13
    aux[A_W5MIX] = w5m
    aux[A_BPR] = w13 / w25
    aux[A_T6] = t6
    aux[A_T7] = t7
    aux[A_P7] = p7
    aux[A_W8] = w8
    aux[A_FG] = fg
    aux[A_FN] = fn
    aux[A_WFL] = wf_c
    aux[A_QSOAK] = q_soak
    aux[A_CLEAR] = clear
    aux[A_OILP] = oil_p
    aux[A_VIB0] = p[P_VIBK1] * (n1 / p[P_N1DES]) ** p[P_VIBEXP] * (1.0 + flt[FLT_VIB1])
    aux[A_VIB1] = p[P_VIBK2] * (n2 / p[P_N2DES]) ** p[P_VIBEXP] * (1.0 + flt[FLT_VIB2])
    aux[A_VIB2] = p[P_VIBK3] * w2 / p[P_W2DES] * (1.0 + flt[FLT_VIBBB])
    aux[A_V0] = v0
    aux[A_PWEXT] = pw_ext
    aux[A_ABHEAT] = ab_heat
    # stiffness estimate of the volume-pressure modes (1/s, real parts only; drives the sub-step count). The
    # mixer pair V5-V6 is coupled through the core flow law: its fastest eigenvalue is bounded by the trace
    # (c5 s5 + c6 S6); the other volumes by their diagonal terms (choked or law outflow slopes).
    e5 = p[P_EPS5].real
    e13 = p[P_EPS13].real
    d5 = dp5.real
    d13 = dp13.real
    s5 = p[P_K5].real * np.sqrt(abs(rho5.real)) * (0.5 * d5 * d5 + e5 * e5) / (d5 * d5 + e5 * e5) ** 1.25
    s13 = (
        p[P_K13].real
        * np.sqrt(abs(rho21.real))
        * (0.5 * d13 * d13 + e13 * e13)
        / (d13 * d13 + e13 * e13) ** 1.25
    )
    c6 = gas_r(f6, war, B).real * t6.real / p[P_V6].real
    lam = r5.real * t5.real / p[P_V5].real * s5 + c6 * (abs(w8.real) / p6.real + s5 + s13)
    lam21 = r_air.real * t21.real / p[P_V21].real * (s13 + abs(w25.real) / p21.real)
    lam3 = r_air.real * t3.real / p[P_V3].real * abs(w41.real) / p3.real
    lam45 = gas_r(f45, war, B).real * t45.real / p[P_V45].real * abs(wlpt.real) / p45.real
    if lam21 > lam:
        lam = lam21
    if lam3 > lam:
        lam = lam3
    if lam45 > lam:
        lam = lam45
    aux[A_LAM] = lam


@njit(**_JIT)
def combustor_exit_temperature(aux, flame, inl, ue, p, tb):
    """T4 (combustor exit, before NGV cooling dilution), from the diagnostics of an evaluation."""
    B = tb.thermo
    war = inl[INL_WAR]
    w41 = aux[A_W41]
    wf_c = aux[A_WFL]
    w_air41 = w41 - wf_c
    if w_air41.real < 1e-3:
        w_air41 = 1e-3 + 0.0 * w_air41
    w_comb = w_air41 / (1.0 + p[P_CNGV])
    lit = 1.0 if flame == 1 else 0.0
    wf_b = wf_c
    wf_st = p[P_FST] * w_comb / (1.0 + war)
    if wf_b.real > wf_st.real:
        wf_b = wf_st
    h3, _ = h_cp(aux[A_T3], 0.0 * war, war, B)
    eta_b = p[P_ETAB] * (1.0 + ue[U_H0 + 8]) * (1.0 + ue[U_WCE]) * lit
    h4 = (w_comb * h3 + eta_b * wf_b * p[P_LHV]) / (w_comb + wf_c)
    f4 = lit * wf_b * (1.0 + war) / w_comb
    return t_from_h(h4, f4, war, B, aux[A_T41AD])


# --------------------------------------------------------------------------------------------- one tick


@njit(**_JIT)
def _eval(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay, flt):
    if n_delay == 0:
        inl[INL_WFL] = x[X_WFM] * (1.0 + ue[U_WFM_D])
    deriv(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, flt)


@njit(**_JIT)
def pressure_error(x, dx, dx2, hs):
    """Refinement error estimate of one Heun sub-step: max over the five volume pressures (P21, P3, P45, P5,
    P6) of the relative Heun-minus-Euler difference 0.5 hs |dx2 - dx| / |x| (real parts; a float)."""
    err = 0.0
    for j in range(X_P21, X_P6 + 1):
        e = 0.5 * hs * abs(dx2[j].real - dx[j].real) / abs(x[j].real)
        if e > err:
            err = e
    return err


@njit(**_JIT)
def _tick(fe, ie, bufe, p, tb, ue, uie, z_ab, a0, dt, n_sub, n_delay, x, xt, dx, dx0, dx2, aux, inl, ye, yie):
    """Advance one engine by one 240 Hz tick (in place on the kernel's private copies)."""
    inlet(ue[U_TS], ue[U_PS], ue[U_Q], ue[U_MACH], ue[U_WIR], p, tb, inl)
    if n_delay > 0:
        inl[INL_WFL] = bufe[ie[I_BUFPOS]]
    ab = ie[I_AB]
    flame = ie[I_FLAME]
    surge = ie[I_SURGE]
    flt = fe[F_FLT0:]
    # discrete-process timers count whole ticks (exact integers held in the float state): no float
    # accumulation, so event instants are exact tick counts (A-W1.3a-9/10)
    k_surge = fe[F_SURGE_TIMER].real
    st = 0.0 * fe[F_SURGE_TIMER] + k_surge * dt
    # Heun sub-steps. The count is state-based and deterministic: at least n_sub, and enough that the stiffest
    # volume mode stays inside the explicit stability region (hs * lam_est <= stab_hlam, from the
    # tick-start evaluation); then, if the Heun-minus-Euler estimate of the local error of any volume pressure
    # exceeds int_tol (relative, per sub-step), the whole tick is recomputed from the same start with twice
    # the sub-steps (up to n_sub_max). Decisions use real parts only (complex-step safe).
    st0 = st
    n_max = int(p[P_NSUBMAX].real)
    for j in range(NX):
        x[j] = fe[j]
    _eval(x, ab, flame, surge, st0, inl, ue, p, tb, dx0, aux, n_delay, flt)
    n_try = n_sub
    n_stab = int(np.ceil(dt * aux[A_LAM].real / p[P_STAB].real))
    if n_stab > n_try:
        n_try = n_stab
    if n_try > n_max:
        n_try = n_max
    tol = p[P_INTTOL].real
    while True:
        for j in range(NX):
            x[j] = fe[j]
        hs = dt / n_try
        err = 0.0
        for _s in range(n_try):
            st = st0 + (_s * hs if surge == 1 else 0.0)
            if _s == 0:
                for j in range(NX):
                    dx[j] = dx0[j]  # the tick-start evaluation (same state, inputs and timer)
            else:
                _eval(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay, flt)
            for j in range(NX):
                xt[j] = x[j] + hs * dx[j]
            _eval(xt, ab, flame, surge, st + 0.5 * hs, inl, ue, p, tb, dx2, aux, n_delay, flt)
            e = pressure_error(x, dx, dx2, hs)
            if e > err:
                err = e
            for j in range(NX):
                x[j] = x[j] + 0.5 * hs * (dx[j] + dx2[j])
        if err <= tol or 2 * n_try > n_max:
            break
        n_try = 2 * n_try
    for j in range(NX):
        fe[j] = x[j]
    if surge == 1:
        k_surge = k_surge + 1.0
        st = st0 + dt
    # output evaluation at the end-of-tick state (outputs are values at t_{k+1})
    _eval(x, ab, flame, surge, st, inl, ue, p, tb, dx, aux, n_delay, flt)
    wf_meas = x[X_WFM] * (1.0 + ue[U_WFM_D])
    ye[Y_N1] = x[X_N1]
    ye[Y_N2] = x[X_N2]
    ye[Y_T2] = aux[A_T2]
    ye[Y_T25] = aux[A_T25]
    ye[Y_T3] = aux[A_T3]
    ye[Y_T5] = aux[A_T5]
    ye[Y_P2] = aux[A_P2]
    ye[Y_PS3] = aux[A_PS3]
    ye[Y_P5] = aux[A_P5]
    ye[Y_WF] = wf_meas
    wfab_o = x[X_WFAB]
    if wfab_o.real < 0.0:
        wfab_o = 0.0 * wfab_o
    ye[Y_WFAB] = wfab_o
    ye[Y_A8] = x[X_A8]
    ye[Y_VG1] = x[X_VG1]
    ye[Y_VG2] = x[X_VG2]
    ye[Y_W2] = aux[A_W2]
    ye[Y_FN] = aux[A_FN]
    ye[Y_OILT] = x[X_TOIL]
    ye[Y_OILP] = aux[A_OILP]
    ye[Y_VIB0] = aux[A_VIB0]
    ye[Y_VIB1] = aux[A_VIB1]
    ye[Y_VIB2] = aux[A_VIB2]
    sm = aux[A_SMHPC]
    if aux[A_SMFAN].real < sm.real:
        sm = aux[A_SMFAN]
    ye[Y_SM] = sm
    ye[Y_BLP3] = x[X_P3]
    ye[Y_BLT3] = aux[A_T3]
    aux[A_T4] = combustor_exit_temperature(aux, flame, inl, ue, p, tb)
    # ---- discrete processes on the end-of-tick state (take effect from the next tick)
    # afterburner light-off state machine
    en = uie[UI_ABEN] == 1 and ue[U_WFAB].real > p[P_WFAB_MIN].real
    if ab == AB_OFF:
        if en:
            ab = AB_LIGHTING
            fe[F_AB_TIMER] = 0.0 * fe[F_AB_TIMER]
            zz = z_ab[ie[I_NAB] - a0]
            fe[F_AB_DELAY] = (
                p[P_AB_TREF]
                * (p[P_AB_PREF] / x[X_P6]) ** p[P_AB_NP]
                * np.exp(p[P_AB_BT] * (p[P_AB_T1REF] / aux[A_T2] - 1.0))
                * np.exp(p[P_AB_SIGMA] * zz)
            )
            ie[I_NAB] = ie[I_NAB] + 1
    elif ab == AB_LIGHTING:
        if not en:
            ab = AB_OFF
        else:
            fe[F_AB_TIMER] = fe[F_AB_TIMER] + 1.0
            if fe[F_AB_TIMER].real * dt >= fe[F_AB_DELAY].real and flt[FLT_AB_BLOCK].real < 0.5:
                ab = AB_LIT
    elif ab == AB_LIT:
        if not en:
            ab = AB_OFF
    # main burner: lean blow-out and relight
    far_lbo = p[P_FARLBO] * (p[P_PLBO] / x[X_P3]) ** p[P_NLBO]
    if flame == 1:
        # lean blow-out after the lean condition persists t_lbo (rich excursions only cap the heat release)
        lean_out = aux[A_FAR4].real < far_lbo.real or aux[A_WFL].real < p[P_WFMINFL].real
        if lean_out:
            fe[F_FLAME_TIMER] = fe[F_FLAME_TIMER] + 1.0
            if fe[F_FLAME_TIMER].real >= np.floor(p[P_TLBO].real / dt + 0.5):
                flame = 0
                fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
        else:
            fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
    else:
        light_ok = (
            uie[UI_IGN] == 1 and aux[A_FAR4].real >= p[P_FARLIGHT].real and x[X_P3].real >= p[P_P3LIGHT].real
        )
        if light_ok:
            fe[F_FLAME_TIMER] = fe[F_FLAME_TIMER] + 1.0
            if fe[F_FLAME_TIMER].real >= np.floor(p[P_TIGN].real / dt + 0.5):
                flame = 1
        else:
            fe[F_FLAME_TIMER] = 0.0 * fe[F_FLAME_TIMER]
    # surge event model (PROXY A-W1.3a-9)
    sm_trig = p[P_SMTRIG].real
    if x[X_N2].real >= flt[FLT_SM_N2].real:
        sm_trig = sm_trig + flt[FLT_SM].real  # stall-margin debit of a fault (repeat stalls)
    if surge == 0:
        if aux[A_SMHPC].real < sm_trig or aux[A_SMFAN].real < sm_trig:
            surge = 1
            k_surge = 0.0
            ie[I_NSURGE] = ie[I_NSURGE] + 1
    elif k_surge >= np.floor(p[P_SURGE_TREC].real / dt + 0.5):
        surge = 0
    fe[F_SURGE_TIMER] = 0.0 * fe[F_SURGE_TIMER] + k_surge
    # oil charge lost by a leak fault (integrated per tick; never below empty)
    if flt[FLT_OIL_RATE].real > 0.0:
        lev = flt[FLT_OIL_LEVEL] - dt * flt[FLT_OIL_RATE]
        if lev.real < 0.0:
            lev = 0.0 * lev
        flt[FLT_OIL_LEVEL] = lev
    ie[I_AB] = ab
    ie[I_FLAME] = flame
    ie[I_SURGE] = surge
    # fuel transport delay ring buffer: store this tick's metered flow
    if n_delay > 0:
        bufe[ie[I_BUFPOS]] = wf_meas
        ie[I_BUFPOS] = (ie[I_BUFPOS] + 1) % n_delay
    ie[I_TICK] = ie[I_TICK] + 1
    yie[YI_AB] = ab
    yie[YI_FLAME] = flame


@njit(**_JIT)
def engine_kernel(f, i, buf, p, tb, u, ui, z_ab, dt, n_sub, n_delay, record_aux):
    """Advance ``E`` engines by ``L = u.shape[0]`` truth ticks. Pure: returns fresh state and outputs.

    f: (E, NF) float state (dtype carries the complex step), i: (E, NI) int64, buf: (E, max(n_delay, 1)),
    p: (NP,) parameters, tb: EngineTables, u: (L, E, NU) inputs, ui: (L, E, NUI) int inputs,
    z_ab: (E, K) standard-normal light-off draws for attempts ``i[e, I_NAB] .. + K - 1``.
    Returns f, i, buf, y (L, E, NY), yi (L, E, NYI), aux (L or 1, E, NAUX).
    """
    f = f.copy()
    i = i.copy()
    buf = buf.copy()
    n_eng = f.shape[0]
    n_t = u.shape[0]
    y = np.empty((n_t, n_eng, NY), dtype=f.dtype)
    yi = np.empty((n_t, n_eng, NYI), dtype=np.int64)
    n_aux_t = n_t if record_aux else 1
    yaux = np.zeros((n_aux_t, n_eng, NAUX), dtype=f.dtype)
    x = np.empty(NX, dtype=f.dtype)
    xt = np.empty(NX, dtype=f.dtype)
    dx = np.empty(NX, dtype=f.dtype)
    dx0 = np.empty(NX, dtype=f.dtype)
    dx2 = np.empty(NX, dtype=f.dtype)
    aux = np.empty(NAUX, dtype=f.dtype)
    inl = np.empty(NINL, dtype=f.dtype)
    for e in range(n_eng):
        a0 = i[e, I_NAB]
        for k in range(n_t):
            _tick(f[e], i[e], buf[e], p, tb, u[k, e], ui[k, e], z_ab[e], a0, dt, n_sub, n_delay,
                  x, xt, dx, dx0, dx2, aux, inl, y[k, e], yi[k, e])  # fmt: skip
            if record_aux:
                for j in range(NAUX):
                    yaux[k, e, j] = aux[j]
    return f, i, buf, y, yi, yaux


@njit(**_JIT)
def deriv_point(x, ab, flame, surge, surge_timer, u_row, p, tb, wf_line):
    """dx/dt and diagnostics at one state for one engine (steady-state solver / linearisation entry point).

    ``wf_line`` < 0 means "no transport delay in effect": the combustor sees ``wfm * (1 + w_fm)``."""
    inl = np.empty(NINL, dtype=x.dtype)
    dx = np.empty(NX, dtype=x.dtype)
    aux = np.empty(NAUX, dtype=x.dtype)
    flt = np.zeros(NFLT, dtype=x.dtype)  # no fault perturbation (steady states and linearisations)
    flt[FLT_OIL_LEVEL] = 1.0
    inlet(u_row[U_TS], u_row[U_PS], u_row[U_Q], u_row[U_MACH], u_row[U_WIR], p, tb, inl)
    if wf_line.real < 0.0:
        inl[INL_WFL] = x[X_WFM] * (1.0 + u_row[U_WFM_D])
    else:
        inl[INL_WFL] = wf_line
    deriv(x, ab, flame, surge, surge_timer, inl, u_row, p, tb, dx, aux, flt)
    aux[A_T4] = combustor_exit_temperature(aux, flame, inl, u_row, p, tb)
    return dx, aux
