"""PHX-ILL-10 · contract-gate.svg — five contract topics flow through the release gate (checks from
data_foundation_asof_20260622.json) into the as-of store, drawn as a cylinder of ingest-time slices with the
06:00 cut-off plane (subject, accent).  Blue: data."""
import math
from lib import *

TOPICS = ['param.samples', 'events', 'usage.counters', 'maint.records', 'orders']


def lcg(seed):
    s = seed

    def r():
        nonlocal s
        s = (1103515245 * s + 12345) % 2147483648
        return s / 2147483648.0
    return r


def build():
    d = Doc('gate', 'Release gate and as-of store',
            'Five contract topics pass a release gate with integrity checks and land in an as-of store of '
            'ingest-time slices; a 06:00 cut-off plane separates what was known from what was not yet ingested.')
    d.std_defs()
    HF = d.hatch('a')
    YS = [236 + i * 92 for i in range(5)]
    GX0, GX1 = 600.0, 680.0
    MX = 860.0
    CY, CR, CRX = 420.0, 150.0, 44.0
    CX0, CX1 = 930.0, 1500.0
    CUT = 1296.0

    # ------------------------------------------------------------------ pipes
    with d.g(id='gate-pipes', cls='pipes'):
        for i, (name, y) in enumerate(zip(TOPICS, YS)):
            with d.g(id='gate-pipe-' + name.replace('.', '-'), cls='pipe'):
                x0, x1, r = 74.0, GX0 - 6, 11.0
                d.rect(x0, y - r - 4, 8, 2 * r + 8, rx=2, w=W1, fill=WHITE)
                d.path(P((x0 + 8, y - r), (x1, y - r)) + ' ' + P((x0 + 8, y + r), (x1, y + r)), w=W1, cls='draw')
                d.line(x0 + 14, y, x1, y, w=W2, stroke=BLUE, dash='3 5', cls='flow')
                for k in range(4):
                    px = 150 + k * 96 + i * 17
                    d.rect(px, y - 5, 22, 10, rx=5, w=0, stroke='none', fill=BLUE, cls='packet')
                d.text(x0 + 2, y - r - 12, name, size=14, mono=True, weight=600)
                # pass-through tick at the gate
                d.circle((GX0 + GX1) / 2, y, 12, w=W1, fill=WHITE, cls='tick-ring')
                d.path(P(((GX0 + GX1) / 2 - 5.5, y + 0.5), ((GX0 + GX1) / 2 - 1.5, y + 4.5),
                         ((GX0 + GX1) / 2 + 6, y - 4.5)), w=W1 * 1.2, cls='tick')
                # out of the gate into the manifold
                d.path('M%s %s C%s %s %s %s %s %s' % (n(GX1 + 6), n(y), n(MX - 80), n(y), n(MX - 60), n(CY),
                                                     n(MX), n(CY)), w=W1, stroke=BLUE, cls='draw flow')
    # ------------------------------------------------------------------ gate
    with d.g(id='gate-gate', cls='gate'):
        top, bot = YS[0] - 58, YS[-1] + 46
        for x in (GX0 - 8, GX1 - 4):
            d.rect(x, top, 12, bot - top, w=W1, fill=d.hatch('f'), cls='draw')
        d.rect(GX0 - 22, top - 18, GX1 - GX0 + 44, 18, w=W1, fill=WHITE, cls='draw')
        d.text((GX0 + GX1) / 2, top - 5, 'RELEASE GATE', size=10, weight=700, ls='0.12em', anchor='middle')
        for y in YS[:-1]:
            d.line(GX0 + 4, y + 46, GX1 - 4, y + 46, w=W2)
        d.rect(GX0 - 22, bot, GX1 - GX0 + 44, 8, w=W1, fill=WHITE)
    # ------------------------------------------------------------------ manifold -> store
    with d.g(id='gate-manifold', cls='pipe'):
        d.circle(MX, CY, 6, w=W1, stroke=BLUE, fill=WHITE)
        d.path(P((MX + 6, CY - 16), (CX0 - CRX * .2, CY - 16)) + ' ' + P((MX + 6, CY + 16), (CX0 - CRX * .2, CY + 16)),
               w=W1)
        d.line(MX + 8, CY, CX0 - 4, CY, w=W1 * 1.2, stroke=BLUE, cls='flow')
        d.arrowhead(CX0 - 2, CY, 0, L=9, half=3, fill=BLUE)

    # ------------------------------------------------------------------ as-of store (cylinder of slices)
    rnd = lcg(26249)
    with d.g(id='gate-store', cls='store'):
        # body silhouette
        d.path('M%s %s L%s %s A%s %s 0 0 1 %s %s L%s %s A%s %s 0 0 1 %s %s Z' % (
            n(CX0), n(CY - CR), n(CX1), n(CY - CR), n(CRX), n(CR), n(CX1), n(CY + CR), n(CX0), n(CY + CR), n(CRX),
            n(CR), n(CX0), n(CY - CR)), w=W1, fill=WHITE, cls='draw', id='gate-store-body')
        xs = [CX0 + 22 + i * 34 for i in range(17)]
        for x in xs:
            known = x < CUT
            with d.g(cls='slice ' + ('known' if known else 'future')):
                d.path(arc_d(x, CY, CRX, 90, 270, ry=CR), w=W2 if known else W3, stroke=INK if known else INK5,
                       dash=None if known else '3 3')
                for k in range(4):
                    a = -80 + rnd() * 160
                    rr = 0.15 + rnd() * 0.75
                    px = x - CRX * rr * math.cos(math.radians(a)) * 0.6 + 8
                    py = CY + CR * rr * math.sin(math.radians(a))
                    if known:
                        d.circle(px, py, 2.6, w=0, stroke='none', fill=BLUE, cls='record')
                    else:
                        d.circle(px, py, 2.6, w=W3, stroke=INK4, fill=WHITE, cls='record future')
        d.ellipse(CX0, CY, CRX, CR, w=W1, fill=F1, id='gate-store-face')
        d.ellipse(CX0, CY, CRX * .55, CR * .55, w=W3)
        # cut-off plane (subject)
        with d.g(id='gate-cutoff', cls='subject'):
            pw, ph = 30.0, 184.0
            pts = [(CUT - pw, CY - ph + 22), (CUT + pw, CY - ph - 8), (CUT + pw, CY + ph - 22), (CUT - pw, CY + ph + 8)]
            d.path(P(*pts, close=True), w=W1, stroke=ACC, fill=HF, fill_opacity='0.9', cls='draw')
            d.path(arc_d(CUT, CY, CRX, -90, 270, ry=CR), w=W1 * 1.2, stroke=ACC)
            d.text(CUT - 44, CY - ph - 22, '06:00 cut-off', size=16, weight=700, fill=ACC, anchor='end')
            d.text(CUT - 44, CY - ph - 4, 'as_of(t): t_ingest ≤ t', size=12, mono=True, fill=ACC, anchor='end')
        d.text(CX1 - 70, CY - CR - 14, 'not yet known', size=11, mono=True, fill=INK4, anchor='middle')
        d.text(CX0 + 120, CY - CR - 14, 'known at 06:00', size=11, mono=True, fill=INK3, anchor='middle')
        # time axis
        ya = CY + CR + 58
        d.line(CX0, ya, CX1 + 20, ya, w=W2, cls='draw')
        d.arrowhead(CX1 + 26, ya, 0, L=8, half=2.4)
        d.text(CX1 + 30, ya + 4, 't_ingest', size=11, mono=True, fill=INK3)
        for x, t in ((CX0 + 22, '21 Jun 06:00'), (CX0 + 22 + 6 * 34, '21 Jun 18:00'), (CUT, '22 Jun 06:00'),
                     (CX0 + 22 + 16 * 34, '22 Jun 18:00')):
            d.line(x, ya - 5, x, ya + 5, w=W1 if x == CUT else W2, stroke=ACC if x == CUT else INK)
            d.text(x, ya + 20, t, size=10.5, mono=True, fill=ACC if x == CUT else INK3, anchor='middle',
                   weight=700 if x == CUT else 500)
        d.text(CX0, CY + CR + 104, 'AS-OF STORE · one slice per ingest batch', size=11, weight=700, ls='0.12em')

    # ------------------------------------------------------------------ check board
    with d.g(id='gate-checks', cls='checks'):
        bx, by = 452.0, 734.0
        checks = [('sha256', '2,782 / 2,782 files'), ('contract a4396f1d', '2,765 / 2,765 parquet'),
                  ('schema', '2,765 / 2,765'), ('row invariants', '0 ingest-before-event · 0 NaN'),
                  ('scoped identity', '3,388 colliding ids resolved')]
        d.text(bx, by - 12, 'GATE CHECKS · release v0.9 · contract 0.2.0', size=11, weight=700, ls='0.12em')
        for i, (k, v) in enumerate(checks):
            c, r = divmod(i, 3)
            x = bx + c * 360
            y = by + 14 + r * 26
            with d.g(id='gate-check-%d' % (i + 1), cls='check'):
                d.circle(x + 9, y - 4, 9, w=W2, fill=WHITE)
                d.path(P((x + 5, y - 4), (x + 8, y - 1), (x + 13.5, y - 7.5)), w=W1)
                d.text(x + 26, y, k, size=12.5, mono=True, weight=600)
                d.text(x + 26 + 8.2 * len(k) + 8, y, v, size=11, mono=True, fill=INK3)

    # ------------------------------------------------------------------ callouts
    with d.g(id='gate-callouts', cls='callouts'):
        d.callout('1', 240, 160, 200, YS[0] - 24, id='gate-c1')
        d.callout('2', (GX0 + GX1) / 2 + 70, 140, (GX0 + GX1) / 2 + 30, YS[0] - 70, id='gate-c2')
        d.callout('3', CX0 - 10, 220, CX0 + 12, CY - 120, id='gate-c3')
        d.callout('4', CUT + 92, 196, CUT + 30, CY - 178, accent=True, id='gate-c4')
    with d.g(id='gate-list', cls='legend'):
        rows = [('1', 'Five contract topics'), ('2', 'Release gate'), ('3', 'As-of store'), ('4', '06:00 cut-off')]
        x = 74
        for num, name in rows:
            d.callout(num, x + 11, 110, accent=(num == '4'))
            d.text(x + 28, 114, name, size=13, weight=650, fill=ACC if num == '4' else INK)
            x += 46 + 7.4 * len(name) + 30
    d.text(64, 76, 'DATA FOUNDATION · CONTRACT → GATE → AS-OF STORE', size=11, weight=700, ls='0.14em')
    d.sheet(10, 'Release gate and as-of store', 'contract 0.2.0 · t_ingest ≤ 06:00')
    return d


if __name__ == '__main__':
    print(build().save('contract-gate.svg'))
