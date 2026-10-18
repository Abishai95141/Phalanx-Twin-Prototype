"""Registry numbers for the other models + the drift panel, all as of 2026-06-22 06:00 IST.

- G0 data gate: sha256 of every fleet file vs MANIFEST.json, contract hash in every schema, dictionary hash.
- Supply lead-time survival: Kaplan-Meier with genuinely open demands right-censored at the snapshot, plus a
  log-normal AFT (lifelines) with priority and part-class covariates; held-out check (fit on demands opened before
  1 May, C-index on demands opened after). Open AOG demands whose job closed without a demand closure are excluded
  and counted (fulfilment not recorded).
- Tyre demand from landings: landings between consecutive tyre installs per tail; backtest May-Jun.
- Removal hazard: removals by part class, shop findings by verdict (0 CONFIRMED -> insufficient evidence).
- Isolation leak parameters: per-code no-fault outcome share (learnable); detection parameters prior-only.
- Drift: weekly BIT events per FH (fleet), Poisson GLR scan with parametric bootstrap; known change-points from
  orders.commands (WASH_SERVICE), COMPONENT_LIFE HYDP installs, and the release/dictionary adoption; per
  change-point before/after rate comparison and classification.
"""
import sys, json, hashlib, glob, os
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *
import pyarrow.parquet as pq
from lifelines import KaplanMeierFitter, LogNormalAFTFitter
from lifelines.utils import concordance_index

R = {}
# ------------------------------------------------------------------ G0: release + file integrity
man = json.load(open(ROOT + "MANIFEST.json"))
R["release_id"] = hashlib.sha256(open(ROOT + "MANIFEST.json", "rb").read()).hexdigest()
ok = bad = 0
for rel, meta in man["files"].items():
    if not rel.startswith("fleet/"):
        continue
    h = hashlib.sha256(open(ROOT + rel, "rb").read()).hexdigest()
    ok += h == meta["sha256"]; bad += h != meta["sha256"]
hashes = set()
for f in glob.glob(B + "**/*.parquet", recursive=True):
    hashes.add((pq.read_schema(f).metadata or {}).get(b"phalanx.contract_hash", b"").decode())
R["g0"] = dict(fleet_files_verified=ok, fleet_files_mismatch=bad, contract_hashes=sorted(hashes),
               code_commit=man["code_commit"], schema_hash=man["schema_hash"], leak_audit=man["validation"]["leak_audit_findings"],
               seeds=man["seeds"])
print("G0", R["g0"]["fleet_files_verified"], R["g0"]["fleet_files_mismatch"], R["g0"]["contract_hashes"])

m = asof(rd("maint.records")); ek = asof(rd("events.bit_faults")); oc = rd("orders.commands")
R["dict"] = sorted(set(m.dict_hash) | set(ek.dict_hash))

# ------------------------------------------------------------------ supply lead time
d = m[m.record_type == "SUPPLY_DEMAND"].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key"], keep="last")
jobs = m[m.record_type.isin(["DEFECT_WO", "INSPECTION"])].sort_values(["record_version", "t_ingest"]).drop_duplicates(["tail_no", "record_key"], keep="last")
jst = {(r.tail_no, r.job_no): r.status for _, r in jobs.iterrows()}
d["job_status"] = [jst.get((r.tail_no, r.job_no), "NOJOB") for _, r in d.iterrows()]
closed = d[d.status == "CLOSED"].copy()
genuine_open = d[(d.status != "CLOSED") & (d.job_status != "CLOSED")].copy()
orphan = d[(d.status != "CLOSED") & (d.job_status == "CLOSED")]
closed["T"] = (closed.t_close_dt - closed.t_open_dt).dt.total_seconds() / 86400; closed["E"] = 1
genuine_open["T"] = (SNAP - genuine_open.t_open_dt).dt.total_seconds() / 86400; genuine_open["E"] = 0
S = pd.concat([closed, genuine_open])
S["part"] = S.part_no.str.replace("SYN-PN-", "")
km = KaplanMeierFitter().fit(S["T"], S["E"])
grid = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 17, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100, 120, 140, 160]
sf = km.survival_function_at_times(grid).values
ci = km.confidence_interval_survival_function_
def ci_at(t):
    i = ci.index.searchsorted(t, side="right") - 1
    return [float(ci.iloc[max(i, 0), 0]), float(ci.iloc[max(i, 0), 1])]
q = lambda p: float(km.percentile(p))  # time where S(t) = p
step = [[float(t), float(s)] for t, s in km.survival_function_.iloc[:, 0].items()]
R["leadtime"] = dict(n=len(S), closed=int(S.E.sum()), censored=int((S.E == 0).sum()), orphan_excluded=len(orphan),
                     closed_only=dict(median=round(float(closed["T"].median()), 1), p90=round(float(closed["T"].quantile(.9)), 1)),
                     km_median=round(q(0.5), 1), km_p75=round(q(0.25), 1),
                     km_p90=None if not np.isfinite(q(0.1)) else round(q(0.1), 1),
                     s_at=dict(zip([str(g) for g in grid], [round(float(x), 4) for x in sf])),
                     s_ci_at={str(g): [round(x, 4) for x in ci_at(g)] for g in grid},
                     step=step, closed_T=sorted([round(float(t), 2) for t in closed["T"]]), censor_times=sorted([round(float(t), 2) for t in genuine_open["T"]]),
                     by_part={p: dict(n=int(len(g)), events=int(g.E.sum())) for p, g in S.groupby("part")},
                     by_prio={p: dict(n=int(len(g)), events=int(g.E.sum())) for p, g in S.groupby("priority")})
print("KM", R["leadtime"]["km_median"], R["leadtime"]["km_p75"], R["leadtime"]["km_p90"], "closed-only", R["leadtime"]["closed_only"], "n", len(S), int(S.E.sum()))
# log-normal AFT
X = S.assign(aog=(S.priority == "AOG").astype(float), chute=(S.part == "CHUTE").astype(float), hydp=(S.part == "HYDP").astype(float))[["T", "E", "aog", "chute", "hydp"]]
X["T"] = X["T"].clip(lower=0.01)
aft = LogNormalAFTFitter().fit(X, "T", "E")
summ = aft.summary
R["leadtime"]["aft"] = dict(params={f"{a}:{b}": [round(float(r["coef"]), 3), round(float(r["coef lower 95%"]), 3), round(float(r["coef upper 95%"]), 3)] for (a, b), r in summ.iterrows()},
                            aic=round(float(aft.AIC_), 1), concordance=round(float(aft.concordance_index_), 3))
for name, row in dict(tyre_mcm=[0, 0, 0], tyre_aog=[1, 0, 0], chute_aog=[1, 1, 0], pump_aog=[1, 0, 1]).items():
    df = pd.DataFrame([row], columns=["aog", "chute", "hydp"])
    R["leadtime"]["aft"][name + "_median"] = round(float(aft.predict_median(df).iloc[0]), 1)
    R["leadtime"]["aft"][name + "_p90"] = round(float(aft.predict_percentile(df, p=0.1).iloc[0]), 1)
# AFT curves (population-average over the covariate mix) for the chart
tt = np.array(grid[1:], float)
sfa = aft.predict_survival_function(X[["aog", "chute", "hydp"]], times=tt).mean(axis=1)
R["leadtime"]["aft_curve"] = [[float(t), round(float(s), 4)] for t, s in zip(tt, sfa)]
# held-out: fit on demands opened before 1 May (as known on 1 May), C-index on demands opened after
O = pd.Timestamp("2026-05-01", tz=IST)
tr = S[S.t_open_dt < O].copy()
tr["E1"] = ((tr.E == 1) & (tr.t_close_dt <= O)).astype(int)
tr["T1"] = np.where(tr.E1 == 1, tr["T"], (O - tr.t_open_dt).dt.total_seconds() / 86400).clip(0.01)
te = S[S.t_open_dt >= O]
Xtr = tr.assign(aog=(tr.priority == "AOG").astype(float), chute=(tr.part == "CHUTE").astype(float), hydp=(tr.part == "HYDP").astype(float))[["T1", "E1", "aog", "chute", "hydp"]]
aft2 = LogNormalAFTFitter().fit(Xtr, "T1", "E1")
Xte = te.assign(aog=(te.priority == "AOG").astype(float), chute=(te.part == "CHUTE").astype(float), hydp=(te.part == "HYDP").astype(float))
pred = aft2.predict_median(Xte[["aog", "chute", "hydp"]])
p90 = aft2.predict_percentile(Xte[["aog", "chute", "hydp"]], p=0.1)
cov = float(((te["T"] <= p90.values) | (te.E == 0)).mean()) if len(te) else None
R["leadtime"]["held_out"] = dict(n_train=len(tr), n_test=len(te), events_test=int(te.E.sum()),
                                 c_index=round(float(concordance_index(te["T"], pred, te.E)), 3),
                                 p90_coverage=round(float(((te["T"] <= p90.values) & (te.E == 1)).sum() / max(te.E.sum(), 1)), 3))
print("AFT", R["leadtime"]["aft"], R["leadtime"]["held_out"])

# ------------------------------------------------------------------ tyre demand from landings
so = m[m.record_type == "SORTIE"].sort_values("t_event")
ty = m[(m.record_type == "COMPONENT_LIFE") & (m.part_no == "SYN-PN-TYRE")]
ints = []
for t, g in ty[ty.install_action == "INSTALL"].groupby("tail_no"):
    times = sorted(g.t_event_dt.unique())
    st = so[so.tail_no == t]
    for a, b in zip(times, times[1:]):
        ints.append(dict(tail=t, start=a, landings=int(st[(st.t_event_dt > a) & (st.t_event_dt <= b)].landings.sum())))
I = pd.DataFrame(ints)
I = I[I.landings > 0]
tr_i = I[I.start < O]
med = float(tr_i.landings.median())
# backtest: predicted tyre changes May 1 -> Jun 22 = landings / median interval (per tail) vs actual install events
bt = []
for t in sorted(so.tail_no.dropna().unique()):
    ld = int(so[(so.tail_no == t) & (so.t_event_dt >= O)].landings.sum())
    act = int(ty[(ty.tail_no == t) & (ty.install_action == "INSTALL") & (ty.t_event_dt >= O)].t_event_dt.nunique())
    bt.append(dict(tail=t, landings=ld, predicted=round(ld / med, 2), actual=act))
B_ = pd.DataFrame(bt)
R["tyres"] = dict(intervals=len(I), median_landings=float(I.landings.median()), iqr=[float(I.landings.quantile(.25)), float(I.landings.quantile(.75))],
                  train_median=med, backtest=bt, pred_total=round(float(B_.predicted.sum()), 1), actual_total=int(B_.actual.sum()),
                  mae_per_tail=round(float((B_.predicted - B_.actual).abs().mean()), 2), tyre_removals=int((ty.install_action == "REMOVE").sum()))
print("tyres", {k: v for k, v in R["tyres"].items() if k != "backtest"})

# ------------------------------------------------------------------ removal hazard + shop findings
cl = m[(m.record_type == "COMPONENT_LIFE") & (m.install_action == "REMOVE")]
sf_ = m[m.record_type == "SHOP_FINDING"]
R["hazard"] = dict(removals=cl.part_no.str.replace("SYN-PN-", "").value_counts().to_dict(),
                   non_tyre_removals=int((cl.part_no != "SYN-PN-TYRE").sum()),
                   shop_findings=sf_.shop_finding.value_counts().to_dict(), confirmed=int((sf_.shop_finding == "CONFIRMED").sum()))
print("hazard", R["hazard"])

# ------------------------------------------------------------------ isolation: leak parameters learnable
co = pd.read_csv(OUT + "assure_cnd_jobs_asof_20260622.csv")
co = co[co.label.notna()]
lk = co.groupby("code").label.agg(["sum", "count"])
R["isolation"] = dict(codes_with_outcomes=int(len(lk)), outcomes=int(lk["count"].sum()),
                      leak_hyd101=dict(nofault=int(lk.loc["HYD-101", "sum"]), n=int(lk.loc["HYD-101", "count"])),
                      tj107_hyd101_sorties=None, detection_confirmed=R["hazard"]["confirmed"])
so107 = so[so.tail_no == "TJ107"]; h107 = ek[(ek.tail_no == "TJ107") & (ek.event_code == "HYD-101")]
R["isolation"]["tj107_hyd101_sorties"] = dict(fired=int(so107.sortie_id.isin(h107.sortie_id).sum()), sorties=len(so107))

# ------------------------------------------------------------------ drift: weekly BIT per FH, change-points
W0 = pd.Timestamp("2026-01-05", tz=IST)
wk = lambda t: ((t - W0).dt.total_seconds() // (7 * 86400)).astype(int)
sw = so.assign(w=wk(so.t_event_dt)); ew = ek.assign(w=wk(ek.t_occurrence_dt))
weeks = list(range(0, 24))
fh = sw.groupby("w").flight_hours.sum().reindex(weeks, fill_value=0); n = ew.groupby("w").size().reindex(weeks, fill_value=0)
rate = (n / fh)
from scipy.stats import poisson
def ci_p(k, e):
    lo = poisson.ppf(0.025, k) if k else 0
    from scipy.stats import chi2
    lo = chi2.ppf(0.025, 2 * k) / 2 if k else 0.0; hi = chi2.ppf(0.975, 2 * k + 2) / 2
    return lo / e, hi / e
series = [dict(w=w, start=str((W0 + pd.Timedelta(days=7 * w)).date()), fh=round(float(fh[w]), 2), n=int(n[w]), rate=round(float(rate[w]), 3),
               lo=round(ci_p(int(n[w]), float(fh[w]))[0], 3), hi=round(ci_p(int(n[w]), float(fh[w]))[1], 3)) for w in weeks]
# Poisson GLR scan for a single rate change, exposure = FH; parametric bootstrap p-value
def glr(nv, ev_):
    N, E = nv.sum(), ev_.sum(); l0 = N * np.log(N / E) - N
    best, arg = -1, None
    for k in range(2, len(nv) - 2):
        a, b = nv[:k].sum(), nv[k:].sum(); ea, eb = ev_[:k].sum(), ev_[k:].sum()
        l1 = (a * np.log(a / ea) - a if a else -0.0) + (b * np.log(b / eb) - b if b else 0.0)
        if l1 - l0 > best:
            best, arg = l1 - l0, k
    return best, arg
nv, evv = n.values.astype(float), fh.values.astype(float)
stat, k = glr(nv, evv)
rng = np.random.default_rng(20260622); lam = nv.sum() / evv.sum()
boot = [glr(rng.poisson(lam * evv).astype(float), evv)[0] for _ in range(2000)]
p = float((np.array(boot) >= stat).mean())
R["drift"] = dict(series=series, fleet_rate=round(float(lam), 3), glr=round(float(stat), 2), glr_week=int(k),
                  glr_week_start=str((W0 + pd.Timedelta(days=7 * k)).date()),
                  rate_before=round(float(nv[:k].sum() / evv[:k].sum()), 3), rate_after=round(float(nv[k:].sum() / evv[k:].sum()), 3), p_value=round(p, 3))
print("GLR", R["drift"]["glr"], R["drift"]["glr_week_start"], R["drift"]["rate_before"], R["drift"]["rate_after"], "p", p)

# change-points
cps = []
o_ = oc[(oc.t_issued_dt <= SNAP) & (oc.action == "WASH_SERVICE")]
def tail_rate(t, a, b, codes=None):
    s_ = so[(so.tail_no == t) & (so.t_event_dt > a) & (so.t_event_dt <= b)]
    e_ = ek[(ek.tail_no == t) & (ek.t_occurrence_dt > a) & (ek.t_occurrence_dt <= b)]
    if codes is not None:
        e_ = e_[e_.event_code.str.startswith(codes)]
    return int(len(e_)), float(s_.flight_hours.sum()), int(len(s_))
tot = dict(b=[0, 0.0], a=[0, 0.0], be=[0, 0.0], ae=[0, 0.0])
for _, r in o_.iterrows():
    t, T = r.target_tail_no, r.t_issued_dt
    nb, fb, sb = tail_rate(t, T - pd.Timedelta(days=21), T); na, fa, sa = tail_rate(t, T, min(T + pd.Timedelta(days=21), SNAP))
    nbe, _, _ = tail_rate(t, T - pd.Timedelta(days=21), T, "ENG"); nae, _, _ = tail_rate(t, T, min(T + pd.Timedelta(days=21), SNAP), "ENG")
    cps.append(dict(kind="WASH_SERVICE", source="orders.commands", order_id=r.order_id, rid=r.rid, issuer=r.issuer_kind,
                    tail=t, t=str(T)[:16], before=dict(n=nb, fh=round(fb, 2), eng=nbe), after=dict(n=na, fh=round(fa, 2), eng=nae)))
    tot["b"][0] += nb; tot["b"][1] += fb; tot["a"][0] += na; tot["a"][1] += fa; tot["be"][0] += nbe; tot["ae"][0] += nae
from scipy.stats import binomtest
def rr(nb, fb, na, fa):  # conditional binomial test for equal Poisson rates
    pval = binomtest(int(na), int(na + nb), fa / (fa + fb)).pvalue if na + nb else 1.0
    return round((na / fa) / (nb / fb), 3) if nb and fa and fb else None, round(float(pval), 3)
R["washes"] = dict(events=cps, pooled_rate_ratio=rr(tot["b"][0], tot["b"][1], tot["a"][0], tot["a"][1]),
                   pooled_eng_rate_ratio=rr(tot["be"][0], tot["b"][1], tot["ae"][0], tot["a"][1]),
                   before=dict(n=tot["b"][0], fh=round(tot["b"][1], 1), eng=tot["be"][0]), after=dict(n=tot["a"][0], fh=round(tot["a"][1], 1), eng=tot["ae"][0]))
print("washes", R["washes"]["pooled_rate_ratio"], R["washes"]["pooled_eng_rate_ratio"], R["washes"]["before"], R["washes"]["after"])
# HYDP installs on TJ107: HYD-101 per sortie in the 5 sorties before vs after each install
pin = m[(m.record_type == "COMPONENT_LIFE") & (m.part_no == "SYN-PN-HYDP") & (m.install_action == "INSTALL")]
p7 = pin[pin.tail_no == "TJ107"].sort_values("t_event")
s7 = so107.sortie_id.tolist(); t7 = so107.t_event_dt.tolist(); fired = set(h107.sortie_id)
bef = aft_ = nb_ = na_ = 0
for _, r in p7.iterrows():
    i = np.searchsorted(np.array(t7, dtype="datetime64[ns]"), np.datetime64(r.t_event_dt.tz_convert("UTC").tz_localize(None)))
    b5, a5 = s7[max(0, i - 5):i], s7[i:i + 5]
    bef += sum(s in fired for s in b5); nb_ += len(b5); aft_ += sum(s in fired for s in a5); na_ += len(a5)
R["pump_installs"] = dict(tj107_installs=int(p7.t_event_dt.nunique()), serials=int(p7.serial_no.nunique()), fleet_installs=int(pin.t_event_dt.nunique()),
                          before=dict(fired=bef, sorties=nb_), after=dict(fired=aft_, sorties=na_),
                          weeks=pin.assign(w=wk(pin.t_event_dt)).groupby("w").size().to_dict())
print("pumps", R["pump_installs"])
R["release"] = dict(dict_version="0.1.3", dict_hash=R["dict"], channels_changed=15, codes=104, channels=464,
                    first_ingest=str(m.t_ingest_dt.min())[:16])
json.dump(R, open(OUT + "assure_models_asof_20260622.json", "w"), indent=1, default=str)
print("ok")
