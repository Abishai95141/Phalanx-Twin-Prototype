"""style-key.svg — the style system of the plate library drawn with the same kit (line weights, hatching, line
types, dimension, callouts, fills, accent, blue, type).  Shown on the contact sheet next to plate 13."""
from lib import *


def build():
    d = Doc('key', 'Plate library — style key', 'Line weights, hatching, line types, dimensions, callouts, '
            'fills, colours and type used by every Phalanx Twin illustration plate.')
    d.std_defs()
    x0 = 96
    d.text(x0, 120, 'STYLE KEY · ONE SYSTEM FOR EVERY PLATE', size=13, weight=700, ls='0.14em')
    d.text(x0, 146, 'white sheet · ink line art · one accent for the subject · blue for data', size=13, mono=True,
           fill=INK3)
    # line weights
    with d.g(id='key-weights'):
        d.kicker(x0, 214, 'Line weights')
        for i, (w, t) in enumerate(((W1, '1.5  primary outline'), (W2, '0.9  secondary detail'),
                                    (W3, '0.6  hatching · construction'))):
            y = 254 + i * 40
            d.line(x0, y, x0 + 220, y, w=w)
            d.text(x0 + 246, y + 5, t, size=14, mono=True)
    # line types
    with d.g(id='key-types'):
        d.kicker(x0, 426, 'Line types')
        rows = [(DASH_CENTRE, 'centre line'), (DASH_HIDDEN, 'hidden detail'), (DASH_PHANTOM, 'phantom / alternate')]
        for i, (dash, t) in enumerate(rows):
            y = 466 + i * 40
            d.line(x0, y, x0 + 220, y, w=W3 if i == 0 else W2, dash=dash)
            d.text(x0 + 246, y + 5, t, size=14, mono=True)
    # hatching + dimension + callouts
    with d.g(id='key-hatch'):
        d.kicker(620, 214, 'Section hatching · 45° · 4 px')
        d.rect(620, 236, 150, 96, w=W1, fill=d.hatch())
        d.rect(790, 236, 150, 96, w=W1, stroke=ACC, fill=d.hatch('a'))
        d.text(620, 356, 'cut material', size=13, mono=True, fill=INK3)
        d.text(790, 356, 'subject (accent)', size=13, mono=True, fill=INK3)
    with d.g(id='key-dim'):
        d.kicker(620, 426, 'Dimension')
        d.dim((620, 500), (940, 500), 0, '13.2 m', ext=False, size=14)
        d.line(620, 470, 620, 512, w=W3)
        d.line(940, 470, 940, 512, w=W3)
    with d.g(id='key-callouts'):
        d.kicker(620, 566, 'Callouts')
        d.callout('1', 640, 606, 720, 640)
        d.text(660, 611, 'part', size=14)
        d.callout('4', 800, 606, 880, 640, accent=True)
        d.text(820, 611, 'subject', size=14, fill=ACC)
    # colour + fills
    with d.g(id='key-colours'):
        d.kicker(1110, 214, 'Colour carries meaning')
        sw = [(INK, '#0B0D10', 'ink · lines and type'), (F1, '#F7F7F5', 'light fill'), (F2, '#EFEFEC', 'light fill'),
              (ACC, '#E8743B', 'accent · the subject only'), (BLUE, '#2563C9', 'blue · data, evidence, signal')]
        for i, (c, hx, t) in enumerate(sw):
            y = 240 + i * 52
            d.rect(1110, y, 44, 36, rx=6, w=W2 if c in (F1, F2) else 0, stroke=INK if c in (F1, F2) else 'none',
                   fill=c)
            d.text(1172, y + 16, hx, size=14, mono=True, weight=600)
            d.text(1172, y + 32, t, size=12, mono=True, fill=INK3)
    with d.g(id='key-type'):
        d.kicker(1110, 566, 'Type')
        d.text(1110, 604, 'Manrope · labels', size=20, weight=650)
        d.text(1110, 636, 'JetBrains Mono · ids, dims', size=17, mono=True)
    with d.g(id='key-notes'):
        d.line(x0, 700, 1504, 700, w=W3)
        notes = ['viewBox 1600 × 900 · 1 : 1 at 1600 px wide · strokes in px at 1 : 1',
                 'ids prefixed per plate (ac-, hyd-, pump-, eng-, mlg-, chute-, lru-, srv-, dl-, gate-, chain-, loop-, tool-)',
                 'class "draw" on stroke paths for draw-on · title block + frame grouped as #<prefix>-sheet (hideable)',
                 'no gradients, blur, shadows, raster or text-as-image · every value is from the data layer or the screens']
        for i, t in enumerate(notes):
            d.text(x0, 734 + i * 24, t, size=13, mono=True, fill=INK3)
    return d


if __name__ == '__main__':
    print(build().save('style-key.svg'))
