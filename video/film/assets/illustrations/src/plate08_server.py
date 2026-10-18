"""PHX-ILL-08 · station-server.svg — compact, unbranded desktop AI appliance on a desk.  Power is plugged in, the
network port is empty: the unplugged RJ45 plug + air-gap bracket + shield are the subject (accent).
Four empty callout slots (#srv-slot-model / -runtime / -memory / -exec, each with an empty *-value group) are
left for the film to fill with runtime stats."""
import math
from lib import *


def build():
    d = Doc('srv', 'Station server — air-gapped appliance',
            'A compact desktop AI appliance on a desk with its network port deliberately empty (air gap) and four '
            'empty callout slots for runtime statistics.')
    d.std_defs()
    I = Iso(600.0, 470.0)

    def fpath(M, segs, **kw):
        d.path(segs_d(segs, M), **kw)

    # ------------------------------------------------------------------ desk
    with d.g(id='srv-desk', cls='desk'):
        u0, u1, v0, v1, th = -230.0, 470.0, -120.0, 370.0, 22.0
        top = [I(u0, v0, 0), I(u1, v0, 0), I(u1, v1, 0), I(u0, v1, 0)]
        d.path(P(*top, close=True), w=W2, fill=F1, cls='draw', id='srv-desk-top')
        d.path(P(I(u0, v0, 0), I(u1, v0, 0), I(u1, v0, -th), I(u0, v0, -th), close=True), w=W1, fill=WHITE,
               cls='draw')
        d.path(P(I(u1, v0, 0), I(u1, v1, 0), I(u1, v1, -th), I(u1, v0, -th), close=True), w=W1, fill=F2,
               cls='draw')
        # wood-grain-free: faint construction grid on the desk top (blueprint feel)
        for i in range(1, 6):
            v = v0 + (v1 - v0) * i / 6
            d.path(P(I(u0 + 10, v, 0), I(u1 - 10, v, 0)), w=W3, stroke=INK5, dash='1.5 5')

    # ------------------------------------------------------------------ appliance
    A0, A1, B0, B1, H = 0.0, 236.0, 0.0, 236.0, 84.0
    MF, MS, MT = I.front(B0), I.side(A1), I.top(H)
    with d.g(id='srv-appliance', cls='part'):
        # feet / plinth shadow line
        d.path(P(I(A0 + 6, B0 + 6, 0), I(A1 - 6, B0 + 6, 0), I(A1 - 6, B1 - 6, 0)), w=W3)
        I.box(d, A0, A1, B0, B1, 6, H, fills=(WHITE, F2, F1), ids=('srv-front', 'srv-side', 'srv-top'))
        # plinth
        d.path(P(I(A0 + 6, B0 + 6, 6), I(A0 + 6, B0 + 6, 0), I(A1 - 6, B0 + 6, 0), I(A1 - 6, B0 + 6, 6)), w=W2)
        d.path(P(I(A1 - 6, B0 + 6, 0), I(A1 - 6, B1 - 6, 0), I(A1 - 6, B1 - 6, 6)), w=W2)
        # top: inset bevel + vent grille
        fpath(MT, rect_segs(12, 12, A1 - 24, B1 - 24, 18), w=W2)
        for r in range(9):
            for c in range(9):
                fpath(MT, circle_segs(50 + c * 17, 50 + r * 17, 2.6), w=0, stroke='none', fill=INK4)
        # front: vent band, power button, status LED
        fpath(MF, rect_segs(16, 30, A1 - 32, 36, 6), w=W2)
        for r in range(3):
            for c in range(22):
                fpath(MF, circle_segs(26 + c * 9.2, 39 + r * 9, 1.6), w=0, stroke='none', fill=INK4)
        fpath(MF, circle_segs(A1 - 26, 17, 6.5), w=W1, fill=WHITE, id='srv-power-button')
        fpath(MF, line_segs((A1 - 26, 13), (A1 - 26, 18)), w=W2)
        fpath(MF, circle_segs(A1 - 48, 17, 2.6), w=0, stroke='none', fill=INK, id='srv-status-led')
        # side: ports (power inlet in use, LAN empty, 2 x USB-C)
        with d.g(id='srv-ports'):
            fpath(MS, rect_segs(30, 22, 30, 26, 2), w=W1, fill=WHITE, id='srv-port-lan')
            fpath(MS, line_segs((34, 26), (34, 42), (56, 42), (56, 26)), w=W3)
            fpath(MS, rect_segs(40, 44, 10, 4, 1), w=W3)
            for p0 in (82, 102):
                fpath(MS, rect_segs(p0, 30, 14, 8, 4), w=W1, fill=WHITE)
            fpath(MS, rect_segs(130, 16, 14, 52, 3), w=W3)
            for q in range(22, 66, 6):
                fpath(MS, line_segs((133, q), (141, q)), w=W3)
            fpath(MS, rect_segs(176, 22, 34, 24, 4), w=W1, fill=WHITE, id='srv-port-power')

    # ------------------------------------------------------------------ power cord (plugged in)
    with d.g(id='srv-power-cord', cls='cable'):
        a = I(A1 + 6, 193, 34)
        b = I(A1 + 30, 200, 2)
        c = I(A1 + 30, 290, 0)
        e = I(A1 + 40, 366, 0)
        d.path(P(I(A1, 193, 34), a), w=W1 * 2.4)
        d.path('M%s %s C%s %s %s %s %s %s S%s %s %s %s' % (*a, *b, *c, *(c[0] - 10, c[1] + 4), *e, *e), w=W1 * 1.6,
               cls='draw')
        d.text(e[0] + 8, e[1] - 4, 'power', size=10.5, mono=True, fill=INK3)

    # ------------------------------------------------------------------ air gap (subject)
    with d.g(id='srv-airgap', cls='subject'):
        port = I(A1, 45, 35)
        plug_tip = I(A1 + 74, 54, 8)
        plug_back = I(A1 + 110, 64, 8)
        # unplugged RJ45 plug lying on the desk, cable trailing away
        with d.g(id='srv-plug'):
            M = Affine(plug_back[0] - plug_tip[0], plug_back[1] - plug_tip[1], 0, -1, *plug_tip)
            L = math.hypot(plug_back[0] - plug_tip[0], plug_back[1] - plug_tip[1])
            ux, uy = (plug_back[0] - plug_tip[0]) / L, (plug_back[1] - plug_tip[1]) / L
            nx, ny = -uy, ux
            pts = [(plug_tip[0] + nx * 9, plug_tip[1] + ny * 9 - 6), (plug_back[0] + nx * 9, plug_back[1] + ny * 9 - 6),
                   (plug_back[0] - nx * 9, plug_back[1] - ny * 9 - 6), (plug_tip[0] - nx * 9, plug_tip[1] - ny * 9 - 6)]
            d.path(P(*pts, close=True), w=W1, fill=WHITE, cls='draw')
            d.path(P(*[(x, y - 8) for x, y in pts[:2]]), w=W2)
            for t in (0.15, 0.3):
                x, y = plug_tip[0] + ux * L * t, plug_tip[1] + uy * L * t
                d.line(x + nx * 9, y + ny * 9 - 6, x - nx * 9, y - ny * 9 - 6, w=W3)
            cab0 = (plug_back[0] + ux * 6, plug_back[1] + uy * 6 - 6)
            cab1 = I(A1 + 170, 110, 0)
            cab2 = I(A1 + 234, 190, 0)
            d.path('M%s %s C%s %s %s %s %s %s' % (*cab0, *(cab0[0] + 60, cab0[1] + 30), *(cab1[0], cab1[1] + 20),
                                                  *cab2), w=W1 * 1.6, cls='draw', id='srv-lan-cable')
            d.text(cab2[0] + 10, cab2[1] + 22, 'network cable · not connected', size=10.5, mono=True, fill=INK3)
        # gap marker between the empty port and the plug tip
        g0 = I(A1 + 8, 46, 30)
        g1 = I(A1 + 64, 54, 14)
        ang = math.atan2(g1[1] - g0[1], g1[0] - g0[0])
        d.line(*g0, *g1, w=W2, stroke=ACC, id='srv-gap')
        d.arrowhead(*g0, ang + math.pi, L=7, half=2, fill=ACC)
        d.arrowhead(*g1, ang, L=7, half=2, fill=ACC)
        for gx, gy in (g0, g1):
            d.line(gx - 7 * math.sin(ang) * -1, gy - 7 * math.cos(ang), gx + 7 * math.sin(ang) * -1, gy + 7 * math.cos(ang),
                   w=W1, stroke=ACC)
        # shield + lock glyph (icon geometry from shell.js, scaled)
        sx, sy, k = 1090.0, 640.0, 3.0
        shield = 'M12 3l7 3v5.4c0 4.3-2.9 7.7-7 9.1-4.1-1.4-7-4.8-7-9.1V6z'
        d.add('<path id="srv-shield" class="draw" d="%s" transform="translate(%s %s) scale(%s)" fill="#FFFFFF" '
              'stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>' % (
                  shield, n(sx), n(sy), n(k), ACC, n(1.7 / k * 1.1)))
        d.add('<path d="M9 11.5h6v5H9z M10.2 11.5V10a1.8 1.8 0 0 1 3.6 0v1.5" transform="translate(%s %s) scale(%s)" '
              'fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>' % (
                  n(sx), n(sy), n(k), ACC, n(1.7 / k * 1.1)))
        cx_, cy_ = sx + 30, sy + 6
        mid = ((g0[0] + g1[0]) / 2, (g0[1] + g1[1]) / 2)
        d.path(P((cx_, cy_), (mid[0], mid[1] + 14)), w=W2, stroke=ACC)
        d.circle(mid[0], mid[1] + 14, 2.2, w=0, stroke='none', fill=ACC)
        d.text(sx + 84, sy + 28, 'Air gap', size=18, weight=700, fill=ACC)
        d.text(sx + 84, sy + 48, 'no network port in use', size=11, mono=True, fill=INK3)
        d.text(sx + 84, sy + 64, 'all services run locally', size=11, mono=True, fill=INK3)

    # ------------------------------------------------------------------ runtime callout slots (empty)
    slots = [('model', 'Model', (90, 130), MT(118, 150)),
             ('runtime', 'Runtime', (90, 262), MF(70, 50)),
             ('memory', 'Memory', (1230, 130), MT(196, 70)),
             ('exec', 'Execution', (1230, 262), MS(150, 70))]
    with d.g(id='srv-slots', cls='slots'):
        for key, label, (x, y), (tx, ty) in slots:
            with d.g(id='srv-slot-' + key, cls='slot', data_slot=key):
                w_, h_ = 280.0, 82.0
                d.rect(x, y, w_, h_, rx=12, w=W2, fill=WHITE, cls='draw')
                d.kicker(x + 18, y + 26, label, size=10.5)
                d.line(x + 18, y + 62, x + w_ - 18, y + 62, w=W3, stroke=INK5, dash='2 3')
                d.add('<g id="srv-slot-%s-value" class="slot-value" transform="translate(%s %s)"></g>' % (
                    key, n(x + 18), n(y + 56)))
                # leader from the nearest slot edge to the appliance
                sxe = x + w_ if x < 600 else x
                d.path(P((sxe, y + h_ / 2), (tx, ty)), w=W3, cls='leader')
                d.circle(tx, ty, 2.2, w=0, stroke='none', fill=INK)
                d.circle(sxe, y + h_ / 2, 2.2, w=W2, fill=WHITE)

    d.text(64, 76, 'STATION SERVER · ON THE ENGINEERING DESK', size=11, weight=700, ls='0.14em')
    d.text(64, 94, 'one appliance runs the twin, the engines and the assistant', size=11, mono=True, fill=INK3)
    d.sheet(8, 'Station server — air-gapped', 'compact appliance · runtime slots empty')
    return d


if __name__ == '__main__':
    print(build().save('station-server.svg'))
