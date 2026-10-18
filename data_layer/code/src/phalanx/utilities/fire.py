"""Engine-bay fire/overheat detection (physical layer of the fire discretes) (M09).

Evidence: Tejas fire protection is a cartridge-fired extinguisher bottle discharged by push-button or crash
switch [DIRECT: ADA GS page]; fire-detection loops/zones on Tejas are not public (note KQ7 gaps). Historic
USAF fire detection: about 50 % of fires undetected and 83 % of warnings false [TRANSFER: DTIC AD0663213] -
the imperfect-BIT rates belong to M14; here they arise physically: a fire whose heat is carried away by bay
ventilation in flight may never heat the detector loop to its alarm temperature, and a shorted loop alarms
without a fire.

State machine: ``fire_on`` (truth; set by an M11 fault event), lumped bay-air temperature driven by
engine-case heat (bleed-port temperature as the HPC case proxy), fire heat release and ram ventilation;
detector loop alarm ``fire_warn`` when the bay air exceeds ``fire_t_alarm`` (loop condition ok), always
(shorted loop) or never (open loop). Extinguisher discharge is an event handled in ``module.py`` (keyed draw
for success).
"""

from __future__ import annotations

from numba import njit

from ._num import JIT, cmax
from .layout import (
    F_BAY_T,
    I_FIRE_DET,
    I_FIRE_ON,
    I_FIRE_WARN,
    P_BAY_HEAT_CAP,
    P_BAY_M_VENT_GROUND,
    P_BAY_UA_CASE,
    P_BAY_VENT_AREA,
    P_CP_AIR,
    P_FIRE_Q,
    P_FIRE_T_ALARM,
)

DET_OK, DET_OPEN, DET_SHORT = 0, 1, 2


@njit(**JIT)
def fire_step(f, i, p, t_case, t_rec, rho, tas, dt):
    """One tick of the bay thermal node and detector loop. Mutates f, i."""
    t = f[F_BAY_T]
    m_vent = cmax(rho * tas * p[P_BAY_VENT_AREA] + 0.0 * t, p[P_BAY_M_VENT_GROUND] + 0.0 * t)
    q = p[P_BAY_UA_CASE] * (t_case - t) - m_vent * p[P_CP_AIR] * (t - t_rec)
    if i[I_FIRE_ON] == 1:
        q = q + p[P_FIRE_Q]
    t = t + dt * q / p[P_BAY_HEAT_CAP]
    f[F_BAY_T] = t
    det = i[I_FIRE_DET]
    if det == DET_SHORT:
        i[I_FIRE_WARN] = 1
    elif det == DET_OPEN:
        i[I_FIRE_WARN] = 0
    else:
        i[I_FIRE_WARN] = 1 if t.real > p[P_FIRE_T_ALARM].real else 0
