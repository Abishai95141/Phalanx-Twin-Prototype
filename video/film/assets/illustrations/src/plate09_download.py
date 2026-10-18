"""PHX-ILL-09 · sortie-download.svg — aircraft on the ground -> removable recorder module -> ground station
(decoder, contract 0.2.0) -> the five contract topics.  Recorder sinks are the dictionary's (MPDRU, HUMS DAU,
ECMS log).  Subject (accent): the removable recorder.  Blue: data."""
import math
from lib import *
from plate01_aircraft import SIDE_TOP, SIDE_BOT

S = 44.0
X0, GY = 74.0, 610.0


def sd(x, z):
    return X0 + x * S, GY - z * S


ICONS = {
    'wave': '<path d="M3 13c2.2 0 2.2-5 4.5-5s2.3 8 4.5 8 2.3-10 4.5-10S18.8 13 21 13"/>',
    'alert': '<path d="M12 4l9 15.5H3z"/><path d="M12 10v4M12 17h.01"/>',
    'gauge': '<path d="M4.5 16.5a7.5 7.5 0 1 1 15 0"/><path d="M12 16.5l3.6-4.4"/>',
    'wrench': '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.1L4 16.7 7.3 20l5.3-5.3a4 4 0 0 0 5.1-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    'send': '<path d="M12 19V5M5.5 11.5L12 5l6.5 6.5"/>',
}


def icon(d, name, x, y, size=24, color=INK, sw=1.7):
    k = size / 24.0
    d.add('<g transform="translate(%s %s) scale(%s)" fill="none" stroke="%s" stroke-width="%s" '
          'stroke-linecap="round" stroke-linejoin="round">%s</g>' % (n(x), n(y), n(k), color, n(sw / k), ICONS[name]))


def build():
    d = Doc('dl', 'Sortie download — recorder to contract topics',
            'The aircraft lands, the removable recorder module is taken to the ground station, decoded against '
            'the frozen contract and split into five topics.')
    d.std_defs()
    HA = d.hatch()

    # ------------------------------------------------------------------ aircraft on the ground
    with d.g(id='dl-aircraft', cls='view'):
        # gear
        ax, ay = sd(3.55, .23)
        d.path(P(sd(3.66, .76), sd(3.55, .23)), w=W1 * 1.4)
        d.circle(ax, ay, .23 * S, w=W1, fill=WHITE)
        ax, ay = sd(8.25, .33)
        d.path(P(sd(8.12, .80), sd(8.25, .33)), w=W1 * 1.6)
        d.circle(ax, ay, .33 * S, w=W1, fill=WHITE)
        d.circle(ax, ay, .15 * S, w=W2, fill=F2)
        d.path('M' + ' L'.join('%s %s' % tuple(n(v) for v in sd(*p)) for p in SIDE_TOP + SIDE_BOT) + ' Z', w=W1,
               fill=WHITE, cls='draw', id='dl-aircraft-outline')
        d.path('M%s %s C%s %s %s %s %s %s' % (*sd(2.62, 1.6), *sd(3.0, 2.38), *sd(3.9, 2.4), *sd(4.75, 1.92)), w=W2,
               fill=F1)
        d.path(P(sd(4.05, .72), sd(4.05, 1.32), sd(4.7, 1.36), sd(5.8, .98), close=True), w=W2, fill=F2)
        d.path(P(sd(11.92, 2.28), sd(12.12, 4.37)), w=W2)
        d.path(P(sd(12.62, 1.08), sd(12.62, 1.92)), w=W2)
        d.line(sd(-0.5, 0)[0], GY, sd(13.8, 0)[0], GY, w=W1)
        d.rect(sd(-0.5, 0)[0], GY, 14.3 * S, 6, w=0, stroke='none', fill=HA)
        # open avionics-bay door + recorder slot (subject)
        with d.g(id='dl-bay', cls='subject'):
            x0, y0 = sd(5.0, 1.82)
            x1, y1 = sd(5.95, 1.46)
            d.rect(x0, y0, x1 - x0, y1 - y0, rx=2, w=W2, fill=F2)
            d.rect(x0 + 6, y0 + 4, 18, y1 - y0 - 8, rx=2, w=W1, stroke=ACC, fill=WHITE, id='dl-slot')
            d.path(P((x0, y1), (x0 - 10, y1 + 26), (x1 - 10, y1 + 26), (x1, y1)), w=W2, dash=DASH_PHANTOM)
        d.text(*sd(0, -0.9), 'TJ107 · on the line after the sortie', size=11, mono=True, fill=INK3)

    # ------------------------------------------------------------------ removable recorder (accent)
    R = Iso(682.0, 330.0)
    with d.g(id='dl-recorder', cls='subject'):
        R.box(d, 0, 112, 0, 70, 0, 24, fills=(WHITE, WHITE, WHITE), stroke=ACC, ids=('dl-rec-front', 'dl-rec-side',
                                                                                     'dl-rec-top'))
        MF, MT = R.front(0), R.top(24)
        d.path(segs_d(rect_segs(14, 6, 40, 12, 3), MF), w=W2, stroke=ACC)
        d.path(segs_d(rect_segs(70, 9, 26, 6, 3), MF), w=W2, stroke=ACC)
        for i in range(5):
            d.path(segs_d(line_segs((14 + i * 18, 14), (14 + i * 18, 56)), MT), w=W3, stroke=ACC)
        d.text(0, 0, 'REC', size=11, mono=True, weight=700, fill=ACC, transform=face_text_matrix(MT, 18, 66 - 8 - 4))
    # move arrow: bay -> recorder
    with d.g(id='dl-move-1', cls='move'):
        a = sd(5.4, 1.95)
        b = R(10, 30, 40)
        d.path('M%s %s C%s %s %s %s %s %s' % (*a, a[0] + 20, a[1] - 120, b[0] - 60, b[1] - 60, b[0] - 8, b[1] - 6),
               w=W2, dash='5 4')
        d.arrowhead(b[0] - 8, b[1] - 6, math.atan2(54, 52), L=9, half=2.6)
        d.text(a[0] - 34, a[1] - 96, 'after landing', size=10.5, mono=True, fill=INK3, anchor='end')

    # ------------------------------------------------------------------ ground station
    G = Iso(930.0, 540.0)
    with d.g(id='dl-ground-station', cls='part'):
        G.box(d, 0, 186, 0, 150, 0, 150, ids=('dl-gs-front', 'dl-gs-side', 'dl-gs-top'))
        MF, MS, MT = G.front(0), G.side(186), G.top(150)
        d.path(segs_d(rect_segs(16, 76, 120, 56, 6), MF), w=W2, fill=F1)              # display
        for i in range(3):
            d.path(segs_d(line_segs((28, 118 - i * 14), (96 - i * 18, 118 - i * 14)), MF), w=W3)
        d.path(segs_d(rect_segs(16, 30, 74, 12, 3), MF), w=W1, fill=WHITE, id='dl-gs-slot')   # reader slot
        d.path(segs_d(circle_segs(160, 36, 6), MF), w=W1, fill=WHITE)
        for i in range(6):
            d.path(segs_d(line_segs((20 + i * 20, 20), (20 + i * 20, 130)), MS), w=W3)
        d.text(0, 0, 'GROUND DECODER', size=10, mono=True, weight=700, transform=face_text_matrix(MF, 16, 58))
    with d.g(id='dl-move-2', cls='move'):
        a = R(112, 35, 12)
        b = G.front(0)(53, 36)
        d.path('M%s %s C%s %s %s %s %s %s' % (*a, a[0] + 60, a[1] + 10, b[0] - 70, b[1] - 30, b[0] - 8, b[1] - 3),
               w=W2, dash='5 4')
        d.arrowhead(b[0] - 8, b[1] - 3, math.atan2(27, 62), L=9, half=2.6)
        d.text(a[0] + 60, a[1] - 12, 'into the reader', size=10.5, mono=True, fill=INK3)

    # ------------------------------------------------------------------ five contract topics
    topics = [('param.samples', 'channel samples · validity · lanes', 'wave'),
              ('events', 'BIT faults · cautions', 'alert'),
              ('usage.counters', 'landings · streamings · hours', 'gauge'),
              ('maint.records', 'jobs · removals · findings', 'wrench'),
              ('orders', 'commands · status', 'send')]
    src = G(186, 30, 110)
    MSg = G.side(186)
    d.path(segs_d(rect_segs(18, 98, 26, 22, 3), MSg), w=W1, fill=WHITE, id='dl-gs-port')
    src = MSg(31, 109)
    with d.g(id='dl-topics', cls='topics'):
        for i, (name, sub, ic) in enumerate(topics):
            y = 214 + i * 92
            x = 1226
            with d.g(id='dl-topic-' + name.replace('.', '-'), cls='topic'):
                c1 = (src[0] + 70, src[1])
                c2 = (x - 70, y + 24)
                if name != 'orders':
                    d.path('M%s %s C%s %s %s %s %s %s' % (*src, *c1, *c2, x - 4, y + 24), w=W1, stroke=BLUE,
                           cls='draw flow')
                    d.arrowhead(x - 2, y + 24, 0, L=8, half=2.4, fill=BLUE)
                else:
                    d.path('M%s %s C%s %s %s %s %s %s' % (*src, *c1, *c2, x - 4, y + 24), w=W1, stroke=BLUE,
                           dash='5 4', cls='draw flow')
                    d.arrowhead(src[0] + 6, src[1] + 2, math.pi + 0.35, L=8, half=2.4, fill=BLUE)
                d.rect(x, y, 312, 48, rx=24, w=W1, stroke=BLUE, fill=WHITE)
                d.circle(x + 24, y + 24, 16, w=W2, stroke=BLUE, fill=WHITE)
                icon(d, ic, x + 24 - 9, y + 24 - 9, size=18, color=BLUE)
                d.text(x + 50, y + 22, name, size=15, mono=True, weight=600)
                d.text(x + 50, y + 37, sub, size=10.5, mono=True, fill=INK3)
        d.text(1226, 196, 'CONTRACT TOPICS · 0.2.0', size=11, weight=700, ls='0.14em')
        d.text(1226, 690, 'orders return only through orders.commands', size=10.5, mono=True, fill=INK3)

    # ------------------------------------------------------------------ captions + callouts
    items = [('1', 'Aircraft on the line', 'sortie flown, data aboard'),
             ('2', 'Removable recorder', 'MPDRU · HUMS DAU · ECMS log'),
             ('3', 'Ground station', 'decoder · contract a4396f1d'),
             ('4', 'Contract topics', 'five streams, read by name')]
    pos = [(sd(1.2, 3.2), sd(1.6, 1.3)), ((660, 220), R(30, 20, 24)), ((1000, 250), G(60, 60, 150)),
           ((1200, 150), (1226, 196 - 14))]
    with d.g(id='dl-callouts', cls='callouts'):
        for (num, _, _), ((bx, by), (tx, ty)) in zip(items, pos):
            d.callout(num, bx, by, tx, ty, accent=(num == '2'), id='dl-c' + num)
    with d.g(id='dl-list', cls='legend'):
        lx, ly = 74, 736
        for i, (num, name, sub) in enumerate(items):
            c, r = divmod(i, 2)
            x = lx + c * 340
            y = ly + r * 42
            d.callout(num, x + 11, y - 4, accent=(num == '2'))
            d.text(x + 30, y - 5, name, size=13.5, weight=650, fill=ACC if num == '2' else INK)
            d.text(x + 30, y + 10, sub, size=10.5, mono=True, fill=INK3)
    with d.g(id='dl-timing', cls='note'):
        d.text(74, 852, 'event time ≠ ingest time: HYD-101 from sortie TJ107-20260618T1430 was ingested 18 Jun 21:08',
               size=11, mono=True, fill=INK3)
    d.text(64, 76, 'SORTIE DOWNLOAD · AIRCRAFT TO CONTRACT', size=11, weight=700, ls='0.14em')
    d.sheet(9, 'Sortie download — recorder to topics', 'recorder · ground decoder · 5 topics')
    return d


if __name__ == '__main__':
    print(build().save('sortie-download.svg'))
