"""Spares lead time (port of the film's assurance run): Kaplan-Meier over supply demands, with genuinely open
demands right-censored at t, and a log-normal accelerated-failure-time model (lifelines) with AOG priority and
part class as covariates.

Demands: SUPPLY_DEMAND records ingested by t, latest version per (tail, demand). Most demands carry no tail
(base-level stock demands); their record ids collide across the preview's eight worlds, so they are merged by id
and demand number as the film did — a caveat shown with every lead-time value. An open demand whose job is
already closed has no recorded fulfilment and is left out (counted as ``orphan``).

``run(store, twin, t) -> list[Finding]``: one PRED finding for the fleet (closed-demand median and p90, KM median
and p90) and one per (part, priority) with the AFT median and p90. ``predict(ctx, part_no, priority)`` → (median,
p90) days for triage.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from interfaces import DAY, Finding, Tier

from engines.common import Context, belief, context, finding, rid_bytes

CAVEAT = "most demands carry no tail; base-level demands are merged across the preview's worlds"


@dataclass(frozen=True)
class LeadTime:
    n: int
    closed: int
    censored: int
    orphan: int
    closed_median: float | None
    closed_p90: float | None
    km_median: float | None
    km_p90: float | None
    parts: tuple[str, ...]  # covariate part classes (reference = the most frequent)
    aft: object | None  # fitted lifelines LogNormalAFTFitter
    frame: pd.DataFrame


def demands(ctx: Context) -> pd.DataFrame:
    m = ctx.maint_all
    d = m[m.record_type == "SUPPLY_DEMAND"].copy()
    d["_tail"] = d.tail_no.fillna("")
    d = d.sort_values("t_ingest", kind="mergesort").drop_duplicates(["_tail", "rid"])
    d = d.sort_values(["record_version", "t_ingest"], kind="mergesort").drop_duplicates(["_tail", "record_key"], keep="last")
    return d


def fit(ctx: Context) -> LeadTime:
    if "leadtime" in ctx._memo:
        return ctx._memo["leadtime"]
    from lifelines import KaplanMeierFitter, LogNormalAFTFitter

    d = demands(ctx)
    m = ctx.maint_all
    jobs = m[m.record_type.isin(["DEFECT_WO", "INSPECTION"]) & m.tail_no.notna()]
    jobs = jobs.sort_values(["record_version", "t_ingest"], kind="mergesort").drop_duplicates(["tail_no", "record_key"], keep="last")
    jst = {(t, j): s for t, j, s in zip(jobs.tail_no, jobs.job_no, jobs.status, strict=True)}
    d["job_status"] = [jst.get((t, j), "NOJOB") for t, j in zip(d.tail_no, d.job_no, strict=True)]
    closed = d[d.status == "CLOSED"].copy()
    closed["T"], closed["E"] = (closed.t_close - closed.t_open) / DAY, 1
    gopen = d[(d.status != "CLOSED") & (d.job_status != "CLOSED")].copy()
    gopen["T"], gopen["E"] = (ctx.t - gopen.t_open) / DAY, 0
    orphan = int(((d.status != "CLOSED") & (d.job_status == "CLOSED")).sum())
    S = pd.concat([closed, gopen])
    S = S[S["T"].notna()].copy()
    S["part"] = S.part_no.fillna("UNKNOWN")
    S["aog"] = (S.priority == "AOG").astype(float)
    if not len(S):
        res = LeadTime(0, 0, 0, orphan, None, None, None, None, (), None, S)
        ctx._memo["leadtime"] = res
        return res
    km = KaplanMeierFitter().fit(S["T"], S["E"])

    def q(p):
        with warnings.catch_warnings():  # lifelines interpolates the step function; the step value is what we want
            warnings.simplefilter("ignore")
            v = float(km.percentile(p))
        return round(v, 1) if np.isfinite(v) else None

    cnt = S.groupby("part").E.sum().sort_values(ascending=False)
    ref = cnt.index[0]
    parts = tuple(p for p, n in cnt.items() if p != ref and n >= 3)
    X = S[["T", "E", "aog"]].copy()
    X["T"] = X["T"].clip(lower=0.01)
    for p in parts:
        X[p] = (S.part == p).astype(float)
    aft = LogNormalAFTFitter().fit(X, "T", "E") if S.E.sum() >= 10 else None
    ct = closed["T"]
    res = LeadTime(len(S), int(S.E.sum()), int((S.E == 0).sum()), orphan,
                   round(float(ct.median()), 1) if len(ct) else None,
                   round(float(ct.quantile(0.9)), 1) if len(ct) else None,
                   q(0.5), q(0.1), (ref,) + parts, aft, S)
    ctx._memo["leadtime"] = res
    return res


def predict(ctx: Context, part_no: str, priority: str = "AOG") -> tuple[float | None, float | None]:
    """AFT median and 90th-percentile lead time (days) for a part class and priority."""
    lt = fit(ctx)
    if lt.aft is None:
        return lt.closed_median, lt.closed_p90
    row = {"aog": float(priority == "AOG")} | {p: float(part_no == p) for p in lt.parts[1:]}
    df = pd.DataFrame([row])
    return (round(float(lt.aft.predict_median(df).iloc[0]), 1),
            round(float(lt.aft.predict_percentile(df, p=0.1).iloc[0]), 1))


def run(store, twin, t: int) -> list[Finding]:
    ctx = context(store, twin, t)
    lt = fit(ctx)
    ev = rid_bytes(lt.frame[lt.frame.tail_no.notna()].rid) if len(lt.frame) else []
    out = [finding("leadtime", Tier.PRED, None, "leadtime:fleet", [
        belief("leadtime", "closed_median_d", lt.closed_median, n=lt.closed, note=CAVEAT),
        belief("leadtime", "closed_p90_d", lt.closed_p90, n=lt.closed, note=CAVEAT),
        belief("leadtime", "km_median_d", lt.km_median, n=lt.n, note=f"{lt.censored} open demands censored at t"),
        belief("leadtime", "km_p90_d", lt.km_p90, n=lt.n, note="None = not reached within the observed times"),
    ], ev, f"Closed demands (n {lt.closed}): median {lt.closed_median} d, p90 {lt.closed_p90} d; with {lt.censored} open "
           f"demands censored, Kaplan-Meier median {lt.km_median} d ({CAVEAT}).")]
    if lt.aft is not None:
        for part in lt.parts:
            for prio in ("AOG", "MCM"):
                med, p90 = predict(ctx, part, prio)
                n = int(((lt.frame.part == part) & ((lt.frame.priority == prio))).sum())
                out.append(finding("leadtime", Tier.PRED, None, f"leadtime:{part}:{prio}", [
                    belief("leadtime", "median_d", med, n=n), belief("leadtime", "p90_d", p90, n=n),
                ], [], f"{part} ({prio}): log-normal lead time median {med} d, 90th percentile {p90} d (n {n})."))
    return out
