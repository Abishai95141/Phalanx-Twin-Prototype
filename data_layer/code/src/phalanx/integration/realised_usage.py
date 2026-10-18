"""Realised usage of an M02 fleet plan flown in telemetry mode (W2.1 brief "Realised usage gates"; E1-MF
MF4d).

``realised_fleet_stats(fleet, start, days, *, scenario, root, max_sorties)`` plans the fleet with M02 (usage
mode, keyed: a pure function of its arguments), flies the first ``max_sorties`` flying sorties in plan order
through the W2.1 truth loop (:class:`~.sortie.SortieRunner`, post-start idle to engine cut-off) and returns
the fleet statistics computed from the **realised** counts, in the plan-level
:class:`phalanx.scenario.gates.FleetStats`
form so the same gates apply:

- Type III cycles and TAC from **M14's ``usage.counters``** (the ECMS LUI counters on recorded CIR);
- Nz exceedances from the level-crossing counters on the realised ``af.nz`` (M10's counter kernel with M14's
  levels; levels 5 g and 7 g);
- flight time from main-gear weight-on-wheels, AB lights from ``eng.ab_state``, time at or above IRP from the
  LUI ``tamp_s`` on truth (same gates as M14), AB time from ``eng.ab_state``; night from the plan.

The harness never substitutes plan values for realised ones. When a sortie cannot be flown it raises
:class:`~.sortie.SortieAborted` (physical-invariant failure: ground impact, loss of control); when M14's
counters are void because their recorded inputs have no producer it raises :class:`ObservedUsageUnavailable`.
Both are the specific exceptions the realised-gate tests expect while those gaps are open.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .sortie import SortieRunner


class ObservedUsageUnavailable(RuntimeError):
    """M14's LUI counters are void for a sortie: an input channel of the counters has no producer (the
    exception names them) or the counter saw a data gap."""


@dataclass(frozen=True)
class RealisedSortie:
    sortie_id: str
    tail: str
    engine_serial: str
    night: bool
    flight_s: float
    type3: float  # M14 LUI.TYPE3 (engine 0)
    tac: float  # M14 USAGE.TAC (engine 0)
    eot_s: float  # truth LUI EOT
    tamp_s: float  # truth LUI time at/above IRP
    ab_s: float
    ab_lights: float
    nz5: float
    nz7: float
    truth_type3: float
    truth_tac: float


def _fly(plan, *, scenario: str, root: int, platform: str) -> RealisedSortie:
    from .system import SortieSpec, build_sortie_system

    ss = build_sortie_system(SortieSpec(plan=plan, scenario=scenario, root=root, platform=platform))
    r = SortieRunner(ss)
    res = r.run_to_end(r.begin())
    st = res.state
    lui_in = set(ss.modules["monitor"].config.lui_channels[0])
    missing = sorted(lui_in & set(r.m14_missing))
    ms = st.world.states["monitor"]
    from phalanx.health.usage import LUI_INTS

    gap = bool(np.asarray(ms["lui_i"])[0][LUI_INTS.index("gap")])
    if missing or gap:
        raise ObservedUsageUnavailable(
            f"{plan.sortie_id}: M14 LUI counters void (inputs without a producer: {missing}; data gap: {gap})"
        )
    obs = r.observed_counters(st)
    u = r.realised_usage(st)
    levels = np.asarray(r._nz_levels, dtype=np.float64)
    i5, i7 = int(np.flatnonzero(levels == 5.0)[0]), int(np.flatnonzero(levels == 7.0)[0])
    return RealisedSortie(
        sortie_id=plan.sortie_id,
        tail=plan.tail,
        engine_serial=plan.engine_serials[0],
        night=bool(plan.night),
        flight_s=float(u.flight_time_s),
        type3=float(obs["LUI.TYPE3[0]"]),
        tac=float(obs["USAGE.TAC[0]"]),
        eot_s=float(u.eot_s[0]),
        tamp_s=float(u.tamp_s[0]),
        ab_s=float(st.usage["ab_s"][0]),
        ab_lights=float(u.ab_lights[0]),
        nz5=float(u.nz_counts[i5]),
        nz7=float(u.nz_counts[i7]),
        truth_type3=float(u.type3[0]),
        truth_tac=float(u.tac()[0]),
    )


def fleet_stats_from_realised(rs: Sequence[RealisedSortie], *, min_engine_fh: float = 10.0):
    """``FleetStats`` from realised sorties (the plan-level formulas of ``scenario.gates.fleet_stats``)."""
    from phalanx.scenario.gates import FleetStats

    fh = sum(r.flight_s for r in rs) / 3600.0
    if fh <= 0:
        raise ValueError("no realised flight time in the sample")
    tac = np.array([r.tac for r in rs])
    per: dict[str, list[float]] = {}
    for r in rs:
        acc = per.setdefault(r.engine_serial, [0.0, 0.0])
        acc[0] += r.tac
        acc[1] += r.flight_s / 3600.0
    rates = np.array([a / b for a, b in per.values() if b >= min_engine_fh])
    disp = float(np.percentile(rates, 95) / rates.mean()) if rates.size >= 2 else float("nan")
    dur = np.array([r.flight_s for r in rs]) / 60.0
    return FleetStats(
        n_sorties=len(rs),
        n_ground_runs=0,
        flight_h=fh,
        type3_per_fh=sum(r.type3 for r in rs) / fh,
        ab_lights_per_fh=sum(r.ab_lights for r in rs) / fh,
        irp_frac=sum(r.tamp_s for r in rs) / 3600.0 / fh,
        ab_frac=sum(r.ab_s for r in rs) / 3600.0 / fh,
        tac_per_fh=float(tac.sum()) / fh,
        eot_per_efh=sum(r.eot_s for r in rs) / 3600.0 / fh,
        usage_cv=float(tac.std(ddof=1) / tac.mean()) if tac.size > 1 and tac.mean() > 0 else float("nan"),
        engine_dispersion=disp,
        nz5_per_1000h=sum(r.nz5 for r in rs) / fh * 1000.0,
        nz7_per_1000h=sum(r.nz7 for r in rs) / fh * 1000.0,
        night_frac=float(np.mean([r.night for r in rs])),
        duration_median_min=float(np.median(dur)),
        duration_p05_min=float(np.percentile(dur, 5)),
        duration_p95_min=float(np.percentile(dur, 95)),
    )


def realised_sorties(
    fleet,
    start: dt.date,
    days: int,
    *,
    scenario: str,
    root: int,
    max_sorties: int | None = None,
    platform: str = "tejas",
) -> list[RealisedSortie]:
    """Fly the first ``max_sorties`` flying sorties of the plan (plan order) and return their realised
    usage."""
    from .plans import flying_sorties

    plans = flying_sorties(fleet, start, days, scenario=scenario, root=root, platform=platform)
    if max_sorties is not None:
        if len(plans) < max_sorties:
            raise ValueError(f"the plan has {len(plans)} flying sorties, fewer than {max_sorties}")
        plans = plans[:max_sorties]
    return [_fly(p, scenario=scenario, root=root, platform=platform) for p in plans]


def realised_fleet_stats(
    fleet,
    start: dt.date,
    days: int,
    *,
    scenario: str,
    root: int,
    max_sorties: int | None = None,
    platform: str = "tejas",
):
    """The realised-usage ``FleetStats`` of the plan (module docstring)."""
    return fleet_stats_from_realised(
        realised_sorties(
            fleet, start, days, scenario=scenario, root=root, max_sorties=max_sorties, platform=platform
        )
    )


__all__ = [
    "ObservedUsageUnavailable",
    "RealisedSortie",
    "fleet_stats_from_realised",
    "realised_fleet_stats",
    "realised_sorties",
]
