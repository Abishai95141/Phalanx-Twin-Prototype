"""PHX-ILL-05 · main-gear-tyre.svg — main landing gear leg (viewed from inboard), wheel, brake and tyre; detail C
tyre section with a tread-depth gauge; landings counter 7 / 8 (tyre life 8 landings).
Numbers from the dictionary: main tyre 26 in (0.66 m); MX.TYRE_P main nominal 16.9 bar.  Subject: the tyre."""
import math
from lib import *

GY = 806.0
WX, WY = 400.0, GY - 132.0
RT = 132.0


def build():
    d = Doc('mlg', 'Main landing gear and tyre',
            'Main landing gear leg with oleo strut, torque links, drag brace and wheel; tyre section detail with '
            'a tread-depth gauge; landings counter at 7 of 8.')
    d.std_defs()
    HA, HF = d.hatch(), d.hatch('a')

    # ------------------------------------------------------------------ airframe structure (section)
    with d.g(id='mlg-structure', cls='part'):
        d.path(P((150, 150), (640, 150), (640, 196), (470, 196), (440, 214), (330, 214), (300, 196), (150, 196),
                 close=True), w=W1, fill=HA, cls='draw')
        d.text(160, 140, 'airframe hard points', size=10.5, mono=True, fill=INK3)
    # ground
    with d.g(id='mlg-ground', cls='ground'):
        d.line(110, GY, 700, GY, w=W1, cls='draw')
        d.rect(110, GY, 590, 7, w=0, stroke='none', fill=HA)

    # ------------------------------------------------------------------ wheel, brake, tyre (behind the leg)
    with d.g(id='mlg-wheel', cls='part'):
        with d.g(id='mlg-tyre', cls='subject'):
            d.circle(WX, WY, RT, w=W1, stroke=ACC, fill=WHITE, cls='draw')
            d.path(arc_d(WX, WY, RT, 0, 359.9) + ' ' + arc_d(WX, WY, RT - 11, 359.9, 0, move=True), w=0,
                   stroke='none', fill=HF, fill_rule='evenodd')
            d.circle(WX, WY, RT - 11, w=W2, stroke=ACC)
            d.circle(WX, WY, 102, w=W3, stroke=ACC)
        d.circle(WX, WY, 90, w=W1, fill=F1)
        d.circle(WX, WY, 82, w=W2)
        d.circle(WX, WY, 64, w=W3, dash=DASH_HIDDEN)            # brake pack behind the wheel
        for i in range(10):
            a = math.radians(i * 36)
            d.circle(WX + 52 * math.cos(a), WY + 52 * math.sin(a), 4.2, w=W2, fill=WHITE)
        d.circle(WX, WY, 30, w=W1, fill=WHITE)
    # ------------------------------------------------------------------ leg (in front)
    SX = WX + 6
    with d.g(id='mlg-leg', cls='part'):
        # retraction actuator (phantom: alternate position / behind)
        d.path(P((560, 214), (SX + 30, 360)), w=W2, dash=DASH_PHANTOM, id='mlg-retraction')
        d.circle(560, 214, 6, w=W2, fill=WHITE)
        # drag brace with knee
        with d.g(id='mlg-drag-brace'):
            d.path(P((214, 214), (262, 330)), w=W1 * 2.2, cls='draw')
            d.path(P((262, 330), (SX - 32, 400)), w=W1 * 2.2, cls='draw')
            for p_ in ((214, 214), (262, 330), (SX - 32, 400)):
                d.circle(*p_, 6.5, w=W1, fill=WHITE)
        # trunnion block + outer cylinder
        with d.g(id='mlg-strut', cls='strut'):
            d.path(P((SX - 44, 214), (SX + 44, 214), (SX + 36, 268), (SX + 32, 300), (SX - 32, 300), (SX - 36, 268),
                     close=True), w=W1, fill=WHITE, cls='draw')
            d.circle(SX, 240, 15, w=W1, fill=WHITE, id='mlg-trunnion')
            d.circle(SX, 240, 6, w=W2)
            d.rect(SX - 32, 300, 64, 236, rx=4, w=W1, fill=WHITE, cls='draw')
            d.line(SX - 32, 330, SX + 32, 330, w=W3)
            d.line(SX - 32, 510, SX + 32, 510, w=W3)
            d.rect(SX - 38, 392, 8, 18, w=W2, fill=WHITE)            # drag-brace lug
            d.text(SX, 430, 'oleo', size=10, mono=True, fill=INK3, anchor='middle')
            # inner sliding tube
            d.rect(SX - 21, 536, 42, 104, w=W1, fill=F1, cls='draw')
            d.line(SX - 21, 548, SX + 21, 548, w=W3)
            # axle fork
            d.path(P((SX - 26, 640), (SX + 26, 640), (SX + 18, WY - 10), (SX - 18, WY - 10), close=True), w=W1,
                   fill=WHITE)
            d.circle(WX, WY, 17, w=W1, fill=WHITE, id='mlg-axle')
            d.circle(WX, WY, 7, w=W2)
        # torque links
        with d.g(id='mlg-torque-links'):
            a, b, c = (SX + 32, 524), (SX + 86, 580), (SX + 26, 632)
            d.path(P(a, b), w=W1 * 2, cls='draw')
            d.path(P(b, c), w=W1 * 2, cls='draw')
            for p_ in (a, b, c):
                d.circle(*p_, 5.5, w=W1, fill=WHITE)
        d.centreline(SX, 200, SX, WY + 18)

    # ------------------------------------------------------------------ diameter dimension + detail circle
    d.dim((WX, WY - RT), (WX, GY), -(RT + 44), 'Ø 0.66 m · 26 in', id='mlg-dim-dia', size=12)
    with d.g(id='mlg-detail-mark', cls='detail-mark'):
        ang = math.radians(-35)
        cx, cy = WX + (RT - 4) * math.cos(ang), WY + (RT - 4) * math.sin(ang)
        d.circle(cx, cy, 30, w=W2, dash='5 3')
        d.path(P((cx + 22, cy - 20), (722, 330)), w=W3)
        d.text(cx - 6, cy - 36, 'C', size=13, weight=700)

    # ------------------------------------------------------------------ detail C: tyre section + tread gauge
    with d.g(id='mlg-detail-c', cls='detail'):
        ox, oy = 924.0, 214.0          # crown centre (tread surface)
        hw = 170.0
        grooves = [-110, -40, 40, 110]
        gw, gd = 16.0, 30.0
        # tyre section (subject, accent hatch) — outer contour with grooves
        top = [(ox - hw, oy + 26)]
        top += [(ox - hw + 10, oy + 4), (ox - hw + 30, oy)]
        for gx in grooves:
            top += [(ox + gx - gw / 2, oy), (ox + gx - gw / 2 + 2, oy + gd), (ox + gx + gw / 2 - 2, oy + gd),
                    (ox + gx + gw / 2, oy)]
        top += [(ox + hw - 30, oy), (ox + hw - 10, oy + 4), (ox + hw, oy + 26)]
        outer = 'M%s %s ' % (n(ox - hw + 6), n(oy + 290)) + \
                'C%s %s %s %s %s %s ' % (n(ox - hw - 24), n(oy + 200), n(ox - hw - 16), n(oy + 90), n(ox - hw), n(oy + 26)) + \
                ' '.join('L%s %s' % (n(x), n(y)) for x, y in top[1:]) + \
                ' C%s %s %s %s %s %s' % (n(ox + hw + 16), n(oy + 90), n(ox + hw + 24), n(oy + 200), n(ox + hw - 6), n(oy + 290)) + \
                ' L%s %s C%s %s %s %s %s %s L%s %s C%s %s %s %s %s %s Z' % (
                    n(ox + hw - 30), n(oy + 290), n(ox + hw - 6), n(oy + 200), n(ox + hw - 8), n(oy + 110),
                    n(ox + hw - 40), n(oy + 58), n(ox - hw + 40), n(oy + 58), n(ox - hw + 8), n(oy + 110),
                    n(ox - hw + 6), n(oy + 200), n(ox - hw + 30), n(oy + 290))
        d.path(outer, w=W1, stroke=ACC, fill=HF, id='mlg-tyre-section', cls='draw subject')
        # carcass plies
        for o in (10, 18):
            d.path('M%s %s C%s %s %s %s %s %s L%s %s C%s %s %s %s %s %s' % (
                n(ox - hw + 18 + o * .2), n(oy + 286), n(ox - hw - 2 + o), n(oy + 200), n(ox - hw + o), n(oy + 110),
                n(ox - hw + 40 + o), n(oy + 50 - o * .2), n(ox + hw - 40 - o), n(oy + 50 - o * .2), n(ox + hw - o),
                n(oy + 110), n(ox + hw + 2 - o), n(oy + 200), n(ox + hw - 18 - o * .2), n(oy + 286)), w=W3,
                stroke=ACC)
        # rim (section)
        rim = [(ox - hw - 6, oy + 268), (ox - hw + 4, oy + 268), (ox - hw + 18, oy + 300), (ox - 60, oy + 304),
               (ox - 60, oy + 330), (ox + 60, oy + 330), (ox + 60, oy + 304), (ox + hw - 18, oy + 300),
               (ox + hw - 4, oy + 268), (ox + hw + 6, oy + 268), (ox + hw + 6, oy + 314), (ox + 70, oy + 318),
               (ox + 70, oy + 344), (ox - 70, oy + 344), (ox - 70, oy + 318), (ox - hw - 6, oy + 314)]
        d.path(P(*rim, close=True), w=W1, fill=HA, id='mlg-rim-section')
        d.centreline(ox, oy - 150, ox, oy + 360)
        # wear limit + tread-depth dimension at the right groove
        gx = ox + grooves[2]
        wl = oy + gd - 7
        d.line(ox - hw + 24, wl, ox + hw - 24, wl, w=W2, dash='5 3', id='mlg-wear-limit')
        d.line(ox - hw - 8, wl, ox - hw + 24, wl, w=W3)
        d.text(ox - hw - 12, wl + 4, 'wear limit', size=11, mono=True, fill=INK3, anchor='end')
        with d.g(id='mlg-tread-dim', cls='dim'):
            xd = ox + hw + 34
            d.line(ox + hw - 26, oy, xd + 6, oy, w=W3)
            d.line(ox + grooves[3] + gw / 2 - 2, oy + gd, xd + 6, oy + gd, w=W3)
            d.line(xd, oy - 22, xd, oy, w=W3)
            d.line(xd, oy + gd, xd, oy + gd + 22, w=W3)
            d.arrowhead(xd, oy, math.pi / 2, L=7, half=1.7)
            d.arrowhead(xd, oy + gd, -math.pi / 2, L=7, half=1.7)
            d.text(xd + 8, oy + gd / 2 + 4, 'tread depth', size=12, mono=True, weight=600)
        # tread-depth gauge in the second groove
        with d.g(id='mlg-gauge', cls='gauge'):
            gx = ox + grooves[1]
            d.rect(gx - 46, oy - 12, 92, 12, rx=2, w=W1, fill=WHITE)                  # foot / bridge
            d.rect(gx - 15, oy - 132, 30, 120, rx=4, w=W1, fill=WHITE, cls='draw')   # barrel
            d.line(gx, oy, gx, oy + gd - 1, w=W1 * 1.6)                                # probe in the groove
            d.circle(gx, oy + gd - 1, 1.8, w=0, stroke='none', fill=INK)
            for i in range(11):
                y = oy - 120 + i * 9
                d.line(gx + 15, y, gx + (25 if i % 5 == 0 else 21), y, w=W3)
            d.path(P((gx - 15, oy - 66), (gx - 26, oy - 60), (gx - 15, oy - 54)), w=W2, fill=WHITE)
            d.rect(gx - 9, oy - 154, 18, 22, rx=3, w=W2, fill=F1)
            d.text(gx - 32, oy - 86, 'tread-depth', size=11, mono=True, fill=INK3, anchor='end')
            d.text(gx - 32, oy - 72, 'gauge', size=11, mono=True, fill=INK3, anchor='end')
        d.text(ox, oy + 384, 'DETAIL C', size=12, weight=700, ls='0.14em', anchor='middle')
        d.text(ox, oy + 402, 'tyre section on the rim · enlarged', size=10.5, mono=True, fill=INK3, anchor='middle')

    # ------------------------------------------------------------------ landings counter
    with d.g(id='mlg-counter', cls='counter'):
        x0, y0 = 1268, 120
        d.kicker(x0, y0, 'Landings · this tyre')
        d.rect(x0, y0 + 18, 96, 120, rx=10, w=W1, fill=WHITE)
        d.text(x0 + 48, y0 + 112, '7', size=88, mono=True, weight=600, anchor='middle', id='mlg-count-used')
        d.text(x0 + 124, y0 + 106, '/', size=56, mono=True, weight=300, anchor='middle', fill=INK4)
        d.rect(x0 + 152, y0 + 18, 96, 120, rx=10, w=W2, fill=F1)
        d.text(x0 + 200, y0 + 112, '8', size=88, mono=True, weight=600, anchor='middle', fill=INK3,
               id='mlg-count-life')
        for i in range(8):
            cx = x0 + i * 31
            if i < 7:
                d.rect(cx, y0 + 160, 24, 24, rx=4, w=W1, fill=F2, id='mlg-cell-%d' % (i + 1))
                d.path(P((cx + 7, y0 + 172), (cx + 11, y0 + 176), (cx + 18, y0 + 167)), w=W2)
            else:
                d.rect(cx, y0 + 160, 24, 24, rx=4, w=W1, dash='3 2.5', fill=WHITE, id='mlg-cell-8')
        d.text(x0, y0 + 212, 'USAGE.LANDINGS · tyre life 8', size=11, mono=True, fill=INK3)
        d.text(x0, y0 + 230, 'one landing left before change', size=11, mono=True, fill=INK3)
        d.line(x0, y0 + 252, 1540, y0 + 252, w=W3)
        d.text(x0, y0 + 276, 'MX.TYRE_P', size=11, mono=True, weight=600)
        d.text(x0 + 82, y0 + 276, 'main 16.9 bar nominal', size=11, mono=True, fill=INK3)

    # ------------------------------------------------------------------ callouts + list
    items = [('1', 'Trunnion', 'pivot to the airframe', (SX + 10, 232), (500, 262)),
             ('2', 'Oleo strut', 'shock absorber', (SX + 32, 450), (520, 450)),
             ('3', 'Torque links', '', (SX + 62, 558), (548, 506)),
             ('4', 'Drag brace', 'with lock knee', (240, 274), (180, 300)),
             ('5', 'Retraction actuator', 'shown phantom', (500, 252), (620, 300)),
             ('6', 'Wheel + brake', 'multi-disc, behind', (WX - 50, WY - 18), (290, 584)),
             ('7', 'Tyre', 'main · 26 in', (WX + RT * .7, WY + RT * .72), (600, 760))]
    with d.g(id='mlg-callouts', cls='callouts'):
        for num, name, sub, (tx, ty), (bx, by) in items:
            d.callout(num, bx, by, tx, ty, accent=(num == '7'), id='mlg-c' + num)
    with d.g(id='mlg-list', cls='legend'):
        lx, ly = 1268, 470
        d.kicker(lx, ly, 'Parts')
        d.line(lx, ly + 12, 1540, ly + 12, w=W3)
        for i, (num, name, sub, _, _) in enumerate(items):
            y = ly + 40 + i * 38
            d.callout(num, lx + 11, y - 4, accent=(num == '7'))
            d.text(lx + 30, y - 5, name, size=13.5, weight=650, fill=ACC if num == '7' else INK)
            if sub:
                d.text(lx + 30, y + 9, sub, size=10.5, mono=True, fill=INK3)
    d.text(110, 76, 'LEFT MAIN GEAR · VIEWED FROM INBOARD', size=11, weight=700, ls='0.14em')
    d.sheet(5, 'Main landing gear and tyre', 'tread depth · landings 7 / 8')
    return d


if __name__ == '__main__':
    print(build().save('main-gear-tyre.svg'))
