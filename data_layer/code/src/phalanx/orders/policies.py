"""Reference decision policies (architecture §11.2; report §14 "reference policies are built in").

Policies act only through the orders channel and observe only the contract ``as_of`` the decision epoch (I5):
they are given an observation source with ``as_of(t, topic)`` and never see truth. They benchmark advice
against "what would have happened anyway":

- :class:`StatusQuoPolicy` - IAF-style hard-time / reactive status quo. Hard-time retirement, scheduled
  servicing and reactive repair are M18's standing procedures; the status-quo *decisions* are Maintenance
  Control's cannibalisations, issued here as CANNIBALISE orders from the same rule M18 uses in open loop
  (:func:`phalanx.maintenance.rules.cann_plan`) applied to a view rebuilt from records. Acceptance A3: with
  M18's built-in CANN switched off, this policy reproduces the open-loop KPIs.
- :class:`ScheduledPolicy` - status quo plus preventive actions at fixed flight-hour intervals (engine wash,
  borescope) from ``configs/policies/scheduled.yaml``.
- :class:`ConditionBasedPolicy` - status quo plus simple condition-based thresholds on observed events
  (``configs/policies/condition_based.yaml``): recurring BIT codes are troubleshot at once instead of being
  monitored; repeated engine exceedances trigger a borescope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pyarrow as pa

from phalanx.core.module import EvidenceTag
from phalanx.dictionary.yamlio import load_yaml
from phalanx.maintenance import scir
from phalanx.maintenance.catalogue import Catalogue
from phalanx.maintenance.rules import AwpJob, FleetView, TailView, cann_plan
from phalanx.maintenance.timebase import NS

from .model import Order

POLICY_FORMAT = "phalanx.policy/1"
_POLICY_DIR = Path(__file__).resolve().parents[3] / "configs" / "policies"


class Observations(Protocol):
    def as_of(self, t: int, topic: str, **kw: Any) -> pa.Table: ...


@dataclass
class PolicyContext:
    """What a policy may know besides the observations: the clock and static configuration (no truth)."""

    t_utc: int
    catalogue: Catalogue
    cann_min_awp_s: int
    tz_offset_s: int = 19_800
    _n: int = 0

    def order_id(self, prefix: str) -> str:
        self._n += 1
        stamp = datetime.fromtimestamp(self.t_utc // NS, tz=UTC).strftime("%Y%m%dT%H%M%S")
        return f"{prefix}:{stamp}:{self._n:03d}"


class Policy(Protocol):
    name: str
    version: str

    def decide(self, obs: Observations, ctx: PolicyContext) -> list[Order]: ...


# ------------------------------------------------------------------------------------------------ record
# views
def _latest(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    """All versions per (record_type, record_key), sorted by version."""
    out: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for r in rows:
        out.setdefault((r["record_type"], r["record_key"]), []).append(r)
    for v in out.values():
        v.sort(key=lambda r: int(r["record_version"]))
    return out


def _us_jobs(text: str | None) -> set[str]:
    """Grounding (U/S) job numbers listed in a tech-log limitations text."""
    out: set[str] = set()
    for part in (text or "").split(";"):
        part = part.strip()
        if part.startswith("U/S:"):
            out |= set(part[4:].split())
    return out


def fleet_view_from_records(maint: pa.Table | Sequence[Mapping[str, Any]], t_utc: int) -> FleetView:
    """Rebuild the maintenance-control view from ``maint.records`` (the consumer's information only)."""
    rows = maint.to_pylist() if isinstance(maint, pa.Table) else list(maint)
    groups = _latest(rows)
    tails: dict[str, dict[str, Any]] = {}
    awp_candidates: list[tuple[str, Mapping[str, Any], list[Mapping[str, Any]]]] = []
    for (rt, key), vers in groups.items():
        last = vers[-1]
        if rt == "TECH_LOG":
            tn = last["tail_no"]
            since = -1
            for v in vers:  # start of the current NMC run
                s = scir.RANK[v["availability_state"]]
                if s in scir.NMC_CODES:
                    if since < 0:
                        since = int(v["t_event"])
                else:
                    since = -1
            t = tails.setdefault(tn, {"installed": {}, "open": set()})
            t.update(
                base=last["base"],
                state=scir.RANK[last["availability_state"]],
                since=since,
                us=_us_jobs(last["limitations_text"]),
            )
        elif rt == "COMPONENT_LIFE" and last["install_action"] == "INSTALL":
            t = tails.setdefault(last["tail_no"], {"installed": {}, "open": set()})
            t["installed"][last["part_no"]] = t["installed"].get(last["part_no"], 0) + 1
        elif rt in ("DEFECT_WO", "EXCEEDANCE_INSPECTION") and last["status"] != "CLOSED":
            t = tails.setdefault(last["tail_no"], {"installed": {}, "open": set()})
            if last["part_no"]:
                t["open"].add(last["part_no"])
            if rt == "DEFECT_WO" and last["status"] == "AWAITING_PARTS" and last["part_no"]:
                awp_candidates.append((key, last, vers))
    views = {
        tn: TailView(
            tn,
            d.get("base", ""),
            d.get("state", scir.FMC),
            d.get("since", -1),
            dict(d["installed"]),
            frozenset(d["open"]),
        )
        for tn, d in tails.items()
    }
    awp = []
    for key, last, vers in awp_candidates:
        if key not in tails.get(last["tail_no"], {}).get("us", set()):
            continue  # not a grounding job
        t_awp = int(last["t_event"])
        for v in reversed(vers):
            if v["status"] != "AWAITING_PARTS":
                break
            t_awp = int(v["t_event"])
        awp.append(AwpJob(key, last["tail_no"], last["base"], last["part_no"], t_awp))
    return FleetView(int(t_utc), views, sorted(awp, key=lambda a: a.job_no))


def _record_ids(maint: pa.Table, keys: set[tuple[str, str]]) -> dict[tuple[str, str], bytes]:
    """Latest record_id per (record_type, record_key)."""
    out: dict[tuple[str, str], tuple[int, bytes]] = {}
    for r in maint.select(["record_id", "record_type", "record_key", "record_version"]).to_pylist():
        k = (r["record_type"], r["record_key"])
        if k in keys and (k not in out or r["record_version"] > out[k][0]):
            out[k] = (r["record_version"], r["record_id"])
    return {k: v[1] for k, v in out.items()}


# ------------------------------------------------------------------------------------------------ policies
@dataclass
class StatusQuoPolicy:
    """IAF-style status quo: Maintenance Control cannibalises by the standing rule (orders, HUMAN issuer)."""

    name: str = "status-quo"
    version: str = "1.0.0"
    issuer_id: str = "MAINT-CONTROL"
    issuer_kind: str = "HUMAN"

    def cann_orders(self, maint: pa.Table, ctx: PolicyContext) -> list[Order]:
        view = fleet_view_from_records(maint, ctx.t_utc)
        plan = cann_plan(view, ctx.cann_min_awp_s * NS)
        if not plan:
            return []
        rids = _record_ids(
            maint, {("DEFECT_WO", j) for j, _ in plan} | {("TECH_LOG", f"TL-{d}") for _, d in plan}
        )
        out = []
        for job_no, donor in plan:
            tail = next(a.tail_no for a in view.awp if a.job_no == job_no)
            ev = [rids[k] for k in (("DEFECT_WO", job_no), ("TECH_LOG", f"TL-{donor}")) if k in rids]
            out.append(
                Order(
                    order_id=ctx.order_id(self.name),
                    issuer_id=self.issuer_id,
                    issuer_kind=self.issuer_kind,
                    t_issued=ctx.t_utc,
                    t_effective=ctx.t_utc,
                    action="CANNIBALISE",
                    parameters={"job_no": job_no, "donor_tail_no": donor},
                    priority="AOG",
                    target_tail_no=tail,
                    evidence=tuple(ev),
                    policy_version=f"{self.name}/{self.version}",
                )
            )
        return out

    def decide(self, obs: Observations, ctx: PolicyContext) -> list[Order]:
        return self.cann_orders(obs.as_of(ctx.t_utc, "maint.records"), ctx)


def load_policy_config(name: str, path: Path | None = None) -> dict[str, Any]:
    path = path or _POLICY_DIR / f"{name}.yaml"
    doc = load_yaml(path)
    if not isinstance(doc, Mapping) or doc.get("format") != POLICY_FORMAT:
        raise ValueError(f"{path.name}: format must be {POLICY_FORMAT}")
    for k, spec in doc["rules"].items():
        EvidenceTag.parse(spec["evidence"]["tag"])
        if not spec["evidence"].get("source"):
            raise ValueError(f"{k}: evidence source required")
        if EvidenceTag.parse(spec["evidence"]["tag"]).kind == "ASSUMPTION" and not spec.get("assumption_id"):
            raise ValueError(f"{k}: ASSUMPTION needs an assumption_id")
    return dict(doc)


def _fh_since(maint_rows: Sequence[Mapping[str, Any]], tail: str, since_utc: int) -> float:
    return sum(
        float(r["flight_hours"] or 0.0)
        for r in maint_rows
        if r["record_type"] == "SORTIE" and r["tail_no"] == tail and int(r["t_event"]) >= since_utc
    )


@dataclass
class ScheduledPolicy(StatusQuoPolicy):
    """Status quo plus fixed-interval preventive actions (engine wash, borescope)."""

    name: str = "scheduled"
    version: str = "1.0.0"
    issuer_id: str = "PLANNER-SCHED"
    issuer_kind: str = "AGENT"
    config: Mapping[str, Any] = field(default_factory=lambda: load_policy_config("scheduled"))

    def decide(self, obs: Observations, ctx: PolicyContext) -> list[Order]:
        maint = obs.as_of(ctx.t_utc, "maint.records")
        out = self.cann_orders(maint, ctx)
        rows = maint.to_pylist()
        latest = [v[-1] for (rt, _), v in _latest(rows).items() if rt == "INSPECTION"]
        tails = sorted({r["tail_no"] for r in rows if r["record_type"] == "TECH_LOG"})
        rules = self.config["rules"]
        for tail in tails:
            for rule, action, prm, itype in (
                ("engine_wash", "WASH_SERVICE", {"type": "ENGINE_WASH"}, "WASH"),
                ("borescope", "INSPECT", {"type": "BORESCOPE"}, "BORESCOPE"),
            ):
                every = float(rules[rule]["every_fh"])
                last = max(
                    (
                        int(r["t_event"])
                        for r in rows
                        if r["record_type"] == "INSPECTION"
                        and r["tail_no"] == tail
                        and r["inspection_type"] == itype
                    ),
                    default=0,
                )
                pending = any(  # the latest version of a job decides whether it is still open
                    r["tail_no"] == tail and r["inspection_type"] == itype and r["status"] != "CLOSED"
                    for r in latest
                )
                if not pending and _fh_since(rows, tail, last) >= every:
                    out.append(
                        Order(
                            order_id=ctx.order_id(self.name),
                            issuer_id=self.issuer_id,
                            issuer_kind=self.issuer_kind,
                            t_issued=ctx.t_utc,
                            t_effective=ctx.t_utc,
                            action=action,
                            parameters=prm,
                            priority="ROUTINE",
                            target_tail_no=tail,
                            policy_version=f"{self.name}/{self.version}",
                        )
                    )
        return out


@dataclass
class ConditionBasedPolicy(StatusQuoPolicy):
    """Status quo plus simple condition-based thresholds on observed events."""

    name: str = "condition-based"
    version: str = "1.0.0"
    issuer_id: str = "PLANNER-CBM"
    issuer_kind: str = "AGENT"
    config: Mapping[str, Any] = field(default_factory=lambda: load_policy_config("condition_based"))

    def decide(self, obs: Observations, ctx: PolicyContext) -> list[Order]:
        maint = obs.as_of(ctx.t_utc, "maint.records")
        out = self.cann_orders(maint, ctx)
        rules = self.config["rules"]
        rows = maint.to_pylist()
        latest = {k: v[-1] for k, v in _latest(rows).items()}
        open_jobs = [
            r
            for (rt, _), r in latest.items()
            if rt in ("DEFECT_WO", "INSPECTION") and r["status"] != "CLOSED"
        ]
        # (1) recurring BIT code under deferred monitoring -> troubleshoot now
        bit = obs.as_of(ctx.t_utc, "events.bit_faults")
        window = int(float(rules["bit_recurrence"]["window_days"]) * 86_400) * NS
        k_min = int(rules["bit_recurrence"]["min_events"])
        recent = [
            e
            for e in bit.select(["record_id", "tail_no", "event_code", "t_occurrence"]).to_pylist()
            if int(e["t_occurrence"]) >= ctx.t_utc - window
        ]
        counts: dict[tuple[str, str], list[bytes]] = {}
        for e in recent:
            counts.setdefault((e["tail_no"], e["event_code"]), []).append(e["record_id"])
        for (tail, code), rids in sorted(counts.items()):
            if len(rids) < k_min:
                continue
            monitored = [
                j
                for j in open_jobs
                if j["tail_no"] == tail
                and j["status"] == "DEFERRED"
                and j["action_taken_code"] == "AT-DEF"
                and code in (j["discrepancy_text"] or "")
            ]
            if monitored:
                out.append(
                    Order(
                        order_id=ctx.order_id(self.name),
                        issuer_id=self.issuer_id,
                        issuer_kind=self.issuer_kind,
                        t_issued=ctx.t_utc,
                        t_effective=ctx.t_utc,
                        action="TROUBLESHOOT",
                        parameters={"code": code},
                        priority="ROUTINE",
                        target_tail_no=tail,
                        evidence=tuple(rids),
                        policy_version=f"{self.name}/{self.version}",
                    )
                )
        # (2) repeated engine exceedances -> borescope
        exc = obs.as_of(ctx.t_utc, "events.exceedances")
        ew = int(float(rules["exceedance_borescope"]["window_days"]) * 86_400) * NS
        n_min = int(rules["exceedance_borescope"]["min_events"])
        by_tail: dict[str, list[bytes]] = {}
        for e in exc.select(["record_id", "tail_no", "t_occurrence"]).to_pylist():
            if int(e["t_occurrence"]) >= ctx.t_utc - ew:
                by_tail.setdefault(e["tail_no"], []).append(e["record_id"])
        for tail, rids in sorted(by_tail.items()):
            pending = any(
                j["tail_no"] == tail
                and j["record_type"] == "INSPECTION"
                and (j["inspection_type"] or "") == "BORESCOPE"
                for j in open_jobs
            )
            done = any(
                r["record_type"] == "INSPECTION"
                and r["tail_no"] == tail
                and r["inspection_type"] == "BORESCOPE"
                and int(r["t_event"]) >= ctx.t_utc - ew
                for r in rows
            )
            if len(rids) >= n_min and not pending and not done:
                out.append(
                    Order(
                        order_id=ctx.order_id(self.name),
                        issuer_id=self.issuer_id,
                        issuer_kind=self.issuer_kind,
                        t_issued=ctx.t_utc,
                        t_effective=ctx.t_utc,
                        action="INSPECT",
                        parameters={"type": "BORESCOPE"},
                        priority="ROUTINE",
                        target_tail_no=tail,
                        evidence=tuple(rids),
                        policy_version=f"{self.name}/{self.version}",
                    )
                )
        return out
