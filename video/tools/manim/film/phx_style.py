"""House style + frame-exact timing helpers for the Phalanx Twin film's Manim clips.

White paper, ink #0B0D10, one accent #E8743B (the quantity that matters), blue #2563C9 (evidence),
grey #9AA0A6 (ghosts). Manrope for words, Computer Modern (MathTex) for maths.
Synthetic preview data only (Phalanx v0.9) -- not Tejas/IAF data, not validated physics.
"""
from pathlib import Path

import manimpango
from manim import (DecimalNumber, ManimColor, MathTex, Scene, Tex, Text, Wait, config)

FONTS = Path(__file__).resolve().parents[2] / "fonts" / "static"
for _ttf in sorted(FONTS.glob("*.ttf")):
    manimpango.register_font(str(_ttf))

INK = ManimColor("#0B0D10")
INK2 = ManimColor("#31353B")
INK3 = ManimColor("#62676F")
ACCENT = ManimColor("#E8743B")
BLUE = ManimColor("#2563C9")
GHOST = ManimColor("#9AA0A6")
LINE = ManimColor("#D6D6D1")
WHITE_PAPER = ManimColor("#FFFFFF")

for _cls in (Text, MathTex, Tex, DecimalNumber):
    _cls.set_default(color=INK)

FPS = 30
# Caption-safe area: nothing below this y (bottom 160 px of 1080 = 1.185 frame units).
SAFE_BOTTOM = -config.frame_height / 2 + 160 / 1080 * config.frame_height


def words(s, size=28, color=INK, weight="MEDIUM", font="Manrope", **kw):
    return Text(s, font=font, weight=weight, font_size=size, color=color, **kw)


def mono(s, size=24, color=INK, weight="NORMAL", **kw):
    return Text(s, font="JetBrains Mono", weight=weight, font_size=size, color=color, **kw)


class Clip(Scene):
    """Scene with a frame counter. Every play/hold is an exact number of frames.

    Manim renders len(arange(0, run_time, 1/fps)) frames per play; run_time = (n - 0.5)/fps gives exactly n.
    """

    TOTAL_FRAMES = None

    def setup(self):
        self.camera.background_color = WHITE_PAPER
        self.fc = 0

    def run(self, *anims, frames, **kw):
        assert frames >= 1
        self.play(*anims, run_time=(frames - 0.5) / FPS, **kw)
        self.fc += frames

    def hold(self, frames):
        if frames <= 0:
            return
        self.wait((frames - 0.5) / FPS, frozen_frame=False)
        self.fc += frames

    def at(self, frame):
        """Hold until the given absolute frame index (the next play starts on it)."""
        assert frame >= self.fc, (frame, self.fc)
        self.hold(frame - self.fc)

    def span(self, *anims, f0, f1, **kw):
        """Play anims from absolute frame f0 to f1 (exclusive)."""
        self.at(f0)
        self.run(*anims, frames=f1 - f0, **kw)

    def finish(self):
        self.hold(self.TOTAL_FRAMES - self.fc)
        assert self.fc == self.TOTAL_FRAMES, (self.fc, self.TOTAL_FRAMES)


def sec_to_frame(t):
    return int(round(t * FPS))
