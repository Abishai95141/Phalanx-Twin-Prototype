"""PHX-ILL-07 · avionics-lru.svg — utility-management electronic unit (BHEEM EU style) in a 3/4 view on its
mounting tray: circular connectors J1–J3, BIT indicator, handle, hold-downs, data plate; view A of the J1 insert.
Facts from the dictionary: BHEEM_EU = utility management, 1553B remote terminal 7 on AV-MUX-2, 40 Hz frame.
Data-plate P/N and S/N are left as engraved blanks (#lru-plate-pn, #lru-plate-sn).  Subject: the BIT indicator."""
import math
from lib import *

WF, HB, DP = 280.0, 236.0, 500.0           # front width, height, depth (local units)
E = (690.0, 704.0)                           # nearest bottom corner (u = WF, v = 0, w = 0) on screen
AX = (-0.906, -0.423)                        # +u  -> screen (front face runs up-left from the near edge)
BX = (0.819 * 0.74, -0.574 * 0.74)           # +v  -> screen (depth, foreshortened)


def iso(u, v, w):
    return (E[0] + (WF - u) * AX[0] + v * BX[0], E[1] + (WF - u) * AX[1] + v * BX[1] - w)


def face(name, off=0.0):
    """affine for face-local (p, q-up) coordinates"""
    if name == 'front':      # p = u, q = w at v = off
        o = iso(0, off, 0)
        return Affine(-AX[0], -AX[1], 0, -1, o[0], o[1])
    if name == 'side':       # p = v, q = w at u = WF + off
        o = iso(WF + off, 0, 0)
        return Affine(BX[0], BX[1], 0, -1, o[0], o[1])
    if name == 'top':        # p = u, q = v at w = HB + off
        o = iso(0, 0, HB + off)
        return Affine(-AX[0], -AX[1], BX[0], BX[1], o[0], o[1])


def text_m(M, p, q):
    a, b, c, d_, e, f = M.m
    x, y = M(p, q)
    return 'matrix(%s %s %s %s %s %s)' % (n(a), n(b), n(-c), n(-d_), n(x), n(y))


def build():
    d = Doc('lru', 'Avionics LRU — utility management EU',
            'Three-quarter view of a utility-management avionics LRU on its tray with circular connectors, BIT '
            'indicator, handle, hold-downs and data plate, plus the J1 insert arrangement.')
    d.std_defs()

    def fpath(M, segs, **kw):
        d.path(segs_d(segs, M), **kw)

    def ftext(M, p, q, s, size=11, mono=True, weight=600, fill=INK, anchor='start', **kw):
        d.text(0, 0, s, size=size, mono=mono, weight=weight, fill=fill, anchor=anchor, transform=text_m(M, p, q),
               **kw)

    MF, MS, MT = face('front'), face('side'), face('top')

    # ------------------------------------------------------------------ tray
    with d.g(id='lru-tray', cls='part'):
        t0, t1, tv0, th = -14.0, WF + 14, -40.0, 14.0
        top = [iso(t0, tv0, 0), iso(t1, tv0, 0), iso(t1, DP + 20, 0), iso(t0, DP + 20, 0)]
        d.path(P(*top, close=True), w=W2, fill=F1)
        frontf = [iso(t0, tv0, 0), iso(t1, tv0, 0), iso(t1, tv0, -th), iso(t0, tv0, -th)]
        d.path(P(*frontf, close=True), w=W1, fill=WHITE, cls='draw')
        sidef = [iso(t1, tv0, 0), iso(t1, DP + 20, 0), iso(t1, DP + 20, -th), iso(t1, tv0, -th)]
        d.path(P(*sidef, close=True), w=W1, fill=F2, cls='draw')
        # hold-down knobs (knurled), on the tray front, engaging the LRU hooks
        for u in (52, WF - 52):
            Mk = face('front', tv0 - 22)
            cx_, cy_ = u, 6
            fpath(Mk, circle_segs(cx_, cy_, 15), w=W1, fill=WHITE)
            fpath(Mk, circle_segs(cx_, cy_, 7), w=W2, fill=F2)
            for i in range(16):
                a = math.radians(i * 22.5)
                fpath(Mk, line_segs((cx_ + 12 * math.cos(a), cy_ + 12 * math.sin(a)),
                                    (cx_ + 15 * math.cos(a), cy_ + 15 * math.sin(a))), w=W3)
            # shank to the hook
            a1, a2 = iso(u - 4, tv0 - 22, 6), iso(u - 4, 0, 6)
            d.line(*a1, *a2, w=W2)

    # ------------------------------------------------------------------ box body
    with d.g(id='lru-body', cls='part'):
        top = [iso(0, 0, HB), iso(WF, 0, HB), iso(WF, DP, HB), iso(0, DP, HB)]
        d.path(P(*top, close=True), w=W1, fill=F1, cls='draw', id='lru-top')
        side = [iso(WF, 0, 0), iso(WF, DP, 0), iso(WF, DP, HB), iso(WF, 0, HB)]
        d.path(P(*side, close=True), w=W1, fill=F2, cls='draw', id='lru-side')
        front = [iso(0, 0, 0), iso(WF, 0, 0), iso(WF, 0, HB), iso(0, 0, HB)]
        d.path(P(*front, close=True), w=W1, fill=WHITE, cls='draw', id='lru-front')
        # top vents
        for r in range(3):
            for c in range(6):
                p0 = 34 + c * 38
                q0 = 250 + r * 64
                fpath(MT, rect_segs(p0, q0, 26, 40, 6), w=W3)
        # side ribs
        for i in range(9):
            p0 = 330 + i * 18
            fpath(MS, line_segs((p0, 20), (p0, HB - 20)), w=W3)
            fpath(MS, line_segs((p0 + 5, 20), (p0 + 5, HB - 20)), w=W3)
        # front-panel bevel
        fpath(MF, rect_segs(8, 8, WF - 16, HB - 16, 6), w=W3)
        # rear connector shadow outline (hidden)
        fpath(MS, line_segs((DP - 8, 10), (DP - 8, HB - 10)), w=W3, dash=DASH_HIDDEN)

    # ------------------------------------------------------------------ front panel details
    CON = [('J1', 72, 96, 36, 13), ('J2', 162, 96, 30, 7), ('J3', 234, 96, 22, 3)]
    with d.g(id='lru-connectors', cls='part'):
        for name, cx_, cy_, r, pins in CON:
            with d.g(id='lru-' + name.lower(), cls='connector'):
                fpath(MF, circle_segs(cx_, cy_, r + 6), w=W2, fill=WHITE)          # flange
                for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    fpath(MF, circle_segs(cx_ + sx * (r + 2), cy_ + sy * (r + 2), 2.2), w=W3)
                fpath(MF, circle_segs(cx_, cy_, r), w=W1, fill=WHITE, cls='draw')  # coupling nut
                for i in range(24):
                    a = math.radians(i * 15)
                    fpath(MF, line_segs((cx_ + (r - 4) * math.cos(a), cy_ + (r - 4) * math.sin(a)),
                                        (cx_ + r * math.cos(a), cy_ + r * math.sin(a))), w=W3)
                ri = r * 0.66
                fpath(MF, circle_segs(cx_, cy_, ri), w=W2, fill=F2)
                fpath(MF, rect_segs(cx_ - 2.5, cy_ + ri - 5, 5, 6), w=W2, fill=WHITE)   # keyway
                if pins >= 13:
                    pts = [(0, 0)] + [(ri * .45 * math.cos(math.radians(a)), ri * .45 * math.sin(math.radians(a)))
                                      for a in range(0, 360, 72)] + \
                          [(ri * .78 * math.cos(math.radians(a + 22)), ri * .78 * math.sin(math.radians(a + 22)))
                           for a in range(0, 360, 51)]
                elif pins == 7:
                    pts = [(0, 0)] + [(ri * .6 * math.cos(math.radians(a)), ri * .6 * math.sin(math.radians(a)))
                                      for a in range(30, 390, 60)]
                else:
                    pts = [(ri * .5 * math.cos(math.radians(a)), ri * .5 * math.sin(math.radians(a)))
                           for a in (90, 210, 330)]
                for px, py in pts:
                    fpath(MF, circle_segs(cx_ + px, cy_ + py, 1.9), w=0, stroke='none', fill=INK)
                ftext(MF, cx_, cy_ - r - 22, name, size=11, anchor='middle', weight=700)
        # handle (protrudes toward the viewer)
        with d.g(id='lru-handle', cls='part'):
            hq = HB - 10
            pts = [iso(46, 0, hq), iso(46, -20, hq), iso(WF - 46, -20, hq), iso(WF - 46, 0, hq)]
            d.path(P(*pts), w=W1 * 2.6, cls='draw')
            d.path(P(*pts), w=W1 * 2.6 - 2.2, stroke=WHITE)
            for u in (46, WF - 46):
                fpath(MF, circle_segs(u, hq, 6), w=W2, fill=WHITE)
        # hold-down hooks at the bottom of the front panel
        with d.g(id='lru-hooks'):
            for u in (52, WF - 52):
                fpath(MF, rect_segs(u - 12, 0, 24, 16, 3), w=W2, fill=F2)
        # BIT indicator (subject) + test button + legend
        with d.g(id='lru-bit', cls='subject'):
            fpath(MF, rect_segs(26, 146, 52, 28, 6), w=W1, stroke=ACC, fill=WHITE)
            fpath(MF, circle_segs(41, 160, 7.5), w=0, stroke='none', fill=ACC, id='lru-bit-led')
            ftext(MF, 53, 156, 'BIT', size=10.5, fill=ACC, weight=700)
        with d.g(id='lru-test'):
            fpath(MF, circle_segs(98, 160, 8), w=W1, fill=WHITE)
            fpath(MF, circle_segs(98, 160, 4.5), w=W2, fill=F2)
            ftext(MF, 112, 156, 'TEST', size=10, fill=INK3)
        ftext(MF, 150, 162, 'BHEEM EU', size=13.5, mono=False, weight=750)
        ftext(MF, 150, 149, 'utility management', size=9.5, fill=INK3, weight=500)

    # ------------------------------------------------------------------ data plate (side face)
    with d.g(id='lru-dataplate', cls='dataplate'):
        p0, q0, w_, h_ = 54.0, 40.0, 250.0, 160.0
        fpath(MS, rect_segs(p0, q0, w_, h_, 8), w=W1, fill=WHITE, cls='draw')
        fpath(MS, rect_segs(p0 + 6, q0 + 6, w_ - 12, h_ - 12, 5), w=W3)
        for cx_, cy_ in ((p0 + 14, q0 + 14), (p0 + w_ - 14, q0 + 14), (p0 + 14, q0 + h_ - 14),
                         (p0 + w_ - 14, q0 + h_ - 14)):
            fpath(MS, circle_segs(cx_, cy_, 3.2), w=W2, fill=F2)
        rows = [('UTILITY MANAGEMENT EU', None, 12, False, 750),
                ('LRU', 'BHEEM_EU', 10.5, True, 600),
                ('BUS', '1553B · AV-MUX-2 · RT 7', 10.5, True, 600),
                ('FRAME', '40 Hz', 10.5, True, 600)]
        y = q0 + h_ - 34
        ftext(MS, p0 + 22, y, rows[0][0], size=12, mono=False, weight=750)
        y -= 26
        for k, v, sz, mono, wt in rows[1:]:
            ftext(MS, p0 + 22, y, k, size=9.5, fill=INK3, weight=500)
            ftext(MS, p0 + 80, y, v, size=10.5, weight=600)
            y -= 20
        for k in ('P/N', 'S/N'):
            ftext(MS, p0 + 22, y, k, size=9.5, fill=INK3, weight=500)
            fpath(MS, line_segs((p0 + 80, y - 3), (p0 + w_ - 26, y - 3)), w=W3,
                  id='lru-plate-' + k.strip('/').lower().replace('/', ''))
            y -= 20

    # ------------------------------------------------------------------ view A: J1 insert arrangement
    with d.g(id='lru-view-a', cls='detail'):
        cx, cy, R = 1210.0, 252.0, 98.0
        d.circle(cx, cy, R, w=W1, fill=WHITE, cls='draw')
        d.circle(cx, cy, R - 12, w=W2)
        d.circle(cx, cy, R * .66, w=W1, fill=F1)
        d.rect(cx - 6, cy - R * .66 - 2, 12, 12, rx=2, w=W2, fill=WHITE)
        for i in range(24):
            a = math.radians(i * 15)
            d.line(cx + (R - 12) * math.cos(a), cy + (R - 12) * math.sin(a), cx + R * math.cos(a),
                   cy + R * math.sin(a), w=W3)
        ri = R * .66
        letters = 'ABCDEFGHJKLMN'
        pts = [(0, 0)] + [(ri * .45 * math.cos(math.radians(a - 90)), ri * .45 * math.sin(math.radians(a - 90)))
                          for a in range(0, 360, 72)] + \
              [(ri * .78 * math.cos(math.radians(a - 90 + 22)), ri * .78 * math.sin(math.radians(a - 90 + 22)))
               for a in range(0, 360, 51)]
        for i, (px, py) in enumerate(pts[:13]):
            d.circle(cx + px, cy + py, 5.2, w=W2, fill=WHITE)
            d.circle(cx + px, cy + py, 1.6, w=0, stroke='none', fill=INK)
            d.text(cx + px + 7, cy + py - 5, letters[i], size=8.5, mono=True, fill=INK3)
        d.centreline(cx - R - 14, cy, cx + R + 14, cy)
        d.centreline(cx, cy - R - 14, cx, cy + R + 14)
        d.text(cx, cy + R + 32, 'VIEW A · J1 insert', size=11, weight=700, ls='0.1em', anchor='middle')
        d.text(cx, cy + R + 48, '13 contacts · keyway at 12 o’clock', size=10.5, mono=True, fill=INK3,
               anchor='middle')
        d.text(cx - R - 30, cy - R + 4, 'A', size=14, weight=700)

    # ------------------------------------------------------------------ callouts + list
    J = {k: MF(cx_, cy_ + r + 4) for k, cx_, cy_, r, _ in CON}
    items = [('1', 'J1 · bus', '1553B AV-MUX-2 · RT 7', MF(72, 96 + 40), (440, 250)),
             ('2', 'J2 · sensor inputs', 'hydraulics · electrical · gear · chute', MF(162, 126), (520, 196)),
             ('3', 'J3 · DC power', '', MF(234, 118), (610, 220)),
             ('4', 'BIT indicator', 'self-test result', MF(30, 168), (330, 330)),
             ('5', 'Data plate', 'LRU · bus · frame · P/N · S/N', MS(250, 186), (1000, 300)),
             ('6', 'Handle', '', iso(WF / 2, -20, HB - 10), (360, 420)),
             ('7', 'Hold-down', 'knurled knob on the tray', iso(52, -62, 6), (330, 640)),
             ('8', 'Mounting tray', '', iso(WF + 14, 300, -7), (1000, 620))]
    with d.g(id='lru-callouts', cls='callouts'):
        for num, name, sub, (tx, ty), (bx, by) in items:
            d.callout(num, bx, by, tx, ty, accent=(num == '4'), id='lru-c' + num)
    # view-A reference
    with d.g(id='lru-view-arrow'):
        ax_, ay_ = MF(72, 96)
        d.path(P((ax_ - 70, ay_ - 30), (ax_ - 30, ay_ - 12)), w=W2)
        d.arrowhead(ax_ - 30, ay_ - 12, math.atan2(18, 40), L=9, half=2.6)
        d.text(ax_ - 84, ay_ - 30, 'A', size=14, weight=700)
    with d.g(id='lru-list', cls='legend'):
        lx, ly = 1110, 446
        d.kicker(lx, ly, 'Parts')
        d.line(lx, ly + 12, 1540, ly + 12, w=W3)
        for i, (num, name, sub, _, _) in enumerate(items):
            y = ly + 40 + i * 36
            d.callout(num, lx + 11, y - 4, accent=(num == '4'))
            d.text(lx + 30, y - 5, name, size=13, weight=650, fill=ACC if num == '4' else INK)
            if sub:
                d.text(lx + 30, y + 9, sub, size=10.5, mono=True, fill=INK3)
    d.text(64, 76, 'UTILITY MANAGEMENT EU · ON ITS TRAY', size=11, weight=700, ls='0.14em')
    d.sheet(7, 'Avionics LRU — BHEEM EU', '1553B RT 7 · 40 Hz frame · BIT')
    return d


if __name__ == '__main__':
    print(build().save('avionics-lru.svg'))
