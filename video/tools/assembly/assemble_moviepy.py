"""Same smoke timeline as timeline_smoke.json, built with MoviePy 2.2.1 (for comparison).

  IMAGEIO_FFMPEG_EXE=/opt/homebrew/bin/ffmpeg .venv/bin/python -I tools/assembly/assemble_moviepy.py

MoviePy has no libass, so captions here come from the SRT via Pillow TextClips
(no per-word highlight); the ffmpeg path burns the styled .ass instead.
"""
import time
from pathlib import Path

import numpy as np
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip, TextClip,
                     VideoFileClip, afx, vfx)
from moviepy.video.tools.subtitles import SubtitlesClip

HERE = Path(__file__).resolve().parent
A = HERE / "assets"
W, H, FPS, TOTAL = 1920, 1080, 30, 16.6
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"

# V1: still with Ken Burns zoom about (0.35, 0.45), then crossfade into a Manim clip
z = lambda t: 1 + 0.08 * t / 8
ui = (ImageClip(str(A / "ui_mock.png")).with_duration(8)
      .resized(lambda t: z(t))
      .with_position(lambda t: (0.35 * W * (1 - z(t)), 0.45 * H * (1 - z(t)))))
weib = VideoFileClip(str(A / "WeibullCurves.mp4")).with_start(7.4).with_effects([vfx.CrossFadeIn(0.6)])

# V2: transparent Manim overlay (qtrle argb .mov)
eq = (VideoFileClip(str(A / "BayesEquation_alpha_qtrle.mov"), has_mask=True)
      .subclipped(0, 6.4).resized(0.5).with_start(0.8)
      .with_position((W - 960 - 40, H - 540 - 150))
      .with_effects([vfx.CrossFadeIn(0.2), vfx.CrossFadeOut(0.5)]))

# Captions from SRT (shifted by the narration start)
subs = SubtitlesClip(str(A / "captions.srt"), make_textclip=lambda txt: TextClip(
    font=FONT, text=txt, font_size=54, color="#0B0D10", bg_color="white", margin=(24, 10)))
subs = subs.with_start(1.0).with_position(("center", H - 150))

video = CompositeVideoClip([ui, eq, weib, subs], size=(W, H), bg_color=(255, 255, 255)).with_duration(TOTAL)

# Audio: narration at 1.0 s; music bed -4 dB with fades and a deterministic duck envelope
nar = AudioFileClip(str(A / "narration.wav")).with_start(1.0)
span = (1.0 + 0.275, 1.0 + 13.075)
def env(t):
    t = np.asarray(t, dtype=float)
    d = np.minimum(np.clip((t - (span[0] - 0.25)) / 0.25, 0, 1), np.clip(((span[1] + 0.6) - t) / 0.6, 0, 1))
    return 1 - (1 - 10 ** (-12 / 20)) * d
music = (AudioFileClip(str(A / "music_bed.wav")).subclipped(0, TOTAL)
         .with_effects([afx.MultiplyVolume(10 ** (-4 / 20)), afx.AudioFadeIn(1.0), afx.AudioFadeOut(2.0)]))
music = music.transform(lambda gf, t: gf(t) * (env(t)[:, None] if np.ndim(t) else env(t)), keep_duration=True)
video = video.with_audio(CompositeAudioClip([music, nar]).with_duration(TOTAL))

out = HERE / "out" / "smoke_moviepy.mp4"; out.parent.mkdir(exist_ok=True)
t0 = time.perf_counter()
video.write_videofile(str(out), fps=FPS, codec="libx264", audio_codec="aac", audio_fps=48000,
                      preset="medium", ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
                      threads=8, logger=None)
print({"out": str(out), "render_s": round(time.perf_counter() - t0, 2), "timeline_s": TOTAL})
