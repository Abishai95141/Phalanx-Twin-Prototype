"""Build the M05 kernel configuration from the parameter registry (``M05.yaml`` plus the M06 hinge model).

Unit handling: the registry stores physical units and the loader converts to SI. The DFCC works in g for
normal acceleration (the FCS.ASA channels' engineering unit), so load factors given in ``standard_gravity``
are
divided by g0 here; natural frequencies given in Hz are converted to rad/s (2 pi f).

Frame timing (AD-42): the DFCC frames on the DFCC acquisition clock domain shared with M13
(``acquisition_clock("DFCC", frame_rate)``), so frames fall exactly on the instants the in-loop lanes are
sampled at; the computation delay is kept in integer ns and resolved to truth frames by
``module.frame_schedule``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phalanx.acquisition.config import acquisition_clock
from phalanx.airframe.build import airframe_param_set, hinge_table
from phalanx.core.module import ContractError, Param, ParamSet
from phalanx.core.sampling import max_samples_per_step
from phalanx.core.time import ClockDomain
from phalanx.dictionary.params import load_params

from .actuators import (
    C_AREA,
    C_ARM,
    C_GCP,
    C_GNULL,
    C_NSEC,
    C_POSMAX,
    C_POSMIN,
    C_SYS,
    C_V0,
    C_WN,
    C_ZETA,
    N_ACOLS,
)
from .design import GAIN_COLUMNS, DesignSettings
from .kernel import FcsTables
from .layout import N_G, N_S, PARAM_NAMES, S_ALIM, S_ARI, S_NZMAX, S_PMAX, S_TALPHA
from .ports import LANE_CAP, N_SIG, N_SURF, lane_mask

M06_SHARED = ("slat_max_ob", "slat_max_mb", "slat_max_ib")


@dataclass(frozen=True)
class FcsConfig:
    p: np.ndarray
    tab: FcsTables
    clock: ClockDomain  # DFCC frame clock (= M13 DFCC acquisition clock)
    delay_ns: int  # computation delay, sample instant -> command available
    tf: float  # frame period, s (the discrete-time step of the DFCC laws)
    n_sub_act: int
    crit_mask: int


def fcs_param_set(
    platform: str = "tejas", config_root: Path | None = None, *, extra: dict[str, Param] | None = None
) -> ParamSet:
    """M05 sets merged, plus the M06 hinge-moment set and the slat travel that normalises the aero tables."""
    merged: dict[str, Param] = {}
    for s in load_params("M05", platform=platform, config_root=config_root).values():
        for k in s:
            if k in merged:
                raise ContractError(f"M05 parameter {k!r} defined twice")
            merged[k] = s[k]
    m06 = airframe_param_set(platform, config_root)
    hinge = load_params("M06", platform=platform, config_root=config_root)["hinge"]
    for k in list(hinge) + list(M06_SHARED):
        if k in merged:
            raise ContractError(f"M06 parameter {k!r} collides with M05")
        merged[k] = m06[k]
    for k, v in (extra or {}).items():
        if k in merged:
            raise ContractError(f"extra parameter {k!r} collides with the registry")
        merged[k] = v
    return ParamSet(f"{platform}.M05", merged)


def _a(ps: ParamSet, k: str) -> np.ndarray:
    return np.asarray(ps.value(k), dtype=np.float64)


def _f(ps: ParamSet, k: str) -> float:
    return float(ps.value(k))


IN_G = frozenset({"n_ref", "nz_min", "nz_max_fixed"})  # load factors: SI -> g for the DFCC


def scalar_vector(ps: ParamSet) -> np.ndarray:
    g0 = _f(ps, "g0")
    v = np.array([_f(ps, n) / g0 if n in IN_G else _f(ps, n) for n in PARAM_NAMES])
    v.flags.writeable = False
    return v


def actuator_table(ps: ParamSet) -> np.ndarray:
    a = np.zeros((N_SURF, N_ACOLS))
    a[:, C_POSMIN] = _a(ps, "pos_min")
    a[:, C_POSMAX] = _a(ps, "pos_max")
    a[:, C_V0] = _a(ps, "rate_noload")
    a[:, C_WN] = 2.0 * math.pi * _a(ps, "servo_wn")
    a[:, C_ZETA] = _f(ps, "servo_zeta")
    a[:, C_AREA] = _a(ps, "piston_area")
    a[:, C_ARM] = _a(ps, "arm")
    a[:, C_NSEC] = _a(ps, "n_sections")
    a[:, C_SYS] = _a(ps, "system")
    a[:, C_GNULL] = _f(ps, "g_null")
    a[:, C_GCP] = _f(ps, "g_crossport")
    if np.any(a[:, C_POSMIN] >= a[:, C_POSMAX]):
        raise ContractError("actuator position limits must satisfy pos_min < pos_max")
    a.flags.writeable = False
    return a


def schedule_tables(ps: ParamSet) -> tuple[np.ndarray, np.ndarray]:
    g0 = _f(ps, "g0")
    bp = _a(ps, "sched_mach")
    s = np.zeros((bp.size, N_S))
    s[:, S_ALIM] = _a(ps, "alpha_lim")
    s[:, S_NZMAX] = _a(ps, "nz_max") / g0
    s[:, S_PMAX] = _a(ps, "p_max")
    s[:, S_ARI] = _a(ps, "ari")
    s[:, S_TALPHA] = _a(ps, "t_alpha_sched")
    if np.any(s[:, S_TALPHA] <= 0.0):
        raise ContractError("t_alpha schedule must be positive")
    if np.any(np.diff(bp) <= 0):
        raise ContractError("schedule Mach breakpoints must increase")
    return bp, s


def monitor_table(ps: ParamSet) -> np.ndarray:
    m = np.column_stack([_a(ps, "mon_thr_abs"), _a(ps, "mon_thr_rel"), _a(ps, "mon_n")])
    if m.shape != (N_SIG, 3):
        raise ContractError(f"monitor table must have {N_SIG} rows (ports.VOTED_SIGNALS order)")
    return m


def gain_tables(ps: ParamSet) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(Mach bp, altitude bp, gains[nm, nh, N_G], fixed[2, N_G]) from the designed-schedule entries."""
    mach = _a(ps, "gs_mach")
    alt = _a(ps, "gs_alt")
    bm = np.unique(mach)
    bh = np.unique(alt)
    if mach.size != bm.size * bh.size:
        raise ContractError("gain schedule must be a full Mach x altitude grid")
    g = np.zeros((bm.size, bh.size, N_G))
    for c, name in enumerate(GAIN_COLUMNS):
        col = _a(ps, f"gs_{name}")
        for k in range(mach.size):
            g[np.searchsorted(bm, mach[k]), np.searchsorted(bh, alt[k]), c] = col[k]
    fixed = np.zeros((2, N_G))
    for c, name in enumerate(GAIN_COLUMNS):
        fixed[:, c] = _a(ps, f"fx_{name}")
    return bm, bh, g, fixed


def crit_mask(ps: ParamSet) -> int:
    m = 0
    for k in _a(ps, "crit_subsystems"):
        if not 0 <= k < 23 or k != int(k):
            raise ContractError(f"crit_subsystems index {k} outside 0..22")
        m |= 1 << int(k)
    return m


def lane_masks() -> np.ndarray:
    m = np.array([lane_mask(s) for s in range(N_SIG)], dtype=np.int64)
    m.flags.writeable = False
    return m


def build_fcs_config(ps: ParamSet, clock: ClockDomain | None = None) -> FcsConfig:
    """Kernel configuration; ``clock`` defaults to the M13 DFCC acquisition clock at ``frame_rate``."""
    bm, bh, g, fixed = gain_tables(ps)
    sbp, sched = schedule_tables(ps)
    tab = FcsTables(
        bm, bh, g, fixed, sbp, sched, monitor_table(ps), lane_masks(), actuator_table(ps), hinge_table(ps)
    )
    rate = _f(ps, "frame_rate")
    if clock is None:
        clock = acquisition_clock("DFCC", rate)
    if clock.f_nom_hz != rate:
        raise ContractError(f"DFCC clock {clock.name} is not at the frame rate {rate} Hz")
    if max_samples_per_step(clock) != LANE_CAP:
        raise ContractError(f"DFCC clock {clock.name}: lane buffers hold {LANE_CAP} sample per truth step")
    delay_ns = round(_f(ps, "compute_delay") * 1e9)
    if not 0 <= delay_ns < clock.period_ns:
        raise ContractError("computation delay must be shorter than one DFCC frame")
    tf = float(clock.period_ns) / 1e9
    return FcsConfig(scalar_vector(ps), tab, clock, delay_ns, tf, int(ps.value("n_sub_act")), crit_mask(ps))


def settings_from_params(ps: ParamSet) -> DesignSettings:
    """Design inputs mirrored from the registry (so the design uses exactly the kernel's parameters)."""
    two_pi = 2.0 * math.pi
    g0 = _f(ps, "g0")
    rate = _f(ps, "frame_rate")
    frame = 1.0 / rate
    delay = math.ceil(_f(ps, "compute_delay") * 240.0 - 1e-12) / 240.0
    elevon_wn = two_pi * float(_a(ps, "servo_wn")[0])
    return DesignSettings(
        n_ref=_f(ps, "n_ref") / g0,
        q_ref=_f(ps, "q_ref"),
        blend_m0=_f(ps, "blend_m0"),
        blend_m1=_f(ps, "blend_m1"),
        w_sp_candidates=tuple(float(x) for x in _a(ps, "w_sp_candidates")),
        zeta_candidates=tuple(float(x) for x in _a(ps, "zeta_sp_candidates")),
        p_i_candidates=tuple(float(x) for x in _a(ps, "p_i_candidates")),
        gm_ref_db=_f(ps, "gm_ref"),
        pm_ref_deg=math.degrees(_f(ps, "pm_ref")),
        servo_wn=elevon_wn,
        servo_zeta=_f(ps, "servo_zeta"),
        frame=frame,
        delay=delay,
        w_roll=_f(ps, "w_roll"),
        zeta_roll=_f(ps, "zeta_roll"),
        w_dr_min=_f(ps, "w_dr_min"),
        zeta_dr=_f(ps, "zeta_dr"),
        x_asa=_f(ps, "x_asa"),
        rsa_wn=two_pi * _f(ps, "rsa_wn"),
        asa_wn=two_pi * _f(ps, "asa_wn"),
        sensor_zeta=_f(ps, "sensor_zeta"),
        g0=g0,
    )
