"""M22 World snapshot and fork service (architecture §6 M22, §11.2).

What-if API (see README.md)::

    session = OpsSession(builder, root)       # a live closed-loop usage-mode session
    session.run_until(t)                      # to a decision epoch
    snap = ForkService.snapshot(session)      # content-hashed snapshot(t)
    fs = ForkService(builder, m18_cfg)
    res = fs.run(snap, BranchSpec("b1", orders=[...]), horizon_ns)    # fork -> run(horizon); or policy=...
    res.kpis                                  # MC/FMC, flying task, AOG days, CANN, man-hours, cost, IFF
    ra, rb, diffs = fs.what_if(snap, a, b, horizon_ns, replicates=n)  # CRN-paired differences + CIs
"""

from .belief import BeliefPosterior, BeliefTarget, SurvivalPosterior, observed_item_hours
from .builder import OpsIds, OpsOnlyBuilder, WorldBuilder
from .kpi import Kpis, compute_kpis
from .service import BranchResult, BranchSpec, ForkService, KpiDifference, member_root, paired_difference
from .session import OpsSession, RecordLog, SessionSnapshot

__all__ = [
    "BeliefPosterior",
    "BeliefTarget",
    "BranchResult",
    "BranchSpec",
    "ForkService",
    "KpiDifference",
    "Kpis",
    "OpsIds",
    "OpsOnlyBuilder",
    "OpsSession",
    "RecordLog",
    "SessionSnapshot",
    "SurvivalPosterior",
    "WorldBuilder",
    "compute_kpis",
    "member_root",
    "observed_item_hours",
    "paired_difference",
]
