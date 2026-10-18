"""Compile edit/master_timeline_v2.json (v2 cut) for tools/assembly/assemble.py from timing_v2.json."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent; V = R.parent
T = json.loads((R / "timing_v2.json").read_text()); S = T["shots"]
vo = json.loads((R / "vo/index.json").read_text())
rel = lambda p: str(Path("..") / Path(p).relative_to(V))
video = []
for g in T["segments"]:
    c = {"src": rel(V / f"renders/{g['src']}.mp4"), "in": g["in"], "dur": g["dur"]}
    if g["xfade"]: c["transition"] = {"type": "fade", "dur": g["xfade"]}
    video.append(c)
ov = [
  {"src": rel(V / "renders/manim/M5_paired_forks_S28.mp4"), "at": S["S28"]["start"], "in": 0, "dur": 4.2, "fade_in": 0.15, "fade_out": 0.2},
  # S26 cut-in: hydraulic plate, the indication path the best next test isolates (film/ins_hyd.html)
  {"src": rel(V / "renders/ins_hyd.mp4"), "at": S["S26"]["start"], "in": 0, "dur": 2.3, "fade_in": 0.12, "fade_out": 0.3},
]
nar = [{"src": rel(V / f"edit/vo/{k}.wav"), "at": S[k]["vo_at"], "gain_db": 0, "speech": [0.0, vo[k]["dur"]]} for k in S]
tl = {"fps": 30, "size": [1920, 1080], "background": "white", "video": video, "overlays": ov,
      "audio": {"narration": nar, "music": {"src": rel(V / "edit/music/bed_v2.wav"), "gain_db": -7, "fade_in": 0.5, "fade_out": 2.5,
                 "duck": {"mode": "envelope", "depth_db": -11, "attack": 0.3, "release": 0.7, "merge_gap": 1.4}}},
      "captions": {"ass": "captions_v2.ass", "offset": 0.0, "fontsdir": rel(V / "tools/fonts/static")},
      "loudness": {"I": -16, "TP": -1.5, "LRA": 11}, "encode": {"crf": 16, "preset": "slow"},
      "out": rel(V / "renders/master_pre_v2.mp4")}
(R / "master_timeline_v2.json").write_text(json.dumps(tl, indent=1))
print("clips", len(video), "overlays", len(ov), "vo", len(nar), "total", T["total"])
