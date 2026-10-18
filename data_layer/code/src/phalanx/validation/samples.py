"""Deterministic flight-sample selection with recorded n and justification (RULES.md rule 1).

Every validation check uses the smallest sample that answers its question. A `FlightSample` records the
selected flights together with n, the justification, the population it was drawn from (size and SHA-256 of
the sorted list) and the exact random source, and it is saved before any analysis reads the flights.

Random source (never the global RNG, never seed arithmetic):
- **build (default):** `phalanx.core.rng` (AD-15, AD-37 mapping v1). The declared GENERATOR stream
  `validation.flight_sample`, keyed by `scenario` (the validation campaign, e.g. ``proxy_gate.s20``);
  the generator index distinguishes selections within a campaign. Requires an `RngService` whose registry
  declares `SAMPLE_STREAM`.
- **round-2 compatibility:** `Generator(PCG64(SeedSequence(entropy, spawn_key)))`, the rule of the
  pre-registered round-2 runner. Use it only to reproduce or extend round-2 lists (e.g. entropy
  ``[20261015, 99]`` on the 110-flight 652 holdout list returns `holdout_652_s20` exactly).

Selection rule in both modes: ``sorted(gen.choice(sorted(population), n, replace=False))``.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

import numpy as np

from phalanx.core.rng import KeyPath, RngService, StreamDecl, Variate

__all__ = [
    "SAMPLE_STREAM",
    "FlightSample",
    "load_sample",
    "population_sha256",
    "save_sample",
    "select_flights",
    "temporal_halves",
]

#: Declared stream of the sample selector (add it to the run's StreamRegistry).
SAMPLE_STREAM = StreamDecl(
    subsystem="validation",
    component="flight_sample",
    identity=("scenario",),
    variate=Variate.GENERATOR,
    block_size=1,
    owner="M20 validation harness (W0.5)",
    description="deterministic flight-sample selection; one generator per selection index within a campaign",
)
RULE = "sorted(gen.choice(sorted(population), n, replace=False))"


def population_sha256(population: Sequence[str]) -> str:
    """SHA-256 of the sorted population, one id per line."""
    return hashlib.sha256("\n".join(sorted(population)).encode()).hexdigest()


@dataclass(frozen=True)
class FlightSample:
    """A saved, reproducible flight list with its size, the reason for that size and its random source."""

    purpose: str
    flights: tuple[str, ...]
    n: int
    justification: str
    population_size: int
    population_sha256: str
    source: Mapping[str, object] = field(default_factory=dict)
    rule: str = RULE

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["flights"] = list(self.flights)
        d["source"] = dict(self.source)
        return d


def _round2_generator(
    entropy: int | Sequence[int], spawn_key: Sequence[int]
) -> tuple[np.random.Generator, dict[str, object]]:
    ent = int(entropy) if isinstance(entropy, (int, np.integer)) else [int(e) for e in entropy]
    sk = [int(k) for k in spawn_key]
    gen = np.random.Generator(np.random.PCG64(np.random.SeedSequence(ent, spawn_key=tuple(sk))))
    return gen, {"mode": "round2_compat", "bit_generator": "PCG64", "entropy": ent, "spawn_key": sk}


def select_flights(
    population: Sequence[str],
    n: int,
    *,
    purpose: str,
    justification: str,
    rng: RngService | None = None,
    scenario: str | None = None,
    index: int = 0,
    entropy: int | Sequence[int] | None = None,
    spawn_key: Sequence[int] = (),
) -> FlightSample:
    """Draw n distinct flights from a population, deterministically, recording n and the justification.

    Build mode: pass `rng` (an `RngService` whose registry declares `SAMPLE_STREAM`), `scenario` (the
    campaign key) and optionally `index`. Round-2 compatibility mode: pass `entropy` (and `spawn_key`).

    Args:
        population: candidate flight ids (order irrelevant; duplicates rejected).
        n: sample size; must not exceed the population.
        purpose: what the sample is for (e.g. "B1-B6 golden reproduction, smoke").
        justification: why n is sufficient (RULES.md rule 1); required.
    """
    if not justification.strip():
        raise ValueError("a sample needs a written justification of its size (RULES.md rule 1)")
    pop = sorted(population)
    if len(set(pop)) != len(pop):
        raise ValueError("population contains duplicate flight ids")
    if not 0 < n <= len(pop):
        raise ValueError(f"n = {n} must be in 1..{len(pop)}")
    if (rng is None) == (entropy is None):
        raise ValueError(
            "pass either rng (+ scenario) for build selections or entropy for round-2 compatibility"
        )
    if rng is not None:
        if not scenario:
            raise ValueError("build selections need a scenario key (the validation campaign)")
        path = KeyPath.of(
            scenario=scenario, subsystem=SAMPLE_STREAM.subsystem, component=SAMPLE_STREAM.component
        )
        gen = rng.generator(path, index)
        source: dict[str, object] = {
            "mode": "phalanx.core.rng",
            **rng.describe(),
            "path": path.canonical(),
            "index": int(index),
        }
    else:
        assert entropy is not None
        gen, source = _round2_generator(entropy, spawn_key)
    pick = sorted(gen.choice(np.asarray(pop), n, replace=False).tolist())
    return FlightSample(
        purpose=purpose,
        flights=tuple(pick),
        n=n,
        justification=justification,
        population_size=len(pop),
        population_sha256=population_sha256(pop),
        source=source,
    )


def save_sample(sample: FlightSample, path: str | os.PathLike[str]) -> None:
    """Write the sample as JSON (flights, n, justification, population hash, random source)."""
    with open(path, "w") as fh:
        json.dump(sample.to_dict(), fh, indent=1, sort_keys=True)
        fh.write("\n")


def load_sample(path: str | os.PathLike[str]) -> FlightSample:
    with open(path) as fh:
        d = json.load(fh)
    return FlightSample(
        purpose=d["purpose"],
        flights=tuple(d["flights"]),
        n=int(d["n"]),
        justification=d["justification"],
        population_size=int(d["population_size"]),
        population_sha256=d["population_sha256"],
        source=d["source"],
        rule=d.get("rule", RULE),
    )


def temporal_halves(flights: Sequence[str], dates: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """Early and late halves at the median flight date, equal counts (round-2 D_temp groups).

    Flights are ordered by date (stable for ties); early = first floor(n/2), late = last floor(n/2); each
    half is returned sorted by id. With an odd n the median flight is in neither half.
    """
    order = sorted(flights, key=lambda f: dates[f])
    h = len(order) // 2
    return sorted(order[:h]), sorted(order[len(order) - h :])
