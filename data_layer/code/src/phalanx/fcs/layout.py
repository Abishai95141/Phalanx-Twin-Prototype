"""M05 state, parameter and I/O layouts (AD-22 flat vectors with name -> index constants).

Float state ``f``: actuator positions/velocities, applied and pending commands (13 each), DFCC dynamic
states (integrators, prefilters, washout, command-path rate-limit memories) and the voted / derived signals of
the last frame. Int state ``i``: truth-tick counter, pending-command apply tick, law and mode words, WoW
persistence and stuck-switch faults, the next DFCC-clock sample index, lane-failure masks and mistrack
counters, channel fault/BIT/status words, actuator fault and BIT words, PBIT/MBIT state machines. Index
constants are checked against the names at import (``StateLayout``).
"""

from __future__ import annotations

from phalanx.core.layout import ParamLayout, StateLayout

from .ports import N_REC, N_SIG, N_SURF, REC_CHANNELS, SIG_POS0, VOTED_SIGNALS

SIG_STEMS = tuple(stem for stem, _, _, _ in VOTED_SIGNALS)
SIG_P, SIG_Q, SIG_R, SIG_NZ, SIG_NY, SIG_AL, SIG_AR, SIG_AOSS, SIG_PS, SIG_PT, SIG_SP, SIG_SR, SIG_PED = (
    range(SIG_POS0)
)
assert SIG_STEMS[SIG_PT] == "pt" and SIG_STEMS[SIG_NZ] == "asa_nz" and SIG_STEMS[SIG_PED] == "pedal"
assert SIG_STEMS[SIG_POS0] == "pos_elevon_lob" and len(SIG_STEMS) == SIG_POS0 + N_SURF

# ---- float state ------------------------------------------------------------------------------------------
F_POS = 0
F_VEL = F_POS + N_SURF
F_CMD = F_VEL + N_SURF
F_PEND = F_CMD + N_SURF
F_ZP = F_PEND + N_SURF  # pitch integrator (normalised error x s)
F_PFP = F_ZP + 1  # pitch stick prefilter
F_ZR = F_PFP + 1  # roll integrator (rad)
F_PFR = F_ZR + 1  # roll stick prefilter
F_WO = F_PFR + 1  # yaw-rate washout state (rad/s)
F_DA = F_WO + 1  # last differential elevon command (rate limit memory)
F_DR = F_DA + 1  # last rudder command
F_VOTE = F_DR + 1  # voted signals, SIG_* order (SI)
F_ALPHA = F_VOTE + N_SIG  # calibrated angle of attack (rad)
F_BETA = F_ALPHA + 1  # calibrated sideslip (rad)
F_MACH = F_BETA + 1
F_QBAR = F_MACH + 1  # Pa
F_HP = F_QBAR + 1  # pressure altitude, m
F_DE = F_HP + 1  # symmetric elevon (pitch) command of the last frame (FCS.VOTED.DE)
N_F = F_DE + 1

FLOAT_NAMES = (
    tuple(f"pos_{s}" for s in range(N_SURF))
    + tuple(f"vel_{s}" for s in range(N_SURF))
    + tuple(f"cmd_{s}" for s in range(N_SURF))
    + tuple(f"pend_{s}" for s in range(N_SURF))
    + ("z_pitch", "pf_pitch", "z_roll", "pf_roll", "washout", "da_last", "dr_last")
    + tuple(f"vote_{s}" for s in SIG_STEMS)
    + ("alpha_est", "beta_est", "mach_est", "qbar_est", "hp_est", "de_cmd")
)
assert len(FLOAT_NAMES) == N_F

# ---- int state --------------------------------------------------------------------------------------------
(
    I_TICK,
    I_APPLY,
    I_LAW,
    I_FLAGS,
    I_WOWCNT,
    I_GROUND,
    I_ADVALID,
    I_ADMIS,
    I_REVLATCH,
    I_SPIN,
    I_PBIT,
    I_PBITT,
    I_MBIT,
    I_MBITT,
    I_FRAMES,
    I_VANECNT,
    I_NNEXT,
    I_WOWF,
    I_WOWV,
) = range(19)
I_LFAIL = 19  # per signal: failed-lane bit mask (bit c = lane A..D)
I_MCNT = I_LFAIL + N_SIG  # per signal x lane mistrack persistence counters
I_CHFLT = I_MCNT + 4 * N_SIG  # injected channel fault words (23 subsystem bits; hidden truth)
I_CBIT = I_CHFLT + 4  # CBIT-latched subsystem words
I_CHST = I_CBIT + 4  # FCS.CH.STATUS words
I_CBCNT = I_CHST + 4  # CBIT persistence counters
I_RSTCNT = I_CBCNT + 4  # frames left showing CHANNEL_RESET
I_JAM = I_RSTCNT + 4  # actuator jam (hidden truth)
I_SERVO = I_JAM + N_SURF  # injected servo-coil channel faults (bits A..D; hidden truth)
I_ACTBIT = I_SERVO + N_SURF  # FCS.ACT.BIT words
I_ACTCNT = I_ACTBIT + N_SURF  # actuator BIT persistence counters
N_I = I_ACTCNT + N_SURF

_INT_SCALARS = (
    "tick",
    "apply_tick",
    "law",
    "mode_flags",
    "wow_count",
    "ground",
    "airdata_valid",
    "airdata_mistrack",
    "reversion_latched",
    "spin_request",
    "pbit_state",
    "pbit_timer",
    "mbit_state",
    "mbit_timer",
    "frames",
    "vane_count",
    "dfcc_next_sample",  # absolute index of the next DFCC-clock sample (core.sampling; module-maintained)
    "wow_fault_mask",  # stuck WoW switches (bit per leg: nose, left, right; hidden truth)
    "wow_fault_value",  # their stuck values
)
INT_NAMES = (
    *_INT_SCALARS,
    *(f"lane_fail_{s}" for s in SIG_STEMS),
    *(f"mistrack_{s}_{c}" for s in SIG_STEMS for c in "abcd"),
    *(f"ch_fault_{c}" for c in "abcd"),
    *(f"ch_cbit_{c}" for c in "abcd"),
    *(f"ch_status_{c}" for c in "abcd"),
    *(f"ch_cbit_count_{c}" for c in "abcd"),
    *(f"ch_reset_count_{c}" for c in "abcd"),
    *(f"jam_{s}" for s in range(N_SURF)),
    *(f"servo_fault_{s}" for s in range(N_SURF)),
    *(f"act_bit_{s}" for s in range(N_SURF)),
    *(f"act_bit_count_{s}" for s in range(N_SURF)),
)
assert len(INT_NAMES) == N_I

LAYOUT = StateLayout("m05.fcs", 1, floats=FLOAT_NAMES, ints=INT_NAMES)
LAYOUT.f.check(**{n: k for k, n in enumerate(FLOAT_NAMES)})
LAYOUT.i.check(**{n: k for k, n in enumerate(INT_NAMES)})
assert (
    FLOAT_NAMES[F_ZP] == "z_pitch"
    and FLOAT_NAMES[F_DE] == "de_cmd"
    and INT_NAMES[I_ACTCNT] == "act_bit_count_0"
)

# ---- codes and bit fields (dictionary code tables / FCS.CH.STATUS, FCS.MODE.FLAGS, FCS.ACT.BIT)
# -------------
LAW_SCHEDULED, LAW_FIXED, LAW_SPIN, LAW_GROUND = 0, 1, 2, 3  # fcs_law (3 = GROUND: proposed dictionary code)
CH_FAILED, CH_RESET, CH_DROPOUT, CCDL_FAIL = 1, 2, 4, 8
FLAG_AP, FLAG_ALSR, FLAG_AOA_LIM, FLAG_G_LIM, FLAG_REVERSION = 1, 2, 4, 8, 16
MIS_PRESSURE, MIS_AOA_VANE, MIS_AOSS = (
    16,
    32,
    64,
)  # FCS.AIRDATA_MISTRACK bits 4-6 (bits 0-3: ADC A-D excluded)
BIT_IDLE, BIT_RUNNING, BIT_PASS, BIT_FAIL = 0, 1, 2, 3
ACT_LVDT_SHIFT = 4  # FCS.ACT.BIT: SERVO_FAIL_A..D bits 0-3, LVDT_SUM_FAIL_A..D bits 4-7, HYD_PRESS_FAIL 8-11
LRU_BIT_FAIL, LRU_PBIT_FAIL, LRU_CBIT_FAIL, LRU_IBIT_RUN = 1, 2, 4, 8  # AV.LRU.BIT bits 0-3

# 23 diagnosable subsystems per DFCC channel (JOAST 57(4) 2005: 23 per channel; names are a SYNTHETIC
# assignment from the published module contents - digital module, analog actuator drivers, sensor interface,
# power supply). The criticality mask (subsystems whose failure drops the channel) is a parameter.
SUBSYSTEMS = (
    "CPU",
    "MEMORY",
    "TRANSPUTER",
    "WATCHDOG",
    "MIL1553",
    "RS422_ADC",
    "DA_CONVERTER",
    "AD_CONVERTER",
    "SILC",
    "CCDL",
    "PSU",
    "DRV_ELEVON_LO",
    "DRV_ELEVON_LI",
    "DRV_ELEVON_RI",
    "DRV_ELEVON_RO",
    "DRV_RUDDER",
    "DRV_SLAT_OB_L",
    "DRV_SLAT_MB_L",
    "DRV_SLAT_IB_L",
    "DRV_SLAT_IB_R",
    "DRV_SLAT_MB_R",
    "DRV_SLAT_OB_R",
    "SENSOR_INTERFACE",
)
assert len(SUBSYSTEMS) == 23
SUB_CCDL = SUBSYSTEMS.index("CCDL")
SUB_DRV0 = SUBSYSTEMS.index("DRV_ELEVON_LO")

# ---- kernel input row ------------------------------------------------------------------------------------
U_AB, U_GEAR = 0, 1
U_DPAV = 2  # 2
U_HEALTH = 4  # 13
U_ALPHA, U_BETA, U_QBAR = 17, 18, 19
U_WOW = 20  # 3 (nose, left main, right main)
U_LANES = 23  # N_SIG x 4 lane slots, signal-major (slots of uninstalled lanes unused)
N_U = U_LANES + 4 * N_SIG

# ---- outputs ----------------------------------------------------------------------------------------------
O_POS = 0
O_RATE = O_POS + N_SURF
O_FLOW = O_RATE + N_SURF
O_LAW = O_FLOW + 2
O_CHST = O_LAW + 1
O_REC = O_CHST + 4  # recorded computed channels, ports.REC_CHANNELS order
N_OUT = O_REC + N_REC
# offsets inside the recorded block
R_POSV = 0  # 13 voted surface positions
R_STICK = R_POSV + N_SURF  # voted stick pitch, stick roll, pedal
R_RSA_P = R_STICK + 3
R_RSA_R = R_RSA_P + 1
R_ASA_NY = R_RSA_R + 1
R_VQ = R_ASA_NY + 1
R_VNZ = R_VQ + 1
R_VDE = R_VNZ + 1
R_CMD = R_VDE + 1  # 5: elevons, rudder
R_LAW = R_CMD + 5
R_FLAGS = R_LAW + 1
R_CHST = R_FLAGS + 1  # 4
R_ACTBIT = R_CHST + 4  # 13
R_ADMIS = R_ACTBIT + N_SURF
R_LRUBIT = R_ADMIS + 1
assert R_LRUBIT + 1 == N_REC
assert (
    REC_CHANNELS[R_POSV] == "FCS.ELEVON.LOB.POS.V"
    and REC_CHANNELS[R_STICK] == "FCS.STICK.PITCH.V"
    and REC_CHANNELS[R_RSA_P] == "FCS.RSA.P.V"
    and REC_CHANNELS[R_ASA_NY] == "FCS.ASA.NY.V"
    and REC_CHANNELS[R_VQ] == "FCS.VOTED.Q"
    and REC_CHANNELS[R_VNZ] == "FCS.VOTED.NZ"
    and REC_CHANNELS[R_VDE] == "FCS.VOTED.DE"
    and REC_CHANNELS[R_CMD] == "FCS.ELEVON.LOB.CMD"
    and REC_CHANNELS[R_LAW] == "FCS.MODE.LAW"
    and REC_CHANNELS[R_CHST] == "FCS.CH.STATUS.A"
    and REC_CHANNELS[R_ACTBIT] == "FCS.ACT.BIT.ELEVON_LOB"
    and REC_CHANNELS[R_ADMIS] == "FCS.AIRDATA_MISTRACK"
    and REC_CHANNELS[R_LRUBIT] == "AV.LRU.BIT.DFCC"
)

# ---- scalar parameter vector
# --------------------------------------------------------------------------------
PARAM_NAMES = (
    "g0",
    "n_ref",
    "q_ref",
    "blend_m0",
    "blend_m1",
    "q_max",
    "nz_min",
    "tau_pf_pitch",
    "tau_pf_roll",
    "de_max",
    "da_max",
    "da_rate",
    "dr_max",
    "dr_rate",
    "tau_washout",
    "k_pedal",
    "slat_alpha0",
    "slat_alpha1",
    "slat_mach0",
    "slat_mach1",
    "slat_reversion",
    "airbrake_open",
    "n_wow",
    "wow_interlock",
    "wow_qbar_max",
    "vane_mistrack",
    "n_vane",
    "vane_k1",
    "vane_c0",
    "aoss_k1",
    "aoss_c0",
    "isa_p0",
    "isa_t0",
    "isa_lapse",
    "r_air",
    "gamma_air",
    "isa_h_trop",
    "n_cbit",
    "pbit_time",
    "mbit_time",
    "reset_time",
    "k_gnd_pitch",
    "k_gnd_q",
    "k_gnd_roll",
    "k_gnd_yaw",
    "p_max_fixed",
    "g_ny_fixed",
    "nz_max_fixed",
    "dp_rated",
    "dp_min",
    "slat_max_ob",
    "slat_max_mb",
    "slat_max_ib",
    "alpha_lead",
    "alpha_min",
)
PARAMS = ParamLayout(PARAM_NAMES)
(
    P_G0,
    P_NREF,
    P_QREF,
    P_BM0,
    P_BM1,
    P_QMAX,
    P_NZMIN,
    P_TPFP,
    P_TPFR,
    P_DEMAX,
    P_DAMAX,
    P_DARATE,
    P_DRMAX,
    P_DRRATE,
    P_TWO,
    P_KPED,
    P_SA0,
    P_SA1,
    P_SM0,
    P_SM1,
    P_SREV,
    P_ABOPEN,
    P_NWOW,
    P_WOWIL,
    P_WOWQ,
    P_VANEMIS,
    P_NVANE,
    P_VK1,
    P_VC0,
    P_BK1,
    P_BC0,
    P_P0,
    P_T0,
    P_LAPSE,
    P_RAIR,
    P_GAMMA,
    P_HTROP,
    P_NCBIT,
    P_PBITT,
    P_MBITT,
    P_RSTT,
    P_KGP,
    P_KGQ,
    P_KGR,
    P_KGY,
    P_PMAXF,
    P_GNYF,
    P_NZMAXF,
    P_DPR,
    P_DPMIN,
    P_SLOB,
    P_SLMB,
    P_SLIB,
    P_ALEAD,
    P_ALIMN,
) = range(len(PARAM_NAMES))
PARAMS.check(**{n: k for k, n in enumerate(PARAM_NAMES)})

# gain columns (schedule and the two fixed-gain sets) and Mach-schedule columns
G_N, G_Q, G_I, G_FF, G_PR, G_IR, G_B, G_R = range(8)
N_G = 8
S_ALIM, S_NZMAX, S_PMAX, S_ARI, S_TALPHA = range(5)
N_S = 5
# monitor table columns (rows = signals)
MON_ABS, MON_REL, MON_N = range(3)
