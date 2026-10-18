"""PHX-ILL-01 · aircraft-3view.svg — general arrangement, three views (top / side / front).
Geometry is the parametric delta of video/screens/assets/aircraft.js (metres; x station from nose,
y buttline +right, z waterline above ground) so every 2D/3D drawing of the aircraft matches."""
import math
from lib import *

# ---- aircraft.js constants (keep in sync) -----------------------------------------------------------
HALF = [[0.00, 0.00], [0.35, 0.05], [0.9, 0.22], [1.6, 0.36], [2.3, 0.45], [3.0, 0.52], [3.7, 0.62],
        [4.05, 0.98], [4.6, 1.02], [7.29, 2.40], [9.32, 4.10], [10.72, 4.10], [11.22, 1.02],
        [11.9, 0.80], [12.55, 0.58], [12.62, 0.50], [13.2, 0.44], [13.2, 0.0]]
CANOPY = dict(x0=2.55, x1=4.55, w=0.34)
SIDE_TOP = [[0, 0.95], [0.6, 1.02], [1.6, 1.28], [2.4, 1.48], [2.7, 1.62], [3.3, 2.05], [4.2, 2.12], [4.8, 1.9],
            [6.0, 1.82], [8.6, 1.84], [9.4, 2.4], [11.25, 4.35], [12.2, 4.38], [12.7, 2.15], [13.2, 1.86]]
SIDE_BOT = [[13.2, 1.18], [12.6, 1.08], [11.4, 0.92], [9.0, 0.78], [6.0, 0.70], [4.4, 0.62], [3.9, 0.74],
            [2.4, 0.82], [1.2, 0.86], [0, 0.95]]
ZONES = dict(RADAR=(1.05, 0, .42), DFCC=(4.9, 0, .34), BHEEM_EU=(5.6, -0.38, .26), AMAGB=(7.25, 0, .32),
             HYD_PUMP=(7.55, 0.42, .24), HYD_PUMP2=(7.55, -0.42, .24), MLG_L=(8.25, -1.42, .36),
             MLG_R=(8.25, 1.42, .36), NLG=(3.55, 0, .26), ENGINE=(10.1, 0, .5), FADEC=(9.0, -0.3, .22),
             CHUTE=(12.75, 0, .24))

S = 50.0                      # px per metre
PX0, PYC = 128.0, 296.0       # plan: nose station 0, centreline
GY = 792.0                    # ground line (side + front)
SX0 = PX0                     # side: nose station 0 (projected from plan)
FX = 1100.0                   # front: centreline


def pl(x, y):   # plan view (nose left, +y = starboard = up)
    return PX0 + x * S, PYC - y * S


def sd(x, z):   # side view (port side, nose left)
    return SX0 + x * S, GY - z * S


def fr(y, z):   # front view (looking aft at the nose: starboard on the viewer's left)
    return FX - y * S, GY - z * S


def ring():
    return HALF + [[x, -y] for x, y in HALF[1:-1][::-1]]


def build():
    d = Doc('ac', 'General arrangement — three view',
            'Blueprint plate of the Phalanx Twin schematic delta-wing aircraft: top, side and front views with '
            'dimensions, station ticks and numbered equipment zones.')
    d.std_defs()
    H = d.hatch()

    # =============================================================================== plan (top view)
    with d.g(id='ac-plan', cls='view'):
        d.path('M' + ' L'.join('%s %s' % tuple(n(v) for v in pl(*p)) for p in ring()) + ' Z',
               w=W1, fill=WHITE, id='ac-plan-outline', cls='draw outline')
        with d.g(id='ac-plan-hidden', cls='hidden'):
            # engine envelope + intake ducts (hidden detail)
            ex0, ex1, er = 8.7, 12.62, 0.44
            d.path(P(pl(ex0 + .15, er), pl(ex1, er)) + ' ' + P(pl(ex0 + .15, -er), pl(ex1, -er)) +
                   ' M%s %s Q%s %s %s %s Q%s %s %s %s' % (*pl(ex0 + .15, er), *pl(ex0, er), *pl(ex0, 0),
                                                         *pl(ex0, -er), *pl(ex0 + .15, -er)),
                   w=W3, dash=DASH_HIDDEN, cls='draw', id='ac-plan-engine')
            for sg in (1, -1):
                a, b = pl(4.3, .80 * sg), pl(8.7, .40 * sg)
                c1, c2 = pl(6.2, .80 * sg), pl(7.2, .40 * sg)
                d.path('M%s %s C%s %s %s %s %s %s' % (*a, *c1, *c2, *b), w=W3, dash=DASH_HIDDEN, cls='draw')
                a, b = pl(4.3, .40 * sg), pl(8.7, .10 * sg)
                d.path('M%s %s C%s %s %s %s %s %s' % (*a, *pl(6.0, .40 * sg), *pl(7.2, .10 * sg), *b), w=W3,
                       dash=DASH_HIDDEN, cls='draw')
            # main wheels (hidden below the wing)
            for sg in (1, -1):
                x, y = pl(8.25 - .33, 1.42 * sg + .11)
                d.rect(x, y, .66 * S, .22 * S, rx=3, w=W3, dash=DASH_HIDDEN, cls='draw')
            # radar antenna
            x, y = pl(1.05, 0)
            d.line(x, y - .36 * S, x, y + .36 * S, w=W3, dash=DASH_HIDDEN)
        with d.g(id='ac-plan-detail', cls='detail'):
            d.centreline(*pl(-0.35, 0), *pl(13.55, 0))
            # canopy
            cx, cy = pl((CANOPY['x0'] + CANOPY['x1']) / 2, 0)
            d.ellipse(cx, cy, (CANOPY['x1'] - CANOPY['x0']) / 2 * S, CANOPY['w'] * S, w=W2, fill=F1,
                      cls='draw', id='ac-plan-canopy')
            d.line(cx - 0.32 * S, cy - CANOPY['w'] * S * .94, cx - 0.32 * S, cy + CANOPY['w'] * S * .94, w=W3)
            # fuselage side lines behind the intakes
            for sg in (1, -1):
                d.path(P(pl(3.7, .62 * sg), pl(4.05, .62 * sg), pl(6.0, .66 * sg)), w=W3)
                d.line(*pl(4.05, .62 * sg), *pl(4.05, .98 * sg), w=W2)
            # outer-wing slats (IB / MB / OB) and elevons (inboard / outboard)
            for sg in (1, -1):
                le0, le1 = (7.29, 2.40), (9.32, 4.10)
                off = 0.30
                ux, uy = le1[0] - le0[0], le1[1] - le0[1]
                L = math.hypot(ux, uy)
                ux, uy = ux / L, uy / L
                ax, ay = le0[0] + uy * off, le0[1] - ux * off      # inboard aft offset
                bx, by = le1[0] + uy * off - .12, le1[1] - ux * off
                pts = [(ax, ay), (bx, by)]
                d.path(P(*[pl(x, y * sg) for x, y in pts]), w=W2, cls='draw')
                for t in (0.0, 1 / 3, 2 / 3, 1.0):
                    lx, ly = le0[0] + (le1[0] - le0[0]) * t, le0[1] + (le1[1] - le0[1]) * t
                    hx, hy = ax + (bx - ax) * t, ay + (by - ay) * t
                    if 0 < t < 1:
                        d.line(*pl(lx, ly * sg), *pl(hx, hy * sg), w=W3)
                # elevons: hinge line ~0.55 m ahead of the trailing edge
                h0, h1 = (10.18, 3.98), (10.66, 1.08)
                d.path(P(pl(h0[0], h0[1] * sg), pl(h1[0], h1[1] * sg)), w=W2, cls='draw')
                te = lambda y: 10.72 + (4.10 - y) / (4.10 - 1.02) * 0.50
                ys = 2.45
                hx = h0[0] + (h1[0] - h0[0]) * (h0[1] - ys) / (h0[1] - h1[1])
                d.line(*pl(hx, ys * sg), *pl(te(ys), ys * sg), w=W2)
                d.line(*pl(h1[0], 1.08 * sg), *pl(te(1.08), 1.08 * sg), w=W2)
                # airbrake panels either side of the fin
                d.path(P(pl(11.35, .20 * sg), pl(12.05, .20 * sg), pl(12.05, .50 * sg), pl(11.35, .56 * sg),
                         close=True), w=W3)
            # fin (seen from above) + rudder hinge
            fin = [(9.4, 0), (10.4, .075), (12.2, .06), (12.75, .03)]
            d.path(P(*[pl(x, y) for x, y in fin]) + ' ' + P(*[pl(x, -y) for x, y in fin]), w=W2,
                   id='ac-plan-fin', cls='draw')
            d.line(*pl(12.05, .07), *pl(12.05, -.07), w=W3)
            # nozzle petals
            for yy in (.14, .29):
                for sg in (1, -1):
                    d.line(*pl(12.62, yy * sg * 1.05), *pl(13.2, yy * sg * .9), w=W3)
        # zone markers
        with d.g(id='ac-plan-zones', cls='zones'):
            for k in ('RADAR', 'CHUTE'):
                x, y, r = ZONES[k]
                d.circle(*pl(x, y), r * S, w=W2, dash='3 2.5', id='ac-zone-' + k.lower())
            # avionics bay
            x0, y0 = pl(4.42, .5)
            d.rect(x0, y0, 1.56 * S, 1.0 * S, rx=4, w=W2, dash='3 2.5', id='ac-zone-avionics')
            # cockpit
            cx, cy = pl(3.55, 0)
            d.ellipse(cx, cy, 1.18 * S, .48 * S, w=W2, dash='3 2.5', id='ac-zone-cockpit')
            # main gear
            for sg, k in ((1, 'r'), (-1, 'l')):
                d.circle(*pl(8.25, 1.42 * sg), .42 * S, w=W2, dash='3 2.5', id='ac-zone-mlg-' + k)
            # engine
            x0, y0 = pl(8.62, .56)
            d.rect(x0, y0, (12.7 - 8.62) * S, 1.12 * S, rx=14, w=W2, dash='3 2.5', id='ac-zone-engine')
            # subject: AMAGB + hydraulic pumps (accent)
            with d.g(id='ac-zone-amagb', cls='subject'):
                x, y, r = ZONES['AMAGB']
                d.circle(*pl(x, y), .62 * S, w=W1, stroke=ACC, dash='4 3')
                d.rect(pl(7.05, .22)[0], pl(7.05, .22)[1], .4 * S, .44 * S, rx=3, w=W1, stroke=ACC, fill=WHITE)
                for k in ('HYD_PUMP', 'HYD_PUMP2'):
                    x, y, r = ZONES[k]
                    d.circle(*pl(x, y), .17 * S, w=W1, stroke=ACC, fill=WHITE)
                    d.circle(*pl(x, y), .06 * S, w=0, stroke='none', fill=ACC)
        d.kicker(PX0, 548, 'Top view', id='ac-plan-title')

    # station ruler (above the plan)
    with d.g(id='ac-stations', cls='stations'):
        y = 66
        d.line(*(pl(0, 0)[0], y), *(pl(13.2, 0)[0], y), w=W2, cls='draw')
        for i in range(0, 27):
            xm = i * 0.5
            x = pl(xm, 0)[0]
            major = i % 2 == 0
            d.line(x, y, x, y + (7 if major else 4), w=W3 if not major else W2, cls='tick')
            if major:
                d.text(x, y - 6, str(i // 2), size=10.5, mono=True, anchor='middle', fill=INK2)
        x = pl(13.2, 0)[0]
        d.line(x, y - 4, x, y + 9, w=W2, cls='tick')
        d.text(x + 10, y + 4, 'STA m', size=10.5, mono=True, fill=INK3)
        # projection lines down into the plan from key stations
        for xm in (0, 13.2):
            x = pl(xm, 0)[0]
            d.line(x, y + 10, x, (pl(xm, 0)[1] - 10) if xm == 0 else (pl(xm, .44)[1] - 10), w=W3, dash='1.5 3', cls='construction')

    # =============================================================================== side view
    with d.g(id='ac-side', cls='view'):
        with d.g(id='ac-side-gear', cls='gear'):
            # nose gear
            ax, ay = sd(3.55, .23)
            d.path(P(sd(3.66, .76), sd(3.55, .23)), w=W1 * 1.6, cls='draw')
            d.path(P(sd(3.78, .74), sd(3.62, .48)), w=W2)
            d.circle(ax, ay, .23 * S, w=W1, fill=WHITE, cls='draw')
            d.circle(ax, ay, .1 * S, w=W2, fill=F2)
            # main gear
            ax, ay = sd(8.25, .33)
            d.path(P(sd(8.12, .80), sd(8.25, .33)), w=W1 * 1.8, cls='draw')
            d.path(P(sd(8.62, .79), sd(8.2, .55)), w=W2)
            d.circle(ax, ay, .33 * S, w=W1, fill=WHITE, cls='draw', id='ac-side-mlg-tyre')
            d.circle(ax, ay, .17 * S, w=W2, fill=F2)
            d.circle(ax, ay, .04 * S, w=W2, fill=WHITE)
        out = SIDE_TOP + SIDE_BOT
        d.path('M' + ' L'.join('%s %s' % tuple(n(v) for v in sd(*p)) for p in out) + ' Z', w=W1, fill=WHITE,
               id='ac-side-outline', cls='draw outline')
        with d.g(id='ac-side-hidden', cls='hidden'):
            # engine (fan face to nozzle), intake duct, radar antenna, avionics bay, seat
            d.path(P(sd(8.7, .93), sd(12.6, .93)) + ' ' + P(sd(8.7, 1.79), sd(12.6, 1.79)) + ' ' +
                   P(sd(8.7, .93), sd(8.7, 1.79)), w=W3, dash=DASH_HIDDEN, cls='draw', id='ac-side-engine')
            d.path('M%s %s C%s %s %s %s %s %s' % (*sd(4.7, 1.34), *sd(6.4, 1.36), *sd(7.4, 1.79), *sd(8.7, 1.79)),
                   w=W3, dash=DASH_HIDDEN, cls='draw')
            d.path('M%s %s C%s %s %s %s %s %s' % (*sd(5.6, 0.98), *sd(6.6, .84), *sd(7.6, .93), *sd(8.7, .93)),
                   w=W3, dash=DASH_HIDDEN, cls='draw')
            d.path(P(sd(1.0, .62), sd(1.12, .95), sd(1.0, 1.28)), w=W3, dash=DASH_HIDDEN)
            x0, y0 = sd(4.42, 1.86)
            d.rect(x0, y0, 1.56 * S, .36 * S, rx=3, w=W3, dash=DASH_HIDDEN)
            # chute canister (fin base)
            d.path(P(sd(12.98, 1.90), sd(12.46, 1.90), sd(12.40, 1.96), sd(12.40, 2.10), sd(12.46, 2.16),
                     sd(12.72, 2.13)), w=W3, dash=DASH_HIDDEN, id='ac-side-chute')
        with d.g(id='ac-side-detail', cls='detail'):
            d.path('M%s %s C%s %s %s %s %s %s' % (*sd(2.62, 1.6), *sd(3.0, 2.38), *sd(3.9, 2.4), *sd(4.75, 1.92)),
                   w=W2, fill=F1, cls='draw', id='ac-side-canopy')
            d.path(P(sd(2.62, 1.6), sd(4.75, 1.92)), w=W3)
            d.path(P(sd(4.05, .72), sd(4.05, 1.32), sd(4.7, 1.36), sd(5.8, .98), close=True), w=W2, fill=F2,
                   cls='draw', id='ac-side-intake')
            d.path(P(sd(4.6, 1.18), sd(11.22, 1.12)), w=W3, dash=DASH_HIDDEN)
            # rudder hinge + fin panel line, nozzle petals, radome joint
            d.path(P(sd(11.92, 2.28), sd(12.12, 4.37)), w=W2)
            d.path(P(sd(12.62, 1.08), sd(12.62, 1.92)), w=W2)
            for z in (1.28, 1.48, 1.68):
                d.line(*sd(12.66, z + (z - 1.48) * .05), *sd(13.18, z - (z - 1.48) * .12 + .04), w=W3)
            d.path(P(sd(1.62, .87), sd(1.62, 1.29)), w=W3)
            # chute cap line
            d.path(P(sd(12.98, 1.88), sd(12.98, 1.99)), w=W2)
            # subject: AMAGB + pump (accent)
            with d.g(id='ac-side-amagb', cls='subject'):
                x0, y0 = sd(7.02, 1.12)
                d.rect(x0, y0, .46 * S, .32 * S, rx=3, w=W1, stroke=ACC, fill=WHITE)
                d.circle(*sd(7.55, .98), .15 * S, w=W1, stroke=ACC, fill=WHITE)
                d.circle(*sd(7.55, .98), .05 * S, w=0, stroke='none', fill=ACC)
                d.path(P(sd(7.48, .96), sd(8.7, 1.2)), w=W3, stroke=ACC, dash=DASH_CENTRE)
        # ground line + hatch
        with d.g(id='ac-ground', cls='ground'):
            x0, x1 = sd(-0.6, 0)[0], sd(13.8, 0)[0]
            d.line(x0, GY, x1, GY, w=W1, cls='draw')
            d.rect(x0, GY, x1 - x0, 7, w=0, stroke='none', fill=H)
            f0, f1 = fr(4.75, 0)[0], fr(-4.75, 0)[0]
            d.line(f0, GY, f1, GY, w=W1, cls='draw')
            d.rect(f0, GY, f1 - f0, 7, w=0, stroke='none', fill=H)
        d.kicker(PX0, 860, 'Side view · port', id='ac-side-title')

    # =============================================================================== front view
    with d.g(id='ac-front', cls='view'):
        # fin
        d.path(P(fr(.075, 1.9), fr(.03, 4.38), fr(-.03, 4.38), fr(-.075, 1.9), close=True), w=W1, fill=WHITE,
               cls='draw', id='ac-front-fin')
        # wing
        wing = [(-4.1, 1.215), (-2.0, 1.265), (0, 1.31), (2.0, 1.265), (4.1, 1.215), (4.1, 1.155), (2.0, 1.10),
                (0, 1.06), (-2.0, 1.10), (-4.1, 1.155)]
        d.path(P(*[fr(y, z) for y, z in wing], close=True), w=W1, fill=WHITE, cls='draw', id='ac-front-wing')
        # main gear legs + braces
        for sg in (1, -1):
            d.path(P(fr(1.42 * sg, 1.08), fr(1.42 * sg, .33)), w=W1 * 1.8, cls='draw')
            d.path(P(fr(1.42 * sg, .78), fr(.62 * sg, 1.0)), w=W2)
        # nose gear leg
        d.path(P(fr(0, .70), fr(0, .23)), w=W1 * 1.6, cls='draw')
        # fuselage section (superellipse)
        pts = []
        for i in range(73):
            t = 2 * math.pi * i / 72
            c, s_ = math.cos(t), math.sin(t)
            yy = .60 * math.copysign(abs(c) ** (2 / 2.6), c)
            zz = 1.30 + (0.60 if s_ > 0 else 0.63) * math.copysign(abs(s_) ** (2 / 2.6), s_)
            pts.append(fr(yy, zz))
        d.path(P(*pts, close=True), w=W1, fill=WHITE, cls='draw', id='ac-front-fuselage')
        # intakes
        for sg in (1, -1):
            o = [(.56, .74), (.92, .74), (1.02, .84), (1.02, 1.30), (.94, 1.37), (.56, 1.37)]
            d.path(P(*[fr(y * sg, z) for y, z in o], close=True), w=W1, fill=WHITE, cls='draw')
            i_ = [(.64, .82), (.90, .82), (.95, .88), (.95, 1.27), (.90, 1.30), (.64, 1.30)]
            d.path(P(*[fr(y * sg, z) for y, z in i_], close=True), w=W2, fill=F2)
        # canopy
        cpts = [fr(.34 * math.cos(t), 1.84 + .38 * math.sin(t)) for t in [math.pi * i / 36 for i in range(37)]]
        d.path(P(*cpts, close=True), w=W2, fill=F1, cls='draw', id='ac-front-canopy')
        # radome
        d.circle(*fr(0, 1.06), .40 * S, w=W3)
        d.circle(*fr(0, .98), .05 * S, w=W2, fill=WHITE)
        d.centreline(*fr(0, -.2), *fr(0, 4.62))
        # wheels
        for sg in (1, -1):
            x, y = fr(1.42 * sg + .11, .66)
            d.rect(x, y, .22 * S, .66 * S, rx=4, w=W1, fill=WHITE, cls='draw')
            d.line(x + .11 * S, y + 2, x + .11 * S, y + .66 * S - 2, w=W3)
        x, y = fr(.08, .46)
        d.rect(x, y, .16 * S, .46 * S, rx=3, w=W1, fill=WHITE, cls='draw')
        d.kicker(fr(4.75, 0)[0], 860, 'Front view', id='ac-front-title')

    # projection construction lines between views (plan -> side, side -> front)
    with d.g(id='ac-proj', cls='construction'):
        def top_z(x):
            pts = SIDE_TOP
            for (x0, z0), (x1, z1) in zip(pts, pts[1:]):
                if x0 <= x <= x1:
                    return z0 + (z1 - z0) * (x - x0) / (x1 - x0)
            return pts[-1][1]
        for xm, yb in ((0, 0), (4.6, 1.02), (9.32, 4.10), (13.2, .44)):
            x = pl(xm, 0)[0]
            y0 = pl(xm, -yb)[1] + 10
            d.line(x, y0, x, sd(xm, top_z(xm))[1] - 10, w=W3, dash='1.5 3')
        for z, x0 in ((4.38, sd(12.2, 0)[0] + 12), (2.12, sd(4.3, 0)[0] + 12)):
            if z < 3:
                continue
            d.line(x0, GY - z * S, fr(0.5, 0)[0] - 6, GY - z * S, w=W3, dash='1.5 3')
        d.line(sd(13.2, 0)[0] + 12, GY - 1.86 * S, fr(1.02, 0)[0] - 8, GY - 1.86 * S, w=W3, dash='1.5 3')

    # =============================================================================== dimensions
    with d.g(id='ac-dims', cls='dims'):
        # length below ground
        p1, p2 = (sd(0, 0)[0], GY + 12), (sd(13.2, 0)[0], GY + 12)
        with d.g(id='ac-dim-length', cls='dim'):
            y = GY + 30
            for x in (p1[0], p2[0]):
                d.line(x, GY + 10, x, y + 5, w=W3)
            d.line(p1[0], y, p2[0], y, w=W3, cls='draw')
            d.arrowhead(p1[0], y, math.pi, L=7.5, half=1.7)
            d.arrowhead(p2[0], y, 0, L=7.5, half=1.7)
            d.text((p1[0] + p2[0]) / 2, y - 5, '13.2 m', size=12.5, mono=True, anchor='middle', halo=True,
                   weight=600)
        # span (plan, right)
        d.dim(pl(10.72, 4.10), pl(10.72, -4.10), (13.2 - 10.72 + .9) * S, '8.2 m', id='ac-dim-span', size=12.5)
        # height (front, right)
        d.dim(fr(-0.03, 4.38), fr(-0.03, 0), (4.1 + .75) * S, '4.4 m', id='ac-dim-height',
              size=12.5, ext_gap=6)

    # =============================================================================== callouts + legend
    Z = [('1', 'Radar', 'RADAR · 1553 RT 12', pl(1.05, 0), (150, 176)),
         ('2', 'Cockpit', 'CWS displays · DVR', pl(3.55, .3), (262, 150)),
         ('3', 'Avionics bay', 'DFCC ×4 · ADC ×4 · BHEEM EU · INS/GPS · AHRS', pl(5.2, .5), (372, 128)),
         ('4', 'AMAGB + hydraulic pumps', 'AMAGB · HYD pump SYS1 / SYS2 · GEN · JFS', pl(7.25, -.62), (438, 474)),
         ('5', 'Main gear', 'MLG L / R · wheel brakes · ANTISKID · tyres', pl(8.25, -1.84), (530, 478)),
         ('6', 'F404 engine', 'FADEC ×2 · ECMS', pl(11.0, .56), (742, 168)),
         ('7', 'Brake chute', 'canister at the fin base', pl(12.75, -.24), (796, 420))]
    with d.g(id='ac-callouts', cls='callouts'):
        for num, name, sub, (tx, ty), (bx, by) in Z:
            d.callout(num, bx, by, tx, ty, accent=(num == '4'), id='ac-c' + num)
    with d.g(id='ac-legend', cls='legend'):
        lx, ly = 980, 76
        d.kicker(lx, ly, 'Equipment zones')
        d.line(lx, ly + 12, 1540, ly + 12, w=W3)
        for i, (num, name, sub, _, _) in enumerate(Z):
            y = ly + 44 + i * 40
            with d.g(id='ac-legend-' + num, cls='legend-row'):
                d.callout(num, lx + 11, y - 4, accent=(num == '4'))
                d.text(lx + 32, y - 6, name, size=14, weight=650, fill=ACC if num == '4' else INK)
                d.text(lx + 32, y + 10, sub, size=11, mono=True, fill=INK3)
        # hidden-line key + scale bar + third-angle symbol
        y = ly + 44 + 7 * 40 + 6
        d.line(lx, y - 14, 1540, y - 14, w=W3)
        d.line(lx, y + 6, lx + 34, y + 6, w=W3, dash=DASH_HIDDEN)
        d.text(lx + 42, y + 10, 'hidden detail', size=11, mono=True, fill=INK3)
        d.line(lx + 160, y + 6, lx + 194, y + 6, w=W3, dash=DASH_CENTRE)
        d.text(lx + 202, y + 10, 'centre line', size=11, mono=True, fill=INK3)
        with d.g(id='ac-scalebar', cls='scalebar'):
            sx = lx + 296
            for i in range(5):
                d.rect(sx + i * S, y + 2, S, 6, w=W3, fill=INK if i % 2 == 0 else WHITE)
            for i in range(6):
                d.text(sx + i * S, y + 22, str(i) + (' m' if i == 5 else ''), size=10, mono=True,
                       anchor='middle', fill=INK3)
        # third-angle projection symbol
        with d.g(id='ac-projection-symbol'):
            px, py = 1512, ly - 4
            d.path(P((px - 22, py - 7), (px - 6, py - 4), (px - 6, py + 4), (px - 22, py + 7), close=True), w=W2)
            d.centreline(px - 28, py, px + 22, py)
            d.circle(px + 10, py, 7, w=W2)
            d.circle(px + 10, py, 4, w=W2)

    d.sheet(1, 'General arrangement — three views', 'delta-wing · single F404 · fleet TJ101–TJ108',
            extra='UNITS m')
    return d


if __name__ == '__main__':
    print(build().save('aircraft-3view.svg'))
