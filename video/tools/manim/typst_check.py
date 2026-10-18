"""No-LaTeX fallback check: Manim CE >= 0.21 MathTypst (bundled Typst compiler, pip `manim[typst]`)."""
from manim import Scene, MathTypst, Write, ManimColor, DOWN

INK, ACCENT = ManimColor("#0B0D10"), ManimColor("#E8743B")

class BayesTypst(Scene):
    def construct(self):
        eq = MathTypst(r'{{ P("fault" mid(|) "code") : lhs }} = (P("code" mid(|) "fault") {{ P("fault") : prior }}) / P("code")',
                       font_size=72, color=INK)
        eq.select("lhs").set_color(ACCENT)
        eq.select("prior").set_color(ACCENT)
        self.play(Write(eq), run_time=1.5)
        self.wait(0.5)
