"""PHX-ILL-13 · assistant-tools.svg — the bounded assistant: a central plan node (subject, accent) calls five
read-only tools (aircraft_summary, event_recurrence, serial_history, evidence_chain, what_if) over blue data
spokes, then returns a cited answer and at most an order draft for a person.  Glyphs follow the shell.js icon
style (24-unit grid, round caps/joins)."""
import math
from lib import *

GLYPHS = {
    'twin': '<path d="M12 2.6l1.25 4.3 6.95 7.9v1.7l-6.7-2.1-.35 4.1 2.3 1.75v1.35L12 20.7l-3.45.9v-1.35l2.3-1.75-.35-4.1-6.7 2.1v-1.7l6.95-7.9z"/>',
    'recur': '<path d="M3.5 16.5h17"/><circle cx="7" cy="16.5" r="1.7"/><circle cx="12" cy="16.5" r="1.7"/><circle cx="17" cy="16.5" r="1.7"/><path d="M6.5 11.5a6 5 0 0 1 11 0"/><path d="M18 7.6v3.9h-3.9"/>',
    'tag': '<path d="M3.5 12.3V4.5a1 1 0 0 1 1-1h7.8l8.2 8.2a1.4 1.4 0 0 1 0 2l-6.6 6.6a1.4 1.4 0 0 1-2 0z"/><circle cx="8" cy="8" r="1.4"/><path d="M10.5 14.5l3-3M13 17l3-3"/>',
    'link': '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    'fork': '<circle cx="6.5" cy="5.5" r="2"/><circle cx="6.5" cy="18.5" r="2"/><circle cx="17.5" cy="8.5" r="2"/><path d="M6.5 7.5v9M17.5 10.5c0 4-4 4-11 6"/>',
    'assistant': '<path d="M5 18.5l-1.2 2.3 3.6-1.2A8 8 0 1 0 5 18.5z"/><path d="M12 8.3v1.6M12 14.1v1.6M8.3 12h1.6M14.1 12h1.6"/>',
    'pen': '<path d="M4 20l1-4.2L16.3 4.5a2 2 0 0 1 2.9 0l.3.3a2 2 0 0 1 0 2.9L8.2 19z"/><path d="M14 7l3 3"/>',
    'book': '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
}


def glyph(d, name, cx, cy, size, color=INK, sw=2.2, id=None):
    k = size / 24.0
    d.add('<g%s transform="translate(%s %s) scale(%s)" fill="none" stroke="%s" stroke-width="%s" '
          'stroke-linecap="round" stroke-linejoin="round" class="glyph">%s</g>' % (
              (' id="%s"' % id) if id else '', n(cx - size / 2), n(cy - size / 2), n(k), color, n(sw / k),
              GLYPHS[name]))


def build():
    d = Doc('tool', 'Assistant — plan and five read-only tools',
            'A central plan node calls five read-only tools and returns a cited answer and, at most, an order '
            'draft that a person signs.')
    d.std_defs()
    CX, CY, RR = 800.0, 404.0, 236.0
    tools = [('aircraft_summary', 'Aircraft summary', 'state of one tail as of 06:00', 'twin'),
             ('event_recurrence', 'Event recurrence', 'how often a code returns', 'recur'),
             ('serial_history', 'Serial history', 'one part across tails', 'tag'),
             ('evidence_chain', 'Evidence chain', 'records behind a claim', 'link'),
             ('what_if', 'What-if', 'belief-mode fork vs status quo', 'fork')]
    angs = [-90, -18, 54, 126, 198]

    # ------------------------------------------------------------------ spokes (data, blue)
    with d.g(id='tool-spokes', cls='spokes'):
        for (key, *_), a in zip(tools, angs):
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            x0, y0 = CX + c * 84, CY + s * 84
            x1, y1 = CX + c * (RR - 62), CY + s * (RR - 62)
            # two lanes: call (out) and result (back)
            nx, ny = -s * 5, c * 5
            d.line(x0 + nx, y0 + ny, x1 + nx, y1 + ny, w=W2, stroke=BLUE, cls='draw call', id='tool-call-' + key)
            d.arrowhead(x1 + nx, y1 + ny, math.atan2(y1 - y0, x1 - x0), L=8, half=2.4, fill=BLUE)
            d.line(x1 - nx, y1 - ny, x0 - nx, y0 - ny, w=W2, stroke=BLUE, dash='3 3', cls='draw result',
                   id='tool-result-' + key)
            d.arrowhead(x0 - nx, y0 - ny, math.atan2(y0 - y1, x0 - x1), L=8, half=2.4, fill=BLUE)
        d.text(CX + 16, CY - 128, 'call →', size=10.5, mono=True, fill=BLUE)
        d.text(CX + 16, CY - 114, '← cited result', size=10.5, mono=True, fill=BLUE)
        d.circle(CX, CY, RR, w=W3, stroke=INK5, dash='2 5')

    # ------------------------------------------------------------------ plan node (subject)
    with d.g(id='tool-plan', cls='subject node'):
        d.circle(CX, CY, 78, w=W1 * 1.3, stroke=ACC, fill=WHITE, cls='draw')
        glyph(d, 'assistant', CX, CY - 16, 40, color=ACC, sw=2.2)
        d.text(CX, CY + 30, 'plan', size=20, weight=700, fill=ACC, anchor='middle')
        d.text(CX, CY + 48, 'pick tools · cite', size=10.5, mono=True, fill=INK3, anchor='middle')

    # ------------------------------------------------------------------ tool nodes
    with d.g(id='tool-nodes', cls='nodes'):
        for (key, name, sub, gl), a in zip(tools, angs):
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            x, y = CX + c * RR, CY + s * RR
            with d.g(id='tool-' + key.replace('_', '-'), cls='node tool'):
                d.rect(x - 52, y - 52, 104, 104, rx=24, w=W1, fill=WHITE, cls='draw')
                glyph(d, gl, x, y, 50, sw=2.2)
                if a == -90:
                    lx, ly, an = x + 70, y - 8, 'start'
                elif c > 0.2:
                    lx, ly, an = x + 70, y - 8, 'start'
                elif c < -0.2:
                    lx, ly, an = x - 70, y - 8, 'end'
                else:
                    lx, ly, an = x, y + 76, 'middle'
                d.text(lx, ly, name, size=16, weight=700, anchor=an)
                d.text(lx, ly + 18, key + '()', size=12, mono=True, weight=600, fill=BLUE, anchor=an)
                d.text(lx, ly + 34, sub, size=10.5, mono=True, fill=INK3, anchor=an)

    # ------------------------------------------------------------------ output: cited answer + order draft
    with d.g(id='tool-output', cls='output'):
        y0 = CY + 78
        d.path(P((CX, y0 + 4), (CX, 708)), w=W1, cls='draw')
        d.path(P((CX - 165, 708), (CX + 180, 708)), w=W1)
        for xx in (CX - 165, CX + 180):
            d.path(P((xx, 708), (xx, 724)), w=W1)
            d.arrowhead(xx, 728, math.pi / 2, L=8, half=2.6)
        bx = CX - 300
        d.rect(bx, 730, 270, 64, rx=12, w=W1, fill=WHITE)
        glyph(d, 'book', bx + 34, 762, 26, sw=1.7)
        d.text(bx + 60, 756, 'Cited answer', size=14, weight=700)
        d.text(bx + 60, 774, 'every claim links a record id', size=10.5, mono=True, fill=INK3)
        bx2 = CX + 30
        d.rect(bx2, 730, 300, 64, rx=12, w=W1, fill=F1, dash='6 4')
        glyph(d, 'pen', bx2 + 34, 762, 26, sw=1.7)
        d.text(bx2 + 60, 756, 'Order draft', size=14, weight=700)
        d.text(bx2 + 60, 774, 'never issued — a person signs', size=10.5, mono=True, fill=INK3)
    d.text(64, 76, 'ASSISTANT · BOUNDED, READ-ONLY, LOCAL', size=11, weight=700, ls='0.14em')
    d.text(64, 94, 'five tools over the as-of state · no tool can write or issue an order', size=11, mono=True,
           fill=INK3)
    d.sheet(13, 'Assistant — plan and five tools', 'read-only tools · cited answers')
    return d


if __name__ == '__main__':
    print(build().save('assistant-tools.svg'))
