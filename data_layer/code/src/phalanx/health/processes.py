"""Degradation process families, one per mechanism (architecture §9.2; report §9; research note
``faults_and_degradation.md`` §5 and §9(c)).

Every function is pure: it takes the current state, the usage increment and the random variates (or a
``numpy.random.Generator`` built from an identity-keyed stream, AD-37) and returns the new state. Nothing here
keeps hidden state or touches a global RNG. A zero rate or a zero usage increment always returns the input
unchanged (acceptance A1 "zero rate gives a flat trend").

Families (function; anchor and tag):

- Recoverable fouling: Wiener with drift ∝ dust index, partial reset by wash (fraction ρ) -
  `wiener_fouling`, `wash`; ≈1 % Γ and η per roughness step [TRANSFER: Kurz & Brun]
- Erosion, clearance, wear: gamma process, commercial rate × fighter severity S - `gamma_increment`;
  ProDiMES HPC η ≈ −5 % at 5,000 flights [TRANSFER]; S [ASSUMPTION]
- Early-life rub-in: step + exponential after each build - `rub_in`; ≈1 % TSFC flight 1, ≈1.5 % by ~200
  flights [TRANSFER: Sallee]
- Abnormal onset: usage energy vs random threshold, then δ = exp(a·t^b) − 1 - `onset_crossed`, `onset_loss`;
  N-CMAPSS form [TRANSFER: Arias Chao 2021]
- Cracks and spalls: Weibull initiation + Paris / exponential growth; debris ∝ growth - `weibull_life`,
  `paris_grow`, `exp_grow`; TM-2011-217117 rates [TRANSFER]
- Shocks (FOD, birds): Poisson with severity - `poisson_count` (used by M11); IAF bird-strike incidents
  [DIRECT → INFERENCE]
- Latent maintenance-induced defects: per-action probability, latency distribution - `latent_draw` (used by
  M11); AIB latencies [DIRECT]; probability [ASSUMPTION]
- Intermittents: two-state Markov, environment-dependent - `markov_two_state` (used by M11); NFF 30–60 %
  [TRANSFER]
- Utility wear curves: incubation then growth - `incubation_growth`; case-drain ΔT flat ≈5 months → limit
  ≈11.5 months [TRANSFER]
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    "exp_grow",
    "gamma_increment",
    "gamma_rate_draw",
    "incubation_growth",
    "latent_draw",
    "markov_two_state",
    "onset_crossed",
    "onset_loss",
    "paris_grow",
    "poisson_count",
    "rub_in",
    "wash",
    "weibull_life",
    "wiener_fouling",
]


# ------------------------------------------------------------------------------------------ fouling
def wiener_fouling(
    x: float, drift_per_unit: float, sigma_per_sqrt_unit: float, du: float, dust: float, z: float
) -> float:
    """Recoverable fouling loss after ``du`` usage units (e.g. engine operating hours).

    X(u + du) = | X(u) + μ·d·du + σ·sqrt(d·du)·z |, with dust index ``d`` scaling the exposure (drift ∝ dust
    index, architecture §9.2). The absolute value is a reflecting boundary at 0: a fouling loss is never a
    gain over the clean blade (a plain Wiener path "can go negative", faults_and_degradation.md §9(c)).
    Mean and variance grow linearly with exposure d·du (property-tested).
    """
    if du < 0 or dust < 0:
        raise ValueError("usage increment and dust index must be >= 0")
    expo = dust * du
    if expo == 0.0:
        return float(x)
    return abs(x + drift_per_unit * expo + sigma_per_sqrt_unit * math.sqrt(expo) * z)


def wash(x: float, rho: float) -> float:
    """Engine wash removes the fraction ``rho`` of recoverable fouling (imperfect maintenance, report §9)."""
    if not 0.0 <= rho <= 1.0:
        raise ValueError("wash recovery fraction must be in [0, 1]")
    return float(x) * (1.0 - rho)


# ------------------------------------------------------------------------------------------ gamma wear
def gamma_increment(
    rng: np.random.Generator, mean_rate: float, cv_ref: float, ref_usage: float, du: float
) -> float:
    """One monotone gamma-process increment over ``du`` usage units.

    Stationary gamma process with mean ``mean_rate`` per unit and coefficient of variation ``cv_ref`` at
    ``ref_usage`` units: shape rate k = 1 / (cv_ref² · ref_usage) per unit, scale θ = mean_rate / k, so the
    increment over du is Gamma(k·du, θ): mean = mean_rate·du, CV(du) = cv_ref·sqrt(ref_usage / du).
    Returns exactly 0.0 when ``mean_rate`` or ``du`` is 0 (no draw is consumed then).
    """
    if mean_rate < 0 or du < 0 or cv_ref <= 0 or ref_usage <= 0:
        raise ValueError("gamma process needs mean_rate >= 0, du >= 0, cv_ref > 0, ref_usage > 0")
    if mean_rate == 0.0 or du == 0.0:
        return 0.0
    k = 1.0 / (cv_ref * cv_ref * ref_usage)
    return float(rng.gamma(k * du, mean_rate / k))


def gamma_rate_draw(rng: np.random.Generator, mean: float, sd: float) -> float:
    """A positive per-unit rate drawn once per serial from a gamma distribution with the fleet ``mean`` and
    standard deviation ``sd`` (shape (mean/sd)², scale sd²/mean): unit-to-unit wear-rate spread such as the
    QFDA filter rates of Bennett et al. 1996 (fleet mean and 2σ, right-skewed: 2σ > mean) [TRANSFER; the gamma
    form is ASSUMPTION A-W2.5-1]. Returns ``mean`` without a draw when ``sd`` is 0, and 0 when ``mean`` is
    0."""
    if mean < 0 or sd < 0:
        raise ValueError("rate mean and sd must be >= 0")
    if mean == 0.0:
        return 0.0
    if sd == 0.0:
        return float(mean)
    shape = (mean / sd) * (mean / sd)
    return float(rng.gamma(shape, mean / shape))


# ------------------------------------------------------------------------------------------ rub-in
def rub_in(n_since_build: int, c0: float, c1: float, tau: float) -> float:
    """Early-life rub-in loss after ``n_since_build`` flights since the last build or overhaul.

    0 before the first flight; c0 + c1·(1 − exp(−n/τ)) afterwards (step on flight 1, then a short exponential;
    Sallee: ≈1 % TSFC on flight 1, ≈1.5 % by ~200 flights [TRANSFER]).
    """
    if n_since_build <= 0:
        return 0.0
    return c0 + c1 * (1.0 - math.exp(-n_since_build / tau))


# ------------------------------------------------------------------------------------------ abnormal onset
def onset_crossed(energy: float, threshold: float) -> bool:
    """N-CMAPSS onset rule: abnormal degradation starts when cumulative usage energy exceeds the unit-specific
    threshold (drawn once per serial from a Gaussian, Arias Chao et al. 2021 [TRANSFER])."""
    return energy >= threshold


def onset_loss(t_since: float, a: float, b: float, tau: float, amplitude: float) -> float:
    """Abnormal-degradation loss ``t_since`` flights after onset: A·(exp(a·(t/τ)^b) − 1).

    N-CMAPSS writes δa = 1 − exp(a·t^b) with a ~ U(0.001, 0.003), b ~ U(1.4, 1.6) per accelerated cycle;
    ``tau`` rescales fighter flights to those cycles and ``amplitude`` maps δ onto a component delta
    [ASSUMPTION, both swept]. Zero at onset, monotone increasing and convex afterwards.
    """
    if t_since <= 0.0:
        return 0.0
    return amplitude * (math.exp(a * (t_since / tau) ** b) - 1.0)


# ------------------------------------------------------------------------------------------ cracks, spalls
def weibull_life(rng: np.random.Generator, shape: float, scale: float) -> float:
    """Initiation life (usage units) ~ Weibull(shape β, scale η), drawn once per serial."""
    if shape <= 0 or scale <= 0:
        raise ValueError("Weibull shape and scale must be > 0")
    return float(scale * rng.weibull(shape))


def exp_grow(length: float, rate: float, du: float) -> float:
    """Exponential growth L(u + du) = L·exp(r·du) (spall past initiation, report §9: growth 0.08–0.34 mm/h
    over the linear-to-knee range is matched by the rate r at the reference size)."""
    if length <= 0.0 or du == 0.0:
        return float(length)
    return float(length * math.exp(rate * du))


def paris_grow(a: float, dn: float, c: float, m: float, dsigma: float, y: float = 1.0) -> float:
    """Paris-law crack growth over ``dn`` cycles: da/dN = C·(Y·Δσ·sqrt(π·a))^m (closed form, m ≠ 2).

    Units: a in m, Δσ in Pa, C in m/cycle/(Pa·sqrt(m))^m. Returns ``a`` unchanged when a or dn is 0.
    """
    if a <= 0.0 or dn == 0.0:
        return float(a)
    if abs(m - 2.0) < 1e-12:
        k = c * (y * dsigma) ** 2 * math.pi
        return float(a * math.exp(k * dn))
    beta = c * (y * dsigma * math.sqrt(math.pi)) ** m
    p = 1.0 - m / 2.0
    base = a**p + p * beta * dn
    if base <= 0.0:  # unstable growth: the crack runs away within dn cycles
        return math.inf
    return float(base ** (1.0 / p))


# ------------------------------------------------------------------------------------------ discrete
# processes
def poisson_count(rng: np.random.Generator, rate: float, exposure: float) -> int:
    """Number of shocks in ``exposure`` units at ``rate`` per unit (0 without a draw if rate·exposure = 0)."""
    lam = rate * exposure
    if lam < 0:
        raise ValueError("Poisson mean must be >= 0")
    if lam == 0.0:
        return 0
    return int(rng.poisson(lam))


def latent_draw(
    rng: np.random.Generator, p_inject: float, latency_median: float, latency_sigma: float
) -> float | None:
    """Maintenance-induced latent defect for one maintenance action.

    With probability ``p_inject`` returns a latency (usage units) ~ LogNormal(ln median, σ); else None. Both
    uniforms/normals are drawn every call so the draw count never depends on the outcome (CRN-stable).
    """
    u = float(rng.random())
    z = float(rng.standard_normal())
    if u >= p_inject:
        return None
    return float(latency_median * math.exp(latency_sigma * z))


def markov_two_state(state: int, p_on: float, p_off: float, u: float) -> int:
    """Two-state (off=0 / on=1) Markov transition with a supplied uniform ``u`` (intermittents, §9.2)."""
    if state:
        return 0 if u < p_off else 1
    return 1 if u < p_on else 0


# ------------------------------------------------------------------------------------------ utility wear
# curve
def incubation_growth(x: float, age: float, du: float, onset: float, growth_to_limit: float) -> float:
    """Monitoring-curve wear: flat until ``onset`` usage, then linear growth reaching 1.0 (the limit) after
    ``growth_to_limit`` further units (pump case-drain ΔT: flat ≈5 months, limit at ≈11.5 months [TRANSFER]).

    ``age`` is the usage at the start of the increment; the result is capped at 1.0 (at the limit the part is
    removed; the cap is the limit, not a clip of a physical quantity).
    """
    if du <= 0.0:
        return float(x)
    a1 = age + du
    if a1 <= onset:
        return float(x)
    active = a1 - max(age, onset)
    return float(min(1.0, x + active / growth_to_limit))
