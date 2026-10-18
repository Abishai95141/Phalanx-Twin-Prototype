"""PHX-ILL-12 · mapek-loop.svg — the daily decision loop (MAPE-K) as a ring: 06:00 snapshot -> analyse -> plan ->
fork gate -> board -> 07:45 freeze -> 08:00 orders -> reconcile, around one state (K); the hash-chained event log
ribbon underneath uses the real event types/times of epoch 22 Jun 08:00 (decision_flow.json).
Subject (accent): the loop itself (ring segments).  Blue: the log ribbon links."""
import json
import math
import os
from lib import *
from plate01_aircraft import HALF

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../../data/decision_flow.json'))
ICONS = {
    'clock': '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    'insights': '<path d="M4 20h16"/><rect x="5.5" y="11" width="3" height="6" rx="1"/><rect x="10.5" y="6" width="3" height="11" rx="1"/><rect x="15.5" y="9" width="3" height="8" rx="1"/>',
    'plan': '<rect x="3.5" y="4.5" width="17" height="16" rx="3"/><path d="M3.5 9h17"/><path d="M8 3v3M16 3v3"/><path d="M7 12.6h5M10 16h7"/>',
    'fork': '<circle cx="6.5" cy="5.5" r="2"/><circle cx="6.5" cy="18.5" r="2"/><circle cx="17.5" cy="8.5" r="2"/><path d="M6.5 7.5v9M17.5 10.5c0 4-4 4-11 6"/>',
    'signature': '<path d="M3 18c3-1 4-9 6-9s-1 8 1 8 3-5 4.5-5 .5 4 2 4 2-1 4.5-1"/><path d="M3 21h18"/>',
    'lock': '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    'send': '<path d="M12 19V5M5.5 11.5L12 5l6.5 6.5"/>',
    'refresh': '<path d="M20 11.5A8 8 0 0 0 5.6 7M4 4v4h4M4 12.5A8 8 0 0 0 18.4 17M20 20v-4h-4"/>',
}


def icon(d, name, cx, cy, size=26, color=INK):
    k = size / 24.0
    d.add('<g transform="translate(%s %s) scale(%s)" fill="none" stroke="%s" stroke-width="%s" '
          'stroke-linecap="round" stroke-linejoin="round">%s</g>' % (n(cx - size / 2), n(cy - size / 2), n(k), color,
                                                                     n(1.7 / k), ICONS[name]))


def build():
    ev = json.load(open(SRC))['lel']['events']
    d = Doc('loop', 'The daily loop — MAPE-K',
            'The daily decision loop as a ring of eight stages around one shared state, with the hash-chained '
            'event log of the epoch underneath.')
    d.std_defs()
    CX, CY, R, NR = 800.0, 384.0, 214.0, 30.0
    stages = [('snapshot', 'Snapshot', '06:00', 'state sealed as of t_ingest', 'clock'),
              ('analyse', 'Analyse', '06:04', 'engines read the state', 'insights'),
              ('plan', 'Plan', '', 'versioned policies · optimisers', 'plan'),
              ('forkgate', 'Fork gate', '', 'paired simulations vs status quo', 'fork'),
              ('board', 'Board', '06:05', 'a person approves · human gate', 'signature'),
              ('freeze', 'Freeze', '07:45', 'board locked', 'lock'),
              ('orders', 'Orders', '08:00', 'only via orders.commands', 'send'),
              ('reconcile', 'Reconcile', '', 'outcomes come back as records', 'refresh')]
    angs = [-90 + i * 45 for i in range(8)]
    pos = [(CX + R * math.cos(math.radians(a)), CY + R * math.sin(math.radians(a))) for a in angs]

    # ------------------------------------------------------------------ ring (subject)
    with d.g(id='loop-ring', cls='subject ring'):
        d.circle(CX, CY, R + 46, w=W3, stroke=INK5, dash='2 4')
        d.circle(CX, CY, R - 70, w=W3, stroke=INK5, dash='2 4')
        gap = math.degrees((NR + 7) / R)
        for i in range(8):
            a0, a1 = angs[i] + gap, angs[i] + 45 - gap
            d.path(arc_d(CX, CY, R, a0, a1), w=W1 * 1.4, stroke=ACC, id='loop-seg-%d' % (i + 1), cls='draw seg')
            ex, ey = CX + R * math.cos(math.radians(a1)), CY + R * math.sin(math.radians(a1))
            d.arrowhead(ex, ey, math.radians(a1 + 90) - 0.06, L=10, half=3.2, fill=ACC)
    # sector labels (MAPE-K)
    with d.g(id='loop-sectors', cls='sectors'):
        for t, a in (('MONITOR', -90), ('ANALYSE', -45), ('PLAN', 22.5), ('EXECUTE', 135)):
            r = R - 66
            x, y = CX + r * math.cos(math.radians(a)), CY + r * math.sin(math.radians(a))
            d.text(x, y + 4, t, size=10, weight=700, ls='0.14em', fill=INK4, anchor='middle')
    # knowledge: one state
    with d.g(id='loop-knowledge', cls='knowledge'):
        s = 7.6
        ring_pts = HALF + [[x, -y] for x, y in HALF[1:-1][::-1]]
        pts = [(CX + y * s, CY - 52 + x * s) for x, y in ring_pts]
        d.path(P(*pts, close=True), w=W2, fill=F1, cls='draw', id='loop-twin')
        d.text(CX, CY + 72, 'K · one state', size=15, weight=700, anchor='middle')
        d.text(CX, CY + 90, 'twin · engines · one log', size=10.5, mono=True, fill=INK3, anchor='middle')
    # nodes + labels
    with d.g(id='loop-nodes', cls='nodes'):
        for i, ((key, name, t, sub, ic), (x, y), a) in enumerate(zip(stages, pos, angs)):
            human = key == 'board'
            with d.g(id='loop-node-' + key, cls='node'):
                d.circle(x, y, NR, w=W1, fill=WHITE if not human else F1, cls='draw')
                icon(d, ic, x, y, size=26)
                c, s_ = math.cos(math.radians(a)), math.sin(math.radians(a))
                lx, ly = x + c * (NR + 18), y + s_ * (NR + 18)
                anchor = 'start' if c > 0.3 else ('end' if c < -0.3 else 'middle')
                if anchor == 'middle':
                    ly = y - NR - 46 if s_ < 0 else y + NR + 22
                else:
                    ly -= 8
                title = (t + ' · ' if t else '') + name
                d.text(lx, ly, title, size=15, weight=700, anchor=anchor, fill=INK)
                d.text(lx, ly + 17, sub, size=10.5, mono=True, fill=INK3, anchor=anchor)
                if human:
                    d.text(lx, ly + 33, 'HUMAN', size=9.5, weight=700, ls='0.12em', fill=INK, anchor=anchor)
    # learning return
    with d.g(id='loop-learning', cls='learning'):
        x, y = pos[7]
        d.path('M%s %s Q%s %s %s %s' % (n(x + 24), n(y + 20), n(CX - 96), n(CY - 60), n(CX - 46), n(CY - 40)),
               w=W2, stroke=ACC, dash='5 4')
        d.arrowhead(CX - 46, CY - 40, math.radians(20), L=9, half=2.6, fill=ACC)
        d.text(CX - 104, CY - 18, 'outcomes → labels', size=10.5, mono=True, fill=ACC, anchor='middle', halo=True)
        d.text(CX - 104, CY - 4, '→ learning', size=10.5, mono=True, fill=ACC, anchor='middle', halo=True)

    # ------------------------------------------------------------------ log ribbon (real events)
    groups = [('SNAPSHOT_SEALED', [1]), ('ANALYZED', [2]), ('BOARD_OPEN', [3]), ('APPROVED ×6', list(range(4, 10))),
              ('ACKNOWLEDGED', [10]), ('FROZEN', [11]), ('HUMAN_SIGNED', [12]), ('SUBMITTED', [13]),
              ('ACCEPTED ×7', list(range(14, 21)))]
    E = {e['event']['seq']: e for e in ev}
    with d.g(id='loop-ribbon', cls='ribbon'):
        x0, y0, bw, bh, g = 92.0, 712.0, 140.0, 58.0, 13.0
        d.kicker(x0, y0 - 14, 'Event log · hash-chained · epoch 22 Jun 08:00')
        for i, (name, seqs) in enumerate(groups):
            x = x0 + i * (bw + g)
            t0 = E[seqs[0]]['event']['t_valid'][11:16]
            t1 = E[seqs[-1]]['event']['t_valid'][11:16]
            t = t0 if t0 == t1 else t0 + '–' + t1
            last = i == len(groups) - 1
            with d.g(id='loop-log-%d' % (i + 1), cls='log-block'):
                d.rect(x, y0, bw, bh, rx=8, w=W1 if last else W2, fill=WHITE, cls='draw')
                d.text(x + 10, y0 + 20, name, size=11, weight=700 if not last else 750)
                d.text(x + 10, y0 + 36, t, size=10.5, mono=True, fill=INK3)
                d.text(x + 10, y0 + 51, E[seqs[-1]]['hash'][:8] + '…', size=10.5, mono=True, fill=BLUE)
            if i:
                lx = x - g / 2
                d.rect(lx - 7, y0 + bh / 2 - 4, 9, 8, rx=4, w=W2, stroke=BLUE, fill=WHITE)
                d.rect(lx - 2, y0 + bh / 2 - 4, 9, 8, rx=4, w=W2, stroke=BLUE, fill='none')
        d.text(x0 + 9 * (bw + g) - g, y0 + bh + 18, 'head afd2fdab… · 20 events', size=10.5, mono=True,
               fill=INK3, anchor='end')
    d.text(64, 76, 'ONE LOOP · EVERY MORNING BEFORE 08:00', size=11, weight=700, ls='0.14em')
    d.text(64, 94, 'monitor · analyse · plan · execute over one shared state (MAPE-K)', size=11, mono=True, fill=INK3)
    d.sheet(12, 'The daily loop — MAPE-K', '06:00 snapshot → 08:00 orders → reconcile')
    return d


if __name__ == '__main__':
    print(build().save('mapek-loop.svg'))
