"""GTSU-110 jet fuel starter: battery-cranked gas generator, free power turbine, start sequencer (M09).

Evidence: DDP GTSU-110 (110 kW, 52 kg, twin-shaft with free power turbine, digital fuel control) [DIRECT];
PTO peak starting torque 410 N m at rated 16,810 rpm [DIRECT]; CAG 17/2015 (M1 failed three consecutive starts
at Leh in Jan 2013/2014; "temperature goes below (-) 16 degrees"; excessive oil consumption) [DIRECT]; HAL via
IDR Feb 2015 (three consecutive starts at -15 degC with an 85 % battery after an 18-20 h cold soak) [DIRECT];
DRDO (rig starts to Khardung La 18,300 ft; modified start schedule; partially charged battery is the stringent
case) [DIRECT]; ADA AR 2018-19 (M2 with self-contained lubrication) [DIRECT]; T-50 F404-102 start timeline
(starter cut-out about 55 % N2) [TRANSFER: KSAS 2006]. JFS speeds, timings and EGT limits are not public
(note KQ1 gaps) and F-16 JFS timings are restricted (report App. A1): none are used.

Model (lumped, energy form): ``d(E_r n^2)/dt = P_motor + P_comb - P_drag`` with ``E_r`` the spool kinetic
energy at rated speed, so ``dn/dt = (P_m + P_c - P_d) / (2 E_r n)``.

- **Cranking**: the battery-fed starter motor delivers ``P_m = e_m I_m`` (``e_m = k_e n``); its current comes
  from the battery Thevenin model (``electrical.py``), so cold (R0 up), low SOC and polarisation from earlier
  starts all reduce cranking power. The motor cuts out at ``n_sa``.
- **Drag**: ``P_d = n^2 (c_visc (mu/mu_ref)^a + c_aero n)``; JFS oil viscosity rises when cold-soaked (Andrade
  law). Variant M1 carries a cold-drag factor (shared lubrication; the M2 has a self-contained system).
- **Light-off**: one keyed uniform draw per start attempt (stream ``util/jfs_ignition``, index = attempt
  number in state) when the spool first reaches ``n_lo``; ignition probability falls with altitude.
- **Acceleration**: combustion surplus ``P_c = p_gg delta theta^k (n - n_lo)/(1 - n_lo)`` (gas-generator power
  lapse with inlet density; the M1 start schedule carries a factor, the "modified start schedule" fix).
- **Engaged**: governed at rated speed; the free turbine drives the AMAGB starter pad: ``P_out = min(P_avail,
  T_peak * max(w_pto, w_floor))``, delivered to the engine as negative ``util.pto_power``. Cut-out when the
  engine reaches ``n2_cutout``.
- **Outcomes**: OK, slow crank (n_lo not reached), no light, hung (n_on not reached), engine not reaching
  cut-out. Consecutive successes are counted (the three-consecutive-start requirement).
"""

from __future__ import annotations

from numba import njit

from ._num import JIT, clip, cmin, pos
from .hydraulics import visc_ratio
from .layout import (
    F_JFS_EGT,
    F_JFS_N,
    F_JFS_OILQ,
    F_JFS_OILT,
    F_JFS_TMODE,
    I_JFS_CONSEC,
    I_JFS_DRAWN,
    I_JFS_FAIL,
    I_JFS_LIT,
    I_JFS_MODE,
    I_JFS_OK,
    I_JFS_OUTCOME,
    I_JFS_VARIANT,
    P_GB_EFF,
    P_HYD_T_REF,
    P_JFS_C_AERO,
    P_JFS_C_VISC,
    P_JFS_E_RATED,
    P_JFS_EGT_RISE,
    P_JFS_GOV_TAU,
    P_JFS_IGN_ALT,
    P_JFS_KE,
    P_JFS_M1_DRAG,
    P_JFS_M1_SCHED,
    P_JFS_N2_CUTOUT,
    P_JFS_N_LO,
    P_JFS_N_ON,
    P_JFS_N_SA,
    P_JFS_OIL_B,
    P_JFS_OIL_HEAT,
    P_JFS_OIL_USE_M1,
    P_JFS_OIL_USE_M2,
    P_JFS_P_GG,
    P_JFS_P_IGN,
    P_JFS_P_RATED,
    P_JFS_T_ACCEL,
    P_JFS_T_CRANK,
    P_JFS_T_ENGINE,
    P_JFS_TAU_EGT,
    P_JFS_TAU_OIL,
    P_JFS_THETA_EXP,
    P_JFS_VISC_EXP,
    P_JFS_W_FLOOR,
    P_N2_100PCT,
    P_PTO_TORQUE_PEAK,
)

JFS_OFF, JFS_CRANK, JFS_ACCEL, JFS_ENGAGED, JFS_COAST = 0, 1, 2, 3, 4
OUT_NONE, OUT_OK, OUT_SLOW_CRANK, OUT_NO_LIGHT, OUT_HUNG, OUT_ENGINE, OUT_ABORT = 0, 1, 2, 3, 4, 5, 6
P_SL = 101325.0  # Pa, ISA sea-level pressure (delta reference; ISO 2533)
T_SL = 288.15  # K, ISA sea-level temperature (theta reference; ISO 2533)
N_MIN = 0.02  # spool speed floor in the energy-form ODE (avoids 1/n at rest); numerical, not physical


@njit(**JIT)
def motor_on(f, i, p):
    """Starter motor energised: cranking/accelerating below the motor cut-out speed."""
    m = i[I_JFS_MODE]
    return (m == JFS_CRANK or m == JFS_ACCEL) and f[F_JFS_N].real < p[P_JFS_N_SA].real


@njit(**JIT)
def motor_emf(f, p):
    """Starter-motor back-EMF (V) at the current JFS speed."""
    return p[P_JFS_KE] * f[F_JFS_N]


@njit(**JIT)
def _finish(f, i, outcome):
    i[I_JFS_OUTCOME] = outcome
    i[I_JFS_MODE] = JFS_COAST
    i[I_JFS_LIT] = 0
    f[F_JFS_TMODE] = f[F_JFS_TMODE] - f[F_JFS_TMODE]
    if outcome == OUT_OK:
        i[I_JFS_CONSEC] = i[I_JFS_CONSEC] + 1
        i[I_JFS_OK] = i[I_JFS_OK] + 1
    else:
        i[I_JFS_CONSEC] = 0
        i[I_JFS_FAIL] = i[I_JFS_FAIL] + 1


@njit(**JIT)
def jfs_step(f, i, p, i_m, n2, w_pto, p_amb, t_amb, t_bay, u_ign, pwr_loss, drag_x, dt):
    """One JFS tick. Mutates f, i. Returns the power (W) delivered into the engine through the PTO (>= 0)."""
    mode = i[I_JFS_MODE]
    n = f[F_JFS_N]
    zero = n - n
    if mode == JFS_OFF:
        f[F_JFS_EGT] = f[F_JFS_EGT] + dt * (t_amb - f[F_JFS_EGT]) / p[P_JFS_TAU_EGT]
        f[F_JFS_OILT] = f[F_JFS_OILT] + dt * (t_bay - f[F_JFS_OILT]) / p[P_JFS_TAU_OIL]
        return zero
    m1 = i[I_JFS_VARIANT] == 1
    drag_f = p[P_JFS_M1_DRAG] if m1 else zero + 1.0
    sched = p[P_JFS_M1_SCHED] if m1 else zero + 1.0
    delta = p_amb / P_SL
    theta = t_amb / T_SL
    lapse = delta * theta ** p[P_JFS_THETA_EXP] * (1.0 - pwr_loss)  # free-turbine output lapse
    mu = visc_ratio(f[F_JFS_OILT], p[P_JFS_OIL_B], p[P_HYD_T_REF])
    n_lo = p[P_JFS_N_LO]
    lit = i[I_JFS_LIT]
    tm = f[F_JFS_TMODE] + dt
    p_out = zero

    def_drag = (
        n * n * (p[P_JFS_C_VISC] * mu ** p[P_JFS_VISC_EXP] * drag_f * (1.0 + drag_x) + p[P_JFS_C_AERO] * n)
    )
    p_m = p[P_JFS_KE] * i_m if motor_on(f, i, p) else zero  # k_e I: motor torque term (W per unit n)
    p_c = p[P_JFS_P_GG] * lapse * sched * clip((n - n_lo) / (1.0 - n_lo), 0.0, 1.0) if lit == 1 else zero

    if mode == JFS_ENGAGED:
        n = n + dt * (1.0 - n) / p[P_JFS_GOV_TAU]
        p_avail = p[P_JFS_P_RATED] * lapse - def_drag
        p_out = cmin(pos(p_avail), p[P_PTO_TORQUE_PEAK] * (pos(w_pto) + p[P_JFS_W_FLOOR])) * p[P_GB_EFF]
    else:
        # motor in torque form (k_e I / 2E_r, defined at standstill); combustion and drag in power form
        n_eff = n if n.real > N_MIN else zero + N_MIN
        e2 = 2.0 * p[P_JFS_E_RATED]
        n = pos(n + dt * (p_m / e2 + (p_c - def_drag) / (e2 * n_eff)))
    f[F_JFS_N] = n
    f[F_JFS_TMODE] = tm

    if mode == JFS_CRANK:
        if i[I_JFS_DRAWN] == 0 and n.real >= n_lo.real:
            i[I_JFS_DRAWN] = 1
            p_ign = p[P_JFS_P_IGN] * (1.0 - p[P_JFS_IGN_ALT] * (1.0 - delta))
            if u_ign < p_ign.real:
                i[I_JFS_LIT] = 1
                i[I_JFS_MODE] = JFS_ACCEL
                f[F_JFS_TMODE] = zero
                use = p[P_JFS_OIL_USE_M1] if m1 else p[P_JFS_OIL_USE_M2]
                f[F_JFS_OILQ] = f[F_JFS_OILQ] - use
        if i[I_JFS_MODE] == JFS_CRANK and tm.real > p[P_JFS_T_CRANK].real:
            _finish(f, i, OUT_SLOW_CRANK if i[I_JFS_DRAWN] == 0 else OUT_NO_LIGHT)
    elif mode == JFS_ACCEL:
        if n.real >= p[P_JFS_N_ON].real:
            i[I_JFS_MODE] = JFS_ENGAGED
            f[F_JFS_TMODE] = zero
        elif tm.real > p[P_JFS_T_ACCEL].real:
            _finish(f, i, OUT_HUNG)
    elif mode == JFS_ENGAGED:
        if n2.real >= (p[P_JFS_N2_CUTOUT] * p[P_N2_100PCT]).real:
            _finish(f, i, OUT_OK)
        elif tm.real > p[P_JFS_T_ENGINE].real:
            _finish(f, i, OUT_ENGINE)
    elif mode == JFS_COAST:
        if n.real < 0.005:
            i[I_JFS_MODE] = JFS_OFF
            f[F_JFS_N] = zero
            f[F_JFS_TMODE] = zero

    running = i[I_JFS_LIT] == 1
    egt_target = t_amb + (p[P_JFS_EGT_RISE] * (2.0 - f[F_JFS_N]) if running else zero)
    f[F_JFS_EGT] = f[F_JFS_EGT] + dt * (egt_target - f[F_JFS_EGT]) / p[P_JFS_TAU_EGT]
    oil_target = t_bay + (p[P_JFS_OIL_HEAT] if running else zero)
    f[F_JFS_OILT] = f[F_JFS_OILT] + dt * (oil_target - f[F_JFS_OILT]) / p[P_JFS_TAU_OIL]
    return p_out
