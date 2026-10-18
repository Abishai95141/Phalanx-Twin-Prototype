"""Phalanx Twin illustration kit — shared style system for every blueprint plate.

All plates are generated as clean SVG geometry (path/line/circle/rect/text) in a 1600 x 900 viewBox
(1:1 = the plate shown 1600 px wide).  Strokes, fills and type are fixed here so every plate matches:

  ink #0B0D10   1.5 primary outline · 0.9 secondary detail · 0.6 hatching / construction / centre lines
  fills         #F7F7F5, #EFEFEC only (light)
  accent        #E8743B — the subject part of the plate, nothing else
  blue          #2563C9 — data / evidence / signal lines only
  type          Manrope (labels), JetBrains Mono (dimensions, ids, codes)

No gradients, blur, shadows, raster or text-as-image.  Ids are prefixed per plate so several plates can be
inlined in one HTML document.
"""
import math
import os
import re

INK = '#0B0D10'
INK2 = '#31353B'
INK3 = '#62676F'
INK4 = '#8E939A'
INK5 = '#B9BDC2'
ACC = '#E8743B'
BLUE = '#2563C9'
F1 = '#F7F7F5'
F2 = '#EFEFEC'
WHITE = '#FFFFFF'
W1, W2, W3 = 1.5, 0.9, 0.6
SANS = "Manrope, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, Menlo, monospace"
DASH_CENTRE = '16 3 2 3'      # dash-dot centre line
DASH_HIDDEN = '5 3'           # hidden detail
DASH_PHANTOM = '10 3 2 3 2 3'  # alternate position / phantom

OUT_FILM = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
OUT_SCREENS = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../../screens/assets/illus'))


def n(v):
    """compact number formatting"""
    if isinstance(v, int):
        return str(v)
    s = '%.2f' % v
    s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def attrs(d):
    out = []
    for k, v in d.items():
        if v is None or v is False:
            continue
        k = {'cls': 'class', 'klass': 'class'}.get(k, k)
        k = k.rstrip('_').replace('_', '-')
        if isinstance(v, float):
            v = n(v)
        out.append('%s="%s"' % (k, esc(v)))
    return (' ' + ' '.join(out)) if out else ''


def P(*pts, close=False):
    """polyline path data from (x, y) tuples"""
    d = 'M' + ' L'.join('%s %s' % (n(float(x)), n(float(y))) for x, y in pts)
    return d + (' Z' if close else '')


def rot(x, y, a, cx=0, cy=0):
    c, s = math.cos(a), math.sin(a)
    x, y = x - cx, y - cy
    return cx + x * c - y * s, cy + x * s + y * c


def arc_d(cx, cy, r, a0, a1, move=True, ry=None):
    """SVG arc from angle a0 to a1 (degrees, clockwise in screen space)"""
    ry = ry or r
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + ry * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + ry * math.sin(math.radians(a1))
    large = 1 if abs(a1 - a0) % 360 > 180 else 0
    sweep = 1 if a1 > a0 else 0
    s = ('M%s %s ' % (n(x0), n(y0))) if move else ''
    return s + 'A%s %s 0 %d %d %s %s' % (n(r), n(ry), large, sweep, n(x1), n(y1))


class Affine:
    """2D affine map  (x, y) -> (a x + c y + e, b x + d y + f)"""

    def __init__(self, a=1, b=0, c=0, d=1, e=0, f=0):
        self.m = (a, b, c, d, e, f)

    def __call__(self, x, y):
        a, b, c, d, e, f = self.m
        return a * x + c * y + e, b * x + d * y + f

    def then(self, other):
        a, b, c, d, e, f = self.m
        A, B, C, D, E, F = other.m
        return Affine(A * a + C * b, B * a + D * b, A * c + C * d, B * c + D * d, A * e + C * f + E, B * e + D * f + F)

    def svg(self):
        return 'matrix(%s)' % ' '.join(n(float(v)) for v in self.m)


K = 0.5522847498


def circle_segs(cx, cy, r, ry=None):
    ry = ry if ry is not None else r
    return [('M', (cx + r, cy)),
            ('C', (cx + r, cy + K * ry), (cx + K * r, cy + ry), (cx, cy + ry)),
            ('C', (cx - K * r, cy + ry), (cx - r, cy + K * ry), (cx - r, cy)),
            ('C', (cx - r, cy - K * ry), (cx - K * r, cy - ry), (cx, cy - ry)),
            ('C', (cx + K * r, cy - ry), (cx + r, cy - K * ry), (cx + r, cy)), ('Z',)]


def rect_segs(x, y, w, h, r=0):
    if r <= 0:
        return [('M', (x, y)), ('L', (x + w, y)), ('L', (x + w, y + h)), ('L', (x, y + h)), ('Z',)]
    k = r * (1 - K)
    return [('M', (x + r, y)), ('L', (x + w - r, y)), ('C', (x + w - k, y), (x + w, y + k), (x + w, y + r)),
            ('L', (x + w, y + h - r)), ('C', (x + w, y + h - k), (x + w - k, y + h), (x + w - r, y + h)),
            ('L', (x + r, y + h)), ('C', (x + k, y + h), (x, y + h - k), (x, y + h - r)),
            ('L', (x, y + r)), ('C', (x, y + k), (x + k, y), (x + r, y)), ('Z',)]


def line_segs(*pts, close=False):
    s = [('M', pts[0])] + [('L', p) for p in pts[1:]]
    return s + ([('Z',)] if close else [])


def segs_d(segs, M=None):
    M = M or Affine()
    out = []
    for s in segs:
        if s[0] == 'Z':
            out.append('Z')
            continue
        pts = ['%s %s' % tuple(n(float(v)) for v in M(*p)) for p in s[1:]]
        out.append(s[0] + ' '.join(pts))
    return ' '.join(out)


class Doc:
    def __init__(self, pfx, title, desc='', w=1600, h=900):
        self.pfx, self.title, self.desc, self.w, self.h = pfx, title, desc, w, h
        self.out = []
        self.defs = []
        self.depth = 0
        self.ids = set()

    # ------------------------------------------------------------------ raw
    def add(self, s):
        self.out.append('  ' * (self.depth + 1) + s)

    def _id(self, i):
        if i:
            assert i not in self.ids, 'duplicate id ' + i
            self.ids.add(i)
        return i

    def g(self, id=None, cls=None, **a):
        doc = self

        class _G:
            def __enter__(s):
                doc.add('<g%s>' % attrs(dict(id=doc._id(id), cls=cls, **a)))
                doc.depth += 1
                return doc

            def __exit__(s, *e):
                doc.depth -= 1
                doc.add('</g>')
        return _G()

    # ------------------------------------------------------------------ primitives
    def path(self, d, w=W1, stroke=INK, fill='none', dash=None, cls=None, id=None, cap='round', join='round', **a):
        self.add('<path%s/>' % attrs(dict(id=self._id(id), cls=cls, d=d, fill=fill, stroke=stroke,
                                          stroke_width=w if stroke != 'none' else None, stroke_dasharray=dash,
                                          stroke_linecap=cap if stroke != 'none' else None,
                                          stroke_linejoin=join if stroke != 'none' else None, **a)))

    def line(self, x1, y1, x2, y2, w=W2, stroke=INK, dash=None, cls=None, id=None, cap='round', **a):
        self.add('<line%s/>' % attrs(dict(id=self._id(id), cls=cls, x1=float(x1), y1=float(y1), x2=float(x2),
                                          y2=float(y2), stroke=stroke, stroke_width=w, stroke_dasharray=dash,
                                          stroke_linecap=cap, **a)))

    def circle(self, cx, cy, r, w=W1, stroke=INK, fill='none', dash=None, cls=None, id=None, **a):
        self.add('<circle%s/>' % attrs(dict(id=self._id(id), cls=cls, cx=float(cx), cy=float(cy), r=float(r),
                                            fill=fill, stroke=stroke,
                                            stroke_width=w if stroke != 'none' else None,
                                            stroke_dasharray=dash, **a)))

    def ellipse(self, cx, cy, rx, ry, w=W1, stroke=INK, fill='none', dash=None, cls=None, id=None, **a):
        self.add('<ellipse%s/>' % attrs(dict(id=self._id(id), cls=cls, cx=float(cx), cy=float(cy), rx=float(rx),
                                             ry=float(ry), fill=fill, stroke=stroke,
                                             stroke_width=w if stroke != 'none' else None,
                                             stroke_dasharray=dash, **a)))

    def rect(self, x, y, w_, h_, rx=0, w=W1, stroke=INK, fill='none', dash=None, cls=None, id=None, **a):
        self.add('<rect%s/>' % attrs(dict(id=self._id(id), cls=cls, x=float(x), y=float(y), width=float(w_),
                                          height=float(h_), rx=float(rx) if rx else None, fill=fill,
                                          stroke=stroke, stroke_width=w if stroke != 'none' else None,
                                          stroke_dasharray=dash, stroke_linejoin='round', **a)))

    def text(self, x, y, s, size=13, mono=False, weight=None, fill=INK, anchor='start', ls=None, cls=None,
             id=None, halo=False, upper=False, transform=None, baseline=None, **a):
        if weight is None:
            weight = 500 if mono else 600
        if upper:
            s = str(s).upper()
        extra = {}
        if halo:
            extra = dict(stroke=WHITE, stroke_width=4 if halo is True else halo, stroke_linejoin='round',
                         paint_order='stroke')
        self.add('<text%s>%s</text>' % (attrs(dict(
            id=self._id(id), cls=cls, x=float(x), y=float(y), font_family=MONO if mono else None,
            font_size=size, font_weight=weight, fill=fill, text_anchor=anchor if anchor != 'start' else None,
            letter_spacing=ls, transform=transform, dominant_baseline=baseline, **extra, **a)), esc(s)))

    def tspans(self, x, y, parts, size=13, anchor='start', id=None, cls=None, halo=False, **a):
        """parts: list of (text, dict(mono, weight, fill))"""
        inner = ''
        for t, st in parts:
            inner += '<tspan%s>%s</tspan>' % (attrs(dict(font_family=MONO if st.get('mono') else None,
                                                          font_weight=st.get('weight'), fill=st.get('fill'),
                                                          font_size=st.get('size'))), esc(t))
        extra = dict(stroke=WHITE, stroke_width=4, stroke_linejoin='round', paint_order='stroke') if halo else {}
        self.add('<text%s>%s</text>' % (attrs(dict(id=self._id(id), cls=cls, x=float(x), y=float(y),
                                                   font_size=size, fill=INK,
                                                   text_anchor=anchor if anchor != 'start' else None,
                                                   **extra, **a)), inner))

    # ------------------------------------------------------------------ drafting helpers
    def arrowhead(self, x, y, ang, L=8.0, half=2.1, fill=INK, cls=None):
        """filled fine arrowhead with its tip at (x, y) pointing along ang (radians)"""
        bx, by = x - L * math.cos(ang), y - L * math.sin(ang)
        px, py = -math.sin(ang) * half, math.cos(ang) * half
        self.path(P((x, y), (bx + px, by + py), (bx - px, by - py), close=True), w=0, stroke='none', fill=fill,
                  cls=cls)

    def arrow(self, pts, w=W2, stroke=INK, head=True, tail=False, dash=None, cls=None, id=None, L=8.0,
              half=2.1):
        with self.g(id=id, cls=cls):
            self.path(P(*pts), w=w, stroke=stroke, dash=dash, cls='draw')
            if head:
                (x0, y0), (x1, y1) = pts[-2], pts[-1]
                self.arrowhead(x1, y1, math.atan2(y1 - y0, x1 - x0), fill=stroke, L=L, half=half)
            if tail:
                (x0, y0), (x1, y1) = pts[1], pts[0]
                self.arrowhead(x1, y1, math.atan2(y1 - y0, x1 - x0), fill=stroke, L=L, half=half)

    def dim(self, p1, p2, off, label, id=None, ext_gap=4, ext_over=5, size=12, text_off=6, flip_text=False,
            ext=True, label_at=0.5, cls='dim'):
        """aligned linear dimension between p1 and p2, dimension line offset by `off` (perpendicular,
        positive = left of p1->p2 in screen space)"""
        (x1, y1), (x2, y2) = p1, p2
        L = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        nx, ny = uy, -ux                       # left normal (screen coords, y down)
        a1 = (x1 + nx * off, y1 + ny * off)
        a2 = (x2 + nx * off, y2 + ny * off)
        sgn = 1 if off >= 0 else -1
        with self.g(id=id, cls=cls):
            if ext:
                for (px, py), (ax, ay) in ((p1, a1), (p2, a2)):
                    self.line(px + nx * ext_gap * sgn, py + ny * ext_gap * sgn, ax + nx * ext_over * sgn,
                              ay + ny * ext_over * sgn, w=W3, cls='draw')
            self.line(*a1, *a2, w=W3, cls='draw')
            ang = math.atan2(uy, ux)
            self.arrowhead(*a1, ang + math.pi, L=7.5, half=1.7)
            self.arrowhead(*a2, ang, L=7.5, half=1.7)
            mx, my = a1[0] + (a2[0] - a1[0]) * label_at, a1[1] + (a2[1] - a1[1]) * label_at
            deg = math.degrees(ang)
            deg = (deg + 180) % 360 - 180
            if deg > 89.9:
                deg -= 180
            elif deg <= -90.1:
                deg += 180
            ox, oy = nx * sgn, ny * sgn            # outward (away from the object)
            if flip_text:
                ox, oy = -ox, -oy
            tx, ty = mx + ox * text_off, my + oy * text_off
            upx, upy = math.sin(math.radians(deg)), -math.cos(math.radians(deg))
            base = 'auto' if ox * upx + oy * upy > 0 else 'hanging'
            self.text(tx, ty, label, size=size, mono=True, anchor='middle', halo=True, baseline=base,
                      transform='rotate(%s %s %s)' % (n(deg), n(tx), n(ty)) if abs(deg) > 1e-6 else None,
                      cls='dim-label')

    def centreline(self, x1, y1, x2, y2, w=W3, stroke=INK, id=None, cls='cl'):
        self.line(x1, y1, x2, y2, w=w, stroke=stroke, dash=DASH_CENTRE, id=id, cls=cls)

    def callout(self, num, x, y, tx=None, ty=None, accent=False, r=10.5, id=None, elbow=None, dot=True,
                size=11.5):
        """circled callout number at (x, y) with a leader to the target (tx, ty)"""
        col = ACC if accent else INK
        with self.g(id=id, cls='callout'):
            if tx is not None:
                pts = [(x, y)] + ([elbow] if elbow else []) + [(tx, ty)]
                (ax, ay), (bx, by) = pts[0], pts[1]
                Ld = math.hypot(bx - ax, by - ay) or 1
                pts[0] = (ax + (bx - ax) / Ld * r, ay + (by - ay) / Ld * r)
                self.path(P(*pts), w=W3 if not accent else W2, stroke=col, cls='leader draw')
                if dot:
                    self.circle(tx, ty, 1.9, w=0, stroke='none', fill=col)
            if accent:
                self.circle(x, y, r, w=0, stroke='none', fill=ACC, cls='bubble')
                self.text(x, y + 0.5, num, size=size, weight=700, fill=WHITE, anchor='middle', baseline='central')
            else:
                self.circle(x, y, r, w=W2, stroke=INK, fill=WHITE, cls='bubble')
                self.text(x, y + 0.5, num, size=size, weight=700, fill=INK, anchor='middle', baseline='central')

    def label(self, x, y, title, sub=None, anchor='start', size=13, sub_size=11, id=None, accent=False,
              sub_mono=True, halo=True, cls='label'):
        with self.g(id=id, cls=cls):
            self.text(x, y, title, size=size, weight=650, anchor=anchor, fill=ACC if accent else INK, halo=halo)
            if sub:
                self.text(x, y + size + 3, sub, size=sub_size, mono=sub_mono, weight=500, fill=INK3,
                          anchor=anchor, halo=halo)

    def kicker(self, x, y, s, anchor='start', fill=INK, size=11, id=None):
        self.text(x, y, s, size=size, weight=700, fill=fill, anchor=anchor, ls='0.14em', upper=True, id=id,
                  cls='kicker')

    # ------------------------------------------------------------------ fills
    def std_defs(self):
        p = self.pfx
        self.defs.append(
            '<pattern id="%s-hatch" width="4" height="4" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="%s" stroke-width="0.6"/>'
            '</pattern>' % (p, INK))
        self.defs.append(
            '<pattern id="%s-hatchf" width="4" height="4" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><rect width="4" height="4" fill="%s"/><line x1="0" y1="0" x2="0" '
            'y2="4" stroke="%s" stroke-width="0.6"/></pattern>' % (p, F1, INK))
        self.defs.append(
            '<pattern id="%s-hatchb" width="4" height="4" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(-45)"><line x1="0" y1="0" x2="0" y2="4" stroke="%s" stroke-width="0.6"/>'
            '</pattern>' % (p, INK))
        self.defs.append(
            '<pattern id="%s-hatcha" width="4" height="4" patternUnits="userSpaceOnUse" '
            'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="%s" stroke-width="0.6"/>'
            '</pattern>' % (p, ACC))
        self.defs.append(
            '<pattern id="%s-dots" width="6" height="6" patternUnits="userSpaceOnUse">'
            '<circle cx="3" cy="3" r="0.75" fill="%s"/></pattern>' % (p, INK))

    def hatch(self, kind=''):
        return 'url(#%s-hatch%s)' % (self.pfx, kind)

    # ------------------------------------------------------------------ sheet
    def sheet(self, num, title, sub, extra=None, total=13, tb_w=420):
        """drawing frame with zone marks + compact title block (bottom-right)"""
        W, H = self.w, self.h
        with self.g(id=self.pfx + '-sheet', cls='sheet'):
            self.rect(12, 12, W - 24, H - 24, w=W3)
            self.rect(28, 28, W - 56, H - 56, w=W2)
            cols = 8
            for i in range(cols + 1):
                x = 28 + (W - 56) * i / cols
                if 0 < i < cols:
                    self.line(x, 12, x, 28, w=W3)
                    self.line(x, H - 28, x, H - 12, w=W3)
            for i in range(cols):
                x = 28 + (W - 56) * (i + .5) / cols
                self.text(x, 23.5, str(i + 1), size=8.5, mono=True, fill=INK4, anchor='middle')
                self.text(x, H - 16.5, str(i + 1), size=8.5, mono=True, fill=INK4, anchor='middle')
            rows = 'ABCD'
            for i in range(len(rows) + 1):
                y = 28 + (H - 56) * i / len(rows)
                if 0 < i < len(rows):
                    self.line(12, y, 28, y, w=W3)
                    self.line(W - 28, y, W - 12, y, w=W3)
            for i, c in enumerate(rows):
                y = 28 + (H - 56) * (i + .5) / len(rows) + 3
                self.text(20, y, c, size=8.5, mono=True, fill=INK4, anchor='middle')
                self.text(W - 20, y, c, size=8.5, mono=True, fill=INK4, anchor='middle')
            # title block
            bw, bh = tb_w, 66
            x0, y0 = W - 28 - bw, H - 28 - bh
            with self.g(id=self.pfx + '-titleblock', cls='titleblock'):
                self.rect(x0, y0, bw, bh, w=W2, fill=WHITE)
                c1 = x0 + bw - 112
                self.line(c1, y0, c1, y0 + bh, w=W3)
                self.line(x0, y0 + 22, x0 + bw, y0 + 22, w=W3)
                self.line(c1, y0 + 44, x0 + bw, y0 + 44, w=W3)
                self.text(x0 + 10, y0 + 15, 'Phalanx Twin · schematic', size=10, weight=700, ls='0.12em',
                          upper=True)
                self.text(x0 + 10, y0 + 40, title, size=14, weight=650)
                self.text(x0 + 10, y0 + 57, sub, size=10.5, mono=True, fill=INK3)
                self.text(c1 + 9, y0 + 15, 'PHX-ILL-%02d' % num, size=10.5, mono=True, weight=600)
                self.text(c1 + 9, y0 + 37, 'SHEET %d / %d' % (num, total), size=10.5, mono=True, fill=INK3)
                self.text(c1 + 9, y0 + 59, extra or 'REV A · NTS', size=10.5, mono=True, fill=INK3)

    # ------------------------------------------------------------------ output
    def render(self):
        head = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
                'id="ill-%s" class="phx-ill" font-family="%s" text-rendering="geometricPrecision" '
                'role="img" aria-labelledby="ill-%s-title ill-%s-desc">' % (
                    self.w, self.h, self.w, self.h, self.pfx, esc(SANS), self.pfx, self.pfx))
        body = [head,
                '  <title id="ill-%s-title">%s</title>' % (self.pfx, esc(self.title)),
                '  <desc id="ill-%s-desc">%s</desc>' % (self.pfx, esc(self.desc)),
                '  <defs>' + ''.join(self.defs) + '</defs>',
                '  <rect id="%s-bg" width="%d" height="%d" fill="#FFFFFF"/>' % (self.pfx, self.w, self.h)]
        return '\n'.join(body + self.out + ['</svg>', ''])

    def save(self, name):
        s = self.render()
        for d in (OUT_FILM, OUT_SCREENS):
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, name), 'w') as fh:
                fh.write(s)
        return len(s)


class Iso:
    """3/4 view used by the object plates (LRU, server, recorder): P(u, v, w) = O + u U + v V + w W.
    Front face = v-min plane (faces down-left), side face = u-max plane (faces down-right), top = w-max."""
    U = (0.906, 0.423)
    V = (0.819 * 0.74, -0.574 * 0.74)
    W = (0.0, -1.0)

    def __init__(self, ox, oy, k=1.0):
        self.o = (ox, oy)
        self.k = k

    def __call__(self, u, v, w):
        k = self.k
        return (self.o[0] + k * (u * self.U[0] + v * self.V[0] + w * self.W[0]),
                self.o[1] + k * (u * self.U[1] + v * self.V[1] + w * self.W[1]))

    def front(self, v=0.0):
        o = self(0, v, 0)
        k = self.k
        return Affine(k * self.U[0], k * self.U[1], k * self.W[0], k * self.W[1], o[0], o[1])

    def side(self, u):
        o = self(u, 0, 0)
        k = self.k
        return Affine(k * self.V[0], k * self.V[1], k * self.W[0], k * self.W[1], o[0], o[1])

    def top(self, w):
        o = self(0, 0, w)
        k = self.k
        return Affine(k * self.U[0], k * self.U[1], k * self.V[0], k * self.V[1], o[0], o[1])

    def box(self, doc, u0, u1, v0, v1, w0, w1, fills=(WHITE, F2, F1), w=W1, ids=(None, None, None), cls='draw',
            stroke=INK):
        P_ = self
        top = [P_(u0, v0, w1), P_(u1, v0, w1), P_(u1, v1, w1), P_(u0, v1, w1)]
        side = [P_(u1, v0, w0), P_(u1, v1, w0), P_(u1, v1, w1), P_(u1, v0, w1)]
        front = [P_(u0, v0, w0), P_(u1, v0, w0), P_(u1, v0, w1), P_(u0, v0, w1)]
        doc.path(P(*top, close=True), w=w, fill=fills[2], cls=cls, id=ids[2], stroke=stroke)
        doc.path(P(*side, close=True), w=w, fill=fills[1], cls=cls, id=ids[1], stroke=stroke)
        doc.path(P(*front, close=True), w=w, fill=fills[0], cls=cls, id=ids[0], stroke=stroke)


def face_text_matrix(M, p, q):
    """SVG transform that writes text on a face (affine M of face-local p, q-up coordinates) at (p, q)"""
    a, b, c, d_, e, f = M.m
    x, y = M(p, q)
    return 'matrix(%s %s %s %s %s %s)' % (n(a), n(b), n(-c), n(-d_), n(x), n(y))
