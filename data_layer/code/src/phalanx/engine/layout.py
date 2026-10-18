"""AD-22 flat layouts for M07: state, kernel parameter vector, per-engine input/output rows, diagnostics.

Every index constant is checked against its name list at import (drift fails loudly), as in
``core/example_kernel.py``. Units are SI throughout.
"""

from __future__ import annotations

from phalanx.core.layout import VectorLayout

# ---------------------------------------------------------------------------------------- continuous state
# integrated by the sub-stepped RK2 (Heun) scheme inside each 240 Hz truth step
X_NAMES = (
    "n1",  # LP spool speed, rad/s
    "n2",  # HP spool speed, rad/s
    "p21",  # fan-exit / bypass-duct volume total pressure, Pa
    "p3",  # HPC-exit / combustor volume total pressure, Pa
    "p45",  # HPT-LPT inter-turbine volume total pressure, Pa
    "p5",  # LPT-exit duct volume total pressure (core stream upstream of the mixer), Pa
    "p6",  # mixer / afterburner volume total pressure, Pa
    "t41",  # HPT rotor-inlet total temperature (combustor energy-storage lag), K
    "wfm",  # metered main fuel flow downstream of the FMV, kg/s
    "a8",  # nozzle throat area, m^2
    "vg1",  # fan IGV (FVG) angle, rad (positive = more closed)
    "vg2",  # HPC VSV (CVG) angle, rad (positive = more closed)
    "wfab",  # afterburner fuel actuator output, kg/s
    "tm",  # hot-section rotor metal temperature (heat soak), K
    "tc",  # HPT case/shroud metal temperature, K
    "toil",  # lube-oil bulk temperature, K
)
X = VectorLayout(X_NAMES)
(
    X_N1, X_N2, X_P21, X_P3, X_P45, X_P5, X_P6, X_T41, X_WFM, X_A8, X_VG1, X_VG2, X_WFAB, X_TM, X_TC, X_TOIL,
) = range(len(X_NAMES))  # fmt: skip
X.check(**{n: j for j, n in enumerate(X_NAMES)})
NX = len(X_NAMES)

# float state = continuous state + discrete-process timers. The timers count whole 240 Hz ticks (exact
# integers held as floats; ab_delay is in seconds): ab_timer (ticks since the light-off attempt), surge_timer
# (ticks since the surge trigger), flame_timer (ticks of persisting lean or light-off conditions)
F_TIMERS = ("ab_timer", "ab_delay", "surge_timer", "flame_timer")
F_AB_TIMER, F_AB_DELAY, F_SURGE_TIMER, F_FLAME_TIMER = NX, NX + 1, NX + 2, NX + 3
# effective fault perturbations (eng.fault_inject, AD-48.4; W2.1b): state written by the module's event
# handler from the per-mode fault parameters, read by the kernel (I6: faults change state only). Units:
# vibration multipliers and torque/bleed fractions are fractions; *_n2 thresholds rad/s; wf cap and bleed
# kg/s; the oil level is a fraction of the normal charge (integrated by the kernel), its rate 1/s
FLT_NAMES = (
    "flt_vib1",  # N1 1/rev vibration source multiplier increment (imbalance)
    "flt_vib2",  # N2 1/rev
    "flt_vibbb",  # broadband
    "flt_tq_lp",  # extra LP-spool load (fraction of the fan power: rub, bearing friction)
    "flt_tq_hp",  # extra HP-spool load (fraction of the HPC + accessory power)
    "flt_sm",  # stall-margin debit added to the surge trigger margin
    "flt_sm_n2",  # N2 (rad/s) above which the debit applies (0 = always)
    "flt_wf_cap",  # cap on the metered-fuel target (kg/s; 0 = none): partly closed shut-off valve
    "flt_bleed",  # extra bleed (kg/s): leak or over-extraction
    "flt_bleed_frac",  # extra bleed as a fraction of core flow (mis-scheduled bleed)
    "flt_ab_block",  # 1 = the afterburner cannot light (no-light)
    "flt_comb",  # combustion-efficiency loss below run speed (hung start)
    "flt_wf_bias",  # metered-fuel excess below run speed (hot start)
    "flt_run_n2",  # run speed (rad/s) below which the start faults act
    "flt_noz_leak",  # nozzle/liner leak area as a fraction of the throat (burn-through)
    "flt_oil_rate",  # oil-charge loss rate (1/s)
    "flt_oil_level",  # oil charge (fraction; integrated by the kernel)
    "flt_oil_crit",  # charge below which oil pressure falls and bearings load up (0 = inactive)
    "flt_oil_seize",  # extra HP load at an empty charge (bearing seizure progression)
    "flt_ua_loss",  # fractional loss of lube heat rejection
)
NFLT = len(FLT_NAMES)
F_NAMES = (*X_NAMES, *F_TIMERS, *FLT_NAMES)
F_FLT0 = NX + len(F_TIMERS)
(
    FLT_VIB1,
    FLT_VIB2,
    FLT_VIBBB,
    FLT_TQ_LP,
    FLT_TQ_HP,
    FLT_SM,
    FLT_SM_N2,
    FLT_WF_CAP,
    FLT_BLEED,
    FLT_BLEED_FRAC,
    FLT_AB_BLOCK,
    FLT_COMB,
    FLT_WF_BIAS,
    FLT_RUN_N2,
    FLT_NOZ_LEAK,
    FLT_OIL_RATE,
    FLT_OIL_LEVEL,
    FLT_OIL_CRIT,
    FLT_OIL_SEIZE,
    FLT_UA_LOSS,
) = range(NFLT)  # fmt: skip  (indices into the fault slice f[F_FLT0:])
NF = len(F_NAMES)
assert F_NAMES[F_FLT0 + FLT_UA_LOSS] == "flt_ua_loss"

# int state
I_NAMES = ("tick", "ab_state", "flame", "surge", "n_surge", "n_ab_attempt", "buf_pos")
I_TICK, I_AB, I_FLAME, I_SURGE, I_NSURGE, I_NAB, I_BUFPOS = range(len(I_NAMES))
NI = len(I_NAMES)

AB_OFF, AB_LIGHTING, AB_LIT = 0, 1, 2

# ---------------------------------------------------------------------------------------- per-engine inputs
U_NAMES = (
    "wf_cmd",
    "wf_ab_cmd",
    "a8_cmd",
    "vg_igv_cmd",
    "vg_vsv_cmd",
    "t_s",
    "p_s",
    "q_spec",
    "mach",
    "w_fuel_metering",
    "w_combustor_eff",
    "w_inlet_recovery",
    "w_shaft_load",
    "w_fan_face",
    "bleed_extract",
    "pto_power",
    "t_fuel",
    "h_fan_eta",
    "h_fan_flow",
    "h_hpc_eta",
    "h_hpc_flow",
    "h_hpt_eta",
    "h_hpt_flow",
    "h_lpt_eta",
    "h_lpt_flow",
    "h_comb_eta",
    "h_nozzle_area",
)
(
    U_WF, U_WFAB, U_A8, U_VG1, U_VG2, U_TS, U_PS, U_Q, U_MACH, U_WFM_D, U_WCE, U_WIR, U_WSL, U_WFF, U_BLEED,
    U_PTO, U_TFUEL, U_H0,
) = range(18)  # fmt: skip
NU = len(U_NAMES)
N_HEALTH = 10
assert U_H0 + N_HEALTH == NU
UI_NAMES = ("ignition", "ab_enable")
UI_IGN, UI_ABEN = 0, 1
NUI = 2

# health.engine column order (W1_interfaces.md M10)
HEALTH_NAMES = (
    "fan_eta", "fan_flow", "hpc_eta", "hpc_flow", "hpt_eta", "hpt_flow", "lpt_eta", "lpt_flow", "comb_eta",
    "nozzle_area",
)  # fmt: skip
# env.w_engine column order (W1_interfaces.md M03, AD-32, AD-46)
W_ENGINE_NAMES = ("fuel_metering", "combustor_eff", "inlet_recovery", "shaft_load", "fan_face")
N_W_ENGINE = len(W_ENGINE_NAMES)
assert U_WFM_D + N_W_ENGINE == U_BLEED
# PTO / starter power -> torque conversion floor (rad/s): T = P / (N2 + PTO_W_FLOOR), the M09 start-drive
# convention (``utilities/jfs.py``: P = min(P_avail, T_peak (w + w_floor)), w_floor = 1 rad/s)
PTO_W_FLOOR = 1.0

# ---------------------------------------------------------------------------------------- outputs (ports)
Y_NAMES = (
    "n1", "n2", "t2", "t25", "t3", "t5", "p2", "ps3", "p5", "wf", "wf_ab", "a8", "vg_igv", "vg_vsv", "w2",
    "thrust", "oil_t", "oil_p", "vib_n1", "vib_n2", "vib_bb", "stall_margin", "bleed_p3", "bleed_t3",
)  # fmt: skip
Y = VectorLayout(Y_NAMES)
(
    Y_N1, Y_N2, Y_T2, Y_T25, Y_T3, Y_T5, Y_P2, Y_PS3, Y_P5, Y_WF, Y_WFAB, Y_A8, Y_VG1, Y_VG2, Y_W2, Y_FN,
    Y_OILT, Y_OILP, Y_VIB0, Y_VIB1, Y_VIB2, Y_SM, Y_BLP3, Y_BLT3,
) = range(len(Y_NAMES))  # fmt: skip
NY = len(Y_NAMES)
YI_NAMES = ("ab_state", "flame_state")
YI_AB, YI_FLAME = 0, 1
NYI = 2
N_VIB_BANDS = 3

# ---------------------------------------------------------------------------------------- diagnostics (aux)
AUX_NAMES = (
    "t2", "p2", "w2", "w2c", "n1c", "t21", "pr_fan", "eta_fan", "sm_fan", "pw_fan",
    "t25", "p25", "w25", "n2c", "pr_hpc", "eta_hpc", "sm_hpc", "beyond_hpc", "t3", "ps3", "pw_hpc",
    "wbleed", "wrot", "p4", "w41", "t4", "far4", "t41_ad", "pr_hpt", "eta_hpt", "pw_hpt", "t45", "wlpt",
    "pr_lpt", "eta_lpt", "pw_lpt", "t5", "p5", "w5mix", "w13", "bpr", "t6", "t7", "p7", "w8", "fg", "fn",
    "wf_line",
    "q_soak", "clearance", "oil_p", "vib_n1", "vib_n2", "vib_bb", "v0", "pw_ext", "ab_heat", "lam_est",
)  # fmt: skip
AUX = VectorLayout(AUX_NAMES)
A = {n: j for j, n in enumerate(AUX_NAMES)}
NAUX = len(AUX_NAMES)
(
    A_T2, A_P2, A_W2, A_W2C, A_N1C, A_T21, A_PRFAN, A_ETAFAN, A_SMFAN, A_PWFAN,
    A_T25, A_P25, A_W25, A_N2C, A_PRHPC, A_ETAHPC, A_SMHPC, A_BEYOND, A_T3, A_PS3, A_PWHPC,
    A_WBLEED, A_WROT, A_P4, A_W41, A_T4, A_FAR4, A_T41AD, A_PRHPT, A_ETAHPT, A_PWHPT, A_T45, A_WLPT,
    A_PRLPT, A_ETALPT, A_PWLPT, A_T5, A_P5, A_W5MIX, A_W13, A_BPR, A_T6, A_T7, A_P7, A_W8, A_FG, A_FN, A_WFL,
    A_QSOAK, A_CLEAR, A_OILP, A_VIB0, A_VIB1, A_VIB2, A_V0, A_PWEXT, A_ABHEAT, A_LAM,
) = range(NAUX)  # fmt: skip
AUX.check(**A)

# inlet work row (computed once per tick per engine)
INL_NAMES = ("t2", "p2", "war", "v0", "p_s", "t_s", "wf_line")
INL_T2, INL_P2, INL_WAR, INL_V0, INL_PS, INL_TS, INL_WFL = range(len(INL_NAMES))
NINL = len(INL_NAMES)

# ---------------------------------------------------------------------------------------- kernel parameters
P_NAMES = (
    # map scalers (derived at the design point by design.py)
    "s_nc_fan", "s_pr_fan", "s_wc_fan", "s_eff_fan",
    "s_nc_hpc", "s_pr_hpc", "s_wc_hpc", "s_eff_hpc",
    "s_np_hpt", "s_pr_hpt", "s_wp_hpt", "s_eff_hpt",
    "s_np_lpt", "s_pr_lpt", "s_wp_lpt", "s_eff_lpt",
    # derived design references
    "k13", "eps13", "a3_eff", "c_ngv", "n1_des", "n2_des", "n1c_des_rpm", "n2c_des_rpm", "w2_des", "w41_des",
    "wc3_des", "wc6_des", "wf_des", "tm_ref", "tc_ref", "k5", "eps5", "r6_mix", "f_stoich",
    # duct and component specifications
    "dp_core_duct", "dp_burner", "dp_ab_dry", "k_rayleigh", "eta_burner", "lhv", "eta_ab",
    "eta_mech", "f_rot", "cfg", "cd8", "pr_choke_hpt", "pr_choke_lpt", "gamma_turb_eq", "stall_slope",
    "p_acc_des", "mil_e_5008b_a", "mil_e_5008b_b",
    # dynamics
    "v21", "v3", "v45", "v5", "v6", "i_lp", "i_hp", "tau_comb",
    # actuators
    "tau_fmv", "tau_a8", "a8_rate", "a8_min", "a8_max", "tau_vg", "vg_rate", "vg_min", "vg_max", "tau_wfab",
    # variable-geometry off-schedule sensitivities
    "k_w_fvg", "k_e_fvg", "k_w_cvg", "k_e_cvg", "vg_dev_sat",
    # heat soak and tip clearance
    "c_metal", "ha_metal", "tau_case", "c_case", "g_clr_case", "g_clr_metal", "g_clr_speed", "k_eta_clr",
    # surge
    "sm_trigger", "surge_c_min", "surge_t_rec", "surge_eff",
    # afterburner light-off
    "ab_t_ref", "ab_p_ref", "ab_n_p", "ab_b_t", "ab_t1_ref", "ab_sigma", "wfab_min",
    # main-burner flame
    "far_lbo_ref", "p_lbo_ref", "n_lbo", "t_lbo", "far_light_min", "p3_light_min", "t_ign", "wf_min_flame",
    # oil
    "c_oil", "q_oil_ref", "ua_oil_air", "ua_oil_fuel", "dt_fuel_sink", "p_oil_reg", "n2_oil_k", "oil_visc_k",
    "t_oil_ref",
    # vibration source
    "vib_k_n1", "vib_k_n2", "vib_k_bb", "vib_exp",
    # numerics: stiffness-based sub-step count and error-controlled refinement
    "int_tol", "n_sub_max", "stab_hlam",
    # fan-face distortion process disturbance (AD-46): efficiency change per unit flow-capacity change
    "k_eta_fan_face",
)  # fmt: skip
P = VectorLayout(P_NAMES)
PI = {n: j for j, n in enumerate(P_NAMES)}
NP = len(P_NAMES)
(
    P_SNC_FAN, P_SPR_FAN, P_SWC_FAN, P_SEFF_FAN,
    P_SNC_HPC, P_SPR_HPC, P_SWC_HPC, P_SEFF_HPC,
    P_SNP_HPT, P_SPR_HPT, P_SWP_HPT, P_SEFF_HPT,
    P_SNP_LPT, P_SPR_LPT, P_SWP_LPT, P_SEFF_LPT,
    P_K13, P_EPS13, P_A3, P_CNGV, P_N1DES, P_N2DES, P_N1CDES, P_N2CDES, P_W2DES, P_W41DES,
    P_WC3DES, P_WC6DES, P_WFDES, P_TMREF, P_TCREF, P_K5, P_EPS5, P_R6MIX, P_FST,
    P_DPCD, P_DPB, P_DPAB, P_KRAY, P_ETAB, P_LHV, P_ETAAB,
    P_ETAM, P_FROT, P_CFG, P_CD8, P_PRCH_HPT, P_PRCH_LPT, P_GTURB, P_STALL_SLOPE,
    P_PACC, P_ME_A, P_ME_B,
    P_V21, P_V3, P_V45, P_V5, P_V6, P_ILP, P_IHP, P_TAUCOMB,
    P_TAUFMV, P_TAUA8, P_A8RATE, P_A8MIN, P_A8MAX, P_TAUVG, P_VGRATE, P_VGMIN, P_VGMAX, P_TAUWFAB,
    P_KWFVG, P_KEFVG, P_KWCVG, P_KECVG, P_VGSAT,
    P_CMET, P_HAMET, P_TAUCASE, P_CCASE, P_GCLR_C, P_GCLR_M, P_GCLR_W, P_KETACLR,
    P_SMTRIG, P_SURGE_CMIN, P_SURGE_TREC, P_SURGE_EFF,
    P_AB_TREF, P_AB_PREF, P_AB_NP, P_AB_BT, P_AB_T1REF, P_AB_SIGMA, P_WFAB_MIN,
    P_FARLBO, P_PLBO, P_NLBO, P_TLBO, P_FARLIGHT, P_P3LIGHT, P_TIGN, P_WFMINFL,
    P_COIL, P_QOIL, P_UAOIL_AIR, P_UAOIL_FUEL, P_DTFUEL, P_POILREG, P_N2OILK, P_OILVISC, P_TOILREF,
    P_VIBK1, P_VIBK2, P_VIBK3, P_VIBEXP,
    P_INTTOL, P_NSUBMAX, P_STAB,
    P_KEFF,
) = range(NP)  # fmt: skip
P.check(**PI)

# derived (computed by design.py, not read from the parameter file)
DERIVED_P = (
    "s_nc_fan", "s_pr_fan", "s_wc_fan", "s_eff_fan", "s_nc_hpc", "s_pr_hpc", "s_wc_hpc", "s_eff_hpc",
    "s_np_hpt", "s_pr_hpt", "s_wp_hpt", "s_eff_hpt", "s_np_lpt", "s_pr_lpt", "s_wp_lpt", "s_eff_lpt",
    "k13", "eps13", "a3_eff", "c_ngv", "n1_des", "n2_des", "n1c_des_rpm", "n2c_des_rpm", "w2_des", "w41_des",
    "wc3_des", "wc6_des", "wf_des", "tm_ref", "tc_ref", "k5", "eps5", "r6_mix", "a8_min", "a8_max",
    "a8_rate", "f_stoich",
)  # fmt: skip
