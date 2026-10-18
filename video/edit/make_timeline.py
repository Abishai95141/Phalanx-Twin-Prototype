"""Compile edit/master_timeline.json for tools/assembly/assemble.py from timing.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent; V = R.parent
T = json.loads((R / "timing.json").read_text()); S = T["shots"]
vo = json.loads((R / "vo/index.json").read_text())
rel = lambda p: str(Path(p).resolve().relative_to(R.resolve(), walk_up=True)) if False else str(Path("..") / Path(p).relative_to(V))
video = [{"src": rel(V / f"renders/{a['id']}.mp4"), "in": 0, "dur": round(a["dur"], 4)} for a in T["acts"]]
ov = [
  {"src": rel(V / "renders/manim/M1_bayes_S25.mp4"), "at": S["S25"]["start"], "in": 0, "dur": S["S25"]["dur"], "fade_in": 0.2, "fade_out": 0.2},
  {"src": rel(V / "renders/manim/M5_paired_forks_S28.mp4"), "at": S["S28"]["start"], "in": 0, "dur": 4.2, "fade_in": 0.15, "fade_out": 0.2},
  {"src": rel(V / "renders/manim/M3_lead_time_S29.mp4"), "at": S["S29"]["start"], "in": 0, "dur": 3.6, "fade_in": 0.15, "fade_out": 0.2},
  # S26 cut-in: hydraulic plate, the indication path the best next test isolates (film/ins_hyd.html); fades to the workbench's cause ranking
  {"src": rel(V / "renders/ins_hyd.mp4"), "at": S["S26"]["start"], "in": 0, "dur": 2.3, "fade_in": 0.12, "fade_out": 0.3},
]
nar = [{"src": rel(V / f"edit/vo/{k}.wav"), "at": S[k]["vo_at"], "gain_db": 0, "speech": [0.0, vo[k]["dur"]]} for k in S if k in vo]
tl = {"fps": 30, "size": [1920, 1080], "background": "white", "video": video, "overlays": ov,
      "audio": {"narration": nar, "music": {"src": rel(V / "edit/music/bed.wav"), "gain_db": -7, "fade_in": 0.5, "fade_out": 2.5,
                 "duck": {"mode": "envelope", "depth_db": -11, "attack": 0.3, "release": 0.7, "merge_gap": 1.4}}},
      "captions": {"ass": "captions.ass", "offset": 0.0, "fontsdir": rel(V / "tools/fonts/static")},
      "loudness": {"I": -16, "TP": -1.5, "LRA": 11}, "encode": {"crf": 16, "preset": "slow"},
      "out": rel(V / "renders/master_pre.mp4")}
(R / "master_timeline.json").write_text(json.dumps(tl, indent=1))
print("clips", len(video), "overlays", len(ov), "vo", len(nar), "total", T["total"])
