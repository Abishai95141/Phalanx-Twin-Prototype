"""Two 280 bar hydraulic networks (architecture §6 M09; report §3; note tejas_utility_systems.md KQ2).

Per system ``h`` (lumped-parameter network, note Synthesis (d)):

- **Pressure-compensated variable-displacement pump** on an AMAGB pad. Maximum geometric flow scales with pad
  speed, i.e. with N2 (``Q_max = q_rated * w_pto / w_rated``). The compensator destrokes linearly over
  ``dp_band`` below the cut-off pressure ``p_nom * (1 + drift)``, sensed at the pump outlet (upstream of the
  pressure filter), with a first-order swash-plate lag ``tau_swash``. A check valve prevents back-flow.
- **Leakage conductances** (pump case drain, system internal, external/overboard) scale with ``1/mu(T)``
  (Andrade viscosity law; warm fluid leaks more, report §3 "Hydraulic temperature -> leakage, pump
  volumetric efficiency"). Health deltas from ``health.utility`` multiply them.
- **Accumulator** (polytropic N2 gas; precharge set at the charging temperature, follows the gas law with the
  fluid temperature, less the health loss) and fluid compressibility set the node capacitance; **relief
  valve** above ``relief_crack * p_nom``.
- **Pressure filter** dP grows with flow, viscosity and loading (exponential in loading [TRANSFER: US
  6,855,249]); it lowers the delivered system pressure at high flow because the compensator senses the
  pump outlet.
- **Bootstrap reservoir** volume closes the fluid balance (thermal expansion included); the reservoir level is
  the leakage observable.
- **Thermal node**: all pump shaft power ends as heat in the fluid (MIL-H-5440H thermal analysis practice);
  heat leaves through a fuel-cooled heat exchanger (cross-flow epsilon-NTU; the fuel side heat-capacity rate
  is the engine fuel flow, so low Wf -> hotter fluid, report §3 heat-sink edge) and to the bay.

Integration: explicit Euler with ``nsub`` sub-steps per 240 Hz tick (architecture §8: stiff hydraulic states
sub-step internally). Pressures are **gauge**. All arithmetic is complex-step safe (``_num`` helpers).
"""

from __future__ import annotations

import numpy as np
from numba import njit

from ._num import JIT, clip, cmax, cmin, pos
from .layout import (
    F_HYD_EIN,
    F_HYD_EOUT,
    F_HYD_P,
    F_HYD_T,
    F_HYD_VEXT,
    F_HYD_VRES,
    F_HYD_X,
    P_FUEL_CP,
    P_HYD_ACC_N,
    P_HYD_ACC_PRE,
    P_HYD_ACC_T_CHARGE,
    P_HYD_ACC_V,
    P_HYD_ALPHA_V,
    P_HYD_BETA,
    P_HYD_C_METAL,
    P_HYD_CP,
    P_HYD_DP_BAND,
    P_HYD_DP_STARVE,
    P_HYD_ETA_HM,
    P_HYD_ETA_V,
    P_HYD_FILTER_DP,
    P_HYD_FILTER_EXP,
    P_HYD_HX_UA,
    P_HYD_P_NOM,
    P_HYD_P_RET,
    P_HYD_Q_HX,
    P_HYD_Q_LEAK_INT,
    P_HYD_Q_RATED,
    P_HYD_RELIEF_CRACK,
    P_HYD_RELIEF_FULL,
    P_HYD_RHO,
    P_HYD_T_REF,
    P_HYD_TAU_SWASH,
    P_HYD_UA_AMB,
    P_HYD_V_LINE,
    P_HYD_V_TOTAL,
    P_HYD_VISC_B,
    P_PTO_RATED_SPEED,
)


@njit(**JIT)
def visc_ratio(t, b, t_ref):
    """mu(T) / mu(T_ref) for an Andrade law mu = A exp(B / T) [ASSUMPTION A-W1.4-5]."""
    return np.exp(b * (1.0 / t - 1.0 / t_ref))


@njit(**JIT)
def crossflow_effectiveness(ntu, cr):
    """Cross-flow, both fluids unmixed (Incropera eq. 11.33 approximation) [TRANSFER: standard HX theory]."""
    if cr.real < 1e-9:
        return 1.0 - np.exp(-ntu)
    return 1.0 - np.exp((1.0 / cr) * ntu**0.22 * (np.exp(-cr * ntu**0.78) - 1.0))


@njit(**JIT)
def hx_heat(ua, c_hot, c_cold, t_hot, t_cold):
    """Heat rate (W) from the hot to the cold stream through an epsilon-NTU cross-flow exchanger."""
    c_min = cmin(c_hot, c_cold)
    if c_min.real <= 1e-9:
        d = t_hot - t_cold
        return d - d
    c_max = cmax(c_hot, c_cold)
    eps = crossflow_effectiveness(ua / c_min, c_min / c_max)
    return eps * c_min * (t_hot - t_cold)


@njit(**JIT)
def precharge(p, pre_loss, t_gas, p_amb):
    """Accumulator gas precharge (gauge Pa) at gas temperature t_gas: charged at ``hyd_acc_t_charge``, then
    isochoric gas law (cold soak lowers it; report §3 cold-soak edge), less the health loss fraction."""
    p_abs = (p[P_HYD_ACC_PRE] * (1.0 - pre_loss) + p_amb) * t_gas / p[P_HYD_ACC_T_CHARGE]
    return p_abs - p_amb


@njit(**JIT)
def accumulator_fluid(p, p_pre, p_amb, acc_v, n):
    """Fluid volume (m^3) in a gas accumulator at gauge pressure p (polytropic gas, precharge p_pre gauge)."""
    if p.real <= p_pre.real:
        return p - p
    vg = acc_v * ((p_pre + p_amb) / (p + p_amb)) ** (1.0 / n)
    return acc_v - vg


@njit(**JIT)
def accumulator_capacitance(p, p_pre, p_amb, acc_v, n):
    """d(fluid volume)/dp of the accumulator (m^3/Pa); zero below the precharge."""
    if p.real <= p_pre.real:
        return p - p
    pa = p + p_amb
    vg = acc_v * ((p_pre + p_amb) / pa) ** (1.0 / n)
    return vg / (n * pa)


@njit(**JIT)
def accumulator_gas_thermal(p, p_pre, p_amb, acc_v, n, t):
    """d(gas volume)/dT at fixed system pressure (m^3/K): V_gas / (n T) above the precharge, else 0."""
    if p.real <= p_pre.real:
        return p - p
    vg = acc_v * ((p_pre + p_amb) / (p + p_amb)) ** (1.0 / n)
    return vg / (n * t)


@njit(**JIT)
def hyd_system(
    f,
    p,
    h,
    w_pto,
    q_dem,
    wf_tot,
    t_fuel,
    t_bay,
    p_amb,
    hp_leak,
    hs_leak,
    he_leak,
    drift,
    f_load,
    pre_loss,
    dt,
    nsub,
):
    """Advance hydraulic system ``h`` by one truth tick (``nsub`` Euler sub-steps). Mutates ``f``.

    Returns (mean pump shaft power W, mean HX heat to fuel W, mean filter dP Pa) over the tick.
    """
    p_nom = p[P_HYD_P_NOM]
    p_ret = p[P_HYD_P_RET]
    q_rated = p[P_HYD_Q_RATED]
    dp_band = p[P_HYD_DP_BAND]
    tau = p[P_HYD_TAU_SWASH]
    eta_hm = p[P_HYD_ETA_HM]
    b = p[P_HYD_VISC_B]
    t_ref = p[P_HYD_T_REF]
    acc_v = p[P_HYD_ACC_V]
    acc_n = p[P_HYD_ACC_N]
    dp_starve = p[P_HYD_DP_STARVE]
    filt0 = p[P_HYD_FILTER_DP] * np.exp(p[P_HYD_FILTER_EXP] * f_load)
    alpha_vt = p[P_HYD_ALPHA_V] * p[P_HYD_V_TOTAL]
    c_f = p[P_HYD_V_LINE] / p[P_HYD_BETA]
    c_th = p[P_HYD_V_TOTAL] * p[P_HYD_RHO] * p[P_HYD_CP] + p[P_HYD_C_METAL]
    c_hyd = p[P_HYD_RHO] * p[P_HYD_Q_HX] * p[P_HYD_CP]
    c_fuel = pos(wf_tot) * p[P_FUEL_CP]
    ua_amb = p[P_HYD_UA_AMB]
    ua_hx = p[P_HYD_HX_UA]
    dp_nom = p_nom - p_ret
    g_pump = (1.0 - p[P_HYD_ETA_V]) * q_rated / dp_nom * (1.0 + hp_leak)
    g_int = p[P_HYD_Q_LEAK_INT] / dp_nom * (1.0 + hs_leak)
    g_ext = he_leak * q_rated / p_nom
    p_crack = p[P_HYD_RELIEF_CRACK] * p_nom
    g_rv = q_rated / ((p[P_HYD_RELIEF_FULL] - p[P_HYD_RELIEF_CRACK]) * p_nom)
    p_set = p_nom * (1.0 + drift)
    q_max = q_rated * pos(w_pto) / p[P_PTO_RATED_SPEED]
    q_d0 = pos(q_dem)

    pr = f[F_HYD_P + h]
    x = f[F_HYD_X + h]
    t = f[F_HYD_T + h]
    vres = f[F_HYD_VRES + h]
    vext = f[F_HYD_VEXT + h]
    ein = f[F_HYD_EIN + h]
    eout = f[F_HYD_EOUT + h]
    hs = dt / nsub
    shaft_sum = pr - pr
    qhx_sum = pr - pr
    dpf_sum = pr - pr
    for _ in range(nsub):
        mu = visc_ratio(t, b, t_ref)
        q_geo = x * q_max
        dpf = filt0 * (q_geo / q_rated) * mu
        p_out = pr + dpf
        q_pl = g_pump / mu * pos(p_out - p_ret)
        q_del = pos(q_geo - q_pl)
        x_cmd = clip((p_set - p_out) / dp_band, 0.0, 1.0)
        dp_sys = pos(pr - p_ret)
        q_li = g_int / mu * dp_sys
        q_le = g_ext / mu * pos(pr)
        q_rv = g_rv * pos(pr - p_crack)
        q_d = q_d0 * clip(dp_sys / dp_starve, 0.0, 1.0)
        shaft = q_geo * pos(p_out - p_ret) / eta_hm
        q_amb = ua_amb * (t - t_bay)
        q_hx = hx_heat(ua_hx, c_hyd, c_fuel, t, t_fuel)
        dt_dt = (shaft - q_amb - q_hx) / c_th
        # node: compressibility + accumulator compliance; the gas follows the fluid temperature, so warming
        # expands it and pushes fluid into the node (dV_gas/dT at fixed P = V_gas / (n T))
        p_pre = precharge(p, pre_loss, t, p_amb)
        c_tot = c_f + accumulator_capacitance(pr, p_pre, p_amb, acc_v, acc_n)
        q_gas = accumulator_gas_thermal(pr, p_pre, p_amb, acc_v, acc_n, t) * dt_dt
        dpr = (q_del - q_d - q_li - q_le - q_rv + q_gas) / c_tot
        pr_new = pr + hs * dpr
        x = x + hs * (x_cmd - x) / tau
        t_new = t + hs * dt_dt
        vres = vres + hs * (q_d + q_li + q_rv - q_del) + alpha_vt * (t_new - t)
        vext = vext + hs * q_le
        ein = ein + hs * shaft
        eout = eout + hs * (q_amb + q_hx)
        pr = pr_new
        t = t_new
        shaft_sum = shaft_sum + shaft
        qhx_sum = qhx_sum + q_hx
        dpf_sum = dpf_sum + dpf
    f[F_HYD_P + h] = pr
    f[F_HYD_X + h] = x
    f[F_HYD_T + h] = t
    f[F_HYD_VRES + h] = vres
    f[F_HYD_VEXT + h] = vext
    f[F_HYD_EIN + h] = ein
    f[F_HYD_EOUT + h] = eout
    return shaft_sum / nsub, qhx_sum / nsub, dpf_sum / nsub


@njit(**JIT)
def hyd_volume_invariant(f, p, h, p_amb, pre_loss, t0):
    """Fluid-volume invariant (m^3): reservoir + accumulator fluid + compression + lost - thermal expansion.

    Constant over a run up to the Euler discretisation of the accumulator compliance (A1 balance test).
    """
    pr = f[F_HYD_P + h]
    p_pre = precharge(p, pre_loss, f[F_HYD_T + h], p_amb)
    v_acc = accumulator_fluid(pr, p_pre, p_amb, p[P_HYD_ACC_V], p[P_HYD_ACC_N])
    c_f = p[P_HYD_V_LINE] / p[P_HYD_BETA]
    exp_v = p[P_HYD_ALPHA_V] * p[P_HYD_V_TOTAL] * (f[F_HYD_T + h] - t0)
    return f[F_HYD_VRES + h] + v_acc + c_f * pr + f[F_HYD_VEXT + h] - exp_v
