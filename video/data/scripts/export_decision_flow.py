"""Export everything computed for the decision flow (board, workbench, epoch) to video/data/decision_flow.json.

Inputs: decision_screens_asof_20260622.json (decision_screens_data.py), order_dryrun_20260622.json (order_dryrun.py),
optional forks/results.json. Pure stdlib. Run: python3 video/data/scripts/export_decision_flow.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = json.loads((ROOT / "data" / "decision_screens_asof_20260622.json").read_text())
DRY = {c["order_id"]: c for c in json.loads((ROOT / "data" / "order_dryrun_20260622.json").read_text())["checks"]}
RES_P = ROOT / "data" / "forks" / "results.json"
OUT = ROOT / "data" / "decision_flow.json"


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def iv(p):
    return {"mean": round(p[0], 4), "lo": round(p[1], 4), "hi": round(p[2], 4)}


t7 = D["tj107"]
SEMVER = {"P-DEC-01": "1.4.0", "P-ORG-02": "1.2.0", "P-SPR-01": "1.0.0"}

# ---------------------------------------------------------------- orders (re-derive digest to prove the id)
orders = []
for o in D["orders"]:
    digest_input = canon({"parameters": o["parameters"], "evidence": sorted(o["evidence"])})
    dg = hashlib.blake2b(digest_input.encode(), digest_size=8).hexdigest()
    assert o["order_id"].endswith(dg)
    orders.append({
        "order_id": o["order_id"], "item": o["item"], "band": o["band"], "tail": o["tail"],
        "rule": o["rule"], "rule_row": o["row"], "policy_semver": SEMVER[o["rule"]], "policy_version": o["policy_version"],
        "action": o["action"], "parameters": o["parameters"], "canonical_parameters": canon(o["parameters"]),
        "evidence_sorted": sorted(o["evidence"]), "evidence_n": len(o["evidence"]),
        "evidence_latest_t_ingest_ist": o["evidence_latest_ingest"], "evidence_all_ingested_by_snapshot": o["evidence_all_ingested"],
        "digest_input_canonical_json": digest_input, "blake2b8": dg,
        "issuer_kind": o["issuer_kind"], "issuer_id": o["issuer_id"], "priority": o["priority"],
        "target_tail_no": o["target_tail_no"], "target_base": o["target_base"],
        "t_issued": "2026-06-22T08:00+05:30 (1782095400000000000 ns UTC)", "t_effective": "same as t_issued",
        "approval_mode": "HUMAN-only (draft, needs signature)" if o["issuer_kind"] == "HUMAN" else "consent",
        "dry_run": DRY[o["order_id"]],
    })

# ---------------------------------------------------------------- board items
items = []
for it in D["items"]:
    x = {k: it.get(k) for k in ("id", "band", "tail", "code", "title", "sev", "reason", "basis", "C", "U", "u_basis", "conf",
                                "action", "params", "rule", "row", "rationale", "priority", "target_tail_no", "target_base",
                                "auth", "mode", "order_id")}
    x["p_true"] = iv(it["p"]) if it.get("p") else None
    x["p_true_n_jobs"] = it.get("p_n")
    x["p_true_note"] = it.get("p_note") or "Jeffreys Beta(k+1/2, n-k+1/2) on fleet jobs for the code; k = confirmed = 0 (all 54 shop findings RTOK)"
    x["evidence"] = it.get("evidence")
    if it.get("second"):
        x["second_order"] = it["second"]
    if it.get("group"):
        x["p4_group"] = it["group"]
    items.append(x)

# ---------------------------------------------------------------- TJ107 rule trace (inputs computed from the as-of store)
runs = t7["runs"]
trace = {
    "gates": [
        {"id": "G1", "test": "WARNING severity code", "input": "HYD-101 severity CAUTION (fault_list PFL)", "pass": False},
        {"id": "G2", "test": "open grounding defect or exceedance inspection", "input": "none open; tail FMC", "pass": False},
        {"id": "G3", "test": "hard-time / limit breach in horizon", "input": "none due", "pass": False},
        {"id": "G4", "test": "model P(failure) above critical on safety-critical item", "input": f"P(confirmed pump fault) {t7['p_confirmed'][0]:.3f}", "pass": False},
    ],
    "P-DEC-01": [
        {"row": "r1", "cond": "severity == WARNING and occ_10d >= 2", "input": "CAUTION", "match": False},
        {"row": "r2", "cond": "deferred/no-fix and occ_10d >= 2 and corroborated", "input": "corroborated = false (no other code or trend)", "match": False},
        {"row": "r3", "cond": "deferred/no-fix and consec_flights >= 3", "input": f"consec_flights = {runs[-1]}; 0 confirmed fixes in {t7['jobs']} jobs", "match": True,
         "output": {"action": "TROUBLESHOOT", "band": "P2", "rationale": "PERSIST_3_FLIGHTS"}},
    ],
    "D8": {"cond": "persistence >= 5 flights and >= 2 prior CND outcomes", "input": f"{runs[-1]} consecutive flights; {t7['actions'].get('AT-CND')} CND outcomes on TJ107",
           "match": True, "output": "nuisance review -> HUMAN-only CHANGE_MONITORING_CONFIG draft"},
    "AP_lookup": {"C": 3, "U": 0, "band": "P3", "note": "band = most conservative of AP lookup (P3) and P-DEC-01 (P2) -> P2"},
    "counterfactual": "consec_flights 34 -> 2 (and D8 not met) -> r5 MONITOR P4; severity WARNING -> r1 P1",
    "policy_version": "P-DEC-01/1.4.0+jdm.3f9c0d7a (product metadata, matches twin page); zen-engine 2.1.3",
}
AP_TABLE = {"C3": {"U3": "P2", "U2": "P2", "U1": "P3", "U0": "P3"}, "C2": {"U3": "P3", "U2": "P3", "U1": "P4", "U0": "P4"},
            "C1": {"U3": "P3", "U2": "P4", "U1": "P4", "U0": "P4"}, "C0": "P4", "gates": "any gate -> P1 (non-compensatory)"}

# ---------------------------------------------------------------- LEL segment (identical construction to build_screen_assets.py)
DECIDED = {"TJ103-LGB-501": ("06:24", "APPROVED"), "TJ106-LGB-501": ("06:29", "APPROVED"), "TJ107-HYD-101": ("06:41", "APPROVED"),
           "TJ108-AOG-CHUTE": ("06:52", "APPROVED"), "TJ105-TYRE": ("07:03", "APPROVED"), "TJ105-SPS-501": ("07:10", "APPROVED"),
           "P4-ADVISORY": ("07:14", "ACKNOWLEDGED")}
EP = "epoch:20260622T0800"
cmc = next(o for o in D["orders"] if o["action"] == "CHANGE_MONITORING_CONFIG")
ev, seq = [], 0


def add(stream, typ, t, actor, payload, refs=None, causation=None):
    global seq
    seq += 1
    ev.append({"event_id": f"lel-20260622-{seq:04d}", "stream": stream, "seq": seq, "type": typ, "t_valid": f"2026-06-22T{t}+05:30",
               "actor": actor, "causation_id": causation, "correlation_id": EP, "refs": refs or {}, "payload": payload})
    return ev[-1]["event_id"]


c0 = add(EP, "SNAPSHOT_SEALED", "06:00:00", "AGENT:PHALANX-LOOP", {"records": D["snapshot"]["records"]},
         {"contract_hash": "a4396f1d5482ce78", "dict_hash": "9428d30f578f0318", "snapshot": D["snapshot"]["hash"]})
c1 = add(EP, "ANALYZED", "06:04:00", "AGENT:PHALANX-LOOP", {"issues_open": D["load"]["open"]}, {"policy_version": "P-DEC-01/1.4.0+jdm.3f9c0d7a"}, c0)
c2 = add(EP, "BOARD_OPEN", "06:05:00", "AGENT:PHALANX-LOOP", {"items": len(D["items"]), "budget": 10}, None, c1)
for it in D["items"]:
    t, st = DECIDED[it["id"]]
    add(f"recommendation:{it['id']}", st, f"{t}:00", "HUMAN:SEO", {"reason": None, "order_id": it.get("order_id")}, None, c2)
c3 = add(EP, "FROZEN", "07:45:00", "AGENT:PHALANX-LOOP", {"order_ids": [o["order_id"] for o in D["orders"]]}, None, c2)
c4 = add(f"order:{cmc['order_id']}", "HUMAN_SIGNED", "07:57:00", "HUMAN:ENGG-OFFICER", {"key": "station key EO-SULUR"}, None, c3)
c5 = add(EP, "SUBMITTED", "08:00:00", "AGENT:PHALANX-LOOP", {"orders": len(D["orders"])}, None, c4)
for o in D["orders"]:
    add(f"order:{o['order_id']}", "ACCEPTED", "08:00:00", "GATEWAY:M21", {"verdict": DRY[o["order_id"]]["verdict"], "status_seq": 0}, None, c5)
prev, lel = "00" * 32, []
for e in ev:
    body = canon(e)
    h = hashlib.blake2b(bytes.fromhex(prev) + body.encode(), digest_size=32).hexdigest()
    lel.append({"event": e, "canonical_json": body, "prev_hash": prev, "hash": h})
    prev = h
# must equal the head written into screens/assets/data-epoch.js by build_screen_assets.py
EXPECTED_HEAD = "afd2fdab2f6818782c4300fc21c3dabd03db1f9a52b470bb91de37f766a8a526"

out = {
    "about": {
        "asof": "2026-06-22 06:00 IST (t_ingest <= snapshot)", "epoch": "2026-06-22 08:00 IST", "session_clock_default": "06:12",
        "source": "/Users/abishaikc/Downloads/phalanx_data_layer_preview/data/v0.9/fleet/ (never _restricted_labels); dedupe (tail_no, record_id); orders.status scoped by order_id",
        "scripts": ["video/data/scripts/decision_screens_data.py (pandas venv)", "video/data/scripts/order_dryrun.py (video/tools/forks/run.sh, data-layer code)",
                    "video/data/scripts/build_screen_assets.py", "video/data/scripts/export_decision_flow.py"],
        "label": "PREVIEW v0.9 synthetic fleet; behaviour not validated",
    },
    "snapshot": D["snapshot"],
    "load": D["load"],
    "ap_table": AP_TABLE,
    "board_items": items,
    "code_outcomes_fleet": {"method": "job belongs to a code if any version cites an event of that code as evidence; keyed (tail_no, job_no) because job numbers collide across worlds; confirmed = shop finding != RTOK (0 of 54)",
                            "codes": D["code_outcomes"]},
    "orders": orders,
    "order_id_formula": "phx:<rule>:<policy semver>:<epoch YYYYMMDDTHHMM>:<tail>:<action>:<blake2b(canonical_json({'parameters': params, 'evidence': sorted(evidence ids)}), digest_size=8).hex()>; canonical_json = json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False)",
    "fork_alignment": {"note": "order params/evidence equal the fork agent's S1 (TJ107 TROUBLESHOOT {code} + CHANGE_MONITORING_CONFIG, same 6 evidence ids), S2 (TJ108 EXPEDITE, 3 ids) and S3 (TJ105 REQUISITION qty 2, 7 ids)",
                       "results_json_present_at_export": RES_P.exists(), "impact_numbers": "none used; fork still running at export"},
    "tj107": {
        "facts": {k: t7[k] for k in ("sorties", "fired", "runs", "events", "gr_events", "jobs", "mh", "actions", "removal_records", "rr_jobs",
                                     "rr_jobs_without_cl", "serials_on_record", "serial_values_on_remove", "sys1_serials", "shop", "inferred_install_jobs")},
        "sys1_now": "HYDP-000010 (inferred from job sulur-26169-0006 text; INSTALL record not ingested); SYS2 HYDP-000002 (never removed)",
        "p_confirmed_pump_fault": {**iv(t7["p_confirmed"]), "basis": f"Jeffreys on 0 of {D['code_outcomes']['HYD-101']['n']} fleet HYD-101 jobs"},
        "p_rtok_if_removed_again": {**iv(t7["p_rtok"]), "basis": f"Jeffreys on {t7['shop']['rtok']} of {t7['shop']['n']} pump bench findings RTOK"},
        "evidence_latest6": t7["evidence"],
        "rule_trace": trace,
        "evidence_chain_lanes": t7["lanes"],
        "natural_experiment_strip": {"sorties": t7["strip"], "removal_marks": t7["removal_marks"],
                                     "note": "SYS1 serial at takeoff from R/R job texts (complete) cross-checked to COMPONENT_LIFE; serial after 19 Jun inferred"},
        "man_hours": t7["mh_stats"],
        "posterior": {**t7["posterior"],
                      "model": "single-fault Bayes; prior = contract suspect isolation confidences (HYD_PUMP 0.8, AMAGB 0.2) x (1-leak), leak = indication path (BHEEM EU channel / pressure switch / harness); likelihood of each of 29 RTOK bench outcomes: (1-d) if pump faulty, 1 otherwise",
                      "assumptions": {"d_shop_detection": "ASSUMPTION, central 0.6, swept 0.3-0.9", "leak_prior_indication_path": "ASSUMPTION, central 0.20, swept 0.05-0.40",
                                      "not_used": "persistence across serial swaps (would only lower the pump further)"},
                      "reading": "pump < 1e-4 everywhere in the sweep; AMAGB vs indication path decided by the leak prior, flip at leak = 0.167"},
        "next_best_test": {"ranked_central": t7["nbt"], "top_counts_over_sweep": t7["nbt_top_counts"],
                           "sweep": "leak in {0.05,0.10,0.15,0.20,0.30,0.40} x test sensitivity in {0.3,0.5,0.7,0.9} (24 cells)",
                           "assumptions": {"test_sensitivity": f"ASSUMPTION {t7['nbt_sens']} (swept 0.3-0.9)", "false_positive": f"ASSUMPTION {t7['nbt_fp']}",
                                           "T3_detection": "= d (0.6)", "T2_man_hours": "proxy: fleet PHX-FIM-SPS jobs (no AMAGB jobs on record)"},
                           "metric": "expected entropy reduction (bits) of the 3-way posterior per median man-hour"},
        "similar_cases": {"tj107_runs": t7["similar"], "tj102": t7["tj102"]},
        "procedure_refs": t7["refs"],
    },
    "tj108": {**D["tj108"], "lead_time_chute": {"n": 6, "median_d": 12.2, "max_d": 50.5}, "remaining_wait": "INSUFFICIENT_EVIDENCE (age exceeds every closed chute demand)",
              "job": "sulur-26093-0003 AWAITING_PARTS, REPLACE BRAKE PARACHUTE DUE TO HI-TIME (45 STREAMINGS)"},
    "tj105": D["tj105"],
    "timings": {
        "data": {"snapshot": "06:00", "freeze": "07:45", "epoch": "08:00", "latest_hyd101_ingest": "18 Jun 21:08",
                 "decision_latency_from_spec": "median 18.4 h ingest -> order"},
        "product_metadata": {"engines_done": "06:04", "board_open": "06:05", "session_default": "06:12", "approved_state": "06:41 (TJ107 by SEO, reason skipped)",
                             "decisions_ui_state": DECIDED, "epoch_page_default": "07:52", "human_signature": "07:57", "submission": "08:00:00"},
    },
    "lel": {"definition": "hash = blake2b(bytes.fromhex(prev_hash) || canonical_json(event), digest_size=32); genesis prev = 32 zero bytes for this epoch segment",
            "events": lel, "head": lel[-1]["hash"], "head_matches_screens_asset": lel[-1]["hash"] == EXPECTED_HEAD},
    "caveats": [
        "HYD-101 fleet jobs = 122 with (tail, job) scoping (85 CND, 35 R/R, 1 TS, 1 open) -> P(confirmed) 0.004 [0.000, 0.020]; the shared CSV's 107 / 0.005 [0.000, 0.023] could not be reproduced (job_no-only grouping gives 106, i.e. likely the cross-world collision).",
        "P4 group: 13 recurring open advisory issues (occ_10d >= 2, codes ENG-201/AVI-201/203/204/ADC-002/ELE-405), not 9; D6 power-code inhibition removed none.",
        "TROUBLESHOOT params use {code: 'HYD-101'} (as in fork S1). position 'SYS1' is not an M18 catalogue position (HYDP1/HYDP2) and would be REJECTED at execution ('unknown position').",
        "Serials: 10 distinct pumps passed through SYS1 (11 HYDP serials on record incl. SYS2 HYDP-000002; one removal logged with serial 'XXX', resolved by record key). 28 REMOVE records; 29 R/R jobs by text (2 without COMPONENT_LIFE removal).",
        "Snapshot hash here (sha256 4c6fcd22...ec13f8) differs from the twin page's '9f1e...c3a2'.",
        "U classes for BIT items are categorical (recurrence / margin basis strings), not from a time-to-failure posterior; C from a MESL-style mapping.",
        "Rule ids P-ORG-02/1.2.0 and P-SPR-01/1.0.0 (+jdm suffixes) are product metadata, as is P-DEC-01/1.4.0+jdm.3f9c0d7a.",
    ],
}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
print("wrote", OUT, "LEL head", lel[-1]["hash"], "matches", lel[-1]["hash"] == EXPECTED_HEAD)
