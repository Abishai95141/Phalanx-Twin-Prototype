"""Audio-only preview of the film: every narration line at its timeline position + ducked music bed."""
import json, subprocess
from pathlib import Path
R = Path(__file__).resolve().parent
T = json.loads((R / "timing.json").read_text()); vo = json.loads((R / "vo/index.json").read_text())
FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
shots = [k for k in T["shots"] if k in vo]
args = [FF, "-y", "-v", "error", "-i", str(R / "music/bed.wav")]
for k in shots: args += ["-i", str(R / f"vo/{k}.wav")]
spans = [(T["shots"][k]["vo_at"], T["shots"][k]["vo_at"] + vo[k]["dur"]) for k in shots]
merged = []
for a, b in sorted(spans):
    if merged and a - merged[-1][1] < 1.4: merged[-1][1] = b
    else: merged.append([a, b])
duck = "+".join(f"min(clip((t-{a-0.3:.2f})/0.3,0,1),clip(({b+0.7:.2f}-t)/0.7,0,1))" for a, b in merged)
g = f"[0:a]volume=-7dB,volume='1-(1-0.28)*min(1,{duck})':eval=frame,afade=t=out:st={T['total']-2.5}:d=2.5[m];"
for i, k in enumerate(shots, 1):
    d = int(T["shots"][k]["vo_at"] * 1000)
    g += f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={d}|{d}[v{i}];"
g += "".join(f"[v{i}]" for i in range(1, len(shots) + 1)) + f"amix=inputs={len(shots)}:normalize=0[vo];"
g += "[vo][m]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
out = R.parent / "renders/audio_preview.m4a"; out.parent.mkdir(exist_ok=True)
subprocess.run(args + ["-filter_complex", g, "-map", "[out]", "-t", str(T["total"]), "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
print(out)
