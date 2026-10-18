"""Fuel tank network, free-surface geometry, slosh, transfer, fuel heat sink and mass properties (M09).

Evidence: note tejas_utility_systems.md KQ3 and Synthesis (b)-(d); report §1 (Fuel row) and §3 (coupling map:
"Pitch, Nx, Nz, slosh -> indicated fuel, low-fuel warning"); ADA AR 2017-18/2018-19 (zoom-climb artefact,
F1A pick-up and vent modification); MIL-F-17874B (feed tanks); Gripen practice (fuel algebraic, low-order
dynamics; ICAS 2006-039).

**AD-42:** M09 owns the *true* tank quantities, transfer, feed, burn, fuel as a heat sink and the tank
geometry parameters. The capacitance-gauge measurement and the false low-fuel warning are M12's (sensor
physics on attitude and acceleration); M09 implements no gauge. The tank table (incl. probe stations,
``tank_probe``) is published for M12's geometry-based gauge.

**Free surface.** Fuel settles normal to the specific force. In the pitch plane the surface slope (rise per
metre towards the aft wall) is ``s* = f_x / max(-f_z, g_min)``: nose-up attitude and forward acceleration
both drive fuel aft (``f_x > 0``), a pull-up (larger ``-f_z``) flattens it, unloading steepens it. A lumped
first sloshing mode (second order, ``slosh_omega``, ``slosh_zeta``) makes the actual slope ``s`` lag ``s*``.
Each tank is a rectangular box (length ``L`` along x, height ``H``); the fluid cross-section ``a = V H L /
cap`` is solved for the surface intercept ``c`` (depth at the aft wall) with the floor and ceiling clipped, by
a fixed-count Newton iteration (complex-step safe). Depth at any station ``d`` from the aft wall is
``clip(c - s d, 0, H)``. PROXY: the geometry is one-dimensional (pitch plane only); roll-plane tilt is not
represented (A-W1.4-15; exposing test ``test_utilities_fuel.py::test_roll_plane_tilt_not_represented``).

**Transfer (ECFM-like).** The engine burns from the collector F2. F1 and F2 are interconnected (fill
fractions equalise with ``fuel_tau_ic``). A level controller tops F2 up from the highest-priority non-empty
group: centreline drop tank -> inboard drop tanks -> wing tanks -> F1A (group column of the tank table).
Each source delivers through its pick-up; the pick-up **wetness** ``clip(depth_at_pickup / band, 0, 1)``
throttles the flow. Pre-modification the F1A pick-up sits at the forward end of the tank (A-W1.4-14), so at
high aft slope and low F1A contents transfer stalls while the ECFM keeps F1A selected (its probe still shows
fuel): F2 drains at the burn rate and fuel is stranded in F1A. This is the true-quantity side of the
zoom-climb case (ADA's fix was a pick-up and vent modification in F1A); the F1A modification moves the pick-up
aft. What the gauges then indicate, and the warning, are M12's (AD-42).

**Heat sink.** One lumped tank-fuel temperature driven by skin heat exchange at the recovery temperature. The
two hydraulic heat exchangers each take half of the engine fuel flow and reject heat into it
(``hydraulics.py``); the engine fuel inlet temperature ``util.fuel_inlet_t`` is the tank temperature plus that
heat over ``Wf cp``.

**Mass properties.** Reference loading (DSJ 71(2) [DIRECT-unnamed]: about 9,000 kg, inertia tensor, CG 34 %
MAC) is the operating-empty aircraft plus the fuselage tanks holding ``m_ref - m_oe``; the datum (origin) is
that reference CG, body axes x forward, y right, z down. Current mass, CG and inertia follow from tank fuel as
rigid level-surface boxes (ASSUMPTION A-W1.4-17: no slosh in the inertia), stores and drop tanks as point
masses. ``util.inertia`` is the tensor J (H = J w): off-diagonals are -Ixy, -Ixz, -Iyz.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from ._num import JIT, clip, cmax, cmin, pos
from .layout import (
    F_FUEL_BURN,
    F_FUEL_M,
    F_FUEL_T,
    F_FUEL_UNMET,
    F_SLOSH_S,
    F_SLOSH_SD,
    F_STORE_M,
    I_F1A_MOD,
    I_XFER_GRP,
    N_STORE,
    N_TANKS,
    P_FUEL_ALPHA,
    P_FUEL_C_STRUCT,
    P_FUEL_CP,
    P_FUEL_F1A_PICKUP_MOD,
    P_FUEL_FILL_TARGET,
    P_FUEL_PICKUP_BAND,
    P_FUEL_Q_XFER,
    P_FUEL_RESIDUAL,
    P_FUEL_RHO_15,
    P_FUEL_TAU_IC,
    P_FUEL_TAU_XFER,
    P_FUEL_UA_SKIN,
    P_G0,
    P_MP_IXX,
    P_MP_IXY,
    P_MP_IXZ,
    P_MP_IYY,
    P_MP_IYZ,
    P_MP_IZZ,
    P_MP_M_OE,
    P_MP_M_REF,
    P_SLOSH_G_MIN,
    P_SLOSH_OMEGA,
    P_SLOSH_S_MAX,
    P_SLOSH_ZETA,
    P_STORE,
    P_TANK,
    T_F1,
    T_F1A,
    T_F2,
    TC_CAP,
    TC_GROUP,
    TC_HGT,
    TC_LEN,
    TC_PICKUP,
    TC_X,
    TC_Y,
    TC_Z,
)

N_NEWTON = 16
N_GROUPS = 4  # transfer groups 1..4; group 0 = feed group (F1, F2)
T_REF_DENSITY = 288.15  # K, reference temperature of fuel_rho_15 (15 degC, definition of the parameter)


@njit(**JIT)
def tcol(p, col, k):
    """Tank-table entry ``col`` for tank ``k``."""
    return p[P_TANK + col * N_TANKS + k]


@njit(**JIT)
def fuel_density(p, t):
    """Fuel density (kg/m^3) at temperature t (linear thermal expansion about 15 degC)."""
    return p[P_FUEL_RHO_15] * (1.0 - p[P_FUEL_ALPHA] * (t - T_REF_DENSITY))


# ------------------------------------------------------------------------------- free-surface geometry
@njit(**JIT)
def _g(x, s, length):
    """G(x) = integral over [0, L] of max(0, x - s d) dd, for s >= 0."""
    if x.real <= 0.0:
        return x - x
    if x.real < (s * length).real:
        return x * x / (2.0 * s)
    return length * x - s * length * length / 2.0


@njit(**JIT)
def _gp(x, s, length):
    """dG/dx."""
    if x.real <= 0.0:
        return x - x
    if x.real < (s * length).real:
        return x / s
    return x - x + length


@njit(**JIT)
def section_area(c, s, length, height):
    """Fluid cross-section (x-z) for surface intercept c at the aft wall and slope s >= 0 (m^2)."""
    return _g(c, s, length) - _g(c - height, s, length)


@njit(**JIT)
def surface_intercept(a, s, length, height):
    """Solve section_area(c) = a for c (fixed-count damped Newton; complex-step safe), slope s >= 0."""
    c_hi = height + s * length
    c = clip(a / length + s * length / 2.0, 1e-9 * height, c_hi - 1e-9 * height)
    for _ in range(N_NEWTON):
        fp = _gp(c, s, length) - _gp(c - height, s, length)
        if fp.real <= 1e-12:
            fp = fp - fp + 1e-12
        c = clip(c - (section_area(c, s, length, height) - a) / fp, 1e-12 * height, c_hi - 1e-12 * height)
    return c


@njit(**JIT)
def depth_at(m, rho, cap, length, height, s, frac):
    """Fuel depth (m) at station ``frac`` (fraction of length from the aft wall) for mass m and slope s."""
    if m.real <= 0.0:
        return m - m
    vol = m / rho
    a = clip(vol / cap, 0.0, 1.0) * height * length
    d = frac * length
    ss = s
    if s.real < 0.0:  # fuel forward: mirror the station
        ss = -s
        d = length - d
    c = surface_intercept(a, ss, length, height)
    return clip(c - ss * d, 0.0, height)


@njit(**JIT)
def pickup_wetness(p, m, k, s, rho, f1a_mod):
    """Fraction of the commanded transfer a tank's pick-up can deliver (0 dry ... 1 covered)."""
    frac = tcol(p, TC_PICKUP, k)
    if k == T_F1A and f1a_mod == 1:
        frac = p[P_FUEL_F1A_PICKUP_MOD]
    h = depth_at(m, rho, tcol(p, TC_CAP, k), tcol(p, TC_LEN, k), tcol(p, TC_HGT, k), s, frac)
    return clip(h / p[P_FUEL_PICKUP_BAND], 0.0, 1.0)


# ------------------------------------------------------------------------------- per-tick dynamics
@njit(**JIT)
def slosh_step(f, p, fsx, fsz, dt):
    """Lumped first sloshing mode on the pitch-plane surface slope."""
    g = p[P_G0]
    gz = cmax(-fsz + 0.0 * g, p[P_SLOSH_G_MIN] * g)
    smax = p[P_SLOSH_S_MAX]
    s_star = clip(fsx / gz, -smax, smax)
    w = p[P_SLOSH_OMEGA]
    s = f[F_SLOSH_S]
    sd = f[F_SLOSH_SD]
    sd = sd + dt * (w * w * (s_star - s) - 2.0 * p[P_SLOSH_ZETA] * w * sd)
    s = s + dt * sd
    f[F_SLOSH_S] = s
    f[F_SLOSH_SD] = sd


@njit(**JIT)
def fuel_step(f, i, p, wf_tot, t_rec, xfer_loss, dt):
    """Burn, interconnect, transfer and tank-fuel temperature for one tick (mass-conservative). Mutates f,
    i."""
    t_fuel = f[F_FUEL_T]
    rho = fuel_density(p, t_fuel)
    s = f[F_SLOSH_S]
    f1a_mod = i[I_F1A_MOD]
    # --- burn from the collector
    need = pos(wf_tot) * dt
    m2 = f[F_FUEL_M + T_F2]
    take = cmin(need, pos(m2))
    f[F_FUEL_M + T_F2] = m2 - take
    f[F_FUEL_BURN] = f[F_FUEL_BURN] + take
    f[F_FUEL_UNMET] = f[F_FUEL_UNMET] + (need - take)
    # --- F1 <-> F2 interconnect (fill fractions equalise; flow through the source-side pick-up)
    cap1 = tcol(p, TC_CAP, T_F1) * p[P_FUEL_RHO_15]
    cap2 = tcol(p, TC_CAP, T_F2) * p[P_FUEL_RHO_15]
    m1 = f[F_FUEL_M + T_F1]
    m2 = f[F_FUEL_M + T_F2]
    q_ic = (m1 / cap1 - m2 / cap2) * cmin(cap1, cap2) / p[P_FUEL_TAU_IC]
    if q_ic.real > 0.0:  # F1 -> F2 through the F1 outlet
        q_ic = cmin(q_ic * pickup_wetness(p, m1, T_F1, s, rho, f1a_mod) * dt, pos(m1)) / dt
    else:  # F2 -> F1 through the F2 outlet
        q_ic = -cmin(-q_ic * pickup_wetness(p, m2, T_F2, s, rho, f1a_mod) * dt, pos(m2)) / dt
    f[F_FUEL_M + T_F1] = m1 - q_ic * dt
    f[F_FUEL_M + T_F2] = m2 + q_ic * dt
    # --- level-controlled transfer into F2 from the highest-priority non-empty group
    m2 = f[F_FUEL_M + T_F2]
    deficit = p[P_FUEL_FILL_TARGET] * cap2 - m2
    q_cmd = clip(deficit / p[P_FUEL_TAU_XFER], 0.0, p[P_FUEL_Q_XFER] * (1.0 - xfer_loss))
    grp = 0
    for g in range(1, N_GROUPS + 1):
        for k in range(N_TANKS):
            if int(tcol(p, TC_GROUP, k).real) == g:
                cap_k = tcol(p, TC_CAP, k) * p[P_FUEL_RHO_15]
                if f[F_FUEL_M + k].real > (p[P_FUEL_RESIDUAL] * cap_k).real:
                    grp = g
                    break
        if grp != 0:
            break
    i[I_XFER_GRP] = grp
    if grp != 0:
        n_src = 0
        for k in range(N_TANKS):
            cap_k = tcol(p, TC_CAP, k) * p[P_FUEL_RHO_15]
            if (
                int(tcol(p, TC_GROUP, k).real) == grp
                and f[F_FUEL_M + k].real > (p[P_FUEL_RESIDUAL] * cap_k).real
            ):
                n_src += 1
        share = q_cmd / n_src
        moved = q_cmd - q_cmd
        for k in range(N_TANKS):
            cap_k = tcol(p, TC_CAP, k) * p[P_FUEL_RHO_15]
            mk = f[F_FUEL_M + k]
            if int(tcol(p, TC_GROUP, k).real) == grp and mk.real > (p[P_FUEL_RESIDUAL] * cap_k).real:
                dm = cmin(share * pickup_wetness(p, mk, k, s, rho, f1a_mod) * dt, mk)
                f[F_FUEL_M + k] = mk - dm
                moved = moved + dm
        f[F_FUEL_M + T_F2] = f[F_FUEL_M + T_F2] + moved
    # --- lumped tank-fuel temperature (skin exchange at recovery temperature)
    m_tot = f[F_FUEL_M] - f[F_FUEL_M]
    for k in range(N_TANKS):
        m_tot = m_tot + f[F_FUEL_M + k]
    c = m_tot * p[P_FUEL_CP] + p[P_FUEL_C_STRUCT]
    f[F_FUEL_T] = t_fuel + dt * p[P_FUEL_UA_SKIN] * (t_rec - t_fuel) / c


# ------------------------------------------------------------------------------- mass properties
@njit(**JIT)
def _add_box(jt, m, x, y, z, lx, ly, lz):
    """Add a solid box (mass m, centroid (x,y,z), edge lengths) to the inertia tensor jt about the origin."""
    r2 = x * x + y * y + z * z
    jt[0, 0] = jt[0, 0] + m * (r2 - x * x) + m * (ly * ly + lz * lz) / 12.0
    jt[1, 1] = jt[1, 1] + m * (r2 - y * y) + m * (lx * lx + lz * lz) / 12.0
    jt[2, 2] = jt[2, 2] + m * (r2 - z * z) + m * (lx * lx + ly * ly) / 12.0
    jt[0, 1] = jt[0, 1] - m * x * y
    jt[0, 2] = jt[0, 2] - m * x * z
    jt[1, 2] = jt[1, 2] - m * y * z


@njit(**JIT)
def _fuel_box(p, k, m, rho):
    """Fuel in tank k as a level-surface box: (z of centroid, x-extent, y-extent, z-extent)."""
    cap = tcol(p, TC_CAP, k)
    length = tcol(p, TC_LEN, k)
    height = tcol(p, TC_HGT, k)
    width = cap / (height * length)
    hbar = clip(m / rho / (length * width), 0.0, height)
    zc = tcol(p, TC_Z, k) + height / 2.0 - hbar / 2.0
    return zc, length, width, hbar


@njit(**JIT)
def mass_properties(f, p, out):
    """Write total mass (kg), CG (m, 3) and inertia tensor J about the CG (kg m^2, 3x3 row-major) into
    out[13]."""
    rho = fuel_density(p, f[F_FUEL_T])
    rho15 = p[P_FUEL_RHO_15]
    zero = rho - rho
    jt = np.zeros((3, 3), dtype=out.dtype)
    # reference fuel: m_ref - m_oe in the fuselage tanks (group 0 and F1A), proportional to capacity
    caps = zero
    for k in range(N_TANKS):
        if int(tcol(p, TC_GROUP, k).real) == 0 or k == T_F1A:
            caps = caps + tcol(p, TC_CAP, k)
    m_fref_tot = p[P_MP_M_REF] - p[P_MP_M_OE]
    # dry inertia about the datum = reference tensor - reference fuel (datum = reference CG)
    jt[0, 0] = p[P_MP_IXX]
    jt[1, 1] = p[P_MP_IYY]
    jt[2, 2] = p[P_MP_IZZ]
    jt[0, 1] = -p[P_MP_IXY]
    jt[0, 2] = -p[P_MP_IXZ]
    jt[1, 2] = -p[P_MP_IYZ]
    mx_ref = zero
    my_ref = zero
    mz_ref = zero
    for k in range(N_TANKS):
        if int(tcol(p, TC_GROUP, k).real) == 0 or k == T_F1A:
            mk = m_fref_tot * tcol(p, TC_CAP, k) / caps
            zc, lx, ly, lz = _fuel_box(p, k, mk, rho15)
            xk = tcol(p, TC_X, k)
            yk = tcol(p, TC_Y, k)
            _add_box(jt, -mk, xk, yk, zc, lx, ly, lz)
            mx_ref = mx_ref + mk * xk
            my_ref = my_ref + mk * yk
            mz_ref = mz_ref + mk * zc
    m_oe = p[P_MP_M_OE]
    # dry CG chosen so that the reference loading has its CG at the datum
    m_tot = m_oe
    mx = -mx_ref
    my = -my_ref
    mz = -mz_ref
    for k in range(N_TANKS):
        mk = f[F_FUEL_M + k]
        if mk.real > 0.0:
            zc, lx, ly, lz = _fuel_box(p, k, mk, rho)
            xk = tcol(p, TC_X, k)
            yk = tcol(p, TC_Y, k)
            _add_box(jt, mk, xk, yk, zc, lx, ly, lz)
            m_tot = m_tot + mk
            mx = mx + mk * xk
            my = my + mk * yk
            mz = mz + mk * zc
    for st in range(N_STORE):
        ms = f[F_STORE_M + st]
        if ms.real > 0.0:
            xs = p[P_STORE + 0 * N_STORE + st]
            ys = p[P_STORE + 1 * N_STORE + st]
            zs = p[P_STORE + 2 * N_STORE + st]
            _add_box(jt, ms, xs, ys, zs, zero, zero, zero)
            m_tot = m_tot + ms
            mx = mx + ms * xs
            my = my + ms * ys
            mz = mz + ms * zs
    cx = mx / m_tot
    cy = my / m_tot
    cz = mz / m_tot
    # parallel-axis shift from the datum to the CG
    c2 = cx * cx + cy * cy + cz * cz
    jt[0, 0] = jt[0, 0] - m_tot * (c2 - cx * cx)
    jt[1, 1] = jt[1, 1] - m_tot * (c2 - cy * cy)
    jt[2, 2] = jt[2, 2] - m_tot * (c2 - cz * cz)
    jt[0, 1] = jt[0, 1] + m_tot * cx * cy
    jt[0, 2] = jt[0, 2] + m_tot * cx * cz
    jt[1, 2] = jt[1, 2] + m_tot * cy * cz
    out[0] = m_tot
    out[1] = cx
    out[2] = cy
    out[3] = cz
    out[4] = jt[0, 0]
    out[5] = jt[0, 1]
    out[6] = jt[0, 2]
    out[7] = jt[0, 1]
    out[8] = jt[1, 1]
    out[9] = jt[1, 2]
    out[10] = jt[0, 2]
    out[11] = jt[1, 2]
    out[12] = jt[2, 2]
