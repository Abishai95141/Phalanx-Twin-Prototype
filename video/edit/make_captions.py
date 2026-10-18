"""Burned-in captions from the script (display text) timed by Kokoro token timestamps.
Writes edit/captions.ass (absolute film time). Phrase in ink on a white pill; current word in accent."""
import difflib, json, re, sys
from pathlib import Path

R = Path(__file__).resolve().parent
# usage: make_captions.py [timing.json] [captions.ass]   (v2: timing_v2.json captions_v2.ass)
TIMING = sys.argv[1] if len(sys.argv) > 1 else "timing.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "captions.ass"
T = json.loads((R / TIMING).read_text())
N = {s["id"]: s for s in json.loads((R / "narration.json").read_text())["shots"]}
INK, ACC = "&H00100D0B", "&H003B74E8"          # ASS colours are &HAABBGGRR
norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
NUMW = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}

def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def word_times(sid):
    toks = [t for t in json.loads((R / "vo" / f"{sid}.tokens.json").read_text()) if norm(t["text"])]
    disp = N[sid]["text"].split()
    a = [norm(w) for w in disp]; b = [norm(t["text"]) for t in toks]
    times = [None] * len(disp)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (toks[blk.b + k]["start"], toks[blk.b + k]["end"])
    for op, i1, i2, j1, j2 in sm.get_opcodes():          # spread unmatched display words over unmatched tokens
        if op in ("replace", "insert") and i2 > i1 and j2 > j1:
            s0, s1 = toks[j1]["start"], toks[j2 - 1]["end"]
            for k in range(i1, i2):
                f0 = (k - i1) / (i2 - i1); f1 = (k - i1 + 1) / (i2 - i1)
                times[k] = (s0 + (s1 - s0) * f0, s0 + (s1 - s0) * f1)
    # fill any holes by neighbours
    for k in range(len(times)):
        if times[k] is None:
            prev = next((times[j] for j in range(k - 1, -1, -1) if times[j]), (0, 0))
            nxt = next((times[j] for j in range(k + 1, len(times)) if times[j]), (prev[1] + .2, prev[1] + .4))
            times[k] = (prev[1], nxt[0] if nxt[0] > prev[1] else prev[1] + .2)
    return disp, times

def phrases(disp):
    out, cur = [], []
    for i, w in enumerate(disp):
        cur.append(i)
        text = " ".join(disp[j] for j in cur)
        brk = re.search(r"[.?!;:]$|—$", w) or (w.endswith(",") and len(text) > 22) or len(text) > 40
        if i + 1 < len(disp) and disp[i + 1] == "—": brk = brk or len(text) > 18
        if brk: out.append(cur); cur = []
    if cur: out.append(cur)
    return out

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Manrope SemiBold,40,&H00100D0B,&H00100D0B,&H0AFFFFFF,&H00000000,0,0,0,0,100,100,0,0,3,13,0,2,200,200,44,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
ev = []
for sid, sh in T["shots"].items():
    if sid not in N: continue
    disp, times = word_times(sid)
    base = sh["vo_at"]
    ph = phrases(disp)
    for pi, idx in enumerate(ph):
        p0 = times[idx[0]][0]; p1 = times[idx[-1]][1] + 0.15
        if pi + 1 < len(ph): p1 = min(p1, times[ph[pi + 1][0]][0] - 0.02)
        for k, wi in enumerate(idx):
            w0 = times[wi][0] if k else p0
            w1 = times[idx[k + 1]][0] if k + 1 < len(idx) else p1
            if w1 <= w0: continue
            txt = " ".join(("{\\c" + ACC + "}" + disp[j].replace("{", "(").replace("}", ")") + "{\\c" + INK + "}") if j == wi else disp[j] for j in idx)
            ev.append(f"Dialogue: 0,{ts(base + w0)},{ts(base + w1)},Cap,,0,0,0,,{txt}")
(R / OUT).write_text(head + "\n".join(ev) + "\n")
print(len(ev), "events")
