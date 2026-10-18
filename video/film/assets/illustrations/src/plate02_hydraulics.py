"""PHX-ILL-02 · hydraulic-system.svg — two independent 280 bar systems (SYS1 / SYS2), ISO-1219-style.
Subject (accent): the pressure-indication path  transducer + pressure switch -> harness -> BHEEM EU -> 1553 ->
CWS caution HYD-101.  Channel ids are the dictionary's (HYD.SYS1.P, HYD.SYS1.LP, HYD.SYS1.T, HYD.SYS1.LEVEL,
HYD.FILTER_DP); 280 bar is the dictionary's nominal limit."""
import math
from lib import *


def build():
    d = Doc('hyd', 'Hydraulic systems — SYS1 / SYS2',
            'Schematic of two independent engine-driven hydraulic systems with reservoirs, filters, '
            'accumulators, actuators and the pressure-indication path to the BHEEM EU.')
    d.std_defs()

    def junction(x, y, col=INK):
        d.circle(x, y, 2.6, w=0, stroke='none', fill=col, cls='junction')

    def pump(cx, cy, pid, label, out='up'):
        with d.g(id=pid, cls='pump'):
            d.circle(cx, cy, 22, w=W1, fill=WHITE, cls='draw')
            # outlet triangle (points to the pressure port)
            t = -1 if out == 'up' else 1
            d.path(P((cx, cy + t * 20), (cx - 6.5, cy + t * 9), (cx + 6.5, cy + t * 9), close=True), w=0,
                   stroke='none', fill=INK)
            # variable displacement arrow
            d.line(cx - 17, cy + 17, cx + 15, cy - 15, w=W2)
            d.arrowhead(cx + 18, cy - 18, math.atan2(-1, 1), L=7, half=2.2)
            d.text(cx - 28, cy - 12 if out == 'up' else cy + 24, label, size=12, weight=650, anchor='end')

    def filt(cx, cy, fid, dp=True, vertical=False):
        with d.g(id=fid, cls='filter'):
            s = 13
            d.path(P((cx - s, cy), (cx, cy - s), (cx + s, cy), (cx, cy + s), close=True), w=W1, fill=WHITE,
                   cls='draw')
            if vertical:
                d.line(cx - s + 3, cy, cx + s - 3, cy, w=W3, dash='2 2')
            else:
                d.line(cx, cy - s + 3, cx, cy + s - 3, w=W3, dash='2 2')

    def check(cx, cy, cid, flow=1):
        """ISO check valve: ball in a V seat, free flow left -> right"""
        with d.g(id=cid, cls='check-valve'):
            d.rect(cx - 12, cy - 9, 24, 18, w=0, stroke='none', fill=WHITE)
            d.path(P((cx - 2, cy - 8), (cx - 10, cy), (cx - 2, cy + 8)), w=W1)
            d.circle(cx + 2, cy, 5.5, w=W1, fill=WHITE)

    def accumulator(cx, top, h, cid, down=True):
        with d.g(id=cid, cls='accumulator'):
            w = 30
            y0 = top
            d.rect(cx - w / 2, y0, w, h, rx=w / 2, w=W1, fill=WHITE, cls='draw')
            ym = y0 + h * (0.42 if down else 0.58)
            d.path('M%s %s Q%s %s %s %s' % (n(cx - w / 2 + 1), n(ym), n(cx), n(ym + (6 if down else -6)),
                                             n(cx + w / 2 - 1), n(ym)), w=W2)
            gas_y = y0 + h * (0.78 if down else 0.22)
            d.path(P((cx, gas_y - 6), (cx - 5, gas_y + 3), (cx + 5, gas_y + 3), close=True), w=0, stroke='none',
                   fill=INK)

    def actuator(cx, top, aid, label, sub=None, tandem=False, motor=False, label_y=None):
        with d.g(id=aid, cls='actuator'):
            if motor:
                d.circle(cx, top + 34, 17, w=W1, fill=WHITE, cls='draw')
                d.path(P((cx, top + 21), (cx - 6, top + 31), (cx + 6, top + 31), close=True), w=0, stroke='none',
                       fill=INK)
                d.line(cx + 17, top + 34, cx + 30, top + 34, w=W2)
                d.line(cx + 17, top + 37, cx + 30, top + 37, w=W2)
                ly = top + 74
            else:
                L = 128 if tandem else 82
                d.rect(cx - 14, top, 28, L, w=W1, fill=WHITE, cls='draw')
                if tandem:
                    d.rect(cx - 14, top + L / 2 - 2.5, 28, 5, w=0, stroke='none', fill=INK)
                    for py in (top + L * .30, top + L * .80):
                        d.rect(cx - 12, py - 3, 24, 6, w=W2, fill=F2)
                    d.path(P((cx - 2.5, top + L * .30), (cx - 2.5, top + L + 22)) + ' ' +
                           P((cx + 2.5, top + L * .30), (cx + 2.5, top + L + 22)), w=W2)
                else:
                    py = top + L * .40
                    d.rect(cx - 12, py - 3, 24, 6, w=W2, fill=F2)
                    d.path(P((cx - 2.5, py), (cx - 2.5, top + L + 22)) + ' ' + P((cx + 2.5, py), (cx + 2.5, top + L + 22)),
                           w=W2)
                d.circle(cx, top + L + 26, 4, w=W2, fill=WHITE)
                ly = top + L + 50
            ly = label_y or ly
            d.text(cx, ly, label, size=12, weight=650, anchor='middle')
            if sub:
                d.text(cx, ly + 14, sub, size=10, mono=True, fill=INK3, anchor='middle')

    def servo(cx, cy, sid, vertical=False):
        with d.g(id=sid, cls='servo-valve'):
            if vertical:
                d.rect(cx - 9, cy - 21, 18, 42, w=W2, fill=WHITE)
                d.line(cx - 9, cy - 7, cx + 9, cy - 7, w=W3)
                d.line(cx - 9, cy + 7, cx + 9, cy + 7, w=W3)
            else:
                d.rect(cx - 21, cy - 9, 42, 18, w=W2, fill=WHITE)
                d.line(cx - 7, cy - 9, cx - 7, cy + 9, w=W3)
                d.line(cx + 7, cy - 9, cx + 7, cy + 9, w=W3)
                d.path(P((cx - 4, cy + 5), (cx + 4, cy - 5)), w=W3)
                d.arrowhead(cx + 4.5, cy - 5.5, math.atan2(-10, 8), L=4, half=1.4)

    def tag(x, y, text, anchor='start', id=None):
        """blue signal tag: wire continues to the BHEEM EU"""
        w = 7.0 * len(text) + 14
        x0 = x if anchor == 'start' else x - w
        with d.g(id=id, cls='signal-tag'):
            d.rect(x0, y - 9, w, 18, rx=9, w=W2, stroke=BLUE, fill=WHITE)
            d.text(x0 + w / 2, y + 3.6, text, size=10, mono=True, fill=BLUE, anchor='middle')

    X_END = 1540
    FCS = [(1010, 'Elevon', 'LOB'), (1090, 'Elevon', 'LIB'), (1170, 'Elevon', 'RIB'), (1250, 'Elevon', 'ROB'),
           (1330, 'Rudder', '')]

    for sysno, P_, R_, sg in ((1, 236, 186, 1), (2, 656, 706, -1)):
        pfx = 'hyd-sys%d' % sysno
        with d.g(id=pfx, cls='system'):
            # ------------------------------------------------ reservoir + suction
            ry0 = 146 if sysno == 1 else 662
            with d.g(id=pfx + '-reservoir', cls='reservoir'):
                d.rect(78, ry0, 100, 92, rx=10, w=W1, fill=WHITE, cls='draw')
                lvl = ry0 + 36 if sysno == 1 else ry0 + 36
                d.rect(80, lvl, 96, ry0 + 90 - lvl, rx=0, w=0, stroke='none', fill=F2)
                d.line(80, lvl, 176, lvl, w=W2)
                d.path(P((88, lvl - 8), (94, lvl - 2), (100, lvl - 8)), w=W3)
                d.text(128, ry0 + 22, 'Reservoir %d' % sysno, size=12, weight=650, anchor='middle')
                # bootstrap / pressurised marker
                d.line(128, ry0 - 10, 128, ry0, w=W2)
                d.line(120, ry0 - 10, 136, ry0 - 10, w=W2)
            # level sensor tag (wire continues to the BHEEM EU)
            ty_ = ry0 + 70 if sysno == 1 else ry0 + 18
            d.circle(178, ty_, 2.2, w=0, stroke='none', fill=BLUE)
            d.line(178, ty_, 196, ty_, w=W2, stroke=BLUE)
            tag(196, ty_, 'LEVEL', id=pfx + '-tag-level')
            # suction line
            suc_y = 336 if sysno == 1 else 576
            sy0 = ry0 + 92 if sysno == 1 else ry0
            d.path(P((128, sy0), (128, suc_y), (278, suc_y)), w=W2, cls='draw line-suction', id=pfx + '-suction')
            d.arrowhead(214, suc_y, 0, L=8, half=2.6)
            # ------------------------------------------------ pump (engine-driven, on the AMAGB)
            pump(300, suc_y, pfx + '-pump', 'EDP %d' % sysno, out='up' if sysno == 1 else 'down')
            d.path(P((300, suc_y - 22 * sg), (300, P_)), w=W1, cls='draw line-pressure')
            # case drain
            cdx = 336
            d.path(P((314, suc_y - 16 * sg), (cdx, suc_y - 36 * sg), (cdx, R_)), w=W3, dash='4 3',
                   cls='line-drain')
            junction(cdx, R_)
            # ------------------------------------------------ pressure rail
            d.path(P((300, P_), (X_END, P_)), w=W1, cls='draw line-pressure', id=pfx + '-pressure')
            d.path(P((X_END, R_), (178, R_)), w=W2, cls='draw line-return', id=pfx + '-return')
            for ax in (720, 1420):
                d.arrowhead(ax, P_, 0, L=9, half=3)
            for ax in (690, 1400):
                d.arrowhead(ax, R_, math.pi, L=8, half=2.6)
            d.text(X_END - 2, P_ - 7 * sg - (0 if sg > 0 else -10), 'P · 280 bar', size=10.5, mono=True,
                   fill=INK3, anchor='end', halo=True)
            d.text(X_END - 2, R_ - 7 * sg - (0 if sg > 0 else -10), 'R', size=10.5, mono=True, fill=INK3,
                   anchor='end', halo=True)
            # filter with clog (dP) indicator
            filt(384, P_, pfx + '-filter')
            with d.g(id=pfx + '-filter-dp', cls='dp-indicator'):
                yb = P_ - 13 * sg
                d.line(384, yb, 384, yb - 8 * sg, w=W2)
                by = yb - 8 * sg - (10 if sg > 0 else 0)
                d.rect(377, by, 14, 10, rx=2, w=W2, fill=WHITE)
                d.line(380, by + 5, 388, by + 5, w=W3)
                d.text(372, by + 8, 'ΔP', size=10, mono=True, weight=600, anchor='end')
                d.line(391, by + 5, 404, by + 5, w=W2, stroke=BLUE)
            tag(404, by + 5, 'FILTER_DP', id=pfx + '-tag-dp')
            # check valve
            check(444, P_, pfx + '-check')
            # accumulator (hangs off the rail, away from the return line)
            junction(500, P_)
            acc_top = P_ + 22 if sysno == 1 else P_ - 22 - 76
            d.line(500, P_, 500, P_ + 22 * sg, w=W1)
            accumulator(500, acc_top, 76, pfx + '-accumulator', down=(sysno == 1))
            d.text(478, acc_top + 36, 'Accumulator', size=11.5, weight=650, anchor='end')
            d.text(478, acc_top + 50, 'N₂ precharge', size=10, mono=True, fill=INK3, anchor='end')
            # return filter + temperature sensor
            filt(800, R_, pfx + '-return-filter', vertical=True)
            with d.g(id=pfx + '-temp', cls='sensor'):
                junction(856, R_)
                d.line(856, R_, 856, R_ - 20 * sg, w=W2)
                d.circle(856, R_ - 29 * sg, 9, w=W2, fill=WHITE)
                d.text(856, R_ - 29 * sg + 3.8, 'T', size=10.5, mono=True, weight=700, anchor='middle')
                d.line(865, R_ - 29 * sg, 878, R_ - 29 * sg, w=W2, stroke=BLUE)
            tag(878, R_ - 29 * sg, 'HYD.SYS%d.T' % sysno, id=pfx + '-tag-t')
            d.text(800, R_ - 20 * sg + (0 if sg > 0 else 8), 'return filter', size=10, mono=True, fill=INK3,
                   anchor='middle', halo=True)
            # ------------------------------------------------ indication path (subject, accent)
            with d.g(id=pfx + '-indication', cls='subject indication-path'):
                # pressure switch (LP)
                junction(640, P_, ACC)
                d.line(640, P_, 640, P_ + 16 * sg, w=W1, stroke=ACC)
                ps_y = P_ + 16 * sg if sysno == 1 else P_ - 16 - 24
                d.rect(628, ps_y, 24, 24, rx=3, w=W1, stroke=ACC, fill=WHITE, id=pfx + '-pressure-switch')
                d.path(P((632, ps_y + 17), (637, ps_y + 17), (645, ps_y + 9)), w=W2, stroke=ACC)
                d.line(645, ps_y + 17, 649, ps_y + 17, w=W2, stroke=ACC)
                # pressure transducer
                junction(700, P_, ACC)
                d.line(700, P_, 700, P_ + 16 * sg, w=W1, stroke=ACC)
                pt_cy = P_ + 28 * sg
                d.circle(700, pt_cy, 12, w=W1, stroke=ACC, fill=WHITE, id=pfx + '-transducer')
                d.text(700, pt_cy + 3.6, 'PT', size=9.5, mono=True, weight=700, fill=ACC, anchor='middle')
                # harness to the BHEEM EU
                eu_edge = 404 if sysno == 1 else 500
                y_ps_out = ps_y + 24 if sysno == 1 else ps_y
                d.path(P((640, y_ps_out), (640, eu_edge)), w=W1, stroke=ACC, cls='draw harness')
                d.path(P((700, pt_cy + 12 * sg), (700, eu_edge)), w=W1, stroke=ACC, cls='draw harness')
                lx = 650
                ly = P_ + 40 * sg + (0 if sg > 0 else 0)
            # labels for the indication sensors
            d.text(620, ps_y + 10, 'pressure switch', size=11.5, weight=650, anchor='end', fill=ACC, halo=True)
            d.text(620, ps_y + 23, 'HYD.SYS%d.LP' % sysno, size=10, mono=True, fill=INK3, anchor='end', halo=True)
            d.text(720, pt_cy - 1, 'pressure transducer', size=11.5, weight=650, fill=ACC, halo=True)
            d.text(720, pt_cy + 12, 'HYD.SYS%d.P' % sysno, size=10, mono=True, fill=INK3, halo=True)
            # ------------------------------------------------ flight-control tandem actuators (both systems)
            for i, (ax, nm, sub) in enumerate(FCS):
                if sysno == 1:
                    vx = ax
                    junction(vx - 8, P_)
                    junction(vx + 8, R_)
                    d.line(vx - 8, P_, vx - 8, 296, w=W1)
                    d.line(vx + 8, R_, vx + 8, 296, w=W2)
                else:
                    vx = ax + 34
                    junction(vx - 4, P_)
                    junction(vx + 6, R_)
                    d.line(vx - 4, P_, vx - 4, 454, w=W1)
                    d.line(vx + 6, R_, vx + 6, 454, w=W2)
            # ------------------------------------------------ utility actuators (this system only)
            util = ([(1432, 'Slats', 'PDU', True), (1508, 'Gear', '', False)] if sysno == 1 else
                    [(1432, 'Brakes', '', False), (1508, 'NWS', '', False)])
            for ux, nm, sub, motor in util:
                junction(ux - 8, P_)
                junction(ux + 8, R_)
                if sysno == 1:
                    d.line(ux - 8, P_, ux - 8, 284, w=W1)
                    d.line(ux + 8, R_, ux + 8, 284, w=W2)
                    servo(ux, 293, 'hyd-valve-' + nm.lower())
                    actuator(ux, 302 if not motor else 284, 'hyd-act-' + nm.lower(), nm, sub, motor=motor,
                             label_y=430)
                else:
                    d.line(ux - 8, P_, ux - 8, 618, w=W1)
                    d.line(ux + 8, R_, ux + 8, 618, w=W2)
                    servo(ux, 609, 'hyd-valve-' + nm.lower())
                    actuator(ux, 500, 'hyd-act-' + nm.lower(), nm, None, label_y=480)

    # flight-control actuators drawn once (tandem: SYS1 chamber above, SYS2 chamber below)
    with d.g(id='hyd-fcs', cls='fcs'):
        for ax, nm, sub in FCS:
            k = (nm + '-' + sub).lower().strip('-')
            with d.g(id='hyd-act-' + k, cls='actuator tandem'):
                servo(ax, 305, 'hyd-valve-%s-1' % k)
                d.line(ax, 314, ax, 330, w=W2)
                L = 132
                top = 330
                d.rect(ax - 14, top, 28, L, w=W1, fill=WHITE, cls='draw')
                d.rect(ax - 14, top + L / 2 - 2.5, 28, 5, w=0, stroke='none', fill=INK)
                for py in (top + L * .28, top + L * .78):
                    d.rect(ax - 12, py - 3, 24, 6, w=W2, fill=F2)
                d.path(P((ax - 2.5, top + L * .28), (ax - 2.5, top + L + 24)) + ' ' +
                       P((ax + 2.5, top + L * .28), (ax + 2.5, top + L + 24)), w=W2)
                d.circle(ax, top + L + 28, 4, w=W2, fill=WHITE)
                # SYS2 servo on the right of the lower chamber
                servo(ax + 35, top + L * .78, 'hyd-valve-%s-2' % k, vertical=True)
                d.line(ax + 14, top + L * .78, ax + 26, top + L * .78, w=W2)
                d.text(ax, 520, nm, size=12, weight=650, anchor='middle')
                if sub:
                    d.text(ax, 534, sub, size=10, mono=True, fill=INK3, anchor='middle')

    # ------------------------------------------------------------------ engine + AMAGB + GEN
    with d.g(id='hyd-drive', cls='drive'):
        with d.g(id='hyd-engine'):
            d.path(P((64, 424), (180, 424), (198, 434), (198, 466), (180, 476), (64, 476), close=True), w=W1,
                   fill=F1, cls='draw')
            d.line(80, 424, 80, 476, w=W3)
            d.line(160, 424, 160, 476, w=W3)
            d.text(120, 454, 'F404', size=12, weight=700, anchor='middle')
        d.centreline(198, 450, 244, 450)
        with d.g(id='hyd-amagb', cls='gearbox'):
            d.rect(244, 404, 112, 92, rx=8, w=W1, fill=WHITE, cls='draw')
            d.circle(280, 442, 20, w=W3, dash=DASH_CENTRE)
            d.circle(320, 442, 20, w=W3, dash=DASH_CENTRE)
            for gx in (280, 320):
                d.line(gx - 4, 442, gx + 4, 442, w=W3)
                d.line(gx, 438, gx, 446, w=W3)
            d.text(300, 486, 'AMAGB', size=11, weight=700, anchor='middle', ls='0.08em')
        for y0, y1 in ((358, 404), (496, 554)):
            d.line(296, y0, 296, y1, w=W2)
            d.line(304, y0, 304, y1, w=W2)
        with d.g(id='hyd-gen'):
            d.line(356, 446, 374, 446, w=W2)
            d.line(356, 454, 374, 454, w=W2)
            d.circle(390, 450, 16, w=W1, fill=WHITE)
            d.text(390, 454, 'G', size=11, weight=700, anchor='middle')
            d.text(390, 480, 'GEN', size=10, mono=True, fill=INK3, anchor='middle')

    # ------------------------------------------------------------------ BHEEM EU + 1553 + CWS (subject end)
    with d.g(id='hyd-eu', cls='subject lru'):
        d.rect(606, 404, 128, 96, rx=6, w=W1, stroke=ACC, fill=WHITE, cls='draw')
        d.text(670, 444, 'BHEEM EU', size=14, weight=700, fill=ACC, anchor='middle')
        d.text(670, 461, 'utility management', size=10, mono=True, fill=INK3, anchor='middle')
        d.text(670, 475, '1553B · RT 7', size=10, mono=True, fill=INK3, anchor='middle')
        for px in (640, 700):
            d.rect(px - 4, 400, 8, 6, w=W2, stroke=ACC, fill=WHITE)
            d.rect(px - 4, 498, 8, 6, w=W2, stroke=ACC, fill=WHITE)
    with d.g(id='hyd-bus', cls='signal'):
        d.line(734, 450, 786, 450, w=W1, stroke=BLUE, cls='draw')
        d.line(786, 398, 786, 514, w=W1, stroke=BLUE)
        d.line(792, 398, 792, 514, w=W1, stroke=BLUE)
        d.text(789, 528, 'AV-MUX-2', size=10, mono=True, fill=BLUE, anchor='middle')
        d.text(789, 541, '1553B', size=10, mono=True, fill=BLUE, anchor='middle')
        for y, t1, t2 in ((424, 'OAC → CWS', 'caution legend'), (482, 'CDR · HUMS DAU', 'recorded per sortie')):
            d.line(792, y, 808, y, w=W2, stroke=BLUE)
            d.rect(808, y - 18, 162, 36, rx=5, w=W2, fill=WHITE)
            d.text(818, y - 2, t1, size=11.5, weight=650)
            d.text(818, y + 12, t2, size=10, mono=True, fill=INK3)
        with d.g(id='hyd-caution', cls='subject'):
            d.rect(910, 415, 52, 18, rx=3, w=W1, stroke=ACC, fill=WHITE)
            d.text(936, 427.5, 'HYD-101', size=9.5, mono=True, weight=700, fill=ACC, anchor='middle')
    # indication-path sequence: sensors -> harness -> BHEEM EU -> 1553 -> caution
    with d.g(id='hyd-path-callouts', cls='callouts'):
        d.callout('1', 670, 266, accent=True, id='hyd-c1')
        d.callout('2', 670, 352, accent=True, id='hyd-c2')
        d.callout('3', 594, 452, 606, 452, accent=True, id='hyd-c3', dot=False)
        d.callout('4', 789, 380, accent=True, id='hyd-c4')
        d.callout('5', 936, 392, 936, 415, accent=True, id='hyd-c5', dot=False)
    d.text(1170, 166, 'flight controls · tandem actuators (SYS1 + SYS2)', size=10.5, mono=True,
           fill=INK3, anchor='middle')

    # ------------------------------------------------------------------ headers + key
    d.text(78, 118, 'SYS 1', size=16, weight=700)
    d.text(130, 118, '280 bar nominal', size=11, mono=True, fill=INK3)
    d.text(78, 792, 'SYS 2', size=16, weight=700)
    d.text(130, 792, '280 bar nominal', size=11, mono=True, fill=INK3)
    with d.g(id='hyd-key', cls='legend'):
        x, y = 78, 838
        items = [('pressure', dict(w=W1)), ('return', dict(w=W2)), ('case drain', dict(w=W3, dash='4 3')),
                 ('signal → BHEEM EU', dict(w=W2, stroke=BLUE)), ('indication path', dict(w=W1, stroke=ACC))]
        for t, st in items:
            d.line(x, y - 4, x + 30, y - 4, **st)
            d.text(x + 38, y, t, size=11, mono=True, fill=INK3)
            x += 46 + 7.0 * len(t) + 26
        d.circle(x + 4, y - 4, 2.6, w=0, stroke='none', fill=INK)
        d.text(x + 14, y, 'junction', size=11, mono=True, fill=INK3)
    d.sheet(2, 'Hydraulic systems — SYS1 / SYS2', 'indication path · HYD-101 reporter BHEEM EU')
    return d


if __name__ == '__main__':
    print(build().save('hydraulic-system.svg'))
