"""False-alarm (could-not-duplicate) model per alert code: Beta-Binomial with a Jeffreys prior shrunk to the fleet
rate (prior strength 2.0, DEVELOPMENT §2.5), plus a learned challenger that must beat it to replace it.

A defect job belongs to a code when any of its versions cites an occurrence of that code as evidence (keyed by
(tail, job): job numbers collide across the preview's worlds). Closed jobs get an outcome:

- NO_FAULT   closed AT-CND or AT-ADM (could not duplicate / admin close);
- TS         closed after troubleshooting with no removal (counted as not confirmed);
- RTOK       removed, and every bench finding on the removed units is RTOK;
- CONFIRMED  removed, and a bench finding is CONFIRMED (or BCM);
- PENDING    removed, no bench finding ingested yet (left out of P(confirmed) until it arrives).

Per code: ``p_confirmed`` = P(the alarm reflects a confirmed fault), ``p_rtok_if_removed`` = P(a unit removed for
it comes back RTOK), ``nofault_rate`` = share of closed jobs closed with no fault found (the champion CND
predictor). The challenger is a scikit-learn logistic regression on job features known at job open (port of the
film's assurance run); it is fitted on labels known before a held-out block and scored on it.

``run(store, twin, t) -> list[Finding]``: one DIAG finding per code with jobs, one per open issue (tail-level
history), and one for the champion/challenger comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from interfaces import DAY, Finding, Tier

from engines.common import (
    CONFIRMED_FINDINGS,
    NO_FAULT_ACTIONS,
    PARAMS,
    Context,
    belief,
    context,
    finding,
    ist,
    num,
    rid_bytes,
    seq,
    shrunk,
    text,
)

P = PARAMS["cnd"]
PS = float(P["prior_strength"])


# ---- outcomes --------------------------------------------------------------------------------------------
def outcomes(ctx: Context) -> pd.DataFrame:
    """One row per (tail, job, code) for every job citing a code: status, action, outcome, man-hours, bench
    findings on the units it removed."""
    if "cnd_outcomes" in ctx._memo:
        return ctx._memo["cnd_outcomes"]
    j = ctx.jobs
    j = j[j.codes.map(len) > 0]
    sf = ctx.shop
    fkey = {}
    if len(sf):
        for (t, job), g in sf.groupby(["tail_no", "job_no"]):
            fkey[(t, job)] = list(g.shop_finding)
    rows = []
    for r in j.itertuples():
        fs = fkey.get((r.tail_no, r.job_no), [])
        closed = r.status == "CLOSED"
        act = r.action_taken_code
        if not closed:
            out = "OPEN"
        elif act in NO_FAULT_ACTIONS:
            out = "NO_FAULT"
        elif act == "AT-RR":
            out = "CONFIRMED" if any(f in CONFIRMED_FINDINGS for f in fs) else ("RTOK" if fs else "PENDING")
        elif act == "AT-TS":
            out = "TS"
        else:
            out = "OTHER"
        for code in sorted(r.codes):
            rows.append((r.tail_no, r.job_no, code, r.status, act, out, num(r.man_hours),
                         sum(f == "RTOK" for f in fs), sum(f in CONFIRMED_FINDINGS for f in fs),
                         int(r.first_ingest), int(r.t_ingest), r.rid))
    df = pd.DataFrame(rows, columns=["tail_no", "job_no", "code", "status", "action", "outcome", "man_hours",
                                     "rtok_units", "confirmed_units", "t_open", "t_known", "rid"])
    ctx._memo["cnd_outcomes"] = df
    return df


@dataclass(frozen=True)
class CodeRates:
    code: str
    jobs: int
    closed: int
    no_fault: int
    removed: int
    ts: int
    pending: int
    confirmed: int
    labelled: int  # closed jobs with a known outcome (closed − pending − other)
    p_confirmed: tuple[float, float, float]
    units_benched: int
    units_rtok: int
    p_rtok: tuple[float, float, float] | None
    nofault: tuple[float, float, float]


def fleet_rates(ctx: Context) -> dict[str, float]:
    o = outcomes(ctx)
    lab = o[o.outcome.isin(["NO_FAULT", "TS", "RTOK", "CONFIRMED"])]
    closed = o[o.outcome != "OPEN"]
    k_c, n_c = int((lab.outcome == "CONFIRMED").sum()), len(lab)
    units = int(o.rtok_units.sum() + o.confirmed_units.sum())
    k_nf, n_nf = int((closed.outcome == "NO_FAULT").sum()), len(closed)
    return {"p_confirmed": (k_c + 0.5) / (n_c + 1), "p_rtok": (int(o.rtok_units.sum()) + 0.5) / (units + 1),
            "nofault": (k_nf + 0.5) / (n_nf + 1), "labelled": n_c, "units": units, "closed": n_nf}


def code_rates(ctx: Context, code: str) -> CodeRates:
    key = ("cnd_rates", code)
    if key in ctx._memo:
        return ctx._memo[key]
    f = fleet_rates(ctx)
    o = outcomes(ctx)
    c = o[o.code == code]
    closed = c[c.outcome != "OPEN"]
    oc = closed.outcome.value_counts()
    confirmed, pending = int(oc.get("CONFIRMED", 0)), int(oc.get("PENDING", 0))
    labelled = int(sum(oc.get(k, 0) for k in ("NO_FAULT", "TS", "RTOK", "CONFIRMED")))
    units_rtok, units_conf = int(c.rtok_units.sum()), int(c.confirmed_units.sum())
    units = units_rtok + units_conf
    res = CodeRates(
        code=code, jobs=len(c), closed=len(closed), no_fault=int(oc.get("NO_FAULT", 0)),
        removed=int(sum(oc.get(k, 0) for k in ("RTOK", "CONFIRMED", "PENDING"))), ts=int(oc.get("TS", 0)),
        pending=pending, confirmed=confirmed, labelled=labelled,
        p_confirmed=shrunk(confirmed, labelled, f["p_confirmed"], PS),
        units_benched=units, units_rtok=units_rtok,
        p_rtok=shrunk(units_rtok, units, f["p_rtok"], PS) if units else None,
        nofault=shrunk(int(oc.get("NO_FAULT", 0)), len(closed), f["nofault"], PS),
    )
    ctx._memo[key] = res
    return res


def code_finding(ctx: Context, code: str) -> Finding:
    r = code_rates(ctx, code)
    pc, nf = r.p_confirmed, r.nofault
    beliefs = [belief("cnd", "p_confirmed", *pc, n=r.labelled,
                      note=f"{r.confirmed} of {r.labelled} closed jobs confirmed"),
               belief("cnd", "nofault_rate", *nf, n=r.closed,
                      note=f"{r.no_fault} of {r.closed} closed with no fault found")]
    rt = ""
    if r.p_rtok is not None:
        beliefs.append(belief("cnd", "p_rtok_if_removed", *r.p_rtok, n=r.units_benched,
                              note=f"{r.units_rtok} of {r.units_benched} removed units RTOK"))
        rt = f", {r.units_rtok} of {r.units_benched} removed units RTOK at the bench"
    pend = f", {r.pending} removals awaiting a bench finding" if r.pending else ""
    reason = (f"{code}: {r.confirmed} of {r.labelled} closed jobs confirmed a fault ({r.no_fault} no fault found"
              f"{rt}{pend}); P(confirmed) {pc[0]:.3f} [{pc[1]:.3f}, {pc[2]:.3f}].")
    jobs = outcomes(ctx)
    ev = jobs[jobs.code == code].rid
    return finding("cnd", Tier.DIAG, None, code, beliefs, rid_bytes(ev), reason)


def issue_history(ctx: Context, tail: str, code: str) -> dict:
    """This tail's record for the code: jobs by action, man-hours, removals and bench findings."""
    o = outcomes(ctx)
    c = o[(o.tail_no == tail) & (o.code == code)]
    acts = c.action.fillna("none").value_counts().to_dict()
    return {"jobs": len(c), "actions": {str(k): int(v) for k, v in acts.items()},
            "man_hours": round(float(c.man_hours.sum()), 1), "removals": int((c.action == "AT-RR").sum()),
            "units_rtok": int(c.rtok_units.sum()), "units_confirmed": int(c.confirmed_units.sum()),
            "open": int((c.outcome == "OPEN").sum())}


def issue_finding(ctx: Context, tail: str, code: str, issue_id: str) -> Finding:
    h = issue_history(ctx, tail, code)
    o = outcomes(ctx)
    ev = o[(o.tail_no == tail) & (o.code == code)].rid
    a = h["actions"]
    reason = (f"{tail} {code}: {h['jobs']} jobs ({a.get('AT-CND', 0)} could not duplicate, {a.get('AT-RR', 0)} remove-and-replace, "
              f"{a.get('AT-TS', 0)} troubleshoot), {h['man_hours']:,} man-hours; {h['units_rtok']} removed units RTOK, "
              f"{h['units_confirmed']} confirmed.")
    return finding("cnd", Tier.DESC, tail, issue_id, [
        belief("cnd", "jobs", h["jobs"]), belief("cnd", "man_hours", h["man_hours"]),
        belief("cnd", "removals", h["removals"]), belief("cnd", "units_rtok", h["units_rtok"]),
        belief("cnd", "units_confirmed", h["units_confirmed"]),
    ], rid_bytes(ev), reason)


# ---- challenger ------------------------------------------------------------------------------------------
NUM = ["persistence", "occ10_l", "occ30_l", "consec_l", "rem30_l", "prior_jobs_l", "code_lo", "tailcode_lo"]
CATS = ["code", "severity", "fault_list", "mech", "system", "lru", "tail_no"]


def job_features(ctx: Context) -> pd.DataFrame:
    """Alert-evidenced jobs (first version cites an alert) with features known at job open and the CND label
    (1 = closed AT-CND/AT-ADM, 0 = closed AT-RR/AT-TS, NaN = not yet known)."""
    if "cnd_features" in ctx._memo:
        return ctx._memo["cnd_features"]
    allv = ctx.maint_all
    dw = allv[(allv.record_type == "DEFECT_WO") & allv.tail_no.notna() & allv.job_no.notna()]
    dw = dw.sort_values(["record_version", "t_ingest"], kind="mergesort")
    v0 = dw.groupby(["tail_no", "job_no"], sort=False).head(1)
    last = {(t, j): (s, a, ti) for t, j, s, a, ti in
            zip(ctx.jobs.tail_no, ctx.jobs.job_no, ctx.jobs.status, ctx.jobs.action_taken_code, ctx.jobs.t_ingest, strict=True)}
    occ = ctx.occ
    by_rid = {}
    for r in occ.itertuples():
        for x in r.rids:
            by_rid[(r.tail_no, x)] = r
    occ_idx = {k: np.sort(g.t_ingest.to_numpy()) for k, g in occ.groupby(["tail_no", "event_code"])}
    occ_sorties = {k: g.sort_values("t_ingest")[["t_ingest", "sortie_id"]] for k, g in occ.groupby(["tail_no", "event_code"])}
    rem = {t: np.sort(g.t_ingest.to_numpy()) for t, g in ctx.removals.groupby("tail_no")}
    rows = []
    for r in v0.itertuples():
        if (r.tail_no, r.job_no) not in last:
            continue  # a duplicate snag
        evs = [bytes(b).hex() for b in seq(r.evidence_record_ids)]
        e = next((by_rid[(r.tail_no, x)] for x in evs if (r.tail_no, x) in by_rid), None)
        if e is None:
            continue
        t_open = int(r.t_ingest)
        st, act, t_known = last[(r.tail_no, r.job_no)]
        lab = np.nan
        if st == "CLOSED" and act in ("AT-CND", "AT-ADM", "AT-RR", "AT-TS"):
            lab = float(act in NO_FAULT_ACTIONS)
        ts = occ_idx[(r.tail_no, e.event_code)]
        so = ctx.sorties(r.tail_no)
        so = so[so.t_ingest <= t_open].sortie_id.tolist()
        oc = occ_sorties[(r.tail_no, e.event_code)]
        fired = set(oc[oc.t_ingest <= t_open].sortie_id)
        consec = 0
        for s in reversed(so):
            if s not in fired:
                break
            consec += 1
        rt = rem.get(r.tail_no, np.array([], dtype=np.int64))
        rows.append({
            "tail_no": r.tail_no, "job_no": r.job_no, "code": e.event_code, "severity": text(e.severity),
            "fault_list": text(e.fault_list), "mech": text(e.detection_mechanism), "system": text(r.system_code),
            "lru": text(e.source_lru), "persistence": int(num(e.persistence_count)),
            "occ10": int(((ts <= t_open) & (ts > t_open - 10 * DAY)).sum()),
            "occ30": int(((ts <= t_open) & (ts > t_open - 30 * DAY)).sum()), "consec": consec,
            "rem30": int(((rt <= t_open) & (rt > t_open - 30 * DAY)).sum()),
            "t_open": t_open, "t_known": None if np.isnan(lab) else int(t_known), "label": lab, "rid": r.rid})
    J = pd.DataFrame(rows)
    if not len(J):
        ctx._memo["cnd_features"] = J
        return J
    J = J.sort_values(["t_open", "tail_no", "job_no"], kind="mergesort").reset_index(drop=True)
    # as-of outcome priors: only labels known strictly before this job opened
    lab = J.label.to_numpy()
    known = (J.t_known.fillna(np.inf).to_numpy()[None, :] < J.t_open.to_numpy()[:, None]) & ~np.isnan(lab)[None, :]
    y = np.nan_to_num(lab)
    n_f, k_f = known.sum(1), known @ y
    fleet = np.where(n_f > 0, k_f / np.maximum(n_f, 1), 0.8)
    same_code = J.code.to_numpy()[:, None] == J.code.to_numpy()[None, :]
    kc, nc = (known & same_code) @ y, (known & same_code).sum(1)
    crate = (kc + PS * fleet) / (nc + PS)
    same_tc = same_code & (J.tail_no.to_numpy()[:, None] == J.tail_no.to_numpy()[None, :])
    kt, nt = (known & same_tc) @ y, (known & same_tc).sum(1)
    J["code_nf_asof"], J["prior_jobs"], J["tailcode_nf_asof"] = crate, nt, (kt + PS * crate) / (nt + PS)
    ctx._memo["cnd_features"] = J
    return J


def _prep(D: pd.DataFrame) -> pd.DataFrame:
    D = D.copy()
    for c in ["occ10", "occ30", "consec", "prior_jobs", "rem30"]:
        D[c + "_l"] = np.log1p(D[c].astype(float))
    lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    D["code_lo"], D["tailcode_lo"] = lg(D.code_nf_asof), lg(D.tailcode_nf_asof)
    for c in CATS:
        D[c] = D[c].astype(str)
    return D


@dataclass(frozen=True)
class Comparison:
    origin: int
    n_train: int
    n_test: int
    brier_champion: float | None
    brier_challenger: float | None
    auc_champion: float | None
    auc_challenger: float | None
    d_brier_ci: tuple[float, float] | None  # challenger − champion, bootstrap 95 %
    champion: str  # "per-code base rate" unless the challenger is better with the CI below zero


def challenger(ctx: Context) -> Comparison:
    """Fit the logistic-regression challenger on labels known before the held-out block, score both on it."""
    if "cnd_cmp" in ctx._memo:
        return ctx._memo["cnd_cmp"]
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    J = job_features(ctx)
    origin = ctx.t - int(P["holdout_days"]) * DAY
    L = J[J.label.notna()] if len(J) else J
    tr = L[L.t_known.astype(float) < origin] if len(L) else L
    te = L[L.t_open >= origin] if len(L) else L
    if len(te) < P["min_holdout"] or len(tr) < 50 or len(set(tr.label)) < 2 or len(set(te.label)) < 2:
        res = Comparison(origin, len(tr), len(te), None, None, None, None, None, "per-code base rate")
        ctx._memo["cnd_cmp"] = res
        return res
    tr, te = _prep(tr), _prep(te)
    ct = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", min_frequency=3, sparse_output=False), CATS),
                            ("n", StandardScaler(), NUM)])
    mdl = make_pipeline(ct, LogisticRegression(C=float(P["challenger_C"]), max_iter=5000))
    mdl.fit(tr[CATS + NUM], tr.label.astype(int))
    y = te.label.astype(int).to_numpy()
    pc, pb = mdl.predict_proba(te[CATS + NUM])[:, 1], te.code_nf_asof.to_numpy()
    rng = np.random.default_rng(int(ctx.t // DAY))
    d = []
    for _ in range(1000):
        i = rng.integers(0, len(y), len(y))
        d.append(brier_score_loss(y[i], pc[i]) - brier_score_loss(y[i], pb[i]))
    lo, hi = float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))
    bc, bb = float(brier_score_loss(y, pc)), float(brier_score_loss(y, pb))
    res = Comparison(origin, len(tr), len(te), round(bb, 4), round(bc, 4), round(float(roc_auc_score(y, pb)), 3),
                     round(float(roc_auc_score(y, pc)), 3), (round(lo, 4), round(hi, 4)),
                     "logistic regression" if (bc < bb and hi < 0) else "per-code base rate")
    ctx._memo["cnd_cmp"] = res
    return res


def challenger_finding(ctx: Context) -> Finding:
    c = challenger(ctx)
    if c.brier_champion is None:
        reason = f"Challenger not scored: {c.n_test} held-out jobs since {ist(c.origin, '%d %b')}; the per-code base rate stays champion."
    else:
        reason = (f"Held-out jobs opened since {ist(c.origin, '%d %b')} (n {c.n_test}): base-rate Brier {c.brier_champion:.4f}, "
                  f"logistic regression {c.brier_challenger:.4f} (difference CI [{c.d_brier_ci[0]:+.4f}, {c.d_brier_ci[1]:+.4f}]); "
                  f"champion: {c.champion}.")
    return finding("cnd_challenger", Tier.DIAG, None, "cnd:champion", [
        belief("cnd_challenger", "brier_champion", c.brier_champion, n=c.n_test),
        belief("cnd_challenger", "brier_challenger", c.brier_challenger, *(c.d_brier_ci or (None, None)), n=c.n_test,
               note="lo/hi: bootstrap 95 % CI of challenger − champion Brier"),
        belief("cnd_challenger", "auc_champion", c.auc_champion, n=c.n_test),
        belief("cnd_challenger", "auc_challenger", c.auc_challenger, n=c.n_test),
        belief("cnd_challenger", "champion_is_base_rate", float(c.champion == "per-code base rate"), n=c.n_train),
    ], [], reason)


def run(store, twin, t: int, with_challenger: bool = True) -> list[Finding]:
    """Per-code rates for every code with jobs, the tail history of every open issue, and the challenger check."""
    from engines.episodes import open_episodes

    ctx = context(store, twin, t)
    codes = sorted(outcomes(ctx).code.unique())
    out = [code_finding(ctx, c) for c in codes]
    out += [issue_finding(ctx, e.tail_no, e.code, e.issue_id) for e in open_episodes(ctx)]
    if with_challenger:
        out.append(challenger_finding(ctx))
    return out
