"""Drift in alert rates: weekly BIT occurrences per flight hour (fleet, and per code with enough events), a Poisson
generalised-likelihood-ratio scan for one rate change with a parametric-bootstrap p-value (port of the film's
assurance run), and a check against known change points — a change within ±1 week of an engine wash
(WASH_SERVICE order), an install of the code's suspect part, or a dictionary release is explained, not drift.

``run(store, twin, t) -> list[Finding]``: one PRED finding for the fleet series and one per code scanned; a
finding is a drift alert (belief ``drift_alert`` = 1) only when p < alpha and the change is not explained.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd
from interfaces import DAY, NS, Finding, Tier

from engines.common import IST, PARAMS, Context, belief, context, finding, ist, seq

P = PARAMS["drift"]
WEEK = P["week_days"] * DAY


@dataclass(frozen=True)
class Scan:
    series: str
    weeks: int
    events: int
    glr: float
    split_week: int | None
    split_start: int | None
    rate_before: float | None
    rate_after: float | None
    p_value: float | None
    explained_by: str | None
    alert: bool


def glr_all(n: np.ndarray, e: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """GLR statistic and best split for each row of ``n`` (counts, B × W) against exposure ``e`` (W)."""
    n = np.atleast_2d(n).astype(float)
    W = n.shape[1]
    N, E = n.sum(1), e.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        l0 = np.where(N > 0, N * np.log(N / E) - N, 0.0)
        ks = np.arange(2, W - 2)
        ca, ce = np.cumsum(n, 1), np.cumsum(e)
        a, ea = ca[:, ks - 1], ce[ks - 1]
        b, eb = N[:, None] - a, E - ea
        la = np.where(a > 0, a * np.log(a / ea) - a, 0.0)
        lb = np.where(b > 0, b * np.log(b / eb) - b, 0.0)
        g = la + lb - l0[:, None]
    g = np.nan_to_num(g, nan=-np.inf)
    i = g.argmax(1)
    return g[np.arange(len(g)), i], ks[i]


def _week0(ctx: Context) -> int:
    """IST midnight of the day the fleet worlds start (the season the film counts its 168 days and 24 weeks from)."""
    from twin import WORLD_START

    d = dt.datetime.fromtimestamp(WORLD_START / NS, IST).date()
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=IST).timestamp()) * NS


def _known(ctx: Context) -> dict[str, list[tuple[int, str]]]:
    """Known change points: washes (all series), installs per part, dictionary releases."""
    out: dict[str, list[tuple[int, str]]] = {"*": []}
    oc = ctx.store.df(ctx.t, "orders.commands")
    if len(oc):
        for r in oc[oc.action == "WASH_SERVICE"].itertuples():
            out["*"].append((int(r.t_issued), f"wash {r.target_tail_no}"))
    cl = ctx.maint_all
    cl = cl[(cl.record_type == "COMPONENT_LIFE") & (cl.install_action == "INSTALL") & cl.tail_no.notna()]
    for r in cl.itertuples():
        out.setdefault(str(r.part_no), []).append((int(r.t_event), f"{r.part_no} install {r.tail_no}"))
    ev = pd.concat([ctx.bit, ctx.cautions])
    if "dict_version" in ev and ev.dict_version.nunique() > 1:
        for v, g in ev.groupby("dict_version"):
            out["*"].append((int(g.t_ingest.min()), f"dictionary {v}"))
    return out


def scan(ctx: Context, name: str, counts: np.ndarray, fh: np.ndarray, w0: int, parts: tuple[str, ...]) -> Scan:
    W = len(counts)
    if counts.sum() < P["min_events"] or W < 6 or fh.sum() <= 0:
        return Scan(name, W, int(counts.sum()), 0.0, None, None, None, None, None, None, False)
    stat, k = glr_all(counts, fh)
    stat, k = float(stat[0]), int(k[0])
    rng = np.random.default_rng(int(P["seed"]))
    lam = counts.sum() / fh.sum()
    boot = rng.poisson(lam * fh, size=(int(P["bootstrap"]), W))
    bs, _ = glr_all(boot, fh)
    p = float((bs >= stat).mean())
    t_split = w0 + k * WEEK
    win = P["known_window_weeks"] * WEEK
    known = _known(ctx)
    cands = known["*"] + [x for pn in parts for x in known.get(pn, [])]
    why = next((lbl for t, lbl in sorted(cands) if abs(t - t_split) <= win), None)
    return Scan(name, W, int(counts.sum()), round(stat, 2), k, t_split,
                round(float(counts[:k].sum() / fh[:k].sum()), 3) if fh[:k].sum() else None,
                round(float(counts[k:].sum() / fh[k:].sum()), 3) if fh[k:].sum() else None,
                round(p, 3), why, bool(p < P["alpha"] and why is None))


def scans(ctx: Context) -> list[Scan]:
    if "drift" in ctx._memo:
        return ctx._memo["drift"]
    w0 = _week0(ctx)
    W = int((ctx.t - w0) // WEEK)
    so = pd.concat([ctx.sorties(t) for t in ctx.tails])
    fh = np.bincount(((so.t_event - w0) // WEEK).astype(int).clip(0, W), weights=so.flight_hours.fillna(0), minlength=W + 1)[:W]
    b = ctx.bit
    wk = ((b.t_occurrence - w0) // WEEK).astype(int)
    keep = (wk >= 0) & (wk < W)
    out = [scan(ctx, "fleet", np.bincount(wk[keep], minlength=W), fh, w0, ())]
    sus = {c: tuple(f"SYN-PN-{s['lru']}" for s in seq(g.suspect_lrus.iloc[-1]))
           for c, g in b.groupby("event_code")}
    sus = {c: tuple(PARAMS["isolation"]["lru_parts"].get(p[7:], p) for p in v) for c, v in sus.items()}
    for code, g in b[keep].groupby("event_code"):
        if len(g) >= P["min_events"]:
            out.append(scan(ctx, code, np.bincount(wk[keep][b[keep].event_code == code], minlength=W), fh, w0, sus.get(code, ())))
    ctx._memo["drift"] = out
    return out


def run(store, twin, t: int) -> list[Finding]:
    ctx = context(store, twin, t)
    out = []
    for s in scans(ctx):
        if s.split_week is None:
            reason = f"{s.series}: {s.events} events in {s.weeks} weeks — too few to scan."
        else:
            verdict = ("drift alert" if s.alert else
                       f"explained by {s.explained_by}" if s.explained_by and s.p_value < P["alpha"] else "no significant change")
            reason = (f"{s.series}: strongest rate change at the week of {ist(s.split_start, '%d %b')} "
                      f"({s.rate_before} → {s.rate_after} per FH), GLR {s.glr}, p {s.p_value} — {verdict}.")
        out.append(finding("drift", Tier.PRED, None, f"drift:{s.series}", [
            belief("drift", "glr", s.glr, n=s.events), belief("drift", "p_value", s.p_value, n=int(P["bootstrap"])),
            belief("drift", "rate_before", s.rate_before), belief("drift", "rate_after", s.rate_after),
            belief("drift", "drift_alert", float(s.alert), note=s.explained_by or ""),
        ], [], reason))
    return out
