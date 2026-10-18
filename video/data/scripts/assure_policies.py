"""Policies screen: write the five JDM policies, evaluate P-DEC-01 with zen-engine (trace on) for the TJ107 HYD-101
issue as of the 22 Jun 06:00 snapshot, measure evaluation time, run the static analysis (gap/overlap over an input
grid, unreachable rows) and the determinism lint, run golden cases, and compute policy_version strings
"<name>/<semver>+jdm.<sha256[:12]>" from the bytes of each JDM file.
"""
import sys, json, hashlib, time, itertools, re, statistics, platform
sys.path.insert(0, "/Users/abishaikc/Phalanx-Solution/video/data/scripts")
from assure_load import *
import zen
from importlib.metadata import version

PDIR = "/Users/abishaikc/Phalanx-Solution/video/data/policies/"


def node(i, t, name, x, content=None):
    n = {"id": i, "type": t, "name": name, "position": {"x": x, "y": 120}}
    if content is not None:
        n["content"] = content
    return n


def table(name, hit, inputs, outputs, rules):
    ins = [{"id": i, "name": nm, "field": f} for i, nm, f in inputs]
    outs = [{"id": i, "name": nm, "field": f} for i, nm, f in outputs]
    rr = []
    for r in rules:
        row = {"_id": r["_id"]}
        for i, _, _ in inputs:
            row[i] = r.get(i, "")
        for i, _, _ in outputs:
            row[i] = r.get(i, "")
        rr.append(row)
    return {"contentType": "application/vnd.gorules.decision",
            "nodes": [node("in", "inputNode", "issue", 0),
                      node("dt", "decisionTableNode", name, 320, {"hitPolicy": hit, "inputs": ins, "outputs": outs, "rules": rr}),
                      node("out", "outputNode", "rec", 640)],
            "edges": [{"id": "e1", "sourceId": "in", "targetId": "dt", "type": "edge"},
                      {"id": "e2", "sourceId": "dt", "targetId": "out", "type": "edge"}]}


# ---------------------------------------------------------------- P-DEC-01 exactly as doc 07 (abridged JDM)
P_DEC_01_IN = [("sev", "Severity", "severity"), ("job", "Job status", "job.status"), ("n10", "Occurrences 10 d", "occ_10d"),
               ("cons", "Consecutive flights", "consec_flights"), ("co", "Corroborated", "corroborated"),
               ("cnd", "Code no-fault rate", "code.nofault_rate")]
P_DEC_01_OUT = [("act", "Action", "rec.action"), ("band", "Band", "rec.band"), ("why", "Rationale", "rec.rationale_id")]
P_DEC_01_RULES = [
    {"_id": "r1", "sev": "'WARNING'", "n10": ">= 2", "act": "'TROUBLESHOOT'", "band": "'P1'", "why": "'PFL_WARNING_RECURS'"},
    {"_id": "r2", "job": "'DEFERRED'", "n10": ">= 2", "co": "true", "act": "'TROUBLESHOOT'", "band": "'P2'", "why": "'RECUR_CORROBORATED'"},
    {"_id": "r3", "job": "'DEFERRED'", "cons": ">= 3", "act": "'TROUBLESHOOT'", "band": "'P2'", "why": "'PERSIST_3_FLIGHTS'"},
    {"_id": "r4", "job": "'DEFERRED'", "n10": ">= 2", "cnd": "< 0.6", "act": "'TROUBLESHOOT'", "band": "'P3'", "why": "'RECUR_LOW_NOFAULT_CODE'"},
    {"_id": "r5", "job": "'DEFERRED'", "n10": ">= 2", "act": "'MONITOR'", "band": "'P4'", "why": "'RECUR_NOFAULT_DOMINATED_REVIEW'"},
    {"_id": "r6", "act": "'NONE'", "band": "'P4'", "why": "'NO_RULE'"},
]
POL = {
    "P-DEC-01": dict(semver="1.4.0", title="Recurring deferred BIT code", layer="L3", hit="first",
                     jdm=table("P-DEC-01 recurring deferred BIT", "first", P_DEC_01_IN, P_DEC_01_OUT, P_DEC_01_RULES)),
    "P-DEC-02": dict(semver="0.3.0", title="Engine serial exceedances → borescope", layer="L3", hit="first",
                     jdm=table("P-DEC-02 engine exceedance recurrence", "first",
                               [("ex30", "Exceedances 30 d (same engine serial)", "engine.exceedances_30d")],
                               [("act", "Action", "rec.action"), ("par", "Type", "rec.params.type"), ("band", "Band", "rec.band"), ("why", "Rationale", "rec.rationale_id")],
                               [{"_id": "r1", "ex30": ">= 2", "act": "'INSPECT'", "par": "'BORESCOPE'", "band": "'P2'", "why": "'ENG_EXCEED_RECUR_30D'"},
                                {"_id": "r2", "act": "'NONE'", "band": "'P4'", "why": "'NO_RULE'"}])),
    "P-ORG-01": dict(semver="2.1.0", title="MEL-like deferral limits", layer="L2", hit="first",
                     jdm=table("P-ORG-01 deferral limits", "first",
                               [("gr", "Grounding defect", "defect.grounding"), ("sev", "Severity", "severity"), ("fl", "Fault list", "fault_list"),
                                ("me", "Mission-essential", "mission_essential")],
                               [("dfr", "Deferrable", "limit.deferrable"), ("fh", "Max FH", "limit.max_fh"), ("why", "Rationale", "limit.rationale_id")],
                               [{"_id": "r1", "gr": "true", "dfr": "false", "fh": "0", "why": "'GROUNDING_NOT_DEFERRABLE'"},
                                {"_id": "r2", "sev": "'WARNING'", "dfr": "false", "fh": "0", "why": "'WARNING_NOT_DEFERRABLE'"},
                                {"_id": "r3", "sev": "'CAUTION'", "me": "true", "dfr": "true", "fh": "10", "why": "'CAUTION_ME_10FH'"},
                                {"_id": "r4", "fl": "'PFL'", "me": "true", "dfr": "true", "fh": "10", "why": "'PFL_ME_10FH'"},
                                {"_id": "r5", "sev": "'ADVISORY'", "dfr": "true", "fh": "25", "why": "'ADVISORY_25FH'"},
                                {"_id": "r6", "fl": "'MFL'", "dfr": "true", "fh": "25", "why": "'MFL_25FH'"},
                                {"_id": "r7", "dfr": "true", "fh": "10", "why": "'DEFAULT_10FH'"}])),
    "P-ORG-02": dict(semver="1.2.0", title="Cannibalise only from NMC donor", layer="L2", hit="first",
                     jdm=table("P-ORG-02 cannibalisation", "first",
                               [("dn", "Donor already NMC", "donor.nmc"), ("awp", "AWP days", "job.awp_days"), ("mn", "AWP minimum", "policy.awp_min_days")],
                               [("act", "Action", "rec.action"), ("why", "Rationale", "rec.rationale_id")],
                               [{"_id": "r1", "dn": "true", "awp": ">= policy.awp_min_days", "act": "'CANNIBALISE'", "why": "'DONOR_NMC_AWP_MIN'"},
                                {"_id": "r2", "act": "'EXPEDITE_SPARES'", "why": "'NO_NMC_DONOR_EXPEDITE'"}])),
    "P-ORG-03": dict(semver="1.1.0", title="Servicing deferral = HUMAN draft", layer="L2", hit="first",
                     jdm=table("P-ORG-03 servicing deferral", "first",
                               [("rq", "Deferral requested", "request.defer_servicing"), ("ext", "Extension %", "request.extension_pct")],
                               [("mode", "Mode", "rec.issuer"), ("st", "Status", "rec.status"), ("why", "Rationale", "rec.rationale_id")],
                               [{"_id": "r1", "rq": "true", "ext": "> 20", "mode": "'HUMAN'", "st": "'BLOCKED_L1'", "why": "'EXT_GT_20PCT_INVARIANT'"},
                                {"_id": "r2", "rq": "true", "mode": "'HUMAN'", "st": "'DRAFT'", "why": "'HUMAN_SIGNED_DRAFT_ONLY'"},
                                {"_id": "r3", "mode": "'NONE'", "st": "'NONE'", "why": "'NO_RULE'"}])),
}

R = dict(engine=dict(package="zen-engine", version=version("zen-engine"), python=platform.python_version()), policies={})
for name, p in POL.items():
    blob = json.dumps(p["jdm"], indent=2, sort_keys=False).encode() + b"\n"
    open(PDIR + f"{name}.jdm.json", "wb").write(blob)
    sha = hashlib.sha256(blob).hexdigest()
    R["policies"][name] = dict(title=p["title"], layer=p["layer"], semver=p["semver"], sha256=sha,
                               policy_version=f"{name}/{p['semver']}+jdm.{sha[:12]}", bytes=len(blob),
                               rows=len(p["jdm"]["nodes"][1]["content"]["rules"]))
    print(R["policies"][name]["policy_version"])

# ---------------------------------------------------------------- the TJ107 HYD-101 issue input, from the data
ev = asof(rd("events.bit_faults")); m = asof(rd("maint.records"))
h = ev[(ev.tail_no == "TJ107") & (ev.event_code == "HYD-101")]
occ10 = int(h[h.t_ingest_dt > SNAP - pd.Timedelta(days=10)].sortie_id.nunique())
so = m[(m.tail_no == "TJ107") & (m.record_type == "SORTIE")].sort_values("t_event")
fired, consec = set(h.sortie_id), 0
for s in so.sortie_id:
    consec = consec + 1 if s in fired else 0
co = pd.read_csv(OUT + "code_outcomes_asof_20260622.csv").set_index("code").loc["HYD-101"]
nf = (int(co["AT-CND"]) + int(co["AT-ADM"])) / int(co["n"])
issue = {"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": occ10, "consec_flights": consec,
         "corroborated": False, "code": {"nofault_rate": round(nf, 4)}}
R["input"] = issue
R["input_sources"] = dict(occ_10d=f"HYD-101 BIT events on TJ107 with t_ingest in (12 Jun 06:00, 22 Jun 06:00]: {occ10}",
                          consec_flights=f"trailing TJ107 sorties with HYD-101: {consec} (of {len(so)} sorties, fired on {int(so.sortie_id.isin(fired).sum())})",
                          nofault=f"fleet HYD-101 jobs: {int(co['AT-CND'])} CND + {int(co['AT-ADM'])} ADM of {int(co['n'])}")

eng = zen.ZenEngine()
pdec = eng.create_decision(json.dumps(POL["P-DEC-01"]["jdm"]))
t0 = time.perf_counter(); first = pdec.evaluate(issue, {"trace": True}); cold = time.perf_counter() - t0
ts = []
for _ in range(2000):
    t0 = time.perf_counter(); pdec.evaluate(issue, {"trace": True}); ts.append(time.perf_counter() - t0)
res = pdec.evaluate(issue, {"trace": True})
R["trace"] = res["trace"]; R["result"] = res["result"]; R["engine_performance"] = res["performance"]
R["timing"] = dict(cold_ms=round(cold * 1e3, 3), warm_median_us=round(statistics.median(ts) * 1e6, 1),
                   warm_p95_us=round(sorted(ts)[int(0.95 * len(ts))] * 1e6, 1), runs=len(ts))
canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
tr_core = {k: {kk: v[kk] for kk in ("id", "input", "output", "traceData")} for k, v in res["trace"].items()}
R["trace_blake2b"] = hashlib.blake2b(canon(tr_core).encode(), digest_size=32).hexdigest()
print("result", res["result"], "matched", res["trace"]["dt"]["traceData"]["rule"]["_id"], R["timing"], res["performance"])

# rows the input fails (why not r1, r2)
def unary(expr, val):
    if expr == "":
        return True
    return bool(zen.evaluate_unary_expression(expr, {"$": val}))
flat = {"severity": issue["severity"], "job.status": "DEFERRED", "occ_10d": occ10, "consec_flights": consec,
        "corroborated": False, "code.nofault_rate": issue["code"]["nofault_rate"]}
fld = {i: f for i, _, f in P_DEC_01_IN}
R["row_checks"] = []
for r in P_DEC_01_RULES:
    cells = []
    for i, _, f in P_DEC_01_IN:
        e = r.get(i, "")
        cells.append(dict(input=i, expr=e, ok=unary(e, flat[f])))
    R["row_checks"].append(dict(row=r["_id"], match=all(c["ok"] for c in cells), cells=cells))

# ---------------------------------------------------------------- static analysis: gap / overlap over an input grid
grid = dict(severity=["ADVISORY", "CAUTION", "WARNING"], job=["OPEN", "DEFERRED", "IN_WORK", "CLOSED"],
            occ_10d=[0, 1, 2, 3, 5, 9], consec_flights=[0, 1, 2, 3, 4, 34], corroborated=[False, True],
            nofault=[0.0, 0.3, 0.59, 0.6, 0.61, 0.9, 1.0])
coll = json.loads(json.dumps(POL["P-DEC-01"]["jdm"])); coll["nodes"][1]["content"]["hitPolicy"] = "collect"
dcoll = eng.create_decision(json.dumps(coll))
rid_of = {r["why"].strip("'"): r["_id"] for r in P_DEC_01_RULES}
gaps = overl = 0; winners = {r["_id"]: 0 for r in P_DEC_01_RULES}; matched_any = {r["_id"]: 0 for r in P_DEC_01_RULES}
pairs = {}
N = 0
t0 = time.perf_counter()
for sev, job, n10, cons, cor, cnd in itertools.product(*grid.values()):
    inp = {"severity": sev, "job": {"status": job}, "occ_10d": n10, "consec_flights": cons, "corroborated": cor, "code": {"nofault_rate": cnd}}
    out = dcoll.evaluate(inp)["result"]
    rows = [rid_of[o["rec"]["rationale_id"]] for o in out]
    N += 1
    if not rows:
        gaps += 1; continue
    for r in rows:
        matched_any[r] += 1
    winners[rows[0]] += 1
    non_default = [r for r in rows if r != "r6"]
    if len(non_default) > 1:
        overl += 1
        k = "+".join(non_default); pairs[k] = pairs.get(k, 0) + 1
sa_s = time.perf_counter() - t0
R["static"] = dict(grid={k: v for k, v in grid.items()}, combinations=N, gaps=gaps, overlaps=overl,
                   overlap_sets=dict(sorted(pairs.items(), key=lambda kv: -kv[1])), winners=winners,
                   unreachable=[r for r, c in winners.items() if c == 0], seconds=round(sa_s, 2),
                   note="hit policy first: overlaps are resolved by row order; every row wins somewhere")
print("static", {k: v for k, v in R["static"].items() if k != "grid"})

# ---------------------------------------------------------------- determinism lint over all five JDMs
BANNED = [(r"\bd\(\s*\)", "zero-argument d() reads the clock"), (r"\bisToday\s*\(", "isToday() reads the clock"),
          (r"\bnow\s*\(", "now()"), (r"\brand(om)?\s*\(", "random()"), (r"Math\.random", "Math.random")]
lint = dict(files=0, nodes=0, expressions=0, function_nodes=0, violations=[])
for name in POL:
    j = json.load(open(PDIR + f"{name}.jdm.json")); lint["files"] += 1
    for n in j["nodes"]:
        lint["nodes"] += 1
        if n["type"] in ("functionNode", "customNode"):
            lint["function_nodes"] += 1; lint["violations"].append(f"{name}:{n['id']} {n['type']}")
        c = n.get("content") or {}
        for r in c.get("rules", []):
            for k, v in r.items():
                if k == "_id" or v == "":
                    continue
                lint["expressions"] += 1
                for pat, why in BANNED:
                    if re.search(pat, v):
                        lint["violations"].append(f"{name}:{r['_id']}:{k} {why}")
R["lint"] = lint
print("lint", lint)

# ---------------------------------------------------------------- golden cases (TESTED stage)
gold = [({"severity": "WARNING", "job": {"status": "OPEN"}, "occ_10d": 2, "consec_flights": 1, "corroborated": False, "code": {"nofault_rate": 0.4}}, "r1"),
        ({"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": 3, "consec_flights": 1, "corroborated": True, "code": {"nofault_rate": 0.9}}, "r2"),
        ({"severity": "CAUTION", "job": {"status": "DEFERRED"}, "occ_10d": 1, "consec_flights": 3, "corroborated": False, "code": {"nofault_rate": 0.9}}, "r3"),
        ({"severity": "ADVISORY", "job": {"status": "DEFERRED"}, "occ_10d": 2, "consec_flights": 1, "corroborated": False, "code": {"nofault_rate": 0.59}}, "r4"),
        ({"severity": "ADVISORY", "job": {"status": "DEFERRED"}, "occ_10d": 2, "consec_flights": 2, "corroborated": False, "code": {"nofault_rate": 0.6}}, "r5"),
        ({"severity": "ADVISORY", "job": {"status": "CLOSED"}, "occ_10d": 0, "consec_flights": 0, "corroborated": False, "code": {"nofault_rate": 0.9}}, "r6")]
gp = sum(pdec.evaluate(i, {"trace": True})["trace"]["dt"]["traceData"]["rule"]["_id"] == want for i, want in gold)
R["golden"] = dict(cases=len(gold), passed=int(gp))
# counterfactual: smallest change that flips the action (consec_flights 3 -> 2)
cf = dict(issue); cf["consec_flights"] = 2
R["counterfactual"] = dict(change="consec_flights 34 → 2", result=pdec.evaluate(cf)["result"])
cf2 = dict(issue); cf2["code"] = {"nofault_rate": 0.55}; cf2["consec_flights"] = 2
R["counterfactual2"] = dict(change="consec_flights 2 and nofault 0.55", result=pdec.evaluate(cf2)["result"])
print("golden", R["golden"], R["counterfactual"], R["counterfactual2"])
json.dump(R, open(OUT + "assure_policies_asof_20260622.json", "w"), indent=1, default=str)
