"""Fleet usage statistics and the R§4 usage gates (AD-28: "accept a configuration only if fleet statistics
fall inside the gates").

Gate targets [TRANSFER: JSSG-2007A, MIL-HDBK-1783B (USAF fighter design usage); ICAF Finland 2017 (FINAF
F404-402 EOT/EFH 1.56); RTO-TR-028 (per-flight usage CV ~0.5, dispersion ~1.3); AGARD R-815 (F-16
operational Nz exceedances, graph-read +/- 30 %)]; tolerances where the report gives "~" are [ASSUMPTION
A-W1.1-30]. Statistics are computed from :class:`~.plan.SortieSummary` records (plan level) or from realised
counts in the same form (telemetry level, W2.1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .plan import SortiePlan

# F-16 operational Nz exceedances per 1,000 h (AGARD R-815 via report §4): 5 g ~7,000; 7 g ~1,300; 9 g ~10
F16_NZ_PER_1000H = {5.0: 7000.0, 7.0: 1300.0, 9.0: 10.0}


@dataclass(frozen=True)
class FleetStats:
    n_sorties: int
    n_ground_runs: int
    flight_h: float
    type3_per_fh: float
    ab_lights_per_fh: float
    irp_frac: float
    ab_frac: float
    tac_per_fh: float
    eot_per_efh: float
    usage_cv: float  # CV of TAC per flight (sorties)
    engine_dispersion: float  # P95 / mean of per-engine TAC per FH
    nz5_per_1000h: float
    nz7_per_1000h: float
    night_frac: float
    duration_median_min: float
    duration_p05_min: float
    duration_p95_min: float


def fleet_stats(plans: Sequence[SortiePlan], *, min_engine_fh: float = 10.0) -> FleetStats:
    sorties = [p for p in plans if p.summary is not None and p.summary.flight_s > 0]
    runs = [p for p in plans if p.summary is not None and p.summary.flight_s == 0]
    s = [p.summary for p in sorties]
    r = [p.summary for p in runs]
    fh = sum(x.flight_s for x in s) / 3600.0
    if fh <= 0:
        raise ValueError("no flight time in the sample")
    every = s + r

    def tot(name):
        return float(sum(getattr(x, name) for x in every))

    tac_flight = np.array([x.tac for x in s])
    per_engine: dict[str, list[float]] = {}
    for p in sorties + runs:
        acc = per_engine.setdefault(p.engine_serials[0], [0.0, 0.0])
        acc[0] += p.summary.tac  # type: ignore[union-attr]
        acc[1] += p.summary.flight_s / 3600.0  # type: ignore[union-attr]
    rates = np.array([a / b for a, b in per_engine.values() if b >= min_engine_fh])
    disp = float(np.percentile(rates, 95) / rates.mean()) if rates.size >= 2 else float("nan")
    dur = np.array([x.flight_s for x in s]) / 60.0
    return FleetStats(
        n_sorties=len(s),
        n_ground_runs=len(r),
        flight_h=fh,
        type3_per_fh=tot("type3") / fh,
        ab_lights_per_fh=tot("ab_lights") / fh,
        irp_frac=tot("irp_s") / 3600.0 / fh,
        ab_frac=tot("ab_s") / 3600.0 / fh,
        tac_per_fh=tot("tac") / fh,
        eot_per_efh=tot("eot_s") / 3600.0 / fh,
        usage_cv=float(tac_flight.std(ddof=1) / tac_flight.mean()),
        engine_dispersion=disp,
        nz5_per_1000h=float(sum(x.nz_exceed[2] for x in s)) / fh * 1000.0,
        nz7_per_1000h=float(sum(x.nz_exceed[4] for x in s)) / fh * 1000.0,
        night_frac=float(np.mean([x.night for x in s])),
        duration_median_min=float(np.median(dur)),
        duration_p05_min=float(np.percentile(dur, 5)),
        duration_p95_min=float(np.percentile(dur, 95)),
    )


#: plan-level gates: name -> (lo, hi) [ASSUMPTION A-W1.1-30 for the bands]
PLAN_GATES: dict[str, tuple[float, float]] = {
    "type3_per_fh": (3.0, 7.0),
    "ab_lights_per_fh": (3.5, 5.5),
    "irp_frac": (0.15, 0.22),
    "ab_frac": (0.03, 0.07),
    "tac_per_fh": (2.2, 3.3),
    "eot_per_efh": (1.41, 1.71),
    "usage_cv": (0.35, 0.65),
    "nz5_per_1000h": (0.7 * F16_NZ_PER_1000H[5.0], 1.3 * F16_NZ_PER_1000H[5.0]),
    "nz7_per_1000h": (0.7 * F16_NZ_PER_1000H[7.0], 1.3 * F16_NZ_PER_1000H[7.0]),
    "night_frac": (0.10, 0.20),
    "duration_median_min": (45.0, 55.0),
}
DISPERSION_GATE = (1.15, 1.5)


def gate_failures(st: FleetStats, gates: dict[str, tuple[float, float]] = PLAN_GATES) -> dict[str, float]:
    return {k: getattr(st, k) for k, (lo, hi) in gates.items() if not lo <= getattr(st, k) <= hi}


__all__ = ["DISPERSION_GATE", "F16_NZ_PER_1000H", "PLAN_GATES", "FleetStats", "fleet_stats", "gate_failures"]
