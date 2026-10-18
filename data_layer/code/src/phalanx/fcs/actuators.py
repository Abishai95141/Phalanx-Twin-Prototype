"""M05 actuator physics (13 surfaces): valve-controlled hydraulic servos, ``@njit`` and complex-step safe.

Per surface (architecture §6 M05; report §1 Actuation row; ``tejas_airframe_aero_fcs.md`` Q2):

- **Servo:** position loop + valve dynamics, a second-order response with natural frequency ``wn`` (the
  published ~9 Hz) and damping ``zeta``: ``v' = (sat(Ka (cmd - x), v+, v-) - v) / tau_v``, ``x' = v -
  v_leak``,
  ``tau_v = 1 / (2 zeta wn)``, ``Ka = wn / (2 zeta)``.
- **Rate capability** follows the valve flow law (report §3, TRANSFER: HARV):
  ``v+ = v0 sqrt(max(dP_avail - P_L, 0) / dP_rated)`` for motion against the load pressure ``P_L`` and
  ``v- = v0 sqrt(max(dP_avail + P_L, 0) / dP_rated)`` the other way; ``P_L = -H / (arm A_eff)`` is the load
  pressure from the true aerodynamic hinge moment ``H`` (positive H aids positive motion). Tandem primaries
  (elevons, rudder) have one section per hydraulic system: a section is active when its system supplies more
  than ``dp_min``; the rate capability is the smaller of the active sections' and ``A_eff`` sums them.
- **Leakage** (``health.actuator`` h >= 0 scales both): cross-port leakage ``v_leak = Gcp (1 + h) P_L /
A_eff``
  (droop under load, lower loaded rate) and quiescent null flow ``Q_null = Gnull (1 + h) dP_avail`` per
  section.
- **Flow demand** per system: ``Q = A_sec |v| + Q_null`` summed over the active sections on that system
  (``Q = A x'`` plus the leakage paths; conservation tested in A5).
- **Faults:** ``jam[s] = 1`` freezes the surface (M11 event). Loss of every supplying system freezes it too
  (A-W1.2-20: a real surface would float to its hinge-moment equilibrium).

Complex-step safety (AD-34): every comparison and branch uses ``.real``; ``max``/``min``/``abs``/saturation go
through helpers that branch on the real part and return derivative-carrying values.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from phalanx.airframe.aero import hinge_moments
from phalanx.airframe.geodesy import NJ

# actuator table columns (rows = 13 surfaces, fcs.surf_pos order)
(
    C_POSMIN,
    C_POSMAX,
    C_V0,
    C_WN,
    C_ZETA,
    C_AREA,
    C_ARM,
    C_NSEC,
    C_SYS,
    C_GNULL,
    C_GCP,
) = range(11)
N_ACOLS = 11


@njit(**NJ)
def cs_pos(x):
    """max(x, 0) on the real part, keeping the derivative where x > 0."""
    return x if x.real > 0.0 else 0.0 * x


@njit(**NJ)
def cs_abs(x):
    return x if x.real >= 0.0 else -x


@njit(**NJ)
def rate_capability(dp_sec, n_active, p_load, v0, dp_rated):
    """(v+, v-) for one actuator given per-section available pressures (inactive sections already removed).

    ``dp_sec`` is a 2-tuple of section pressures (use the same value twice for single-section actuators).
    """
    vp0 = v0 * np.sqrt(cs_pos(dp_sec[0] - p_load) / dp_rated)
    vm0 = v0 * np.sqrt(cs_pos(dp_sec[0] + p_load) / dp_rated)
    if n_active > 1:
        vp1 = v0 * np.sqrt(cs_pos(dp_sec[1] - p_load) / dp_rated)
        vm1 = v0 * np.sqrt(cs_pos(dp_sec[1] + p_load) / dp_rated)
        if vp1.real < vp0.real:
            vp0 = vp1
        if vm1.real < vm0.real:
            vm0 = vm1
    return vp0, vm0


@njit(**NJ)
def _sections(s, dp_avail, atab, dp_min):
    """Active-section pressures and count for surface ``s``; also which systems are active (0/1 flags)."""
    if atab[s, C_NSEC].real > 1.5:
        a0 = dp_avail[0].real > dp_min
        a1 = dp_avail[1].real > dp_min
        if a0 and a1:
            return dp_avail[0], dp_avail[1], 2, 1.0, 1.0
        if a0:
            return dp_avail[0], dp_avail[0], 1, 1.0, 0.0
        if a1:
            return dp_avail[1], dp_avail[1], 1, 0.0, 1.0
        return dp_avail[0], dp_avail[0], 0, 0.0, 0.0
    h = 0 if atab[s, C_SYS].real < 0.5 else 1
    if dp_avail[h].real > dp_min:
        if h == 0:
            return dp_avail[0], dp_avail[0], 1, 1.0, 0.0
        return dp_avail[1], dp_avail[1], 1, 0.0, 1.0
    return dp_avail[h], dp_avail[h], 0, 0.0, 0.0


@njit(**NJ)
def _rhs(
    pos, vel, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, dpos, dvel
):
    """Time derivatives of (pos, vel) for all surfaces; ``hm`` is hinge-moment scratch."""
    hinge_moments(alpha, beta, qbar, pos, htab, hm)
    for s in range(pos.shape[0]):
        d0, d1, n_act, _f0, _f1 = _sections(s, dp_avail, atab, dp_min)
        if jam[s] != 0 or n_act == 0:
            dpos[s] = 0.0 * vel[s]
            dvel[s] = -vel[s] * 2.0 * atab[s, C_ZETA] * atab[s, C_WN]
            continue
        wn = atab[s, C_WN]
        zeta = atab[s, C_ZETA]
        a_eff = atab[s, C_AREA] * n_act
        p_load = -hm[s] / (atab[s, C_ARM] * a_eff)
        vp, vm = rate_capability((d0, d1), n_act, p_load, atab[s, C_V0], dp_rated)
        ka = wn / (2.0 * zeta)
        vd = ka * (cmd[s] - pos[s])
        if vd.real > vp.real:
            vd = vp
        elif vd.real < -vm.real:
            vd = -vm
        # cross-port droop: leak flow G p over the piston area is a ram speed; / arm -> surface rate (W2.1a-2:
        # was used as a surface rate directly, arm ~0.1 m too small)
        v_leak = atab[s, C_GCP] * (1.0 + health[s]) * p_load / atab[s, C_AREA] / n_act / atab[s, C_ARM]
        dvel[s] = (vd - vel[s]) * 2.0 * zeta * wn
        dpos[s] = vel[s] - v_leak


@njit(**NJ)
def actuator_tick(
    pos, vel, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, dt, n_sub
):
    """Advance all actuators by one truth tick (RK4, ``n_sub`` sub-steps, position stops after each sub-step).

    Returns ``(pos, vel, rate, flow)``: new positions and valve velocities, the surface rate ``x'`` at the end
    of the tick, and the hydraulic flow demand per system (m^3/s). Pure (fresh arrays); complex-step safe.
    """
    n = pos.shape[0]
    dt_ = pos.dtype
    p = pos.copy()
    v = vel.copy()
    hm = np.empty(n, dtype=dt_)
    k1p = np.empty(n, dtype=dt_)
    k1v = np.empty(n, dtype=dt_)
    k2p = np.empty(n, dtype=dt_)
    k2v = np.empty(n, dtype=dt_)
    k3p = np.empty(n, dtype=dt_)
    k3v = np.empty(n, dtype=dt_)
    k4p = np.empty(n, dtype=dt_)
    k4v = np.empty(n, dtype=dt_)
    tp = np.empty(n, dtype=dt_)
    tv = np.empty(n, dtype=dt_)
    h = dt / n_sub
    for _ in range(n_sub):
        _rhs(p, v, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, k1p, k1v)
        for s in range(n):
            tp[s] = p[s] + 0.5 * h * k1p[s]
            tv[s] = v[s] + 0.5 * h * k1v[s]
        _rhs(
            tp, tv, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, k2p, k2v
        )
        for s in range(n):
            tp[s] = p[s] + 0.5 * h * k2p[s]
            tv[s] = v[s] + 0.5 * h * k2v[s]
        _rhs(
            tp, tv, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, k3p, k3v
        )
        for s in range(n):
            tp[s] = p[s] + h * k3p[s]
            tv[s] = v[s] + h * k3v[s]
        _rhs(
            tp, tv, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, k4p, k4v
        )
        for s in range(n):
            p[s] = p[s] + h / 6.0 * (k1p[s] + 2.0 * k2p[s] + 2.0 * k3p[s] + k4p[s])
            v[s] = v[s] + h / 6.0 * (k1v[s] + 2.0 * k2v[s] + 2.0 * k3v[s] + k4v[s])
            if p[s].real > atab[s, C_POSMAX].real:  # mechanical stops
                p[s] = atab[s, C_POSMAX] + 0.0 * p[s]
                if v[s].real > 0.0:
                    v[s] = 0.0 * v[s]
            elif p[s].real < atab[s, C_POSMIN].real:
                p[s] = atab[s, C_POSMIN] + 0.0 * p[s]
                if v[s].real < 0.0:
                    v[s] = 0.0 * v[s]
    # end-of-tick rate and flow demand
    _rhs(p, v, cmd, dp_avail, alpha, beta, qbar, health, jam, atab, htab, dp_rated, dp_min, hm, k1p, k1v)
    flow = np.zeros(2, dtype=dt_)
    for s in range(n):
        _d0, _d1, n_act, f0, f1 = _sections(s, dp_avail, atab, dp_min)
        at_stop = (p[s].real >= atab[s, C_POSMAX].real and k1p[s].real > 0.0) or (
            p[s].real <= atab[s, C_POSMIN].real and k1p[s].real < 0.0
        )
        if at_stop:
            k1p[s] = 0.0 * k1p[s]
        if n_act == 0:
            continue
        # piston flow = area x ram speed, ram speed = arm x surface rate (W2.1a-2: the arm was missing, so the
        # demand was ~1/arm = 8x too high and full-rate elevon inputs collapsed the 280 bar systems)
        q_sec = atab[s, C_AREA] * atab[s, C_ARM] * cs_abs(v[s]) * (0.0 if jam[s] != 0 else 1.0)
        leak = atab[s, C_GNULL] * (1.0 + health[s])
        flow[0] += f0 * (q_sec + leak * dp_avail[0])
        flow[1] += f1 * (q_sec + leak * dp_avail[1])
    return p, v, k1p, flow


def actuator_tick_reference(*args):
    """NumPy reference: the same source, uncompiled."""
    return actuator_tick.py_func(*args)
