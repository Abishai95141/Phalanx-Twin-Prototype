"""Assemble the page data files for assurance.html, policies.html and provenance.html from the computed outputs.
Also computes the cnd-clf 2.3.0 gate evidence chain (blake2b over canonical JSON), the G2 shadow replay window and
the harmful-shift test used by the drift panel.
"""
import sys, json, hashlib
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *
from sklearn.metrics import brier_score_loss

A = "/Users/abishaikc/Phalanx-Solution/video/screens/assets/"
canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
b2 = lambda s, n=32: hashlib.blake2b(s.encode(), digest_size=n).hexdigest()
ld = lambda f: json.load(open(OUT + f))
cnd, mdl, pol, prov = ld("assure_cnd_asof_20260622.json"), ld("assure_models_asof_20260622.json"), ld("assure_policies_asof_20260622.json"), ld("assure_provenance_asof_20260622.json")
g3 = [ld(f"assure_g3_fork_2026-06-{d}.json") for d in ("01", "08", "15")]
J = pd.read_csv(OUT + "assure_cnd_jobs_asof_20260622.csv")
for c in ("t_open", "t_known"):
    J[c] = pd.to_datetime(J[c], utc=True).dt.tz_convert(IST)
L = J[J.label.notna()].copy(); L["label"] = L.label.astype(int)
ts = lambda s: pd.Timestamp(s, tz=IST)


def ece(y, p, b=10):
    k = np.clip((p * b).astype(int), 0, b - 1)
    return float(sum((k == i).sum() / len(y) * abs(y[k == i].mean() - p[k == i].mean()) for i in range(b) if (k == i).sum()))


# ---- G1 for 2.3.0 as it stood on 1 May: rolling-origin blocks Mar-Apr, labels known by 1 May 06:00
from sklearn.metrics import roc_auc_score
w = L[(L.t_open >= ts("2026-03-01")) & (L.t_open < ts("2026-05-01")) & (L.t_known < ts("2026-05-01 06:00"))]
G1 = dict(n=len(w), pos=int(w.label.sum()), auc=round(roc_auc_score(w.label, w.code_nf_asof), 3),
          brier=round(brier_score_loss(w.label, w.code_nf_asof), 3), brier_const=round(brier_score_loss(w.label, w.fleet_nf_asof), 3),
          ece=round(ece(w.label.values, w.code_nf_asof.values), 3))
# ---- G2 shadow replay: 14 daily epochs 2-15 May (cut-off 06:00), BIT jobs that became known in the prior 24 h
eps = [ts(f"2026-05-{d:02d} 06:00") for d in range(2, 16)]
sc = [int(((J.t_open <= e) & (J.t_open > e - pd.Timedelta(days=1))).sum()) for e in eps]
seen = set(L[L.t_known < ts("2026-05-01 06:00")].code)
ood = int(sum(((J.t_open <= e) & (J.t_open > e - pd.Timedelta(days=1)) & ~J.code.isin(seen)).sum() for e in eps))
G2 = dict(epochs=len(eps), scored=int(sum(sc)), max_per_epoch=int(max(sc)), outside_support=ood)
# ---- harmful-shift test: matured-label Brier in the latest block (opened 1 Jun ->) vs the G1 reference block
ref, cur = w, L[L.t_open >= ts("2026-06-01")]
rng = np.random.default_rng(20260622); db = []
for _ in range(4000):
    a = ref.sample(len(ref), replace=True, random_state=int(rng.integers(1 << 30)))
    b = cur.sample(len(cur), replace=True, random_state=int(rng.integers(1 << 30)))
    db.append(brier_score_loss(b.label, b.code_nf_asof) - brier_score_loss(a.label, a.code_nf_asof))
HS = dict(ref_brier=G1["brier"], cur_brier=round(brier_score_loss(cur.label, cur.code_nf_asof), 3), n_cur=len(cur),
          delta=round(float(np.mean(db)), 3), lower05=round(float(np.quantile(db, 0.05)), 3), upper95=round(float(np.quantile(db, 0.95)), 3), tolerance=0.05)
HS["harmful"] = HS["lower05"] > HS["tolerance"]  # alarm only when the risk increase is credibly above tolerance
print("G1", G1, "G2", G2, "HS", HS)

# ---- gate evidence chain for cnd-clf 2.3.0
g0 = mdl["g0"]
fk = [dict(epoch=g["epoch"][:10], pairs=g["n_pairs"], snapshot=g["snapshot_id"][:12],
           d_mc=[round(g["paired"]["mc"][k], 3) for k in ("mean", "ci_low", "ci_high")],
           d_iff=[round(g["paired"]["in_flight_failures"][k], 3) for k in ("mean", "ci_low", "ci_high")],
           d_mh=[round(g["paired"]["man_hours"][k], 1) for k in ("mean", "ci_low", "ci_high")]) for g in g3]
gates = [
    dict(g="G0", name="Data", t="2026-05-01T05:40+05:30", actor="AGENT:gate-svc", status="PASS",
         payload=dict(release_id=mdl["release_id"], fleet_files_verified=g0["fleet_files_verified"], mismatches=g0["fleet_files_mismatch"],
                      contract_hash=g0["contract_hashes"][0], dict_hash=DICT_HASH, restricted_reads=0, point_in_time="t_known < origin")),
    dict(g="G1", name="Offline backtest", t="2026-05-01T05:52+05:30", actor="AGENT:backtest", status="PASS",
         payload=dict(split="rolling-origin Mar, Apr · labels known by 1 May", **G1, ece_limit=0.05)),
    dict(g="G2", name="Shadow", t="2026-05-15T08:00+05:30", actor="AGENT:shadow", status="PASS",
         payload=dict(window="2-15 May", **G2)),
    dict(g="G3", name="Fork evaluation", t="2026-06-15T09:10+05:30", actor="AGENT:fork-svc", status="PASS",
         payload=dict(mode="belief", arms="status quo vs champion path", epochs=fk, epsilon_iff=0.2)),
    dict(g="G4", name="Human approval", t="2026-06-16T11:20+05:30", actor="HUMAN:QA-ENGINEER", status="SIGNED",
         payload=dict(author="HUMAN:PDM-ANALYST", independent=True)),
    dict(g="G5", name="Canary", t="2026-06-17T08:00+05:30", actor="AGENT:canary", status="RUNNING",
         payload=dict(scope="1 squadron · 14 epochs", epochs_done=6, rollback_to="cnd-clf 2.2.1@previous_champion",
                      harmful_shift=dict(delta_brier=HS["delta"], lower05=HS["lower05"], tol=HS["tolerance"], alarm=HS["harmful"]))),
]
prev = "0" * 64
for g in gates:
    body = dict(model="cnd-clf", version="2.3.0", gate=g["g"], t_valid=g["t"], actor=g["actor"], status=g["status"], payload=g["payload"])
    if g["g"] == "G4":
        body["payload"]["signs_head"] = prev
        g["signs"] = prev
    g["prev"] = prev
    g["hash"] = b2(prev + canon(body))
    g["bundle"] = b2(canon(g["payload"]), 16)
    prev = g["hash"]

ho = cnd["held_out"]
SEL, BR = "logreg · one-hot codes", "per-code base rate"
ASSURE = dict(
    g1=G1, g2=G2, harmful=HS, gates=gates, forks=fk,
    held_out=dict(n=ho["n_test"], pos=ho["pos_test"], n_train=ho["n_train"],
                  champion={k: ho[BR][k] for k in ("auc", "brier", "ece")}, challenger={k: ho[SEL][k] for k in ("auc", "brier", "ece")},
                  gbm={k: ho["gbm+platt · as-of priors"][k] for k in ("auc", "brier", "ece")},
                  cal_champion=ho[BR]["calibration"], cal_challenger=ho[SEL]["calibration"],
                  vs=cnd["held_out_vs_baseline"], tail_grouped={k: cnd["tail_grouped"][k] for k in (SEL, BR)},
                  folds=[dict(origin=f["origin"], role=f["role"], n=f["n_test"], ch=f[BR]["brier"], cl=f[SEL]["brier"], ch_auc=f[BR]["auc"], cl_auc=f[SEL]["auc"]) for f in cnd["rolling_origin"]],
                  const_brier=round(brier_score_loss(L[L.t_open >= ts("2026-05-01")].label, L[L.t_open >= ts("2026-05-01")].fleet_nf_asof), 3)),
    population=cnd["population"], selection=cnd["selection"], artefact=cnd["artefact_sha256"], feature_spec=cnd["feature_spec_sha256"],
    train_set=cnd["train_set_blake2b"],
    leadtime={k: mdl["leadtime"][k] for k in ("n", "closed", "censored", "orphan_excluded", "closed_only", "km_median", "km_p75", "km_p90", "step", "closed_T", "censor_times", "aft_curve", "held_out", "s_at", "s_ci_at")},
    aft={k: v for k, v in mdl["leadtime"]["aft"].items() if k != "params"},
    tyres={k: v for k, v in mdl["tyres"].items() if k != "backtest"}, hazard=mdl["hazard"], isolation=mdl["isolation"],
    drift=mdl["drift"], washes={k: v for k, v in mdl["washes"].items() if k != "events"},
    wash_events=[dict(tail=e["tail"], t=e["t"], order_id=e["order_id"], issuer=e["issuer"]) for e in mdl["washes"]["events"]],
    pumps=mdl["pump_installs"], release=dict(id=mdl["release_id"], dict_hash=DICT_HASH, contract=CONTRACT_HASH, first_ingest=mdl["release"]["first_ingest"]),
)
open(A + "data-assurance.js", "w").write("window.PHX_ASSURE = " + json.dumps(ASSURE, default=str) + ";\n")

POLICIES = dict(policies=pol["policies"], engine=pol["engine"], input=pol["input"], input_sources=pol["input_sources"],
                result=pol["result"], trace=pol["trace"]["dt"], trace_nodes={k: dict(order=v["order"], perf=v["performance"]) for k, v in pol["trace"].items()},
                engine_performance=pol["engine_performance"], timing=pol["timing"], trace_hash=pol["trace_blake2b"],
                row_checks=pol["row_checks"], static=pol["static"], lint=pol["lint"], golden=pol["golden"],
                counterfactual=pol["counterfactual"], counterfactual2=pol["counterfactual2"],
                jdm=json.load(open("/Users/abishaikc/Phalanx-Solution/video/data/policies/P-DEC-01.jdm.json")), forks=fk)
open(A + "data-policies.js", "w").write("window.PHX_POLICIES = " + json.dumps(POLICIES, default=str) + ";\n")

PROV = dict(prov, gates_head=gates[-1]["hash"])
open(A + "data-provenance.js", "w").write("window.PHX_PROV = " + json.dumps(PROV, default=str) + ";\n")
print("wrote", [len(open(A + f).read()) for f in ("data-assurance.js", "data-policies.js", "data-provenance.js")])
for g in gates:
    print(g["g"], g["status"], g["hash"][:12], g["bundle"][:12])
