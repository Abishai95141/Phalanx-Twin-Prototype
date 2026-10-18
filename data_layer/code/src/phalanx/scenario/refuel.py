"""``util.refuel`` targets (M02 -> M09, AD-44 catalogue; AD-49 fill-to-target): the sortie's planned fuel load
per M09 tank.

The plan carries the total load (full internal fuel plus full drop tanks, :class:`~.plan.SortiePlan`
``fuel_kg`` / ``drop_tanks``). It is split over M09's tanks (``phalanx.utilities.layout.TANKS`` order, the
dictionary ``FUEL.QTY.TANK.<name>`` order): internal fuel in proportion to the internal tank volumes of the
M09 tank table, two drop tanks on the inboard stations [ASSUMPTION A-W1.1-37]. Each share is a **target**
mass (AD-49): M09 fills the tank up to it with fuel at the station temperature (``t_fuel``), stops at the
tank volume at the mixed fuel temperature (its own density law: a full tank on a hot day holds less mass)
and never defuels, so M09 need not start empty and M02 needs no density estimate of its own.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .config import ScenarioParams
from .plan import SortiePlan


@lru_cache(maxsize=1)
def _m09_caps() -> np.ndarray:
    from phalanx.utilities import layout as UL
    from phalanx.utilities import load_m09_params
    from phalanx.utilities.params import param_vector

    p9 = param_vector(load_m09_params())
    return np.array([p9[UL.P_TANK + UL.TC_CAP * UL.N_TANKS + k] for k in range(UL.N_TANKS)])


def refuel_loads(plan: SortiePlan, params: ScenarioParams) -> list[tuple[int, float]]:
    """[(M09 tank index, target kg)] for the plan's fuel load (shares sum to ``plan.fuel_kg``)."""
    from phalanx.utilities import layout as UL

    caps = _m09_caps()
    internal = (UL.T_F1, UL.T_F1A, UL.T_F2, UL.T_WL, UL.T_WR)
    n_drop = int(plan.drop_tanks)
    if n_drop not in (0, 2):
        raise ValueError(f"{n_drop} drop tanks: M02 plans 0 or 2 (inboard pair)")
    internal_kg = float(plan.fuel_kg) - n_drop * params.drop_tank_kg
    v_int = float(sum(caps[k] for k in internal))
    out = [(k, internal_kg * float(caps[k]) / v_int) for k in internal]
    if n_drop:
        out += [(k, float(params.drop_tank_kg)) for k in (UL.T_DTL, UL.T_DTR)]
    return out


__all__ = ["refuel_loads"]
