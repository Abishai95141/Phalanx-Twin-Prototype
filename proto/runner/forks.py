"""CRN-paired what-if forks for candidate orders, from the live session (DEVELOPMENT.md §4 Phase 2).

For each member m, the status quo (station routine only) and the treatment (routine + the candidate orders,
submitted at their 08:00 epoch) run from the same snapshot with the same exogenous future, and the data layer's
``ForkService.compare(paired=True)`` gives the treatment − status-quo differences with 95 % intervals.

Mode is ``belief`` (the in-loop what-if the product may show). In preview v0.9 the belief posterior only
conditions one failure mode (M10 bearing spall), so results equal ensemble mode — the screens say "simulated".
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from datalayer import DAY, BranchSpec, Order, ScheduledPolicy, SurvivalPosterior

KPIS = ("mc", "fmc", "nmcs", "nmcm", "aog_days", "man_hours", "cost", "flown_fh", "sorties", "in_flight_failures")


def run_pairs(tr, snap, orders: Sequence[Order], *, n: int = 10, horizon_days: int = 30) -> dict[str, Any]:
    """``tr``: the tail's TailRunner (for its fork service); ``snap``: a snapshot of its live session."""
    fs = tr.fork_service()
    horizon = horizon_days * DAY
    w0 = time.perf_counter()
    sq_runs, tr_runs, walls = [], [], []
    for m in range(n):
        w = time.perf_counter()
        belief = SurvivalPosterior("m10", m18_id="m18")
        sq = fs.run(snap, BranchSpec("sq", policy=ScheduledPolicy(), mode="belief", member=m, belief=belief), horizon)
        belief = SurvivalPosterior("m10", m18_id="m18")
        tx = fs.run(snap, BranchSpec("tr", orders=tuple(orders), policy=ScheduledPolicy(), mode="belief", member=m,
                                     belief=belief), horizon)
        sq_runs.append(sq)
        tr_runs.append(tx)
        walls.append(round(time.perf_counter() - w, 2))
    diffs = {d.kpi: {"mean": d.mean, "ci_low": d.ci_low, "ci_high": d.ci_high, "n": d.n}
             for d in fs.compare(tr_runs, sq_runs, paired=True)}
    oids = {o.order_id for o in orders}
    verdicts = {x.order_id: x.verdict for r in tr_runs for x in r.submissions if x.order_id in oids}
    no_change = all(abs(v["mean"]) < 1e-12 and abs(v["ci_low"]) < 1e-12 and abs(v["ci_high"]) < 1e-12 for v in diffs.values())
    return {
        "pairs": n, "horizon_days": horizon_days, "mode": "belief", "diffs": diffs,
        "status_quo_mean": {k: sum(getattr(r.kpis, k) for r in sq_runs) / n for k in KPIS if hasattr(sq_runs[0].kpis, k)},
        "verdicts": verdicts, "no_change": no_change, "wall_s": round(time.perf_counter() - w0, 1), "pair_wall_s": walls,
    }
