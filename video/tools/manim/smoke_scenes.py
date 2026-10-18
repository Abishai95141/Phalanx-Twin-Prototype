"""Manim CE smoke test for the Phalanx Twin launch video.

House style: white paper, near-black ink #0B0D10, one accent #E8743B, a muted grey
for "ghost"/reference elements. Render from this directory (manim.cfg sets 1920x1080@30):

  cd video/tools/manim
  ../../.venv/bin/manim render smoke_scenes.py WeibullCurves
  ../../.venv/bin/manim render smoke_scenes.py BayesUpdate
  ../../.venv/bin/manim render smoke_scenes.py BayesEquation
  # transparent overlay version (ProRes 4444 .mov with alpha):
  ../../.venv/bin/manim render -t smoke_scenes.py BayesEquation

NOTE: synthetic illustration only -- beta/eta/likelihood values are made up and
are not Tejas/F404 data.
"""
import numpy as np
from manim import (
    Axes, Create, DashedLine, DecimalNumber, Dot, FadeIn, FadeOut, LaggedStart,
    MathTex, ReplacementTransform, Scene, SurroundingRectangle, Text,
    TransformMatchingTex, VGroup, ValueTracker, Write, always_redraw,
    DOWN, LEFT, RIGHT, UP, UL, UR, ManimColor, rate_functions,
)
from scipy.stats import beta as beta_dist

INK = ManimColor("#0B0D10")
ACCENT = ManimColor("#E8743B")
GHOST = ManimColor("#9AA0A6")
FONT = "Helvetica Neue"

# Make every default-coloured object ink instead of Manim's white.
for cls in (Text, MathTex, DecimalNumber):
    cls.set_default(color=INK)

AXIS_CFG = dict(color=INK, stroke_width=2.5, include_tip=False,
                font_size=26, tick_size=0.06)


def label(txt, size=30, **kw):
    return Text(txt, font=FONT, font_size=size, color=kw.pop("color", INK), **kw)


class WeibullCurves(Scene):
    """Weibull survival S(t) and hazard h(t) drawing on, with a 'now' marker."""

    def construct(self):
        b, eta = 2.2, 1200.0                       # illustrative shape / scale (flight hours)
        S = lambda t: np.exp(-(t / eta) ** b)
        h = lambda t: (b / eta) * (t / eta) ** (b - 1) * 1000  # per 1000 FH

        title = label("Remaining-life model: Weibull", 40, weight="BOLD").to_corner(UL, buff=0.6)

        ax_s = Axes(x_range=[0, 2400, 600], y_range=[0, 1.0, 0.25], x_length=5.4, y_length=3.6,
                    axis_config=AXIS_CFG, x_axis_config={"numbers_to_include": [0, 600, 1200, 1800, 2400]},
                    y_axis_config={"numbers_to_include": [0, 0.5, 1.0], "decimal_number_config": {"num_decimal_places": 1, "color": INK}})
        ax_h = Axes(x_range=[0, 2400, 600], y_range=[0, 4.5, 1], x_length=5.4, y_length=3.6,
                    axis_config=AXIS_CFG, x_axis_config={"numbers_to_include": [0, 600, 1200, 1800, 2400]},
                    y_axis_config={"numbers_to_include": [0, 1, 2, 3, 4]})
        VGroup(ax_s, ax_h).arrange(RIGHT, buff=1.6).move_to(DOWN * 0.7)
        for ax in (ax_s, ax_h):
            for n in ax.x_axis.numbers + ax.y_axis.numbers:
                n.set_color(INK)

        xl_s = label("flight hours", 24).next_to(ax_s.x_axis, DOWN, buff=0.45)
        xl_h = label("flight hours", 24).next_to(ax_h.x_axis, DOWN, buff=0.45)
        eq_s = MathTex(r"S(t)=e^{-(t/\eta)^{\beta}}", font_size=40).next_to(ax_s, UP, buff=0.25)
        eq_h = MathTex(r"h(t)=\frac{\beta}{\eta}\left(\frac{t}{\eta}\right)^{\beta-1}", font_size=40).next_to(ax_h, UP, buff=0.25)

        curve_s = ax_s.plot(S, x_range=[0, 2400], color=INK, stroke_width=5)
        curve_h = ax_h.plot(h, x_range=[0, 2400], color=ACCENT, stroke_width=5)

        self.play(FadeIn(title, shift=0.2 * DOWN), Create(ax_s), Create(ax_h),
                  FadeIn(xl_s), FadeIn(xl_h), run_time=1.2)
        self.play(Write(eq_s), Write(eq_h), run_time=1.2)
        self.play(Create(curve_s), Create(curve_h), run_time=2.5, rate_func=rate_functions.ease_in_out_sine)

        t = ValueTracker(600)
        dot = always_redraw(lambda: Dot(ax_s.c2p(t.get_value(), S(t.get_value())), radius=0.08, color=ACCENT))
        guide = always_redraw(lambda: DashedLine(ax_s.c2p(t.get_value(), 0), ax_s.c2p(t.get_value(), S(t.get_value())),
                                                 color=GHOST, stroke_width=2.5, dash_length=0.08))
        readout = always_redraw(lambda: VGroup(
            MathTex(r"S(t)=", font_size=34),
            DecimalNumber(S(t.get_value()), num_decimal_places=2, font_size=34, color=ACCENT),
        ).arrange(RIGHT, buff=0.12).next_to(ax_s.c2p(t.get_value(), S(t.get_value())), UR, buff=0.15))
        self.play(FadeIn(dot), FadeIn(guide), FadeIn(readout))
        self.play(t.animate.set_value(1500), run_time=2.5, rate_func=rate_functions.ease_in_out_cubic)
        self.wait(0.8)


class BayesUpdate(Scene):
    """Prior Beta distribution over a fault rate morphs into the posterior after evidence."""

    def construct(self):
        ax = Axes(x_range=[0, 0.6, 0.1], y_range=[0, 9, 3], x_length=10, y_length=4.6,
                  axis_config=AXIS_CFG, x_axis_config={"numbers_to_include": [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                                                       "decimal_number_config": {"num_decimal_places": 1, "color": INK}})
        ax.shift(DOWN * 0.5)
        for n in ax.x_axis.numbers:
            n.set_color(INK)
        xl = MathTex(r"p_{\text{fault}}", font_size=36).next_to(ax.x_axis, DOWN, buff=0.45)
        title = label("Belief about a fault, before and after evidence", 40, weight="BOLD").to_corner(UL, buff=0.6)

        a, b = ValueTracker(2.0), ValueTracker(18.0)          # prior Beta(2, 18): mean 0.10
        def pdf_curve(color, width=5, a_=None, b_=None):
            aa = a.get_value() if a_ is None else a_
            bb = b.get_value() if b_ is None else b_
            return ax.plot(lambda x: beta_dist.pdf(x, aa, bb), x_range=[0.001, 0.6, 0.004],
                           color=color, stroke_width=width, use_smoothing=False)
        curve = always_redraw(lambda: pdf_curve(INK))
        area = always_redraw(lambda: ax.get_area(pdf_curve(INK), x_range=[0.001, 0.6], color=ACCENT, opacity=0.18))

        prior_lbl = MathTex(r"\text{prior}\;\mathrm{Beta}(2,18)", font_size=36).move_to(ax.c2p(0.47, 6.5))
        self.play(FadeIn(title, shift=0.2 * DOWN), Create(ax), FadeIn(xl), run_time=1.0)
        self.play(Create(curve), FadeIn(area), Write(prior_lbl), run_time=1.8)

        ghost = pdf_curve(GHOST, width=3, a_=2.0, b_=18.0).set_stroke(opacity=0.9)
        evidence = label("Evidence: 3 of 10 sorties raised fault code F-217 (synthetic)", 28, color=ACCENT)
        evidence.next_to(title, DOWN, aligned_edge=LEFT, buff=0.3)
        self.add(ghost)
        self.play(FadeIn(evidence, shift=0.1 * RIGHT), run_time=0.8)

        post_lbl = MathTex(r"\text{posterior}\;\mathrm{Beta}(5,25)", font_size=36, color=ACCENT).move_to(prior_lbl)
        self.play(a.animate.set_value(5.0), b.animate.set_value(25.0),
                  ReplacementTransform(prior_lbl, post_lbl), run_time=2.5, rate_func=rate_functions.ease_in_out_sine)
        mean_line = DashedLine(ax.c2p(5 / 30, 0), ax.c2p(5 / 30, beta_dist.pdf(5 / 30, 5, 25)), color=ACCENT, stroke_width=3)
        mean_lbl = MathTex(r"\mathbb{E}[p]=0.17", font_size=32, color=ACCENT).next_to(ax.c2p(5 / 30, 0), UP + RIGHT, buff=0.15).shift(UP * 0.3)
        self.play(Create(mean_line), FadeIn(mean_lbl), run_time=1.0)
        self.wait(0.8)


class BayesEquation(Scene):
    """Bayes' rule written, coloured by term, then transformed into numbers."""

    def construct(self):
        eq = MathTex(r"P(\text{fault}\mid\text{code})", "=",
                     r"{P(\text{code}\mid\text{fault})", r"\,P(\text{fault})", r"\over", r"P(\text{code})}",
                     font_size=72)
        eq[0].set_color(ACCENT)
        self.play(Write(eq), run_time=2.2)
        box = SurroundingRectangle(eq[3], color=ACCENT, buff=0.12, stroke_width=3)
        prior_tag = Text("prior", font=FONT, font_size=28, color=ACCENT).next_to(box, UP, buff=0.15)
        self.play(Create(box), FadeIn(prior_tag, shift=0.1 * DOWN), run_time=0.8)
        self.wait(0.4)

        num = MathTex(r"P(\text{fault}\mid\text{code})", "=", r"{0.90", r"\times 0.02", r"\over", r"0.05}",
                      font_size=72)
        num[0].set_color(ACCENT)
        self.play(FadeOut(box), FadeOut(prior_tag), run_time=0.4)
        self.play(TransformMatchingTex(eq, num), run_time=1.6)
        result = MathTex(r"P(\text{fault}\mid\text{code})", "=", "0.36", font_size=72)
        result[0].set_color(ACCENT); result[2].set_color(ACCENT)
        self.play(TransformMatchingTex(num, result), run_time=1.4)
        note = Text("illustrative numbers", font=FONT, font_size=26, color=GHOST).next_to(result, DOWN, buff=0.5)
        self.play(FadeIn(note), run_time=0.5)
        self.wait(0.8)
