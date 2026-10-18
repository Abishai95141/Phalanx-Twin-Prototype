"""Similar past cases (architecture 09): a NetworkX graph of issues, codes, suspect LRUs, removed parts and job
outcomes; the nearest cases to an open issue are the issues sharing the most weighted neighbours (same code, same
suspect LRUs, same part removed, same outcome path), ties broken by larger history, recency and id.

Jobs belong to an issue when they cite one of its occurrences as evidence.

``run(store, twin, t) -> list[Finding]``: one DIAG finding per open issue with the top cases and their outcomes.
``cases(ctx, issue_id)`` returns the ranked case summaries for the screens.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np
from interfaces import Finding, Tier

from engines.common import (
    PARAMS,
    Context,
    belief,
    context,
    finding,
    ist,
    num,
    rid_bytes,
)
from engines.episodes import Episode, episodes, open_episodes

P = PARAMS["similar"]
W = P["weights"]


@dataclass(frozen=True)
class Case:
    issue_id: str
    tail_no: str
    code: str
    first: int
    last: int
    n_alerts: int
    open: bool
    jobs: int
    no_fault: int
    removals: int
    rtok_units: int
    confirmed_units: int
    man_hours: float
    score: float
    shared: tuple[str, ...]


def _issue_jobs(ctx: Context) -> dict[str, list]:
    """issue id → rows of ctx.jobs citing any of its occurrences."""
    if "similar_jobs" in ctx._memo:
        return ctx._memo["similar_jobs"]
    prim = {}
    for r in ctx.occ.itertuples():
        for x in r.rids:
            prim[(r.tail_no, x)] = r.rid
    ep_of = {(e.tail_no, rid): e.issue_id for e in episodes(ctx) for rid in e.rids}
    out: dict[str, list] = {}
    for j in ctx.jobs.itertuples():
        hit = {ep_of.get((j.tail_no, prim.get((j.tail_no, x)))) for x in j.evidence}
        for iid in hit - {None}:
            out.setdefault(iid, []).append(j)
    ctx._memo["similar_jobs"] = out
    return out


def graph(ctx: Context) -> nx.Graph:
    if "similar_graph" in ctx._memo:
        return ctx._memo["similar_graph"]
    from engines.cnd import outcomes

    oc = outcomes(ctx)
    outcome_of = {(t, j, c): o for t, j, c, o in zip(oc.tail_no, oc.job_no, oc.code, oc.outcome, strict=True)}
    G = nx.Graph()
    jobs = _issue_jobs(ctx)
    for e in episodes(ctx):
        n = ("issue", e.issue_id)
        G.add_node(n, ep=e)
        G.add_edge(n, ("code", e.code), weight=W["code"])
        for lru, _ in e.suspects:
            G.add_edge(n, ("lru", lru), weight=W["lru"])
        for j in jobs.get(e.issue_id, []):
            if j.action_taken_code == "AT-RR" and isinstance(j.part_no, str):
                G.add_edge(n, ("part", j.part_no), weight=W["part"])
            o = outcome_of.get((j.tail_no, j.job_no, e.code))
            if o and o != "OPEN":
                G.add_edge(n, ("outcome", o), weight=W["outcome"])
    ctx._memo["similar_graph"] = G
    return G


def _summary(ctx: Context, e: Episode, score: float, shared) -> Case:
    from engines.cnd import outcomes

    oc = outcomes(ctx)
    js = _issue_jobs(ctx).get(e.issue_id, [])
    keys = {(j.tail_no, j.job_no) for j in js}
    o = oc[(oc.code == e.code).to_numpy() & np.array([(a, b) in keys for a, b in zip(oc.tail_no, oc.job_no, strict=True)], dtype=bool)]
    return Case(e.issue_id, e.tail_no, e.code, e.first, e.last, e.n, e.open, len(js),
                int((o.outcome == "NO_FAULT").sum()), int((o.action == "AT-RR").sum()), int(o.rtok_units.sum()),
                int(o.confirmed_units.sum()), round(float(sum(num(j.man_hours) for j in js)), 1), round(score, 3),
                tuple(sorted(f"{k}:{v}" for k, v in shared)))


def cases(ctx: Context, issue_id: str, top: int | None = None) -> list[Case]:
    G = graph(ctx)
    a = ("issue", issue_id)
    if a not in G:
        return []
    scored = []
    for b in G.nodes:
        if b[0] != "issue" or b == a:
            continue
        shared = list(nx.common_neighbors(G, a, b))
        if not shared:
            continue
        s = sum(min(G[a][x]["weight"], G[b][x]["weight"]) for x in shared)
        scored.append((s, G.nodes[b]["ep"], shared))
    scored.sort(key=lambda x: (-x[0], -x[1].n, -x[1].last, x[1].issue_id))
    return [_summary(ctx, e, s, sh) for s, e, sh in scored[: top or P["top"]]]


def findings(ctx: Context, ep: Episode) -> list[Finding]:
    cs = cases(ctx, ep.issue_id)
    if not cs:
        return []
    c = cs[0]
    reason = (f"Closest past case: {c.tail_no} {c.code} ({ist(c.first, '%d %b')} – {ist(c.last, '%d %b')}, {c.n_alerts} sorties, "
              f"{c.jobs} jobs: {c.no_fault} no fault found, {c.removals} removals, {c.rtok_units} units RTOK, "
              f"{c.confirmed_units} confirmed).")
    # record ids are scoped by tail: cite the case's jobs only when it is on the same aircraft
    ev = [j.rid for j in _issue_jobs(ctx).get(c.issue_id, [])][-10:] if c.tail_no == ep.tail_no else []
    return [finding("similar", Tier.DIAG, ep.tail_no, ep.issue_id, [
        belief("similar", x.issue_id, x.score, n=x.n_alerts,
               note=f"{x.jobs} jobs · {x.no_fault} no fault · {x.removals} removals · {x.rtok_units} RTOK · "
                    f"{x.confirmed_units} confirmed · {x.man_hours} man-h")
        for x in cs
    ], rid_bytes(ev), reason)]


def run(store, twin, t: int) -> list[Finding]:
    ctx = context(store, twin, t)
    return [f for ep in open_episodes(ctx) for f in findings(ctx, ep)]
