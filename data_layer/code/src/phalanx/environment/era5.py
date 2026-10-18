"""ERA5 replay interface and adapter (architecture §6 M03 "ERA5 replay with METAR override").

Evidence (report §7 row 3; research_notes/.../modelling_methodology.md §1): ERA5 hourly reanalysis on 37
pressure levels (0.25 deg grid, native ~31 km) supplies temperature, specific humidity, u/v wind and
geopotential; METAR/ISD surface observations override the near-surface values at the airfield; IGRA
radiosondes validate. ERA5 cannot resolve turbulence or convective gusts, so the stochastic turbulence is
superimposed on ERA5 mean winds, never replaced by them.

W1 scope: the interface and a small adapter from arrays (no download, no NetCDF reader: a W2 data task reads
the CDS files into :class:`Era5Column`). Tests use a synthetic fixture.

Adapter rules:
- time: linear interpolation between the two bracketing analysis times;
- vertical: nodes at the geopotential altitude H = z / g0 of each level (sorted ascending), temperature
  linear in H between nodes, ``ln e`` linear, winds linear (u east, v north);
- pressure: hydrostatically integrated (dry temperature, the evaluator's own form) from an anchor — the
  METAR station pressure at the field if given, else the lowest ERA5 level. The residual against the ERA5
  level pressures (the virtual-temperature effect, ~0.1-0.5 %) is reported by :func:`pressure_residual`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .atmosphere import NMAX, PR_H, PR_P, Constants, build_profile, geopotential_altitude, profile_tp


@dataclass(frozen=True)
class Era5Column:
    """ERA5 pressure-level data at one location: ``nt`` analysis times x ``nl`` levels (SI units)."""

    times_utc_s: np.ndarray  # (nt,)
    pressure_pa: np.ndarray  # (nl,) level pressures
    geopotential: np.ndarray  # (nt, nl) m^2/s^2 (ERA5 variable z)
    temperature_k: np.ndarray  # (nt, nl)
    specific_humidity: np.ndarray  # (nt, nl) kg/kg
    u_mps: np.ndarray  # (nt, nl) eastward
    v_mps: np.ndarray  # (nt, nl) northward

    def __post_init__(self) -> None:
        nt, nl = np.shape(self.temperature_k)
        for name in ("geopotential", "specific_humidity", "u_mps", "v_mps"):
            if np.shape(getattr(self, name)) != (nt, nl):
                raise ValueError(f"{name} must have shape ({nt}, {nl})")
        if np.shape(self.times_utc_s) != (nt,) or np.shape(self.pressure_pa) != (nl,):
            raise ValueError("times (nt,) and pressure levels (nl,) required")
        if nl + 1 > NMAX or nt < 1:
            raise ValueError(f"at most {NMAX - 1} levels and at least one time")
        if np.any(np.diff(self.times_utc_s) <= 0):
            raise ValueError("times must increase")


@dataclass(frozen=True)
class MetarOverride:
    """Surface observation at the airfield (station level)."""

    field_elev_m: float  # geometric
    p_station_pa: float
    t_k: float
    dewpoint_k: float
    wind_speed_mps: float = 0.0
    wind_from_rad: float = 0.0


def _interp_time(col: Era5Column, t_utc_s: float) -> tuple[float, int, int]:
    ts = np.asarray(col.times_utc_s, dtype=float)
    if t_utc_s <= ts[0]:
        return 0.0, 0, 0
    if t_utc_s >= ts[-1]:
        return 0.0, ts.size - 1, ts.size - 1
    j = int(np.searchsorted(ts, t_utc_s, side="right") - 1)
    return (t_utc_s - ts[j]) / (ts[j + 1] - ts[j]), j, j + 1


def vapour_pressure(q: np.ndarray, p: np.ndarray, c: Constants) -> np.ndarray:
    eps = c.m_water / c.m0
    return q * p / (eps + (1.0 - eps) * q)


def profile_at(
    col: Era5Column,
    t_utc_s: float,
    c: Constants,
    magnus: np.ndarray,
    *,
    metar: MetarOverride | None = None,
) -> tuple[np.ndarray, int]:
    """Profile (rows H, T, P, ln e, wind N, wind E) at time ``t_utc_s`` (see module docstring)."""
    w, j0, j1 = _interp_time(col, t_utc_s)

    def tint(a):
        a = np.asarray(a, dtype=float)
        return (1 - w) * a[j0] + w * a[j1]

    h = tint(col.geopotential) / c.g0
    t = tint(col.temperature_k)
    q = tint(col.specific_humidity)
    p_lev = np.asarray(col.pressure_pa, dtype=float)
    e = np.maximum(vapour_pressure(q, p_lev, c), 1e-6)
    wn = tint(col.v_mps)
    we = tint(col.u_mps)
    order = np.argsort(h)
    h, t, e, wn, we, p_lev = h[order], t[order], e[order], wn[order], we[order], p_lev[order]
    if metar is not None:
        hs = float(geopotential_altitude(metar.field_elev_m, c.r0))
        keep = h > hs + 1.0
        tc = metar.dewpoint_k - 273.15
        es = magnus[0] * math.exp(magnus[1] * tc / (tc + magnus[2]))
        wn_s = -metar.wind_speed_mps * math.cos(metar.wind_from_rad)
        we_s = -metar.wind_speed_mps * math.sin(metar.wind_from_rad)
        h = np.concatenate([[hs], h[keep]])
        t = np.concatenate([[metar.t_k], t[keep]])
        e = np.concatenate([[es], e[keep]])
        wn = np.concatenate([[wn_s], wn[keep]])
        we = np.concatenate([[we_s], we[keep]])
        anchor_h, anchor_p = hs, metar.p_station_pa
    else:
        anchor_h, anchor_p = float(h[0]), float(p_lev[0])
    return build_profile(
        h, t, c, p_anchor=anchor_p, h_anchor=anchor_h, lne_nodes=np.log(e), wn_nodes=wn, we_nodes=we
    )


def pressure_residual(col: Era5Column, t_utc_s: float, c: Constants, magnus: np.ndarray) -> np.ndarray:
    """Relative difference between the adapter's hydrostatic pressure at each level height and the ERA5
    level pressure (no METAR override)."""
    prof, n = profile_at(col, t_utc_s, c, magnus)
    w, j0, j1 = _interp_time(col, t_utc_s)
    h = ((1 - w) * np.asarray(col.geopotential)[j0] + w * np.asarray(col.geopotential)[j1]) / c.g0
    cv = c.vector()
    p_model = np.array([profile_tp(prof, n, float(x), cv)[1] for x in h])
    return p_model / np.asarray(col.pressure_pa, dtype=float) - 1.0


__all__ = [
    "PR_H",
    "PR_P",
    "Era5Column",
    "MetarOverride",
    "pressure_residual",
    "profile_at",
    "vapour_pressure",
]
