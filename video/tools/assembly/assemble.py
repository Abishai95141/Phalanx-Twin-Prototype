"""Timeline-as-JSON -> one deterministic FFmpeg render (keg-only ffmpeg-full for libass).

  .venv/bin/python -I tools/assembly/assemble.py tools/assembly/timeline_smoke.json [--dry-run]

Timeline schema (all times in seconds; paths relative to the JSON file):
{
  "fps": 30, "size": [1920, 1080], "background": "white",
  "video": [                                   # V1: clips laid end to end
    {"src": "a.png", "dur": 8, "kenburns": {"z0": 1.0, "z1": 1.08, "cx": 0.5, "cy": 0.5}},
    {"src": "b.mp4", "in": 0, "dur": 9.2, "transition": {"type": "fade", "dur": 0.6}}
  ],                                           # transition = any ffmpeg xfade type, overlaps previous clip
  "overlays": [                                # V2+: alpha clips (qtrle/ProRes 4444/VP9-alpha) or PNGs
    {"src": "eq.mov", "at": 0.8, "in": 0, "dur": 7, "scale": 0.5, "x": "W-w-80", "y": "H-h-60",
     "fade_in": 0.3, "fade_out": 0.5}
  ],
  "audio": {
    "narration": [{"src": "n1.wav", "at": 1.0, "gain_db": 0, "speech": [0.27, 13.1]}],
    "music": {"src": "m.wav", "gain_db": -6, "fade_in": 1, "fade_out": 2,
              "duck": {"mode": "envelope", "depth_db": -12, "attack": 0.25, "release": 0.6, "merge_gap": 1.2}},
              # or {"mode": "sidechain", "threshold": 0.02, "ratio": 8, "attack": 20, "release": 400}
    "sfx": [{"src": "whoosh.wav", "at": 7.4, "gain_db": -8}]
  },
  "captions": {"ass": "captions.ass", "offset": 1.0, "fontsdir": null},
  "loudness": {"I": -16, "TP": -1.5, "LRA": 11},
  "encode": {"crf": 18, "preset": "medium"},
  "out": "out/smoke.mp4",
  "debug_outputs": {"ducked_music": "out/ducked_music.wav"}
}
"""
import json, re, shlex, subprocess, sys, time
from pathlib import Path

FFMPEG = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"   # keg-only build with libass/freetype
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def db(x):
    return f"{x}dB"


def media_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def duck_envelope_expr(spans, depth_db=-12.0, attack=0.25, release=0.6, merge_gap=1.2):
    """volume= expression: unity gain, ramping down to depth_db over each narration span.

    Deterministic alternative to sidechaincompress: no pumping between sentences
    (spans closer than merge_gap are merged), exact ramp times.
    """
    spans = sorted(spans); merged = []
    for a, b in spans:
        if merged and a - merged[-1][1] < merge_gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    g = 10 ** (depth_db / 20)
    terms = [f"min(clip((t-{a - attack:.3f})/{attack},0,1),clip(({b + release:.3f}-t)/{release},0,1))" for a, b in merged]
    dexpr = terms[0]
    for tm in terms[1:]:
        dexpr = f"max({dexpr},{tm})"
    return f"1-{1 - g:.5f}*{dexpr}"


def shift_ass(src: Path, dst: Path, offset: float):
    """Write a copy of an .ass file with every Dialogue start/end shifted by offset seconds."""
    def to_s(ts):
        h, m, s = ts.split(":"); return int(h) * 3600 + int(m) * 60 + float(s)

    def to_ts(x):
        cs = max(0, int(round(x * 100))); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    out = []
    for line in src.read_text().splitlines():
        m = re.match(r"^(Dialogue: [^,]*,)([^,]*),([^,]*),(.*)$", line)
        if m:
            line = f"{m[1]}{to_ts(to_s(m[2]) + offset)},{to_ts(to_s(m[3]) + offset)},{m[4]}"
        out.append(line)
    dst.write_text("\n".join(out) + "\n")


def esc(path: Path) -> str:
    """Escape a path for use inside a filtergraph option value."""
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def build(tl: dict, base: Path):
    fps = tl.get("fps", 30); W, H = tl.get("size", [1920, 1080]); bg = tl.get("background", "white")
    args, fg, n_in = [], [], 0

    def add_input(spec_args):
        nonlocal n_in
        args.extend(spec_args); n_in += 1
        return n_in - 1

    norm = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={bg},setsar=1"

    # ---- V1 sequence with xfade transitions
    seg_labels, t_end = [], 0.0
    for k, c in enumerate(tl["video"]):
        src = base / c["src"]; dur = float(c["dur"])
        if src.suffix.lower() in IMG_EXT:
            i = add_input(["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(src)])
        else:
            i = add_input(["-ss", f"{c.get('in', 0):.3f}", "-t", f"{dur:.3f}", "-i", str(src)])
        chain = f"[{i}:v]"
        kb = c.get("kenburns")
        if kb:
            n = max(1, round(dur * fps)); z0, z1 = kb.get("z0", 1.0), kb.get("z1", 1.08)
            cx, cy = kb.get("cx", 0.5), kb.get("cy", 0.5)
            # upscale 2x first so zoompan's integer x/y stepping doesn't visibly jitter
            chain += (f"scale={2 * W}:{2 * H}:force_original_aspect_ratio=decrease,pad={2 * W}:{2 * H}:(ow-iw)/2:(oh-ih)/2:color={bg},"
                      f"zoompan=z='{z0}+({z1}-{z0})*on/{max(1, n - 1)}':"
                      # (cx, cy) is the fixed point of the zoom: it stays put on screen
                      f"x='{cx}*(iw-iw/zoom)':y='{cy}*(ih-ih/zoom)':"
                      f"d=1:s={W}x{H}:fps={fps},")
        chain += f"{norm},format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{k}]"
        fg.append(chain)
        tr = c.get("transition")
        if k == 0:
            cur, t_end = f"[v{k}]", dur
        else:
            td = float(tr["dur"]) if tr else 0.0
            if tr:
                off = t_end - td
                fg.append(f"{cur}[v{k}]xfade=transition={tr.get('type', 'fade')}:duration={td}:offset={off:.3f}[x{k}]")
            else:
                fg.append(f"{cur}[v{k}]concat=n=2:v=1:a=0[x{k}]")
            cur, t_end = f"[x{k}]", t_end + dur - td
    total = t_end

    # ---- overlays (alpha)
    for j, o in enumerate(tl.get("overlays", [])):
        src = base / o["src"]; dur = float(o["dur"]); at = float(o["at"])
        if src.suffix.lower() in IMG_EXT:
            i = add_input(["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(src)])
            dec = []
        else:
            i = add_input((["-c:v", "libvpx-vp9"] if src.suffix.lower() == ".webm" else [])  # VP9 alpha needs libvpx decoder
                          + ["-ss", f"{o.get('in', 0):.3f}", "-t", f"{dur:.3f}", "-i", str(src)])
        ch = f"[{i}:v]fps={fps},format=yuva444p,setpts=PTS-STARTPTS"
        if o.get("scale", 1) != 1:
            ch += f",scale=iw*{o['scale']}:-2"
        if o.get("fade_in"):
            ch += f",fade=t=in:st=0:d={o['fade_in']}:alpha=1"
        if o.get("fade_out"):
            ch += f",fade=t=out:st={dur - o['fade_out']:.3f}:d={o['fade_out']}:alpha=1"
        ch += f",tpad=start_duration={at:.3f}:color=black@0.0[o{j}]"
        fg.append(ch)
        fg.append(f"{cur}[o{j}]overlay=x='{o.get('x', '(W-w)/2')}':y='{o.get('y', '(H-h)/2')}':eof_action=pass:format=auto[ov{j}]")
        cur = f"[ov{j}]"

    # ---- captions (libass)
    cap = tl.get("captions")
    if cap:
        shifted = Path(tl["out"]).with_suffix(".captions.ass") if Path(tl["out"]).is_absolute() else base / Path(tl["out"]).with_suffix(".captions.ass")
        shifted.parent.mkdir(parents=True, exist_ok=True)
        shift_ass(base / cap["ass"], shifted, float(cap.get("offset", 0)))
        opt = f"subtitles=filename='{esc(shifted)}'"
        if cap.get("fontsdir"):
            opt += f":fontsdir='{esc(base / cap['fontsdir'])}'"
        fg.append(f"{cur}{opt},format=yuv420p[vout]")
    else:
        fg.append(f"{cur}format=yuv420p[vout]")

    # ---- audio: narration bus, music bed with sidechain ducking, sfx
    au = tl.get("audio", {}); a_fmt = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    nar_labels, nar_spans = [], []
    for k, n in enumerate(au.get("narration", [])):
        i = add_input(["-i", str(base / n["src"])])
        ms = int(round(float(n["at"]) * 1000))
        # speech span on the timeline; optional "speech": [start, end] (e.g. from word timestamps)
        sp = n.get("speech") or [0.0, media_duration(base / n["src"])]
        nar_spans.append((float(n["at"]) + sp[0], float(n["at"]) + sp[1]))
        fg.append(f"[{i}:a]{a_fmt},volume={db(n.get('gain_db', 0))},adelay={ms}:all=1[n{k}]")
        nar_labels.append(f"[n{k}]")
    sfx_labels = []
    for k, s in enumerate(au.get("sfx", [])):
        i = add_input(["-i", str(base / s["src"])])
        ms = int(round(float(s["at"]) * 1000))
        fg.append(f"[{i}:a]{a_fmt},volume={db(s.get('gain_db', 0))},adelay={ms}:all=1[s{k}]")
        sfx_labels.append(f"[s{k}]")
    mix_in = []
    if nar_labels:
        fg.append(f"{''.join(nar_labels)}amix=inputs={len(nar_labels)}:duration=longest:normalize=0,apad,atrim=0:{total:.3f}[nar]"
                  if len(nar_labels) > 1 else f"{nar_labels[0]}apad,atrim=0:{total:.3f}[nar]")
    m = au.get("music")
    debug = tl.get("debug_outputs", {})
    if m:
        i = add_input(["-stream_loop", "-1", "-i", str(base / m["src"])])
        ch = f"[{i}:a]{a_fmt},atrim=0:{total:.3f},volume={db(m.get('gain_db', -6))}"
        if m.get("fade_in"):
            ch += f",afade=t=in:st=0:d={m['fade_in']}"
        if m.get("fade_out"):
            ch += f",afade=t=out:st={total - m['fade_out']:.3f}:d={m['fade_out']}"
        fg.append(ch + "[mus]")
        d = m.get("duck")
        if d and nar_labels and d.get("mode", "envelope") == "envelope":
            expr = duck_envelope_expr(nar_spans, d.get("depth_db", -12), d.get("attack", 0.25),
                                      d.get("release", 0.6), d.get("merge_gap", 1.2))
            # asetnsamples=64: re-evaluate the gain every 64 samples (no zipper steps)
            fg.append(f"[mus]asetnsamples=n=64,volume='{expr}':eval=frame[mus_d]")
            if debug.get("ducked_music"):
                fg.append("[mus_d]asplit=2[mus_mix][mus_dbg]")
                mix_in += ["[nar]", "[mus_mix]"]
            else:
                mix_in += ["[nar]", "[mus_d]"]
        elif d and nar_labels:  # mode == "sidechain": signal-driven compressor
            fg.append("[nar]asplit=2[nar_mix][nar_sc]")
            fg.append(f"[mus][nar_sc]sidechaincompress=threshold={d.get('threshold', 0.02)}:ratio={d.get('ratio', 8)}:"
                      f"attack={d.get('attack', 20)}:release={d.get('release', 400)}:makeup=1[mus_d]")
            if debug.get("ducked_music"):
                fg.append("[mus_d]asplit=2[mus_mix][mus_dbg]")
                mix_in += ["[nar_mix]", "[mus_mix]"]
            else:
                mix_in += ["[nar_mix]", "[mus_d]"]
        else:
            mix_in += (["[nar]"] if nar_labels else []) + ["[mus]"]
    elif nar_labels:
        mix_in.append("[nar]")
    mix_in += sfx_labels
    loud = tl.get("loudness", {"I": -16, "TP": -1.5, "LRA": 11})
    fg.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:duration=first:normalize=0,"
              f"loudnorm=I={loud['I']}:TP={loud['TP']}:LRA={loud.get('LRA', 11)},{a_fmt},atrim=0:{total:.3f}[aout]")

    enc = tl.get("encode", {})
    out = base / tl["out"]; out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [FFMPEG, "-hide_banner", "-y", "-nostdin", *args, "-filter_complex", ";\n".join(fg),
           "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", enc.get("preset", "medium"), "-crf", str(enc.get("crf", 18)),
           "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(out)]
    if m and m.get("duck") and nar_labels and debug.get("ducked_music"):  # extra output for verification
        dbg = base / debug["ducked_music"]; dbg.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-map", "[mus_dbg]", "-t", f"{total:.3f}", "-c:a", "pcm_s16le", str(dbg)]
    return cmd, total, out


def main():
    tl_path = Path(sys.argv[1]).resolve(); base = tl_path.parent
    tl = json.loads(tl_path.read_text())
    cmd, total, out = build(tl, base)
    script = base / Path(tl["out"]).with_suffix(".ffmpeg.sh")
    script.write_text("#!/bin/sh\n" + " ".join(shlex.quote(c) for c in cmd) + "\n")
    print(f"timeline duration {total:.3f}s; command written to {script}")
    if "--dry-run" in sys.argv:
        return
    t0 = time.perf_counter()
    subprocess.run(cmd, check=True)
    print(json.dumps({"out": str(out), "render_s": round(time.perf_counter() - t0, 2), "timeline_s": round(total, 3)}))


if __name__ == "__main__":
    main()
