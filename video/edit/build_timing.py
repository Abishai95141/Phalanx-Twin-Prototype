"""Build edit/timing.json: per-shot start/dur (absolute + within act) from VO durations."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent
vo = json.loads((R/"vo/index.json").read_text())
ACTS = [("act01", ["S01","S02","S03","S04","S05","S06","S07","S08","S09","S10"]),
        ("act2",  ["S11","S12","S13","S14","S15","S16","S17","S18"]),
        ("act3a", ["S19","S20","S21","S22","S23","S24","S25","S26","S27"]),
        ("act3b", ["S28","S29","S30","S31","S32"]),
        ("act4",  ["S33A","S33B","S33C","S33D","S34","S35"])]
LEAD, TAIL = 0.28, 0.36
EXTRA = {"S01": 1.0, "S03": 0.4, "S04": 1.4, "S10": 0.4, "S15": 0.6, "S16": 0.4, "S18": 1.2, "S24": 0.5,
         "S25": 0.8, "S28": 0.8, "S29": 0.6, "S33A": 0.5, "S33B": 0.6, "S33C": 0.6, "S33D": 0.8, "S34": 0.6, "S35": 2.8}
PLACEHOLDER = {"S34": 6.5}
t = 0.0; out = {"fps": 30, "acts": [], "shots": {}}
for act, shots in ACTS:
    a0 = t; at = 0.0
    for s in shots:
        v = vo.get(s, {}).get("dur", PLACEHOLDER.get(s))
        d = round(LEAD + v + TAIL + EXTRA.get(s, 0), 2)
        d = round(round(d * 30) / 30, 4)                     # frame-align
        out["shots"][s] = {"act": act, "start": round(t, 4), "act_start": round(at, 4), "dur": d,
                           "vo_at": round(t + LEAD, 4), "vo_at_in_act": round(at + LEAD, 4), "vo_dur": v,
                           "text": vo.get(s, {}).get("text", "")}
        t += d; at += d
    out["acts"].append({"id": act, "start": round(a0, 4), "dur": round(t - a0, 4), "shots": shots})
out["total"] = round(t, 3)
(R/"timing.json").write_text(json.dumps(out, indent=1))
for a in out["acts"]: print(a["id"], a["start"], a["dur"])
print("total", out["total"])
