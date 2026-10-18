"""PHX-ILL-04 · f404-engine.svg — low-bypass afterburning turbofan, side cutaway (both halves sectioned along the
gas path) with the accessory gearbox, FADEC and sensor harness hung below.  Gas-path stations 2 · 25 · 3 · 4 · 5 · 7.
Sensor names are the dictionary's ENG.* channels.  Subject (accent): the FADEC; blue: sensor harness."""
import math
from lib import *

A = 418.0
KR = 1.1


def build():
    d = Doc('eng', 'F404-class afterburning turbofan — cutaway',
            'Side view of a low-bypass afterburning turbofan: upper half sectioned along the gas path with '
            'stations 2, 25, 3, 4, 5 and 7; lower half external with the accessory gearbox, FADEC and sensor '
            'harness.')
    d.std_defs()
    HA, HB = d.hatch(), d.hatch('b')
    S = {'sg': 1, 'sfx': ''}
    T = lambda x, rr: (x, A - S['sg'] * rr * KR)

    def poly(pts, **kw):
        d.path(P(*[T(x, r) for x, r in pts], close=True), **kw)

    def pl(pts, **kw):
        d.path(P(*[T(x, r) for x, r in pts]), **kw)

    # outer profile (rr of the outer casing skin) and inner skin
    OUT = [(128, 170), (150, 180), (380, 180), (420, 172), (1000, 166), (1290, 166)]
    IN_ = [(150, 168), (380, 168), (420, 160), (1000, 154), (1290, 154)]

    def outer_r(x):
        for (x0, r0), (x1, r1) in zip(OUT, OUT[1:]):
            if x0 <= x <= x1:
                return r0 + (r1 - r0) * (x - x0) / (x1 - x0)
        return OUT[-1][1]

    # ================================================================== section (both halves)
    def section():
      with d.g(id='eng-section' + S['sfx'], cls='view section'):
        with d.g(id='eng-casing' + S['sfx'], cls='part'):
            poly(OUT + IN_[::-1], w=W1, fill=HA, cls='draw')
            # inlet lip
            pl([(150, 168), (132, 166), (126, 172), (128, 178), (150, 180)], w=W1)
            for x in (380, 640, 1000):
                pl([(x, outer_r(x) + 6), (x, outer_r(x) - 18)], w=W2)
        # core cowl (inner wall of the bypass duct)
        with d.g(id='eng-core-casing' + S['sfx'], cls='part'):
            core_o = [(380, 116), (420, 124), (640, 132), (780, 134), (900, 128)]
            core_i = [(904, 120), (780, 126), (640, 124), (420, 116), (386, 112)]
            poly(core_o + core_i, w=W1, fill=HB, cls='draw')
            d.path(P(T(380, 116), T(372, 113), T(386, 112)), w=W1)
        # spinner + fan hub + IGV + fan
        with d.g(id='eng-fan' + S['sfx'], cls='part'):
            spin = 'M%s %s C%s %s %s %s %s %s L%s %s L%s %s' % (
                *T(150, 0), *T(160, 30), *T(190, 44), *T(222, 50), *T(360, 84), *T(360, 0))
            d.path(spin, w=W1, fill=F1, cls='draw')
            # variable inlet guide vanes
            pl([(200, 46), (200, 166)], w=W2)
            pl([(196, 46), (204, 46), (204, 166), (196, 166)], w=W3)
            cx, cy = T(200, 168)
            d.circle(cx, cy - 4 * S['sg'], 2.2, w=W2, fill=WHITE)
            hub = lambda x: 50 + (84 - 50) * (x - 222) / (360 - 222)
            for i, x in enumerate((226, 272, 318)):
                poly([(x, hub(x) + 1), (x + 22, hub(x + 22) + 1), (x + 18, 166), (x + 3, 166)], w=W1, fill=F2,
                     cls='blade')
                xs = x + 30
                poly([(xs, hub(xs) + 2), (xs + 10, hub(xs + 10) + 2), (xs + 10, 166), (xs, 166)], w=W2,
                     fill=WHITE, cls='vane')
            # fan discs
            for x in (228, 274, 320):
                poly([(x + 2, 16), (x + 18, 16), (x + 16, hub(x + 10) - 2), (x + 4, hub(x + 10) - 2)], w=W2,
                     fill=F1)
        # HP compressor (7 stages)
        with d.g(id='eng-hpc' + S['sfx'], cls='part'):
            def hub_c(x):
                return 78 + (96 - 78) * (x - 400) / (612 - 400)

            def tip_c(x):
                return 114 - (114 - 106) * (x - 400) / (612 - 400)
            pl([(386, 86), (400, 78), (612, 96), (640, 98)], w=W1)
            for i in range(7):
                x = 404 + i * 30
                poly([(x, hub_c(x)), (x + 13, hub_c(x + 13)), (x + 12, tip_c(x + 12)), (x + 1, tip_c(x + 1))],
                     w=W1, fill=F2, cls='blade')
                xs = x + 16
                poly([(xs, hub_c(xs) + 1), (xs + 8, hub_c(xs + 8) + 1), (xs + 8, tip_c(xs + 8) + 2),
                      (xs, tip_c(xs) + 2)], w=W2, fill=WHITE, cls='vane')
            # drum
            pl([(404, 30), (612, 30)], w=W2)
            pl([(404, 30), (404, 76)], w=W2)
            pl([(612, 30), (612, 94)], w=W2)
            for i in range(1, 7):
                x = 404 + i * 30 - 2
                pl([(x, 34), (x, hub_c(x) - 3)], w=W3)
        # combustor
        with d.g(id='eng-combustor' + S['sfx'], cls='part'):
            pl([(612, 96), (640, 98), (650, 94)], w=W1)
            liner_o = [(660, 118), (700, 122), (760, 120)]
            liner_i = [(760, 88), (700, 84), (660, 88)]
            d.path('M%s %s C%s %s %s %s %s %s L%s %s L%s %s L%s %s L%s %s C%s %s %s %s %s %s' % (
                *T(660, 118), *T(648, 116), *T(644, 92), *T(660, 88), *T(700, 84), *T(760, 88), *T(760, 120),
                *T(700, 122), *T(670, 122), *T(662, 121), *T(660, 118)), w=W1, fill=F1, cls='draw')
            for x in (690, 712, 734):
                cx, cy = T(x, 121)
                d.circle(cx, cy + 1.5, 1.6, w=W3, fill=WHITE)
                cx, cy = T(x, 85)
                d.circle(cx, cy - 1.5, 1.6, w=W3, fill=WHITE)
            # fuel nozzle through the casing
            pl([(650, 132), (650, 108), (656, 104)], w=W1)
            cx, cy = T(658, 103)
            d.circle(cx, cy, 3, w=W1, fill=WHITE)
            # inner casing
            pl([(640, 70), (770, 70)], w=W2)
        # turbines
        with d.g(id='eng-turbines' + S['sfx'], cls='part'):
            # HPT: NGV + rotor
            poly([(768, 86), (780, 86), (780, 124), (768, 124)], w=W2, fill=WHITE, cls='vane')
            poly([(788, 84), (804, 84), (804, 126), (788, 126)], w=W1, fill=F2, cls='blade')
            poly([(786, 30), (806, 30), (804, 82), (788, 82)], w=W2, fill=F1)
            # LPT: NGV + rotor
            poly([(818, 82), (830, 82), (830, 126), (818, 126)], w=W2, fill=WHITE, cls='vane')
            poly([(838, 80), (854, 80), (854, 128), (838, 128)], w=W1, fill=F2, cls='blade')
            poly([(836, 14), (856, 14), (854, 78), (838, 78)], w=W2, fill=F1)
            # HP shaft (tube) + LP shaft
            pl([(404, 26), (786, 26)], w=W2)
            pl([(220, 14), (856, 14)], w=W2)
            pl([(220, 6), (870, 6)], w=W3)
        # exhaust centrebody + mixer
        with d.g(id='eng-exhaust' + S['sfx'], cls='part'):
            d.path('M%s %s L%s %s L%s %s Q%s %s %s %s L%s %s Z' % (*T(856, 14), *T(856, 78), *T(950, 16),
                                                                   *T(966, 4), *T(972, 0), *T(856, 0)),
                   w=W1, fill=F1, cls='draw', id='eng-tailcone' + S['sfx'])
            pl([(900, 128), (930, 134), (940, 126)], w=W1)
        # afterburner
        with d.g(id='eng-afterburner' + S['sfx'], cls='part'):
            pl([(1000, 146), (1290, 146)], w=W2)
            for x in range(1012, 1290, 14):
                cx, cy = T(x, 150)
                d.circle(cx, cy, 1.3, w=W3, fill=WHITE)
            for rr in (40, 86, 128):
                cx, cy = T(1034, rr)
                d.path(P((cx + 13, cy - 8), (cx, cy), (cx + 13, cy + 8), (cx + 9, cy + 8), (cx + 3, cy),
                         (cx + 9, cy - 8), close=True), w=W2, fill=F2, cls='flameholder')
            for rr in (62, 106):
                cx, cy = T(1008, rr)
                d.line(cx, cy - 9, cx, cy + 9, w=W2)
                for k in (-5, 0, 5):
                    d.circle(cx + 3, cy + k, 1.1, w=0, stroke='none', fill=INK)
            # diffuser cone of the AB
            pl([(972, 0), (1000, 22), (1010, 22)], w=W3, dash=DASH_HIDDEN)
        # variable nozzle
        with d.g(id='eng-nozzle' + S['sfx'], cls='part'):
            pl([(1290, 166), (1300, 166), (1432, 140)], w=W1)
            poly([(1290, 154), (1362, 122), (1366, 124), (1296, 156)], w=W1, fill=F2, cls='draw')
            poly([(1366, 122), (1432, 132), (1432, 136), (1366, 125)], w=W1, fill=F2)
            pl([(1290, 154), (1290, 166)], w=W1)
            pl([(1432, 132), (1432, 140)], w=W1)
            cx, cy = T(1364, 123)
            d.circle(cx, cy, 2.4, w=W2, fill=WHITE)
        # gas-path flow arrows
        with d.g(id='eng-flow' + S['sfx'], cls='flow'):
            for pts in ([(120, 110), (190, 110)], [(400, 142), (470, 142)], [(680, 103), (740, 103)],
                        [(1080, 80), (1180, 80)], [(1380, 60), (1470, 60)]):
                d.arrow([T(*p) for p in pts], w=W2, L=9, half=2.6)

    section()
    S.update(sg=-1, sfx='-lower')
    section()
    S.update(sg=1, sfx='')
    d.centreline(*T(100, 0), *T(1490, 0))

    # ================================================================== lower half: external
    with d.g(id='eng-external', cls='view external'):
        # nozzle actuators
        with d.g(id='eng-nozzle-actuator', cls='part'):
            poly([(1170, -168), (1270, -168), (1270, -186), (1170, -186)], w=W1, fill=WHITE)
            pl([(1270, -177), (1330, -160)], w=W1)
            cx, cy = T(1330, -160)
            d.circle(cx, cy, 3, w=W1, fill=WHITE)
            pl([(1180, -168), (1180, -186)], w=W3)
        # accessory gearbox + tower shaft
        with d.g(id='eng-agb', cls='part'):
            poly([(430, -190), (560, -190), (570, -200), (570, -226), (560, -236), (430, -236), (420, -226),
                  (420, -200)], w=W1, fill=F1, cls='draw')
            for gx in (455, 495, 535):
                cx, cy = T(gx, -213)
                d.circle(cx, cy, 13, w=W3, dash=DASH_CENTRE)
            pl([(470, -176), (470, -190)], w=W2)
            pl([(470, -26), (470, -176)], w=W3, dash=DASH_HIDDEN)
            d.text(*T(495, -252), 'accessory gearbox', size=11, weight=650, anchor='middle')
        # FADEC (subject)
        with d.g(id='eng-fadec', cls='subject'):
            x0, x1, r0, r1 = 640, 790, -194, -250
            for bx in (660, 770):
                pl([(bx, -174), (bx, -194)], w=W2, stroke=ACC)
                cx, cy = T(bx, -184)
                d.circle(cx, cy, 3.4, w=W2, stroke=ACC, fill=WHITE)
            poly([(x0, r0), (x1, r0), (x1, r1), (x0, r1)], w=W1, stroke=ACC, fill=WHITE, cls='draw')
            for i in range(6):
                xx = x0 + 18 + i * 10
                pl([(xx, r1 + 6), (xx, r1 + 16)], w=W3, stroke=ACC)
            cx, cy = T(x1 - 20, (r0 + r1) / 2)
            d.circle(cx, cy, 9, w=W1, stroke=ACC, fill=WHITE)
            d.circle(cx, cy, 4, w=W2, stroke=ACC, fill=WHITE)
            d.text(*T(x0 + 14, -214), 'FADEC', size=15, weight=750, fill=ACC)
            d.text(*T(x0 + 14, -230), 'lanes A / B', size=10, mono=True, fill=INK3)
        # sensor harness (blue) — FADEC to the gas-path sensors
        with d.g(id='eng-harness', cls='signal'):
            ry = -262
            xs = {'T1': 160, 'N1': 290, 'T25': 396, 'N2': 470, 'PS3': 616, 'T5': 866, 'A8': 1250}
            pl([(160, ry), (640, ry)], w=W2, stroke=BLUE, cls='draw')
            pl([(790, ry), (1250, ry)], w=W2, stroke=BLUE, cls='draw')
            pl([(650, -250), (650, ry), (640, ry)], w=W2, stroke=BLUE)
            pl([(780, -250), (780, ry), (790, ry)], w=W2, stroke=BLUE)
            for k, x in xs.items():
                top = -outer_r(x) - (0 if k not in ('N2', 'A8') else 0)
                if k == 'N2':
                    top = -236
                if k == 'A8':
                    top = -186
                pl([(x, ry), (x, top - 2)], w=W2, stroke=BLUE)
                cx, cy = T(x, top - 2)
                d.circle(cx, cy, 2.8, w=0, stroke='none', fill=BLUE)
                cx, cy = T(x, ry)
                d.circle(cx, cy, 2.2, w=0, stroke='none', fill=BLUE)
                d.text(cx, cy + 18, 'ENG.' + k, size=10.5, mono=True, fill=BLUE, anchor='middle', weight=600)
            probes = {'T1': (160, -168, -112), 'T25': (396, -122, -96), 'PS3': (616, -132, -100),
                      'T5': (866, -128, -104)}
            for k, (x, r_out, r_tip) in probes.items():
                pl([(x, -outer_r(x)), (x, r_tip)], w=W2, stroke=BLUE, dash='3 2')
                cx, cy = T(x, r_tip)
                d.circle(cx, cy, 3.2, w=W2, stroke=BLUE, fill=WHITE)

    # ================================================================== stations
    with d.g(id='eng-stations', cls='stations'):
        ys = A - 222 * KR
        st = [('2', 192), ('25', 394), ('3', 616), ('4', 764), ('5', 866), ('7', 1286)]
        d.line(150, ys, 1440, ys, w=W2, cls='draw')
        d.text(140, ys + 4, 'STATION', size=10, weight=700, ls='0.12em', anchor='end')
        flow_r = {'2': 46, '25': 72, '3': 94, '4': 86, '5': 80, '7': 0}
        for s, x in st:
            with d.g(id='eng-st-' + s, cls='station'):
                d.line(x, ys - 6, x, ys + 6, w=W1)
                d.text(x, ys - 11, s, size=12.5, mono=True, weight=700, anchor='middle', halo=True)
                d.line(x, ys + 8, x, A - flow_r[s] * KR, w=W3, dash='2 3')

    # ================================================================== balloons + legend
    items = [('1', 'Fan', '3 stages · variable inlet guide vanes', (300, 140), (300, 268)),
             ('2', 'HP compressor', '7 stages · variable stators', (520, 100), (520, 268)),
             ('3', 'Combustor', 'annular', (708, 104), (708, 268)),
             ('4', 'HP turbine', '1 stage', (796, 110), (810, 268)),
             ('5', 'LP turbine', '1 stage · drives the fan', (846, 112), (880, 268)),
             ('6', 'Afterburner', 'spray bars · flameholders', (1030, 92), (1060, 268)),
             ('7', 'Variable nozzle', 'convergent–divergent · A8', (1400, 134), (1400, 268)),
             ('8', 'FADEC', 'engine control + condition data', (640, -222), (604, -222)),
             ('9', 'Accessory gearbox', 'tower shaft drive', (420, -213), (390, -213))]
    with d.g(id='eng-callouts', cls='callouts'):
        for num, name, sub, (tx, rr), (bx, brr) in items:
            if num in ('8', '9'):
                d.callout(num, *T(bx - 16, brr), *T(tx, rr), accent=(num == '8'), id='eng-c' + num)
            else:
                d.callout(num, bx, 122, *T(tx, rr), id='eng-c' + num)
    with d.g(id='eng-legend', cls='legend'):
        lx, ly = 64, 776
        for i, (num, name, sub, _, _) in enumerate(items):
            c, r = divmod(i, 3)
            x = lx + c * 300
            y = ly + r * 34
            d.callout(num, x + 11, y - 4, accent=(num == '8'))
            d.text(x + 30, y - 5, name, size=13.5, weight=650, fill=ACC if num == '8' else INK)
            d.text(x + 30, y + 9, sub, size=10.5, mono=True, fill=INK3)

    d.text(64, 76, 'SECTION ON THE ENGINE AXIS · ACCESSORIES BELOW', size=11, weight=700, ls='0.14em')
    d.text(64, 94, 'stations: 2 fan face · 25 HPC inlet · 3 HPC exit · 4 HPT inlet · 5 LPT exit · 7 nozzle inlet',
           size=11, mono=True, fill=INK3)
    d.sheet(4, 'Afterburning turbofan — F404 class', 'gas-path stations · FADEC · ENG.* sensors')
    return d


if __name__ == '__main__':
    print(build().save('f404-engine.svg'))
