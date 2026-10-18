"""CND/NFF classifier P(defect closes could-not-duplicate or admin-closed) — trained for real, as of the snapshot.

Population: BIT-evidenced defect jobs (first version cites >= 1 events.bit_faults record) known by
2026-06-22 06:00 IST; labelled when the job's closing version (t_ingest <= snapshot) carries an action code.
Label: 1 = AT-CND or AT-ADM (closed no-fault), 0 = AT-RR / AT-TS (an item was removed / troubleshot).
Features — every one computed from records with t_ingest <= job open (the job's first version), never from later
versions of the job:
  code, severity, fault list (PFL/MFL), detection mechanism, system code, source LRU, tail,
  persistence_count of the evidence event, occ_10d / occ_30d (same tail+code events ingested in the prior 10/30 d),
  consecutive flights with the code, component removals on the tail in the prior 30 d,
  code no-fault rate as of open (fleet labels known before open, Beta-shrunk to the as-of fleet rate),
  tail+code prior closed jobs and their as-of no-fault share (shrunk to the code rate).
Protocol: rolling-origin by month; train on labels known before the origin; test on jobs opened in the next block.
Model configuration is chosen on the validation origins (Mar, Apr) only; the held-out block (opened
1 May -> 22 Jun 06:00) is scored once. Tail-grouped check: train on 6 tails, test on the 2 held out, no tail id.
"""
import sys, json, hashlib, time, pickle, os
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

CACHE = OUT + "assure_cnd_jobs_asof_20260622.csv"
PS = 2.0  # Beta pseudo-count for shrinkage


def build():
    m = asof(rd("maint.records"))
    ev = asof(rd("events.bit_faults"))
    evk = ev.set_index(ev.tail_no + ":" + ev.rid)
    dw = m[m.record_type == "DEFECT_WO"].sort_values(["tail_no", "record_key", "record_version"])
    g = dw.groupby(["tail_no", "record_key"], sort=False)
    first, last = g.head(1).set_index(["tail_no", "record_key"]), g.tail(1).set_index(["tail_no", "record_key"])
    sorties = m[m.record_type == "SORTIE"].sort_values("t_event")
    removals = m[(m.record_type == "COMPONENT_LIFE") & (m.install_action == "REMOVE")]
    rows = []
    for (tail, key), j in first.iterrows():
        evs = j.evidence_record_ids
        if evs is None or len(evs) == 0:
            continue
        ks = [k for k in (tail + ":" + bytes(x).hex() for x in evs) if k in evk.index]
        if not ks:
            continue
        e = evk.loc[ks[0]]
        t_open = j.t_ingest_dt
        L = last.loc[(tail, key)]
        lab = np.nan
        if L.status == "CLOSED" and L.action_taken_code in ("AT-CND", "AT-ADM", "AT-RR", "AT-TS"):
            lab = int(L.action_taken_code in ("AT-CND", "AT-ADM"))
        same = ev[(ev.tail_no == tail) & (ev.event_code == e.event_code) & (ev.t_ingest_dt <= t_open)]
        so = sorties[(sorties.tail_no == tail) & (sorties.t_ingest_dt <= t_open)].sortie_id.tolist()
        has, consec = set(same.sortie_id), 0
        for s in reversed(so):
            if s in has:
                consec += 1
            else:
                break
        rows.append(dict(tail_no=tail, job=j.job_no, key=key, code=e.event_code, severity=e.severity,
                         fault_list=e.fault_list, mech=e.detection_mechanism, system=j.system_code, lru=e.source_lru,
                         persistence=int(e.persistence_count),
                         occ10=int((same.t_ingest_dt > t_open - pd.Timedelta(days=10)).sum()),
                         occ30=int((same.t_ingest_dt > t_open - pd.Timedelta(days=30)).sum()), consec=consec,
                         rem30=int(((removals.tail_no == tail) & (removals.t_ingest_dt <= t_open) &
                                    (removals.t_ingest_dt > t_open - pd.Timedelta(days=30))).sum()),
                         t_open=t_open, t_known=L.t_ingest_dt if lab == lab else pd.NaT, label=lab,
                         action=L.action_taken_code, ev_rid=ks[0].split(":")[1]))
    J = pd.DataFrame(rows).sort_values(["t_open", "tail_no", "key"]).reset_index(drop=True)
    # as-of outcome priors: only labels whose t_known < this job's open time
    cr, tj, tn, fr_ = [], [], [], []
    for _, r in J.iterrows():
        known = J[J.label.notna() & (J.t_known < r.t_open)]
        f = float(known.label.mean()) if len(known) else 0.8
        c = known[known.code == r.code]
        crate = (c.label.sum() + PS * f) / (len(c) + PS)
        t = c[c.tail_no == r.tail_no]
        cr.append(crate); fr_.append(f); tj.append(len(t))
        tn.append((t.label.sum() + PS * crate) / (len(t) + PS))
    J["fleet_nf_asof"], J["code_nf_asof"], J["prior_jobs"], J["tailcode_nf_asof"] = fr_, cr, tj, tn
    J.to_csv(CACHE, index=False)
    return J


if os.environ.get("CND_CACHE") and os.path.exists(CACHE):
    J = pd.read_csv(CACHE)
    for c in ("t_open", "t_known"):
        J[c] = pd.to_datetime(J[c], utc=True).dt.tz_convert(IST)
else:
    J = build()
print("jobs", len(J), "labelled", int(J.label.notna().sum()), "positives", int(J.label.sum()))

lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))


def prep(D):
    D = D.copy()
    for c in ["occ10", "occ30", "consec", "prior_jobs", "rem30"]:
        D[c + "_l"] = np.log1p(D[c])
    D["code_lo"], D["tailcode_lo"] = lg(D.code_nf_asof), lg(D.tailcode_nf_asof)
    return D


NUM_ALL = ["persistence", "occ10_l", "occ30_l", "consec_l", "rem30_l", "prior_jobs_l", "code_lo", "tailcode_lo"]
CONFIGS = {
    # name: (categoricals, numerics, estimator)
    "logreg · one-hot codes": (["code", "severity", "fault_list", "mech", "system", "lru", "tail_no"], NUM_ALL, "lr"),
    "logreg · as-of priors": (["severity", "mech", "tail_no"], NUM_ALL, "lr"),
    "gbm+platt · as-of priors": (["severity", "mech", "tail_no"], NUM_ALL, "gbm"),
}


def make(cats, nums, kind):
    if kind == "lr":
        ct = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", min_frequency=3, sparse_output=False), cats),
                                ("n", StandardScaler(), nums)])
        return make_pipeline(ct, LogisticRegression(C=0.5, max_iter=5000))
    ct = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", min_frequency=3, sparse_output=False), cats),
                            ("n", "passthrough", nums)])
    return CalibratedClassifierCV(make_pipeline(ct, HistGradientBoostingClassifier(
        max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=1.0, random_state=0)), method="sigmoid", cv=3)


def ece(y, p, bins=10):
    b = np.clip((p * bins).astype(int), 0, bins - 1)
    tot, out = 0.0, []
    for k in range(bins):
        s = b == k
        if s.sum():
            tot += s.sum() / len(y) * abs(y[s].mean() - p[s].mean())
            out.append(dict(lo=k / bins, n=int(s.sum()), p=round(float(p[s].mean()), 4), y=round(float(y[s].mean()), 4)))
    return float(tot), out


def metrics(y, p):
    e, _ = ece(y, p)
    return dict(auc=round(float(roc_auc_score(y, p)), 3), brier=round(float(brier_score_loss(y, p)), 4),
                ece=round(e, 4), n=int(len(y)), pos=int(y.sum()))


def base_rate(test):  # the per-code base-rate baseline: code no-fault rate as of open (same shrinkage)
    return test.code_nf_asof.values


def run(tr, te, cfgs=CONFIGS, drop_tail=False):
    tr, te = prep(tr), prep(te)
    out = {}
    for name, (cats, nums, kind) in cfgs.items():
        cats = [c for c in cats if not (drop_tail and c == "tail_no")]
        mdl = make(cats, nums, kind)
        t0 = time.perf_counter(); mdl.fit(tr[cats + nums], tr.label.astype(int)); dt = time.perf_counter() - t0
        out[name] = (mdl.predict_proba(te[cats + nums])[:, 1], dt, mdl)
    out["per-code base rate"] = (base_rate(te), 0.0, None)
    return out


L = J[J.label.notna()].copy(); L["label"] = L.label.astype(int)
R = dict(population=dict(bit_evidenced_jobs=int(len(J)), labelled=int(len(L)), no_fault=int(L.label.sum()),
                         removed_or_ts=int(len(L) - L.label.sum()), open_or_deferred=int(J.label.isna().sum()),
                         actions=L.action.value_counts().to_dict()))

origins = [pd.Timestamp(d, tz=IST) for d in ("2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01")]
ends = origins[1:] + [SNAP]
folds = []
for o, e in zip(origins, ends):
    tr = L[L.t_known < o]; te = L[(L.t_open >= o) & (L.t_open < e)]
    res = run(tr, te)
    f = dict(origin=str(o.date()), n_train=len(tr), n_test=len(te), pos_test=int(te.label.sum()),
             role="validation" if o < pd.Timestamp("2026-05-01", tz=IST) else "held-out")
    for k, (p, dt, _) in res.items():
        f[k] = metrics(te.label.values, p)
    folds.append(f)
    print(f["origin"], f["role"], {k: (v["auc"], v["brier"], v["ece"]) for k, v in f.items() if isinstance(v, dict)})
R["rolling_origin"] = folds

# model selection on validation origins only (mean Brier)
val = [f for f in folds if f["role"] == "validation"]
sel = min(CONFIGS, key=lambda k: np.mean([f[k]["brier"] for f in val]))
R["selection"] = dict(rule="lowest mean Brier on validation origins 2026-03-01, 2026-04-01", selected=sel,
                      val_brier={k: round(float(np.mean([f[k]["brier"] for f in val])), 4) for k in list(CONFIGS) + ["per-code base rate"]})
print("selected", sel, R["selection"]["val_brier"])

# held-out block, scored once
O = pd.Timestamp("2026-05-01", tz=IST)
tr = L[L.t_known < O]; te = L[L.t_open >= O]
res = run(tr, te)
H = dict(train="labels known before 2026-05-01", test="jobs opened 2026-05-01 -> 2026-06-22 06:00",
         n_train=len(tr), pos_train=int(tr.label.sum()), n_test=len(te), pos_test=int(te.label.sum()))
for k, (p, dt, mdl) in res.items():
    mt = metrics(te.label.values, p); _, bins = ece(te.label.values, p)
    H[k] = dict(**mt, fit_s=round(dt, 3), calibration=bins)
R["held_out"] = H
for k in list(CONFIGS) + ["per-code base rate"]:
    print("HELD-OUT", k, {kk: H[k][kk] for kk in ("auc", "brier", "ece", "n", "pos")})

# bootstrap CI on held-out AUC/Brier difference (selected vs base rate), paired by job
rng = np.random.default_rng(20260622)
ps, pb, y = res[sel][0], res["per-code base rate"][0], te.label.values
dA, dB = [], []
for _ in range(2000):
    i = rng.integers(0, len(y), len(y))
    if y[i].min() == y[i].max():
        continue
    dA.append(roc_auc_score(y[i], ps[i]) - roc_auc_score(y[i], pb[i]))
    dB.append(brier_score_loss(y[i], ps[i]) - brier_score_loss(y[i], pb[i]))
R["held_out_vs_baseline"] = dict(d_auc=round(float(np.mean(dA)), 3), d_auc_ci=[round(float(np.quantile(dA, .025)), 3), round(float(np.quantile(dA, .975)), 3)],
                                 d_brier=round(float(np.mean(dB)), 4), d_brier_ci=[round(float(np.quantile(dB, .025)), 4), round(float(np.quantile(dB, .975)), 4)], boot=len(dA))
print("vs baseline", R["held_out_vs_baseline"])

# tail-grouped: train on 6 tails (labels before origin), test on the 2 held-out tails' later block; no tail id
tails = sorted(L.tail_no.unique()); groups = [tails[i:i + 2] for i in range(0, len(tails), 2)]
pp = {k: np.zeros(len(te)) for k in [sel, "per-code base rate"]}
for gt in groups:
    mask = te.tail_no.isin(gt).values
    if mask.sum() == 0:
        continue
    rg = run(tr[~tr.tail_no.isin(gt)], te[mask], {sel: CONFIGS[sel]}, drop_tail=True)
    pp[sel][mask] = rg[sel][0]; pp["per-code base rate"][mask] = te[mask].code_nf_asof.values
R["tail_grouped"] = {k: metrics(te.label.values, v) for k, v in pp.items()}
R["tail_grouped"]["groups"] = groups
print("tail-grouped", R["tail_grouped"])

# frozen artefact: refit the selected configuration on all labels known by the snapshot; hash it
cats, nums, kind = CONFIGS[sel]
final = make(cats, nums, kind).fit(prep(L)[cats + nums], L.label)
R["artefact_sha256"] = hashlib.sha256(pickle.dumps(final)).hexdigest()
spec = json.dumps(dict(config=sel, cats=cats, nums=nums, label="AT-CND|AT-ADM vs AT-RR|AT-TS",
                       population="BIT-evidenced DEFECT_WO", asof="2026-06-22T06:00+05:30", shrink=PS), sort_keys=True)
R["feature_spec_sha256"] = hashlib.sha256(spec.encode()).hexdigest()
R["train_set_blake2b"] = hashlib.blake2b("\n".join(sorted(L.tail_no + ":" + L.key)).encode(), digest_size=16).hexdigest()
if kind == "lr":
    lr = final.named_steps["logisticregression"]; names = final.named_steps["columntransformer"].get_feature_names_out()
    coef = sorted(zip(names, lr.coef_[0]), key=lambda t: -abs(t[1]))
    R["coefficients_top"] = [(n.replace("n__", "").replace("c__", ""), round(float(c), 3)) for n, c in coef[:8]]

# TJ107 HYD-101: score the latest open-issue job (for the provenance finding)
ji = J[(J.tail_no == "TJ107") & (J.code == "HYD-101")].sort_values("t_open")
last_j = ji.iloc[-1]
R["tj107_hyd101_latest_job"] = dict(job=last_j.job, t_open=str(last_j.t_open), label=None if last_j.label != last_j.label else int(last_j.label),
                                    p_nofault=round(float(final.predict_proba(prep(ji.tail(1))[cats + nums])[:, 1][0]), 3),
                                    code_nf_asof=round(float(last_j.code_nf_asof), 3))
R["code_rates_asof_snapshot"] = {c: dict(n=int(n), nofault=int(s), rate=round(float(s / n), 3)) for c, (s, n) in
                                 L.groupby("code").label.agg(["sum", "count"]).sort_values("count", ascending=False).head(10).iterrows()}
json.dump(R, open(OUT + "assure_cnd_asof_20260622.json", "w"), indent=1, default=str)
print("artefact", R["artefact_sha256"][:16], R.get("coefficients_top"), R["tj107_hyd101_latest_job"])

# ---- champion (2.3.0 = per-code Beta-Binomial no-fault rate, as-of) promotion evidence, as it stood on 1 Jun
G1w = L[(L.t_open >= pd.Timestamp("2026-03-01", tz=IST)) & (L.t_open < pd.Timestamp("2026-06-01", tz=IST))]
G1w = G1w[G1w.t_known < pd.Timestamp("2026-06-01 06:00", tz=IST)]
R["champion_g1"] = dict(window="jobs opened 1 Mar -> 31 May, labels known by 1 Jun 06:00",
                        model=metrics(G1w.label.values, G1w.code_nf_asof.values),
                        constant_fleet_rate=metrics(G1w.label.values, G1w.fleet_nf_asof.values),
                        calibration=ece(G1w.label.values, G1w.code_nf_asof.values)[1])
print("champion G1", R["champion_g1"]["model"], R["champion_g1"]["constant_fleet_rate"])
# ---- G2 shadow replay: 14 daily epochs 1-14 Jun; at each 06:00 cut-off score the BIT jobs that became known in the prior 24 h
ep = []
for d in pd.date_range("2026-06-01 06:00", "2026-06-14 06:00", freq="D", tz=IST):
    s = J[(J.t_open <= d) & (J.t_open > d - pd.Timedelta(days=1))]
    ep.append(dict(cutoff=str(d)[:16], scored=int(len(s)), low_nf=int((s.code_nf_asof < 0.6).sum())))
nlab = L.groupby("code").size()
R["g2_shadow_replay"] = dict(epochs=len(ep), scored=int(sum(e["scored"] for e in ep)), max_per_epoch=int(max(e["scored"] for e in ep)),
                             below_0_6=int(sum(e["low_nf"] for e in ep)), per_epoch=ep)
print("G2", {k: v for k, v in R["g2_shadow_replay"].items() if k != "per_epoch"})
json.dump(R, open(OUT + "assure_cnd_asof_20260622.json", "w"), indent=1, default=str)
