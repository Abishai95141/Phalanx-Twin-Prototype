"""Generate stand-in assets for the assembly smoke test (no real UI exists yet).

  .venv/bin/python -I tools/assembly/make_test_assets.py tools/assembly/assets

Writes:
  ui_mock.png      1920x1080 placeholder "fleet board" (stands in for a HyperFrames render)
  music_bed.wav    24 s synthetic ambient pad, 48 kHz stereo (stands in for licensed music)
All content is synthetic and labelled MOCK.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

INK, ACCENT, PAPER, LINE, MUTED = "#0B0D10", "#E8743B", "#FFFFFF", "#E4E6EA", "#6B7280"
HN = "/System/Library/Fonts/HelveticaNeue.ttc"


def font(size, bold=False):
    return ImageFont.truetype(HN, size, index=1 if bold else 0)


def ui_mock(path):
    im = Image.new("RGB", (1920, 1080), PAPER)
    d = ImageDraw.Draw(im)
    d.text((96, 72), "Phalanx Twin", font=font(44, True), fill=INK)
    d.text((96, 128), "Fleet board  ·  08:00 decision brief  ·  MOCK DATA", font=font(26), fill=MUTED)
    d.line((96, 184, 1824, 184), fill=LINE, width=2)
    status = ["FLY", "FLY", "HOLD", "FLY", "INSPECT", "FLY", "FLY", "HOLD"]
    for i, s in enumerate(status):
        x = 96 + (i % 4) * 438
        y = 230 + (i // 4) * 300
        d.rounded_rectangle((x, y, x + 410, y + 260), radius=18, outline=LINE, width=3, fill=PAPER)
        d.text((x + 28, y + 24), f"TAIL-{i + 1:02d}", font=font(34, True), fill=INK)
        col = ACCENT if s != "FLY" else INK
        d.rounded_rectangle((x + 28, y + 84, x + 28 + 24 * len(s) + 40, y + 132), radius=24, fill=col)
        d.text((x + 48, y + 92), s, font=font(26, True), fill=PAPER)
        # tiny sparkline
        rng = np.random.default_rng(i)
        ys = np.cumsum(rng.normal(0, 1, 40)); ys = (ys - ys.min()) / (np.ptp(ys) + 1e-9)
        pts = [(x + 28 + k * 9, y + 230 - 70 * v) for k, v in enumerate(ys)]
        d.line(pts, fill=col, width=4)
    d.text((96, 860), "Signed decisions today: 3   ·   Evidence ingested before 07:45 only", font=font(30), fill=INK)
    im.save(path)


def music_bed(path, dur=24.0, sr=48000):
    t = np.arange(int(dur * sr)) / sr
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    out = np.zeros_like(t)
    seg = 4.0
    for k in range(int(np.ceil(dur / seg))):
        f = chords[k % 4]
        m = (t >= k * seg - 0.5) & (t < (k + 1) * seg + 0.5)
        tt = t[m] - k * seg
        env = np.clip((tt + 0.5) / 1.0, 0, 1) * np.clip(((seg + 0.5) - tt) / 1.0, 0, 1)
        for i, fr in enumerate(f):
            out[m] += env * (np.sin(2 * np.pi * fr * tt) + 0.3 * np.sin(2 * np.pi * 2 * fr * tt)) / (i + 1.5)
    out += 0.15 * np.sin(2 * np.pi * 110 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))  # soft pulse
    out *= 10 ** (-16 / 20) / np.max(np.abs(out))  # peak at -16 dBFS (a quiet bed)
    l = out; r = np.roll(out, int(0.012 * sr))       # slight stereo width
    sf.write(path, np.stack([l, r], 1).astype(np.float32), sr, subtype="PCM_16")


if __name__ == "__main__":
    outdir = Path(sys.argv[1]); outdir.mkdir(parents=True, exist_ok=True)
    ui_mock(outdir / "ui_mock.png")
    music_bed(outdir / "music_bed.wav")
    print("wrote", outdir)
