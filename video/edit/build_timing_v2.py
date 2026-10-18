"""Build edit/timing_v2.json for the v2 cut (3:40) from the v1 act renders and VO durations.

v2 keeps S01–S12, S17–S24, S26–S28, S30–S31, S34–S35, adds the LinuxONE section (L1–L3, film/linuxone.html) and
drops S13–S16, S25 (M1), S29 (M3), S32 and S33A–D. Kept shots keep their v1 lengths, so the act renders are cut at
shot boundaries instead of re-timed. Each segment is a span of one act render; a segment with "xfade" crossfades
into the previous one (the previous segment runs on for that long, so shot starts are unchanged).

Writes per shot: film start/dur, vo_at (film), src (render) and src_start, plus the segment list and music sections.
"""
import json
from pathlib import Path
R = Path(__file__).resolve().parent
vo = json.loads((R / "vo/index.json").read_text())
V1 = json.loads((R / "timing.json").read_text())["shots"]
LEAD, TAIL = 0.28, 0.36
FR = lambda d: round(round(d * 30) / 30, 4)                     # frame-align

# LinuxONE section: shot lengths from its narration (as build_timing.py does for the acts)
L_EXTRA = {"L1": 0.0, "L2": 0.15, "L3": 0.6}
lin, t = {}, 0.0
for s in ["L1", "L2", "L3"]:
    d = FR(LEAD + vo[s]["dur"] + TAIL + L_EXTRA[s])
    lin[s] = {"act_start": round(t, 4), "dur": d}; t += d
LIN_DUR = FR(t)
# act4 v2 runs 1.0 s longer than v1 (the end card holds for the tagline and credit)
S35_DUR = FR(V1["S35"]["dur"] + 1.0)

def shot_src(s):
    if s in lin: return "linuxone", lin[s]["act_start"], lin[s]["dur"]
    v = V1[s]; return v["act"], v["act_start"], (S35_DUR if s == "S35" else v["dur"])

# (render, src in, src out, xfade into this segment, shots)
SEGS = [("act01_v2", 0.0, 66.5999, 0.0, ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"]),
        ("act2_v2", 0.0, 10.85, 0.0, ["S11", "S12"]),                    # runs 0.15 s past S12 (columns fold away)
        ("act2_v2", 50.12, 67.2, 0.3, ["S17", "S18"]),                   # crossfade into the camera's move to triage
        ("act3a", 0.0, 37.2001, 0.0, ["S19", "S20", "S21", "S22", "S23", "S24"]),   # S24 ends on white
        ("act3a", 48.7001, 63.0667, 0.0, ["S26", "S27"]),                # S26 starts from white (ins_hyd cut-in)
        ("act3b", 0.0, 9.2, 0.0, ["S28"]),                               # S28 ends on white
        ("act3b", 18.3333, 33.1667, 0.3, ["S30", "S31"]),                # fade up on the decision screen
        ("linuxone", 0.0, LIN_DUR, 0.3, ["L1", "L2", "L3"]),             # S31 crossfades into the LinuxONE section
        ("act4_v2", 37.6334, 57.3, 0.0, ["S34", "S35"])]                 # section ends on white; S34 builds from white

out = {"fps": 30, "segments": [], "shots": {}, "linuxone": {"dur": LIN_DUR, "shots": lin}}
t_end = 0.0
for src, a, b, xf, shots in SEGS:
    f0 = round(t_end - xf, 4)
    out["segments"].append({"src": src, "in": a, "dur": round(b - a, 4), "xfade": xf, "film_start": f0, "shots": shots})
    for s in shots:
        act, s0, d = shot_src(s)
        st = round(f0 + (s0 - a), 4)
        out["shots"][s] = {"src": src, "src_start": s0, "start": st, "dur": d, "vo_at": round(st + LEAD, 4),
                           "vo_at_in_act": round(s0 + LEAD, 4), "vo_dur": vo[s]["dur"], "text": vo[s]["text"]}
    t_end = f0 + (b - a)
out["total"] = round(t_end, 3)
S = out["shots"]
# music sections (film time): promise, pain, solution, demonstration, proof, platform, close
out["sections"] = {"promise": 0.0, "pain": S["S05"]["start"], "solution": S["S11"]["start"], "demo": S["S19"]["start"],
                   "proof": S["S28"]["start"], "platform": S["L1"]["start"], "result": S["S34"]["start"], "close": S["S35"]["start"]}
(R / "timing_v2.json").write_text(json.dumps(out, indent=1))
for s, v in S.items(): print(f"{s:5s} {v['start']:8.3f} {v['dur']:7.3f}  {v['src']}@{v['src_start']}")
print("linuxone", LIN_DUR, lin)
print("total", out["total"])
