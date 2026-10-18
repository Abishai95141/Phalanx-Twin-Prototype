"""Subset the app's fonts (Manrope, JetBrains Mono) and return @font-face CSS with base64 woff2, so the README's
SVGs and animation frames render in the product's typeface wherever GitHub shows them."""
import base64, io, pathlib
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parents[4]
FONTS = ROOT / "proto/web/assets/fonts"
CHARS = "".join(chr(c) for c in range(32, 127)) + "·→←↑↓−–—×≤≥%°•✓✗…’‘“”€₹±≈▲▼●○◆■□▸│─┌┐└┘├┤"


def face(family, file, weight="200 800"):
    font = TTFont(FONTS / file)
    opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["*"]
    sub = subset.Subsetter(opts); sub.populate(text=CHARS); sub.subset(font)
    buf = io.BytesIO(); font.flavor = "woff2"; font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")


def css():
    return face("Manrope", "Manrope-var-latin.woff2") + face("JBMono", "JetBrainsMono-var-latin.woff2", "100 800")


if __name__ == "__main__":
    print(len(css()))
