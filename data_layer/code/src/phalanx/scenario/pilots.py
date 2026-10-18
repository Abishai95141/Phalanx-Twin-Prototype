"""AD-28 layer 5: latent per-pilot traits and per-tail affinity (report §4 "Pilot layer").

Traits (vector order ``TRAIT_NAMES``), drawn once per pilot identity from that pilot's stream (so the same
pilot behaves the same in every sortie and every fork):
- ``throttle``: multiplier on the weight of power-active primitives (more throttle excursions; RTO-TR-028:
  "one used the throttle to climb ... the other used the elevators");
- ``g``: multiplier on (Nz target - 1) (g-onset aggressiveness);
- ``ab``: multiplier on the AB-use probability (AB propensity);
- ``cooldown``: multiplier on the idle time before shutdown (cooldown discipline);
- ``aar_mean_mps``, ``aar_sd_mps``: AAR closure-speed distribution in m/s (NFTC/ADA: 1.71-4.3 kt,
  pilot effect);
- ``tau_s``: pilot effective delay (crossover model, 0.1-0.2 s); ``gain``: guidance-gain multiplier
  (crossover frequency); ``remnant``: remnant SD (normalised inceptor units).
All multipliers are lognormal with median 1 [ASSUMPTION A-W1.1-26].
"""

from __future__ import annotations

import math

import numpy as np

from .config import ScenarioParams

TRAIT_NAMES = ("throttle", "g", "ab", "cooldown", "aar_mean_mps", "aar_sd_mps", "tau_s", "gain", "remnant")
T_THROTTLE, T_G, T_AB, T_COOLDOWN, T_AAR_MEAN, T_AAR_SD, T_TAU, T_GAIN, T_REMNANT = range(len(TRAIT_NAMES))
KT = 1852.0 / 3600.0


def draw_traits(gen: np.random.Generator, p: ScenarioParams) -> np.ndarray:
    """Traits from a pilot's own generator (fixed draw order). SI units (AAR closure in m/s)."""
    z = gen.standard_normal(6)
    u = gen.random(2)
    sd = p.trait_sd
    lo, hi = p.aar_mean_range
    tlo, thi = p.tau_range
    v = np.empty(len(TRAIT_NAMES))
    v[T_THROTTLE] = math.exp(sd["throttle"] * z[0])
    v[T_G] = math.exp(sd["g"] * z[1])
    v[T_AB] = math.exp(sd["ab"] * z[2])
    v[T_COOLDOWN] = math.exp(sd["cooldown"] * z[3])
    v[T_AAR_MEAN] = lo + (hi - lo) * u[0]
    v[T_AAR_SD] = p.aar_sd
    v[T_TAU] = tlo + (thi - tlo) * u[1]
    v[T_GAIN] = math.exp(sd["gain"] * z[4])
    v[T_REMNANT] = p.remnant_med * math.exp(sd["remnant"] * z[5])
    return v


def draw_tail_affinity(gen: np.random.Generator, p: ScenarioParams) -> float:
    """Per-tail multiplier on high-activity mission weights [ASSUMPTION A-W1.1-31]."""
    return float(math.exp(p.tail_affinity_sd * gen.standard_normal()))


def pilot_ids(squadron: str, n_tails: int, p: ScenarioParams) -> tuple[str, ...]:
    """Pilot identities of a squadron: ceil(pilots_per_aircraft x aircraft) [DIRECT: 1:1.25]."""
    n = math.ceil(p.pilots_per_aircraft * n_tails - 1e-9)
    return tuple(f"PLT-{squadron}-{k:02d}" for k in range(1, n + 1))


__all__ = ["KT", "TRAIT_NAMES", "draw_tail_affinity", "draw_traits", "pilot_ids"]
