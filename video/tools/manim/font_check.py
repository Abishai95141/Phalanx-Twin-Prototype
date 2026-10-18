"""Brand fonts in Manim: register the static Manrope / JetBrains Mono TTFs, then use them in Text()."""
from pathlib import Path
import manimpango
from manim import Scene, Text, VGroup, DOWN, LEFT, ManimColor, SEMIBOLD, NORMAL, BOLD

FONTS = Path(__file__).resolve().parent.parent / "fonts" / "static"
for ttf in sorted(FONTS.glob("*.ttf")):
    manimpango.register_font(str(ttf))
INK, ACCENT = ManimColor("#0B0D10"), ManimColor("#E8743B")

class FontCheck(Scene):
    def construct(self):
        g = VGroup(
            Text("Manrope Regular: Phalanx Twin", font="Manrope", weight=NORMAL, font_size=56, color=INK),
            Text("Manrope SemiBold: signed decisions", font="Manrope", weight=SEMIBOLD, font_size=56, color=INK),
            Text("Manrope Bold: fleet availability", font="Manrope", weight=BOLD, font_size=56, color=ACCENT),
            Text("JetBrains Mono: TAIL-07  F-217  0.36", font="JetBrains Mono", font_size=48, color=INK),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.5).scale_to_fit_width(12)
        self.add(g)
        print("available:", [f for f in manimpango.list_fonts() if "Manrope" in f or "JetBrains" in f])
