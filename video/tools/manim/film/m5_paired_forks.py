"""M5 - Paired forks / common random numbers (first 4.2 s of shot S28 = 126 frames @ 30 fps).

Two lanes of the same 30 futures (CRN members 0-29): status quo vs treatment (S1, TJ107, belief mode, 30-day
horizon), one row per future, connected pairwise. The pairs collapse into the 30 paired differences in
mission-capable fraction (mc) with the Student-t 95 % CI.  Ends by fading to white in the last 0.3 s.
Values are read from video/data/forks/scenario_S1.json (modes.belief.members[*].{status_quo,treatment}.mc).
Synthetic preview data (Phalanx v0.9 simulator, not validated).

Render:  cd video/tools/manim && ../../.venv/bin/manim render film/m5_paired_forks.py M5PairedForks
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy import stats
from manim import (
    AnimationGroup, Create, DashedLine, Dot, FadeIn, FadeOut, GrowFromCenter, LaggedStart, Line, MathTex,
    Transform, VGroup, rate_functions as rf, DOWN, LEFT, RIGHT, UP,
)
from phx_style import ACCENT, GHOST, INK, INK2, INK3, LINE, SAFE_BOTTOM, Clip, sec_to_frame, words

# ---------------------------------------------------------------- data (read + computed)
S1 = Path(__file__).resolve().parents[3] / "data" / "forks" / "scenario_S1.json"
_d = json.loads(S1.read_text())["modes"]["belief"]
_members = sorted(_d["members"], key=lambda m: m["member"])
assert [m["member"] for m in _members] == list(range(30))
SQ = np.array([m["status_quo"]["mc"] for m in _members])
TR = np.array([m["treatment"]["mc"] for m in _members])
DL = TR - SQ
N = len(DL)
D_MEAN = DL.mean()
_half = stats.t.ppf(0.975, N - 1) * DL.std(ddof=1) / np.sqrt(N)
D_LO, D_HI = D_MEAN - _half, D_MEAN + _half
_ref = _d["kpis"]["mc"]["paired_difference_treatment_minus_status_quo"]
assert abs(D_MEAN - _ref["mean"]) < 1e-9 and abs(D_LO - _ref["ci_low"]) < 1e-9 and abs(D_HI - _ref["ci_high"]) < 1e-9
assert (f"{D_MEAN:+.3f}", f"{D_LO:.3f}", f"{D_HI:.3f}") == ("+0.217", "0.167", "0.268")

VO = 0.28
F_PAIRED = sec_to_frame(VO + 3.123)     # "paired"

# ---------------------------------------------------------------- geometry
S = 5.0                                  # frame units per 1.0 of MC fraction (same in lanes and in delta panel)
L1 = -6.0                                # x of MC = 0.3 in the status-quo lane
L2 = L1 + 0.7 * S + 0.5                  # x of MC = 0.3 in the treatment lane
DZ = 2.35 + 0.2 * S                      # x of delta = 0 (delta panel spans -0.2 .. 0.6)
Y0, DY = 2.72, 0.148                     # row y for member 0, row spacing
YA = -1.86                               # lane axes / delta axis
R = 0.062                                # dot radius (rows)
RS = 0.082                               # dot radius (swarm)


def xl1(v):
    return L1 + (v - 0.3) * S


def xl2(v):
    return L2 + (v - 0.3) * S


def xd(v):
    return DZ + v * S


def yrow(m):
    return Y0 - m * DY


def beeswarm(vals, r, base):
    """Exact x, stacked y: each dot takes the lowest level free of overlap."""
    order = np.argsort(vals)
    placed, pos = [], {}
    for i in order:
        x = xd(vals[i])
        level = 0
        while any(abs(x - px) < 2 * r * 0.98 and lv == level for px, lv in placed):
            level += 1
        placed.append((x, level))
        pos[i] = np.array([x, base + r + 0.02 + level * 2 * r * 1.02, 0.0])
    return pos


class M5PairedForks(Clip):
    TOTAL_FRAMES = 126

    def construct(self):
        # ---------------- static, composed first frame
        def lane_axis(xf, lab_on=True):
            ax = Line([xf(0.3), YA, 0], [xf(1.0), YA, 0], color=INK, stroke_width=2)
            tk = VGroup(*[Line([xf(v), YA, 0], [xf(v), YA - 0.07, 0], color=INK, stroke_width=2)
                          for v in (0.4, 0.6, 0.8, 1.0)])
            tl = VGroup(*[MathTex(s, font_size=24, color=INK2).next_to([xf(v), YA - 0.07, 0], DOWN, buff=0.1)
                          for v, s in ((0.4, "0.4"), (0.6, "0.6"), (0.8, "0.8"), (1.0, "1.0"))])
            return VGroup(ax, tk, tl)

        ax1, ax2 = lane_axis(xl1), lane_axis(xl2)
        def header(txt, color, x, ref_glyph):
            t = words(txt, 17, color, "SEMIBOLD")
            t.move_to([x, 3.22, 0])
            return t.shift((3.1 - t[ref_glyph].get_bottom()[1]) * UP)   # common baseline

        h1 = header("status quo", INK3, xl1(0.65), 0)
        h2 = header("treatment", INK, xl2(0.65), 0)
        cap_l = words("mission-capable fraction, 30 days", 14, INK3).move_to([(xl1(0.3) + xl2(1.0)) / 2, -2.5, 0])
        rows = VGroup(*[Line([xl1(0.3) - 0.12, yrow(m), 0], [xl2(1.0) + 0.12, yrow(m), 0],
                             color=LINE, stroke_width=1.2) for m in range(N)])
        fut = words("30 shared futures", 13, INK3).rotate(np.pi / 2).move_to([xl1(0.3) - 0.42, (yrow(0) + yrow(N - 1)) / 2, 0])

        axd = Line([xd(-0.2), YA, 0], [xd(0.6), YA, 0], color=INK, stroke_width=2)
        tkd = VGroup(*[Line([xd(v), YA, 0], [xd(v), YA - 0.07, 0], color=INK, stroke_width=2)
                       for v in (-0.2, 0, 0.2, 0.4, 0.6)])
        tld = VGroup(*[MathTex(s, font_size=24, color=INK2).next_to([xd(v), YA - 0.07, 0], DOWN, buff=0.1)
                       for v, s in ((-0.2, "-0.2"), (0, "0"), (0.2, "+0.2"), (0.4, "+0.4"), (0.6, "+0.6"))])
        hd = header("paired difference", INK, xd(0.2), 1)
        cap_d = MathTex(r"\Delta\,\text{MC} = \text{treatment} - \text{status quo}", font_size=24, color=INK3) \
            .move_to([xd(0.2), -2.5, 0])
        zero = DashedLine([xd(0), YA, 0], [xd(0), yrow(0) + 0.1, 0], color=GHOST, stroke_width=1.6,
                          dash_length=0.06)
        base = VGroup(ax1, ax2, h1, h2, cap_l, rows, fut, axd, tkd, tld, hd, cap_d, zero)
        self.add(base)
        assert base.get_bottom()[1] > SAFE_BOTTOM + 0.05, base.get_bottom()
        assert base.get_left()[0] > -6.75 and base.get_right()[0] < 6.75, (base.get_left(), base.get_right())

        # ---------------- the 30 pairs
        sq = [Dot([xl1(SQ[m]), yrow(m), 0], radius=R, color=GHOST) for m in range(N)]
        tr = [Dot([xl2(TR[m]), yrow(m), 0], radius=R, color=INK) for m in range(N)]
        cn = [Line(sq[m].get_center(), tr[m].get_center(), color=INK, stroke_width=1.3, stroke_opacity=0.35)
              for m in range(N)]
        pair_anims = [AnimationGroup(GrowFromCenter(sq[m]), GrowFromCenter(tr[m]), Create(cn[m]))
                      for m in range(N)]
        self.span(LaggedStart(*pair_anims, lag_ratio=0.12), f0=2, f1=38, rate_func=rf.linear)

        # ---------------- each pair keeps its future (row) and slides into the delta panel
        msq = [d.copy() for d in sq]
        mtr = [d.copy() for d in tr]
        mcn = [c.copy() for c in cn]
        self.add(*mcn, *msq, *mtr)
        moves = []
        for m in range(N):
            a = np.array([xd(0), yrow(m), 0])
            b = np.array([xd(DL[m]), yrow(m), 0])
            moves.append(AnimationGroup(
                msq[m].animate.move_to(a), mtr[m].animate.move_to(b),
                Transform(mcn[m], Line(a, b, color=INK, stroke_width=2.2, stroke_opacity=0.6))))
        dim = [d.animate.set_opacity(0.28) for d in sq + tr] + [c.animate.set_stroke(opacity=0.12) for c in cn]
        self.span(LaggedStart(*moves, lag_ratio=0.025), *dim, f0=41, f1=63, rate_func=rf.ease_in_out_cubic)

        # ---------------- collapse into the distribution of the 30 paired differences
        pos = beeswarm(DL, RS, YA)
        top = max(p[1] for p in pos.values()) + RS
        coll = []
        for m in range(N):
            coll.append(mtr[m].animate.move_to(pos[m]).scale(RS / R))
            coll.append(msq[m].animate.scale(0.2).set_opacity(0))
            coll.append(mcn[m].animate.put_start_and_end_on(pos[m], pos[m] + 0.001 * RIGHT).set_stroke(opacity=0))
        yc = top + 0.34
        coll.append(zero.animate.become(DashedLine([xd(0), YA, 0], [xd(0), yc + 0.22, 0], color=GHOST,
                                                   stroke_width=1.6, dash_length=0.06)))
        self.span(*coll, f0=63, f1=84, rate_func=rf.ease_in_out_cubic)
        self.remove(*msq, *mcn)

        # ---------------- mean and 95 % CI (CRN-paired, Student t, n = 30)
        mean_dot = Dot([xd(D_MEAN), yc, 0], radius=0.095, color=ACCENT)
        ci = Line([xd(D_LO), yc, 0], [xd(D_HI), yc, 0], color=ACCENT, stroke_width=7)
        caps = VGroup(*[Line([xd(v), yc - 0.11, 0], [xd(v), yc + 0.11, 0], color=ACCENT, stroke_width=4)
                        for v in (D_LO, D_HI)])
        num = words("+0.217", 40, ACCENT, "SEMIBOLD")
        ci_txt = MathTex(r"95\%\ \text{CI}\ [+0.167,\ +0.268]", font_size=26, color=INK2)
        n_txt = words("n = 30 paired runs · belief mode", 13, INK3)
        lab = VGroup(num, ci_txt, n_txt).arrange(DOWN, buff=0.12)
        lab.next_to([xd(D_MEAN), yc, 0], UP, buff=0.32)
        assert lab.get_top()[1] < 3.5 and lab.get_right()[0] < 6.75, (lab.get_top(), lab.get_right())
        self.span(GrowFromCenter(mean_dot), f0=84, f1=90, rate_func=rf.ease_out_back)
        ci_start = Line([xd(D_MEAN), yc, 0], [xd(D_MEAN) + 0.001, yc, 0], color=ACCENT, stroke_width=7)
        self.add(ci_start)
        self.bring_to_front(mean_dot)
        self.span(Transform(ci_start, ci), FadeIn(caps), FadeIn(num, shift=0.1 * UP), f0=90, f1=F_PAIRED,
                  rate_func=rf.ease_out_cubic)
        self.run(FadeIn(ci_txt, shift=0.06 * UP), FadeIn(n_txt), frames=10, rate_func=rf.ease_out_cubic)

        # ---------------- fade to white in the last 0.3 s (9 frames; the last one is pure white)
        self.at(self.TOTAL_FRAMES - 9)
        self.run(*[FadeOut(m) for m in list(self.mobjects)], frames=8, rate_func=rf.ease_in_sine)
        self.finish()
