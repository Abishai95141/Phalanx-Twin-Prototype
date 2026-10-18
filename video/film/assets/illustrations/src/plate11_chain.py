"""PHX-ILL-11 · hash-chain.svg — the epoch 22 Jun 08:00 event log as a hash chain.  Every value is read from
video/data/decision_flow.json (lel.events): hash = blake2b(prev_hash || canonical_json(event), 32 bytes).
Subject (accent): the chain head.  Blue: prev_hash -> hash links."""
import json
import os
from lib import *

SRC = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../../data/decision_flow.json'))


def build():
    lel = json.load(open(SRC))['lel']
    ev = lel['events']
    E = {e['event']['seq']: e for e in ev}

    def item(seq):
        e = E[seq]
        x = e['event']
        return dict(kind='block', seq=str(seq), type=x['type'], t=x['t_valid'][11:16], actor=x['actor'],
                    prev=e['prev_hash'], hash=e['hash'])

    def gap(a, b, label):
        return dict(kind='gap', seq='%d–%d' % (a, b), type=label, t='%s–%s' % (E[a]['event']['t_valid'][11:16],
                                                                          E[b]['event']['t_valid'][11:16]),
                    actor='%d events' % (b - a + 1), prev=E[a]['prev_hash'], hash=E[b]['hash'])

    row1 = [item(1), item(2), item(3), gap(4, 10, 'APPROVED ×6 · ACK'), item(11)]
    row2 = [item(12), item(13), gap(14, 19, 'ACCEPTED ×6'), item(20)]
    head = ev[-1]

    d = Doc('chain', 'Hash-chained event log',
            'Blocks of the epoch event log, each carrying the previous block’s hash; the chain head is the hash '
            'shown on the orders screen.')
    d.std_defs()
    BW, BH, G = 252.0, 156.0, 44.0
    X0 = 84.0
    Y1, Y2 = 168.0, 470.0

    def block(it, x, y, idx, is_head=False):
        col = ACC if is_head else INK
        gid = 'chain-block-' + it['seq'].replace('–', '-')
        with d.g(id=gid, cls='block' + (' head subject' if is_head else '') + (' gap' if it['kind'] == 'gap' else '')):
            d.rect(x, y, BW, BH, rx=10, w=W1, stroke=col, fill=WHITE, dash='6 4' if it['kind'] == 'gap' else None,
                   cls='draw')
            d.text(x + 16, y + 26, 'seq ' + it['seq'], size=11, mono=True, fill=INK3)
            d.text(x + BW - 16, y + 26, it['t'], size=11, mono=True, fill=INK3, anchor='end')
            d.text(x + 16, y + 48, it['type'], size=14.5 if len(it['type']) < 16 else 13, weight=700, fill=col)
            d.text(x + 16, y + 66, it['actor'], size=10.5, mono=True, fill=INK3)
            d.line(x + 12, y + 80, x + BW - 12, y + 80, w=W3)
            # prev_hash row
            d.text(x + 16, y + 102, 'prev_hash', size=10, mono=True, fill=INK3)
            d.text(x + 92, y + 102, it['prev'][:8] + '…', size=12.5, mono=True, weight=500,
                   id=gid + '-prev')
            d.line(x + 92, y + 107, x + 92 + 9 * 7.6, y + 107, w=W2, stroke=BLUE)
            # hash row (boxed)
            d.rect(x + 10, y + 116, BW - 20, 30, rx=6, w=W2 if not is_head else W1, stroke=col,
                   fill=F1 if not is_head else WHITE)
            d.text(x + 16, y + 136, 'hash', size=10, mono=True, fill=INK3)
            d.text(x + 92, y + 136, it['hash'][:8] + '…', size=12.5, mono=True, weight=700, fill=col,
                   id=gid + '-hash')
            if is_head:
                d.rect(x + BW - 62, y - 11, 52, 20, rx=10, w=0, stroke='none', fill=ACC)
                d.text(x + BW - 36, y + 3, 'HEAD', size=10, weight=700, fill=WHITE, anchor='middle', ls='0.1em')

    def link(x0, y0, x1, y1, pts=None, id=None):
        with d.g(id=id, cls='link'):
            path = [(x0, y0)] + (pts or []) + [(x1, y1)]
            d.path(P(*path), w=W1, stroke=BLUE, cls='draw')
            d.arrowhead(x1, y1, 0, L=8, half=2.4, fill=BLUE)
            d.circle(x0, y0, 2.4, w=0, stroke='none', fill=BLUE)
            # chain-link glyph on the riser between the two blocks
            if pts and len(pts) == 2:
                gx, gy = pts[0][0], (pts[0][1] + pts[1][1]) / 2
                d.rect(gx - 5, gy - 11, 10, 14, rx=5, w=W2, stroke=BLUE, fill=WHITE)
                d.rect(gx - 5, gy - 3, 10, 14, rx=5, w=W2, stroke=BLUE, fill='none')

    xs1 = [X0 + i * (BW + G) for i in range(5)]
    xs2 = [X0 + i * (BW + G) for i in range(4)]
    with d.g(id='chain-row-1'):
        for i, it in enumerate(row1):
            block(it, xs1[i], Y1, i)
    with d.g(id='chain-row-2'):
        for i, it in enumerate(row2):
            block(it, xs2[i], Y2, i, is_head=(it['seq'] == '20'))
    with d.g(id='chain-links', cls='links'):
        for i in range(4):
            link(xs1[i] + BW - 10, Y1 + 131, xs1[i + 1] - 2, Y1 + 98, pts=[(xs1[i] + BW + G / 2, Y1 + 131),
                                                                         (xs1[i] + BW + G / 2, Y1 + 98)],
                 id='chain-link-r1-%d' % i)
        # wrap from the end of row 1 to the start of row 2
        xe = xs1[4] + BW - 10
        link(xe, Y1 + 131, X0 - 2, Y2 + 98, pts=[(xe + 26, Y1 + 131), (xe + 26, (Y1 + BH + Y2) / 2),
                                                  (X0 - 26, (Y1 + BH + Y2) / 2), (X0 - 26, Y2 + 98)],
             id='chain-link-wrap')
        for i in range(3):
            link(xs2[i] + BW - 10, Y2 + 131, xs2[i + 1] - 2, Y2 + 98, pts=[(xs2[i] + BW + G / 2, Y2 + 131),
                                                                         (xs2[i] + BW + G / 2, Y2 + 98)],
                 id='chain-link-r2-%d' % i)
        d.text(700, (Y1 + BH + Y2) / 2 - 8, 'prev_hash of each block = hash of the block before',
               size=11, mono=True, fill=BLUE, anchor='middle', halo=True)

    # ------------------------------------------------------------------ formula + head panel
    with d.g(id='chain-formula', cls='note'):
        x, y = xs2[3] + BW + 52, Y2 + 8
        d.kicker(x, y + 6, 'How a block is sealed')
        d.text(x, y + 36, 'hash = blake2b(', size=13, mono=True, weight=600)
        d.text(x + 18, y + 56, 'prev_hash ‖ canonical_json(event)', size=12, mono=True)
        d.text(x, y + 76, ')  · 32 bytes', size=13, mono=True, weight=600)
        d.text(x, y + 104, 'change any event and every', size=11, mono=True, fill=INK3)
        d.text(x, y + 120, 'later hash changes with it', size=11, mono=True, fill=INK3)
    with d.g(id='chain-head-full', cls='note'):
        x, y = X0, Y2 + BH + 64
        d.kicker(x, y, 'Chain head · epoch 22 Jun 08:00 · 20 events', fill=ACC)
        d.text(x, y + 26, head['hash'], size=13, mono=True, weight=600, id='chain-head-hash')
        d.text(x, y + 46, 'genesis prev_hash = 32 zero bytes · stream epoch:20260622T0800 · same value on the '
                          'orders screen', size=11, mono=True, fill=INK3)
    d.text(64, 76, 'ONE LOG · EVERY STEP OF THE EPOCH, HASH-CHAINED', size=11, weight=700, ls='0.14em')
    d.text(64, 94, 'read from the epoch log (lel.events) — values are the real hashes', size=11, mono=True, fill=INK3)
    d.sheet(11, 'Hash-chained event log', 'epoch 22 Jun 08:00 · head afd2fdab…')
    return d


if __name__ == '__main__':
    print(build().save('hash-chain.svg'))
