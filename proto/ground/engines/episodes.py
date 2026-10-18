"""Alerts → occurrences → issues (architecture 07, D1–D4 and D6).

- D1 records are already deduplicated by the store per (tail, record id), earliest ingest.
- D2 BIT and caution rows sharing an ``event_id`` are one occurrence (``common.Context.occ``).
- D3 occurrences of the same code on the same sortie count once.
- D4 occurrences of the same (tail, code) whose ingest times are less than 10 days apart form one issue; a gap of
  10 days or more starts a new issue. An issue is open while its latest occurrence is younger than 10 days at t.
- D6 an ADVISORY occurrence on a sortie where a power-supply code (ELE-405, ENG-401) fired on the same tail is
  inhibited; an issue whose occurrences in its last 10 days are all inhibited is SUPPRESSED_BY_DESIGN (flagged,
  still counted).

``run(store, twin, t) -> list[Finding]``: one DESC finding per open issue and one for the alert funnel.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from interfaces import DAY, Finding, Tier

from engines.common import (
    PARAMS,
    POWER_CODES,
    SEV_RANK,
    Context,
    belief,
    context,
    finding,
    ist,
    rid_bytes,
    seq,
    text,
)

P = PARAMS["episodes"]
WINDOW = P["window_days"] * DAY
OPEN = P["open_days"] * DAY


@dataclass(frozen=True)
class Episode:
    issue_id: str  # f"{tail}-{code}" for the open issue; earlier issues of the pair get "@<first IST date>"
    tail_no: str
    code: str
    severity: str  # WARNING if any occurrence was a WARNING, else the first occurrence's severity
    fault_list: str
    source_lru: str
    description: str
    suspects: tuple[tuple[str, float], ...]  # (LRU, isolation confidence) of the latest occurrence
    first: int  # ingest time of the first occurrence
    last: int  # ingest time of the latest occurrence
    last_occurrence: int  # event time of the latest occurrence
    n: int  # sorties with the code in the issue (D3)
    rids: tuple[str, ...]  # primary record ids (hex) of every occurrence, oldest first
    open: bool
    inhibited: bool  # D6: every occurrence in the last 10 days fell on a power-code sortie


def _suspects(s) -> tuple[tuple[str, float], ...]:
    return tuple((str(x["lru"]), float(x["isolation_confidence"])) for x in seq(s))


def _inhibited(ctx: Context) -> set[tuple[str, str]]:
    """(tail, primary rid) of occurrences muted by a power-supply code on the same sortie (D6)."""
    o = ctx.occ
    power = set(zip(o[o.event_code.isin(POWER_CODES)].tail_no, o[o.event_code.isin(POWER_CODES)].sortie_id, strict=True))
    dep = o[~o.event_code.isin(POWER_CODES) & o.severity.isin(P["inhibited_severities"])]
    return {(t, r) for t, s, r in zip(dep.tail_no, dep.sortie_id, dep.rid, strict=True) if (t, s) in power}


def episodes(ctx: Context) -> list[Episode]:
    """Every issue (open and closed) as of ``ctx.t``, ordered by tail, code, first ingest."""
    if "episodes" in ctx._memo:
        return ctx._memo["episodes"]
    muted = _inhibited(ctx)
    out: list[Episode] = []
    for (tail, code), g in ctx.occ.groupby(["tail_no", "event_code"], sort=True):
        g = g.sort_values(["t_ingest", "event_id"], kind="mergesort")
        heads = g.drop_duplicates("sortie_id")  # D3: the first occurrence per sortie carries the chain
        chains: list[list] = []
        chain_of: dict = {}
        for r in heads.itertuples():
            if not chains or r.t_ingest - chains[-1][-1].t_ingest >= WINDOW:
                chains.append([])
            chains[-1].append(r)
            chain_of[r.sortie_id] = len(chains) - 1
        members: list[list] = [[] for _ in chains]
        for r in g.itertuples():
            members[chain_of[r.sortie_id]].append(r)
        for i, ch in enumerate(chains):
            first, last = ch[0], ch[-1]
            ch = members[i]
            sev = max((x.severity for x in ch), key=lambda s: SEV_RANK.get(s, 0))
            sev = "WARNING" if sev == "WARNING" else first.severity
            is_open = ctx.t - last.t_ingest < OPEN
            t_last_occ = max(x.t_occurrence for x in ch)
            recent = [x for x in ch if x.t_occurrence >= t_last_occ - WINDOW]
            iid = f"{tail}-{code}" if i == len(chains) - 1 else f"{tail}-{code}@{ist(first.t_ingest, '%Y%m%d')}"
            out.append(Episode(
                issue_id=iid, tail_no=tail, code=code, severity=sev, fault_list=text(first.fault_list),
                source_lru=text(first.source_lru), description=text(first.description),
                suspects=_suspects(last.suspect_lrus), first=int(first.t_ingest), last=int(last.t_ingest),
                last_occurrence=int(t_last_occ), n=len({x.sortie_id for x in ch}),
                rids=tuple(x.rid for x in ch), open=bool(is_open),
                inhibited=bool(recent) and all((tail, x.rid) in muted for x in recent),
            ))
    ctx._memo["episodes"] = out
    return out


def open_episodes(ctx: Context) -> list[Episode]:
    return [e for e in episodes(ctx) if e.open]


def recent_occurrences(ctx: Context, ep: Episode) -> pd.DataFrame:
    """Occurrences of the issue in the 10 days up to its latest occurrence (the recurrence window that policies
    read as ``occ_10d`` and that orders cite as evidence), oldest first."""
    o = ctx.occ
    g = o[(o.tail_no == ep.tail_no) & (o.event_code == ep.code) & o.rid.isin(ep.rids)]
    g = g[g.t_occurrence >= ep.last_occurrence - WINDOW]
    return g.sort_values(["t_ingest", "event_id"], kind="mergesort")


def funnel(ctx: Context) -> dict[str, int]:
    eps = episodes(ctx)
    return {"alert_rows": int(len(ctx.bit) + len(ctx.cautions)), "bit_rows": len(ctx.bit),
            "caution_rows": len(ctx.cautions), "occurrences": len(ctx.occ), "issues": len(eps),
            "open": sum(e.open for e in eps), "suppressed": sum(e.open and e.inhibited for e in eps)}


def issue_finding(ctx: Context, ep: Episode) -> Finding:
    rec = recent_occurrences(ctx, ep)
    occ10 = int(rec.sortie_id.nunique())
    cons = ctx.consecutive(ep.tail_no, ep.code)
    flown = len(ctx.sorties(ep.tail_no))
    fired = len(ctx.fired_sorties(ep.tail_no, ep.code) & set(ctx.sorties(ep.tail_no).sortie_id))
    tail_txt = f"; fired on the last {cons} flights" if cons >= 2 else ("; fired on the last flight" if cons == 1 else "")
    reason = (f"{ep.code} ({ep.description}) on {ep.tail_no}: {ep.n} sorties since {ist(ep.first, '%d %b')}, "
              f"{occ10} in the 10 days to {ist(ep.last_occurrence, '%d %b')}{tail_txt}.")
    if ep.inhibited:
        reason += " Every recent occurrence fell on a power-supply fault sortie (inhibited)."
    return finding("episodes", Tier.DESC, ep.tail_no, ep.issue_id, [
        belief("episodes", "n_alerts", ep.n),
        belief("episodes", "occ_10d", occ10),
        belief("episodes", "consecutive_flights", cons),
        belief("episodes", "sorties_fired", fired, n=flown, note=f"{fired} of {flown} sorties"),
    ], rid_bytes(rec.rid), reason)


def run(store, twin, t: int) -> list[Finding]:
    """One DESC finding per open issue (evidence = its occurrences in the last 10 days) and one for the funnel."""
    ctx = context(store, twin, t)
    out = [issue_finding(ctx, ep) for ep in open_episodes(ctx)]
    f = funnel(ctx)
    out.append(finding("episodes", Tier.DESC, None, "funnel", [belief("episodes", k, v) for k, v in f.items()], [],
                       f"{f['alert_rows']:,} alert rows → {f['occurrences']:,} occurrences → {f['issues']} issues, "
                       f"{f['open']} open as of {ist(t)} IST."))
    return out
