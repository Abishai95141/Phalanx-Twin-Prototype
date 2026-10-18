"""Atmosphere: USSA-1976 / ISA, layered non-standard profiles and moist-air state (architecture §6 M03).

Evidence:
- USSA-1976 (NASA-TM-X-74335) is the baseline atmosphere; "identical with the ICAO Standard (1964) up to
  32 km" [DIRECT: standard] (report §7 row 1; research_notes/.../modelling_methodology.md §1).
- Non-standard (climatic-extreme) atmospheres keep the USSA **pressure vs geopotential altitude** and vary the
  temperature (JSSG-2007A Figure 5 note 4: "The ambient static pressure variation shall be as defined in U.S.
  Standard Atmosphere for geopotential altitude") [TRANSFER: USAF engine spec]. Climatology and replay
  atmospheres instead integrate hydrostatically from a surface pressure anchor (``pressure_mode``).
- Humidity enters as specific humidity and through the virtual temperature (report §3: humidity is "of the
  same order as engine-to-engine scatter"; modelling_methodology.md §1).

Representation (one code path for every atmosphere): a **profile** of up to ``NMAX`` nodes over geopotential
altitude H (m'), with temperature T (K) linear between nodes, static pressure P (Pa) hydrostatically
consistent with that temperature, ``ln e`` (vapour pressure, Pa) linear between nodes (exact for an
exponential decay) and wind components (m/s, NED north/east) linear between nodes. Below the first node and
above the last the end segment is extended (USSA itself extends its first gradient down to -5 km).

The ``@njit`` evaluators are pure functions of (profile arrays, constants, altitude); the NumPy reference is
the same source uncompiled (``.py_func``). Units: SI throughout (m, K, Pa, kg/m^3, m/s).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numba import njit

# --- constants vector layout (filled from configs/tejas/params/M03.yaml set `atmosphere`) ----------------
C_R_STAR, C_M0, C_G0, C_R0, C_GAMMA, C_M_WATER = 0, 1, 2, 3, 4, 5
CONST_NAMES = ("r_star", "m0", "g0", "r0", "gamma", "m_water")

NMAX = 48  # profile nodes (ERA5: 37 pressure levels + surface/top padding)
# profile array rows
PR_H, PR_T, PR_P, PR_LNE, PR_WN, PR_WE = 0, 1, 2, 3, 4, 5
N_PROFILE_ROWS = 6

# Magnus saturation vapour pressure over water (Pa) [TRANSFER: standard meteorology; constants in M03.yaml]
_LAPSE_EPS = 1e-12  # K/m: below this a segment is treated as isothermal


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def geopotential_altitude(z_m, r0):
    """Geometric altitude Z (m) -> geopotential altitude H (m'), USSA-1976 eq. 18: H = r0 Z / (r0 + Z)."""
    return r0 * z_m / (r0 + z_m)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def geometric_altitude(h_m, r0):
    """Inverse of :func:`geopotential_altitude`: Z = r0 H / (r0 - H)."""
    return r0 * h_m / (r0 - h_m)


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _segment(prof, n, h):
    """Index j of the segment [H_j, H_{j+1}) containing h, clamped to [0, n-2] (end segments extend)."""
    j = 0
    while j < n - 2 and h >= prof[PR_H, j + 1]:
        j += 1
    return j


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _hydrostatic_ratio(t_j, lapse, dh, t_h, g0, m0, r_star):
    """P(H)/P(H_j) for a linear-temperature segment (USSA-1976 eqs. 33a/33b)."""
    if abs(lapse) < _LAPSE_EPS:
        return math.exp(-g0 * m0 * dh / (r_star * t_j))
    return (t_h / t_j) ** (-g0 * m0 / (r_star * lapse))


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def profile_tp(prof, n, h, c):
    """Temperature (K) and pressure (Pa) at geopotential altitude h (m') from a profile."""
    j = _segment(prof, n, h)
    h0 = prof[PR_H, j]
    t0 = prof[PR_T, j]
    lapse = (prof[PR_T, j + 1] - t0) / (prof[PR_H, j + 1] - h0)
    t = t0 + lapse * (h - h0)
    p = prof[PR_P, j] * _hydrostatic_ratio(t0, lapse, h - h0, t, c[C_G0], c[C_M0], c[C_R_STAR])
    return t, p


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def _lin(prof, row, n, h):
    j = _segment(prof, n, h)
    h0 = prof[PR_H, j]
    w = (h - h0) / (prof[PR_H, j + 1] - h0)
    return prof[row, j] + w * (prof[row, j + 1] - prof[row, j])


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def saturation_vapour_pressure(t_k, a_pa, b, c_k):
    """Magnus form e_s = a exp(b (T - 273.15) / (T - 273.15 + c)) (Pa) [TRANSFER: standard meteorology]."""
    tc = t_k - 273.15
    return a_pa * math.exp(b * tc / (tc + c_k))


@njit(cache=True, fastmath=False, error_model="numpy", nogil=True)
def moist_state(prof, n, z_geometric, c, magnus):
    """Full atmospheric state at geometric altitude z (m).

    Returns (T K, p Pa, rho kg/m^3, a m/s, q kg/kg, wind_north m/s, wind_east m/s). Density and speed of
    sound use the virtual temperature T_v = T (1 + (1/eps - 1) q) with eps = M_water / M0 (moist air is
    lighter). With zero vapour (ln e very negative) the result is the dry USSA-1976 state exactly.
    """
    r_star = c[C_R_STAR]
    m0 = c[C_M0]
    h = geopotential_altitude(z_geometric, c[C_R0])
    t, p = profile_tp(prof, n, h, c)
    e = math.exp(_lin(prof, PR_LNE, n, h))
    es = saturation_vapour_pressure(t, magnus[0], magnus[1], magnus[2])
    if e > es:
        e = es
    eps = c[C_M_WATER] / m0
    q = eps * e / (p - (1.0 - eps) * e)
    tv = t * (1.0 + (1.0 / eps - 1.0) * q)
    r_d = r_star / m0
    rho = p / (r_d * tv)
    a = math.sqrt(c[C_GAMMA] * r_d * tv)
    wn = _lin(prof, PR_WN, n, h)
    we = _lin(prof, PR_WE, n, h)
    return t, p, rho, a, q, wn, we


# ----------------------------------------------------------------------------------------------- builders


@dataclass(frozen=True)
class Constants:
    """USSA-1976 defining constants (SI) taken from the M03 `atmosphere` parameter set."""

    r_star: float  # J/(kmol K)
    m0: float  # kg/kmol
    g0: float  # m^2/(s^2 m')
    r0: float  # m
    gamma: float
    m_water: float  # kg/kmol

    def vector(self) -> np.ndarray:
        v = np.array([self.r_star, self.m0, self.g0, self.r0, self.gamma, self.m_water], dtype=np.float64)
        v.flags.writeable = False
        return v


def empty_profile() -> np.ndarray:
    return np.zeros((N_PROFILE_ROWS, NMAX), dtype=np.float64)


def _propagate_pressure(h: np.ndarray, t: np.ndarray, anchor_j: int, p_anchor_node: float, c) -> np.ndarray:
    """Hydrostatic node pressures given the pressure at node ``anchor_j`` (same formula as the evaluator)."""
    n = h.size
    p = np.zeros(n)
    p[anchor_j] = p_anchor_node
    for j in range(anchor_j, n - 1):
        lapse = (t[j + 1] - t[j]) / (h[j + 1] - h[j])
        p[j + 1] = p[j] * _hydrostatic_ratio(t[j], lapse, h[j + 1] - h[j], t[j + 1], c.g0, c.m0, c.r_star)
    for j in range(anchor_j - 1, -1, -1):
        lapse = (t[j + 1] - t[j]) / (h[j + 1] - h[j])
        p[j] = p[j + 1] / _hydrostatic_ratio(t[j], lapse, h[j + 1] - h[j], t[j + 1], c.g0, c.m0, c.r_star)
    return p


def build_profile(
    h_nodes: np.ndarray,
    t_nodes: np.ndarray,
    c: Constants,
    *,
    p_anchor: float,
    h_anchor: float,
    lne_nodes: np.ndarray | None = None,
    wn_nodes: np.ndarray | None = None,
    we_nodes: np.ndarray | None = None,
) -> tuple[np.ndarray, int]:
    """A profile (rows H, T, P, ln e, wind N, wind E) hydrostatically anchored at (h_anchor m', p_anchor Pa).

    ``h_nodes`` strictly increasing geopotential altitudes; temperatures in K. Missing humidity means dry air
    (ln e = -1e3 Pa, i.e. e ~ 0) and missing winds mean calm.
    """
    h = np.asarray(h_nodes, dtype=np.float64)
    t = np.asarray(t_nodes, dtype=np.float64)
    n = h.size
    if n < 2 or n > NMAX or t.shape != h.shape or np.any(np.diff(h) <= 0) or np.any(t <= 0):
        raise ValueError("profile needs 2..NMAX strictly increasing nodes with T > 0")
    j = int(np.clip(np.searchsorted(h, h_anchor, side="right") - 1, 0, n - 2))
    lapse = (t[j + 1] - t[j]) / (h[j + 1] - h[j])
    t_a = t[j] + lapse * (h_anchor - h[j])
    ratio = _hydrostatic_ratio(t[j], lapse, h_anchor - h[j], t_a, c.g0, c.m0, c.r_star)
    p = _propagate_pressure(h, t, j, p_anchor / ratio, c)
    prof = empty_profile()
    prof[PR_H, :n] = h
    prof[PR_T, :n] = t
    prof[PR_P, :n] = p
    prof[PR_LNE, :n] = -1000.0 if lne_nodes is None else np.asarray(lne_nodes, dtype=np.float64)
    prof[PR_WN, :n] = 0.0 if wn_nodes is None else np.asarray(wn_nodes, dtype=np.float64)
    prof[PR_WE, :n] = 0.0 if we_nodes is None else np.asarray(we_nodes, dtype=np.float64)
    return prof, n


@dataclass(frozen=True)
class UssaLayers:
    """USSA-1976 layer table below 86 km: base geopotential heights (m') and gradients (K/m')."""

    h_base: np.ndarray
    lapse: np.ndarray
    t0: float  # K at H = 0
    p0: float  # Pa at H = 0

    def node_temperatures(self) -> np.ndarray:
        t = [self.t0]
        for j in range(self.lapse.size):
            t.append(t[-1] + self.lapse[j] * (self.h_base[j + 1] - self.h_base[j]))
        return np.array(t)


def ussa76_profile(layers: UssaLayers, c: Constants, *, dt_k: float = 0.0) -> tuple[np.ndarray, int]:
    """The USSA-1976 profile (``dt_k`` = 0) or the ISA+dT atmosphere anchored at the standard sea-level
    pressure (temperature offset at every altitude; ICAO-style "ISA deviation")."""
    t = layers.node_temperatures() + dt_k
    return build_profile(layers.h_base, t, c, p_anchor=layers.p0, h_anchor=0.0)


def anchored_offset_profile(
    layers: UssaLayers,
    c: Constants,
    *,
    h_station: float,
    p_station: float,
    t_station: float,
    e_station: float,
    vapour_scale_height: float,
    wind_north: float = 0.0,
    wind_east: float = 0.0,
) -> tuple[np.ndarray, int]:
    """Climatology atmosphere: USSA gradients with a constant temperature offset chosen so that T equals the
    station temperature at the station's geopotential height, pressure hydrostatically anchored at the
    station pressure, and vapour pressure decaying exponentially with ``vapour_scale_height`` from the
    station value [ASSUMPTION A-W1.1-3, A-W1.1-4]. Winds constant with height (aloft winds: ERA5 replay)."""
    t_std = layers.node_temperatures()
    j = int(np.clip(np.searchsorted(layers.h_base, h_station, side="right") - 1, 0, layers.lapse.size - 1))
    t_std_station = t_std[j] + layers.lapse[j] * (h_station - layers.h_base[j])
    dt = t_station - t_std_station
    h = layers.h_base
    lne = math.log(e_station) - (h - h_station) / vapour_scale_height
    n = h.size
    return build_profile(
        h,
        t_std + dt,
        c,
        p_anchor=p_station,
        h_anchor=h_station,
        lne_nodes=lne,
        wn_nodes=np.full(n, wind_north),
        we_nodes=np.full(n, wind_east),
    )


def design_day_profile(
    hp_nodes: np.ndarray, t_nodes: np.ndarray, layers: UssaLayers, c: Constants
) -> tuple[np.ndarray, int]:
    """A MIL-HDBK-310-style design atmosphere [TRANSFER: USAF engine spec, JSSG-2007A Fig. 5 note 4].

    The design-day table gives temperature against altitude with "the ambient static pressure variation as
    defined in U.S. Standard Atmosphere for geopotential altitude", i.e. the table altitude is a **pressure
    altitude**: node k has p_k = p_USSA(Hp_k) and T_k = T_table(Hp_k). The true geopotential heights of the
    nodes follow from hydrostatics with T linear in H between nodes (closed form per segment), so the
    profile is physically consistent and reproduces the table exactly at every node (tested)."""
    std, ns = ussa76_profile(layers, c)
    hp = np.asarray(hp_nodes, dtype=float)
    t = np.asarray(t_nodes, dtype=float)
    if hp.size < 2 or hp.size > NMAX or np.any(np.diff(hp) <= 0) or t.shape != hp.shape:
        raise ValueError("design-day table needs 2..NMAX increasing pressure altitudes")
    cv = c.vector()
    p = np.array([profile_tp(std, ns, x, cv)[1] for x in hp])
    k = c.g0 * c.m0 / c.r_star
    h = np.empty_like(hp)
    _, p_sl = profile_tp(std, ns, 0.0, cv)
    # anchor: the first node's geopotential height from the hydrostatic layer between it and sea level at
    # its own temperature (isothermal estimate; exact when the first node is at Hp = 0)
    h[0] = -math.log(p[0] / p_sl) * t[0] / k
    for j in range(hp.size - 1):
        lr = math.log(p[j + 1] / p[j])
        if abs(t[j + 1] - t[j]) < 1e-9:
            h[j + 1] = h[j] - t[j] * lr / k
        else:
            lapse = -k * math.log(t[j + 1] / t[j]) / lr
            h[j + 1] = h[j] + (t[j + 1] - t[j]) / lapse
    prof = empty_profile()
    n = hp.size
    prof[PR_H, :n] = h
    prof[PR_T, :n] = t
    prof[PR_P, :n] = p
    prof[PR_LNE, :n] = -1000.0
    return prof, n


def magnus_vector(a_pa: float, b: float, c_k: float) -> np.ndarray:
    v = np.array([a_pa, b, c_k], dtype=np.float64)
    v.flags.writeable = False
    return v


def specific_humidity(e_pa: float, p_pa: float, c: Constants) -> float:
    """q = eps e / (p - (1 - eps) e), eps = M_water / M0."""
    eps = c.m_water / c.m0
    return eps * e_pa / (p_pa - (1.0 - eps) * e_pa)


__all__ = [
    "CONST_NAMES",
    "NMAX",
    "PR_H",
    "PR_LNE",
    "PR_P",
    "PR_T",
    "PR_WE",
    "PR_WN",
    "Constants",
    "UssaLayers",
    "anchored_offset_profile",
    "build_profile",
    "design_day_profile",
    "geometric_altitude",
    "geopotential_altitude",
    "magnus_vector",
    "moist_state",
    "profile_tp",
    "saturation_vapour_pressure",
    "specific_humidity",
    "ussa76_profile",
]
