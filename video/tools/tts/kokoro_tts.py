"""Kokoro-82M narration generator (smoke test + reusable CLI).

Usage:
  HF_HOME=video/tools/cache/hf .venv/bin/python -I tools/tts/kokoro_tts.py \
      --voice am_michael --speed 1.0 --text "..." --out tools/tts/out/x.wav

Writes a 24 kHz mono WAV plus <out>.tokens.json with Kokoro's own per-token
start/end timestamps (from the duration predictor) for caption alignment.
"""
import argparse, json, time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from kokoro import KPipeline

SR = 24000

def synth(pipeline, text, voice, speed):
    audio_chunks, tokens, offset = [], [], 0.0
    for res in pipeline(text, voice=voice, speed=speed, split_pattern=r"\n+"):
        a = res.audio.detach().cpu().numpy() if hasattr(res.audio, "detach") else np.asarray(res.audio)
        for t in (res.tokens or []):
            if t.start_ts is None or t.end_ts is None:
                continue
            tokens.append({"text": t.text, "phonemes": t.phonemes,
                           "start": round(offset + t.start_ts, 3),
                           "end": round(offset + t.end_ts, 3)})
        audio_chunks.append(a)
        offset += len(a) / SR
    return np.concatenate(audio_chunks), tokens

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--voice", default="am_michael")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--lang", default=None, help="a=American, b=British (default from voice prefix)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0, help="torch seed: the vocoder is stochastic; fixed seed = bit-identical WAV")
    args = ap.parse_args()
    lang = args.lang or args.voice[0]
    t0 = time.perf_counter()
    pipeline = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    t1 = time.perf_counter()
    torch.manual_seed(args.seed)
    audio, tokens = synth(pipeline, args.text, args.voice, args.speed)
    t2 = time.perf_counter()
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, SR, subtype="PCM_16")
    out.with_suffix(".tokens.json").write_text(json.dumps(tokens, indent=1))
    dur = len(audio) / SR
    print(json.dumps({"voice": args.voice, "speed": args.speed, "audio_s": round(dur, 2),
                      "load_s": round(t1 - t0, 2), "synth_s": round(t2 - t1, 2),
                      "rtf": round((t2 - t1) / dur, 3), "out": str(out)}))

if __name__ == "__main__":
    main()
