"""Provenance screen: "Why was this order issued?" for TJ107 TROUBLESHOOT HYD-101 at epoch 20260622T0800.

Computes (all deterministic, re-run by --replay in a fresh process with the input rows shuffled):
- snapshot hash: per topic, blake2b-256 of the sorted scoped record ids ("<tail>:<record_id>") with t_ingest <= 06:00;
  snapshot = blake2b-256 over "<topic>:<count>:<topic hash>" lines in topic order;
- order id per doc 07: phx:<rule>:<policy semver>:<epoch>:<tail>:<action>:<blake2b8(canonical params | sorted evidence)>;
- the Lifecycle Event Log chain: hash_i = blake2b-256(prev_hash_i || canonical_json(event_i)), canonical JSON =
  sorted keys, no whitespace, UTF-8.
"""
import sys, json, hashlib, random, subprocess
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *

canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
b2 = lambda s, n=32: hashlib.blake2b(s.encode() if isinstance(s, str) else s, digest_size=n).hexdigest()
TOPICS = ["events.bit_faults", "events.cautions", "maint.records", "orders.commands", "orders.status", "usage.counters"]
REPLAY = "--replay" in sys.argv


def core(shuffle_seed=None):
    frames = {t: asof(rd(t)) for t in TOPICS}
    lines, counts = [], {}
    for t in TOPICS:
        df = frames[t]
        scope = df["tail_no"] if "tail_no" in df else (df["target_tail_no"] if "target_tail_no" in df else pd.Series(["-"] * len(df), index=df.index))
        ids = list((scope.fillna("-") + ":" + df.rid))
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(ids)
        h = b2("\n".join(sorted(ids)))
        counts[t] = dict(n=len(ids), hash=h); lines.append(f"{t}:{len(ids)}:{h}")
    snap = b2("\n".join(lines))
    ev = frames["events.bit_faults"]
    h = ev[(ev.tail_no == "TJ107") & (ev.event_code == "HYD-101")].sort_values(["t_ingest", "rid"])
    if shuffle_seed is not None:
        h = h.sample(frac=1, random_state=shuffle_seed).sort_values(["t_ingest", "rid"])
    evid = h.tail(6)
    params = {"code": "HYD-101"}
    pol = json.load(open(OUT + "assure_policies_asof_20260622.json"))
    semver = pol["policies"]["P-DEC-01"]["semver"]
    # re-derive the policy input from the frames and re-evaluate the JDM with zen (trace on)
    import zen
    so = frames["maint.records"]; so = so[(so.tail_no == "TJ107") & (so.record_type == "SORTIE")].sort_values("t_event")
    fired, consec = set(h.sortie_id), 0
    for s_ in so.sortie_id:
        consec = consec + 1 if s_ in fired else 0
    inp = dict(pol["input"]); inp["occ_10d"] = int(h[h.t_ingest_dt > SNAP - pd.Timedelta(days=10)].sortie_id.nunique()); inp["consec_flights"] = consec
    jdm = open("/Users/abishaikc/Phalanx-Solution/video/data/policies/P-DEC-01.jdm.json").read()
    jsha = hashlib.sha256(jdm.encode()).hexdigest()
    res = zen.ZenEngine().create_decision(jdm).evaluate(inp, {"trace": True})
    tr_core = {k: {kk: v[kk] for kk in ("id", "input", "output", "traceData")} for k, v in res["trace"].items()}
    trace_h = b2(canon(tr_core))
    digest = b2(canon({"parameters": params, "evidence": sorted(evid.rid)}), 8)
    oid = f"phx:P-DEC-01:{semver}:20260622T0800:TJ107:TROUBLESHOOT:{digest}"
    return dict(snapshot=snap, topics=counts, order_id=oid, params=params,
                evidence=[dict(rid=r.rid, sortie=r.sortie_id, t_occ=str(r.t_occurrence_dt)[:16], t_ingest=str(r.t_ingest_dt)[:19],
                               persistence=int(r.persistence_count)) for _, r in evid.iterrows()],
                policy_version=f"P-DEC-01/{semver}+jdm.{jsha[:12]}", trace_blake2b=trace_h, matched=res["trace"]["dt"]["traceData"]["rule"]["_id"])


if REPLAY:
    print(json.dumps(core(shuffle_seed=int(sys.argv[-1]))))
    sys.exit()

C = core()
print("snapshot", C["snapshot"], C["order_id"])
# ---------------------------------------------------------------- inputs for the chain
man_sha = hashlib.sha256(open(ROOT + "MANIFEST.json", "rb").read()).hexdigest()
man = json.load(open(ROOT + "MANIFEST.json"))
last = C["evidence"][-1]
batch_file = [f for f in files("events.bit_faults") if "TJ107-20260618T1430" in f][0]
rel = batch_file.replace(ROOT, "")
batch_sha = hashlib.sha256(open(batch_file, "rb").read()).hexdigest()
assert batch_sha == man["files"][rel]["sha256"]
pol = json.load(open(OUT + "assure_policies_asof_20260622.json"))
cnd = json.load(open(OUT + "assure_cnd_asof_20260622.json"))
S1 = json.load(open(OUT + "forks/scenario_S1.json"))
bel = S1["modes"]["belief"]["kpis"]
fork_core = dict(snapshot_id=S1["snapshot_id"], orders=[{k: o[k] for k in ("action", "parameters", "evidence", "target_tail_no", "t_issued")} for o in S1["orders"]],
                 paired={k: bel[k]["paired_difference_treatment_minus_status_quo"] for k in sorted(bel)})
fork_id = "fork:" + b2(canon(fork_core), 16)
d_mc = bel["mc"]["paired_difference_treatment_minus_status_quo"]; d_mh = bel["man_hours"]["paired_difference_treatment_minus_status_quo"]
d_if = bel["in_flight_failures"]["paired_difference_treatment_minus_status_quo"]
co = pd.read_csv(OUT + "code_outcomes_asof_20260622.csv").set_index("code").loc["HYD-101"]
mdl = json.load(open(OUT + "assure_models_asof_20260622.json"))
iss_id = "iss:TJ107:HYD-101:20260302"
rec_id = "rec:20260622T0800:TJ107:HYD-101:01"
CONTRACT, DICT = CONTRACT_HASH, DICT_HASH
inp = pol["input"]

E = []
def ev(type_, stream, t_valid, actor, payload, refs=None, cause=None):
    e = dict(event_id=f"lel:{len(E) + 1:04d}", stream=stream, seq=sum(1 for x in E if x["stream"] == stream) + 1, type=type_,
             t_valid=t_valid, actor=actor, causation_id=cause, correlation_id="epoch:20260622T0800", refs=refs or {}, payload=payload)
    E.append(e); return e["event_id"]

e1 = ev("RELEASE_ADOPTED", "release:v0.9", "2026-01-05T05:30+05:30", "HUMAN:DATA-STEWARD",
        dict(state="ADOPTED", maturity="PREVIEW", files=len(man["files"])),
        dict(release_id=man_sha, contract_hash=CONTRACT, dict_hash=DICT, code_commit=man["code_commit"]))
e2 = ev("BATCH_ADMITTED", "batch:" + batch_sha[:12], last["t_ingest"].replace(" ", "T"), "AGENT:gate-svc",
        dict(states=["CHECKSUM_OK", "SCHEMA_OK", "CONTENT_VALID", "ADMITTED"], topic="events.bit_faults", sortie=last["sortie"]),
        dict(file_sha256=batch_sha, release_id=man_sha, contract_hash=CONTRACT), e1)
e3 = ev("SNAPSHOT_SEALED", "epoch:20260622T0800", "2026-06-22T06:00+05:30", "AGENT:epoch-run",
        dict(cutoff="t_ingest <= 2026-06-22T06:00+05:30", records={t: v["n"] for t, v in C["topics"].items()}),
        dict(snapshot_hash=C["snapshot"], release_id=man_sha), e2)
e4 = ev("EVIDENCE_LINKED", iss_id, "2026-06-22T06:01+05:30", "AGENT:triage",
        dict(code="HYD-101", all_ingested_before_cutoff=all(x["t_ingest"] <= "2026-06-22 06:00" for x in C["evidence"])),
        dict(record_ids=[x["rid"] for x in C["evidence"]]), e3)
e5 = ev("FINDING", "finding:TJ107:HYD-101", "2026-06-22T06:02+05:30", "AGENT:diagnostics",
        dict(nofault=f"{int(co['AT-CND']) + int(co['AT-ADM'])}/{int(co['n'])}", confirmed=f"0/{int(co['n'])}",
             isolation="indication path likely", pump_changes_tj107=28),
        dict(model_version="cnd-clf 2.3.0@champion", feature_spec_hash=cnd["feature_spec_sha256"][:16]), e4)
e6 = ev("ISSUE_TRIAGED", iss_id, "2026-06-22T06:02+05:30", "AGENT:triage",
        dict(state="TRIAGED", band="P2", d8="standing · nuisance review", consec_flights=inp["consec_flights"], occ_10d=inp["occ_10d"]),
        dict(), e5)
e7 = ev("POLICY_EVALUATED", "policy:P-DEC-01", "2026-06-22T06:03+05:30", "AGENT:policy",
        dict(engine=f"zen-engine {pol['engine']['version']}", hit_policy="first", matched="r3", result=pol["result"]["rec"],
             d8="CHANGE_MONITORING_CONFIG draft (HUMAN-only)"),
        dict(policy_version=pol["policies"]["P-DEC-01"]["policy_version"], trace_hash=pol["trace_blake2b"][:16]), e6)
e8 = ev("FORK_EVALUATED", "fork:S1", "2026-06-22T06:04+05:30", "AGENT:fork-svc",
        dict(mode="belief", pairs=d_mc["n"], d_mc=[round(d_mc["mean"], 3), round(d_mc["ci_low"], 3), round(d_mc["ci_high"], 3)],
             d_man_hours=[round(d_mh["mean"], 1), round(d_mh["ci_low"], 1), round(d_mh["ci_high"], 1)],
             d_in_flight_failures=[round(d_if["mean"], 3), round(d_if["ci_low"], 3), round(d_if["ci_high"], 3)]),
        dict(fork_result_id=fork_id, fork_snapshot_id=S1["snapshot_id"]), e7)
e9 = ev("RECOMMENDATION_PROPOSED", rec_id, "2026-06-22T06:05+05:30", "AGENT:planner",
        dict(action="TROUBLESHOOT", params=C["params"], band="P2", issue_state="PROPOSED", order_id=C["order_id"]),
        dict(policy_version=pol["policies"]["P-DEC-01"]["policy_version"], model_version="cnd-clf 2.3.0", fork_result_id=fork_id), e8)
e10 = ev("APPROVED", rec_id, "2026-06-22T06:41+05:30", "HUMAN:SEO",
         dict(decision="APPROVE", mode="consent", modified=False), dict(), e9)
e11 = ev("ORDER_ACCEPTED", "order:" + C["order_id"], "2026-06-22T08:00+05:30", "AGENT:gateway",
         dict(issuer_kind="AGENT", t_issued="2026-06-22T08:00+05:30", verdict="ACCEPTED", status_seq=0),
         dict(order_id=C["order_id"], record_ids=[x["rid"] for x in C["evidence"]]), e10)
e12 = ev("ORDER_STATUS", "order:" + C["order_id"], "2026-06-22T08:00+05:30", "AGENT:gateway",
         dict(status="QUEUED", status_seq=1), dict(order_id=C["order_id"]), e11)
e13 = ev("LABEL_PENDING", "label:" + rec_id, "2026-06-22T08:00+05:30", "AGENT:learning",
         dict(state="PENDING", awaits="result_record_ids · job close · shop finding", t_known=None), dict(order_id=C["order_id"]), e12)

prev = "0" * 64
for e in E:
    e["prev_hash"] = prev
    e["hash"] = b2(prev + canon({k: v for k, v in e.items() if k not in ("hash",)}))
    prev = e["hash"]
print("chain head", prev)

# ---------------------------------------------------------------- replay in fresh processes, inputs shuffled
py = sys.executable
reps = []
for seed in (11, 29):
    out = subprocess.run([py, "-W", "ignore", __file__, "--replay", str(seed)], capture_output=True, text=True, check=True).stdout
    r = json.loads(out.strip().splitlines()[-1])
    reps.append(dict(seed=seed, snapshot_equal=r["snapshot"] == C["snapshot"], order_equal=r["order_id"] == C["order_id"],
                     trace_equal=r["trace_blake2b"] == pol["trace_blake2b"], policy_equal=r["policy_version"] == pol["policies"]["P-DEC-01"]["policy_version"], head_inputs=r["matched"]))
print("replay", reps)
R = dict(order_id=C["order_id"], params=C["params"], evidence=C["evidence"], snapshot=C["snapshot"], topics=C["topics"],
         release_id=man_sha, batch=dict(file=rel, sha256=batch_sha), fork_id=fork_id, chain=E, head=prev, replay=reps,
         policy_version=C["policy_version"], order_digest_rule="blake2b-64(canonical_json({parameters, sorted evidence record_ids}))")
json.dump(R, open(OUT + "assure_provenance_asof_20260622.json", "w"), indent=1, default=str)
