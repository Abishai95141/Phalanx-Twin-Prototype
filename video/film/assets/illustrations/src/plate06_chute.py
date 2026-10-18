"""PHX-ILL-06 · brake-chute.svg — drag-chute canister at the fin base (aft fuselage from aircraft.js geometry),
detail D canister cutaway, and the deployed ring-slot chute with pilot chute.  Streamings ring: 45 ticks =
USAGE.CHUTE_STREAMINGS life limit 45 (dictionary).  Subject (accent): the chute (packed and deployed)."""
import math
from lib import *

SIDE_TOP = [[0, 0.95], [0.6, 1.02], [1.6, 1.28], [2.4, 1.48], [2.7, 1.62], [3.3, 2.05], [4.2, 2.12], [4.8, 1.9],
            [6.0, 1.82], [8.6, 1.84], [9.4, 2.4], [11.25, 4.35], [12.2, 4.38], [12.7, 2.15], [13.2, 1.86]]
SIDE_BOT = [[13.2, 1.18], [12.6, 1.08], [11.4, 0.92], [9.0, 0.78], [6.0, 0.70], [4.4, 0.62], [3.9, 0.74],
            [2.4, 0.82], [1.2, 0.86], [0, 0.95]]
K = 118.0
X0, ZB, YB = 70.0, 0.7, 572.0


def sd(x, z):
    return X0 + (x - 9.0) * K, YB - (z - ZB) * K


def interp(pts, x):
    for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
        if min(x0, x1) <= x <= max(x0, x1) and x0 != x1:
            return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
    return None


def build():
    d = Doc('chute', 'Brake chute — canister and deployed chute',
            'Aft fuselage with the brake-chute canister at the fin base, a cutaway detail of the packed chute and '
            'the deployed ring-slot chute with its pilot chute; a 45-tick streamings life ring.')
    d.std_defs()
    HA, HF = d.hatch(), d.hatch('a')

    # ------------------------------------------------------------------ aft fuselage (x >= 9.0 m)
    with d.g(id='chute-airframe', cls='view'):
        top = [p for p in SIDE_TOP if p[0] >= 9.0]
        bot = [p for p in SIDE_BOT if p[0] >= 9.0]
        z_top9, z_bot9 = interp(SIDE_TOP, 9.0), interp(SIDE_BOT, 9.0)
        outline = [(9.0, z_top9)] + top + bot + [(9.0, z_bot9)]
        d.path(P(*[sd(*p) for p in outline]), w=W1, fill=WHITE, cls='draw', id='chute-airframe-outline')
        # break line at station 9.0
        xa, ya = sd(9.0, z_top9)
        xb, yb = sd(9.0, z_bot9)
        m = (ya + yb) / 2
        d.path('M%s %s L%s %s L%s %s L%s %s L%s %s' % (n(xa), n(ya), n(xa), n(m - 14), n(xa + 9), n(m - 4),
                                                        n(xa - 9), n(m + 4), n(xa), n(m + 14)) +
               ' L%s %s' % (n(xb), n(yb)), w=W2)
        # fin details: rudder hinge, panel lines, nozzle petals, airbrake hinge
        d.path(P(sd(11.92, 2.28), sd(12.12, 4.37)), w=W2)
        d.path(P(sd(10.2, 2.32), sd(12.0, 2.28)), w=W3)
        d.path(P(sd(12.62, 1.08), sd(12.62, 1.93)), w=W2)
        for z in (1.28, 1.48, 1.68):
            d.line(*sd(12.66, z + (z - 1.48) * .05), *sd(13.18, z - (z - 1.48) * .12 + .04), w=W3)
        d.path(P(sd(9.0, 1.12), sd(11.22, 1.12)), w=W3, dash=DASH_HIDDEN)
        d.text(*sd(9.3, 0.98), 'aft fuselage', size=10.5, mono=True, fill=INK3)
        d.text(*sd(11.2, 3.2), 'fin', size=10.5, mono=True, fill=INK3)

    # canister (in place, small) — subject packed chute in accent
    with d.g(id='chute-canister', cls='part'):
        c0, c1, zb, zt = 12.40, 12.98, 1.90, 2.17
        d.path(P(sd(c0, zb), sd(c1, zb), sd(c1, zt - 0.06), sd(c0 + 0.12, zt), sd(c0, zt - 0.04), close=True),
               w=W1, fill=WHITE, cls='draw')
        d.path(P(sd(c0 + .06, zb + .04), sd(c1 - .08, zb + .04), sd(c1 - .08, zt - .08), sd(c0 + .14, zt - .04),
                 sd(c0 + .06, zt - .08), close=True), w=W1, stroke=ACC, fill=HF, id='chute-packed-small')
        d.path(P(sd(c1, zb - .02), sd(c1, zt - .04)), w=W1 * 1.6)
        hx, hy = sd(12.92, 1.86)
        d.circle(hx, hy, 4, w=W1, fill=WHITE, id='chute-hook-small')

    # ------------------------------------------------------------------ deployed chute
    AXY = 426.0
    hx, hy = sd(12.92, 1.86)
    CF = (930.0, AXY)                 # confluence point
    SK, CR, RMAX = 1130.0, 1394.0, 138.0

    def prof(t):
        """canopy profile: t 0 (skirt) -> 1 (crown); returns (x, r)"""
        x = SK + (CR - SK) * t
        if t < 0.45:
            r = 124 + (RMAX - 124) * math.sin(t / 0.45 * math.pi / 2)
        else:
            u = (t - 0.45) / 0.55
            r = RMAX * math.sqrt(max(0.0, 1 - u * u)) if u < 1 else 0
            r = max(r, 9)
        return x, r

    with d.g(id='chute-deployed', cls='subject'):
        # riser with a break (shown shortened)
        with d.g(id='chute-riser'):
            mx = 740
            ym = hy + (AXY - hy) * (mx - hx) / (CF[0] - hx)
            d.path(P((hx + 4, hy), (mx, ym)), w=W1 * 1.4, stroke=ACC, cls='draw')
            d.path(P((mx + 26, ym - .5), CF), w=W1 * 1.4, stroke=ACC, cls='draw')
            for dx in (6, 20):
                d.line(mx + dx - 5, ym + 10, mx + dx + 5, ym - 10, w=W2, stroke=ACC)
            d.text(mx + 13, ym + 28, 'riser · shown shortened', size=10.5, mono=True, fill=INK3, anchor='middle')
        # suspension lines
        with d.g(id='chute-lines'):
            for ph in (0, 35, 65, 90):
                for sg in (1, -1):
                    if ph == 90 and sg < 0:
                        continue
                    x, r = prof(0)
                    y = AXY - sg * r * math.cos(math.radians(ph))
                    d.line(CF[0], CF[1], x, y, w=W3 if ph else W2, stroke=ACC)
            d.circle(*CF, 3.2, w=W1, stroke=ACC, fill=WHITE)
        # canopy
        with d.g(id='chute-canopy'):
            N = 40
            top = [prof(i / N) for i in range(N + 1)]
            outline = [(x, AXY - r) for x, r in top] + [(x, AXY + r) for x, r in top[::-1]]
            d.path(P(*outline, close=True), w=W1, stroke=ACC, fill=WHITE, cls='draw')
            for ph in (35, 65):
                for sg in (1, -1):
                    pts = [(x, AXY - sg * r * math.cos(math.radians(ph))) for x, r in top]
                    d.path(P(*pts), w=W3, stroke=ACC)
            d.path(P(*[(x, AXY) for x, r in top]), w=W3, stroke=ACC)
            # ring slots (latitude bands seen edge-on)
            for t in (0.10, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82):
                x, r = prof(t)
                d.line(x, AXY - r, x, AXY + r, w=W2, stroke=ACC)
                x2, r2 = prof(t + 0.025)
                d.line(x2, AXY - r2, x2, AXY + r2, w=W3, stroke=ACC)
            # vent + pilot chute
            vx, vr = prof(1.0)
            d.path(P((vx, AXY - 9), (vx, AXY + 9)), w=W1, stroke=ACC)
            d.line(vx, AXY, vx + 52, AXY, w=W2, stroke=ACC, id='chute-bridle')
            pc = [(vx + 52 + 46 * (i / 20), 34 * math.sqrt(max(0, 1 - (i / 20) ** 2)) if i else 26) for i in range(21)]
            pc[0] = (vx + 52, 26)
            pcl = [(x, AXY - r) for x, r in pc] + [(x, AXY + r) for x, r in pc[::-1]]
            d.path(P(*pcl, close=True), w=W1, stroke=ACC, fill=WHITE, id='chute-pilot')
            for t in (0.3, 0.6):
                x, r = pc[int(t * 20)]
                d.line(x, AXY - r, x, AXY + r, w=W3, stroke=ACC)
        # flow arrow
        d.arrow([(760, 300), (900, 300)], w=W2, L=9, half=2.6, id='chute-airflow')
        d.text(760, 288, 'relative airflow', size=10.5, mono=True, fill=INK3)

    # ------------------------------------------------------------------ CHUTE.STATE signal
    with d.g(id='chute-signal', cls='signal'):
        sx, sy = sd(12.5, 1.90)
        d.circle(sx, sy + 3, 2.4, w=0, stroke='none', fill=BLUE)
        d.path(P((sx, sy + 3), (sx, sy + 40), (sx - 120, sy + 40)), w=W2, stroke=BLUE)
        w_ = 200
        d.rect(sx - 120 - w_, sy + 31, w_, 18, rx=9, w=W2, stroke=BLUE, fill=WHITE)
        d.text(sx - 120 - w_ / 2, sy + 44, 'CHUTE.STATE → BHEEM EU', size=10, mono=True, fill=BLUE, anchor='middle')

    # ------------------------------------------------------------------ detail D: canister cutaway (enlarged)
    with d.g(id='chute-detail-d', cls='detail'):
        cx, cy = 330.0, 742.0
        k = 2.7
        T = lambda x, z: (cx + (x - 12.69) * K * k / 1.0 * 1.0 / 1.0, cy - (z - 2.03) * K * k / 1.0)
        d.text(70, 652, 'DETAIL D', size=12, weight=700, ls='0.14em')
        d.text(70, 668, 'canister cutaway · enlarged', size=10.5, mono=True, fill=INK3)
        # skin + fin base (section)
        c0, c1, zb, zt = 12.40, 12.98, 1.90, 2.17
        d.path(P(T(c0 - .08, zt + .02), T(c0 + .12, zt + .05), T(c1 + .02, zt - .04), T(c1 + .02, zt - .07),
                 T(c0 + .12, zt + .02), T(c0 - .08, zt - .01), close=True), w=W1, fill=HA)
        # canister wall
        d.path(P(T(c0, zb), T(c1, zb), T(c1, zt - .06)) + ' ' + P(T(c0 + .12, zt), T(c0, zt - .04), T(c0, zb)),
               w=W1 * 1.3, cls='draw')
        # packed chute bag (subject)
        d.path(P(T(c0 + .03, zb + .03), T(c1 - .09, zb + .03), T(c1 - .09, zt - .09), T(c0 + .13, zt - .04),
                 T(c0 + .03, zt - .07), close=True), w=W1, stroke=ACC, fill=HF, id='chute-packed')
        # pilot-chute spring
        sx0, sy0 = T(c0 + .05, 2.035)
        sx1, sy1 = T(c0 + .16, 2.035)
        pts = [(sx0, sy0)] + [(sx0 + (sx1 - sx0) * i / 8, sy0 + (8 if i % 2 else -8)) for i in range(1, 8)] + [(sx1, sy1)]
        d.path(P(*pts), w=W2, stroke=ACC)
        # door / cap (hinged at the top), shown closed + phantom open
        d.path(P(T(c1, zb - .02), T(c1, zt - .05)), w=W1 * 2)
        hx_, hy_ = T(c1, zt - .05)
        d.circle(hx_, hy_, 4, w=W1, fill=WHITE)
        d.path(P(T(c1, zt - .05), T(c1 + .2, zt - .02)), w=W2, dash=DASH_PHANTOM)
        # attach + jettison hook
        jx, jy = T(12.92, 1.86)
        d.path('M%s %s L%s %s Q%s %s %s %s Q%s %s %s %s' % (n(jx - 20), n(jy - 14), n(jx - 6), n(jy - 14),
                                                             n(jx + 10), n(jy - 14), n(jx + 10), n(jy),
                                                             n(jx + 10), n(jy + 12), n(jx - 4), n(jy + 10)),
               w=W1 * 1.3, id='chute-hook')
        d.path(P((jx + 10, jy + 2), (jx + 70, jy + 14)), w=W1 * 1.4, stroke=ACC)
        d.circle(jx - 20, jy - 14, 3, w=W2, fill=WHITE)
        # frame circle
        d.circle(cx + 10, cy, 112, w=W2, dash='5 3')
    # detail mark on the small view
    with d.g(id='chute-detail-mark'):
        mx, my = sd(12.69, 2.03)
        d.circle(mx, my, 34, w=W2, dash='5 3')
        d.text(mx - 34, my - 38, 'D', size=13, weight=700)

    # ------------------------------------------------------------------ streamings life ring
    with d.g(id='chute-streamings', cls='counter'):
        cx, cy, R = 660.0, 738.0, 78.0
        for i in range(45):
            a = math.radians(-90 + i * 8)
            r0, r1 = R - (11 if i % 5 == 0 else 7), R
            d.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                   w=W2 if i % 5 == 0 else W3, cls='tick', id='chute-tick-%d' % (i + 1))
        d.text(cx, cy + 16, '45', size=50, mono=True, weight=600, anchor='middle', id='chute-life-count')
        d.text(cx, cy + 34, 'streamings', size=10.5, mono=True, fill=INK3, anchor='middle')
        d.text(cx + R + 22, cy - 18, 'Streamings life', size=14, weight=650)
        d.text(cx + R + 22, cy + 0, 'USAGE.CHUTE_STREAMINGS', size=11, mono=True, fill=INK3)
        d.text(cx + R + 22, cy + 16, 'life limit 45 · one tick each', size=11, mono=True, fill=INK3)

    # ------------------------------------------------------------------ callouts + list
    items = [('1', 'Chute canister', 'at the fin base', sd(12.47, 2.12), (556, 318)),
             ('2', 'Door / cap', 'opens on deploy', sd(12.98, 2.0), (612, 362)),
             ('3', 'Attach + jettison hook', '', (hx + 2, hy + 3), (600, 500)),
             ('4', 'Riser', '', (690, hy + (AXY - hy) * (690 - hx) / (CF[0] - hx)), (690, 500)),
             ('5', 'Suspension lines', '', (1020, AXY - 64), (990, 300)),
             ('6', 'Ring-slot canopy', 'the brake chute', (1290, AXY - 134), (1250, 252)),
             ('7', 'Pilot chute', '', (1462, AXY - 30), (1490, 340))]
    with d.g(id='chute-callouts', cls='callouts'):
        for num, name, sub, (tx, ty), (bx, by) in items:
            d.callout(num, bx, by, tx, ty, accent=(num == '6'), id='chute-c' + num)
    with d.g(id='chute-list', cls='legend'):
        lx, ly = 1000, 652
        for i, (num, name, sub, _, _) in enumerate(items):
            c, r = divmod(i, 4)
            x = lx + c * 230
            y = ly + r * 36
            d.callout(num, x + 11, y - 4, accent=(num == '6'))
            d.text(x + 30, y - 5, name, size=13, weight=650, fill=ACC if num == '6' else INK)
            if sub:
                d.text(x + 30, y + 9, sub, size=10.5, mono=True, fill=INK3)
    d.text(70, 76, 'BRAKE CHUTE · STOWED AND STREAMED', size=11, weight=700, ls='0.14em')
    d.sheet(6, 'Brake chute — canister and canopy', 'life 45 streamings · CHUTE.STATE')
    return d


if __name__ == '__main__':
    print(build().save('brake-chute.svg'))
