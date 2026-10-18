"""AD-22 flat layouts for M09: state vectors, kernel inputs/outputs, index maps behind the util.* ports.

Index maps (published to neighbours through ``ports.py`` and the README):

- tanks ``k`` (``util.fuel_mass``): F1, F1A, F2 (collector/feed), wing L, wing R, drop tank centreline,
  inboard L, inboard R (dictionary FUEL.QTY.TANK.<name> names; the order M12 assumed, A-W1.6-16).
  F1/F1A/F2 and the wing tanks are DIRECT names (ADA); the split and the drop-tank stations are
  [ASSUMPTION] (A-W0.3-4).
- buses (``util.bus_v``): DC main, DC essential, DC emergency (28 V), AC main (V rms, 115 V 400 Hz)
  (HAL master box bus list [DIRECT-part]; allocation [ASSUMPTION]; DC order = ELEC.DCBUS.V.{MAIN,
  ESSENTIAL, EMERGENCY}).
- ECS points (``util.ecs_t``/``util.ecs_p``): bleed manifold, PHX outlet, ACM turbine outlet (cabin supply),
  cockpit, avionics bay. Pressures are absolute (dictionary ECS.BLEED_P/ECS.CABIN_P are absolute).
- hydraulic systems ``h`` = 2; pressures ``util.hyd_p`` are **gauge** (dictionary HYD.SYSn.P is gauge).
- gear legs ``g`` (``af.wow``): nose, left main, right main [ASSUMPTION, to be confirmed by M06].
- wheels (``util.brake_*``, ``util.tyre_wear``, ``af.wheel_speed``): left main, right main.

Every name -> index constant is checked at import against the name tuples (a swapped or missing constant
fails the import, not a run).
"""

from __future__ import annotations

from phalanx.core.layout import ParamLayout, StateLayout

N_HYD = 2
N_TANKS = 8
N_BUS = 4
N_ECS = 5
N_GEAR = 3
N_WHEEL = 2
N_STORE = 5

TANKS = (
    "F1",
    "F1A",
    "F2",
    "WING_L",
    "WING_R",
    "DT_CL",
    "DT_IB_L",
    "DT_IB_R",
)  # dictionary FUEL.QTY.TANK.<name>
T_F1, T_F1A, T_F2, T_WL, T_WR, T_DTC, T_DTL, T_DTR = range(N_TANKS)
BUSES = (
    "DC_MAIN",
    "DC_ESS",
    "DC_EMERG",
    "AC_MAIN",
)  # dictionary ELEC.DCBUS.V.{MAIN,ESSENTIAL,EMERGENCY}, then AC
B_DCM, B_ESS, B_EMG, B_AC = range(N_BUS)
ECS_POINTS = ("BLEED", "PHX_OUT", "TURBINE_OUT", "COCKPIT", "AVIONICS_BAY")
E_BLEED, E_PHX, E_TURB, E_CAB, E_AV = range(N_ECS)
GEAR = ("NOSE", "LEFT_MAIN", "RIGHT_MAIN")
STORES = ("INBOARD_L", "INBOARD_R", "OUTBOARD_L", "OUTBOARD_R", "CENTRELINE")

# health.utility index map consumed by M09 (proposed to M10, which publishes the authoritative map).
# All entries are dimensionless; 0 = nominal build.
HEALTH_INDEX = (
    "hyd_pump_leak_0",  # fractional excess pump internal (case-drain) leakage conductance, >= 0
    "hyd_pump_leak_1",
    "hyd_sys_leak_0",  # fractional excess system internal leakage conductance, >= 0
    "hyd_sys_leak_1",
    "hyd_ext_leak_0",  # external (overboard) leak conductance, as a fraction of rated pump flow at p_nom
    "hyd_ext_leak_1",
    "hyd_comp_drift_0",  # compensator set-point drift, fraction of p_nom (signed)
    "hyd_comp_drift_1",
    "hyd_filter_load_0",  # pressure-filter loading, fraction of capacity in [0, 1)
    "hyd_filter_load_1",
    "hyd_precharge_loss_0",  # accumulator N2 precharge loss, fraction in [0, 1)
    "hyd_precharge_loss_1",
    "ecs_hx_fouling",  # PHX fouling factor in [0, 1] (UA multiplier 1 - k*fouling)
    "ecs_cabin_leak",  # fractional excess canopy-seal/cabin leakage conductance, >= 0
    "batt_fade",  # battery capacity fade, fraction in [0, 1)
    "jfs_power_loss",  # JFS gas-generator power loss, fraction in [0, 1)
    "jfs_drag_excess",  # JFS spool drag excess, fractional, >= 0
    "amagb_wear",  # AMAGB gear/bearing loss excess, fractional, >= 0
    "brake_wear_0",  # carbon heat-sink wear at sortie start, fraction of life in [0, 1]
    "brake_wear_1",
    "tyre_wear_0",  # main-tyre tread wear at sortie start, fraction of life in [0, 1]
    "tyre_wear_1",
    "fuel_xfer_loss",  # transfer-pump capacity loss, fraction in [0, 1)
)
N_HEALTH = len(HEALTH_INDEX)
(
    H_PUMP_LEAK,
    _H1,
    H_SYS_LEAK,
    _H3,
    H_EXT_LEAK,
    _H5,
    H_COMP_DRIFT,
    _H7,
    H_FILTER,
    _H9,
    H_PRECHARGE,
    _H11,
    H_HX_FOUL,
    H_CAB_LEAK,
    H_BATT_FADE,
    H_JFS_PWR,
    H_JFS_DRAG,
    H_AMAGB,
    H_BRAKE_WEAR,
    _H19,
    H_TYRE_WEAR,
    _H21,
    H_XFER_LOSS,
) = range(N_HEALTH)


def _expand(blocks: tuple[tuple[str, int], ...]) -> tuple[tuple[str, ...], dict[str, int]]:
    names: list[str] = []
    offsets: dict[str, int] = {}
    for base, n in blocks:
        offsets[base] = len(names)
        names.extend([base] if n == 1 else [f"{base}_{j}" for j in range(n)])
    return tuple(names), offsets


def _check(offsets: dict[str, int], prefix: str, ns: dict) -> None:
    for base, off in offsets.items():
        const = ns.get(f"{prefix}{base.upper()}")
        if const != off:
            raise AssertionError(
                f"layout constant {prefix}{base.upper()}={const} but block {base!r} is at {off}"
            )


# ---------------------------------------------------------------------------------------- float state
_F_BLOCKS = (
    ("hyd_p", N_HYD),  # gauge pressure, Pa
    ("hyd_x", N_HYD),  # pump displacement (swash) fraction, 1
    ("hyd_t", N_HYD),  # fluid temperature, K
    ("hyd_vres", N_HYD),  # bootstrap reservoir fluid volume, m^3
    ("hyd_vext", N_HYD),  # cumulative external leak (fluid lost), m^3
    ("hyd_ein", N_HYD),  # cumulative heat into fluid (pump shaft power), J  [audit]
    ("hyd_eout", N_HYD),  # cumulative heat rejected (HX + ambient), J  [audit]
    ("gb_t", 1),  # AMAGB oil temperature, K
    ("fuel_m", N_TANKS),  # fuel mass per tank, kg
    ("fuel_t", 1),  # lumped tank fuel temperature, K
    ("slosh_s", 1),  # fuel-surface slope (pitch plane, + = fuel aft), 1
    ("slosh_sd", 1),  # slope rate, 1/s
    ("fuel_burn", 1),  # cumulative fuel delivered to the engine(s), kg  [audit]
    ("fuel_unmet", 1),  # cumulative engine demand not met (feed tank empty), kg  [audit]
    ("fuel_refuel", 1),  # cumulative fuel added by refuel events, kg  [audit]
    ("batt_soc", 1),  # battery state of charge (of faded capacity), 1
    ("batt_vp", 1),  # battery polarisation voltage (1-RC branch), V
    ("batt_t", 1),  # battery temperature, K
    ("batt_v", 1),  # battery terminal voltage (last tick), V
    ("batt_q", 1),  # cumulative battery discharge charge, C  [audit]
    ("ecs_tcv", 1),  # TCV hot-bypass fraction, 1
    ("ecs_tphx", 1),  # PHX outlet temperature (duct-lagged), K
    ("ecs_tcab", 1),  # cockpit temperature, K
    ("ecs_tav", 1),  # avionics-bay temperature, K
    ("ecs_pcab", 1),  # cockpit absolute pressure, Pa
    ("ecs_mbleed", 1),  # cumulative bleed extracted, kg  [audit]
    ("ecs_msup", 1),  # cumulative bleed delivered to subscribers, kg  [audit]
    ("jfs_n", 1),  # JFS gas-generator speed, fraction of rated
    ("jfs_egt", 1),  # JFS exhaust gas temperature, K
    ("jfs_oilt", 1),  # JFS oil temperature, K
    ("jfs_oilq", 1),  # JFS oil quantity, m^3
    ("jfs_tmode", 1),  # time in current JFS mode, s
    ("brk_t", N_WHEEL),  # brake heat-sink temperature, K
    ("brk_dw", N_WHEEL),  # brake wear accrued this sortie, fraction of life
    ("brk_ein", N_WHEEL),  # cumulative brake energy absorbed, J  [audit]
    ("brk_eout", N_WHEEL),  # cumulative heat-sink cooling, J  [audit]
    ("tyre_dw", N_WHEEL),  # tyre wear accrued this sortie, fraction of life
    ("bay_t", 1),  # engine-bay (fire zone) air temperature, K
    ("last_tas", 1),  # true airspeed at the last tick, m/s (for event-time checks)
    ("store_m", N_STORE),  # store masses at stations, kg (configuration; released by events)
)
F_NAMES, _F_OFF = _expand(_F_BLOCKS)
(
    F_HYD_P,
    F_HYD_X,
    F_HYD_T,
    F_HYD_VRES,
    F_HYD_VEXT,
    F_HYD_EIN,
    F_HYD_EOUT,
) = (0, 2, 4, 6, 8, 10, 12)
F_GB_T = 14
F_FUEL_M = 15
F_FUEL_T = 23
F_SLOSH_S = 24
F_SLOSH_SD = 25
F_FUEL_BURN = 26
F_FUEL_UNMET = 27
F_FUEL_REFUEL = 28
F_BATT_SOC = 29
F_BATT_VP = 30
F_BATT_T = 31
F_BATT_V = 32
F_BATT_Q = 33
F_ECS_TCV = 34
F_ECS_TPHX = 35
F_ECS_TCAB = 36
F_ECS_TAV = 37
F_ECS_PCAB = 38
F_ECS_MBLEED = 39
F_ECS_MSUP = 40
F_JFS_N = 41
F_JFS_EGT = 42
F_JFS_OILT = 43
F_JFS_OILQ = 44
F_JFS_TMODE = 45
F_BRK_T = 46
F_BRK_DW = 48
F_BRK_EIN = 50
F_BRK_EOUT = 52
F_TYRE_DW = 54
F_BAY_T = 56
F_LAST_TAS = 57
F_STORE_M = 58
_check(_F_OFF, "F_", globals())

# ---------------------------------------------------------------------------------------- int state
_I_BLOCKS = (
    ("tick", 1),  # ticks since init (absolute draw-index base)
    ("gen_on", 1),  # main AC generator online
    ("gen_fault", 1),  # main generator internal fault latched (M11 event)
    ("bk_on", 1),  # 5 kW DC backup generator online
    ("bk_fault", 1),  # backup generator fault latched
    ("xfer_left", 1),  # remaining interruption ticks on the essential/emergency buses (<= 50 ms)
    ("ess_src", 1),  # essential-bus source: 0 none, 1 TRU (main gen), 2 DC backup, 3 battery
    ("jfs_mode", 1),  # JFS mode (see jfs.py JFS_* codes)
    ("jfs_attempt", 1),  # start attempts this sortie (ignition draw index)
    ("jfs_consec", 1),  # consecutive successful starts
    ("jfs_outcome", 1),  # last start outcome (jfs.py OUT_* codes)
    ("jfs_ok", 1),  # successful starts this sortie
    ("jfs_fail", 1),  # failed starts this sortie
    ("jfs_variant", 1),  # 1 = GTSU-110 M1, 2 = GTSU-110 M2 (configuration)
    ("jfs_lit", 1),  # JFS combustor lit
    ("jfs_drawn", 1),  # ignition draw consumed for the current attempt
    ("f1a_mod", 1),  # F1A pick-up/vent modification embodied (configuration; 0 = pre-mod)
    ("xfer_grp", 1),  # active transfer source group (0 = none)
    ("brk_on", N_WHEEL),  # brake application in progress
    ("brk_apps", N_WHEEL),  # brake applications this sortie
    ("wow_prev", 1),  # main-gear weight-on-wheels at the previous tick
    ("landings", 1),  # touchdowns this sortie
    ("tyre_burst", N_WHEEL),  # tyre burst latched
    ("chute", 1),  # brake chute: 0 stowed, 1 streamed, 2 jettisoned, 3 failed
    ("chute_n", 1),  # streamings this sortie
    ("chute_over", 1),  # streamings above the normal deploy limit this sortie
    ("fire_on", 1),  # fire present in the engine bay (truth)
    ("fire_warn", 1),  # detector loop alarm (physical detector output)
    ("fire_det", 1),  # detector loop condition: 0 ok, 1 open (cannot alarm), 2 short (always alarms)
    ("ext_charged", 1),  # extinguisher bottle charged
    ("fire_n", 1),  # fire events this sortie (extinguish draw index)
)
I_NAMES, _I_OFF = _expand(_I_BLOCKS)
(
    I_TICK,
    I_GEN_ON,
    I_GEN_FAULT,
    I_BK_ON,
    I_BK_FAULT,
    I_XFER_LEFT,
    I_ESS_SRC,
    I_JFS_MODE,
    I_JFS_ATTEMPT,
    I_JFS_CONSEC,
    I_JFS_OUTCOME,
    I_JFS_OK,
    I_JFS_FAIL,
    I_JFS_VARIANT,
    I_JFS_LIT,
    I_JFS_DRAWN,
    I_F1A_MOD,
    I_XFER_GRP,
) = range(18)
I_BRK_ON = 18
I_BRK_APPS = 20
I_WOW_PREV = 22
I_LANDINGS = 23
I_TYRE_BURST = 24
I_CHUTE = 26
I_CHUTE_N = 27
I_CHUTE_OVER = 28
I_FIRE_ON = 29
I_FIRE_WARN = 30
I_FIRE_DET = 31
I_EXT_CHARGED = 32
I_FIRE_N = 33
_check(_I_OFF, "I_", globals())

STATE = StateLayout("utilities.m09", 1, floats=F_NAMES, ints=I_NAMES)
NF = len(F_NAMES)
NI = len(I_NAMES)

# ---------------------------------------------------------------------------------------- kernel inputs
# Fixed columns of the packed input block u[L, NU_FIXED + 6 * n_engines] (float64; discretes as 0/1).
_U_BLOCKS = (
    ("hyd_dem", N_HYD),  # fcs.hyd_flow_demand, m^3/s
    ("w_hyd", N_HYD),  # env.w_hyd, m^3/s
    ("fspec", 3),  # af.f_spec_body, m/s^2 (body x fwd, y right, z down)
    ("tas", 1),  # af.tas, m/s
    ("mach", 1),  # af.mach, 1
    ("wow", N_GEAR),  # af.wow, 0/1
    ("wheel", N_WHEEL),  # af.wheel_speed, rad/s
    ("pbrk", N_WHEEL),  # af.brake_energy_rate, W
    ("t_s", 1),  # env.t_s, K
    ("p_s", 1),  # env.p_s, Pa
    ("rho", 1),  # env.rho, kg/m^3
    ("health", N_HEALTH),  # health.utility, 1
)
U_NAMES, _U_OFF = _expand(_U_BLOCKS)
U_HYD_DEM = 0
U_W_HYD = 2
U_FSPEC = 4
U_TAS = 7
U_MACH = 8
U_WOW = 9
U_WHEEL = 12
U_PBRK = 14
U_T_S = 16
U_P_S = 17
U_RHO = 18
U_HEALTH = 19
_check(_U_OFF, "U_", globals())
NU_FIXED = len(U_NAMES)
# Per-engine blocks follow the fixed part: column = NU_FIXED + block * n_engines + e.
UE_N2, UE_P3, UE_T3, UE_WF, UE_WFAB, UE_WBP = range(6)
NUE = 6

# ---------------------------------------------------------------------------------------- kernel outputs
_O_BLOCKS = (
    ("hyd_p", N_HYD),
    ("hyd_dp", N_HYD),
    ("hyd_t", N_HYD),
    ("fuel_m", N_TANKS),
    ("mass", 1),
    ("cg", 3),
    ("inertia", 9),
    ("bus_v", N_BUS),
    ("batt_soc", 1),
    ("ecs_t", N_ECS),
    ("ecs_p", N_ECS),
    ("brk_t", N_WHEEL),
    ("brk_w", N_WHEEL),
    ("tyre_w", N_WHEEL),
    ("brk_p", N_WHEEL),
    ("hyd_lvl", N_HYD),
    ("amagb_w", 1),
    ("batt_ah", 1),
    ("cab_alt", 1),
)
O_NAMES, _O_OFF = _expand(_O_BLOCKS)
O_HYD_P = 0
O_HYD_DP = 2
O_HYD_T = 4
O_FUEL_M = 6
O_MASS = 14
O_CG = 15
O_INERTIA = 18
O_BUS_V = 27
O_BATT_SOC = 31
O_ECS_T = 32
O_ECS_P = 37
O_BRK_T = 42
O_BRK_W = 44
O_TYRE_W = 46
O_BRK_P = 48
O_HYD_LVL = 50
O_AMAGB_W = 52
O_BATT_AH = 53
O_CAB_ALT = 54
_check(_O_OFF, "O_", globals())
NO_FIXED = len(O_NAMES)
OE_BLEED, OE_PTO, OE_FUEL_IN = range(3)  # per-engine output blocks: column = NO_FIXED + block * ne + e
NOE = 3
OI_GEN_ON, OI_JFS, OI_PROBE_HEAT, OI_GEN_OUT, OI_BATT_LOW, OI_BK_BITE, OI_CHUTE = range(7)
NOI = 7


# ---------------------------------------------------------------------------------------- parameters
# Scalar kernel parameters (flat float64 vector, AD-22). Values, units, tags and sources: configs/tejas/
# params/M09.yaml. The tank table (configs/tejas/params/M09/tanks.csv) is appended after the scalars.
P_NAMES = (
    # physical constants
    "g0",
    "r_air",
    "gamma_air",
    "cp_air",
    # AMAGB / PTO
    "pto_ratio",
    "pto_rated_speed",
    "pto_torque_peak",
    "gb_loss_rated",
    "gb_heat_cap",
    "gb_ua",
    "gb_eff",
    # hydraulics
    "hyd_p_nom",
    "hyd_p_ret",
    "hyd_dp_band",
    "hyd_q_rated",
    "hyd_tau_swash",
    "hyd_eta_v",
    "hyd_eta_hm",
    "hyd_q_leak_int",
    "hyd_visc_b",
    "hyd_t_ref",
    "hyd_beta",
    "hyd_v_line",
    "hyd_acc_v",
    "hyd_acc_pre",
    "hyd_acc_n",
    "hyd_relief_crack",
    "hyd_relief_full",
    "hyd_filter_dp",
    "hyd_filter_exp",
    "hyd_dp_starve",
    "hyd_res_v",
    "hyd_rho",
    "hyd_cp",
    "hyd_alpha_v",
    "hyd_v_total",
    "hyd_c_metal",
    "hyd_ua_amb",
    "hyd_hx_ua",
    "hyd_q_hx",
    # fuel
    "fuel_rho_15",
    "fuel_alpha",
    "fuel_cp",
    "fuel_c_struct",
    "fuel_ua_skin",
    "fuel_q_xfer",
    "fuel_tau_xfer",
    "fuel_fill_target",
    "fuel_tau_ic",
    "fuel_pickup_band",
    "fuel_f1a_pickup_mod",
    "fuel_residual",
    "slosh_omega",
    "slosh_zeta",
    "slosh_g_min",
    "slosh_s_max",
    # mass properties
    "mp_m_ref",
    "mp_ixx",
    "mp_iyy",
    "mp_izz",
    "mp_ixz",
    "mp_ixy",
    "mp_iyz",
    "mp_m_oe",
    "dt_dry_mass_inboard",
    "dt_dry_mass_centre",
    # electrical
    "gen_cutin",
    "gen_dropout",
    "bk_cutin",
    "bk_dropout",
    "ac_v_nom",
    "ac_v_droop",
    "gen_eff",
    "gen_noload",
    "tru_v_nl",
    "tru_r",
    "tru_eff",
    "bk_v_nl",
    "bk_r",
    "bk_rating",
    "bk_eff",
    "batt_cap_ah",
    "batt_ocv_full",
    "batt_ocv_empty",
    "batt_r0",
    "batt_rp",
    "batt_tau_p",
    "batt_r_tcoef",
    "batt_t_ref",
    "batt_i_charge",
    "batt_heat_cap",
    "batt_ua",
    "load_ac_ground",
    "load_ac_air",
    "load_dcm_ground",
    "load_dcm_air",
    "load_ess",
    "load_emerg",
    "load_heater",
    "load_heater_t",
    "av_heat_frac",
    # ECS
    "ecs_m_set",
    "ecs_cda",
    "ecs_m_aux",
    "ecs_phx_ua",
    "ecs_foul_k",
    "ecs_ram_area",
    "ecs_m_ram_ground",
    "ecs_phx_dp",
    "ecs_eta_t",
    "ecs_tau_duct",
    "ecs_p_cab_iso",
    "ecs_dp_max",
    "ecs_dpdt_max",
    "ecs_tau_cab_p",
    "ecs_leak_frac",
    "ecs_f_cab",
    "ecs_c_cab",
    "ecs_ua_cab",
    "ecs_q_cab",
    "ecs_c_av",
    "ecs_ua_av",
    "ecs_t_set",
    "ecs_ki",
    "ecs_stroke",
    # JFS
    "jfs_p_rated",
    "jfs_e_rated",
    "jfs_ke",
    "jfs_rm",
    "jfs_c_visc",
    "jfs_visc_exp",
    "jfs_oil_b",
    "jfs_c_aero",
    "jfs_n_lo",
    "jfs_n_sa",
    "jfs_n_on",
    "jfs_p_gg",
    "jfs_theta_exp",
    "jfs_p_ign",
    "jfs_ign_alt",
    "jfs_t_crank",
    "jfs_t_accel",
    "jfs_t_engine",
    "jfs_n2_cutout",
    "jfs_m1_drag",
    "jfs_m1_sched",
    "jfs_oil_use_m1",
    "jfs_oil_use_m2",
    "jfs_egt_rise",
    "jfs_tau_egt",
    "jfs_oil_heat",
    "jfs_tau_oil",
    "n2_100pct",
    # brakes, tyres, chute
    "brk_m_hs",
    "brk_cp",
    "brk_mass_loss",
    "brk_tau_cool",
    "brk_p_on",
    "brk_p_off",
    "brk_w_app",
    "brk_w_energy",
    "brk_t_ox",
    "brk_k_ox",
    "tyre_r",
    "tyre_w_td",
    "tyre_m_ref",
    "tyre_v_ref",
    "tyre_w_brake",
    "tyre_w_skid",
    "tyre_mu_skid",
    "chute_v_normal",
    "chute_v_emerg",
    # fire
    "bay_heat_cap",
    "bay_ua_case",
    "bay_vent_area",
    "bay_m_vent_ground",
    "fire_q",
    "fire_t_alarm",
    "fire_p_ext",
    "load_heater_ramp",
    "brk_ox_scale",
    "skid_v_min",
    "skid_slip",
    "td_v_min",
    "jfs_gov_tau",
    "jfs_w_floor",
    "jfs_rated_speed",
    "batt_r_soc",
    "load_v_ref",
    "hyd_acc_t_charge",
    "isa_t0",
    "isa_lapse",
    "isa_p0",
    "brk_torque_gain",
    "brk_p_max",
    "load_probe_heat",
    "batt_low_warn_ah",
)
NP_SCALAR = len(P_NAMES)
PARAMS = ParamLayout(P_NAMES)

# Explicit constants (Numba reads module globals as compile-time constants). The guard below checks that
# every constant P_<NAME> equals the position of <name> in P_NAMES, so a swap fails at import.
(
    P_G0,
    P_R_AIR,
    P_GAMMA_AIR,
    P_CP_AIR,
    P_PTO_RATIO,
    P_PTO_RATED_SPEED,
    P_PTO_TORQUE_PEAK,
    P_GB_LOSS_RATED,
    P_GB_HEAT_CAP,
    P_GB_UA,
    P_GB_EFF,
    P_HYD_P_NOM,
    P_HYD_P_RET,
    P_HYD_DP_BAND,
    P_HYD_Q_RATED,
    P_HYD_TAU_SWASH,
    P_HYD_ETA_V,
    P_HYD_ETA_HM,
    P_HYD_Q_LEAK_INT,
    P_HYD_VISC_B,
    P_HYD_T_REF,
    P_HYD_BETA,
    P_HYD_V_LINE,
    P_HYD_ACC_V,
    P_HYD_ACC_PRE,
    P_HYD_ACC_N,
    P_HYD_RELIEF_CRACK,
    P_HYD_RELIEF_FULL,
    P_HYD_FILTER_DP,
    P_HYD_FILTER_EXP,
    P_HYD_DP_STARVE,
    P_HYD_RES_V,
    P_HYD_RHO,
    P_HYD_CP,
    P_HYD_ALPHA_V,
    P_HYD_V_TOTAL,
    P_HYD_C_METAL,
    P_HYD_UA_AMB,
    P_HYD_HX_UA,
    P_HYD_Q_HX,
    P_FUEL_RHO_15,
    P_FUEL_ALPHA,
    P_FUEL_CP,
    P_FUEL_C_STRUCT,
    P_FUEL_UA_SKIN,
    P_FUEL_Q_XFER,
    P_FUEL_TAU_XFER,
    P_FUEL_FILL_TARGET,
    P_FUEL_TAU_IC,
    P_FUEL_PICKUP_BAND,
    P_FUEL_F1A_PICKUP_MOD,
    P_FUEL_RESIDUAL,
    P_SLOSH_OMEGA,
    P_SLOSH_ZETA,
    P_SLOSH_G_MIN,
    P_SLOSH_S_MAX,
    P_MP_M_REF,
    P_MP_IXX,
    P_MP_IYY,
    P_MP_IZZ,
    P_MP_IXZ,
    P_MP_IXY,
    P_MP_IYZ,
    P_MP_M_OE,
    P_DT_DRY_MASS_INBOARD,
    P_DT_DRY_MASS_CENTRE,
    P_GEN_CUTIN,
    P_GEN_DROPOUT,
    P_BK_CUTIN,
    P_BK_DROPOUT,
    P_AC_V_NOM,
    P_AC_V_DROOP,
    P_GEN_EFF,
    P_GEN_NOLOAD,
    P_TRU_V_NL,
    P_TRU_R,
    P_TRU_EFF,
    P_BK_V_NL,
    P_BK_R,
    P_BK_RATING,
    P_BK_EFF,
    P_BATT_CAP_AH,
    P_BATT_OCV_FULL,
    P_BATT_OCV_EMPTY,
    P_BATT_R0,
    P_BATT_RP,
    P_BATT_TAU_P,
    P_BATT_R_TCOEF,
    P_BATT_T_REF,
    P_BATT_I_CHARGE,
    P_BATT_HEAT_CAP,
    P_BATT_UA,
    P_LOAD_AC_GROUND,
    P_LOAD_AC_AIR,
    P_LOAD_DCM_GROUND,
    P_LOAD_DCM_AIR,
    P_LOAD_ESS,
    P_LOAD_EMERG,
    P_LOAD_HEATER,
    P_LOAD_HEATER_T,
    P_AV_HEAT_FRAC,
    P_ECS_M_SET,
    P_ECS_CDA,
    P_ECS_M_AUX,
    P_ECS_PHX_UA,
    P_ECS_FOUL_K,
    P_ECS_RAM_AREA,
    P_ECS_M_RAM_GROUND,
    P_ECS_PHX_DP,
    P_ECS_ETA_T,
    P_ECS_TAU_DUCT,
    P_ECS_P_CAB_ISO,
    P_ECS_DP_MAX,
    P_ECS_DPDT_MAX,
    P_ECS_TAU_CAB_P,
    P_ECS_LEAK_FRAC,
    P_ECS_F_CAB,
    P_ECS_C_CAB,
    P_ECS_UA_CAB,
    P_ECS_Q_CAB,
    P_ECS_C_AV,
    P_ECS_UA_AV,
    P_ECS_T_SET,
    P_ECS_KI,
    P_ECS_STROKE,
    P_JFS_P_RATED,
    P_JFS_E_RATED,
    P_JFS_KE,
    P_JFS_RM,
    P_JFS_C_VISC,
    P_JFS_VISC_EXP,
    P_JFS_OIL_B,
    P_JFS_C_AERO,
    P_JFS_N_LO,
    P_JFS_N_SA,
    P_JFS_N_ON,
    P_JFS_P_GG,
    P_JFS_THETA_EXP,
    P_JFS_P_IGN,
    P_JFS_IGN_ALT,
    P_JFS_T_CRANK,
    P_JFS_T_ACCEL,
    P_JFS_T_ENGINE,
    P_JFS_N2_CUTOUT,
    P_JFS_M1_DRAG,
    P_JFS_M1_SCHED,
    P_JFS_OIL_USE_M1,
    P_JFS_OIL_USE_M2,
    P_JFS_EGT_RISE,
    P_JFS_TAU_EGT,
    P_JFS_OIL_HEAT,
    P_JFS_TAU_OIL,
    P_N2_100PCT,
    P_BRK_M_HS,
    P_BRK_CP,
    P_BRK_MASS_LOSS,
    P_BRK_TAU_COOL,
    P_BRK_P_ON,
    P_BRK_P_OFF,
    P_BRK_W_APP,
    P_BRK_W_ENERGY,
    P_BRK_T_OX,
    P_BRK_K_OX,
    P_TYRE_R,
    P_TYRE_W_TD,
    P_TYRE_M_REF,
    P_TYRE_V_REF,
    P_TYRE_W_BRAKE,
    P_TYRE_W_SKID,
    P_TYRE_MU_SKID,
    P_CHUTE_V_NORMAL,
    P_CHUTE_V_EMERG,
    P_BAY_HEAT_CAP,
    P_BAY_UA_CASE,
    P_BAY_VENT_AREA,
    P_BAY_M_VENT_GROUND,
    P_FIRE_Q,
    P_FIRE_T_ALARM,
    P_FIRE_P_EXT,
    P_LOAD_HEATER_RAMP,
    P_BRK_OX_SCALE,
    P_SKID_V_MIN,
    P_SKID_SLIP,
    P_TD_V_MIN,
    P_JFS_GOV_TAU,
    P_JFS_W_FLOOR,
    P_JFS_RATED_SPEED,
    P_BATT_R_SOC,
    P_LOAD_V_REF,
    P_HYD_ACC_T_CHARGE,
    P_ISA_T0,
    P_ISA_LAPSE,
    P_ISA_P0,
    P_BRK_TORQUE_GAIN,
    P_BRK_P_MAX,
    P_LOAD_PROBE_HEAT,
    P_BATT_LOW_WARN_AH,
) = range(NP_SCALAR)
for _j, _n in enumerate(P_NAMES):
    if globals()[f"P_{_n.upper()}"] != _j:  # pragma: no cover - import-time guard
        raise AssertionError(f"parameter constant P_{_n.upper()} out of order")

# Tank table, appended after the scalars: column-major blocks of N_TANKS values each.
TANK_COLS = ("cap", "length", "height", "x", "y", "z", "pickup", "group")  # probe stations: params only (M12)
TC_CAP, TC_LEN, TC_HGT, TC_X, TC_Y, TC_Z, TC_PICKUP, TC_GROUP = range(len(TANK_COLS))
P_TANK = NP_SCALAR  # p[P_TANK + col * N_TANKS + tank]
# Store-station table (positions only; masses are configuration in the float state).
STORE_COLS = ("x", "y", "z")
P_STORE = P_TANK + len(TANK_COLS) * N_TANKS  # p[P_STORE + col * N_STORE + station]
NP_TOTAL = P_STORE + len(STORE_COLS) * N_STORE

# Integer configuration vector passed to the kernel (not calibrated; structure of the installation).
C_NE, C_PUMP_ENG0, C_PUMP_ENG1, C_GEN_ENG, C_JFS_ENG, C_NSUB, C_XFER_TICKS, C_BRK_SYS = range(8)
NC = 8
