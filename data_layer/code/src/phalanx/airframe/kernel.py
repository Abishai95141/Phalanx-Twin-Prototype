"""M06 airframe kernel (AD-22): quaternion 6-DOF on a rotating WGS-84 Earth, ground model, outputs.

One ``@njit`` function ``airframe_kernel(f, i, dp, ap, tab, gtab, ttab, u[L, nu], dt, n_eng, mode)`` advances
``L`` truth ticks. ``step`` is ``step_block`` with ``L = 1`` (bitwise identical by construction) and the NumPy
reference is the same source uncompiled (``airframe_kernel.py_func``).

**Equations of motion** (ECEF formulation; Stevens & Lewis §1.6 form; A-W1.2-2):

    r_e' = v_e                                             (v_e: velocity relative to Earth, ECEF axes)
    v_e' = C_eb f_b + g(r_e) - 2 Omega x v_e               (g: J2 gravitation + centrifugal)
    q_eb' = 1/2 q_eb * (0, w_ib - C_be Omega)              (body -> ECEF attitude quaternion)
    J w_ib' = M_b - w_ib x J w_ib                          (about the CG; J from util.inertia, J' ignored)

integrated by classical RK4 with ``n_sub`` sub-steps per 240 Hz tick: ``n_sub_air`` away from the ground and
``n_sub_ground`` when the reference point is within ``prox_height`` of the runway (stiffer gear dynamics). The
quaternion is renormalised after every sub-step. Inputs (surfaces, thrust, mass properties, atmosphere,
turbulence) are held over the tick (zero-order hold, AD-36).

**Ground model** (three legs: nose, left main, right main; A-W1.2-10): massless strut+tyre spring-damper
along the local vertical (``k1 d + k3 d^3 + c d'``, unilateral), wheel no-slip rolling with an
anti-skid-capped brake force (``PROXY``: tyre longitudinal slip dynamics are not modelled), lateral force
with a saturating cornering law, WoW when the compression exceeds ``wow_threshold``. Wheel speed relaxes
exactly (exponential, outside RK4) to ground speed / rolling radius in contact, spins down in the air. Brake
energy rate = brake force x contact ground speed (the power the brake absorbs under anti-skid control).

``mode`` (int): 0 = Tejas (aero + thrust + gear + chute); 1 = ballistic sphere with drag area ``sphere_cda``;
2 = no forces (vacuum); 3 = no forces, linear damping torque ``-brick_damping * w`` (NESC-style check cases).
"""

from __future__ import annotations

import math

import numpy as np
from numba import njit

from .aero import N_SURF, aero_coeffs
from .geodesy import NJ, dcm_ne, ecef_to_geodetic, gravity_ecef, q_en, q_to_dcm, qmul

# ---- state layout (float vector f / int vector i) --------------------------------------------------------
F_RX, F_RY, F_RZ, F_VX, F_VY, F_VZ, F_Q0, F_Q1, F_Q2, F_Q3, F_WX, F_WY, F_WZ = range(13)
F_GEAR, F_WHL, F_WHR, F_HGND = range(13, 17)
# AD-48.4 (W2.1c): af.fault_inject severities, one per (mode, leg): 0 = healthy, 1 = full effect. Modes in
# AF_FAULT_MODES order, legs nose / left main / right main; set only by events (state perturbations, I6).
AF_FAULT_MODES = ("tyre_burst", "strut_extension_failure", "gear_collapse_on_touchdown", "runway_excursion")
FM_BURST, FM_FROZEN, FM_COLLAPSE, FM_SOFT = range(4)
F_FLT0 = 17
N_F = F_FLT0 + 3 * len(AF_FAULT_MODES)
I_TICK, I_NSUB = 0, 1
N_I = 2
FLOAT_NAMES = (
    "rx",
    "ry",
    "rz",
    "vx",
    "vy",
    "vz",
    "q0",
    "q1",
    "q2",
    "q3",
    "wx",
    "wy",
    "wz",
    "gear_pos",
    "wheel_l",
    "wheel_r",
    "h_ground",
    *(f"flt_{m}_{leg}" for m in ("burst", "frozen", "collapse", "soft") for leg in ("n", "l", "r")),
)
INT_NAMES = ("tick", "n_sub_last")
N_X = 13  # RK4-integrated part of f

# ---- dynamics parameter vector -----------------------------------------------------------------------------
DYN_PARAM_NAMES = (
    "earth_a",
    "earth_f",
    "earth_omega",
    "earth_gm",
    "earth_j2",
    "g0",
    "mu_roll",
    "mu_brake_max",
    "mu_lat",
    "k_corner",
    "v_eps",
    "v0_lat",
    "brake_torque_max",
    "r_roll",
    "wheel_tau_spin",
    "wheel_tau_air",
    "wow_threshold",
    "gear_t_ext",
    "prox_height",
    "keel_x",
    "keel_z",
    "keel_k",
    "keel_c",
    "keel_mu",
    "chute_cds",
    "sphere_cda",
    "brick_damping",
    "n_sub_air",
    "n_sub_ground",
    "brake_torque_gain",
    "brake_p_max",
    "brake_hyd_system",
    "rim_radius",
    "mu_rim",
    "grip_rim",
    "frozen_stroke",
    "k_frozen",
    "mu_soft",
    "grip_soft",
    "mu_brake_static",
    "v_antiskid",
)
(
    D_A,
    D_F,
    D_OM,
    D_GM,
    D_J2,
    D_G0,
    D_MUR,
    D_MUB,
    D_MUL,
    D_KCOR,
    D_VEPS,
    D_V0L,
    D_TBMAX,
    D_RROLL,
    D_TAUSPIN,
    D_TAUAIR,
    D_WOWTH,
    D_TEXT,
    D_PROX,
    D_KEELX,
    D_KEELZ,
    D_KEELK,
    D_KEELC,
    D_KEELMU,
    D_CHUTE,
    D_SPHCDA,
    D_BRICKC,
    D_NSUBA,
    D_NSUBG,
    D_BRKGAIN,
    D_BRKPMAX,
    D_BRKSYS,
    D_RIM,
    D_MURIM,
    D_GRIPRIM,
    D_FROZEN,
    D_KFROZEN,
    D_MUSOFT,
    D_GRIPSOFT,
    D_MUBS,
    D_VAS,
) = range(41)
N_DYN = 41

# gear table rows: nose, left main, right main; columns:
G_X, G_Y, G_Z, G_LEXT, G_K1, G_K3, G_C, G_MAIN = range(8)
N_GCOLS = 8
# thrust table rows: engines; columns: point x, y, z (relative to the reference point), axis x, y, z (unit)
T_PX, T_PY, T_PZ, T_AX, T_AY, T_AZ = range(6)

# ---- input columns ---------------------------------------------------------------------------------------
U_SURF = 0
U_THR = N_SURF
# columns after the thrust block (offset o = N_SURF + n_eng): mass 0, cg 1-3, inertia 4-12, rho 13, a 14,
# T 15, wind 16-18, turbulence velocity 19-21 and rate 22-24, gear handle 25, and (AD-47, W2.1c) the pilot's
# toe brakes L/R 26-27 (pilot.brake_cmd), the M09 chute state 28 (util.chute_state) and the hydraulic system
# pressures 29-30 (util.hyd_p, gauge Pa) of which the brake system's limits the brake torque
U_BRAKE, U_CHUTE, U_HYDP = 26, 28, 29


def input_width(n_eng: int) -> int:
    return N_SURF + n_eng + 31


@njit(**NJ)
def _uoff(n_eng):
    return N_SURF + n_eng  # first column after thrust (mass)


# ---- outputs ---------------------------------------------------------------------------------------------
(
    O_LAT,
    O_LON,
    O_H,
    O_ALT,
    O_VN,
    O_VE,
    O_VD,
    O_QN0,
    O_QN1,
    O_QN2,
    O_QN3,
    O_WX,
    O_WY,
    O_WZ,
    O_FX,
    O_FY,
    O_FZ,
    O_ALPHA,
    O_BETA,
    O_TAS,
    O_MACH,
    O_QBAR,
    O_NZ,
    O_WOW0,
    O_WOW1,
    O_WOW2,
    O_WHL,
    O_WHR,
    O_PBL,
    O_PBR,
    O_HAG,
) = range(31)
N_OUT = 31

# auxiliary vector written by _forces
X_ALPHA, X_BETA, X_TAS, X_MACH, X_QBAR, X_FSX, X_FSY, X_FSZ = range(8)
X_WOW0, X_WOW1, X_WOW2, X_PBL, X_PBR, X_VGL, X_VGR, X_LAT, X_LON, X_H, X_HAGL = range(8, 19)
N_AUX = 19


@njit(**NJ)
def _inv3(m, out):
    a, b, c = m[0, 0], m[0, 1], m[0, 2]
    d, e, f = m[1, 0], m[1, 1], m[1, 2]
    g, h, k = m[2, 0], m[2, 1], m[2, 2]
    c00 = e * k - f * h
    c01 = -(d * k - f * g)
    c02 = d * h - e * g
    det = a * c00 + b * c01 + c * c02
    inv = 1.0 / det
    out[0, 0] = c00 * inv
    out[0, 1] = -(b * k - c * h) * inv
    out[0, 2] = (b * f - c * e) * inv
    out[1, 0] = c01 * inv
    out[1, 1] = (a * k - c * g) * inv
    out[1, 2] = -(a * f - c * d) * inv
    out[2, 0] = c02 * inv
    out[2, 1] = -(a * h - b * g) * inv
    out[2, 2] = (a * e - b * d) * inv


@njit(**NJ)
def _forces(x, uj, gear_pos, h_gnd, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux):
    """Total external force (N, body axes) and moment about the CG (N m, body axes) -> ws.fm[0:6]."""
    ceb, cne, cnb, coef = ws[0], ws[1], ws[2], ws[4]
    fm = ws[5]
    o = N_SURF + n_eng
    mass = uj[o]
    cgx, cgy, cgz = uj[o + 1], uj[o + 2], uj[o + 3]
    rho = uj[o + 13]
    a_snd = uj[o + 14]
    t_s = uj[o + 15]
    a_e, f_e = dp[D_A], dp[D_F]
    lat, lon, h = ecef_to_geodetic(x[F_RX], x[F_RY], x[F_RZ], a_e, f_e)
    q_to_dcm(x[F_Q0], x[F_Q1], x[F_Q2], x[F_Q3], ceb)
    dcm_ne(lat, lon, cne)
    for r in range(3):  # C_nb = C_ne C_eb
        for c in range(3):
            cnb[r, c] = cne[r, 0] * ceb[0, c] + cne[r, 1] * ceb[1, c] + cne[r, 2] * ceb[2, c]
    vn = cne[0, 0] * x[F_VX] + cne[0, 1] * x[F_VY] + cne[0, 2] * x[F_VZ]
    ve = cne[1, 0] * x[F_VX] + cne[1, 1] * x[F_VY] + cne[1, 2] * x[F_VZ]
    vd = cne[2, 0] * x[F_VX] + cne[2, 1] * x[F_VY] + cne[2, 2] * x[F_VZ]
    # Earth-relative body rate (aero and contact kinematics)
    om = dp[D_OM]
    wex = x[F_WX] - ceb[2, 0] * om
    wey = x[F_WY] - ceb[2, 1] * om
    wez = x[F_WZ] - ceb[2, 2] * om
    # air-relative velocity in body axes
    an = vn - uj[o + 16]
    ae = ve - uj[o + 17]
    ad = vd - uj[o + 18]
    ub = cnb[0, 0] * an + cnb[1, 0] * ae + cnb[2, 0] * ad - uj[o + 19]
    vb = cnb[0, 1] * an + cnb[1, 1] * ae + cnb[2, 1] * ad - uj[o + 20]
    wb = cnb[0, 2] * an + cnb[1, 2] * ae + cnb[2, 2] * ad - uj[o + 21]
    vt = math.sqrt(ub * ub + vb * vb + wb * wb)
    qbar = 0.5 * rho * vt * vt
    mach = vt / a_snd
    if vt > 1.0e-6:
        alpha = math.atan2(wb, ub)
        sbeta = vb / vt
        if sbeta > 1.0:
            sbeta = 1.0
        if sbeta < -1.0:
            sbeta = -1.0
        beta = math.asin(sbeta)
    else:
        alpha = 0.0
        beta = 0.0
    fx = 0.0
    fy = 0.0
    fz = 0.0
    mx = 0.0
    my = 0.0
    mz = 0.0
    h_agl = h - h_gnd
    for k in range(N_AUX):
        aux[k] = 0.0
    if mode == 0:
        # ---- aerodynamics about the reference point, transferred to the CG -------------------------------
        if vt > 1.0e-3:
            v2 = 2.0 * vt
            pa = wex - uj[o + 22]
            qa = wey - uj[o + 23]
            ra = wez - uj[o + 24]
            b = ap[1]
            cbar = ap[2]
            mu = 1.458e-6 * t_s**1.5 / (t_s + 110.4)  # Sutherland (USSA-76)
            rey = rho * vt * cbar / mu
            hob = h_agl / b if h_agl > 0.0 else 1.0e3
            aero_coeffs(
                alpha,
                beta,
                mach,
                pa * b / v2,
                qa * cbar / v2,
                ra * b / v2,
                uj[0:N_SURF],
                gear_pos,
                hob,
                rey,
                ap,
                tab,
                coef,
            )
            qs = qbar * ap[0]
            fax, fay, faz = qs * coef[0], qs * coef[1], qs * coef[2]
            fx += fax
            fy += fay
            fz += faz
            mx += qs * b * coef[3] - (cgy * faz - cgz * fay)
            my += qs * cbar * coef[4] - (cgz * fax - cgx * faz)
            mz += qs * b * coef[5] - (cgx * fay - cgy * fax)
            chute = uj[o + U_CHUTE]  # util.chute_state: 1 = streamed (M09 owns limits and failures)
            if chute > 0.5 and chute < 1.5:
                fc = qbar * dp[D_CHUTE] / vt  # drag along -v_air, applied at the reference point
                fx -= fc * ub
                fy -= fc * vb
                fz -= fc * wb
        # ---- thrust ----------------------------------------------------------------------------------
        for e in range(n_eng):
            t = uj[N_SURF + e]
            tx, ty, tz = t * ttab[e, 3], t * ttab[e, 4], t * ttab[e, 5]
            rx, ry, rz = ttab[e, 0] - cgx, ttab[e, 1] - cgy, ttab[e, 2] - cgz
            fx += tx
            fy += ty
            fz += tz
            mx += ry * tz - rz * ty
            my += rz * tx - rx * tz
            mz += rx * ty - ry * tx
        # ---- ground contact (gear legs when locked, keel otherwise) ------------------------------------
        if h_agl < dp[D_PROX]:
            # heading of the body x axis in the ground plane
            hx, hy = cnb[0, 0], cnb[1, 0]
            hn = math.sqrt(hx * hx + hy * hy)
            if hn > 1.0e-9:
                hx /= hn
                hy /= hn
            else:
                hx, hy = 1.0, 0.0
            locked = gear_pos > 0.999
            nleg = 3 if locked else 1
            for g in range(nleg):
                grip = 1.0
                if locked and flt[FM_COLLAPSE * 3 + g] > 0.5:
                    # AD-48.4 gear collapse: the leg folded; the structure at its attach point meets the
                    # runway with the belly-contact properties (PROXY A-W2.1c-2: no wing-tip contact)
                    px = gtab[g, 0] - cgx
                    py = gtab[g, 1] - cgy
                    pz = gtab[g, 2] - cgz
                    k1, k3, cc = dp[D_KEELK], 0.0, dp[D_KEELC]
                    is_main = False
                    mu_lat = dp[D_KEELMU]
                    mu_long = dp[D_KEELMU]
                elif locked:
                    sb = flt[FM_BURST * 3 + g]  # burst tyre: rolls on the rim
                    sf = flt[FM_FROZEN * 3 + g]  # ice-locked strut: stays compressed, near-rigid
                    ss = flt[FM_SOFT * 3 + g]  # runway excursion: unprepared ground
                    ext = gtab[g, 3] - sb * (dp[D_RROLL] - dp[D_RIM]) - sf * dp[D_FROZEN]
                    px = gtab[g, 0] - cgx
                    py = gtab[g, 1] - cgy
                    pz = gtab[g, 2] + ext - cgz
                    km = 1.0 + sf * (dp[D_KFROZEN] - 1.0)
                    k1, k3, cc = gtab[g, 4] * km, gtab[g, 5] * km, gtab[g, 6] * km
                    is_main = gtab[g, 7] > 0.5
                    grip = (1.0 - sb * (1.0 - dp[D_GRIPRIM])) * (1.0 - ss * (1.0 - dp[D_GRIPSOFT]))
                    mu_lat = dp[D_MUL] * grip
                    mu_long = dp[D_MUR] + sb * dp[D_MURIM] + ss * dp[D_MUSOFT]
                else:
                    px = dp[D_KEELX] - cgx
                    py = -cgy
                    pz = dp[D_KEELZ] - cgz
                    k1, k3, cc = dp[D_KEELK], 0.0, dp[D_KEELC]
                    is_main = False
                    mu_lat = dp[D_KEELMU]
                    mu_long = dp[D_KEELMU]
                # contact point offset in NED and its Earth-relative velocity
                dd = cnb[2, 0] * px + cnb[2, 1] * py + cnb[2, 2] * pz
                wxp_x = wey * pz - wez * py
                wxp_y = wez * px - wex * pz
                wxp_z = wex * py - wey * px
                cvn = vn + cnb[0, 0] * wxp_x + cnb[0, 1] * wxp_y + cnb[0, 2] * wxp_z
                cve = ve + cnb[1, 0] * wxp_x + cnb[1, 1] * wxp_y + cnb[1, 2] * wxp_z
                cvd = vd + cnb[2, 0] * wxp_x + cnb[2, 1] * wxp_y + cnb[2, 2] * wxp_z
                pen = h_gnd - (h - dd)  # penetration of the contact point below the runway plane
                if pen <= 0.0:
                    continue
                if locked and pen > dp[D_WOWTH]:
                    aux[X_WOW0 + g] = 1.0
                fnorm = k1 * pen + k3 * pen * pen * pen + cc * cvd
                if fnorm <= 0.0:
                    continue
                u_c = cvn * hx + cve * hy
                v_c = -cvn * hy + cve * hx
                th = math.tanh(u_c / dp[D_VEPS])
                f_long = -mu_long * fnorm * th
                if is_main:
                    brk = uj[o + U_BRAKE + g - 1]  # pilot.brake_cmd, 0..1 (AD-47)
                    brk = 0.0 if brk < 0.0 else (1.0 if brk > 1.0 else brk)
                    # torque available from the brake system's supply (AD-47, A-W1.4-32): gain x metered
                    # pressure, capped by the brake's own maximum torque
                    p_sup = uj[o + U_HYDP + int(dp[D_BRKSYS])]
                    p_sup = 0.0 if p_sup < 0.0 else p_sup
                    p_met = p_sup if p_sup < dp[D_BRKPMAX] else dp[D_BRKPMAX]
                    t_av = dp[D_BRKGAIN] * p_met
                    t_av = t_av if t_av < dp[D_TBMAX] else dp[D_TBMAX]
                    fb_dem = brk * t_av / dp[D_RROLL]
                    # W2.1a take-off fix (A-W2.1-8): the anti-skid limit (D_MUB) regulates the slip of a
                    # rolling wheel; a stopped or slow wheel under brake holds up to the tyre's static
                    # friction (anti-skid inactive below v_antiskid; linear blend in between)
                    mu_b = dp[D_MUB]
                    au = abs(u_c)
                    if au < dp[D_VAS]:
                        mu_b = dp[D_MUBS] + (dp[D_MUB] - dp[D_MUBS]) * (au / dp[D_VAS])
                    fb_cap = mu_b * grip * fnorm
                    fb = fb_dem if fb_dem < fb_cap else fb_cap
                    f_long -= fb * th
                    aux[X_PBL + g - 1] = abs(fb * th * u_c)
                    aux[X_VGL + g - 1] = u_c
                arg = dp[D_KCOR] * v_c / (mu_lat * (abs(u_c) + dp[D_V0L]))
                f_lat = -mu_lat * fnorm * math.tanh(arg)
                gn = f_long * hx - f_lat * hy
                ge = f_long * hy + f_lat * hx
                gd = -fnorm
                gbx = cnb[0, 0] * gn + cnb[1, 0] * ge + cnb[2, 0] * gd
                gby = cnb[0, 1] * gn + cnb[1, 1] * ge + cnb[2, 1] * gd
                gbz = cnb[0, 2] * gn + cnb[1, 2] * ge + cnb[2, 2] * gd
                fx += gbx
                fy += gby
                fz += gbz
                mx += py * gbz - pz * gby
                my += pz * gbx - px * gbz
                mz += px * gby - py * gbx
    elif mode == 1:
        if vt > 1.0e-9:
            fc = qbar * dp[D_SPHCDA] / vt
            fx -= fc * ub
            fy -= fc * vb
            fz -= fc * wb
    elif mode == 3:
        c = dp[D_BRICKC]
        mx -= c * x[F_WX]
        my -= c * x[F_WY]
        mz -= c * x[F_WZ]
    fm[0] = fx
    fm[1] = fy
    fm[2] = fz
    fm[3] = mx
    fm[4] = my
    fm[5] = mz
    aux[X_ALPHA] = alpha
    aux[X_BETA] = beta
    aux[X_TAS] = vt
    aux[X_MACH] = mach
    aux[X_QBAR] = qbar
    aux[X_FSX] = fx / mass
    aux[X_FSY] = fy / mass
    aux[X_FSZ] = fz / mass
    aux[X_LAT] = lat
    aux[X_LON] = lon
    aux[X_H] = h
    aux[X_HAGL] = h_agl


@njit(**NJ)
def _deriv(x, uj, gear_pos, h_gnd, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux, xd):
    _forces(x, uj, gear_pos, h_gnd, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux)
    ceb, jm, jinv, fm = ws[0], ws[3], ws[6], ws[5]
    mass = uj[N_SURF + n_eng]
    om = dp[D_OM]
    # translational (ECEF)
    fsx, fsy, fsz = fm[0] / mass, fm[1] / mass, fm[2] / mass
    gx, gy, gz = gravity_ecef(x[F_RX], x[F_RY], x[F_RZ], dp[D_GM], dp[D_A], dp[D_J2], om)
    xd[F_RX] = x[F_VX]
    xd[F_RY] = x[F_VY]
    xd[F_RZ] = x[F_VZ]
    xd[F_VX] = ceb[0, 0] * fsx + ceb[0, 1] * fsy + ceb[0, 2] * fsz + gx + 2.0 * om * x[F_VY]
    xd[F_VY] = ceb[1, 0] * fsx + ceb[1, 1] * fsy + ceb[1, 2] * fsz + gy - 2.0 * om * x[F_VX]
    xd[F_VZ] = ceb[2, 0] * fsx + ceb[2, 1] * fsy + ceb[2, 2] * fsz + gz
    # attitude: q_eb' = 1/2 q_eb (0, w_eb)
    wex = x[F_WX] - ceb[2, 0] * om
    wey = x[F_WY] - ceb[2, 1] * om
    wez = x[F_WZ] - ceb[2, 2] * om
    d0, d1, d2, d3 = qmul(x[F_Q0], x[F_Q1], x[F_Q2], x[F_Q3], 0.0, wex, wey, wez)
    xd[F_Q0] = 0.5 * d0
    xd[F_Q1] = 0.5 * d1
    xd[F_Q2] = 0.5 * d2
    xd[F_Q3] = 0.5 * d3
    # rotational (about the CG): J w' = M - w x J w   (J, J^-1 set once per tick by _set_inertia)
    wx, wy, wz = x[F_WX], x[F_WY], x[F_WZ]
    hx = jm[0, 0] * wx + jm[0, 1] * wy + jm[0, 2] * wz
    hy = jm[1, 0] * wx + jm[1, 1] * wy + jm[1, 2] * wz
    hz = jm[2, 0] * wx + jm[2, 1] * wy + jm[2, 2] * wz
    tx = fm[3] - (wy * hz - wz * hy)
    ty = fm[4] - (wz * hx - wx * hz)
    tz = fm[5] - (wx * hy - wy * hx)
    xd[F_WX] = jinv[0, 0] * tx + jinv[0, 1] * ty + jinv[0, 2] * tz
    xd[F_WY] = jinv[1, 0] * tx + jinv[1, 1] * ty + jinv[1, 2] * tz
    xd[F_WZ] = jinv[2, 0] * tx + jinv[2, 1] * ty + jinv[2, 2] * tz


@njit(**NJ)
def _set_inertia(uj, n_eng, ws):
    jm, jinv = ws[3], ws[6]
    o = N_SURF + n_eng
    for r in range(3):
        for c in range(3):
            jm[r, c] = uj[o + 4 + 3 * r + c]
    _inv3(jm, jinv)


@njit(**NJ)
def _workspace(dtype):
    ws = (
        np.empty((3, 3), dtype),  # C_eb
        np.empty((3, 3), dtype),  # C_ne
        np.empty((3, 3), dtype),  # C_nb
        np.empty((3, 3), dtype),  # J
        np.empty(9, dtype),  # aero coefficients
        np.empty(6, dtype),  # force/moment
        np.empty((3, 3), dtype),  # J^-1
    )
    return ws


@njit(**NJ)
def _write_out(x, f, aux, cne, dp, orow):
    """Outputs at the end of a tick from the integrated state ``x``, the discrete state ``f`` and ``aux``."""
    lat, lon = aux[X_LAT], aux[X_LON]
    orow[O_LAT] = lat
    orow[O_LON] = lon
    orow[O_H] = aux[X_H]
    orow[O_ALT] = aux[X_H]
    orow[O_VN] = cne[0, 0] * x[F_VX] + cne[0, 1] * x[F_VY] + cne[0, 2] * x[F_VZ]
    orow[O_VE] = cne[1, 0] * x[F_VX] + cne[1, 1] * x[F_VY] + cne[1, 2] * x[F_VZ]
    orow[O_VD] = cne[2, 0] * x[F_VX] + cne[2, 1] * x[F_VY] + cne[2, 2] * x[F_VZ]
    a0, a1, a2, a3 = q_en(lat, lon)
    n0, n1, n2, n3 = qmul(a0, -a1, -a2, -a3, x[F_Q0], x[F_Q1], x[F_Q2], x[F_Q3])
    orow[O_QN0] = n0
    orow[O_QN1] = n1
    orow[O_QN2] = n2
    orow[O_QN3] = n3
    orow[O_WX] = x[F_WX]
    orow[O_WY] = x[F_WY]
    orow[O_WZ] = x[F_WZ]
    orow[O_FX] = aux[X_FSX]
    orow[O_FY] = aux[X_FSY]
    orow[O_FZ] = aux[X_FSZ]
    orow[O_ALPHA] = aux[X_ALPHA]
    orow[O_BETA] = aux[X_BETA]
    orow[O_TAS] = aux[X_TAS]
    orow[O_MACH] = aux[X_MACH]
    orow[O_QBAR] = aux[X_QBAR]
    orow[O_NZ] = -aux[X_FSZ] / dp[D_G0]
    orow[O_WOW0] = aux[X_WOW0]
    orow[O_WOW1] = aux[X_WOW1]
    orow[O_WOW2] = aux[X_WOW2]
    orow[O_WHL] = f[F_WHL]
    orow[O_WHR] = f[F_WHR]
    orow[O_PBL] = aux[X_PBL]
    orow[O_PBR] = aux[X_PBR]
    orow[O_HAG] = aux[X_HAGL]


@njit(**NJ)
def airframe_outputs(f, dp, ap, tab, gtab, ttab, uj, n_eng, mode):
    """Outputs of a state for one input row without stepping (``initial_outputs``, trim and analysis)."""
    ws = _workspace(np.float64)
    aux = np.empty(N_AUX, dtype=np.float64)
    x = f[0:N_X].copy()
    _set_inertia(uj, n_eng, ws)
    _forces(
        x,
        uj,
        f[F_GEAR],
        f[F_HGND],
        f[F_FLT0:],
        dp,
        ap,
        tab,
        gtab,
        ttab,
        n_eng,
        mode,
        ws,
        aux,
    )
    orow = np.empty(N_OUT, dtype=np.float64)
    _write_out(x, f, aux, ws[1], dp, orow)
    return orow


@njit(**NJ)
def airframe_derivative(f, dp, ap, tab, gtab, ttab, uj, n_eng, mode):
    """Time derivative of the 13 integrated states plus the auxiliary vector (trim, linearisation, tests)."""
    ws = _workspace(np.float64)
    aux = np.empty(N_AUX, dtype=np.float64)
    x = f[0:N_X].copy()
    xd = np.empty(N_X, dtype=np.float64)
    _set_inertia(uj, n_eng, ws)
    _deriv(
        x,
        uj,
        f[F_GEAR],
        f[F_HGND],
        f[F_FLT0:],
        dp,
        ap,
        tab,
        gtab,
        ttab,
        n_eng,
        mode,
        ws,
        aux,
        xd,
    )
    return xd, aux


@njit(**NJ)
def airframe_kernel(f, i, dp, ap, tab, gtab, ttab, u, dt, n_eng, mode):
    """Advance ``L = u.shape[0]`` ticks. Pure: returns new ``f``, ``i`` and ``out[L, N_OUT]``."""
    f = f.copy()
    i = i.copy()
    n = u.shape[0]
    out = np.empty((n, N_OUT), dtype=np.float64)
    ws = _workspace(np.float64)
    aux = np.empty(N_AUX, dtype=np.float64)
    x = f[0:N_X].copy()
    k1 = np.empty(N_X, dtype=np.float64)
    k2 = np.empty(N_X, dtype=np.float64)
    k3 = np.empty(N_X, dtype=np.float64)
    k4 = np.empty(N_X, dtype=np.float64)
    xt = np.empty(N_X, dtype=np.float64)
    o = N_SURF + n_eng
    for j in range(n):
        uj = u[j]
        gear = f[F_GEAR]
        hg = f[F_HGND]
        flt = f[F_FLT0:]  # fault severities: constant within the block
        _lat0, _lon0, h0 = ecef_to_geodetic(x[F_RX], x[F_RY], x[F_RZ], dp[D_A], dp[D_F])
        near = mode == 0 and (h0 - hg) < dp[D_PROX]
        n_sub = int(dp[D_NSUBG]) if near else int(dp[D_NSUBA])
        hs = dt / n_sub
        _set_inertia(uj, n_eng, ws)
        for _s in range(n_sub):
            _deriv(x, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux, k1)
            for m in range(N_X):
                xt[m] = x[m] + 0.5 * hs * k1[m]
            _deriv(xt, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux, k2)
            for m in range(N_X):
                xt[m] = x[m] + 0.5 * hs * k2[m]
            _deriv(xt, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux, k3)
            for m in range(N_X):
                xt[m] = x[m] + hs * k3[m]
            _deriv(xt, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux, k4)
            for m in range(N_X):
                x[m] = x[m] + hs / 6.0 * (k1[m] + 2.0 * k2[m] + 2.0 * k3[m] + k4[m])
            # explicit products: Numba lowers x**2 to x*x but interpreted Python calls pow(), not always
            # correctly rounded on darwin libm (W1.2 finding) - products keep compiled == reference bitwise
            qn = math.sqrt(x[F_Q0] * x[F_Q0] + x[F_Q1] * x[F_Q1] + x[F_Q2] * x[F_Q2] + x[F_Q3] * x[F_Q3])
            x[F_Q0] /= qn
            x[F_Q1] /= qn
            x[F_Q2] /= qn
            x[F_Q3] /= qn
        # ---- discrete / kinematic updates at the end of the tick ------------------------------------
        _forces(x, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux)
        wow_any = aux[X_WOW0] + aux[X_WOW1] + aux[X_WOW2] > 0.5
        cmd = uj[o + 25]
        if mode == 0:
            step = dt / dp[D_TEXT]
            if cmd > 0.5:
                gear = gear + step if gear + step < 1.0 else 1.0
            elif not wow_any:  # retraction inhibited with weight on wheels (A-W1.2-11)
                gear = gear - step if gear - step > 0.0 else 0.0
        # wheel spin: exact first-order relaxation toward ground speed / rolling radius
        for side in range(2):
            fi = F_WHL + side
            if aux[X_WOW1 + side] > 0.5:
                target = aux[X_VGL + side] / dp[D_RROLL]
                f[fi] = target + (f[fi] - target) * math.exp(-dt / dp[D_TAUSPIN])
            else:
                f[fi] = f[fi] * math.exp(-dt / dp[D_TAUAIR])
        if gear != f[F_GEAR]:  # gear moved: forces at t_{k+1} with the new gear position
            _forces(x, uj, gear, hg, flt, dp, ap, tab, gtab, ttab, n_eng, mode, ws, aux)
        f[F_GEAR] = gear
        i[I_TICK] += 1
        i[I_NSUB] = n_sub
        _write_out(x, f, aux, ws[1], dp, out[j])
    for m in range(N_X):
        f[m] = x[m]
    return f, i, out


def kernel_reference(f, i, dp, ap, tab, gtab, ttab, u, dt, n_eng, mode):
    """NumPy reference: the same source, uncompiled (identical to ``NUMBA_DISABLE_JIT=1``)."""
    return airframe_kernel.py_func(f, i, dp, ap, tab, gtab, ttab, u, dt, n_eng, mode)
