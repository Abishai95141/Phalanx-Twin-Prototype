"""Carbon brakes (energy -> heat sink -> wear), main tyres (wear per landing, skid, burst), brake chute (M09).

Evidence: HAL carbon brake unit (3 rotors / 4 stators) and main wheel 26 x 8.00-14 [DIRECT-part]; ADA RTO
trials at 50/70/90 % brake wear [DIRECT]; brake chute 17 m^2, deploy <= 285 km/h normal and <= 340 km/h
emergency, life 45 streamings / 8 years [DIRECT]; carbon wear mainly per application, oxidation at high
temperature, heat-sink time constants of tens of minutes [TRANSFER: Mortimore CEAS 2007; US 7,963,620;
Boeing AERO]; carbon brakes 1,400 landings (F-15) and F-16 main tyres 4-12 landings [TRANSFER] (report §9.2).

Interfaces: the airframe (M06) owns the ground model, wheel dynamics, anti-skid and brake torque and publishes
``af.brake_energy_rate`` and ``af.wheel_speed``. M09 owns what the energy does to the heat sink, the wear and
the tyre. The wear accrued in a sortie is added to the sortie-start wear from ``health.utility``; the
per-serial wear process across sorties lives in M10, which can call the same increment laws in usage mode.

- **Heat sink**: ``C dT/dt = P_brake - C (T - T_amb) / tau_cool`` with ``C = m_hs (1 - k_mass * wear0) c_p``:
  worn heat sinks have less mass, so the same RTO energy gives a higher peak temperature (A-W1.4-26).
- **Brake wear**: ``brk_w_app`` per application (hysteretic detection on brake power) plus an energy term with
  an oxidation multiplier above ``brk_t_ox`` (A-W1.4-27).
- **Tyre wear**: per touchdown (spin-up scrub, scaled by mass and touchdown speed squared), braking slip
  (proportional to brake energy) and locked-wheel skid (wheel speed below 20 % of rolling speed with weight on
  wheels: power ``mu_skid * (m g / 2) * V``). Burst latched at wear >= 1 (the brake-software event chain:
  anti-skid failure -> locked wheel -> burst).
- **Chute**: deploy events check the true airspeed against the normal and emergency limits; above the
  emergency limit the canopy fails. Streamings are counted (life counter for M18).
"""

from __future__ import annotations

from numba import njit

from ._num import JIT, clip, cmax, cmin, pos
from .layout import (
    F_BRK_DW,
    F_BRK_EIN,
    F_BRK_EOUT,
    F_BRK_T,
    F_TYRE_DW,
    I_BRK_APPS,
    I_BRK_ON,
    I_LANDINGS,
    I_TYRE_BURST,
    I_WOW_PREV,
    N_WHEEL,
    P_BRK_CP,
    P_BRK_K_OX,
    P_BRK_M_HS,
    P_BRK_MASS_LOSS,
    P_BRK_OX_SCALE,
    P_BRK_P_MAX,
    P_BRK_P_OFF,
    P_BRK_P_ON,
    P_BRK_T_OX,
    P_BRK_TAU_COOL,
    P_BRK_TORQUE_GAIN,
    P_BRK_W_APP,
    P_BRK_W_ENERGY,
    P_G0,
    P_JFS_W_FLOOR,
    P_SKID_SLIP,
    P_SKID_V_MIN,
    P_TD_V_MIN,
    P_TYRE_M_REF,
    P_TYRE_MU_SKID,
    P_TYRE_R,
    P_TYRE_V_REF,
    P_TYRE_W_BRAKE,
    P_TYRE_W_SKID,
    P_TYRE_W_TD,
)


@njit(**JIT)
def heat_capacity(p, wear0):
    """Brake heat-sink heat capacity (J/K) at sortie-start wear wear0."""
    return p[P_BRK_M_HS] * (1.0 - p[P_BRK_MASS_LOSS] * wear0) * p[P_BRK_CP]


@njit(**JIT)
def brake_wear_rate(p, pw, t_hs):
    """Continuous (energy) part of carbon wear (fraction of life per second) at brake power pw and
    temperature."""
    return p[P_BRK_W_ENERGY] * pw * (1.0 + p[P_BRK_K_OX] * pos(t_hs - p[P_BRK_T_OX]) / p[P_BRK_OX_SCALE])


@njit(**JIT)
def touchdown_tyre_wear(p, mass, v_td):
    """Tyre wear (fraction of life) of one touchdown: spin-up scrub scaled by mass and speed squared."""
    rv = v_td / p[P_TYRE_V_REF]
    return p[P_TYRE_W_TD] * (mass / p[P_TYRE_M_REF]) * (rv * rv)  # explicit square (R8)


@njit(**JIT)
def landing_step(f, i, p, pbrk, wheel, wow_l, wow_r, tas, mass, t_amb, wear0, tyre0, p_supply, brk_p, dt):
    """One tick of brakes and tyres (pbrk, wheel, wear0, tyre0, brk_p: length-2 arrays). Mutates f, i, brk_p.

    Brake pressure (``util.brake_p``) is the pressure that produces the brake torque implied by the absorbed
    power, ``T = P / (w_wheel + w_floor)`` and ``p = T / brk_torque_gain``; a locked wheel in a skid needs at
    least the pressure that holds the tyre friction torque. It is capped by the metered maximum and by the
    supplying hydraulic system's pressure ``p_supply`` (gauge).
    """
    wow_main = 1 if (wow_l > 0.5 or wow_r > 0.5) else 0
    if wow_main == 1 and i[I_WOW_PREV] == 0 and tas > p[P_TD_V_MIN].real:
        i[I_LANDINGS] = i[I_LANDINGS] + 1
        dw_td = touchdown_tyre_wear(p, mass, tas)
        for w in range(N_WHEEL):
            f[F_TYRE_DW + w] = f[F_TYRE_DW + w] + dw_td
    i[I_WOW_PREV] = wow_main
    for w in range(N_WHEEL):
        pw = pos(pbrk[w] + 0.0 * mass)
        c = heat_capacity(p, wear0[w])
        t = f[F_BRK_T + w]
        q_cool = c * (t - t_amb) / p[P_BRK_TAU_COOL]
        f[F_BRK_T + w] = t + dt * (pw - q_cool) / c
        f[F_BRK_EIN + w] = f[F_BRK_EIN + w] + dt * pw
        f[F_BRK_EOUT + w] = f[F_BRK_EOUT + w] + dt * q_cool
        if i[I_BRK_ON + w] == 0 and pw.real > p[P_BRK_P_ON].real:
            i[I_BRK_ON + w] = 1
            i[I_BRK_APPS + w] = i[I_BRK_APPS + w] + 1
            f[F_BRK_DW + w] = f[F_BRK_DW + w] + p[P_BRK_W_APP]
        elif i[I_BRK_ON + w] == 1 and pw.real < p[P_BRK_P_OFF].real:
            i[I_BRK_ON + w] = 0
        f[F_BRK_DW + w] = f[F_BRK_DW + w] + dt * brake_wear_rate(p, pw, t)
        # tyre: braking slip and locked-wheel skid
        dtw = p[P_TYRE_W_BRAKE] * pw
        wow_w = wow_l if w == 0 else wow_r
        skid = (
            wow_w > 0.5
            and tas > p[P_SKID_V_MIN].real
            and wheel[w] * p[P_TYRE_R].real < p[P_SKID_SLIP].real * tas
        )
        if skid:
            dtw = dtw + p[P_TYRE_W_SKID] * p[P_TYRE_MU_SKID] * mass * p[P_G0] / 2.0 * tas
        f[F_TYRE_DW + w] = f[F_TYRE_DW + w] + dt * dtw
        if (tyre0[w] + f[F_TYRE_DW + w]).real >= 1.0:
            i[I_TYRE_BURST + w] = 1
        # brake pressure behind the torque (or holding a locked wheel)
        pr = pw / ((wheel[w] + p[P_JFS_W_FLOOR]) * p[P_BRK_TORQUE_GAIN])
        if skid:
            pr = cmax(pr, p[P_TYRE_MU_SKID] * mass * p[P_G0] / 2.0 * p[P_TYRE_R] / p[P_BRK_TORQUE_GAIN])
        brk_p[w] = clip(pr, 0.0, cmin(p[P_BRK_P_MAX], pos(p_supply)))
