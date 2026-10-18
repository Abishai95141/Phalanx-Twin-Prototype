import json, subprocess, numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
R = Path(__file__).resolve().parent
m = WhisperModel("small.en", device="cpu", compute_type="int8")
idx = json.loads((R/"vo/index.json").read_text())
for sid, v in idx.items():
    pcm = subprocess.run(["ffmpeg","-v","error","-i",str(R/f"vo/{sid}.wav"),"-ac","1","-ar","16000","-f","f32le","-"],capture_output=True).stdout
    a = np.frombuffer(pcm, np.float32)
    segs, _ = m.transcribe(a, beam_size=1, language="en")
    print(sid, "|", " ".join(s.text.strip() for s in segs), flush=True)
