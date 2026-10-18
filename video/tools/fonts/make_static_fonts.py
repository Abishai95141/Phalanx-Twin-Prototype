"""Make static TTF weights from the brand's variable woff2 fonts (for libass + Manim/Pango).

libass can't select variable-font instances, and the Manrope variable font's default
family name is "Manrope ExtraLight", so we instance fixed weights and rename them.

  woff2_decompress <font>.woff2           # brew 'woff2' (installed with dvisvgm)
  ../../.venv/bin/python -I make_static_fonts.py Manrope-var-latin.ttf Manrope 400:Regular 500:Medium 600:SemiBold 700:Bold
  ../../.venv/bin/python -I make_static_fonts.py JetBrainsMono-var-latin.ttf "JetBrains Mono" 400:Regular 700:Bold
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

src, family, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
for spec in specs:
    wght, style = spec.split(":"); wght = int(wght)
    f = instantiateVariableFont(TTFont(src), {"wght": wght}, inplace=False)
    ribbi = style in ("Regular", "Bold")
    fam1 = family if ribbi else f"{family} {style}"
    sub2 = style if ribbi else "Regular"
    ps = f"{family.replace(' ', '')}-{style}"
    name = f["name"]
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17, 25):
            name.removeNames(nameID=rec.nameID)
    for nid, val in {1: fam1, 2: sub2, 3: f"{ps};static", 4: f"{family} {style}", 6: ps, 16: family, 17: style}.items():
        name.setName(val, nid, 3, 1, 0x409); name.setName(val, nid, 1, 0, 0)
    os2 = f["OS/2"]; os2.usWeightClass = wght
    os2.fsSelection = (os2.fsSelection & ~0b1100001) | (0b100000 if style == "Bold" else 0b1000000)  # BOLD or REGULAR bit
    f["head"].macStyle = 1 if style == "Bold" else 0
    out = f"{ps}.ttf"; f.save(out); print("wrote", out)
