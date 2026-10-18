"""Tejas-anchored parametric aero build-up (AD-08, architecture §6 M06): ``@njit`` coefficient functions.

Structure mirrors the HAL "Aero Data Set" (report §0/§1; ``tejas_airframe_aero_fcs.md`` Q4, Q8 recipe (f)):
basic(alpha, beta, Mach) + per-surface increments (four elevons with no port/starboard coupling, rudder,
slats, airbrakes, gear) + dynamic derivatives + hinge moments. Every number is a parameter (``M06.yaml``);
this file holds only the functional forms:

- **Lift core** (Tejas WT anchor): ``CL = CL0 + Kp rP(M) sin a cos^2 a + Kv rV(M) cos a sin a |sin a|``
  (Polhamus form fitted to the digitised Tejas WT curve), blended to a flat-plate normal force above the
  vortex-breakdown band. ``rP(M)`` comes from the DATCOM subsonic lift-slope formula and supersonic linear
  theory (``build.py``).
- **Pitching moment** about the reference point (34 % MAC): low-speed shape ``Cm_ls(alpha)`` (integral of a
  ``Cm_alpha(alpha)`` table through the NAL anchors), plus a Mach static-margin shift ``dSM(M) * CN_pot`` that
  reproduces the NFTC time-to-double map, plus damping and elevon power.
- **Lateral-directional:** Tejas ``Cn_beta(alpha)`` and ``Cl_beta(alpha)`` (digitised WT), Tejas ``Cn_dr``;
  damping/control derivatives that are not public are tagged ASSUMPTION (strip theory, slender-wing theory).
- **Drag build-up:** flat-plate turbulent skin friction on Reynolds number with compressibility, wave drag
  ``dCD_w(M)``, induced drag ``K(M) CL^2`` blended to zero leading-edge suction ``CL tan(alpha)`` at high
  alpha, ground-effect factor on induced drag (McCormick), increments for gear, airbrakes, slats.

Surface vector ``d`` (rad), the M05 port order: elevon LO, LI, RI, RO; rudder; slats OB_L, MB_L, IB_L, IB_R,
MB_R, OB_R; airbrake L, R. Signs: elevon and slat positive trailing-edge / leading-edge down; rudder positive
trailing-edge left (nose-left yaw, ``Cn_dr < 0``); airbrake positive open.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
from numba import njit

from .geodesy import NJ, sin_cos

# ---- surface indices (fcs.surf_pos order, W1_interfaces.md §2) ------------------------------------------
S_LO, S_LI, S_RI, S_RO, S_RUD = 0, 1, 2, 3, 4
S_SLAT0, S_AB_L, S_AB_R = 5, 11, 12
N_SURF = 13

# ---- alpha-table columns (uniform grid; built by build.py) ----------------------------------------------
A_CMA, A_CMDE, A_CMQ, A_EFF, A_CNB, A_CLB, A_CLP, A_CNR, A_CNDA, A_RUDEFF, A_SDCL, A_SDCD, A_SDCM = range(13)
N_ACOLS = 13
# ---- Mach-table columns ---------------------------------------------------------------------------------
M_RP, M_RV, M_DSM, M_CDW, M_K, M_RCTRL, M_RDIR, M_RDAMP, M_DCM0 = range(9)
N_MCOLS = 9

# ---- flat aero parameter vector (``AERO_PARAMS`` names, checked in params.py) -----------------------------
(
    P_S,
    P_B,
    P_C,
    P_CL0,
    P_KP,
    P_KV,
    P_CNMAX,
    P_AFP1,
    P_AFP2,
    P_CM0,
    P_CLQ,
    P_CLDE,
    P_FIB,
    P_CLDIB,
    P_CLDOB,
    P_CYB,
    P_CLDR,
    P_CYDR,
    P_CNDR,
    P_KCLR,
    P_KCNP,
    P_KF,
    P_CDDE,
    P_AIND1,
    P_AIND2,
    P_DCDGEAR,
    P_DCMGEAR,
    P_DCDAB,
    P_DCMAB,
    P_CNAB,
    P_CLSLAT,
    P_SLATMAX0,
    P_SLATMAX1,
    P_SLATMAX2,
    P_ABMAX,
) = range(35)
N_AERO = 35

AERO_PARAM_NAMES = (
    "s_ref",
    "b_ref",
    "c_ref",
    "cl0",
    "kp",
    "kv",
    "cn_max_flat",
    "alpha_flat_lo",
    "alpha_flat_hi",
    "cm0",
    "cl_q",
    "cl_de",
    "frac_pitch_ib",
    "cl_da_ib",
    "cl_da_ob",
    "cy_beta",
    "cl_dr",
    "cy_dr",
    "cn_dr",
    "k_cl_r",
    "k_cn_p",
    "k_friction",
    "cd_de2",
    "alpha_suction_lo",
    "alpha_suction_hi",
    "dcd_gear",
    "dcm_gear",
    "dcd_airbrake",
    "dcm_airbrake",
    "cn_airbrake_asym",
    "cl_slat_asym",
    "slat_max_ob",
    "slat_max_mb",
    "slat_max_ib",
    "airbrake_max",
)


class AeroTables(NamedTuple):
    """Uniform-grid tables fed to the kernels (AD-22: tables as NamedTuples)."""

    a0: float  # alpha grid start, rad
    da: float  # alpha grid step, rad
    atab: np.ndarray  # (n_alpha, N_ACOLS)
    m0: float  # Mach grid start
    dm: float  # Mach grid step
    mtab: np.ndarray  # (n_mach, N_MCOLS)
    cm_ls: np.ndarray  # (n_alpha,) Cm_ls(alpha): integral of A_CMA on the same grid (+ cm0 added in kernel)


@njit(**NJ)
def grid_index(x0, dx, n, x):
    """Index and weight for linear interpolation on a uniform grid, clamped at both ends."""
    s = (x - x0) / dx
    if s <= 0.0:
        return 0, 0.0
    if s >= n - 1:
        return n - 2, 1.0
    i = int(s)
    return i, s - i


@njit(**NJ)
def lerp(tab, i, w, col):
    return tab[i, col] + w * (tab[i + 1, col] - tab[i, col])


@njit(**NJ)
def lerp1(v, i, w):
    return v[i] + w * (v[i + 1] - v[i])


@njit(**NJ)
def smoothstep(x, lo, hi):
    if x <= lo:
        return 0.0
    if x >= hi:
        return 1.0
    t = (x - lo) / (hi - lo)
    return t * t * (3.0 - 2.0 * t)


@njit(**NJ)
def cl_basic(alpha, rp, rv, ap):
    """Lift of the clean wing-body (no controls), Polhamus form blended to a flat plate at high alpha."""
    sa, ca = sin_cos(alpha)
    pol = ap[P_CL0] + ap[P_KP] * rp * sa * ca * ca + ap[P_KV] * rv * ca * sa * abs(sa)
    w = smoothstep(abs(alpha), ap[P_AFP1], ap[P_AFP2])
    flat = ap[P_CNMAX] * sa * ca
    return (1.0 - w) * pol + w * flat, w


@njit(**NJ)
def friction_cd0(reynolds, mach, kf):
    """Skin-friction drag: turbulent flat plate (Prandtl-Schlichting) with the DATCOM/Raymer compressibility
    factor, times a friction-equivalent wetted-area/form factor ``kf`` (calibrated, ASSUMPTION)."""
    re = reynolds if reynolds > 1.0e5 else 1.0e5
    lg = math.log10(re)
    cf = 0.455 / (lg**2.58) / (1.0 + 0.144 * mach * mach) ** 0.65
    return kf * cf


@njit(**NJ)
def aero_coeffs(alpha, beta, mach, phat, qhat, rhat, d, gear_pos, h_over_b, reynolds, ap, tab, out):
    """Body-axis force and moment coefficients about the aero reference point.

    Writes ``out[0:6] = (CX, CY, CZ, Cl, Cm, Cn)`` (body axes; moments: Cl, Cn on span, Cm on chord) and
    ``out[6:9] = (CL, CD, CYw)`` for diagnostics. ``phat = p b / 2V``, ``qhat = q c / 2V``,
    ``rhat = r b / 2V`` (air-relative rates). ``h_over_b``: height of the reference point above ground /
    span (ground effect).
    """
    na = tab.atab.shape[0]
    ia, wa = grid_index(tab.a0, tab.da, na, alpha)
    nm = tab.mtab.shape[0]
    im, wm = grid_index(tab.m0, tab.dm, nm, mach)
    at = tab.atab
    mt = tab.mtab
    rp = lerp(mt, im, wm, M_RP)
    rv = lerp(mt, im, wm, M_RV)
    dsm = lerp(mt, im, wm, M_DSM)
    cdw = lerp(mt, im, wm, M_CDW)
    kind = lerp(mt, im, wm, M_K)
    rctrl = lerp(mt, im, wm, M_RCTRL)
    rdir = lerp(mt, im, wm, M_RDIR)
    rdamp = lerp(mt, im, wm, M_RDAMP)
    dcm0 = lerp(mt, im, wm, M_DCM0)

    cmde = lerp(at, ia, wa, A_CMDE)
    cmq = lerp(at, ia, wa, A_CMQ)
    eff = lerp(at, ia, wa, A_EFF)
    cnb = lerp(at, ia, wa, A_CNB)
    clb = lerp(at, ia, wa, A_CLB)
    clp = lerp(at, ia, wa, A_CLP)
    cnr = lerp(at, ia, wa, A_CNR)
    cnda = lerp(at, ia, wa, A_CNDA)
    rudeff = lerp(at, ia, wa, A_RUDEFF)
    sdcl = lerp(at, ia, wa, A_SDCL)
    sdcd = lerp(at, ia, wa, A_SDCD)
    sdcm = lerp(at, ia, wa, A_SDCM)
    cm_ls = lerp1(tab.cm_ls, ia, wa)

    sa, ca = sin_cos(alpha)
    sb = math.sin(beta)

    # ---- surfaces ---------------------------------------------------------------------------------------
    fib = ap[P_FIB]
    sym = fib * 0.5 * (d[S_LI] + d[S_RI]) + (1.0 - fib) * 0.5 * (d[S_LO] + d[S_RO])
    diff_ib = d[S_LI] - d[S_RI]
    diff_ob = d[S_LO] - d[S_RO]
    drud = d[S_RUD]
    sl_l = (d[5] / ap[P_SLATMAX0] + d[6] / ap[P_SLATMAX1] + d[7] / ap[P_SLATMAX2]) / 3.0
    sl_r = (d[8] / ap[P_SLATMAX2] + d[9] / ap[P_SLATMAX1] + d[10] / ap[P_SLATMAX0]) / 3.0
    slat = 0.5 * (sl_l + sl_r)
    ab_l = d[S_AB_L] / ap[P_ABMAX]
    ab_r = d[S_AB_R] / ap[P_ABMAX]
    ab = 0.5 * (ab_l + ab_r)

    # ---- longitudinal ----------------------------------------------------------------------------------
    clb_basic, wflat = cl_basic(alpha, rp, rv, ap)
    cn_pot = ap[P_KP] * rp * sa * ca  # potential normal-force part (Mach-shifted aerodynamic centre)
    cl_e = ap[P_CLDE] * eff * rctrl * sym
    cl = clb_basic + cl_e + ap[P_CLQ] * rdamp * qhat + sdcl * slat
    cm = (
        ap[P_CM0]
        + dcm0
        + cm_ls
        + dsm * cn_pot
        + cmq * rdamp * qhat
        + cmde * rctrl * sym
        + sdcm * slat
        + ap[P_DCMAB] * ab
        + ap[P_DCMGEAR] * gear_pos
    )

    # drag build-up
    cd0 = friction_cd0(reynolds, mach, ap[P_KF]) + cdw
    x = 16.0 * h_over_b
    phi_ge = x * x / (1.0 + x * x) if h_over_b > 0.0 else 1.0
    w_s = smoothstep(abs(alpha), ap[P_AIND1], ap[P_AIND2])
    dcl = cl - ap[P_CL0]
    cdi = kind * dcl * dcl * phi_ge
    if w_s > 0.0 and wflat < 1.0:  # zero leading-edge suction at high alpha (alpha <= alpha_flat_hi here)
        cdi_hi = cl * math.tan(alpha)
        if cdi_hi < 0.0:
            cdi_hi = 0.0
        cdi = (1.0 - w_s) * cdi + w_s * cdi_hi
    cdi = (1.0 - wflat) * cdi + wflat * (ap[P_CNMAX] * sa * sa)
    lo, li, ri, ro = d[S_LO], d[S_LI], d[S_RI], d[S_RO]
    cd_ctrl = ap[P_CDDE] * (
        lo * lo + li * li + ri * ri + ro * ro + drud * drud
    )  # products, not **2 (see kernel)
    cd = cd0 + cdi + cd_ctrl + sdcd * slat + ap[P_DCDAB] * ab + ap[P_DCDGEAR] * gear_pos

    # ---- lateral-directional (body axes) ------------------------------------------------------------------
    cl_roll_ctrl = (ap[P_CLDIB] * diff_ib + ap[P_CLDOB] * diff_ob) * eff * rctrl
    cy = ap[P_CYB] * rdir * sb + ap[P_CYDR] * rudeff * rdir * drud
    croll = (
        clb * sb
        + cl_roll_ctrl
        + ap[P_CLDR] * rudeff * rdir * drud
        + clp * rdamp * phat
        + ap[P_KCLR] * cl * rhat
        + ap[P_CLSLAT] * (sl_l - sl_r)
    )
    cn = (
        cnb * rdir * sb
        + cnda * cl_roll_ctrl
        + ap[P_CNDR] * rudeff * rdir * drud
        + ap[P_KCNP] * cl * phat
        + cnr * rdamp * rhat
        + ap[P_CNAB] * (ab_l - ab_r)
    )

    # stability axes -> body axes (drag along stability x, lift normal to it; side force on body y)
    out[0] = -cd * ca + cl * sa
    out[1] = cy
    out[2] = -cd * sa - cl * ca
    out[3] = croll
    out[4] = cm
    out[5] = cn
    out[6] = cl
    out[7] = cd
    out[8] = cy


# ---- hinge moments (M05 actuator loads) ------------------------------------------------------------------
# per-surface hinge-moment parameters, rows = 13 surfaces: (ch0, ch_alpha, ch_beta, ch_delta, area, chord)
H_CH0, H_CHA, H_CHB, H_CHD, H_AREA, H_CHORD = range(6)
N_HCOLS = 6


@njit(**NJ)
def hinge_moments(alpha, beta, qbar, d, htab, out):
    """Aerodynamic hinge moment per surface (N m), positive in the surface's positive-deflection sense.

    ``Ch = ch0 + ch_alpha*alpha + ch_beta*beta + ch_delta*delta``; ``H = Ch qbar S_s c_s``. Only the rudder
    row carries a ``ch_beta`` term (``build.hinge_table``). Pure products: complex-step safe (M05 actuators).
    """
    for s in range(d.shape[0]):
        ch = htab[s, H_CH0] + htab[s, H_CHA] * alpha + htab[s, H_CHB] * beta + htab[s, H_CHD] * d[s]
        out[s] = ch * qbar * htab[s, H_AREA] * htab[s, H_CHORD]
