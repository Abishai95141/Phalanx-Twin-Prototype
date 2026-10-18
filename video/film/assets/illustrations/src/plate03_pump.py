"""PHX-ILL-03 · hyd-pump.svg — engine-driven axial-piston pump (variable displacement, swashplate type).
Top: assembled half-section A–A.  Bottom: #pump-exploded — the same part sections pulled apart along the axis.
Every part is drawn by one function in (x, rr) coordinates (rr = radius above the axis), so the assembled
and exploded drawings are the same geometry.  Assembled part groups carry data-explode-x (px offset that
moves them to their exploded station) for in-place explode animation.  Subject (accent): the swashplate."""
import math
from lib import *

A = 292.0                         # assembled axis (screen y)
XS = 392.0                        # swashplate pivot (x)
ALPHA = math.radians(16.0)
TA = math.tan(ALPHA)
NX, NY = math.cos(ALPHA), math.sin(ALPHA)   # swash face normal (screen coords, points to the pistons)


def face(rr):
    return XS + TA * rr


def build():
    d = Doc('pump', 'Engine-driven hydraulic pump — cutaway',
            'Axial-piston, variable-displacement engine-driven pump in half-section with an exploded view of '
            'the rotating group, the valve-plate face and the data plate.')
    d.std_defs()
    HA, HB, HF = d.hatch(), d.hatch('b'), d.hatch('a')

    def mk(x0, xa, k, Y):
        return lambda x, rr: (x0 + (x - xa) * k, Y - rr * k)

    def poly(T, pts, **kw):
        d.path(P(*[T(x, r) for x, r in pts], close=True), **kw)

    def both(T, pts, **kw):
        poly(T, pts, **kw)
        poly(T, [(x, -r) for x, r in pts], **kw)

    # ------------------------------------------------------------------ parts (shared geometry)
    def p_shaft(T, k=1.0, broken=False):
        def edge(sg):
            pts = [(120, 13 * sg), (124, 17 * sg)]
            x = 128
            while x < 208:
                pts += [(x, 17 * sg), (x + 3, 14 * sg), (x + 6, 17 * sg)]
                x += 6
            pts += [(214, 17 * sg), (214, 20 * sg)]
            return pts
        top = edge(1)
        bot = edge(-1)
        if not broken:
            outline = top + [(784, 20), (790, 15), (790, -15), (784, -20)] + bot[::-1]
            poly(T, outline, w=W1, fill=WHITE, cls='draw')
        else:
            xb = 330
            outline = top + [(xb, 20)]
            d.path(P(*[T(x, r) for x, r in outline]) + ' ' + P(*[T(x, r) for x, r in [(xb, -20)] + bot[::-1]]),
                   w=W1, fill='none', cls='draw')
            # break symbol + rear end
            x1, y1 = T(xb, 20)
            x2, y2 = T(xb, -20)
            d.path('M%s %s C%s %s %s %s %s %s' % (n(x1), n(y1), n(x1 + 8), n(y1 + (y2 - y1) * .3), n(x1 - 8),
                                                   n(y1 + (y2 - y1) * .7), n(x2), n(y2)), w=W2)
            g = 26
            Tx = lambda x, r: T(x - 700 + xb + g, r)
            outline2 = [(700, 20), (784, 20), (790, 15), (790, -15), (784, -20), (700, -20)]
            d.path(P(*[Tx(x, r) for x, r in outline2]), w=W1, cls='draw')
            x1, y1 = Tx(700, 20)
            x2, y2 = Tx(700, -20)
            d.path('M%s %s C%s %s %s %s %s %s' % (n(x1), n(y1), n(x1 + 8), n(y1 + (y2 - y1) * .3), n(x1 - 8),
                                                   n(y1 + (y2 - y1) * .7), n(x2), n(y2)), w=W2)
            d.centreline(*T(110, 0), *Tx(800, 0))
            return
        # spline teeth root line (hidden) + centreline
        d.path(P(T(128, 14), T(208, 14)) + ' ' + P(T(128, -14), T(208, -14)), w=W3)
        d.centreline(*T(104, 0), *T(806, 0))

    def p_seal(T):
        for sg in (1, -1):
            poly(T, [(230, 20 * sg), (244, 20 * sg), (244, 26 * sg), (230, 26 * sg)], w=W2, fill=F2)
            d.path(P(T(233, 20.5 * sg), T(237, 24 * sg), T(241, 20.5 * sg)), w=W3)

    def p_bearing(T, k=1.0):
        for sg in (1, -1):
            poly(T, [(248, 36 * sg), (276, 36 * sg), (276, 44 * sg), (248, 44 * sg)], w=W2, fill=HB)
            poly(T, [(248, 20 * sg), (276, 20 * sg), (276, 28 * sg), (248, 28 * sg)], w=W2, fill=HB)
            cx, cy = T(262, 32 * sg)
            d.circle(cx, cy, 6.2 * k, w=W2, fill=WHITE)

    def p_ctrl(T, k=1.0):
        poly(T, [(312, 106), (386, 106), (392, 102), (392, 98), (386, 94), (312, 94)], w=W1, fill=WHITE,
             cls='draw')
        d.path(P(T(318, 100), T(380, 100)), w=W3, dash='3 2')

    def p_swash(T, k=1.0, hub=False):
        def body(r1, r2):
            pts = []
            for rr in (r1, r2):
                pts.append((face(rr), rr))
            back = [(face(rr) - 30 * NX, rr - 30 * NY * -1 * -1) for rr in (r2, r1)]
            # back face: offset along -normal (screen normal (NX, NY) -> (x, rr) normal (NX, -NY))
            back = [(face(rr) - 30 * NX, rr + 30 * NY) for rr in (r2, r1)]
            return pts + back
        for r1, r2 in ((36, 116), (-116, -36)):
            poly(T, body(r1, r2), w=W1, stroke=ACC, fill=HF, cls='draw')
        if hub:   # bore surface behind the cutting plane
            for o in (0, 30):
                d.path(P(T(face(36) - o * NX, 36 + o * NY), T(face(-36) - o * NX, -36 + o * NY)), w=W2, stroke=ACC)
        # pivot (trunnion axis, perpendicular to the page) — hidden
        cx, cy = T(XS - 14, 0)
        d.circle(cx, cy, 9 * k, w=W2, stroke=ACC, dash='3 2', fill='none')
        d.line(cx - 13 * k, cy, cx + 13 * k, cy, w=W3, stroke=ACC)
        d.line(cx, cy - 13 * k, cx, cy + 13 * k, w=W3, stroke=ACC)

    def p_retainer(T, k=1.0):
        # slippers on the face + retainer plate (parallel to the face, offset along the normal)
        def off(rr, o):
            return (face(rr) + o * NX, rr - o * NY)
        for rc in (80, -80):
            pad = [off(rc + 15, 0.4), off(rc + 15, 6), off(rc + 7, 7), off(rc + 7, 15), off(rc - 7, 15),
                   off(rc - 7, 7), off(rc - 15, 6), off(rc - 15, 0.4)]
            poly(T, pad, w=W1, fill=F1)
        for r1, r2 in ((40, 112), (-112, -40)):
            pts = [off(r1, 13), off(r2, 13), off(r2, 18), off(r1, 18)]
            poly(T, pts, w=W2, fill=F2)

    def piston_x(rc):
        """ball centre x for a piston at pitch radius rc"""
        return face(rc) + 20 / NX

    def p_pistons(T, k=1.0):
        for rc in (80, -80):
            xb = piston_x(rc)
            x0, x1 = xb + 6, xb + 176
            poly(T, [(x0, rc + 14), (x1 - 4, rc + 14), (x1, rc + 10), (x1, rc - 10), (x1 - 4, rc - 14),
                     (x0, rc - 14)], w=W1, fill=F2, cls='draw')
            cx, cy = T(xb, rc)
            d.circle(cx, cy, 8.5 * k, w=W1, fill=F2)
            d.path(P(T(xb + 3, rc), T(x1 - 2, rc)), w=W3, dash='3 2')

    BX0, BX1 = 500, 720

    def p_barrel(T, k=1.0):
        for sg in (1, -1):
            body = [(BX0 + 4, 112 * sg), (BX1, 112 * sg), (BX1, 20 * sg), (BX0, 20 * sg), (BX0, 108 * sg)]
            poly(T, body, w=W1, fill=HA, cls='draw')
            poly(T, [(BX0, 95 * sg), (BX1 - 18, 95 * sg), (BX1 - 18, 65 * sg), (BX0, 65 * sg)], w=W2, fill=WHITE)
            poly(T, [(BX1 - 18, 86 * sg), (BX1, 86 * sg), (BX1, 74 * sg), (BX1 - 18, 74 * sg)], w=W2,
                 fill=WHITE)
            for x in range(586, 650, 6):
                d.path(P(T(x, 20 * sg), T(x + 3, 23 * sg), T(x + 6, 20 * sg)), w=W3)

    def p_valveplate(T, k=1.0):
        for sg, (r1, r2) in ((1, (70, 90)), (-1, (68, 94))):
            poly(T, [(720, 118 * sg), (736, 118 * sg), (736, r2 * sg), (720, r2 * sg)], w=W1, fill=HB)
            poly(T, [(720, r1 * sg), (736, r1 * sg), (736, 22 * sg), (720, 22 * sg)], w=W1, fill=HB)

    PB0, PB1 = 736, 900

    def p_portblock(T, k=1.0):
        poly(T, [(PB0, 142), (PB1, 142), (PB1, -142), (PB0, -142)], w=W1, fill=HA, cls='draw')
        # shaft bore + rear needle bearing
        poly(T, [(PB0, 30), (812, 30), (812, -30), (PB0, -30)], w=W1, fill=WHITE)
        for sg in (1, -1):
            poly(T, [(764, 21 * sg), (806, 21 * sg), (806, 30 * sg), (764, 30 * sg)], w=W2, fill=F2)
            for x in range(768, 806, 6):
                d.path(P(T(x, 22 * sg), T(x, 29 * sg)), w=W3)
        # pressure passage (top) -> outlet on the rear face
        poly(T, [(PB0, 90), (PB1, 90), (PB1, 70), (PB0, 70)], w=W1, fill=WHITE)
        # suction passage (bottom) -> inlet on the lower face
        poly(T, [(PB0, -66), (856, -66), (856, -142), (816, -142), (816, -94), (PB0, -94)], w=W1, fill=WHITE)
        # pilot passage to the compensator
        poly(T, [(826, 90), (832, 90), (832, 142), (826, 142)], w=W2, fill=WHITE)

    def p_comp(T, k=1.0):
        poly(T, [(784, 142), (884, 142), (884, 184), (784, 184)], w=W1, fill=HB, cls='draw')
        poly(T, [(792, 158), (870, 158), (870, 168), (792, 168)], w=W2, fill=WHITE)
        for x0 in (800, 826, 852):
            poly(T, [(x0, 159), (x0 + 10, 159), (x0 + 10, 167), (x0, 167)], w=W2, fill=F2)
        d.path(P(T(870, 163), T(878, 163)), w=W2)
        pts = [(870, 163)] + [(870 + i * 2, 163 + (3 if i % 2 else -3)) for i in range(1, 6)]
        d.path(P(*[T(x, r) for x, r in pts]), w=W3)
        d.path(P(T(829, 142), T(829, 158)), w=W2)

    def p_fittings(T, k=1.0):
        # outlet (pressure) on the rear face
        poly(T, [(PB1, 98), (918, 98), (918, 62), (PB1, 62)], w=W1, fill=WHITE)
        poly(T, [(918, 92), (936, 92), (936, 68), (918, 68)], w=W1, fill=WHITE)
        d.path(P(T(PB1, 88), T(936, 88)) + ' ' + P(T(PB1, 72), T(936, 72)), w=W3, dash='3 2')
        # inlet (suction) on the lower face
        poly(T, [(808, -142), (864, -142), (864, -160), (808, -160)], w=W1, fill=WHITE)
        poly(T, [(814, -160), (858, -160), (858, -178), (814, -178)], w=W1, fill=WHITE)
        d.path(P(T(818, -142), T(818, -178)) + ' ' + P(T(854, -142), T(854, -178)), w=W3, dash='3 2')

    def p_housing(T):
        top = [(228, 24), (228, 168), (256, 168), (256, 142), (PB0, 142), (PB0, 128), (330, 128), (330, 86),
               (300, 86), (300, 60), (278, 60), (278, 46), (246, 46), (246, 26), (244, 24)]
        bot = [(228, -24), (228, -168), (256, -168), (256, -142), (PB0, -142), (PB0, -128), (300, -128),
               (300, -60), (278, -60), (278, -46), (246, -46), (246, -26), (244, -24)]
        poly(T, top, w=W1, fill=HA, cls='draw')
        poly(T, bot, w=W1, fill=HA, cls='draw')
        # control-piston bore in the upper boss
        poly(T, [(306, 107), (330, 107), (330, 93), (306, 93)], w=W2, fill=WHITE)
        # case-drain port through the top wall
        poly(T, [(566, 128), (578, 128), (578, 142), (566, 142)], w=W2, fill=WHITE)
        poly(T, [(560, 142), (584, 142), (584, 156), (560, 156)], w=W1, fill=WHITE)
        poly(T, [(563, 156), (581, 156), (581, 166), (563, 166)], w=W1, fill=WHITE)
        # mounting-flange bolt (hidden)
        for sg in (1, -1):
            d.path(P(T(228, 156 * sg), T(256, 156 * sg)), w=W3, dash=DASH_CENTRE)

    def p_spring(T):
        # bias spring between the front wall and the lower back of the swashplate
        x0, x1 = 300, face(-104) - 30 * NX
        pts = [(x0, -104)]
        m = 8
        for i in range(1, m):
            pts.append((x0 + (x1 - x0) * i / m, -104 + (7 if i % 2 else -7)))
        pts.append((x1, -104))
        d.path(P(*[T(x, r) for x, r in pts]), w=W2)

    # ================================================================== assembled half-section
    T0 = lambda x, rr: (x, A - rr)
    EXK, EY = 0.62, 694.0
    order = [('shaft', 120, 450), ('seal', 228, 246), ('bearing', 246, 278), ('ctrl', 312, 392),
             ('swash', 326, 428), ('retainer', 360, 440), ('pistons', 388, 612), ('barrel', BX0, BX1),
             ('valveplate', 720, 736), ('portblock', PB0, 936)]
    ex_x0 = {}
    x = 66.0
    for nm, xa, xb in order:
        ex_x0[nm] = (x, xa)
        x += (xb - xa) * EXK + 26
    ex_end = x

    with d.g(id='pump-assembled', cls='view'):
        with d.g(id='pump-housing', cls='part'):
            p_housing(T0)
        parts = [('pump-shaft', 'shaft', lambda T: p_shaft(T)), ('pump-seal', 'seal', p_seal),
                 ('pump-bearing', 'bearing', lambda T: p_bearing(T)), ('pump-control-piston', 'ctrl', p_ctrl),
                 ('pump-swashplate', 'swash', lambda T: (p_swash(T), p_spring(T0))),
                 ('pump-slippers', 'retainer', p_retainer), ('pump-barrel', 'barrel', p_barrel),
                 ('pump-pistons', 'pistons', p_pistons), ('pump-valveplate', 'valveplate', p_valveplate),
                 ('pump-portblock', 'portblock', lambda T: (p_portblock(T), p_comp(T), p_fittings(T)))]
        for pid, key, fn in parts:
            x0, xa = ex_x0[key]
            with d.g(id=pid, cls='part' + (' subject' if key == 'swash' else ''),
                     data_explode_x=n(x0 - xa), data_explode_y=n(EY - A)):
                fn(T0)
        # flow arrows
        d.arrow([(836, A + 236), (836, A + 196)], w=W1, L=10, half=3, id='pump-flow-in')
        d.text(824, A + 230, 'IN · suction', size=11, mono=True, fill=INK3, anchor='end')
        d.arrow([(944, A - 80), (986, A - 80)], w=W1, L=10, half=3, id='pump-flow-out')
        d.text(944, A - 96, 'OUT · 280 bar', size=11, mono=True, fill=INK3)
        d.text(64, 518, 'SECTION A–A · assembled', size=11, weight=700, ls='0.14em')

    # ================================================================== exploded (same parts)
    with d.g(id='pump-exploded', cls='view exploded'):
        d.centreline(54, EY, ex_end - 10, EY)
        for pid, key, fn in parts:
            x0, xa = ex_x0[key]
            T = mk(x0, xa, EXK, EY)
            with d.g(id=pid + '-x', cls='part' + (' subject' if key == 'swash' else '')):
                if key == 'shaft':
                    p_shaft(T, EXK, broken=True)
                elif key == 'swash':
                    p_swash(T, EXK, hub=True)
                    # swash angle annotation
                    with d.g(id='pump-alpha', cls='annotation'):
                        px, py = T(XS, 0)
                        top = T(face(150), 150)
                        d.line(px, py, px, py - 150 * EXK, w=W3, stroke=ACC, dash='2 3')
                        d.line(px, py, top[0], top[1], w=W3, stroke=ACC, dash='2 3')
                        r = 128 * EXK
                        d.path(arc_d(px, py, r, -90, -90 + math.degrees(ALPHA)), w=W2, stroke=ACC)
                        d.text(px + 7, py - r - 6, 'α', size=14, weight=700, fill=ACC)
                elif key == 'bearing':
                    p_bearing(T, EXK)
                elif key == 'portblock':
                    p_portblock(T, EXK)
                    p_comp(T, EXK)
                    p_fittings(T, EXK)
                else:
                    fn(T)
                    if key in ('barrel', 'valveplate', 'bearing', 'seal'):
                        xa_, xb_ = {'barrel': (BX0, BX1), 'valveplate': (720, 736), 'bearing': (248, 276),
                                    'seal': (230, 244)}[key]
                        r0 = {'barrel': 20, 'valveplate': 22, 'bearing': 20, 'seal': 20}[key]
                        for xx in (xa_, xb_):
                            d.path(P(T(xx, r0), T(xx, -r0)), w=W2)
        d.text(64, 806, 'EXPLODED · rotating group', size=11, weight=700, ls='0.14em')

    # ================================================================== balloons (assembled + exploded)
    items = [('1', 'Drive spline', 'to the AMAGB pad', (166, A + 17), (166, 548)),
             ('2', 'Shaft seal', '', (237, A - 23), (226, 76)),
             ('3', 'Front bearing', '', (262, A + 40), (262, 548)),
             ('4', 'Swashplate', 'sets displacement (α)', (face(70) - 12, A - 70), (360, 76)),
             ('5', 'Control piston', 'compensator-driven', (352, A - 100), (300, 76)),
             ('6', 'Slipper + retainer', '', (face(-80) + 8, A + 80), (380, 548)),
             ('7', 'Piston ×9', '', (560, A - 80), (470, 76)),
             ('8', 'Cylinder barrel', 'splined to the shaft', (650, A + 104), (650, 548)),
             ('9', 'Valve plate', 'kidney ports', (728, A + 108), (730, 548)),
             ('10', 'Port block', '', (884, A + 120), (900, 548)),
             ('11', 'Compensator', 'pressure limit', (850, A - 176), (850, 76)),
             ('12', 'Case drain', 'to return', (572, A - 166), (572, 76)),
             ]
    with d.g(id='pump-callouts', cls='callouts'):
        for num, name, sub, (tx, ty), (bx, by) in items:
            d.callout(num, bx, by, tx, ty, accent=(num == '4'), id='pump-c' + num)
    # exploded balloons
    exb = {'1': ('shaft', 166, 17), '3': ('bearing', 262, 44), '5': ('ctrl', 352, 106), '4': ('swash', 410, 116),
           '6': ('retainer', 400, 112), '7': ('pistons', 560, 94), '8': ('barrel', 640, 112),
           '9': ('valveplate', 728, 118), '10': ('portblock', 780, 142), '11': ('portblock', 850, 184)}
    with d.g(id='pump-x-callouts', cls='callouts'):
        for num, (key, xx, rr) in exb.items():
            x0, xa = ex_x0[key]
            T = mk(x0, xa, EXK, EY)
            tx, ty = T(xx, rr)
            by = 586 if num not in ('11',) else 576
            bx = tx
            if num == '3':
                bx = tx - 4
            if num == '4':
                bx = tx - 44
            if num == '10':
                tx, ty = T(800, -142)
                ty += 2
                bx, by = tx, 790
            if num == '11':
                bx = tx + 34
            d.callout(num, bx, by, tx, ty - 2, accent=(num == '4'), id='pump-xc' + num, r=9.5, size=10.5)

    # ================================================================== parts list
    with d.g(id='pump-partslist', cls='legend'):
        lx, ly = 1040, 76
        d.kicker(lx, ly, 'Parts')
        d.line(lx, ly + 12, 1540, ly + 12, w=W3)
        col = 0
        for i, (num, name, sub, _, _) in enumerate(items):
            c, r = divmod(i, 6)
            x = lx + c * 252
            y = ly + 42 + r * 40
            d.callout(num, x + 11, y - 4, accent=(num == '4'))
            d.text(x + 30, y - 6, name, size=13.5, weight=650, fill=ACC if num == '4' else INK)
            if sub:
                d.text(x + 30, y + 9, sub, size=10.5, mono=True, fill=INK3)
        d.line(lx, ly + 282, 1540, ly + 282, w=W3)
        d.text(lx, ly + 304, 'axial piston · variable displacement · engine-driven via the AMAGB', size=11,
               mono=True, fill=INK3)
        d.text(lx, ly + 322, 'one per system: SYS1 and SYS2 · nominal 280 bar', size=11, mono=True, fill=INK3)

    # ================================================================== view B (valve plate face) + data plate
    with d.g(id='pump-viewb', cls='detail'):
        cx, cy, R = 1240, 662, 80
        d.circle(cx, cy, R, w=W1, fill=WHITE, cls='draw')
        d.circle(cx, cy, 20, w=W1)
        for a in (30, 150, 270):
            d.circle(cx + 74 * math.cos(math.radians(a)), cy + 74 * math.sin(math.radians(a)), 4, w=W2)

        def kidney(r1, r2, a0, a1, fill=WHITE, **kw):
            p = arc_d(cx, cy, r2, a0, a1) + ' ' + arc_d(cx, cy, r1, a1, a0, move=False).replace('A', 'L%s %s A' % (
                n(cx + r1 * math.cos(math.radians(a1))), n(cy + r1 * math.sin(math.radians(a1)))), 1) + ' Z'
            d.path(p, fill=fill, **kw)
        kidney(42, 58, -160, -20, w=W1, id='pump-kidney-pressure')
        kidney(40, 62, 20, 160, w=W1, fill=F2, id='pump-kidney-suction')
        d.centreline(cx - R - 12, cy, cx + R + 12, cy)
        d.centreline(cx, cy - R - 12, cx, cy + R + 12)
        d.text(cx, cy - 64, 'P', size=11, mono=True, weight=700, anchor='middle', halo=True)
        d.text(cx, cy + 74, 'S', size=11, mono=True, weight=700, anchor='middle', halo=True)
        d.path(arc_d(cx, cy, R + 8, 200, 245), w=W2)
        d.arrowhead(cx + (R + 8) * math.cos(math.radians(246)), cy + (R + 8) * math.sin(math.radians(246)),
                    math.radians(246 + 90), L=8, half=2.4)
        d.text(cx, cy + R + 30, 'VIEW B · valve plate face', size=11, weight=700, ls='0.1em', anchor='middle')
    with d.g(id='pump-dataplate', cls='dataplate'):
        x0, y0, w_, h_ = 1352, 596, 196, 150
        d.rect(x0, y0, w_, h_, rx=8, w=W1, fill=F1)
        d.rect(x0 + 6, y0 + 6, w_ - 12, h_ - 12, rx=5, w=W3)
        for cx_, cy_ in ((x0 + 14, y0 + 14), (x0 + w_ - 14, y0 + 14), (x0 + 14, y0 + h_ - 14),
                         (x0 + w_ - 14, y0 + h_ - 14)):
            d.circle(cx_, cy_, 3, w=W2, fill=WHITE)
        d.text(x0 + w_ / 2, y0 + 34, 'ENGINE-DRIVEN PUMP', size=11, weight=700, ls='0.08em', anchor='middle')
        rows = [('P/N', 'SYN-PN-HYDP'), ('S/N', 'HYDP-000010'), ('SYS', '280 bar nominal')]
        for i, (k, v) in enumerate(rows):
            y = y0 + 62 + i * 22
            d.text(x0 + 24, y, k, size=10.5, mono=True, fill=INK3)
            d.text(x0 + 62, y, v, size=11, mono=True, weight=600, id='pump-plate-' + k.replace('/', '').lower())
        d.text(x0 + w_ / 2, y0 + h_ - 24, 'serial follows the part', size=9.5, mono=True, fill=INK4,
               anchor='middle')

    d.sheet(3, 'Engine-driven pump — axial piston', 'section A–A · exploded rotating group')
    return d


if __name__ == '__main__':
    print(build().save('hyd-pump.svg'))
