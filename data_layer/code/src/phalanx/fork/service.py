"""M22 snapshot and fork service and the what-if API (architecture §11.2, AD-17).

``snapshot(t)`` -> ``fork(snapshot, branch_id, order_suffix | policy)`` -> ``run(horizon)`` -> KPIs, compared
by CRN-paired differences with confidence intervals.

Fork modes:

- **oracle**: the true state (strict restore, same root): one exact future; privileged, for scoring advice;
- **ensemble**: the true state with a different exogenous future: the root is derived from (root, scenario,
  member) by a SeedSequence spawn key (never seed arithmetic); member ``m`` of every branch shares the same
  root, so branch differences inside a member are CRN-paired;
- **belief**: hidden states resampled consistent with the observations at t through a pluggable posterior
  (:mod:`.belief`), then run like an ensemble member.

A branch is the parent snapshot plus its own order suffix (copy-on-write: the parent's record and observation
prefixes and its state arrays are shared, never copied or mutated).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.stats import t as student_t

from phalanx.core.rng import DrawLedger, KeyPath
from phalanx.maintenance.config import M18Config
from phalanx.orders.gateway import SubmitResult
from phalanx.orders.model import Order
from phalanx.orders.params import M22Config, load_m22_config
from phalanx.orders.policies import Policy, PolicyContext
from phalanx.orders.replay import order_log_hash

from .builder import WorldBuilder
from .kpi import Kpis, compute_kpis
from .session import OpsSession, SessionSnapshot

MODES = ("oracle", "ensemble", "belief")


def member_root(root: int, scenario: str, member: int) -> int:
    """128-bit root of ensemble member ``member``: a SeedSequence spawn-key child of the parent root
    (AD-37)."""
    path = KeyPath.of(scenario=scenario, event=f"ensemble.{int(member)}")
    words = np.random.SeedSequence(entropy=int(root), spawn_key=path.words()).generate_state(4, np.uint32)
    out = 0
    for i, w in enumerate(words.tolist()):
        out |= int(w) << (32 * i)
    return out


@dataclass(frozen=True)
class BranchSpec:
    branch_id: str
    orders: Sequence[Order] = ()
    policy: Policy | None = None
    mode: str = "oracle"
    member: int = 0
    belief: Any | None = None  # a BeliefPosterior (belief mode)

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if self.mode == "belief" and self.belief is None:
            raise ValueError("belief mode needs a posterior")


@dataclass
class BranchResult:
    branch_id: str
    mode: str
    member: int
    root: int
    kpis: Kpis
    order_log_hash: str
    record_digest: str
    submissions: list[SubmitResult] = field(default_factory=list)
    session: OpsSession | None = field(default=None, repr=False)


@dataclass(frozen=True)
class KpiDifference:
    kpi: str
    n: int
    mean: float
    sd: float
    ci_low: float
    ci_high: float


class ForkService:
    def __init__(
        self,
        builder: WorldBuilder,
        m18_cfg: M18Config,
        *,
        defects_factory: Any | None = None,
        m22: M22Config | None = None,
    ) -> None:
        self.builder = builder
        self.m18_cfg = m18_cfg
        self.defects_factory = defects_factory  # root -> DefectInjector | None
        self.m22 = m22 or load_m22_config()

    # ---- snapshot / fork ----------------------------------------------------------------------------------
    @staticmethod
    def snapshot(session: OpsSession) -> SessionSnapshot:
        return session.snapshot()

    def root_for(self, snap: SessionSnapshot, spec: BranchSpec) -> int:
        if spec.mode == "oracle":
            return snap.root
        return member_root(snap.root, self.builder.scenario, spec.member)

    def fork(
        self, snap: SessionSnapshot, spec: BranchSpec, *, ledger: DrawLedger | None = None
    ) -> OpsSession:
        root = self.root_for(snap, spec)
        defects = self.defects_factory(snap.root) if self.defects_factory else None
        s = OpsSession.restore(self.builder, snap, root=root, defects=defects, ledger=ledger)
        if spec.mode == "belief":
            spec.belief.apply(s, particle=spec.member)
        return s

    def run(
        self,
        snap: SessionSnapshot,
        spec: BranchSpec,
        horizon_ns: int,
        *,
        ledger: DrawLedger | None = None,
        keep_session: bool = False,
    ) -> BranchResult:
        """Run a branch from ``snap`` for ``horizon_ns`` (kernel ns) and return its KPIs over that window."""
        s = self.fork(snap, spec, ledger=ledger)
        t0, t1 = snap.t, snap.t + int(horizon_ns)
        epoch = self.builder.epoch_utc_ns
        suffix: dict[int, list[Order]] = {}
        for o in spec.orders:
            ti = o.t_issued - epoch
            if not t0 <= ti < t1:
                raise ValueError(f"order {o.order_id} issued outside the branch window")
            suffix.setdefault(ti, []).append(o)
        times = set(suffix)
        if spec.policy is not None:
            times |= set(self.builder.calendar.epochs(t0, t1))
        for t in sorted(times):
            s.run_until(t)
            batch = list(suffix.get(t, []))
            if spec.policy is not None and s.obs is not None:
                ctx = PolicyContext(
                    t_utc=s.t_utc,
                    catalogue=self.m18_cfg.catalogue,
                    cann_min_awp_s=self.m18_cfg.cann_min_awp_s,
                    tz_offset_s=self.m18_cfg.tz_offset_s,
                )
                batch += spec.policy.decide(s.obs, ctx)
            if batch:
                s.submit(batch)
        s.run_until(t1)
        k = compute_kpis(s.log, self.m18_cfg, t0_utc=epoch + t0, t1_utc=epoch + t1, tails=self.tails())
        return BranchResult(
            spec.branch_id,
            spec.mode,
            spec.member,
            s.root,
            k,
            order_log_hash(s.world.order_log),
            s.log.digest,
            list(s.submissions),
            s if keep_session else None,
        )

    def tails(self) -> tuple[str, ...]:
        fleet = getattr(self.builder, "fleet", None)
        if fleet is None:
            raise AttributeError("the builder must expose its FleetSpec as .fleet")
        return tuple(fleet.tails)

    # ---- what-if -------------------------------------------------------------------------------------------
    def what_if(
        self, snap: SessionSnapshot, a: BranchSpec, b: BranchSpec, horizon_ns: int, *, replicates: int
    ) -> tuple[list[BranchResult], list[BranchResult], list[KpiDifference]]:
        """Run ``a`` and ``b`` as ensemble members 0..replicates-1 (member m of both shares one exogenous
        future) and return the CRN-paired KPI differences (a - b) with confidence intervals."""
        ra, rb = [], []
        for m in range(replicates):
            ra.append(self.run(snap, _as_member(a, m), horizon_ns))
            rb.append(self.run(snap, _as_member(b, m), horizon_ns))
        return ra, rb, self.compare(ra, rb)

    def compare(
        self, a: Sequence[BranchResult], b: Sequence[BranchResult], *, paired: bool = True
    ) -> list[KpiDifference]:
        if paired:
            if [x.member for x in a] != [x.member for x in b]:
                raise ValueError("paired comparison needs the same members in both branches")
        out = []
        level = self.m22.ci_level
        for kpi in Kpis.__dataclass_fields__:
            xa = np.array([getattr(r.kpis, kpi) for r in a], dtype=np.float64)
            xb = np.array([getattr(r.kpis, kpi) for r in b], dtype=np.float64)
            out.append(
                paired_difference(kpi, xa, xb, level=level, paired=paired, min_pairs=self.m22.min_pairs)
            )
        return out


def _as_member(spec: BranchSpec, m: int) -> BranchSpec:
    mode = "ensemble" if spec.mode == "oracle" else spec.mode
    return BranchSpec(spec.branch_id, spec.orders, spec.policy, mode, m, spec.belief)


def paired_difference(
    kpi: str, xa: np.ndarray, xb: np.ndarray, *, level: float, paired: bool, min_pairs: int = 3
) -> KpiDifference:
    """Mean difference with a Student t interval: paired (CRN) or Welch-type independent."""
    n = int(min(xa.size, xb.size))
    if paired:
        d = xa - xb
        mean = float(d.mean()) if n else 0.0
        sd = float(d.std(ddof=1)) if n > 1 else 0.0
        se = sd / math.sqrt(n) if n > 1 else math.inf
        dof = n - 1
    else:
        mean = float(xa.mean() - xb.mean())
        va = float(xa.var(ddof=1)) if xa.size > 1 else 0.0
        vb = float(xb.var(ddof=1)) if xb.size > 1 else 0.0
        sd = math.sqrt(va + vb)
        se = math.sqrt(va / max(xa.size, 1) + vb / max(xb.size, 1))
        dof = max(min(xa.size, xb.size) - 1, 1)
    if n < min_pairs or not math.isfinite(se):
        return KpiDifference(kpi, n, mean, sd, -math.inf, math.inf)
    q = float(student_t.ppf(0.5 + level / 2.0, dof))
    return KpiDifference(kpi, n, mean, sd, mean - q * se, mean + q * se)
