"""Proxy demand pre-map: the MEASURED flight-condition terms of the fuel-control law, fed to M08's lever
input.

M08's corrected-core-speed demand is a function of PLA only (``n2c_pla``, built by ``proxy.schedules`` at the
ground reference: M 0, delta = theta = 1). The round-2 MEASURED fuel-control law of the proxy engines also
depends on the flight condition:

    Wd = f_P(PLA) + cM (M - 0.5) + cD ln(delta) + cT (theta - 1)   [corrected lb/h]

and the demand is g(Wd) (frozen M-A, 687-CAL). Since the table is g(f_P(PLA') + cM (0 - 0.5)) carried to
theta25, feeding M08 the **effective lever** PLA' with

    f_P(PLA') = f_P(PLA) + cM M + cD ln(delta) + cT (theta - 1)

gives exactly the measured demand at every flight condition, through M08's existing input (coordinator
decision on the W2.4a-2 stage-1 item (i): a proxy-specific pre-map, no new M08 schedule dimension). It is
mathematically equivalent wherever the target lies inside the table's lever range; below the first f knot (the
idle stop) the lever is passed unchanged (the fuel cut-off logic sees the recorded lever), and a target beyond
the top knot is held at the top knot, where the table is flat (M08 clamps there too). f_P is monotone (PCHIP,
linear end extrapolation; the round-2 ``MonoMap`` convention), so the inverse is unique.

delta = p_t2 / p_SL (ISA static pressure at the pressure altitude, full ram recovery), theta = TAT / 288.15
(the round-2 convention, ``validation.dashlink.corrections``).

**A/T floor** (coordinator decision, W2.4a-2 stage 2 item): M08's A/T demand was floored at the table's
lowest demand, the ground idle, so in high-altitude idle descents the A/T could ask for less than the real
flight idle and the fuel sat on the minimum clamp (0.7-7.5 % of a CAL flight). With ``at_floor_idle_stop`` the
proxy feeds M08 the pre-mapped **idle-stop** lever while the A/T is engaged, and M08's option
``at_floor_lever`` floors the A/T demand at that lever's demand: the measured flight idle at the condition.
In manual segments M08 is fed the pre-mapped recorded lever as before.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phalanx.core.module import ParamSet
from phalanx.validation.dashlink import corrections

from .schedules import _monotone_pchip

FT = 0.3048
_GRID = 4001


@dataclass(frozen=True)
class DemandPremap:
    """Parameters in SI as the parameter loader delivers them (lever in rad, corrected fuel in kg/s); the map
    is linear in both units, so the effective lever does not depend on them."""

    f_pla: tuple[float, ...]  # rad
    f_wfc: tuple[float, ...]  # kg/s (corrected)
    c_mach: float  # kg/s per unit Mach
    c_lndelta: float  # kg/s per unit ln(delta)
    c_theta: float  # kg/s per unit (theta - 1)
    table_mach: float = 0.0
    #: A/T floor at the idle stop (M08 option ``at_floor_lever``): while the A/T is engaged M08 is fed the
    #: pre-mapped idle-stop lever and floors the A/T demand at its demand (the flight idle at the condition)
    idle_stop: float = 0.0  # rad
    at_floor: bool = False

    @classmethod
    def from_params(cls, ps: ParamSet) -> DemandPremap:
        return cls(
            tuple(float(v) for v in np.asarray(ps.value("f_pla_deg"), float)),
            tuple(float(v) for v in np.asarray(ps.value("f_wfc_lbh"), float)),
            float(ps.value("c_mach")),
            float(ps.value("c_lndelta")),
            float(ps.value("c_theta")),
            float(ps.value("table_mach")),
            float(ps.value("idle_stop_pla")),
            bool(int(ps.value("at_floor_idle_stop"))),
        )

    def delta_wfc(self, mach: np.ndarray, delta: np.ndarray, theta: np.ndarray) -> np.ndarray:
        """Corrected-fuel offset of the flight condition relative to the table's reference condition."""
        return (
            self.c_mach * (np.asarray(mach, float) - self.table_mach)
            + self.c_lndelta * np.log(np.asarray(delta, float))
            + self.c_theta * (np.asarray(theta, float) - 1.0)
        )

    def effective_pla(
        self, pla_rad: np.ndarray, alt_ft: np.ndarray, mach: np.ndarray, tat_c: np.ndarray
    ) -> np.ndarray:
        """The lever M08 is fed, (E, n) [rad], from the recorded levers (E, n) [rad] and the flight condition
        (n,)."""
        pla = np.asarray(pla_rad, float)
        th, de = corrections(np.asarray(alt_ft, float), np.asarray(mach, float), np.asarray(tat_c, float))
        x0, x1 = self.f_pla[0], self.f_pla[-1]
        f = _monotone_pchip(self.f_pla, self.f_wfc)
        grid = np.linspace(x0, x1, _GRID)
        fg = np.asarray(f(grid), float)
        target = np.asarray(f(pla), float) + self.delta_wfc(mach, de, th)[None, :]
        eff = np.interp(target, fg, grid)  # clamps to [x0, x1]: the table is flat beyond the top knot
        return np.where(pla < x0, pla, eff)

    def lever_fed(self, pla_rad: np.ndarray, at_engage: np.ndarray) -> np.ndarray:
        """The recorded lever, or the idle stop while the A/T is engaged when the A/T floor option is on
        (before the pre-map). The first sample keeps the recorded lever: M08's bootstrap demand, from which an
        engaged A/T starts bumplessly, is then the recorded operating point."""
        pla = np.asarray(pla_rad, float)
        if not self.at_floor:
            return pla
        sub = np.asarray(at_engage) == 1
        sub[:1] = False
        return np.where(sub[None, :], self.idle_stop, pla)


__all__ = ["DemandPremap"]
