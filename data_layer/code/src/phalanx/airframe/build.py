"""Build the M06 kernel configuration from the parameter registry (``configs/<platform>/params/M06.yaml``).

Everything numeric comes from the registry (architecture P4). This module only

- flattens scalar parameters into the kernel vectors (``DYN_PARAM_NAMES``, ``AERO_PARAM_NAMES``);
- resamples the source tables (breakpoints at the evidence angles/Mach numbers) onto the uniform grids the
  kernel interpolates on (alpha -40..90 deg step 0.25 deg; Mach 0..2.5 step 0.01), exact at every grid node;
- derives the potential-lift Mach ratio ``rP(M)`` from the DATCOM subsonic lift-slope formula and supersonic
  linear theory (A-W1.2-4), and integrates ``Cm_ls(alpha)`` from the ``Cm_alpha(alpha)`` table (A-W1.2-5);
- assembles the gear, thrust and hinge-moment tables.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.special import ellipe

from phalanx.core.module import ContractError, Param, ParamSet
from phalanx.dictionary.params import load_params

from .aero import (
    A_CLB,
    A_CLP,
    A_CMA,
    A_CMDE,
    A_CMQ,
    A_CNB,
    A_CNDA,
    A_CNR,
    A_EFF,
    A_RUDEFF,
    A_SDCD,
    A_SDCL,
    A_SDCM,
    AERO_PARAM_NAMES,
    H_AREA,
    H_CH0,
    H_CHA,
    H_CHB,
    H_CHD,
    H_CHORD,
    M_CDW,
    M_DCM0,
    M_DSM,
    M_K,
    M_RCTRL,
    M_RDAMP,
    M_RDIR,
    M_RP,
    M_RV,
    N_ACOLS,
    N_AERO,
    N_HCOLS,
    N_MCOLS,
    N_SURF,
    AeroTables,
)
from .kernel import DYN_PARAM_NAMES, N_DYN, N_GCOLS

ALPHA_MIN_DEG, ALPHA_MAX_DEG, ALPHA_STEP_DEG = -40.0, 90.0, 0.25
MACH_MAX, MACH_STEP = 2.5, 0.01
assert len(AERO_PARAM_NAMES) == N_AERO and len(DYN_PARAM_NAMES) == N_DYN


@dataclass(frozen=True)
class AirframeConfig:
    """Kernel-ready configuration (read-only arrays)."""

    dp: np.ndarray
    ap: np.ndarray
    tab: AeroTables
    gtab: np.ndarray
    ttab: np.ndarray
    htab: np.ndarray
    n_eng: int


def airframe_param_set(
    platform: str = "tejas", config_root: Path | None = None, *, extra: dict[str, Param] | None = None
) -> ParamSet:
    """All M06 parameter sets merged into one ParamSet (names are unique across sets), plus ``extra``."""
    sets = load_params("M06", platform=platform, config_root=config_root)
    merged: dict[str, Param] = {}
    for s in sets.values():
        for k in s:
            if k in merged:
                raise ContractError(f"M06 parameter {k!r} defined in more than one set")
            merged[k] = s[k]
    for k, v in (extra or {}).items():
        if k in merged:
            raise ContractError(f"extra parameter {k!r} collides with M06.yaml")
        merged[k] = v
    return ParamSet(f"{platform}.M06", merged)


def _arr(ps: ParamSet, name: str) -> np.ndarray:
    return np.asarray(ps.value(name), dtype=np.float64)


def alpha_grid() -> np.ndarray:
    n = round((ALPHA_MAX_DEG - ALPHA_MIN_DEG) / ALPHA_STEP_DEG) + 1
    return np.radians(ALPHA_MIN_DEG + ALPHA_STEP_DEG * np.arange(n))


def mach_grid() -> np.ndarray:
    n = round(MACH_MAX / MACH_STEP) + 1
    return MACH_STEP * np.arange(n)


def _resample(x_bp: np.ndarray, y: np.ndarray, grid: np.ndarray) -> np.ndarray:
    if x_bp.shape != y.shape or x_bp.size < 2 or np.any(np.diff(x_bp) <= 0):
        raise ContractError("table breakpoints must be strictly increasing and match the values")
    return np.interp(grid, x_bp, y)


def lift_slope(mach: np.ndarray, aspect: float, kappa: float, lam_half: float, cot_lam: float) -> np.ndarray:
    """CL_alpha (per rad) vs Mach: DATCOM subsonic formula / supersonic linear theory (no fairing)."""
    out = np.empty_like(mach)
    for j, m in enumerate(mach):
        if m < 1.0:
            b2 = 1.0 - m * m
            t2 = math.tan(lam_half) ** 2
            root = math.sqrt(aspect**2 * b2 / kappa**2 * (1.0 + t2 / b2) + 4.0)
            out[j] = 2.0 * math.pi * aspect / (2.0 + root)
        else:
            beta = math.sqrt(m * m - 1.0)
            bc = beta * cot_lam
            if bc < 1.0:  # subsonic leading edge: 2 pi cot(L) / E(k), k^2 = 1 - (beta cot L)^2
                out[j] = 2.0 * math.pi * cot_lam / float(ellipe(1.0 - bc * bc))
            else:  # supersonic leading edge: Ackeret
                out[j] = 4.0 / beta
    return out


def potential_lift_ratio(ps: ParamSet, mach: np.ndarray) -> np.ndarray:
    """rP(M) = CL_alpha(M) / CL_alpha(0.2) with a linear transonic fairing (A-W1.2-4)."""
    aspect = float(ps.value("b_ref")) ** 2 / float(ps.value("s_ref"))
    kap = float(ps.value("datcom_kappa"))
    lam = float(ps.value("sweep_half_chord"))
    cot = float(ps.value("supersonic_cot_lambda"))
    lo, hi = float(ps.value("mach_fair_lo")), float(ps.value("mach_fair_hi"))
    cla = lift_slope(mach, aspect, kap, lam, cot)
    c_lo, c_hi = lift_slope(np.array([lo, hi]), aspect, kap, lam, cot)
    fair = (mach >= lo) & (mach <= hi)
    cla[fair] = c_lo + (mach[fair] - lo) / (hi - lo) * (c_hi - c_lo)
    ref = lift_slope(np.array([0.2]), aspect, kap, lam, cot)[0]
    return cla / ref


def build_tables(ps: ParamSet) -> AeroTables:
    ag = alpha_grid()
    mg = mach_grid()
    at = np.zeros((ag.size, N_ACOLS))
    a_cm = _arr(ps, "cm_ls_alpha")
    at[:, A_CMA] = _resample(a_cm, _arr(ps, "cm_alpha_ls"), ag)
    at[:, A_CMDE] = _resample(a_cm, _arr(ps, "cm_de_ls"), ag)
    at[:, A_CMQ] = _resample(a_cm, _arr(ps, "cm_q_ls"), ag)
    at[:, A_EFF] = _resample(a_cm, _arr(ps, "elev_eff"), ag)
    at[:, A_CNB] = _resample(_arr(ps, "cn_beta_alpha"), _arr(ps, "cn_beta"), ag)
    at[:, A_CLB] = _resample(_arr(ps, "cl_beta_alpha"), _arr(ps, "cl_beta"), ag)
    a_lat = _arr(ps, "lat_alpha")
    at[:, A_CLP] = _resample(a_lat, _arr(ps, "cl_p"), ag)
    at[:, A_CNR] = _resample(a_lat, _arr(ps, "cn_r"), ag)
    at[:, A_CNDA] = _resample(a_lat, _arr(ps, "cn_da_ratio"), ag)
    at[:, A_RUDEFF] = _resample(a_lat, _arr(ps, "rud_eff"), ag)
    a_sl = _arr(ps, "slat_alpha")
    at[:, A_SDCL] = _resample(a_sl, _arr(ps, "slat_dcl"), ag)
    at[:, A_SDCD] = _resample(a_sl, _arr(ps, "slat_dcd"), ag)
    at[:, A_SDCM] = _resample(a_sl, _arr(ps, "slat_dcm"), ag)
    # Cm_ls(alpha) = integral_0^alpha Cm_alpha d(alpha) (trapezoid on the grid, zero at alpha = 0)
    seg = 0.5 * (at[1:, A_CMA] + at[:-1, A_CMA]) * np.diff(ag)
    cm_ls = np.concatenate(([0.0], np.cumsum(seg)))
    i0 = int(np.argmin(np.abs(ag)))
    cm_ls = cm_ls - cm_ls[i0]
    mt = np.zeros((mg.size, N_MCOLS))
    m_bp = _arr(ps, "mach_bp")
    mt[:, M_RP] = potential_lift_ratio(ps, mg)
    mt[:, M_RV] = _resample(m_bp, _arr(ps, "r_vortex"), mg)
    mt[:, M_DSM] = _resample(m_bp, _arr(ps, "dsm"), mg)
    mt[:, M_CDW] = _resample(m_bp, _arr(ps, "cd_wave"), mg)
    mt[:, M_K] = _resample(m_bp, _arr(ps, "k_ind"), mg)
    mt[:, M_RCTRL] = _resample(m_bp, _arr(ps, "r_ctrl"), mg)
    mt[:, M_RDIR] = _resample(m_bp, _arr(ps, "r_dir"), mg)
    mt[:, M_RDAMP] = _resample(m_bp, _arr(ps, "r_damp"), mg)
    # zero-lift moment change that accompanies the subsonic forward neutral-point shift (A-W1.2-5)
    mt[:, M_DCM0] = float(ps.value("k_dcm0_dsm")) * np.maximum(mt[:, M_DSM], 0.0)
    for a in (at, mt, cm_ls):
        a.flags.writeable = False
    return AeroTables(float(ag[0]), float(ag[1] - ag[0]), at, float(mg[0]), float(mg[1] - mg[0]), mt, cm_ls)


def hinge_table(ps: ParamSet) -> np.ndarray:
    """(13, N_HCOLS) hinge-moment rows in fcs.surf_pos order."""
    h = np.zeros((N_SURF, N_HCOLS))
    area = _arr(ps, "surf_area")
    chord = _arr(ps, "surf_chord")
    if area.shape != (N_SURF,) or chord.shape != (N_SURF,):
        raise ContractError("surf_area and surf_chord need 13 entries (fcs.surf_pos order)")
    for s in range(4):
        h[s, H_CHA] = ps.value("ch_elevon_alpha")
        h[s, H_CHD] = ps.value("ch_elevon_delta")
    h[4, H_CHB] = ps.value("ch_rudder_beta")
    h[4, H_CHD] = ps.value("ch_rudder_delta")
    for s in range(5, 11):
        h[s, H_CHA] = ps.value("ch_slat_alpha")
        h[s, H_CHD] = ps.value("ch_slat_delta")
    for s in (11, 12):
        h[s, H_CH0] = ps.value("ch_airbrake_0")
        h[s, H_CHD] = ps.value("ch_airbrake_delta")
    h[:, H_AREA] = area
    h[:, H_CHORD] = chord
    h.flags.writeable = False
    return h


def build_config(ps: ParamSet, n_eng: int = 1) -> AirframeConfig:
    dp = np.array([float(ps.value(k)) for k in DYN_PARAM_NAMES])
    ap = np.array([float(ps.value(k)) for k in AERO_PARAM_NAMES])
    pts = _arr(ps, "gear_points")
    if pts.shape != (3, 3):
        raise ContractError("gear_points must be 3 x 3 (nose, left main, right main)")
    gtab = np.zeros((3, N_GCOLS))
    gtab[:, 0:3] = pts
    gtab[:, 3] = _arr(ps, "gear_l_ext")
    gtab[:, 4] = _arr(ps, "gear_k1")
    gtab[:, 5] = _arr(ps, "gear_k3")
    gtab[:, 6] = _arr(ps, "gear_c")
    gtab[:, 7] = (0.0, 1.0, 1.0)
    tp = _arr(ps, "thrust_points").reshape(-1, 3)
    ta = _arr(ps, "thrust_axes").reshape(-1, 3)
    if tp.shape[0] != n_eng or ta.shape[0] != n_eng:
        raise ContractError(f"thrust geometry has {tp.shape[0]} engines, configuration has n_engines={n_eng}")
    norms = np.linalg.norm(ta, axis=1)
    if np.any(np.abs(norms - 1.0) > 1e-9):
        raise ContractError("thrust_axes rows must be unit vectors")
    ttab = np.concatenate([tp, ta], axis=1)
    for a in (dp, ap, gtab, ttab):
        a.flags.writeable = False
    return AirframeConfig(dp, ap, build_tables(ps), gtab, ttab, hinge_table(ps), n_eng)
