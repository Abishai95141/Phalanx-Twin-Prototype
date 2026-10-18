"""M1 - Bayes from outcomes (shot S25, whole shot: 11.5 s = 345 frames @ 30 fps).

Left: the contract's suspect weight HYD-101 -> hydraulic pump = 0.8 (isolation confidence from the BIT code).
Right: Jeffreys prior Beta(1/2, 1/2) updated by fleet outcomes.
  P(confirmed pump fault | HYD-101): 0 confirmed of 107 jobs -> Beta(0.5, 107.5)
  P(RTOK | removal):               33 RTOK of 33 pump shop findings -> Beta(33.5, 0.5)
Numbers are computed below with scipy (equal-tailed 95 % intervals). Synthetic preview data (Phalanx v0.9).

Render:  cd video/tools/manim && ../../.venv/bin/manim render film/m1_bayes.py M1Bayes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.optimize import brentq
from scipy.stats import beta as B
from manim import (
    Brace, Create, FadeIn, FadeOut, Line, MathTex, Polygon, Rectangle, Transform, ValueTracker, VGroup,
    VMobject, Write, always_redraw, interpolate_color, rate_functions as rf, DOWN, LEFT, RIGHT, UP,
)
from phx_style import ACCENT, BLUE, GHOST, INK, INK2, INK3, LINE, SAFE_BOTTOM, Clip, sec_to_frame, words

# ---------------------------------------------------------------- numbers (computed, not typed)
K1, N1 = 0, 107          # HYD-101 fleet jobs: confirmed pump faults of jobs
K2, N2 = 33, 33          # pump shop findings: RTOK of removals (tail-less shop rows linked by job + serial)
A0 = B0 = 0.5            # Jeffreys prior
post1 = B(A0 + K1, B0 + N1 - K1)
post2 = B(A0 + K2, B0 + N2 - K2)
M1_MEAN, (M1_LO, M1_HI) = post1.mean(), post1.ppf([0.025, 0.975])
M2_MEAN, (M2_LO, M2_HI) = post2.mean(), post2.ppf([0.025, 0.975])
assert f"{M1_MEAN:.3f}" == "0.005" and f"{M1_LO:.3f}" == "0.000" and f"{M1_HI:.3f}" == "0.023"
assert f"{M2_MEAN:.3f}" == "0.985" and f"{M2_LO:.2f}" == "0.93" and f"{M2_HI:.2f}" == "1.00"

VO = 0.28                # narration starts 0.28 s into the shot
F_HALF = sec_to_frame(VO + 3.810)      # "half a percent"
F_98 = sec_to_frame(VO + 6.685)        # "ninety-eight percent"
F_NFF = sec_to_frame(VO + 8.897)       # "no fault found"

# ---------------------------------------------------------------- geometry
X0, X1 = -1.85, 6.15     # theta axis 0..1
YB, H = -1.65, 3.0       # baseline, density display height


def X(th):
    return X0 + th * (X1 - X0)


TH = np.unique(np.concatenate([
    np.geomspace(1e-7, 0.06, 260), np.linspace(0.06, 0.94, 160), 1 - np.geomspace(0.06, 1e-7, 260)]))

# display scale: both final posteriors share one y-scale (Y_TOP); during each update the scale tracks the
# density so the curve always reaches the top at a fixed theta* (3b1b-style axis rescale)
TH1 = 0.004
Y_TOP = post1.pdf(TH1)
TH2 = brentq(lambda t: post2.pdf(t) - Y_TOP, 0.9, 1 - 1e-9)


def dens_points(a, b, ymax, lo=0.0, hi=1.0):
    th = TH[(TH >= lo) & (TH <= hi)]
    if lo > TH[0]:
        th = np.concatenate([[lo], th])
    if hi < TH[-1]:
        th = np.concatenate([th, [hi]])
    y = np.clip(B.pdf(th, a, b) / ymax, 0, 1) * H
    return [np.array([X(t), YB + v, 0.0]) for t, v in zip(th, y)]


def curve(a, b, ymax, color, width=4.5):
    pts = np.array(dens_points(a, b, ymax))
    keep = (pts[:, 1] - YB) > 0.004            # drop the part that lies on the axis (< 0.6 px)
    dil = keep.copy()
    dil[1:] |= keep[:-1]
    dil[:-1] |= keep[1:]
    keep = dil
    v = VMobject(stroke_color=color, stroke_width=width)
    v.set_points_as_corners(list(pts[keep]))
    return v


def brace_lik(eq):
    return Brace(VGroup(eq[6], eq[7]), DOWN, buff=0.1, color=INK3, sharpness=1.6)


def brace_pri(eq):
    return Brace(eq[8], DOWN, buff=0.1, color=INK3, sharpness=1.6)


def place_lik(mob, br):
    return mob.next_to(br, DOWN, buff=0.1).align_to(br, RIGHT).shift(0.06 * LEFT)


def place_pri(mob, br):
    return mob.next_to(br, DOWN, buff=0.1).align_to(br, LEFT).shift(0.14 * RIGHT)


def area(a, b, ymax, color, opacity, lo=0.0, hi=1.0):
    pts = dens_points(a, b, ymax, lo, hi)
    poly = [np.array([pts[0][0], YB, 0])] + pts + [np.array([pts[-1][0], YB, 0])]
    return Polygon(*poly, stroke_width=0, fill_color=color, fill_opacity=opacity)


def eq_parts(k, n, nk):
    return [r"p(\theta\mid", k, r",\,", n, r")", r"\;\propto\;", r"\theta^{%s}" % k,
            r"(1-\theta)^{%s}" % nk, r"\;\theta^{-1/2}(1-\theta)^{-1/2}"]


def make_eq(k="k", n="n", nk="n-k"):
    eq = MathTex(*eq_parts(k, n, nk), font_size=38, color=INK)
    eq[1].set_color(BLUE)
    eq[3].set_color(BLUE)
    eq[6][1:].set_color(BLUE)
    eq[7][5:].set_color(BLUE)
    return eq.move_to([2.15, 2.8, 0])


class M1Bayes(Clip):
    TOTAL_FRAMES = 345

    def construct(self):
        # ---------------- left panel: what the code says
        bx = -4.9
        frame = Rectangle(width=1.0, height=H, stroke_color=LINE, stroke_width=2).move_to([bx, YB + H / 2, 0])
        bar = Rectangle(width=1.0, height=0.8 * H, stroke_color=INK, stroke_width=2,
                        fill_color=GHOST, fill_opacity=0.35).align_to(frame, DOWN).align_to(frame, LEFT)
        base = Line([bx - 0.62, YB, 0], [bx + 0.62, YB, 0], color=INK, stroke_width=2.5)
        t0 = MathTex("0", font_size=26, color=INK3).next_to([bx - 0.62, YB, 0], LEFT, buff=0.12)
        t1 = MathTex("1", font_size=26, color=INK3).next_to([bx - 0.5, YB + H, 0], LEFT, buff=0.24)
        val = words("0.8", 44, INK, "SEMIBOLD").next_to(bar.get_corner(RIGHT + UP), RIGHT, buff=0.22)
        val.align_to(bar, UP).shift(0.06 * UP)
        head = words("HYD-101  →  hydraulic pump", 16, INK2, "SEMIBOLD")
        head.move_to([bx, YB + H + 0.42, 0])
        cap = VGroup(words("isolation confidence,", 16, INK2), words("from the BIT code", 16, INK2)) \
            .arrange(DOWN, buff=0.1).next_to(base, DOWN, buff=0.28)
        left = VGroup(frame, bar, base, t0, t1, val, head, cap)

        # ---------------- right panel: theta axis
        axis = Line([X0, YB, 0], [X1, YB, 0], color=INK, stroke_width=2.5)
        ticks = VGroup(*[Line([X(t), YB, 0], [X(t), YB - 0.09, 0], color=INK, stroke_width=2)
                         for t in (0, 0.25, 0.5, 0.75, 1)])
        tl = VGroup(*[MathTex(s, font_size=27, color=INK).next_to([X(t), YB - 0.09, 0], DOWN, buff=0.14)
                      for t, s in ((0, "0"), (0.5, "0.5"), (1, "1"))])
        thl = MathTex(r"\theta", font_size=32, color=INK).next_to([X1, YB, 0], RIGHT, buff=0.18)
        right = VGroup(axis, ticks, tl, thl)

        self.add(left, right)
        for m in (left, right):
            assert m.get_bottom()[1] > SAFE_BOTTOM + 0.05, m.get_bottom()

        # ---------------- equation (general)
        eq = make_eq()
        br_lik, br_pri = brace_lik(eq), brace_pri(eq)
        pri_lbl = place_pri(VGroup(words("Jeffreys prior", 14, INK3),
                                   MathTex(r"\mathrm{Beta}(\tfrac12,\tfrac12)", font_size=24, color=INK3))
                            .arrange(RIGHT, buff=0.1), br_pri)

        n1 = ValueTracker(0.0)
        k2 = ValueTracker(0.0)
        mode = {"part": 1}

        def lik_label():
            if mode["part"] == 1:
                s = f"0 confirmed of {int(round(n1.get_value()))} jobs"
            else:
                k = int(round(k2.get_value()))
                s = f"{k} RTOK of {k} pump shop findings"
            return place_lik(words(s, 14, BLUE, "SEMIBOLD"), br_lik)

        lik_lbl = always_redraw(lik_label)

        # ---------------- prior -> posterior 1 (driven by n1)
        def ab1():
            n = n1.get_value()
            return A0 + K1, B0 + n - K1

        def ymax1():
            a, b = ab1()
            return B.pdf(TH1, a, b)

        def col1():
            return interpolate_color(GHOST, ACCENT, rf.smooth(min(1.0, n1.get_value() / 12)))

        c1 = always_redraw(lambda: curve(*ab1(), ymax1(), col1()))
        f1 = always_redraw(lambda: area(*ab1(), ymax1(), ACCENT, 0.10 * min(1.0, n1.get_value() / 12)))

        # Beat 1: write the general equation, draw the prior
        self.span(Write(eq), f0=3, f1=32, rate_func=rf.ease_out_sine)
        self.add(f1)
        self.span(Create(c1), FadeIn(br_lik), FadeIn(br_pri), FadeIn(pri_lbl, shift=0.08 * UP),
                  FadeIn(lik_lbl), f0=32, f1=56, rate_func=rf.ease_in_out_sine)

        # Beat 2: outcomes accumulate, density collapses against zero ("the chance this pump...")
        self.span(n1.animate.set_value(N1), f0=58, f1=102, rate_func=rf.ease_in_out_cubic)
        c1.clear_updaters(); f1.clear_updaters()
        c1.become(curve(*ab1(), Y_TOP, ACCENT)); f1.become(area(*ab1(), Y_TOP, ACCENT, 0.10))
        lik_lbl.clear_updaters()

        eq1 = make_eq("0", "107", "107")
        self.span(*[Transform(eq[i], eq1[i]) for i in range(len(eq))],
                  br_lik.animate.become(brace_lik(eq1)), br_pri.animate.become(brace_pri(eq1)),
                  place_pri(pri_lbl.animate, brace_pri(eq1)), place_lik(lik_lbl.animate, brace_lik(eq1)),
                  f0=102, f1=114, rate_func=rf.ease_in_out_sine)

        # interval + readout land on "half a percent"
        a1, b1 = A0 + K1, B0 + N1 - K1
        ci1_fill = area(a1, b1, Y_TOP, ACCENT, 0.42, M1_LO, M1_HI)
        ci1_bar = Line([X(M1_LO), YB - 0.13, 0], [X(M1_HI), YB - 0.13, 0], color=ACCENT, stroke_width=9)
        r1_lbl = MathTex(r"P(\text{confirmed pump fault}\mid\text{HYD-101})", font_size=27, color=INK)
        r1_num = words(f"{100 * M1_MEAN:.1f} %", 56, ACCENT, "SEMIBOLD")
        r1_st = MathTex(r"\text{mean } %.3f \qquad 95\%%\ \text{interval } [%.3f,\ %.3f]" % (M1_MEAN, M1_LO, M1_HI),
                        font_size=24, color=INK2)
        r1 = VGroup(r1_lbl, r1_num, r1_st).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
        r1.move_to([X(0.04), 1.2, 0], aligned_edge=LEFT + UP)
        self.span(FadeIn(ci1_fill), Create(ci1_bar), FadeIn(r1_lbl, shift=0.1 * UP), f0=114, f1=F_HALF - 3)
        self.run(FadeIn(r1_num, shift=0.12 * UP), FadeIn(r1_st, shift=0.08 * UP), frames=10,
                 rate_func=rf.ease_out_cubic)

        # Beat 3: "Remove it again" -> ghost part 1, reset equation, new prior for RTOK
        r1c = VGroup(words(f"{100 * M1_MEAN:.1f} %", 30, INK, "SEMIBOLD"),
                     MathTex(r"P(\text{fault}\mid\text{HYD-101})", font_size=22, color=INK3)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=0.12).move_to([X(0.04), 1.2, 0], aligned_edge=LEFT + UP)
        eq_g = make_eq()
        mode["part"] = 2

        def ab2():
            k = k2.get_value()
            return A0 + k, B0 + (k - k)

        def ymax2():
            a, b = ab2()
            return B.pdf(TH2, a, b)

        def col2():
            return interpolate_color(GHOST, ACCENT, rf.smooth(min(1.0, k2.get_value() / 6)))

        c2 = always_redraw(lambda: curve(*ab2(), ymax2(), col2()))
        f2 = always_redraw(lambda: area(*ab2(), ymax2(), ACCENT, 0.10 * min(1.0, k2.get_value() / 6)))

        f_r = 150
        lik_lbl2 = always_redraw(lik_label)
        self.add(f2)
        self.span(c1.animate.set_stroke(GHOST, width=3.5), f1.animate.set_fill(GHOST, opacity=0.08),
                  ci1_fill.animate.set_fill(GHOST, opacity=0.25), ci1_bar.animate.set_stroke(GHOST),
                  FadeOut(r1_lbl), FadeOut(r1_st), Transform(r1_num, r1c[0]), FadeIn(r1c[1]),
                  *[Transform(eq[i], eq_g[i]) for i in range(len(eq))],
                  br_lik.animate.become(brace_lik(eq_g)), br_pri.animate.become(brace_pri(eq_g)),
                  place_pri(pri_lbl.animate, brace_pri(eq_g)),
                  FadeOut(lik_lbl), FadeIn(lik_lbl2), Create(c2),
                  f0=f_r, f1=f_r + 14, rate_func=rf.ease_in_out_sine)

        # Beat 4: 33 of 33 RTOK -> mass piles near 1
        self.span(k2.animate.set_value(K2), f0=f_r + 14, f1=F_98 - 13, rate_func=rf.ease_in_out_cubic)
        c2.clear_updaters(); f2.clear_updaters(); lik_lbl2.clear_updaters()
        a2, b2 = A0 + K2, B0 + N2 - K2
        c2.become(curve(a2, b2, Y_TOP, ACCENT)); f2.become(area(a2, b2, Y_TOP, ACCENT, 0.10))

        eq2 = make_eq(str(K2), str(N2), str(N2 - K2))
        nb_lik, nb_pri = brace_lik(eq2), brace_pri(eq2)
        ci2_fill = area(a2, b2, Y_TOP, ACCENT, 0.42, M2_LO, M2_HI)
        ci2_bar = Line([X(M2_LO), YB - 0.13, 0], [X(M2_HI), YB - 0.13, 0], color=ACCENT, stroke_width=9)
        r2_lbl = MathTex(r"P(\text{RTOK}\mid\text{removal})", font_size=27, color=INK)
        r2_num = words(f"{100 * M2_MEAN:.1f} %", 56, ACCENT, "SEMIBOLD")
        r2_st = MathTex(r"\text{mean } %.3f \qquad 95\%%\ \text{interval } [%.2f,\ %.2f]" % (M2_MEAN, M2_LO, M2_HI),
                        font_size=24, color=INK2)
        r2 = VGroup(r2_lbl, r2_num, r2_st).arrange(DOWN, aligned_edge=RIGHT, buff=0.16)
        r2.move_to([X(0.955), 1.2, 0], aligned_edge=RIGHT + UP)
        self.span(*[Transform(eq[i], eq2[i]) for i in range(len(eq))],
                  br_lik.animate.become(nb_lik), br_pri.animate.become(nb_pri),
                  place_pri(pri_lbl.animate, nb_pri), place_lik(lik_lbl2.animate, nb_lik),
                  FadeIn(ci2_fill), Create(ci2_bar), FadeIn(r2_lbl, shift=0.1 * UP),
                  f0=F_98 - 13, f1=F_98 - 5, rate_func=rf.ease_in_out_sine)
        self.run(FadeIn(r2_num, shift=0.12 * UP), FadeIn(r2_st, shift=0.08 * UP), frames=10,
                 rate_func=rf.ease_out_cubic)

        # Beat 5: gloss on "no fault found"
        gloss = words("RTOK: retested OK — no fault found", 15, INK3).next_to(r2, DOWN, buff=0.22)
        gloss.align_to(r2, RIGHT)
        self.span(FadeIn(gloss, shift=0.08 * UP), f0=F_NFF - 4, f1=F_NFF + 10)
        self.finish()
