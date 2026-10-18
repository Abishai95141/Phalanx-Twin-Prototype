"""Fault isolation for one open issue: leaky noisy-OR suspect posterior and expected-information-gain test ranking
(architecture 04 D4; port of the film's TJ107 workbench, generalised to any code with suspect LRUs).

Hypotheses: each suspect LRU of the code (prior = its isolation confidence × (1 − leak)), the indication path
``IND`` (the reporting LRU's channel, the sensor and the harness; prior = leak) and, when the confidences sum to
less than 1, ``UNDETERMINED``. Evidence: bench findings on units of a suspect's part removed from this tail under
jobs of this code — P(RTOK | unit faulty) = 1 − d, P(RTOK | healthy) = 1, P(CONFIRMED | healthy) = false_confirm.

Tests come from the data: the code's troubleshooting procedure (PHX-FIM-…, from its could-not-duplicate jobs) tests
the indication path; a suspect with removals on record gets "remove and replace + bench" (PHX-TASK-…, detects with
probability d); a suspect without a part on record gets a check (procedure from params.yaml or the code's FIM).
Man-hours are the median of this tail's matching jobs (≥ 5) or the fleet's. Tests are ranked by expected
information gain per man-hour; robustness = in how many of the 24 (leak × sensitivity) settings a test ranks first.
Every assumption (d, leak, sensitivity, false positives) is in params.yaml with its sweep.

``run(store, twin, t) -> list[Finding]``: for each open issue whose code has suspects, a DIAG finding with the
suspect posterior (lo/hi = range over the d × leak grid) and a PRESC finding with the ranked tests.
``analyse(ctx, tail, code)`` returns the full result for the Workbench screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from interfaces import Finding, Tier

from engines.common import (
    PARAMS,
    Context,
    belief,
    context,
    finding,
    median_mh,
    rid_bytes,
    seq,
    top_proc,
)
from engines.episodes import Episode, open_episodes, recent_occurrences

P = PARAMS["isolation"]
IND, UND = "IND", "UNDETERMINED"


@dataclass(frozen=True)
class Test:
    id: str
    name: str
    detail: str
    proc: str | None
    mh: float
    mh_n: int
    mh_src: str
    kind: str  # "indication" | "check" | "remove_replace"
    target: str  # hypothesis it is aimed at


@dataclass(frozen=True)
class RankedTest:
    test: Test
    eig: float
    p_pos: float
    eig_per_mh: float
    best_in: int  # settings (of ``settings``) in which this test ranks first


@dataclass(frozen=True)
class Result:
    tail_no: str
    code: str
    hypotheses: tuple[str, ...]
    labels: dict[str, str]
    iso: dict[str, float]  # suspect LRU → isolation confidence (from the dictionary, via the events)
    parts: dict[str, str | None]  # suspect LRU → part number with removals under this code
    bench: dict[str, tuple[int, int]]  # suspect LRU → (units RTOK, units CONFIRMED) removed from this tail
    prior: dict[str, float]
    posterior: dict[str, float]
    lo: dict[str, float]  # min over the d × leak grid
    hi: dict[str, float]
    flip_leak: float | None  # leak above which IND outranks the second suspect
    tests: tuple[RankedTest, ...]  # ranked at the central setting
    settings: int
    evidence: tuple[str, ...]  # occurrence + job record ids (hex)


def _label(lru: str) -> str:
    return P["lru_labels"].get(lru, lru.replace("_", " ").lower())


def _part(lru: str) -> str:
    return P["lru_parts"].get(lru, f"SYN-PN-{lru}")


def posterior(prior: dict[str, float], bench: dict[str, tuple[int, int]], d: float) -> dict[str, float]:
    fc = float(P["false_confirm"])
    lik = {}
    for h in prior:
        k, c = bench.get(h, (0, 0))
        # hypothesis h true: its unit is faulty → RTOK with 1 − d, CONFIRMED with d; every other unit healthy
        lik[h] = (1 - d) ** k * d ** c
        for g, (kg, cg) in bench.items():
            if g != h:
                lik[h] *= fc ** cg
    z = sum(prior[h] * lik[h] for h in prior)
    return {h: prior[h] * lik[h] / z for h in prior} if z > 0 else dict(prior)


def _prior(iso: dict[str, float], leak: float) -> dict[str, float]:
    s = sum(iso.values())
    p = {h: c * (1 - leak) for h, c in iso.items()}
    if s < 1 - 1e-9:
        p[UND] = (1 - s) * (1 - leak)
    p[IND] = leak
    z = sum(p.values())
    return {h: v / z for h, v in p.items()}


def _H(p: dict[str, float]) -> float:
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def _eig(p: dict[str, float], sens: dict[str, float]) -> tuple[float, float]:
    pp = sum(p[h] * sens.get(h, 0.0) for h in p)
    pn = 1 - pp
    post_pos = {h: p[h] * sens.get(h, 0.0) / pp for h in p} if pp > 0 else p
    post_neg = {h: p[h] * (1 - sens.get(h, 0.0)) / pn for h in p} if pn > 0 else p
    return _H(p) - (pp * _H(post_pos) + pn * _H(post_neg)), pp


def _sens(t: Test, hyps, sens: float, fp: float, d: float) -> dict[str, float]:
    if t.kind == "remove_replace":
        return {h: (d if h == t.target else 0.0) for h in hyps}
    return {h: (sens if h == t.target else fp) for h in hyps}


def catalogue(ctx: Context, tail: str, code: str, suspects: dict[str, float], parts: dict[str, str | None]) -> list[Test]:
    """Tests for the issue: indication path first, then checks, then remove-and-replace, ids T1, T2, …"""
    mint = int(P["min_tail_jobs"])
    fleet = ctx.code_jobs(code)
    fleet = fleet[fleet.status == "CLOSED"]
    mine = fleet[fleet.tail_no == tail]

    def pick(rows_tail, rows_fleet, what):
        mh, n = median_mh(rows_tail)
        if n >= mint:
            return mh, n, f"{tail} {code} {what} jobs"
        mh, n = median_mh(rows_fleet)
        return mh, n, f"fleet {code} {what} jobs"

    out: list[tuple[str, str, str | None, float, int, str, str, str]] = []
    cnd_t, cnd_f = mine[mine.action_taken_code == "AT-CND"], fleet[fleet.action_taken_code == "AT-CND"]
    fim = top_proc(cnd_f, "PHX-FIM")
    mh, n, src = pick(cnd_t, cnd_f, f"troubleshooting{' ' + fim if fim else ''}")
    if mh is not None:
        lru = ctx.occ[ctx.occ.event_code == code].source_lru.iloc[-1]
        out.append(("Indication-path isolation", f"{lru} channel · sensor · harness continuity", fim, mh, n, src,
                    "indication", IND))
    for lru in suspects:
        if parts.get(lru):
            continue
        chk = P["lru_checks"].get(lru, {})
        proc = chk.get("proc", fim)
        jobs = ctx.jobs[(ctx.jobs.status == "CLOSED") & ctx.jobs.procs.map(lambda ps, p=proc: p in ps)] if proc else ctx.jobs.iloc[:0]
        mh, n = median_mh(jobs)
        if mh is None:
            continue
        lab = _label(lru)
        out.append((chk.get("name", f"{lab[:1].upper()}{lab[1:]} check"), chk.get("detail", f"{lru} functional check"),
                    proc, mh, n, f"fleet {proc} jobs" + (f" ({chk['note']})" if chk.get("note") else ""), "check", lru))
    rr_t, rr_f = mine[mine.action_taken_code == "AT-RR"], fleet[fleet.action_taken_code == "AT-RR"]
    for lru in suspects:
        pn = parts.get(lru)
        if not pn:
            continue
        task = top_proc(rr_f, "PHX-TASK")
        mh, n, src = pick(rr_t[rr_t.part_no == pn], rr_f[rr_f.part_no == pn], f"remove and replace{' ' + task if task else ''}")
        if mh is None:
            continue
        again = " again" if len(rr_t) else ""
        out.append((f"Remove and replace {_label(lru)}{again}", "status-quo response · bench test of the removed unit",
                    task, mh, n, src, "remove_replace", lru))
    return [Test(f"T{i}", *row) for i, row in enumerate(out, start=1)]


def analyse(ctx: Context, tail: str, code: str) -> Result | None:
    key = ("isolation", tail, code)
    if key in ctx._memo:
        return ctx._memo[key]
    o = ctx.occ[(ctx.occ.tail_no == tail) & (ctx.occ.event_code == code)]
    if not len(o):
        return None
    sus = o.suspect_lrus.iloc[-1]
    iso = {str(x["lru"]): float(x["isolation_confidence"]) for x in seq(sus)}
    if not iso:
        ctx._memo[key] = None
        return None
    jobs = ctx.code_jobs(code)
    parts, bench = {}, {}
    for lru in iso:
        pn = _part(lru)
        on_record = jobs[(jobs.part_no == pn) & (jobs.action_taken_code == "AT-RR")]
        parts[lru] = pn if len(on_record) else None
        if parts[lru]:
            mine = jobs[(jobs.tail_no == tail) & (jobs.part_no == pn)]
            sf = ctx.shop
            sf = sf[(sf.tail_no == tail) & (sf.part_no == pn) & sf.job_no.isin(set(mine.job_no))] if len(sf) else sf
            bench[lru] = (int((sf.shop_finding == "RTOK").sum()) if len(sf) else 0,
                          int(sf.shop_finding.isin(["CONFIRMED", "BCM"]).sum()) if len(sf) else 0)
    d0, l0 = float(P["detection"]), float(P["leak"])
    prior = _prior(iso, l0)
    post = posterior(prior, bench, d0)
    grid = [posterior(_prior(iso, L), bench, d) for L in P["sweep_leak"] for d in P["sweep_detection"]]
    lo = {h: min(g[h] for g in grid) for h in post}
    hi = {h: max(g[h] for g in grid) for h in post}
    ranked_iso = sorted(iso, key=lambda h: -iso[h])
    flip = iso[ranked_iso[1]] / (1 + iso[ranked_iso[1]]) if len(ranked_iso) > 1 else None
    tests = catalogue(ctx, tail, code, iso, parts)
    hyps = tuple(post)
    sens0, fp = float(P["sensitivity"]), float(P["false_positive"])

    def rank(p, sens):
        r = []
        for t in tests:
            g, pp = _eig(p, _sens(t, hyps, sens, fp, d0))
            r.append((t, g, pp, g / t.mh))
        return sorted(r, key=lambda x: (-x[3], x[0].id))

    best: dict[str, int] = {}
    settings = 0
    for L in P["sweep_leak"]:
        for s in P["sweep_sensitivity"]:
            settings += 1
            r = rank(posterior(_prior(iso, L), bench, d0), s)
            if r:
                best[r[0][0].id] = best.get(r[0][0].id, 0) + 1
    ranked = tuple(RankedTest(t, round(g, 6), round(pp, 6), round(gm, 6), best.get(t.id, 0)) for t, g, pp, gm in rank(post, sens0))
    labels = {h: _label(h) for h in iso} | {IND: "indication path", UND: "undetermined"}
    ep_rids = tuple(o.rid)
    res = Result(tail, code, hyps, labels, iso, parts, bench, prior, post, lo, hi, flip, ranked, settings,
                 ep_rids + tuple(jobs[jobs.tail_no == tail].rid))
    ctx._memo[key] = res
    return res


def findings(ctx: Context, ep: Episode) -> list[Finding]:
    r = analyse(ctx, ep.tail_no, ep.code)
    if r is None:
        return []
    order = sorted(r.posterior, key=lambda h: -r.posterior[h])
    txt = ", ".join(f"{r.labels[h]} {r.posterior[h]:.2f}" if r.posterior[h] >= 0.0001 else f"{r.labels[h]} < 0.0001"
                    for h in order)
    benched = "; ".join(f"{k} of {k + c} {r.labels[h]} units RTOK" for h, (k, c) in r.bench.items() if k + c)
    ev = rid_bytes(recent_occurrences(ctx, ep).rid)
    out = [finding("isolation", Tier.DIAG, ep.tail_no, ep.issue_id, [
        belief("isolation", f"p_{h}", r.posterior[h], r.lo[h], r.hi[h], note=r.labels[h]) for h in order
    ], ev, f"Most likely cause of {ep.code} on {ep.tail_no}: {txt}" + (f" ({benched})." if benched else "."))]
    if r.tests:
        top = r.tests[0]
        out.append(finding("isolation", Tier.PRESC, ep.tail_no, f"{ep.issue_id}:tests", [
            belief("isolation", t.test.id, t.eig_per_mh, n=t.best_in,
                   note=f"{t.test.name} · {t.test.mh} man-h (n {t.test.mh_n}) · {t.test.proc or '-'} · "
                        f"best in {t.best_in} of {r.settings}")
            for t in r.tests
        ], ev, f"Next test: {top.test.name.lower()} ({top.test.mh} man-h) gives the most information per man-hour, "
               f"best in {top.best_in} of {r.settings} assumption settings."))
    return out


def run(store, twin, t: int) -> list[Finding]:
    ctx = context(store, twin, t)
    return [f for ep in open_episodes(ctx) for f in findings(ctx, ep)]
