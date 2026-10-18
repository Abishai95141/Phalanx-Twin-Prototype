"""Bleed-air ECS: bleed extraction, PHX (epsilon-NTU), ACM, TCV loop, cabin pressure and bay thermals.

Evidence: note tejas_utility_systems.md KQ5 and Synthesis (b)-(d); HAL-ARDC fighter ECS (Heliyon 2022:
bootstrap cycle, bleed 2.8-6.4 bar and 175-440 degC over 75-97 % rpm, TCV bypass, 6-10 s valve stroke)
[TRANSFER: HAL fighter]; HAL primary heat exchanger 34.5 kg/min, <= 578 degC in, < 170 degC out
[DIRECT-part]; ADA "gimbal assembly with venturi" [DIRECT]; MIL-E-18927E (pressurisation rates) and Webb &
Pilmanis (5 psi differential above 23,000 ft) [TRANSFER]; Gripen ECS practice (ICAS 2016-0188).

- **Bleed extraction** (``util.bleed_extract``): a flow-control valve holds the set flow ``ecs_m_set``
  (scaled by the process disturbance ``env.w_bleed_pto``) unless the flow-limiting venturi chokes it:
  ``m <= Cd A p3 / sqrt(T3) * K(gamma, R) * psi(p_cab / p3)`` (compressible orifice; HAL paper). At low N2 the
  extraction therefore follows bleed pressure; above it, it is flat. Tank pressurisation and OBOGS add
  ``ecs_m_aux`` while bleed pressure exceeds ambient. The extraction is the M07 input (report §3: bleed
  extraction -> thrust and T5, an M07-side sign).
- **PHX**: hot bleed vs ram air (cross-flow epsilon-NTU; fouling from ``health.utility`` lowers UA). Ram flow
  ``rho V A_ram`` in flight, ``ecs_m_ram_ground`` (ejector/fan) on the ground. Duct thermal lag ``tau_duct``.
- **ACM**: PROXY (A-W1.4-24) - the bootstrap compressor/secondary-HX stage is reduced to a single turbine
  expansion from PHX-outlet pressure to cabin pressure with isentropic efficiency ``ecs_eta_t``. Exposing
  test:
  ``test_utilities_ecs.py::test_acm_proxy_has_no_bootstrap_gain``.
- **TCV**: hot bleed bypass fraction mixed into the supply; integrating controller on cockpit temperature,
  rate-limited to the 6-10 s full stroke (slow limit-cycling rather than white noise, note KQ5).
- **Cabin pressure**: unpressurised below the isobaric cabin pressure, isobaric to the 5 psi differential,
  then constant differential; tracked first-order and limited to 0.2 psi/s (MIL-E-18927E); the achievable
  differential is capped by supply flow against the leak (canopy seal health).
- **Thermal nodes**: cockpit and avionics bay (electrical load dissipated in the bay heats it; the coupling
  electrical -> ECS).
"""

from __future__ import annotations

import numpy as np
from numba import njit

from ._num import JIT, clip, cmin, pos
from .hydraulics import hx_heat
from .layout import (
    F_ECS_MBLEED,
    F_ECS_MSUP,
    F_ECS_PCAB,
    F_ECS_TAV,
    F_ECS_TCAB,
    F_ECS_TCV,
    F_ECS_TPHX,
    P_CP_AIR,
    P_ECS_C_AV,
    P_ECS_C_CAB,
    P_ECS_CDA,
    P_ECS_DP_MAX,
    P_ECS_DPDT_MAX,
    P_ECS_ETA_T,
    P_ECS_F_CAB,
    P_ECS_FOUL_K,
    P_ECS_KI,
    P_ECS_LEAK_FRAC,
    P_ECS_M_AUX,
    P_ECS_M_RAM_GROUND,
    P_ECS_M_SET,
    P_ECS_P_CAB_ISO,
    P_ECS_PHX_DP,
    P_ECS_PHX_UA,
    P_ECS_Q_CAB,
    P_ECS_RAM_AREA,
    P_ECS_STROKE,
    P_ECS_T_SET,
    P_ECS_TAU_CAB_P,
    P_ECS_TAU_DUCT,
    P_ECS_UA_AV,
    P_ECS_UA_CAB,
    P_GAMMA_AIR,
    P_R_AIR,
)


@njit(**JIT)
def orifice_flow(cda, p_up, t_up, p_down, gamma, r_gas):
    """Compressible orifice mass flow (kg/s), choked or subsonic (isentropic nozzle relations)."""
    if p_up.real <= p_down.real or p_up.real <= 0.0:
        d = p_up - p_up
        return d
    pr = p_down / p_up
    crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
    if pr.real <= crit.real:
        k = np.sqrt(gamma / r_gas) * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        return cda * p_up / np.sqrt(t_up) * k
    k = np.sqrt(2.0 * gamma / (r_gas * (gamma - 1.0)) * (pr ** (2.0 / gamma) - pr ** ((gamma + 1.0) / gamma)))
    return cda * p_up / np.sqrt(t_up) * k


@njit(**JIT)
def ecs_step(f, p, ne, p3, t3, wbp, p_amb, t_rec, rho, tas, fouling, cab_leak, av_heat, bleed_out, dt):
    """One ECS tick. Writes per-engine bleed extraction into bleed_out[ne]; mutates f.

    Returns (T_bleed, T_phx, T_turbine_out, P_bleed, P_phx, P_turbine_out) for the ecs_t/ecs_p points.
    """
    gamma = p[P_GAMMA_AIR]
    rg = p[P_R_AIR]
    cp = p[P_CP_AIR]
    pcab = f[F_ECS_PCAB]
    zero = pcab - pcab
    m_sup = zero
    m_aux = zero
    mt = zero
    mp = zero
    p_mean = zero
    t_mean = zero
    for e in range(ne):
        m_set_e = p[P_ECS_M_SET] * (1.0 + wbp[e]) / ne
        m_max_e = orifice_flow(p[P_ECS_CDA] / ne, p3[e], t3[e], pcab, gamma, rg)
        m_e = cmin(pos(m_set_e), m_max_e)
        aux = p[P_ECS_M_AUX] / ne if p3[e].real > p_amb.real else zero
        bleed_out[e] = m_e + aux
        m_sup = m_sup + m_e
        m_aux = m_aux + aux
        mt = mt + m_e * t3[e]
        mp = mp + m_e * p3[e]
        p_mean = p_mean + p3[e] / ne
        t_mean = t_mean + t3[e] / ne
        f[F_ECS_MBLEED] = f[F_ECS_MBLEED] + dt * bleed_out[e]
    if m_sup.real > 1e-9:
        t_b = mt / m_sup
        p_b = mp / m_sup
    else:
        t_b = t_mean
        p_b = p_mean
    # PHX
    m_ram = rho * tas * p[P_ECS_RAM_AREA]
    if m_ram.real < p[P_ECS_M_RAM_GROUND].real:
        m_ram = p[P_ECS_M_RAM_GROUND] + zero
    ua = p[P_ECS_PHX_UA] * (1.0 - p[P_ECS_FOUL_K] * fouling)
    c_h = m_sup * cp
    q = hx_heat(ua, c_h, m_ram * cp, t_b, t_rec)
    t_phx_ss = t_b - q / c_h if c_h.real > 1e-9 else t_b
    tphx = f[F_ECS_TPHX] + dt * (t_phx_ss - f[F_ECS_TPHX]) / p[P_ECS_TAU_DUCT]
    p_phx = p_b * (1.0 - p[P_ECS_PHX_DP])
    pr_t = clip(pcab / p_phx, 0.0, 1.0) if p_phx.real > 0.0 else zero + 1.0
    t_to = tphx * (1.0 - p[P_ECS_ETA_T] * (1.0 - pr_t ** ((gamma - 1.0) / gamma)))
    x = f[F_ECS_TCV]
    t_sup = (1.0 - x) * t_to + x * t_b
    # cabin pressure schedule (absolute)
    p_iso = p[P_ECS_P_CAB_ISO]
    if p_amb.real >= p_iso.real:
        target = p_amb + zero
    else:
        target = cmin(p_iso + zero, p_amb + p[P_ECS_DP_MAX])
    m_cab = p[P_ECS_F_CAB] * m_sup
    k_leak = (
        p[P_ECS_LEAK_FRAC] * p[P_ECS_M_SET] * p[P_ECS_F_CAB] / np.sqrt(p[P_ECS_DP_MAX]) * (1.0 + cab_leak)
    )
    r_leak = m_cab / k_leak
    dp_ach = r_leak * r_leak  # explicit square (R8)
    target = cmin(target, p_amb + dp_ach)
    dpdt = clip((target - pcab) / p[P_ECS_TAU_CAB_P], -p[P_ECS_DPDT_MAX], p[P_ECS_DPDT_MAX])
    f[F_ECS_PCAB] = pcab + dt * dpdt
    # cockpit and avionics bay
    tcab = f[F_ECS_TCAB]
    tav = f[F_ECS_TAV]
    q_cab = m_cab * cp * (t_sup - tcab) + p[P_ECS_UA_CAB] * (t_rec - tcab) + p[P_ECS_Q_CAB]
    q_av = (m_sup - m_cab) * cp * (t_sup - tav) + p[P_ECS_UA_AV] * (t_rec - tav) + av_heat
    f[F_ECS_TCAB] = tcab + dt * q_cab / p[P_ECS_C_CAB]
    f[F_ECS_TAV] = tav + dt * q_av / p[P_ECS_C_AV]
    f[F_ECS_TPHX] = tphx
    # TCV: integrating, rate-limited
    rate = clip(p[P_ECS_KI] * (p[P_ECS_T_SET] - tcab), -1.0 / p[P_ECS_STROKE], 1.0 / p[P_ECS_STROKE])
    f[F_ECS_TCV] = clip(x + dt * rate, 0.0, 1.0)
    f[F_ECS_MSUP] = f[F_ECS_MSUP] + dt * (m_cab + (m_sup - m_cab) + m_aux)
    return t_b, tphx, t_to, p_b, p_phx, pcab
