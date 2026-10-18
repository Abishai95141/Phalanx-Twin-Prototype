"""Triage (DEVELOPMENT §2.6, architecture 07): open issues → P1 gates → consequence × urgency lookup → policy floor
→ rank within band; issue states with python-statemachine.

Issues come in four kinds: ``alert`` (open alert issues from ``engines.episodes``), ``supply`` (an aircraft not
mission capable, waiting for a part: an AWAITING_PARTS job the tech log lists as U/S, with its open demand),
``life`` (a usage-limited item at its limit, ``engines.life``) and ``group`` (the P4 advisory group).

1. Gates → P1: G1 a WARNING code recurring (≥ 2 sorties within 10 days); G2 an open unscheduled defect the tech
   log lists as U/S (grounding); G3 a life limit reached on a fitted item; G4 a removal risk above the critical
   threshold (from S3's hazard findings, when given).
2. Consequence C from ``triage/effects.yaml`` (dictionary severity; supply 3; life item at its limit 2; inhibited 0).
3. Urgency U from the time-to-act margin when a time to failure exists (life: days to the limit; margin = days −
   (lead-time median + epoch delay + work)), else from state: down for this issue U3; recurring while the aircraft
   is partly capable U2; recurring and recovered U1; otherwise U0.
4. Band = C × U lookup; a decision-table row (P-DEC-01) may raise it, never lower it.
5. Rank within band by expected NMC-days avoided = P(true | evidence) × NMC-days avoidable − weight × man-hours;
   ties by issue id. Confidence from the outcome sample size behind P(true).

Which open issues are decisions today: every gated issue; alert issues that recur (≥ 2 sorties in their 10-day
window) and are still active (fired on the tail's latest sortie, or an open/deferred job) with band P1–P3; supply
and life issues with band P1–P3; and one P4 group of the recurring advisory issues on no-fault-dominated codes.
Everything else open is MONITORING (re-checked every epoch; it returns on recurrence).

``run(store, twin, t) -> list[Issue]`` is the board (decisions, ranked). ``evaluate(store, twin, t)`` returns the
whole ``Board``: decisions, monitoring issues, candidate orders that passed the invariants (and the ones that did
not, with reasons), policy evaluations per issue, the facts, and the alert funnel.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from engines import cnd, isolation, leadtime, similar
from engines import episodes as eps
from engines import life as life_eng
from engines.common import (
    Context,
    belief,
    context,
    finding,
    ist,
    median_mh,
    num,
    seq,
    serial,
    shrunk,
    text,
)
from interfaces import DAY, CandidateOrder, Finding, Issue, IssueState, Tier
from policies import check, policies, prefs
from policies import rules as prules
from statemachine import State, StateMachine

EFFECTS = yaml.safe_load((Path(__file__).resolve().parent / "triage" / "effects.yaml").read_text())
BANDS = ("P1", "P2", "P3", "P4")
MC = ("FMC", "PMCM", "PMCS")


# ---- issue states ----------------------------------------------------------------------------------------
class IssueMachine(StateMachine):
    """Issue life cycle (architecture 07): NEW → TRIAGED → ACKNOWLEDGED → PROPOSED → APPROVED → ORDERED → IN_WORK →
    RESOLVED {CONFIRMED | CND | RTOK} → CLOSED after 3 clean flights; side states MONITORING, SHELVED (time-bound),
    SUPPRESSED_BY_DESIGN; REOPENED on recurrence within 30 days."""

    new = State(initial=True, value=IssueState.NEW.value)
    triaged = State(value=IssueState.TRIAGED.value)
    acknowledged = State(value=IssueState.ACKNOWLEDGED.value)
    monitoring = State(value=IssueState.MONITORING.value)
    shelved = State(value=IssueState.SHELVED.value)
    suppressed = State(value=IssueState.SUPPRESSED_BY_DESIGN.value)
    proposed = State(value=IssueState.PROPOSED.value)
    approved = State(value=IssueState.APPROVED.value)
    ordered = State(value=IssueState.ORDERED.value)
    in_work = State(value=IssueState.IN_WORK.value)
    resolved = State(value=IssueState.RESOLVED.value)
    closed = State(value=IssueState.CLOSED.value)
    reopened = State(value=IssueState.REOPENED.value)

    triage = new.to(triaged) | reopened.to(triaged)
    acknowledge = triaged.to(acknowledged)
    monitor = triaged.to(monitoring) | acknowledged.to(monitoring) | proposed.to(monitoring)
    shelve = triaged.to(shelved) | acknowledged.to(shelved) | monitoring.to(shelved) | proposed.to(shelved)
    unshelve = shelved.to(triaged)
    suppress = new.to(suppressed) | triaged.to(suppressed) | monitoring.to(suppressed)
    unsuppress = suppressed.to(triaged)
    propose = triaged.to(proposed) | acknowledged.to(proposed) | monitoring.to(proposed)
    approve = proposed.to(approved)
    reject = proposed.to(triaged)
    order = approved.to(ordered)
    start_work = ordered.to(in_work)
    resolve = in_work.to(resolved) | monitoring.to(resolved)
    close = resolved.to(closed)
    reopen = resolved.to(reopened) | closed.to(reopened) | monitoring.to(reopened)


def next_state(prior: IssueState | None, *, decision: bool, has_order: bool, suppressed: bool) -> IssueState:
    """The state an issue reaches this epoch from ``prior`` (None = first seen). Human steps (approve, order, …)
    are events the loop sends later; triage only moves issues between NEW/TRIAGED/PROPOSED/MONITORING/SUPPRESSED."""
    m = IssueMachine(start_value=prior.value) if prior else IssueMachine()
    s = lambda: IssueState(m.current_state_value)
    if s() in (IssueState.RESOLVED, IssueState.CLOSED):
        m.send("reopen")
    if s() in (IssueState.NEW, IssueState.REOPENED):
        if suppressed:
            m.send("suppress")
            return s()
        m.send("triage")
    if s() == IssueState.SUPPRESSED_BY_DESIGN and not suppressed:
        m.send("unsuppress")
    if suppressed and s() in (IssueState.TRIAGED, IssueState.MONITORING):
        m.send("suppress")
    elif decision and has_order and s() in (IssueState.TRIAGED, IssueState.ACKNOWLEDGED, IssueState.MONITORING):
        m.send("propose")
    elif not decision and s() in (IssueState.TRIAGED, IssueState.ACKNOWLEDGED, IssueState.PROPOSED):
        m.send("monitor")
    return s()


# ---- facts -----------------------------------------------------------------------------------------------
@dataclass
class Facts:
    """Everything gates, lookup, policies and the screens need about one issue at t."""

    issue_id: str
    kind: str  # alert | supply | life | group
    tail_no: str | None
    code: str
    title: str  # board label, in the film's voice ("Hydraulic alarm that never clears")
    severity: str
    description: str = ""  # dictionary description of the code, or the item
    card: str = ""  # decision-page title ("TJ107 · hydraulic alarm HYD-101")
    fault_list: str = ""
    first: int = 0
    last: int = 0
    n_alerts: int = 0
    occ_10d: int = 0
    consec: int = 0
    recurring: bool = False
    active: bool = False
    job_status: str = "NONE"
    grounding: bool = False
    corroborated: bool = False
    inhibited: bool = False
    nofault_rate: float = 0.0
    prior_cnd: int = 0
    removals: int = 0
    confirmed: int = 0  # removed units of this tail confirmed faulty at the bench
    p_true: tuple[float, float, float] | None = None
    p_n: int | None = None
    aircraft: str = ""
    down_for_issue: bool = False
    down_days: float = 0.0
    ttf_days: float | None = None
    lead_days: float | None = None
    work_days: float = 0.0
    action_mh: float = 0.0
    nmc_avoidable: float = 0.0
    life_used: float | None = None
    life_limit: int | None = None
    life_left: float | None = None
    life_unit: str = ""
    life_overrun: int = 0  # uses past the limit the station's own hard-time changes reach (life.station_overrun)
    life_overrun_n: int = 0
    rate_per_day: float | None = None
    part_no: str | None = None
    quantity: int = 0
    demand_no: str | None = None
    base: str | None = None
    donor_nmc: bool = False
    donor_tail: str | None = None
    evidence: tuple[str, ...] = ()
    occ_times: tuple[int, ...] = ()
    gate: str | None = None
    C: int | None = None
    U: int | None = None
    margin: float | None = None
    u_basis: str = ""
    lookup: str | None = None
    band: str | None = None
    basis: str = ""
    value: float | None = None
    confidence: str = ""
    reason: str = ""
    decision: bool = False
    members: tuple[str, ...] = ()


def _confidence(n: int | None, pr) -> str:
    if n is None:
        return "high"
    return "high" if n >= pr["confidence_n"]["high"] else "med" if n >= pr["confidence_n"]["med"] else "low"


def _nmc_per_job(ctx: Context, code: str) -> float:
    """Mean non-mission-capable days per closed job of the code across the fleet (capped at 30 d per job)."""
    key = ("triage_nmc", code)
    if key not in ctx._memo:
        j = ctx.code_jobs(code)
        j = j[(j.status == "CLOSED") & j.t_close.notna()]
        v = [min(ctx.non_mc_days(r.tail_no, int(r.first_ingest), int(r.t_close)), 30.0) for r in j.itertuples()]
        ctx._memo[key] = round(sum(v) / len(v), 3) if v else 0.0
    return ctx._memo[key]


def _job_status(ctx: Context, tail: str, code: str) -> str:
    jobs = ctx.code_jobs(code, tail)
    open_j = jobs[jobs.status != "CLOSED"]
    if (open_j.status == "DEFERRED").any():
        return "DEFERRED"
    if len(open_j):
        t_open = int(open_j.first_ingest.min())
        so = ctx.sorties(tail)
        fired = ctx.fired_sorties(tail, code)
        if any(s in fired for s in so[so.t_event > t_open].sortie_id):
            return "DEFERRED"  # carried: the aircraft has flown with the defect open
        return str(open_j.sort_values("first_ingest").status.iloc[-1])
    return "CLOSED" if len(jobs) else "NONE"


def alert_facts(ctx: Context, ep: eps.Episode, pr) -> Facts:
    rec = eps.recent_occurrences(ctx, ep)
    occ10 = int(rec.sortie_id.nunique())
    cons = ctx.consecutive(ep.tail_no, ep.code)
    js = _job_status(ctx, ep.tail_no, ep.code)
    jobs = ctx.code_jobs(ep.code, ep.tail_no)
    us = set(ctx.unserviceable_jobs(ep.tail_no))
    open_j = jobs[jobs.status != "CLOSED"]
    grounding = bool(((open_j.job_no.isin(us)) & (open_j.when_discovered != "WD-SCH")).any())
    cited = {x for ev in jobs.evidence for x in ev}
    latest = ctx.occ[(ctx.occ.tail_no == ep.tail_no) & ctx.occ.rid.isin(ep.rids)].iloc[-1]
    unanswered = not (set(latest.rids) & cited)
    top = max(ep.suspects, key=lambda s: s[1])[0] if ep.suspects else None
    corro = False
    if top:
        o = ctx.occ
        o = o[(o.tail_no == ep.tail_no) & o.sortie_id.isin(set(rec.sortie_id)) & (o.event_code != ep.code)]
        corro = any(seq(s) and max(seq(s), key=lambda x: x["isolation_confidence"])["lru"] == top
                    for s in o.suspect_lrus)
    rates = cnd.code_rates(ctx, ep.code)
    hist = cnd.issue_history(ctx, ep.tail_no, ep.code)
    state = ctx.state_now.get(ep.tail_no, ("UNKNOWN", None))[0]
    iso = isolation.analyse(ctx, ep.tail_no, ep.code)
    mh = iso.tests[0].test.mh if iso and iso.tests else (median_mh(jobs[jobs.action_taken_code == "AT-CND"])[0] or 0.0)
    # removals: of the part the code's remove-and-replace jobs change (fleet), counted as removal events on this tail
    rr = ctx.code_jobs(ep.code)
    rr = rr[rr.action_taken_code == "AT-RR"].part_no.dropna()
    removed_part = rr.mode().iat[0] if len(rr) else None
    removals = len(ctx.removal_events(ep.tail_no, removed_part)) if removed_part else hist["removals"]
    return Facts(
        issue_id=ep.issue_id, kind="alert", tail_no=ep.tail_no, code=ep.code,
        title=ep.description, description=ep.description, severity=ep.severity,
        fault_list=ep.fault_list, first=ep.first, last=ep.last, n_alerts=ep.n, occ_10d=occ10, consec=cons,
        recurring=occ10 >= pr["recurrence_min"], active=cons >= 1 or unanswered or js in ("DEFERRED", "OPEN", "IN_WORK", "AWAITING_PARTS"),
        job_status=js, grounding=grounding, corroborated=corro, inhibited=ep.inhibited,
        nofault_rate=rates.nofault[0], prior_cnd=int(hist["actions"].get("AT-CND", 0)), removals=removals,
        confirmed=hist["units_confirmed"],
        p_true=rates.p_confirmed, p_n=rates.labelled, aircraft=state, down_for_issue=state not in MC and grounding,
        action_mh=float(mh), work_days=float(mh) / pr["work_day_hours"], nmc_avoidable=_nmc_per_job(ctx, ep.code),
        evidence=tuple(rec.rid), occ_times=tuple(int(x) for x in rec.t_occurrence),
    )


def supply_facts(ctx: Context, pr) -> list[Facts]:
    """Aircraft down for a part: NMCS now, with an AWAITING_PARTS job the tech log lists as U/S and its open demand."""
    out = []
    lat = ctx.latest
    for tail, (state, since) in sorted(ctx.state_now.items()):
        if state != "NMCS":
            continue
        us = set(ctx.unserviceable_jobs(tail))
        jobs = ctx.jobs[(ctx.jobs.tail_no == tail) & ctx.jobs.job_no.isin(us) & (ctx.jobs.status == "AWAITING_PARTS")]
        for j in jobs.itertuples():
            dem = lat[(lat.tail_no == tail) & (lat.record_type == "SUPPLY_DEMAND") & (lat.job_no == j.job_no) &
                      (lat.status != "CLOSED")].sort_values("t_open")
            if not len(dem):
                continue
            d = dem.iloc[0]
            short = str(j.part_no).replace("SYN-PN-", "")
            label = EFFECTS["labels"].get(j.part_no, short.lower())
            med, _ = leadtime.predict(ctx, j.part_no, text(d.priority) or "AOG")
            donor = None
            if pr["cannibalisation_enabled"]:
                donor = next((t for t, (s, _) in sorted(ctx.state_now.items()) if t != tail and s not in MC and
                              any(x.part_no == j.part_no for x in ctx.twin.installed(ctx.t, t))), None)
            tl = ctx.tech_log.get(tail)
            down = (ctx.t - int(since)) / DAY if since is not None else 0.0
            out.append(Facts(
                issue_id=f"{tail}-AOG-{short}", kind="supply", tail_no=tail, code=str(j.part_no), title=f"AOG {label}", description=label,
                severity="NMCS", first=int(d.t_open), last=int(d.t_open), aircraft=state, down_for_issue=True,
                down_days=round(down, 1), lead_days=med, part_no=str(j.part_no), demand_no=str(d.demand_no),
                base=str(j.base) if isinstance(j.base, str) else None, donor_nmc=donor is not None, donor_tail=donor,
                nmc_avoidable=float(med or 0.0),
                evidence=tuple([d.rid, j.rid] + ([tl.rid] if tl is not None else [])),
            ))
    return out


def life_facts(ctx: Context, pr) -> list[Facts]:
    out = []
    for it in life_eng.items(ctx):
        if it.fitted == 0 or it.left > pr["life_at_limit_uses"]:
            continue
        state = ctx.state_now.get(it.tail_no, ("UNKNOWN", None))[0]
        if state == "NMCD":
            continue  # at the depot: no use until it returns
        short = it.part_no.replace("SYN-PN-", "")
        med, _ = leadtime.predict(ctx, it.part_no, "MCM")
        rr = ctx.jobs[(ctx.jobs.part_no == it.part_no) & (ctx.jobs.status == "CLOSED")]
        mh = median_mh(rr)[0] or 0.0
        base = ctx.latest[ctx.latest.tail_no == it.tail_no].base.dropna()
        ttf = it.days_to_limit
        out.append(Facts(
            issue_id=f"{it.tail_no}-{short}", kind="life", tail_no=it.tail_no, code=it.part_no,
            title=f"{it.label.capitalize()} at limit", description=it.label, severity="LIFE", first=it.installed_at or 0, last=ctx.t,
            aircraft=state, ttf_days=ttf, lead_days=med, work_days=mh / pr["work_day_hours"], action_mh=0.0,
            life_used=it.used, life_limit=it.limit, life_left=it.left, life_unit=it.unit, rate_per_day=it.rate_per_day,
            life_overrun=it.overrun, life_overrun_n=it.overrun_n,
            part_no=it.part_no, quantity=it.fitted, base=str(base.iat[-1]) if len(base) else None,
            nmc_avoidable=max(float(med or 0.0) - float(ttf or 0.0), 0.0), evidence=it.evidence,
        ))
    return out


def inspection_facts(ctx: Context) -> list[Facts]:
    """Gate G2's second half: an open exceedance inspection (none in the preview)."""
    out = []
    lat = ctx.latest
    ins = lat[(lat.record_type == "INSPECTION") & (lat.status != "CLOSED")]
    kinds = EFFECTS["exceedance_inspections"]
    for r in ins.itertuples():
        if any(k in text(r.inspection_type) for k in kinds):
            out.append(Facts(issue_id=f"{r.tail_no}-INSP-{r.record_key}", kind="inspection", tail_no=r.tail_no,
                             code=str(r.inspection_type), title=f"Open {r.inspection_type} inspection", severity="INSPECTION",
                             first=int(r.t_event), last=int(r.t_event), gate="G2",
                             aircraft=ctx.state_now.get(r.tail_no, ("UNKNOWN", None))[0], evidence=(r.rid,)))
    return out


def risk_facts(ctx: Context, extra: Iterable[Finding], pr) -> list[Facts]:
    """Gate G4 from S3's hazard findings: a removal-risk belief above the critical threshold on a safety-critical
    class (the serial's prefix, e.g. HYDP-000010 → HYDP)."""
    out = []
    for f in extra:
        if str(f.subject).split("-")[0] not in EFFECTS["safety_critical_classes"]:
            continue
        for b in f.beliefs:
            if b.name.startswith("removal_risk") and b.value is not None and b.value >= pr["critical_removal_risk"]:
                out.append(Facts(
                    issue_id=f"{f.tail_no}-RISK-{f.subject}", kind="risk", tail_no=f.tail_no, code=f.subject,
                    title="Removal risk", severity="RISK", first=ctx.t, last=ctx.t, gate="G4",
                    p_true=(b.value, b.lo or b.value, b.hi or b.value), p_n=b.n,
                    evidence=tuple(bytes(e).hex() for e in f.evidence),
                ))
    return out


# ---- score -----------------------------------------------------------------------------------------------
def _gate(f: Facts) -> str | None:
    if f.gate:
        return f.gate
    if f.kind == "alert" and f.severity == "WARNING" and f.recurring:
        return "G1"
    if f.kind == "alert" and f.grounding:
        return "G2"
    if f.kind == "life" and f.life_left is not None and -f.life_left > f.life_overrun:
        return "G3"  # past the limit by more than the station's own hard-time changes ever go
    return None


def _consequence(f: Facts) -> int:
    c = EFFECTS["consequence"]
    if f.kind == "alert":
        return c["suppressed"] if f.inhibited else int(c["severity"].get(f.severity, 1))
    if f.kind == "supply":
        return int(c["supply"])
    if f.kind == "life":
        return int(c["life_at_limit"])
    return 3


def _urgency(f: Facts, pr) -> tuple[int, float | None, str]:
    if f.ttf_days is not None:
        m = f.ttf_days - ((f.lead_days or 0.0) + pr["epoch_delay_days"] + f.work_days)
        th = EFFECTS["urgency_margin_days"]
        u = 3 if m < th["U3"] else 2 if m < th["U2"] else 1 if m < th["U1"] else 0
        return u, round(m, 2), (f"{f.life_left:g} {f.life_unit} left · {f.rate_per_day:g}/d · margin {m:+.1f} d"
                                if f.kind == "life" else f"margin {m:+.1f} d")
    if f.down_for_issue:
        return 3, None, f"{f.severity} {f.down_days:.0f} d" if f.kind == "supply" else f"{f.aircraft} for this issue"
    if f.recurring and f.aircraft in ("PMCM", "PMCS"):
        return 2, None, f"recurring · aircraft {f.aircraft}"
    if f.recurring:
        return 1, None, f"{f.occ_10d} in 10 d · aircraft recovered ({f.aircraft})"
    return 0, None, f"aircraft {f.aircraft}" if f.aircraft else "no mission effect"


def _value(f: Facts, pr) -> float:
    p = f.p_true[0] if f.p_true else 1.0
    return round(p * f.nmc_avoidable - pr["weight_man_hour"] * f.action_mh, 4)


NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
       11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen"}
TIMES = {1: "once", 2: "twice"}


def _times(k: int) -> str:
    return TIMES.get(k) or f"{NUM.get(k, k)} times"


def _part_of(ctx: Context, f: Facts) -> str | None:
    """Label of the suspect part removed under the code (e.g. "pump"), if the code has one."""
    iso = isolation.analyse(ctx, f.tail_no, f.code)
    lru = next((h for h, p in iso.parts.items() if p), None) if iso else None
    return iso.labels[lru] if lru else None


def _texts(ctx: Context, f: Facts, pr) -> tuple[str, str, str]:
    """(board label, board "why" line, decision-page title), built from templates over the facts."""
    d = lambda t: ist(t, "%d %b")
    if f.kind == "alert":
        word = f.description.split(" ", 1)[0]
        ts = sorted(f.occ_times)
        if f.gate == "G1":
            gap = round((ts[-1] - ts[0]) / DAY) if len(ts) > 1 else 0
            why = f"The same warning {_times(len(ts))} in {NUM.get(gap, gap)} days · {d(ts[0])} and {d(ts[-1])}"
            return f"{f.description} warning", why, f"{f.tail_no} · {_lc(f.description)} {f.code}"
        if f.consec >= pr["standing_flights"]:
            part = _part_of(ctx, f)
            if f.removals and part:
                why = (f"{f.consec} flights in a row · {f.removals} {part} removals found nothing" if f.confirmed == 0
                       else f"{f.consec} flights in a row · {f.confirmed} of {f.removals} {part} removals confirmed")
            else:
                why = f"{f.consec} flights in a row · {f.prior_cnd} could-not-duplicate closes"
            return f"{word} alarm that never clears", why, f"{f.tail_no} · {word.lower()} alarm {f.code}"
        k = len({*ts})
        why = f"{_times(k).capitalize()} in ten days" if k else f"{f.n_alerts} sorties"
        return f.description, why, f"{f.tail_no} · {_lc(f.description)} {f.code}"
    if f.kind == "supply":
        return (f"Waiting for a {f.description}", f"Grounded {f.down_days:.0f} days · oldest open AOG demand",
                f"{f.tail_no} · waiting for a {f.description}")
    if f.kind == "life":
        label = f"{f.description.capitalize()} at {f.life_used:g} of {f.life_limit} {f.life_unit}"
        if f.life_left is not None and f.life_left < 0:
            over, unit = -f.life_left, f.life_unit.rstrip("s")
            why = (f"{over:g} {unit if over == 1 else f.life_unit} past the limit · the station's own changes go up to "
                   f"{f.life_overrun} past it" if over <= f.life_overrun else
                   f"{over:g} {f.life_unit} past the limit, beyond the station's usual {f.life_overrun} · "
                   "or the change is not on record yet")
        else:
            why = f"The next {f.life_unit.rstrip('s')} reaches the limit · {f.rate_per_day:g} a day"
        return label, why, f"{f.tail_no} · {_lc(label)}"
    if f.kind == "inspection":
        return f.title, f"{f.title} on {f.tail_no}", f"{f.tail_no} · {_lc(f.title)}"
    if f.kind == "risk":
        why = f"Removal risk {f.p_true[0]:.2f} over the next 30 days, above {pr['critical_removal_risk']}"
        return f"Removal risk on {f.code}", why, f"{f.tail_no} · removal risk {f.code}"
    return f.title, f.reason, f.title


def _raise(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b, key=BANDS.index)


@dataclass(frozen=True)
class Board:
    t: int
    issues: tuple[Issue, ...]  # decisions, ranked: P1 first
    monitoring: tuple[Issue, ...]
    orders: tuple[CandidateOrder, ...]
    rejected: tuple[tuple[CandidateOrder, str], ...]
    evaluations: Mapping[str, Mapping[str, object]]  # issue id → policy → policies.Evaluation
    facts: Mapping[str, Facts]
    funnel: Mapping[str, int]
    flood: bool = False
    group: tuple[str, ...] = field(default=())  # issue ids in the P4 group


def evaluate(store, twin, t: int, *, extra_findings: Iterable[Finding] = (),
             prior_states: Mapping[str, IssueState] | None = None, open_orders=()) -> Board:
    ctx = context(store, twin, t)
    key = ("board", tuple(extra_findings), tuple(sorted((prior_states or {}).items())), tuple(open_orders))
    if key not in ctx._memo:
        ctx._memo[key] = _evaluate(ctx, tuple(extra_findings), prior_states or {}, tuple(open_orders))
    return ctx._memo[key]


def _evaluate(ctx: Context, extra_findings, prior_states, open_orders) -> Board:
    t = ctx.t
    pr, pol = prefs(), policies()
    facts = [alert_facts(ctx, e, pr) for e in eps.open_episodes(ctx)]
    facts += supply_facts(ctx, pr) + life_facts(ctx, pr) + inspection_facts(ctx) + risk_facts(ctx, extra_findings, pr)
    evals, orders = {}, {}
    group: list[Facts] = []
    for f in facts:
        f.gate = _gate(f)
        f.C = _consequence(f)
        f.U, f.margin, f.u_basis = _urgency(f, pr)
        f.lookup = EFFECTS["band"][f.C][f.U]
        evals[f.issue_id] = prules.evaluate(pol, f, pr)
        fl, row = prules.floor(evals[f.issue_id])
        if f.gate:
            f.band, f.basis = "P1", f"Gate {f.gate} · {EFFECTS['gates'][f.gate]}"
        else:
            f.band = _raise(f.lookup, fl)
            raised = fl is not None and f.band == fl and f.band != f.lookup
            f.basis = f"{row} · policy floor" if raised else f"AP lookup · C{f.C} × U{f.U}"
        if f.kind == "alert" and prules.nuisance(f, pr):
            f.basis += " · D8 nuisance review"
        f.value = _value(f, pr)
        f.confidence = _confidence(f.p_n if f.kind == "alert" else None, pr)
        f.title, f.reason, f.card = _texts(ctx, f, pr)
        if f.kind == "alert":
            individual = f.band in ("P1", "P2", "P3") and (f.gate is not None or (f.recurring and f.active) or
                                                           (fl is not None and fl != "P4"))
            if individual:
                f.decision = True
            elif (f.severity == "ADVISORY" and f.recurring and not f.inhibited
                  and f.nofault_rate >= pr["nofault_dominated"]):
                group.append(f)
        else:
            f.decision = f.band in ("P1", "P2", "P3")
        if f.decision:
            orders[f.issue_id] = prules.candidates(pol, f, evals[f.issue_id], f.band, pr)
    by_id = {f.issue_id: f for f in facts}
    if group:
        codes = sorted({g.code for g in group})
        rates = [cnd.code_rates(ctx, c) for c in codes]
        k, n = sum(r.confirmed for r in rates), sum(r.labelled for r in rates)
        fr = cnd.fleet_rates(ctx)["p_confirmed"]
        r5 = any((evals[g.issue_id].get("P-DEC-01") and evals[g.issue_id]["P-DEC-01"].row == "r5") for g in group)
        nf = sum(r.no_fault for r in rates) / max(sum(r.closed for r in rates), 1)
        n_tails = len({x.tail_no for x in group})
        label = f"{NUM.get(len(group), len(group)).capitalize()} advisory issues, grouped"
        g = Facts(issue_id="P4-ADVISORY", kind="group", tail_no=None, code=" · ".join(codes),
                  title=label, card=f"{n_tails} tails · {_lc(label)}", severity="ADVISORY", first=min(x.first for x in group),
                  last=max(x.last for x in group), n_alerts=sum(x.n_alerts for x in group), C=1, U=0, band="P4",
                  lookup="P4", basis="P-DEC-01 r5 · RECUR_NOFAULT_DOMINATED_REVIEW" if r5 else "AP lookup · C1 × U0",
                  u_basis="advisory · no mission effect", p_true=shrunk(k, n, fr, cnd.PS), p_n=n, value=0.0,
                  confidence=_confidence(n, pr), decision=True, members=tuple(x.issue_id for x in group),
                  reason=("Almost always closed as could-not-duplicate" if nf >= 0.9 else
                          f"Mostly closed with no fault found ({nf:.0%})") + f" · {n_tails} tails",
                  evidence=tuple(e for x in group for e in x.evidence))
        by_id[g.issue_id] = g
        evals[g.issue_id] = {}
    decisions = [f for f in by_id.values() if f.decision]
    decisions.sort(key=lambda f: (BANDS.index(f.band), -(f.value or 0.0), f.issue_id))
    flood = len(decisions) > 2 * pr["budget"]
    # candidate orders in board order, through the invariants
    cands = [c for f in decisions for c in orders.get(f.issue_id, [])]
    ing = ctx.ingest_of_rid
    kept, rejected = check(cands, t, lambda tail, e: ing.get((tail, bytes(e).hex())), open_orders)
    with_order = {c.issue_id for c in kept}
    member = {m for f in decisions for m in f.members}

    def issue(f: Facts) -> Issue:
        st = next_state(prior_states.get(f.issue_id), decision=f.decision or f.issue_id in member,
                        has_order=f.issue_id in with_order, suppressed=f.inhibited)
        return Issue(issue_id=f.issue_id, tail_no=f.tail_no, code=f.code, title=f.title, severity=f.severity,
                     first=int(f.first), last=int(f.last), n_alerts=int(f.n_alerts), state=st,
                     band=f.band if (f.decision or f.issue_id in member) else None, consequence=f.C, urgency=f.U,
                     basis=f.basis, rank_value=f.value, confidence=f.confidence,
                     findings=tuple(issue_findings(ctx, f, evals.get(f.issue_id, {}))))

    board = tuple(issue(f) for f in decisions)
    mon = tuple(issue(f) for f in sorted(by_id.values(), key=lambda x: x.issue_id)
                if not f.decision and f.issue_id not in member)
    fun = eps.funnel(ctx) | {"decisions": len(board), "monitoring": len(mon)}
    return Board(t=t, issues=board, monitoring=mon, orders=tuple(kept), rejected=tuple(rejected), evaluations=evals,
                 facts=by_id, funnel=fun, flood=flood, group=tuple(member))


def issue_findings(ctx: Context, f: Facts, evals) -> list[Finding]:
    """The triage finding (board reason, C, U, band, value) first, then the engine findings behind the issue."""
    beliefs = [belief("triage", "consequence", f.C), belief("triage", "urgency", f.U, note=f.u_basis),
               belief("triage", "rank_value", f.value, note="expected NMC-days avoided")]
    if f.p_true:
        beliefs.append(belief("triage", "p_true", *f.p_true, n=f.p_n))
    if f.margin is not None:
        beliefs.append(belief("triage", "margin_days", f.margin))
    for name, e in evals.items():
        beliefs.append(belief("triage", f"policy:{name}", None, note=f"{e.version} {e.row} → {e.rec or e.output}"))
    out = [finding("triage", Tier.PRESC, f.tail_no, f.issue_id, beliefs, [bytes.fromhex(x) for x in f.evidence],
                   f.reason)]
    if f.kind == "alert":
        ep = next(e for e in eps.open_episodes(ctx) if e.issue_id == f.issue_id)
        out.append(eps.issue_finding(ctx, ep))
        out.append(cnd.code_finding(ctx, f.code))
        out.append(cnd.issue_finding(ctx, f.tail_no, f.code, f.issue_id))
        if f.decision:
            out += isolation.findings(ctx, ep) + similar.findings(ctx, ep)
    return out


def run(store, twin, t: int) -> list[Issue]:
    """The decision board at t: issues needing a decision, ranked (P1 first, then by expected NMC-days avoided)."""
    return list(evaluate(store, twin, t).issues)


# ---- entry points of the loop and the API (shapes: proto/web/assets/SHAPES.md) ---------------------------
ROW_TEXT = {
    "r1": "A warning-level code that recurs within 10 days is troubleshot at once.",
    "r2": "A deferred code that recurs and is corroborated by another source is troubleshot.",
    "r3": "A deferred code that keeps returning for three or more flights is troubleshot.",
    "r4": "A deferred code that recurs on a code with a low no-fault rate is troubleshot.",
    "r5": "A deferred code that recurs on a no-fault-dominated code is monitored and reviewed.",
    "r6": "No decision-table row applies.",
}


def build_board(store, twin, t: int):
    """For S1's epoch loop: (board issues, [(candidate order, policy semver)], funnel)."""
    b = evaluate(store, twin, t)
    ctx = context(store, twin, t)
    sem = policies().semver
    from engines.drift import _week0

    fun = dict(b.funnel) | {"items": len(b.issues), "days": round((t - _week0(ctx)) / DAY)}
    return list(b.issues), [(c, sem[c.rule]) for c in b.orders], fun


def _lc(s: str) -> str:
    """Lower-case the first letter unless the first word is an acronym ("AOG brake chute" stays)."""
    w = s.split(" ", 1)[0]
    return s if w.isupper() and len(w) > 1 else s[:1].lower() + s[1:]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}"


def _ev_rows(ctx: Context, f: Facts, k: int = 6) -> list[dict]:
    o = ctx.occ
    rows = o[o.rid.isin(set(f.evidence))].sort_values("t_ingest").tail(k)
    if len(rows):
        return [{"rid": r.rid, "sortie": r.sortie_id, "t_occ": ist(r.t_occurrence), "t_ingest": ist(r.t_ingest),
                 "before_snapshot": bool(r.t_ingest <= ctx.t), "persistence": int(num(r.persistence_count)),
                 "mech": text(r.detection_mechanism) or None} for r in rows.itertuples()]
    ing = ctx.ingest_of_rid
    return [{"rid": x, "t_occ": None, "t_ingest": ist(ing.get((f.tail_no, x))),
             "before_snapshot": (ing.get((f.tail_no, x)) or ctx.t + 1) <= ctx.t} for x in f.evidence[-k:]]


def issue_detail(store, twin, t: int, issue_id: str) -> dict | None:
    """``PHX_ISSUE`` without the parts S1 adds (orders, decision, impact): state / why / forecast, evidence, the
    rule trace and why the alternatives lose."""
    b = evaluate(store, twin, t)
    f = b.facts.get(issue_id)
    if f is None:
        return None
    ctx = context(store, twin, t)
    ev = b.evaluations.get(issue_id, {})
    order = next((c for c in b.orders if c.issue_id == issue_id), None)
    from policies import candidate_order_id

    d: dict = {"id": f.issue_id, "tail": f.tail_no or f"{len({m.split('-')[0] for m in f.members})} tails",
               "code": f.code, "band": f.band, "whynot": [], "donothing": None,
               "state": next((i.state.value for i in (*b.issues, *b.monitoring) if i.issue_id == issue_id), None),
               "evidence": {"cited": len(f.evidence), "rows": _ev_rows(ctx, f),
                            "order_id": candidate_order_id(order, t) if order else None}}
    gate_step = {"h": f"Gate {f.gate} · {EFFECTS['gates'][f.gate]}" if f.gate else "Safety gates — none tripped",
                 "p": f.reason if f.gate else "No recurring warning, no grounding defect, no limit reached. The issue is scored, not gated.",
                 "hit": bool(f.gate)}
    steps = [gate_step, {"h": f"Lookup · C{f.C} × U{f.U} → {f.lookup or 'monitor'}",
                         "p": f"Consequence {f.C}, urgency {f.U}: {f.u_basis}.", "hit": not f.gate and f.lookup == f.band}]
    for name, e in ev.items():
        if name in ("P-DEC-01", "P-ORG-02", "P-SPR-01"):
            steps.append({"h": f"Policy {name} · row {e.row}", "p": ROW_TEXT.get(e.row, "") if name == "P-DEC-01" else
                          f"{e.rec.get('action')} · {e.rec.get('rationale_id')}", "hit": e.rec.get("action") not in (None, "NONE"),
                          "tag": f"{e.rec.get('action')} → {e.rec.get('band') or f.band}"})
    if f.kind == "alert" and prules.nuisance(f, prefs()):
        steps.append({"h": "Triage rule D8 · standing alarm", "hit": True, "tag": f"{f.prior_cnd} no-fault outcomes on {f.tail_no}",
                      "p": "Five or more flights with two or more no-fault outcomes goes to a human nuisance review."})
    d["rule"] = {"steps": steps, "note": " · ".join(e.version for e in ev.values())}
    if f.kind == "alert":
        r = cnd.code_rates(ctx, f.code)
        iso = isolation.analyse(ctx, f.tail_no, f.code)
        lab = {h: iso.labels[h] for h in iso.posterior} if iso else {}
        top = max(iso.posterior, key=iso.posterior.get) if iso else None
        part_lru = next((h for h, p in iso.parts.items() if p), None) if iso else None
        rr = ctx.code_jobs(f.code)
        rr = rr[rr.action_taken_code == "AT-RR"].part_no.dropna()
        removed = rr.mode().iat[0] if len(rr) else None
        part = iso.labels[part_lru] if part_lru else EFFECTS["labels"].get(removed, str(removed or "unit").replace("SYN-PN-", ""))
        d["title"] = f.card
        d["standing"] = f"Standing for {f.consec} flights" if f.consec >= 2 else f"{f.occ_10d} times in 10 days"
        if part_lru and f.removals >= 3 and f.confirmed == 0 and top and top != part_lru:
            d["reco"] = {"headline": f"Stop removing the {part}. Troubleshoot the {lab[top]}.",
                         "text": f"The {f.code} alarm on {f.tail_no} has outlived {f.removals} {part} removals, and the shop "
                                 f"found nothing wrong with any of them."}
        else:
            what = f"start with the {iso.tests[0].test.name.lower()}" if iso and iso.tests else "troubleshoot"
            d["reco"] = {"headline": f"Troubleshoot {f.code} on {f.tail_no}: {what}.", "text": f"{f.reason}. {f.basis}."}
        state_txt = "mission capable" if f.aircraft in MC else f"{f.aircraft}"
        since = ist(f.first, "%d %b")
        if part_lru and f.removals:
            seq, _ = _chain(ctx, f.tail_no, iso.parts[part_lru])
            n_ser = len({sn for _, sn in seq})
            st_txt = (f"{NUM.get(n_ser, n_ser).capitalize()} different {part}s in that position since "
                      f"{ist(seq[0][0], '%d %b')}." if seq else f"{f.n_alerts} sorties with {f.code} since {since}.")
        else:
            st_txt = f"{f.n_alerts} sorties with {f.code} since {since}."
        if r.confirmed == 0:
            why_txt = f"No {f.code} job in the fleet confirmed a fault."
            if r.units_benched and r.units_rtok == r.units_benched:
                why_txt += f" All {r.units_benched} {part}s sent to the shop came back RTOK."
            elif r.units_benched:
                why_txt += f" {r.units_rtok} of {r.units_benched} {part}s sent to the shop came back RTOK."
        else:
            why_txt = f"{r.confirmed} of {r.labelled} {f.code} jobs in the fleet confirmed a fault."
        d["facts"] = {
            "state": {"tier": "DESC", "big": str(f.removals if f.removals else f.consec or f.occ_10d),
                      "unit": f"{part} removals" if f.removals else "consecutive flights" if f.consec else "in 10 days",
                      "text": f"{st_txt} The aircraft is {state_txt} today."},
            "why": {"tier": "DIAG", "big": str(r.confirmed), "unit": f"of {r.labelled} confirmed", "text": why_txt},
        }
        if r.p_rtok is not None:
            pr_, pc = r.p_rtok, r.p_confirmed
            d["facts"]["forecast"] = {"tier": "PRED", "big": _pct(pr_[0]), "unit": "% no fault found",
                                      "text": f"if the {part} is removed again. Chance the alarm reflects a real fault: {_pct(pc[0])} %.",
                                      "ci": f"{pr_[0]:.3f} [{pr_[1]:.2f}, {pr_[2]:.2f}] · {r.units_rtok} of {r.units_benched} {part}s RTOK"}
        else:
            pc = r.p_confirmed
            d["facts"]["forecast"] = {"tier": "PRED", "big": _pct(pc[0]), "unit": "% confirmed fault",
                                      "text": f"chance the next job on {f.code} confirms a fault.",
                                      "ci": f"{pc[0]:.3f} [{pc[1]:.3f}, {pc[2]:.3f}] · n = {r.labelled}"}
        wn = []
        if r.p_rtok is not None:
            wn.append({"alt": f"REMOVE_REPLACE {part}", "verdict": "Blocked by evidence" if r.p_rtok[0] > 0.9 else "Weak",
                       "text": f"{_pct(r.p_rtok[0])} % chance the shop finds nothing" +
                               (f". {f.removals} removals have not changed the symptom." if f.removals else ".")})
        if not f.gate:
            wn.append({"alt": "GROUND aircraft", "verdict": "Not justified",
                       "text": "No gate tripped, and the aircraft is " + ("mission capable." if f.aircraft in MC else f"{f.aircraft}.")})
        if f.consec >= prefs()["standing_flights"]:
            wn.append({"alt": "DEFER again", "verdict": "Repeats the loop",
                       "text": f"The alarm is standing. Deferring repeats the last {f.consec} flights."})
            wn.append({"alt": "Filter the code only", "verdict": "Needs a test first",
                       "text": "Hides the alarm without checking the indication path first."})
        d["whynot"] = wn
    elif f.kind == "supply":
        med, p90 = leadtime.predict(ctx, f.part_no, "AOG")
        d["title"] = f.card
        d["standing"] = f"Grounded for {f.down_days:.0f} days"
        d["reco"] = {"headline": f"Expedite demand {f.demand_no}.", "text": f"{f.reason}. {f.basis}."}
        d["facts"] = {
            "state": {"tier": "DESC", "big": f"{f.down_days:.0f}", "unit": "days NMCS", "text": f"Waiting for {f.part_no} on demand {f.demand_no}."},
            "why": {"tier": "DIAG", "big": "AWP", "unit": "awaiting parts", "text": "The job is open and the part has not arrived; no other aircraft can donate one in this release."},
            "forecast": {"tier": "PRED", "big": f"{med}", "unit": "days median lead time",
                         "text": f"for an AOG {f.part_no} demand (90th percentile {p90} d; {leadtime.CAVEAT}).", "ci": f"log-normal AFT · n = {leadtime.fit(ctx).n}"},
        }
        d["whynot"] = [{"alt": "CANNIBALISE", "verdict": "Not available", "text": "Moving parts between aircraft needs the data layer's multi-aircraft release."}]
    elif f.kind == "life":
        d["title"] = f.card
        d["standing"] = f"{f.life_used:g} of {f.life_limit} {f.life_unit}"
        d["reco"] = {"headline": f"Requisition {f.quantity} × {f.part_no}.", "text": f"{f.reason}. {f.basis}."}
        d["facts"] = {
            "state": {"tier": "DESC", "big": f"{f.life_used:g}/{f.life_limit}", "unit": f.life_unit, "text": f"Used since the last change; {f.rate_per_day:g} {f.life_unit}/day over 30 days."},
            "why": {"tier": "DIAG", "big": f"{f.ttf_days:g}" if f.ttf_days is not None else "—", "unit": "days to the limit", "text": f"Margin {f.margin:+.1f} d after lead time, epoch delay and work."},
            "forecast": {"tier": "PRED", "big": f"{f.lead_days}", "unit": "days median lead time", "text": f"for {f.part_no} ({leadtime.CAVEAT}).", "ci": f"log-normal AFT · n = {leadtime.fit(ctx).n}"},
        }
    else:
        d["title"] = f.card
        d["standing"] = f"{len(f.members)} issues · codes {f.code}"
        d["reco"] = {"headline": "Monitor; no order today.", "text": f"{f.reason}. {f.basis}."}
        pc = f.p_true
        d["facts"] = {
            "state": {"tier": "DESC", "big": str(len(f.members)), "unit": "advisory issues", "text": "Recurring in the last 10 days: " + ", ".join(f.members) + "."},
            "why": {"tier": "DIAG", "big": "0", "unit": f"of {f.p_n} confirmed", "text": "These codes almost always close as could-not-duplicate or admin close."},
            "forecast": {"tier": "PRED", "big": _pct(pc[0]), "unit": "% confirmed fault", "text": "pooled over the group's codes.", "ci": f"{pc[0]:.4f} [{pc[1]:.4f}, {pc[2]:.4f}] · n = {f.p_n}"},
        }
    return d


def _chain(ctx: Context, tail: str, part_no: str) -> tuple[list[tuple[int, str]], list[list]]:
    """Serial history of the position under test: start from the first serial removed under the part and follow each
    remove → install. Returns ([(t, serial fitted from t)], [[t, out, in], …])."""
    ev = [e | {"removed": serial(e["removed"]), "installed": serial(e["installed"])}
          for e in ctx.twin.config_events(ctx.t, tail) if e["part_no"] == part_no]
    rem = [e for e in ev if e["removed"]]
    if not rem:
        fitted = [e for e in ev if e["installed"]]
        return ([(fitted[0]["t"], fitted[0]["installed"])] if fitted else []), []
    cur = rem[0]["removed"]
    first = next((e for e in ev if e["installed"] == cur), None)
    seq, swaps = [(first["t"] if first else 0, cur)], []
    for e in ev:
        if e["removed"] and e["removed"] == cur and e["installed"]:
            swaps.append([e["t"], e["removed"], e["installed"]])
            cur = e["installed"]
            seq.append((e["t"], cur))
    return seq, swaps


def _test_order(ctx: Context, f: Facts, iso, test, part_no: str | None) -> dict:
    """The order that carries out a workbench test, with the data layer's parameter schema: TROUBLESHOOT {code} for
    the indication path, TROUBLESHOOT {position} for a check of one suspect, REMOVE_REPLACE {position} for the
    position under test (the slot whose serials the alarm has outlived)."""
    from twinview import registry

    reg = registry()
    if test.kind == "remove_replace" and part_no:
        seq, _ = _chain(ctx, f.tail_no, part_no)
        initial = [e["installed"] for e in ctx.twin.config_events(ctx.t, f.tail_no)
                   if e["part_no"] == part_no and not serial(e["job_no"]) and serial(e["installed"])]
        slot = initial.index(seq[0][1]) + 1 if seq and seq[0][1] in initial else 1
        pos = reg.position(part_no=part_no, slot=slot)
        if pos:
            return {"action": "REMOVE_REPLACE", "parameters": {"position": pos}}
    if test.kind == "check":
        pos = reg.position(lru=test.target)
        if pos:
            return {"action": "TROUBLESHOOT", "parameters": {"position": pos}}
    return {"action": "TROUBLESHOOT", "parameters": {"code": f.code}}


def workbench(store, twin, t: int, issue_id: str) -> dict | None:
    """``PHX_WB`` for an alert issue whose code has suspects: sortie strip, suspects, ranked tests."""
    b = evaluate(store, twin, t)
    f = b.facts.get(issue_id)
    if f is None or f.kind != "alert":
        return None
    ctx = context(store, twin, t)
    iso = isolation.analyse(ctx, f.tail_no, f.code)
    if iso is None:
        return None
    import datetime as dt

    from engines.common import IST

    part_lru = next((h for h, p in iso.parts.items() if p), None)
    part_no = iso.parts.get(part_lru) if part_lru else None
    label = iso.labels.get(part_lru, "unit") if part_lru else "unit"
    so = ctx.sorties(f.tail_no)
    t0d = dt.datetime.fromtimestamp(int(so.t_event.min()) / 1e9, IST).date() if len(so) else None
    t0 = int(dt.datetime(t0d.year, t0d.month, t0d.day, tzinfo=IST).timestamp()) * 10**9 if t0d else ctx.t
    fired = ctx.fired_sorties(f.tail_no, f.code)
    seq, _ = _chain(ctx, f.tail_no, part_no) if part_no else ([], [])

    def serial_at(x):
        s = None
        for ts, sn in seq:
            if ts <= x:
                s = sn
        return s or (seq[0][1] if seq else None)

    sorties = [[round((r.t_event - t0) / DAY, 3), int(r.sortie_id in fired), serial_at(r.t_event), ist(r.t_event, "%d %b")]
               for r in so.itertuples()]
    serials = {x[2] for x in sorties if x[2]}
    order = sorted(iso.posterior, key=lambda h: -iso.posterior[h])
    def why(h):
        if h == "IND":
            return iso.tests[0].test.detail if iso.tests else "reporting channel · sensor · harness"
        k, c = iso.bench.get(h, (0, 0))
        if k + c and iso.hi[h] < 1e-3:
            return f"Ruled out in every assumption tested · {k} of {k + c} removed units RTOK"
        if k + c:
            return f"{k} of {k + c} removed units RTOK"
        return f"No removals on record · prior {iso.iso.get(h, 0):.1f} from the code's suspect list"

    text = {h: why(h) for h in order}
    best = max((x.eig_per_mh for x in iso.tests), default=0.0) or 1.0
    orders = {x.test.id: _test_order(ctx, f, iso, x.test, part_no) for x in iso.tests}
    return {
        "issue_id": f.issue_id, "tail": f.tail_no, "code": f.code, "title": f.card,
        "sub": f"Workbench · is it the {label}, and what should we test next?",
        "manual": iso.tests[0].test.proc if iso.tests else None, "t0": ist(t0, "%Y-%m-%d"),
        "sorties": sorties, "removals": [[round((e["t"] - t0) / DAY, 3), e["removed"], e["installed"]]
                                         for e in (ctx.removal_events(f.tail_no, part_no) if part_no else [])],
        "strip": {"title": (f"The alarm follows the aircraft, not the {label}" if len({x[2] for x in sorties if x[1]}) > 1
                            else f"{f.code} on {f.tail_no}, sortie by sortie"),
                  "ci": f"{f.code} fired on {sum(x[1] for x in sorties)} of {len(sorties)} sorties",
                  "note": f"Each band is one {label} serial · {len(serials)} serials" if part_no else "No removable part under this code"},
        "suspects": [{"id": h, "name": iso.labels[h][:1].upper() + iso.labels[h][1:], "text": text[h], "p": round(iso.posterior[h], 6)}
                     for h in order],
        "suspects_note": f"Central assumptions · {iso.settings} assumption settings swept",
        "source": "Simulated fleet",
        "tests": [{"test_id": x.test.id, "name": x.test.name, "text": f"{x.test.detail} · {x.test.proc or '-'}", "man_h": x.test.mh,
                   "value": round(x.eig_per_mh / best, 2), "robust": f"best in {x.best_in} of {iso.settings}" if x.eig > 0 else "tells us nothing new",
                   "order": orders[x.test.id]}
                  for x in iso.tests],
    }


def readiness_cards(store, twin, t: int) -> dict[str, dict]:
    """``PHX_DATA.fleet[].card`` per tail (``twinview.readiness_cards``)."""
    from twinview import readiness_cards as cards

    return cards(store, twin, t)


def twin_view(store, twin, t: int, tail: str) -> dict | None:
    """Optional ``PHX_TWIN`` fields with model output (``twinview.twin_view``)."""
    from twinview import twin_view as view

    return view(store, twin, t, tail)
