"""Write page data for decisions.html, workbench.html and epoch.html.

Inputs (all produced by scripts in this folder, nothing typed in by hand except UI-state times):
  video/data/decision_screens_asof_20260622.json   (decision_screens_data.py, as-of 06:00 store)
  video/data/order_dryrun_20260622.json            (order_dryrun.py, data-layer gateway checks)
  video/data/forks/results.json                    (optional; fork agent's S1-S3 summary, belief mode)
Outputs:
  video/screens/assets/data-decisions.js  -> window.PHX_DEC
  video/screens/assets/data-workbench.js  -> window.PHX_WB
  video/screens/assets/data-epoch.js      -> window.PHX_EP   (incl. a blake2b hash-chained LEL segment)

Run: python3 video/data/scripts/build_screen_assets.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = json.loads((ROOT / "data" / "decision_screens_asof_20260622.json").read_text())
DRY = json.loads((ROOT / "data" / "order_dryrun_20260622.json").read_text())
RES_P = ROOT / "data" / "forks" / "results.json"
RES = json.loads(RES_P.read_text()) if RES_P.exists() else None
ASSETS = ROOT / "screens" / "assets"


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def f3(x):
    return f"{x:.3f}"


def iv(p, nd=3):
    """'0.004 [0.000, 0.020]' pieces."""
    return {"v": f"{p[0]:.{nd}f}", "lo": f"{p[1]:.{nd}f}", "hi": f"{p[2]:.{nd}f}"}


# ------------------------------------------------------------------ fork results (belief mode only)
def fork_summary(sc):
    """Return belief-mode paired differences for a scenario, or None while the fork agent is still running."""
    if not RES:
        return None
    node = RES.get(sc) or (RES.get("scenarios") or {}).get(sc)
    if not node:
        return None
    b = (node.get("modes") or node).get("belief") or node.get("belief")
    if not b:
        return None
    kp = b.get("kpis") or {}
    out = {"n": None, "kpis": {}}
    for k, v in kp.items():
        diff = v.get("paired_difference_treatment_minus_status_quo") or v.get("diff")
        if not diff:
            continue
        out["n"] = diff.get("n", out["n"])
        out["kpis"][k] = {"mean": diff["mean"], "lo": diff["ci_low"], "hi": diff["ci_high"],
                          "sq": (v.get("status_quo") or {}).get("mean"), "tr": (v.get("treatment") or {}).get("mean")}
    if not out["kpis"] or not out["n"] or out["n"] < 3:
        return None
    return out


forks = {s: fork_summary(s) for s in ("S1", "S2", "S3")}

# ------------------------------------------------------------------ decisions page
t7 = D["tj107"]
items = D["items"]
orders = {o["order_id"]: o for o in D["orders"]}
dry = {c["order_id"]: c for c in DRY["checks"]}
co = D["code_outcomes"]

DECIDED = {  # UI-state times for the film (human actions on the board, not data)
    "TJ103-LGB-501": ("06:24", "APPROVED"), "TJ106-LGB-501": ("06:29", "APPROVED"), "TJ107-HYD-101": ("06:41", "APPROVED"),
    "TJ108-AOG-CHUTE": ("06:52", "APPROVED"), "TJ105-TYRE": ("07:03", "APPROVED"), "TJ105-SPS-501": ("07:10", "APPROVED"),
    "P4-ADVISORY": ("07:14", "ACKNOWLEDGED"),
}
board = []
for it in items:
    row = {k: it.get(k) for k in ("id", "band", "tail", "code", "title", "sev", "reason", "basis", "C", "U", "u_basis", "conf",
                                    "action", "params", "rule", "row", "auth", "mode", "order_id", "p_note", "p_n")}
    row["p"] = iv(it["p"]) if it.get("p") else None
    if it.get("second"):
        row["second"] = {"action": it["second"]["action"], "auth": "HUMAN", "order_id": it["second"]["order_id"]}
    if it.get("group"):
        row["group"] = it["group"]
    row["decided"] = DECIDED[it["id"]]
    board.append(row)

hyd = next(i for i in items if i["id"] == "TJ107-HYD-101")
o_ts = orders[hyd["order_id"]]
o_cmc = orders[hyd["second"]["order_id"]]
p_conf, p_rtok = t7["p_confirmed"], t7["p_rtok"]

dec = {
    "snapshot": D["snapshot"], "load": D["load"], "board": board,
    "code_outcomes": co,
    "tj107": {
        "runs": t7["runs"], "sorties": t7["sorties"], "fired": t7["fired"], "events": t7["events"], "gr": len(t7["gr_events"]),
        "jobs": t7["jobs"], "mh": t7["mh"], "actions": t7["actions"], "removal_records": t7["removal_records"],
        "rr_jobs": t7["rr_jobs"], "sys1_serials": len(t7["sys1_serials"]), "shop": t7["shop"],
        "evidence": t7["evidence"], "p_conf": iv(p_conf), "p_rtok": iv(p_rtok, 2), "fleet": co["HYD-101"],
        "mh_rr": t7["mh_stats"]["task_hydp_rr"], "mh_fim": t7["mh_stats"]["fim_hyd_cnd"],
        "post": t7["posterior"]["post"], "pump_max": t7["posterior"]["pump_max_over_sweep"],
        "orders": [
            {"order_id": o_ts["order_id"], "action": "TROUBLESHOOT", "params": o_ts["parameters"], "auth": "AGENT", "mode": "consent",
             "evidence_n": len(o_ts["evidence"]), "dry": dry[o_ts["order_id"]]},
            {"order_id": o_cmc["order_id"], "action": "CHANGE_MONITORING_CONFIG", "params": o_cmc["parameters"], "auth": "HUMAN",
             "mode": "HUMAN-only draft", "evidence_n": len(o_cmc["evidence"]), "dry": dry[o_cmc["order_id"]]},
        ],
        "fork": forks["S1"],
    },
    "tj108": {"age_d": D["tj108"]["age_d"], "demand_open": D["tj108"]["demand_open"], "fork": forks["S2"],
              "order": next(o for o in D["orders"] if o["action"] == "EXPEDITE_SPARES")},
    "orders": D["orders"],
}

# ------------------------------------------------------------------ workbench page
post = t7["posterior"]
wb = {
    "strip": t7["strip"], "removal_marks": t7["removal_marks"], "lanes": t7["lanes"], "runs": t7["runs"],
    "sorties": t7["sorties"], "fired": t7["fired"], "gr": t7["gr_events"], "sys1_serials": t7["sys1_serials"],
    "removal_records": t7["removal_records"], "rr_jobs": t7["rr_jobs"], "rr_jobs_without_cl": t7["rr_jobs_without_cl"],
    "inferred_install_jobs": t7["inferred_install_jobs"], "shop": t7["shop"], "jobs": t7["jobs"], "mh": t7["mh"],
    "actions": t7["actions"], "fleet": co["HYD-101"],
    "posterior": post, "nbt": t7["nbt"], "nbt_top_counts": t7["nbt_top_counts"], "nbt_sens": t7["nbt_sens"], "nbt_fp": t7["nbt_fp"],
    "mh_stats": t7["mh_stats"], "similar": t7["similar"], "tj102": t7["tj102"], "refs": t7["refs"],
    "p_conf": iv(p_conf), "p_rtok": iv(p_rtok, 2),
}

# ------------------------------------------------------------------ epoch page + Lifecycle Event Log segment
ep_orders = []
for o in D["orders"]:
    c = dry[o["order_id"]]
    ep_orders.append({**o, "dry": c})


def lel_chain(events, prev="00" * 32):
    out = []
    for e in events:
        body = canon(e)
        h = hashlib.blake2b(bytes.fromhex(prev) + body.encode(), digest_size=32).hexdigest()
        out.append({"event": e, "prev_hash": prev, "hash": h, "canonical_len": len(body)})
        prev = h
    return out


EP = "epoch:20260622T0800"
refs_base = {"contract_hash": "a4396f1d5482ce78", "dict_hash": "9428d30f578f0318", "snapshot": D["snapshot"]["hash"]}
ev = []
seq = 0


def add(stream, typ, t, actor, payload, refs=None, causation=None):
    global seq
    seq += 1
    ev.append({"event_id": f"lel-20260622-{seq:04d}", "stream": stream, "seq": seq, "type": typ, "t_valid": f"2026-06-22T{t}+05:30",
               "actor": actor, "causation_id": causation, "correlation_id": EP, "refs": refs or {}, "payload": payload})
    return ev[-1]["event_id"]


c0 = add(EP, "SNAPSHOT_SEALED", "06:00:00", "AGENT:PHALANX-LOOP", {"records": D["snapshot"]["records"]}, refs_base)
c1 = add(EP, "ANALYZED", "06:04:00", "AGENT:PHALANX-LOOP", {"issues_open": D["load"]["open"]}, {"policy_version": "P-DEC-01/1.4.0+jdm.3f9c0d7a"}, c0)
c2 = add(EP, "BOARD_OPEN", "06:05:00", "AGENT:PHALANX-LOOP", {"items": len(items), "budget": 10}, None, c1)
for it in items:
    t, st = DECIDED[it["id"]]
    add(f"recommendation:{it['id']}", st, f"{t}:00", "HUMAN:SEO", {"reason": None, "order_id": it.get("order_id")}, None, c2)
c3 = add(EP, "FROZEN", "07:45:00", "AGENT:PHALANX-LOOP", {"order_ids": [o["order_id"] for o in D["orders"]]}, None, c2)
c4 = add(f"order:{o_cmc['order_id']}", "HUMAN_SIGNED", "07:57:00", "HUMAN:ENGG-OFFICER", {"key": "station key EO-SULUR"}, None, c3)
c5 = add(EP, "SUBMITTED", "08:00:00", "AGENT:PHALANX-LOOP", {"orders": len(D["orders"])}, None, c4)
for o in D["orders"]:
    add(f"order:{o['order_id']}", "ACCEPTED", "08:00:00", "GATEWAY:M21", {"verdict": dry[o["order_id"]]["verdict"], "status_seq": 0}, None, c5)
chain = lel_chain(ev)

epd = {"orders": ep_orders, "snapshot": D["snapshot"], "lel": chain, "decided": DECIDED,
       "forks": {k: (v is not None) for k, v in forks.items()}}

for name, var, obj in (("data-decisions.js", "PHX_DEC", dec), ("data-workbench.js", "PHX_WB", wb), ("data-epoch.js", "PHX_EP", epd)):
    (ASSETS / name).write_text(f"/* generated by video/data/scripts/build_screen_assets.py — do not edit */\nwindow.{var} = {json.dumps(obj, ensure_ascii=False, default=str)};\n")
    print("wrote", ASSETS / name)
print("forks available:", {k: v is not None for k, v in forks.items()})
print("LEL head", chain[-1]["hash"], "events", len(chain))
