"""Word-level alignment + caption files for a narration WAV.

Two timing sources:
  --source whisper  : faster-whisper word timestamps (works for ANY voice recording)
  --source kokoro   : Kokoro's own token timestamps (<wav>.tokens.json, exact for TTS)
Either way the caption TEXT is the original script (whisper words are mapped onto
script words with difflib), so captions never show ASR spelling mistakes.

Outputs: <stem>.<source>.words.json, .srt (phrase captions), .ass (phrase captions
with the currently-spoken word highlighted in the accent colour).

Usage:
  HF_HOME=tools/cache/hf .venv/bin/python -I tools/align/align_captions.py \
     --wav tools/tts/out/am_michael_1.0.wav --script-file script.txt --source whisper
"""
import argparse, difflib, json, re, time
from pathlib import Path

ACCENT_ASS = "&H3B74E8&"   # #E8743B as an ASS override colour (&HBBGGRR&)
INK_ASS = "&H100D0B&"      # #0B0D10
INK_STYLE = "&H00100D0B"   # style-line colours are &HAABBGGRR

def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'"))

def script_words(text):
    # keep punctuation attached to words for display; glue standalone dashes onto
    # the previous word ("decisions —") so they still act as phrase breaks
    text = re.sub(r"\[([^\]]+)\]\(/[^)]*/\)", r"\1", text)  # strip Kokoro/misaki [word](/phonemes/) overrides
    out = []
    for w in text.split():
        if norm(w) or not out:
            out.append(w)
        else:
            out[-1] += " " + w
    return out

def whisper_words(wav, model_name, script_text):
    from faster_whisper import WhisperModel
    t0 = time.perf_counter()
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    t1 = time.perf_counter()
    # Decode with system ffmpeg -> 16 kHz mono float32. (faster-whisper 1.2.1's own
    # decoder passes metadata_errors= to av.open(), which PyAV >= 15 rejects; Manim 0.22
    # pulls PyAV 19, so we bypass faster_whisper.audio.decode_audio.)
    import subprocess, numpy as np
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    segs, info = model.transcribe(audio, language="en", word_timestamps=True,
                                  beam_size=5, vad_filter=False,
                                  initial_prompt=script_text or None)
    words = [{"text": w.word.strip(), "start": w.start, "end": w.end, "p": w.probability}
             for s in segs for w in s.words]
    t2 = time.perf_counter()
    return words, {"model_load_s": round(t1 - t0, 2), "transcribe_s": round(t2 - t1, 2),
                   "audio_s": round(info.duration, 2)}

def kokoro_words(wav):
    toks = json.loads(Path(wav).with_suffix(".tokens.json").read_text())
    return [{"text": t["text"], "start": t["start"], "end": t["end"]} for t in toks if norm(t["text"])], {}

def map_to_script(script, asr):
    """Map ASR/TTS word timings onto script words; interpolate any unmatched words."""
    a = [norm(w) for w in script]; b = [norm(w["text"]) for w in asr]
    out = [None] * len(script)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                out[i1 + k] = (asr[j1 + k]["start"], asr[j1 + k]["end"], tag)
        elif tag == "replace":  # n script words <-> m asr words: spread the span evenly
            s, e = asr[j1]["start"], asr[j2 - 1]["end"]; n = i2 - i1
            for k in range(n):
                out[i1 + k] = (s + (e - s) * k / n, s + (e - s) * (k + 1) / n, "spread")
    # interpolate gaps (script words the ASR dropped)
    for i, v in enumerate(out):
        if v is None:
            prev_end = next((out[j][1] for j in range(i - 1, -1, -1) if out[j]), 0.0)
            nxt = next((out[j][0] for j in range(i + 1, len(out)) if out[j]), prev_end + 0.3)
            out[i] = (prev_end, max(prev_end + 0.05, nxt), "interp")
    return [{"text": w, "start": round(s, 3), "end": round(e, 3), "how": h}
            for w, (s, e, h) in zip(script, out)]

def phrases(words, max_chars=42, max_gap=0.6):
    """Group words into caption phrases: break on sentence punctuation, pauses, length."""
    cur, res = [], []
    for i, w in enumerate(words):
        if cur and (len(" ".join(x["text"] for x in cur + [w])) > max_chars
                    or w["start"] - cur[-1]["end"] > max_gap):
            res.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.?!—]$", w["text"]) or (re.search(r"[,;:]$", w["text"]) and len(" ".join(x["text"] for x in cur)) > 24):
            res.append(cur); cur = []
    if cur: res.append(cur)
    return res

def phrase_end(ph, i, pad=0.15):
    """Phrase end + small hold, but never overlapping the next phrase."""
    end = ph[i][-1]["end"] + pad
    return min(end, ph[i + 1][0]["start"] - 0.01) if i + 1 < len(ph) else end

def ts_srt(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def ts_ass(t):
    cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

def write_srt(ph, path):
    lines = []
    for i, p in enumerate(ph, 1):
        lines += [str(i), f"{ts_srt(p[0]['start'])} --> {ts_srt(phrase_end(ph, i - 1))}", " ".join(w["text"] for w in p), ""]
    Path(path).write_text("\n".join(lines))

def write_ass(ph, path, font="Manrope SemiBold", size=52, margin_v=70):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{INK_STYLE},{INK_STYLE},&H00FFFFFF,&H33FFFFFF,0,0,0,0,100,100,0,0,3,14,0,2,160,160,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for i, p in enumerate(ph):
        p_end = phrase_end(ph, i)
        # one event per word: whole phrase visible, current word in accent colour
        for k, w in enumerate(p):
            s = w["start"] if k else p[0]["start"]
            e = p[k + 1]["start"] if k + 1 < len(p) else p_end
            txt = " ".join((r"{\c" + ACCENT_ASS + "}" + x["text"] + r"{\c" + INK_ASS + "}") if j == k else x["text"]
                           for j, x in enumerate(p))
            ev.append(f"Dialogue: 0,{ts_ass(s)},{ts_ass(e)},Cap,,0,0,0,,{txt}")
    Path(path).write_text(head + "\n".join(ev) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--script-file"); ap.add_argument("--script")
    ap.add_argument("--source", choices=["whisper", "kokoro"], default="whisper")
    ap.add_argument("--model", default="small.en")
    ap.add_argument("--font", default="Manrope SemiBold", help="family name as libass sees it (static TTFs in tools/fonts/static)")
    ap.add_argument("--no-prompt", action="store_true",
                    help="don't bias Whisper with the script (use to measure TTS intelligibility)")
    args = ap.parse_args()
    text = args.script or Path(args.script_file).read_text()
    sw = script_words(text)
    if args.source == "whisper":
        raw, stats = whisper_words(args.wav, args.model, "" if args.no_prompt else text)
    else:
        raw, stats = kokoro_words(args.wav)
    words = map_to_script(sw, raw)
    stem = Path(args.wav).with_suffix(f".{args.source}")
    Path(f"{stem}.words.json").write_text(json.dumps({"raw": raw, "words": words, "stats": stats}, indent=1))
    ph = phrases(words)
    write_srt(ph, f"{stem}.srt"); write_ass(ph, f"{stem}.ass", font=args.font)
    asr_text = " ".join(w["text"] for w in raw)
    print(json.dumps({"stats": stats, "n_script_words": len(sw), "n_raw_words": len(raw),
                      "matched": sum(w["how"] == "equal" for w in words), "asr_text": asr_text,
                      "outputs": [f"{stem}.words.json", f"{stem}.srt", f"{stem}.ass"]}, indent=1))

if __name__ == "__main__":
    main()
