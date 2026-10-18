"""Build tour.gif — the product walk-through — from screenshots of the live deployment.

Screens are captured with headless Chrome by shoot_screens.sh (2x, 1440x900 CSS pixels) into shots/.
Run: python3 docs/assets/readme/src/make_tour.py
"""
import pathlib, subprocess, tempfile
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SHOTS = HERE / "shots"
OUT = HERE.parent

STEPS = [
    ("readiness", "Readiness", "6 of 8 aircraft mission capable — and why the other two are not"),
    ("decisions", "Decisions", "1,192 alerts become 9 ranked decisions before 07:45"),
    ("decision", "Recommendation", "Stop removing the pump: +18 pts mission capable in paired simulations"),
    ("why", "Why", "Every piece of evidence was received before the 06:00 snapshot"),
    ("workbench", "Workbench", "The alarm follows the aircraft, not the pump — and the best next test"),
    ("twin", "Aircraft twin", "One state per aircraft and per part, computed from the twin"),
    ("epoch", "Orders", "Sign, freeze at 07:45, issue through the simulator's gateway at 08:00"),
    ("provenance", "Provenance", "One hash chain an auditor can verify and replay"),
]
W, SH, BAR = 1200, 750, 78
FPS, HOLD, FADE = 10, 30, 5


def font(weight, size):
    ttf = HERE / "build" / "Manrope.ttf"
    if not ttf.exists():
        ttf.parent.mkdir(exist_ok=True)
        f = TTFont(ROOT / "proto/web/assets/fonts/Manrope-var-latin.woff2"); f.flavor = None; f.save(ttf)
    fnt = ImageFont.truetype(str(ttf), size)
    fnt.set_variation_by_axes([weight])
    return fnt


def frame(i, step):
    name, title, text = step
    shot = Image.open(SHOTS / f"{name}.png").convert("RGB").resize((W, SH), Image.LANCZOS)
    im = Image.new("RGB", (W, SH + BAR), "white")
    im.paste(shot, (0, 0))
    d = ImageDraw.Draw(im)
    d.line([(0, SH), (W, SH)], fill="#E6E6E2", width=2)
    # progress segments
    seg = (W - 64 - 7 * 8) / 8
    for k in range(8):
        x = 32 + k * (seg + 8)
        d.rounded_rectangle([x, SH + 14, x + seg, SH + 18], radius=2, fill="#E8743B" if k <= i else "#E6E6E2")
    d.text((32, SH + 30), f"{i + 1}  {title}", font=font(800, 22), fill="#0B0D10")
    tx = 32 + d.textlength(f"{i + 1}  {title}", font=font(800, 22)) + 18
    d.text((tx, SH + 33), text, font=font(500, 19), fill="#4B5563")
    d.text((W - 32, SH + 33), "148.100.99.205", font=font(700, 16), fill="#8A8F98", anchor="ra")
    return im


def main():
    stills = [frame(i, s) for i, s in enumerate(STEPS)]
    with tempfile.TemporaryDirectory() as tmp:
        n = 0
        for i, im in enumerate(stills):
            nxt = stills[(i + 1) % len(stills)]
            for _ in range(HOLD):
                im.save(f"{tmp}/f{n:04d}.png"); n += 1
            for k in range(1, FADE + 1):
                Image.blend(im, nxt, k / (FADE + 1)).save(f"{tmp}/f{n:04d}.png"); n += 1
        out = OUT / "tour.gif"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/f%04d.png",
                        "-vf", "split[a][b];[a]palettegen=max_colors=192:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
                        str(out)], check=True)
        print(out, f"{out.stat().st_size/1e6:.1f} MB, {n} frames")


if __name__ == "__main__":
    main()
