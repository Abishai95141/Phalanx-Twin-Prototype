"""Life left of usage-limited items (tyres in landings, brake chutes in streamings).

- Limit: read from the station's hard-time job text for the part ("… DUE TO HI-TIME (8 LDG).",
  "(45 STREAMINGS)"), most common value in the fleet's jobs.
- Used: usage since the latest install of the part on the tail — landings from SORTIE records for tyres, the
  ``USAGE.CHUTE_STREAMINGS`` counter increments for chutes.
- Rate: usage per day over the last 30 days; days to limit = left / rate.

``run(store, twin, t) -> list[Finding]``: one PRED finding per (tail, item). ``items(ctx)`` returns the
``LifeItem`` list for triage (an item is at its limit when the next use reaches it).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from interfaces import DAY, Finding, Tier

from engines.common import (
    PARAMS,
    Context,
    belief,
    context,
    finding,
    ist,
    num,
    rid_bytes,
    serial,
    text,
)

P = PARAMS["life"]


@dataclass(frozen=True)
class LifeItem:
    tail_no: str
    part_no: str
    label: str
    unit: str
    limit: int
    used: float
    left: float
    rate_per_day: float
    days_to_limit: float | None
    t_limit: int | None
    fitted: int  # serials of the part fitted on the tail
    installed_at: int | None
    evidence: tuple[str, ...]  # install record + the sorties counted (hex)
    overrun: int = 0  # uses past the limit the station's own hard-time changes reach (95th percentile, fleet history)
    overrun_n: int = 0  # hard-time changes behind that percentile


def limit_of(ctx: Context, part_no: str) -> int | None:
    word = P["items"][part_no]["text"]
    rx = re.compile(rf"HI-TIME \((\d+) {word}\)")
    j = ctx.jobs[ctx.jobs.part_no == part_no]
    vals = Counter(int(m.group(1)) for txt in j.discrepancy_text.fillna("") for m in [rx.search(txt)] if m)
    return vals.most_common(1)[0][0] if vals else None


def station_overrun(ctx: Context, part_no: str) -> tuple[int, int]:
    """How far past the limit the station itself goes before its hard-time change: the 95th percentile of the uses
    counted at each closed HI-TIME job of the part (since the tail's previous change of that part) minus the limit,
    over the fleet's history; (0, n) under 10 changes. In these worlds tyres are changed between 8 and 14 landings."""
    key = ("life_overrun", part_no)
    if key in ctx._memo:
        return ctx._memo[key]
    lim = limit_of(ctx, part_no)
    over: list[float] = []
    for tail in ctx.tails:
        changes = sorted({x["t"] for x in _installs(ctx, tail, part_no)})
        j = ctx.jobs[(ctx.jobs.tail_no == tail) & (ctx.jobs.part_no == part_no) & (ctx.jobs.status == "CLOSED")
                     & ctx.jobs.discrepancy_text.map(lambda x: "HI-TIME" in text(x))]
        for r in j.itertuples():
            prev = max([x for x in changes if x < r.first_ingest - DAY // 24] or [None], key=lambda x: x or 0)
            used = _used_between(ctx, tail, part_no, prev, int(num(r.t_close, ctx.t)))
            over.append(max(used - lim, 0.0))
    res = (math.ceil(float(np.quantile(over, 0.95))), len(over)) if len(over) >= 10 else (0, len(over))
    ctx._memo[key] = res
    return res


def _used_between(ctx: Context, tail: str, part_no: str, t0: int | None, t1: int) -> float:
    spec = P["items"][part_no]
    so = ctx.sorties(tail)
    so = so[(so.t_event <= t1) & ((so.t_event > t0) if t0 is not None else True)]
    if spec["unit"] == "landings":
        return float(so.landings.fillna(0).sum())
    u = ctx.store.df(ctx.t, "usage.counters", tail_no=tail)
    u = u[(u.param_id == spec["counter"]) & u.sortie_id.isin(set(so.sortie_id))] if len(u) else u
    return float(u.increment_eu.fillna(0).sum()) if len(u) else 0.0


def _usage(ctx: Context, tail: str, part_no: str, since: int | None) -> tuple[float, float, list[str]]:
    """(used since install, used in the last 30 days, sortie record ids counted)."""
    spec = P["items"][part_no]
    so = ctx.sorties(tail)
    after = so if since is None else so[so.t_event > since]
    w0 = ctx.t - P["window_days"] * DAY
    if spec["unit"] == "landings":
        return float(after.landings.fillna(0).sum()), float(so[so.t_event > w0].landings.fillna(0).sum()), list(after.rid)
    u = ctx.store.df(ctx.t, "usage.counters", tail_no=tail)
    u = u[u.param_id == spec["counter"]] if len(u) else u
    if not len(u):
        return 0.0, 0.0, []
    st = dict(zip(so.sortie_id, so.t_event, strict=True))
    u = u.assign(t=u.sortie_id.map(st))
    used = u[u.t > since] if since is not None else u
    return (float(used.increment_eu.fillna(0).sum()), float(u[u.t > w0].increment_eu.fillna(0).sum()),
            list(after.rid))


def _installs(ctx: Context, tail: str, part_no: str) -> list[dict]:
    """Installs of the part on the tail, oldest first, from the twin's configuration events (job text plus
    COMPONENT_LIFE records: job text is complete, install records can be missing or late), each with the record
    that shows it (the INSTALL record, or the job that states it)."""
    ev = [e for e in ctx.twin.config_events(ctx.t, tail) if e["part_no"] == part_no and serial(e["installed"])]
    cl = ctx.maint_all
    inst = cl[(cl.record_type == "COMPONENT_LIFE") & (cl.install_action == "INSTALL") & (cl.tail_no == tail) &
              (cl.part_no == part_no)].sort_values(["t_event", "record_version"], kind="mergesort")
    rec = {s: (int(t), r) for s, t, r in zip(inst.serial_no, inst.t_event, inst.rid, strict=True)}
    jobs = dict(zip(ctx.jobs[ctx.jobs.tail_no == tail].job_no, ctx.jobs[ctx.jobs.tail_no == tail].rid, strict=True))
    out = []
    for e in ev:
        t_rec, rid = rec.get(e["installed"], (None, None))
        out.append({"serial": e["installed"], "t": max(int(e["t"]), t_rec or 0), "rid": rid or jobs.get(e["job_no"]),
                    "removed_later": False})
    for i, a in enumerate(out):
        a["removed_later"] = any(serial(e["removed"]) == a["serial"] and e["t"] >= a["t"] for e in ev[i + 1:])
    return sorted(out, key=lambda x: x["t"])


def items(ctx: Context) -> list[LifeItem]:
    """Per tail and part: usage since the latest change of the part (the serials installed within a day of it, e.g.
    a tyre pair), the film's and the twin's definition. Per-serial tracking is not used: the data layer's corrupted
    serial records leave removals unmatched, which would show stale serials far past their limit. Known limit: when
    only some positions were changed last, the older positions' usage is not seen (follow-up for the twin)."""
    if "life" in ctx._memo:
        return ctx._memo["life"]
    out = []
    for part_no, spec in P["items"].items():
        lim = limit_of(ctx, part_no)
        if lim is None:
            continue
        for tail in ctx.tails:
            ins = _installs(ctx, tail, part_no)
            group = [x for x in ins if ins and x["t"] >= ins[-1]["t"] - DAY]
            since = ins[-1]["t"] if ins else None
            used, w, sids = _usage(ctx, tail, part_no, since)
            rate = w / P["window_days"]
            left = lim - used
            dtl = round(left / rate, 2) if rate > 0 else None
            rid = ins[-1]["rid"] if ins else None
            ov, ov_n = station_overrun(ctx, part_no)
            out.append(LifeItem(tail, part_no, spec["label"], spec["unit"], lim, used, left, round(rate, 3), dtl,
                                None if dtl is None else int(ctx.t + max(dtl, 0) * DAY),
                                len({x["serial"] for x in group}), since, tuple(([rid] if rid else []) + sids), ov, ov_n))
    ctx._memo["life"] = out
    return out


def run(store, twin, t: int) -> list[Finding]:
    ctx = context(store, twin, t)
    out = []
    for it in items(ctx):
        when = (f"{-it.left:g} past the limit; the station's own hard-time changes go up to {it.overrun} past it "
                f"(95 % of {it.overrun_n})" if it.left < 0 else
                f"limit in about {it.days_to_limit:g} days ({ist(it.t_limit, '%d %b')})" if it.days_to_limit is not None
                else "no use in the last 30 days")
        out.append(finding("life", Tier.PRED, it.tail_no, f"{it.tail_no}:{it.part_no}", [
            belief("life", "used", it.used, n=it.limit, note=it.unit), belief("life", "limit", it.limit, note=it.unit),
            belief("life", "left", it.left, note=it.unit), belief("life", "rate_per_day", it.rate_per_day, note=f"{it.unit}/day, 30 d"),
            belief("life", "days_to_limit", it.days_to_limit),
            belief("life", "station_overrun", it.overrun, n=it.overrun_n, note="95th percentile of uses past the limit at the station's hard-time changes"),
        ], rid_bytes(it.evidence), f"{it.tail_no} {it.label}: {it.used:g} of {it.limit} {it.unit} used, {it.left:g} left at "
                                    f"{it.rate_per_day:g} {it.unit}/day → {when}."))
    return out
