"""M3 - The lead-time race (first 3.6 s of shot S29 = 108 frames @ 30 fps).

The data layer's AOG lead-time model (M18 supply): a log-normal fitted to the CAG 24/2017 IL-76 AOG timeliness
bins, scaled by the Tejas support factor 0.3 (assumption A-W1.8-10). Documented as median ~ 29 d, mean ~ 159 d;
sigma follows from mean = median * exp(sigma^2 / 2).

Plotted: survival S(t) = P(lead time > t). The area under S is the expected AOG wait with no stock on the shelf
(E[L] = integral of S). A warning w days ahead lets the order go in w days early, so the AOG days it recovers are
E[min(L, w)] = integral_0^w S(t) dt  (useful lead time = warning - lead time, when positive): the accent area.
Expected remaining wait after a demand has been open a days: integral_a^inf S / S(a).
Ends by fading to white in the last 0.3 s.  Synthetic model (Phalanx v0.9), not validated, not IAF data.

Render:  cd video/tools/manim && ../../.venv/bin/manim render film/m3_lead_time.py M3LeadTime
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy import integrate
from scipy.stats import lognorm
from manim import (
    Create, DashedLine, Dot, FadeIn, FadeOut, Line, MathTex, Polygon, ValueTracker, VGroup, VMobject,
    always_redraw, rate_functions as rf, DOWN, LEFT, RIGHT, UP,
)
from phx_style import ACCENT, BLUE, GHOST, INK, INK2, INK3, SAFE_BOTTOM, Clip, sec_to_frame, words

# ---------------------------------------------------------------- model + numbers (computed)
MEDIAN, MEAN = 29.0, 159.0                         # documented AOG lead-time model (days)
SIGMA = np.sqrt(2 * np.log(MEAN / MEDIAN))         # mean = median * exp(sigma^2/2)
L = lognorm(SIGMA, scale=MEDIAN)
W_END = 30.0                                       # warning horizon shown (days)
AGE_TJ108 = 79.92                                  # TJ108 brake-chute AOG demand: opened 3 Apr 08:00, as of 22 Jun 06:00


def e_remaining(a):
    return integrate.quad(L.sf, a, np.inf, limit=500)[0] / L.sf(a)


REC_30 = integrate.quad(L.sf, 0, W_END)[0] / L.mean()
EREM_0, EREM_30 = e_remaining(0.0), e_remaining(W_END)
assert abs(L.mean() - MEAN) < 1e-6 and abs(L.median() - MEDIAN) < 1e-9
assert round(100 * REC_30) == 13, REC_30
assert round(EREM_0) == 159 and 275 <= EREM_30 <= 290, (EREM_0, EREM_30)

VO = 0.28
F_WARNING = sec_to_frame(VO + 0.852)     # "warning"
F_BEATS = sec_to_frame(VO + 2.114)       # "beats"

# ---------------------------------------------------------------- geometry
T_MAX = 360.0
XA0, XA1 = -5.15, 5.25
YA0, YA1 = -1.72, 1.12
HY = YA1 - YA0


def X(t):
    return XA0 + t / T_MAX * (XA1 - XA0)


def Y(s):
    return YA0 + s * HY


TG = np.unique(np.concatenate([np.linspace(0, 45, 451), np.linspace(45, T_MAX, 316)]))
SG = L.sf(TG)
CUM = np.concatenate([[0.0], np.cumsum(np.diff(TG) * (SG[1:] + SG[:-1]) / 2)])   # integral_0^t S


def recovered(w):
    return np.interp(w, TG, CUM) / MEAN


def curve_pts(t0, t1):
    t = TG[(TG > t0) & (TG < t1)]
    t = np.concatenate([[t0], t, [t1]])
    return [np.array([X(v), Y(L.sf(v)), 0.0]) for v in t]


def area_under(t0, t1, color, opacity):
    pts = curve_pts(t0, t1)
    return Polygon(np.array([X(t0), YA0, 0]), *pts, np.array([X(t1), YA0, 0]),
                   stroke_width=0, fill_color=color, fill_opacity=opacity)


class M3LeadTime(Clip):
    TOTAL_FRAMES = 108

    def construct(self):
        # ---------------- composed first frame
        title = words("AOG lead-time model", 20, INK, "SEMIBOLD").to_corner(UP + LEFT, buff=0.62)
        sub = words(f"log-normal fit to IL-76 AOG lead times × 0.3 support factor  ·  "
                    f"median {MEDIAN:.0f} d  ·  mean {MEAN:.0f} d", 13, INK3)
        sub.next_to(title, DOWN, aligned_edge=LEFT, buff=0.12)

        xax = Line([XA0, YA0, 0], [XA1, YA0, 0], color=INK, stroke_width=2.5)
        yax = Line([XA0, YA0, 0], [XA0, YA1, 0], color=INK, stroke_width=2.5)
        xt = VGroup(*[Line([X(t), YA0, 0], [X(t), YA0 - 0.08, 0], color=INK, stroke_width=2)
                      for t in (0, 90, 180, 270, 360)])
        xl = VGroup(*[MathTex(str(t), font_size=26, color=INK2).next_to([X(t), YA0 - 0.08, 0], DOWN, buff=0.1)
                      for t in (0, 90, 180, 270, 360)])
        yt = VGroup(*[Line([XA0, Y(s), 0], [XA0 - 0.08, Y(s), 0], color=INK, stroke_width=2) for s in (0.5, 1)])
        yl = VGroup(*[MathTex(s, font_size=26, color=INK2).next_to([XA0 - 0.08, Y(v), 0], LEFT, buff=0.1)
                      for v, s in ((0, "0"), (0.5, "0.5"), (1, "1"))])
        xcap = words("days since the AOG demand was raised", 15, INK3).next_to(xl, DOWN, buff=0.16)
        xcap.set_x((XA0 + XA1) / 2)
        ycap = words("share still waiting", 15, INK3).rotate(np.pi / 2).move_to([XA0 - 0.75, Y(0.5), 0])
        frame0 = VGroup(title, sub, xax, yax, xt, xl, yt, yl, xcap, ycap)
        self.add(frame0)
        assert frame0.get_bottom()[1] > SAFE_BOTTOM + 0.05, frame0.get_bottom()
        assert frame0.get_left()[0] > -6.75 and frame0.get_right()[0] < 6.75

        # ---------------- the model: survival curve; area = expected AOG days
        crv = VMobject(stroke_color=INK, stroke_width=4).set_points_smoothly(curve_pts(0.0, T_MAX))
        grey = area_under(0.0, T_MAX, GHOST, 0.16)
        area_lbl = VGroup(words("area under the curve", 15, INK3),
                          words(f"= expected AOG wait, mean {MEAN:.0f} d", 15, INK3)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=0.08).move_to([X(205), Y(0.36), 0], aligned_edge=LEFT)
        tail = words("tail runs on past a year →", 13, GHOST).next_to([X(T_MAX), Y(L.sf(T_MAX)), 0], UP, buff=0.16)
        tail.align_to([XA1, 0, 0], RIGHT)

        p108 = np.array([X(AGE_TJ108), Y(L.sf(AGE_TJ108)), 0])
        dot108 = Dot(p108, radius=0.075, color=BLUE)
        lab108 = words("TJ108 · open 80 d", 15, BLUE, "SEMIBOLD").move_to(p108 + np.array([0.22, 0.62, 0]),
                                                                            aligned_edge=LEFT)
        lead108 = Line(p108 + 0.09 * UP, lab108.get_corner(DOWN + LEFT) + np.array([-0.04, -0.03, 0]),
                       color=BLUE, stroke_width=1.6)

        led_h = words("expected remaining wait", 14, INK3)
        led_r = VGroup(
            VGroup(words("when raised", 15, INK2), words(f"{EREM_0:.0f} d", 15, INK, "SEMIBOLD")),
            VGroup(words(f"open {W_END:.0f} d", 15, INK2), words(f"{EREM_30:.0f} d", 15, INK, "SEMIBOLD")),
        )
        led_r.arrange(DOWN, aligned_edge=LEFT, buff=0.1)
        for row in led_r:
            row.arrange(RIGHT, buff=0.3)
        led_r.arrange(DOWN, aligned_edge=LEFT, buff=0.1)
        x_num = max(row[0].get_right()[0] for row in led_r) + 0.3
        for row in led_r:                                    # numbers in one left-aligned column
            row[1].align_to([x_num, 0, 0], LEFT)
        ledger = VGroup(led_h, led_r).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        ledger.move_to([X(205), Y(0.86), 0], aligned_edge=LEFT)

        self.at(2)
        self.add(grey)
        grey.set_fill(opacity=0)
        self.run(Create(crv), grey.animate.set_fill(opacity=0.16), frames=20, rate_func=rf.ease_in_out_sine)
        self.span(FadeIn(area_lbl, shift=0.06 * UP), FadeIn(tail), FadeIn(dot108, scale=0.5), Create(lead108),
                  FadeIn(lab108, shift=0.06 * UP), f0=22, f1=F_WARNING - 3)

        # ---------------- the warning window slides; only what it beats is shaded
        w = ValueTracker(0.6)
        y_b = YA1 + 0.3

        def shade():
            return area_under(0.0, max(w.get_value(), 0.05), ACCENT, 0.42)

        def bracket():
            x1 = X(w.get_value())
            return VGroup(Line([X(0), y_b, 0], [x1, y_b, 0], color=ACCENT, stroke_width=4),
                          Line([X(0), y_b - 0.09, 0], [X(0), y_b + 0.09, 0], color=ACCENT, stroke_width=3),
                          Line([x1, y_b - 0.09, 0], [x1, y_b + 0.09, 0], color=ACCENT, stroke_width=3),
                          DashedLine([x1, YA0, 0], [x1, y_b, 0], color=ACCENT, stroke_width=1.8, dash_length=0.07))

        def blabel():
            return words(f"warning {w.get_value():.0f} d", 15, ACCENT, "SEMIBOLD") \
                .next_to([X(w.get_value()), y_b, 0], RIGHT, buff=0.14)

        def readout():
            pct = 100 * recovered(w.get_value())
            return VGroup(words(f"recovers {pct:.0f} %", 22, ACCENT, "SEMIBOLD"),
                          words("of expected AOG days (no stock on the shelf)", 15, INK2)) \
                .arrange(DOWN, aligned_edge=LEFT, buff=0.06) \
                .move_to([max(X(w.get_value()), X(12.0)) + 0.2, Y(0.74), 0], aligned_edge=LEFT)

        sh, br, bl, ro = (always_redraw(f) for f in (shade, bracket, blabel, readout))
        self.add(sh)
        self.bring_to_front(crv)
        self.span(FadeIn(br), FadeIn(bl), FadeIn(ro), f0=F_WARNING - 3, f1=F_WARNING + 3)
        cap = VGroup(words("useful lead time", 24, ACCENT, "SEMIBOLD"),
                     words("= warning − lead time", 24, INK, "MEDIUM")).arrange(RIGHT, buff=0.16)
        cap[1].shift((cap[0][0].get_bottom()[1] - cap[1][1].get_bottom()[1]) * UP)   # common baseline
        cap.next_to(sub, DOWN, aligned_edge=LEFT, buff=0.42)
        self.span(w.animate(rate_func=rf.ease_in_out_cubic).set_value(W_END),
                  FadeIn(ledger, shift=0.06 * UP, rate_func=rf.squish_rate_func(rf.smooth, 0.0, 0.3)),
                  FadeIn(cap, shift=0.06 * UP, rate_func=rf.squish_rate_func(rf.smooth, 0.62, 0.9)),
                  f0=F_WARNING + 3, f1=F_BEATS + 14)
        for m in (sh, br, bl, ro):
            m.clear_updaters()
        assert cap.get_right()[0] < 6.75 and ledger.get_right()[0] < 6.75

        # ---------------- fade to white in the last 0.3 s (9 frames; the last one is pure white)
        self.at(self.TOTAL_FRAMES - 9)
        self.run(*[FadeOut(m) for m in list(self.mobjects)], frames=8, rate_func=rf.ease_in_sine)
        self.finish()
