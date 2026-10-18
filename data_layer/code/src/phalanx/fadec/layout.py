"""AD-22 flat layouts of M08: per-engine state vectors, the flat parameter vector, tables and integer config.

State of one M08 instance (all engines): ``f`` float64 ``[n_engines, NF]``, ``i`` int64 ``[n_engines, NI]``
and
``g`` int64 ``[NG]`` (instance-level: the FADEC clock's next frame index and the last frame instant). The
names
below generate the index constants used by the kernel; `test_fadec_kernel.py` checks them against the layouts.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np

from phalanx.core.layout import VectorLayout
from phalanx.core.state import Field, StateSchema

from .codes import NS

#: lane-B comparison history depth (skew failure mode, frames); skew is capped at SKEW_MAX - 1
SKEW_MAX = 9
N_LANES = 12  # 2 lanes x 6 sensors (single-lane sensors leave slot B unused)

# ------------------------------------------------------------------ per-engine float state
_F_NAMES: list[str] = []
_F_NAMES += [f"lane_prev_{k}" for k in range(N_LANES)]
_F_NAMES += [f"hist_b_{s}_{j}" for s in range(NS) for j in range(SKEW_MAX)]
_F_NAMES += [f"sel_{s}" for s in range(NS)]
_F_NAMES += [f"hold_{s}" for s in range(NS)]
_F_NAMES += [f"trim_{s}" for s in range(NS)]
_F_NAMES += [f"xmod_{s}" for s in range(NS)]
_F_NAMES += [
    "xi_gov",
    "xi_n1",
    "xi_n2m",
    "xi_t5f",
    "xi_p3x",
    "xi_p3n",
    "xi_a8",
    "u_sel",
    "wf_cmd",
    "wf_ab_cmd",
    "a8_cmd",
    "fvg_cmd",
    "cvg_cmd",
    "ab_ru",
    "n2c_at",
    "n2c_dem",
    "n2dot",
    "n2_prev",
    "n1dot",
    "n1_prev",
    "ps3_filt",
    "ps3_prev",
    "pla_prev",
    "n1_lim",
    "t5_tgt",
    "ps3dot",
    # physical fault perturbations (fadec.fault_inject, AD-48.4; W2.1b, A-W2.1b-5): written by the module's
    # event handler, read by the kernel (I6: faults change state only)
    "flt_a8_gain",  # nozzle T5-loop gain increment (nozzle_loop_gain_margin)
    "flt_ru_bias",  # ratio-unit schedule bias (fuel_schedule_bias)
    "flt_wf_gain",  # fuel-metering demand gain error (fuel_overmetering)
    "flt_pla_hold",  # 1 = throttle binding: the PLA input is held at flt_pla_val
    "flt_pla_val",  # held PLA (rad)
]
F_LAYOUT = VectorLayout(_F_NAMES)
NF = len(F_LAYOUT)
_fi = F_LAYOUT.index
F_LANE_PREV = _fi["lane_prev_0"]
F_HIST_B = _fi["hist_b_0_0"]
F_SEL = _fi["sel_0"]
F_HOLD = _fi["hold_0"]
F_TRIM = _fi["trim_0"]
F_XMOD = _fi["xmod_0"]
F_XI_GOV = _fi["xi_gov"]
F_XI_N1 = _fi["xi_n1"]
F_XI_N2M = _fi["xi_n2m"]
F_XI_T5F = _fi["xi_t5f"]
F_XI_P3X = _fi["xi_p3x"]
F_XI_P3N = _fi["xi_p3n"]
F_XI_A8 = _fi["xi_a8"]
F_U_SEL = _fi["u_sel"]
F_WF_CMD = _fi["wf_cmd"]
F_WF_AB_CMD = _fi["wf_ab_cmd"]
F_A8_CMD = _fi["a8_cmd"]
F_FVG_CMD = _fi["fvg_cmd"]
F_CVG_CMD = _fi["cvg_cmd"]
F_AB_RU = _fi["ab_ru"]
F_N2C_AT = _fi["n2c_at"]
F_N2C_DEM = _fi["n2c_dem"]
F_N2DOT = _fi["n2dot"]
F_N2_PREV = _fi["n2_prev"]
F_N1DOT = _fi["n1dot"]
F_N1_PREV = _fi["n1_prev"]
F_PS3_FILT = _fi["ps3_filt"]
F_PS3_PREV = _fi["ps3_prev"]
F_PLA_PREV = _fi["pla_prev"]
F_N1_LIM = _fi["n1_lim"]
F_T5_TGT = _fi["t5_tgt"]
F_PS3DOT = _fi["ps3dot"]
F_FLT_A8_GAIN = _fi["flt_a8_gain"]
F_FLT_RU_BIAS = _fi["flt_ru_bias"]
F_FLT_WF_GAIN = _fi["flt_wf_gain"]
F_FLT_PLA_HOLD = _fi["flt_pla_hold"]
F_FLT_PLA_VAL = _fi["flt_pla_val"]

# ------------------------------------------------------------------ per-engine int state
_I_NAMES: list[str] = []
_I_NAMES += [f"cnt_rng_{k}" for k in range(N_LANES)]
_I_NAMES += [f"cnt_rate_{k}" for k in range(N_LANES)]
_I_NAMES += [f"cnt_good_{k}" for k in range(N_LANES)]
_I_NAMES += [f"lane_fail_{k}" for k in range(N_LANES)]
for _n in ("xc_cnt", "xc_fail", "xc_good", "an_cnt", "an_fail", "an_good", "hold_cnt", "vstate", "has_lane"):
    _I_NAMES += [f"{_n}_{s}" for s in range(NS)]
_I_NAMES += [
    "init",
    "frame",
    "fuel_code",
    "noz_code",
    "ab_state",
    "ab_retry",
    "ab_cnt",
    "ab_lost",
    "ab_event",
    "start_state",
    "start_cnt",
    "fo_latch",
    "fo_cnt",
    "fo_ok",
    "hs_cnt",
    "hs_on",
    "si_cnt",
    "ot_cnt",
    "os1_cnt",
    "os2_cnt",
    "stall_cnt",
    "ign",
    "ab_enable",
    "at_prev",
    "acc",
    "faults",
    "skew_pos",
    "sub_mode",
]
I_LAYOUT = VectorLayout(_I_NAMES)
NI = len(I_LAYOUT)
_ii = I_LAYOUT.index
I_CNT_RNG = _ii["cnt_rng_0"]
I_CNT_RATE = _ii["cnt_rate_0"]
I_CNT_GOOD = _ii["cnt_good_0"]
I_LANE_FAIL = _ii["lane_fail_0"]
I_XC_CNT = _ii["xc_cnt_0"]
I_XC_FAIL = _ii["xc_fail_0"]
I_XC_GOOD = _ii["xc_good_0"]
I_AN_CNT = _ii["an_cnt_0"]
I_AN_FAIL = _ii["an_fail_0"]
I_AN_GOOD = _ii["an_good_0"]
I_HOLD_CNT = _ii["hold_cnt_0"]
I_VSTATE = _ii["vstate_0"]
I_HAS_LANE = _ii["has_lane_0"]
I_INIT = _ii["init"]
I_FRAME = _ii["frame"]
I_FUEL_CODE = _ii["fuel_code"]
I_NOZ_CODE = _ii["noz_code"]
I_AB_STATE = _ii["ab_state"]
I_AB_RETRY = _ii["ab_retry"]
I_AB_CNT = _ii["ab_cnt"]
I_AB_LOST = _ii["ab_lost"]
I_AB_EVENT = _ii["ab_event"]
I_START_STATE = _ii["start_state"]
I_START_CNT = _ii["start_cnt"]
I_FO_LATCH = _ii["fo_latch"]
I_FO_CNT = _ii["fo_cnt"]
I_FO_OK = _ii["fo_ok"]
I_HS_CNT = _ii["hs_cnt"]
I_HS_ON = _ii["hs_on"]
I_SI_CNT = _ii["si_cnt"]
I_OT_CNT = _ii["ot_cnt"]
I_OS1_CNT = _ii["os1_cnt"]
I_OS2_CNT = _ii["os2_cnt"]
I_STALL_CNT = _ii["stall_cnt"]
I_IGN = _ii["ign"]
I_AB_ENABLE = _ii["ab_enable"]
I_AT_PREV = _ii["at_prev"]
I_ACC = _ii["acc"]
I_FAULTS = _ii["faults"]
I_SKEW_POS = _ii["skew_pos"]
I_SUB_MODE = _ii["sub_mode"]

# ------------------------------------------------------------------ instance-level int state
G_LAYOUT = VectorLayout(("n_next", "last_frame_t"))
NG = len(G_LAYOUT)
G_N_NEXT, G_LAST_FRAME_T = 0, 1
G_LAYOUT.check(n_next=G_N_NEXT, last_frame_t=G_LAST_FRAME_T)

# ------------------------------------------------------------------ per-step outputs of the block kernel
O_WF, O_WF_AB, O_A8, O_FVG, O_CVG = range(5)
O_SEL = 5  # .. 5 + NS: validated (selected) sensor values, SI
NOF = O_SEL + NS
O_IGN, O_AB_EN, O_LIMITER = 0, 1, 2
O_VSTATE = 3  # .. 3 + NS
O_FAULTS = 3 + NS
NOI = O_FAULTS + 1

# ------------------------------------------------------------------ flat parameter vector (kernel floats)
P_NAMES: tuple[str, ...] = (
    "t_std",
    "p_std",
    "n1_ref",
    "n2_ref",
    "pla_cutoff",
    "pla_gi",
    "pla_irp",
    "pla_ab_min",
    "n1c_cap",
    "n2_max",
    "n2_reduce",
    "n2c_part",
    "gov_kp",
    "gov_ki",
    "n1_kp",
    "n1_ki",
    "n2m_kp",
    "n2m_ki",
    "t5f_kp",
    "t5f_ki",
    "ps3x_kp",
    "ps3x_ki",
    "ps3n_kp",
    "ps3n_ki",
    "k_ifb",
    "acc_k",
    "dec_k",
    "wf_min",
    "wf_max",
    "ps3_max",
    "ps3_min",
    "t5_lim_p0_k",
    "t5_fuel_margin",
    "a8_scale",
    "a8_min",
    "a8_max",
    "a8_kp",
    "a8_ki",
    "a8_preopen",
    "a8_safe",
    "t5_reset",
    "ab_ru_light",
    "ab_ru_rate",
    "ab_perm_n1",
    "at_kp",
    "at_ki",
    "at_rate",
    "an_tol_steady",
    "an_tol_transient",
    "trim_alpha",
    "trans_n2dot",
    "trans_pla_rate",
    "xc_rate_k",
    "vm_tol_scale",
    "n2dot_alpha",
    "hs_deadband",
    "ign_lo",
    "ign_hi",
    "n2_run",
    "fo_n2dot",
    "fo_hyst",
    "n2_subidle",
    "stall_drop",
    "t5_ot",
    "n1_os",
    "n2_os",
    "gov_kff",
    "n1_lead",
    "gov_kl",
    "gov_edz",
    "ps3_alpha",
    "fo_t5_min",
    "fo_dem_margin",
    "nd_sched",
    "nd_kp",
    "nd_ki",
    "t5_start_lim",
    "hs_pla_lo",
    "hs_pla_hi",
    "ps3_lead",
    "fo_delta_min",
    "n1dot_alpha",
    "ps3dot_alpha",
    "n1_gs_t0",
    "n1_gs_k",
    "n1_gs_max",
    "n1_gs_pexp",
    "n1_gs_pmax",
)
P_LAYOUT = VectorLayout(P_NAMES)
NP_ = len(P_LAYOUT)
_pi = P_LAYOUT.index
(
    P_T_STD,
    P_P_STD,
    P_N1_REF,
    P_N2_REF,
    P_PLA_CUTOFF,
    P_PLA_GI,
    P_PLA_IRP,
    P_PLA_AB_MIN,
    P_N1C_CAP,
    P_N2_MAX,
    P_N2_REDUCE,
    P_N2C_PART,
    P_GOV_KP,
    P_GOV_KI,
    P_N1_KP,
    P_N1_KI,
    P_N2M_KP,
    P_N2M_KI,
    P_T5F_KP,
    P_T5F_KI,
    P_PS3X_KP,
    P_PS3X_KI,
    P_PS3N_KP,
    P_PS3N_KI,
    P_K_IFB,
    P_ACC_K,
    P_DEC_K,
    P_WF_MIN,
    P_WF_MAX,
    P_PS3_MAX,
    P_PS3_MIN,
    P_T5_LIM_P0_K,
    P_T5_FUEL_MARGIN,
    P_A8_SCALE,
    P_A8_MIN,
    P_A8_MAX,
    P_A8_KP,
    P_A8_KI,
    P_A8_PREOPEN,
    P_A8_SAFE,
    P_T5_RESET,
    P_AB_RU_LIGHT,
    P_AB_RU_RATE,
    P_AB_PERM_N1,
    P_AT_KP,
    P_AT_KI,
    P_AT_RATE,
    P_AN_TOL_STEADY,
    P_AN_TOL_TRANSIENT,
    P_TRIM_ALPHA,
    P_TRANS_N2DOT,
    P_TRANS_PLA_RATE,
    P_XC_RATE_K,
    P_VM_TOL_SCALE,
    P_N2DOT_ALPHA,
    P_HS_DEADBAND,
    P_IGN_LO,
    P_IGN_HI,
    P_N2_RUN,
    P_FO_N2DOT,
    P_FO_HYST,
    P_N2_SUBIDLE,
    P_STALL_DROP,
    P_T5_OT,
    P_N1_OS,
    P_N2_OS,
    P_GOV_KFF,
    P_N1_LEAD,
    P_GOV_KL,
    P_GOV_EDZ,
    P_PS3_ALPHA,
    P_FO_T5_MIN,
    P_FO_DEM_MARGIN,
    P_ND_SCHED,
    P_ND_KP,
    P_ND_KI,
    P_T5_START_LIM,
    P_HS_PLA_LO,
    P_HS_PLA_HI,
    P_PS3_LEAD,
    P_FO_DELTA_MIN,
    P_N1DOT_ALPHA,
    P_PS3DOT_ALPHA,
    P_N1_GS_T0,
    P_N1_GS_K,
    P_N1_GS_MAX,
    P_N1_GS_PEXP,
    P_N1_GS_PMAX,
) = range(NP_)
assert P_N2_OS == _pi["n2_os"] and P_GOV_KP == _pi["gov_kp"] and P_ACC_K == _pi["acc_k"]

#: loop-gain entries of the parameter vector (complex-step safe; W2.4 identifies them)
LOOP_GAINS: tuple[str, ...] = (
    "gov_kff",
    "gov_kl",
    "gov_kp",
    "gov_ki",
    "n1_kp",
    "n1_ki",
    "n2m_kp",
    "n2m_ki",
    "t5f_kp",
    "t5f_ki",
    "ps3x_kp",
    "ps3x_ki",
    "ps3n_kp",
    "ps3n_ki",
    "k_ifb",
    "a8_kp",
    "a8_ki",
    "at_kp",
    "at_ki",
)

# ------------------------------------------------------------------ integer configuration vector
C_NAMES: tuple[str, ...] = (
    "fuel_law",
    "autothrottle",
    "n_range",
    "n_rate",
    "n_xc",
    "heal",
    "lane_heal",
    "n_an",
    "n_hold",
    "max_subst",
    "skew",
    "wrap",
    "analytic",
    "hs_window",
    "hs_timeout",
    "fo_detect",
    "fo_confirm",
    "si_frames",
    "stall_hold",
    "ot_frames",
    "os_frames",
    "ab_nolight",
    "ab_max_retries",
    "ab_retry",
    "ab_preopen",
    "ab_blowout",
    "nl_0",
    "nl_1",
    "nl_2",
    "nl_3",
    "nl_4",
    "nl_5",
    "anti_windup",
    "handoff",
    "edge_hold",
    # W2.4a-2 (proxy, coordinator decision): the A/T demand floor is the demand of the lever M08 is fed (1;
    # the proxy feeds the pre-mapped idle-stop lever while the A/T is engaged) instead of the schedule's
    # lowest demand (0, default: the Tejas/W1.3b law, bitwise unchanged). Set with
    # ``FadecConfig.with_cfg``.
    "at_floor_lever",
)
C_LAYOUT = VectorLayout(C_NAMES)
NC = len(C_LAYOUT)
(
    C_FUEL_LAW,
    C_AUTOTHROTTLE,
    C_N_RANGE,
    C_N_RATE,
    C_N_XC,
    C_HEAL,
    C_LANE_HEAL,
    C_N_AN,
    C_N_HOLD,
    C_MAX_SUBST,
    C_SKEW,
    C_WRAP,
    C_ANALYTIC,
    C_HS_WINDOW,
    C_HS_TIMEOUT,
    C_FO_DETECT,
    C_FO_CONFIRM,
    C_SI_FRAMES,
    C_STALL_HOLD,
    C_OT_FRAMES,
    C_OS_FRAMES,
    C_AB_NOLIGHT,
    C_AB_MAX_RETRIES,
    C_AB_RETRY,
    C_AB_PREOPEN,
    C_AB_BLOWOUT,
    C_NL0,
    _C_NL1,
    _C_NL2,
    _C_NL3,
    _C_NL4,
    _C_NL5,
    C_ANTI_WINDUP,
    C_HANDOFF,
    C_EDGE_HOLD,
    C_AT_FLOOR_LEVER,
) = range(NC)
assert C_NL0 == C_LAYOUT.index["nl_0"] and C_HANDOFF == C_LAYOUT.index["handoff"]
#: `handoff` bits: the MIN/MAX limiters with a bumpless hand-off past their limit (W2.1 entry gate 4)
HO_N1, HO_N2MAX, HO_T5, HO_PS3MAX, HO_PS3MIN = 1, 2, 4, 8, 16


class Tables(NamedTuple):
    """Schedules, on-board model and per-sensor validator arrays (all float64, SI)."""

    n2c_pla_x: np.ndarray
    n2c_pla_y: np.ndarray
    a8_pla_x: np.ndarray
    a8_pla_y: np.ndarray
    ru_x: np.ndarray
    ru_y: np.ndarray
    ruff_x: np.ndarray  # demand N2/sqrt(theta25) -> feed-forward ratio units
    ruff_y: np.ndarray
    ab_ru_x: np.ndarray
    ab_ru_y: np.ndarray
    fvg_x: np.ndarray
    fvg_y: np.ndarray
    cvg_x: np.ndarray
    cvg_y: np.ndarray
    n1lim_x: np.ndarray
    n1lim_y: np.ndarray
    t5lim_x: np.ndarray
    t5lim_y: np.ndarray
    fo_x: np.ndarray
    fo_y: np.ndarray
    obm_n1_x: np.ndarray  # n2c -> n1c
    obm_n1_y: np.ndarray
    obm_n2_x: np.ndarray  # n1c -> n2c (inverse of the above)
    obm_n2_y: np.ndarray
    obm_pr3_x: np.ndarray
    obm_pr3_y: np.ndarray
    obm_t25_x: np.ndarray
    obm_t25_y: np.ndarray
    obm_t5_x: np.ndarray
    obm_t5_y: np.ndarray
    v_lo: np.ndarray  # [NS] range-fail low (SI)
    v_hi: np.ndarray  # [NS] range-fail high (SI)
    v_rate: np.ndarray  # [NS] rate bound (SI/s)
    v_xc: np.ndarray  # [NS] cross-channel tolerance (SI)
    v_safe: np.ndarray  # [NS] safer direction (+1 / -1)
    # N2-governor gain schedule (W2.3a): multiplier on gov_kp and gov_ki vs N2/sqrt(theta1); flat 1 = none
    govk_x: np.ndarray
    govk_y: np.ndarray


def state_schema(n_engines: int) -> StateSchema:
    """The M08 state schema for `n_engines` (versioned with the layout)."""
    e = int(n_engines)
    return StateSchema(
        f"fadec.m08.e{e}",
        3,  # 2: + ps3dot (W2.1b PS3 limiter rate anticipation) and the handoff config; 3: + fault slice
        (Field("f", "<f8", (e, NF)), Field("i", "<i8", (e, NI)), Field("g", "<i8", (NG,))),
    )


__all__ = [
    "C_LAYOUT",
    "F_LAYOUT",
    "G_LAYOUT",
    "I_LAYOUT",
    "LOOP_GAINS",
    "NC",
    "NF",
    "NG",
    "NI",
    "NOF",
    "NOI",
    "NP_",
    "O_SEL",
    "P_LAYOUT",
    "P_NAMES",
    "SKEW_MAX",
    "Tables",
    "state_schema",
]
