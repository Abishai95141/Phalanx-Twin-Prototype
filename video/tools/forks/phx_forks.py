"""In-process what-if forks on the Phalanx data layer (preview v0.9 code snapshot), for the product demo.

Everything here calls the data layer's own code read-only (``PYTHONPATH`` -> ``.../code/src``; run through
``run.sh``, which also stops Python and numba from writing caches into the read-only source tree):

- the per-tail usage-mode world is built by the preview builder's own ``_fleet_world`` (loaded from
  ``code/tools/build_preview.py``), with the same scenario key, root seed, start date, M14 regime, policy and
  data-quality defect injector as the published v0.9 fleet worlds;
- the decision epoch is reached with the same loop the builder uses (``ScheduledPolicy`` at every 08:00 IST
  decision epoch);
- snapshots, forks, branch runs, KPIs and CRN-paired differences are ``phalanx.fork.ForkService``.

Two thin, documented additions (no data-layer module is changed):

1. ``MirrorSession`` publishes the ``events.*`` rows that M14 downloads to M18 (``obs.event``, at their
   ``t_ingest``) into the session's observation set. The preview builder captured exactly these rows for the
   consumer ``fleet/events.*`` trees, but its session did not put them in the observation set that the
   orders gateway checks evidence against, so an order citing a BIT event would otherwise be rejected as
   "evidence not ingested". ``ScheduledPolicy`` reads only ``maint.records``, so this changes no decision.
2. ``MirrorForkService.fork`` is ``ForkService.fork`` with ``MirrorSession`` instead of ``OpsSession``.

Hard rules honoured: no ``_restricted_labels`` / ``labels.truth`` reads; orders are built from the
observation set as of ``t_issued`` only; decisions act only through ``orders.commands``.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

CODE = Path("/Users/abishaikc/Downloads/phalanx_data_layer_preview/code")
PREVIEW_FLEET = Path("/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet")

_spec = importlib.util.spec_from_file_location("phx_build_preview", CODE / "tools" / "build_preview.py")
bp = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(bp)

from phalanx.fork.belief import SurvivalPosterior  # noqa: E402
from phalanx.fork.service import BranchResult, BranchSpec, ForkService  # noqa: E402
from phalanx.fork.session import OpsSession, SessionSnapshot  # noqa: E402
from phalanx.health.protocol import read_payload  # noqa: E402
from phalanx.maintenance import load_m18_config  # noqa: E402
from phalanx.maintenance.defects import DefectInjector  # noqa: E402
from phalanx.maintenance.records import rows_to_table  # noqa: E402
from phalanx.orders.model import Order  # noqa: E402
from phalanx.orders.policies import PolicyContext, ScheduledPolicy  # noqa: E402

NS = 10**9
DAY = 86_400 * NS
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TAILS = ("TJ101", "TJ102", "TJ103", "TJ104", "TJ105", "TJ106", "TJ107", "TJ108")
EVENT_TOPICS = ("events.bit_faults", "events.exceedances", "events.cautions")


def ist_ns(y: int, m: int, d: int, h: int = 0, mi: int = 0) -> int:
    return int(dt.datetime(y, m, d, h, mi, tzinfo=IST).timestamp()) * NS


def fmt_ist(t_utc_ns: int) -> str:
    return dt.datetime.fromtimestamp(t_utc_ns / NS, IST).strftime("%Y-%m-%d %H:%M IST")


def iso_utc(t_utc_ns: int) -> str:
    return dt.datetime.fromtimestamp(t_utc_ns // NS, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MirrorSession(OpsSession):
    """OpsSession that also publishes M14's ``obs.event`` downloads (``events.*`` rows, at their ingest time)
    into the observation set, as the preview builder did for the consumer ``fleet/events.*`` trees."""

    def _collect(self, trace) -> None:  # type: ignore[override]
        by_topic: dict[str, list[dict[str, Any]]] = {}
        for _, ev in trace.dispatched:
            if ev.kind == "obs.event":
                doc = read_payload(ev.payload)
                by_topic.setdefault(doc["topic"], []).append(doc["row"])
        super()._collect(trace)
        if self.obs is not None:
            for topic in sorted(by_topic):
                self.obs.append(topic, rows_to_table(self.contract, topic, by_topic[topic]))


class MirrorForkService(ForkService):
    """``ForkService`` whose branches are ``MirrorSession``s (otherwise identical to ``ForkService.fork``)."""

    def fork(self, snap: SessionSnapshot, spec: BranchSpec, *, ledger=None) -> OpsSession:  # type: ignore[override]
        root = self.root_for(snap, spec)
        defects = self.defects_factory(snap.root) if self.defects_factory else None
        s = MirrorSession.restore(self.builder, snap, root=root, defects=defects, ledger=ledger)
        if spec.mode == "belief":
            spec.belief.apply(s, particle=spec.member)
        return s


class TailWorld:
    """One preview tail world (the builder's ``_fleet_world``) plus its fork service."""

    def __init__(self, tail: str, days: int) -> None:
        self.tail = tail
        self.k = TAILS.index(tail)
        self.days = days
        self.builder = bp._fleet_world(self.k, days)
        # The preview's World object lacks the WorldBuilder protocol's ``scenario`` field (the preview never
        # forked in ensemble/belief mode). Use the scenario key of the world it wraps (the System's RNG
        # identity), which member_root() and the belief stream key on.
        if not hasattr(self.builder, "scenario"):
            self.builder.scenario = self.builder._ops.scenario
        self.m18_cfg = load_m18_config()
        self.contract = bp._contract()
        b = self.builder

        def defects(root: int) -> DefectInjector:
            return DefectInjector(
                self.m18_cfg.defects,
                root=root,
                scenario=bp.FLEET_SCENARIO,
                contract=self.contract,
                dict_version=b.dict_version,
                dict_hash=b.dict_hash,
            )

        self._defects = defects
        self.fs = MirrorForkService(b, self.m18_cfg, defects_factory=defects)

    @property
    def epoch(self) -> int:
        return self.builder.epoch_utc_ns

    def kernel(self, t_utc: int) -> int:
        return int(t_utc) - self.epoch

    def run_reference(self, t_utc: int) -> tuple[MirrorSession, dict[str, Any]]:
        """The preview's closed loop (ScheduledPolicy at every decision epoch) up to ``t_utc`` (a decision
        epoch; events at exactly ``t_utc`` are not processed, the policy has not yet decided there)."""
        b = self.builder
        t0 = self.kernel(t_utc)
        if not b.calendar.is_epoch(t0):
            raise ValueError("snapshot time must be a decision epoch")
        wall = time.perf_counter()
        s = MirrorSession(b, bp.FLEET_ROOT, defects=self._defects(bp.FLEET_ROOT))
        policy = ScheduledPolicy()
        n_orders = 0
        for t in b.calendar.epochs(1 * NS, t0):
            s.run_until(t)
            ctx = PolicyContext(
                t_utc=s.t_utc,
                catalogue=self.m18_cfg.catalogue,
                cann_min_awp_s=self.m18_cfg.cann_min_awp_s,
                tz_offset_s=self.m18_cfg.tz_offset_s,
            )
            orders = policy.decide(s.obs, ctx)
            if orders:
                s.submit(orders)
                n_orders += len(orders)
        s.run_until(t0)
        return s, {"orders_submitted_before_epoch": n_orders, "wall_s": round(time.perf_counter() - wall, 2)}


def order(
    *,
    order_id: str,
    issuer_id: str,
    issuer_kind: str,
    t_issued: int,
    action: str,
    parameters: dict[str, Any],
    priority: str = "ROUTINE",
    target_tail_no: str | None = None,
    target_base: str | None = None,
    evidence: Sequence[bytes] = (),
    policy_version: str | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        issuer_id=issuer_id,
        issuer_kind=issuer_kind,
        t_issued=int(t_issued),
        t_effective=int(t_issued),  # the 08:00 IST decision epoch itself
        action=action,
        parameters=parameters,
        priority=priority,
        target_tail_no=target_tail_no,
        target_base=target_base,
        evidence=tuple(evidence),
        policy_version=policy_version,
    )


def order_json(o: Order) -> dict[str, Any]:
    return {
        "order_id": o.order_id,
        "issuer_id": o.issuer_id,
        "issuer_kind": o.issuer_kind,
        "t_issued": o.t_issued,
        "t_issued_utc": iso_utc(o.t_issued),
        "t_issued_ist": fmt_ist(o.t_issued),
        "t_effective": o.t_effective,
        "action": o.action,
        "parameters": dict(o.parameters),
        "priority": o.priority,
        "target_tail_no": o.target_tail_no,
        "target_base": o.target_base,
        "evidence": o.evidence_hex(),
        "policy_version": o.policy_version,
    }


def timed_run(
    tw: TailWorld, snap: SessionSnapshot, spec: BranchSpec, horizon_ns: int
) -> tuple[BranchResult, float]:
    w = time.perf_counter()
    r = tw.fs.run(snap, spec, horizon_ns, keep_session=True)
    return r, time.perf_counter() - w


def belief_posterior() -> SurvivalPosterior:
    return SurvivalPosterior("m10", m18_id="m18")
