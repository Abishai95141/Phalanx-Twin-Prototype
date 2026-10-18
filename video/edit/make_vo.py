"""Generate per-shot narration with Kokoro (af_heart) + token timings. Usage: make_vo.py [shot ids...]"""
import json, sys, time
from pathlib import Path
import numpy as np, soundfile as sf, torch
from kokoro import KPipeline
SR = 24000
ROOT = Path(__file__).resolve().parent
N = json.loads((ROOT / "narration.json").read_text())
want = set(sys.argv[1:])
pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
out = {}
idx_path = ROOT / "vo" / "index.json"
if idx_path.exists(): out = json.loads(idx_path.read_text())
for s in N["shots"]:
    if want and s["id"] not in want: continue
    spoken = s.get("spoken", s["text"]).replace("Phalanx", "[Phalanx](/fˈAlˌæŋks/)")
    torch.manual_seed(7)
    chunks, toks, off = [], [], 0.0
    for r in pipe(spoken, voice=N["voice"], speed=N["speed"], split_pattern=r"\n+"):
        a = r.audio.detach().cpu().numpy()
        for t in (r.tokens or []):
            if t.start_ts is None: continue
            toks.append({"text": t.text, "start": round(off + t.start_ts, 3), "end": round(off + t.end_ts, 3)})
        chunks.append(a); off += len(a) / SR
    a = np.concatenate(chunks)
    # trim leading/trailing silence to 0.12 s
    thr = 0.006; nz = np.where(np.abs(a) > thr)[0]
    s0 = max(0, nz[0] - int(.12 * SR)); s1 = min(len(a), nz[-1] + int(.18 * SR))
    a = a[s0:s1]; shift = s0 / SR
    for t in toks: t["start"] = round(t["start"] - shift, 3); t["end"] = round(t["end"] - shift, 3)
    p = ROOT / "vo" / f"{s['id']}.wav"; sf.write(p, a, SR, subtype="PCM_16")
    (ROOT / "vo" / f"{s['id']}.tokens.json").write_text(json.dumps(toks))
    out[s["id"]] = {"dur": round(len(a) / SR, 3), "text": s["text"], "words": len(s["text"].split())}
    print(s["id"], out[s["id"]]["dur"], flush=True)
idx_path.write_text(json.dumps(out, indent=1))
print("total", round(sum(v["dur"] for v in out.values()), 2), "words", sum(v["words"] for v in out.values()))
