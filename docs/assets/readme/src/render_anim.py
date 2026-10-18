"""Render anim/<name>.html into ../<name>.gif.

Each frame is one headless-Chrome screenshot of anim/<name>.html?t=<seconds>; the page draws time t exactly, so
frames are deterministic.  Usage: python3 render_anim.py <name> <seconds> [fps]
"""
import pathlib, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from fonts import css

HERE = pathlib.Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1200, 560


def main(name, seconds, fps=12):
    (HERE / "build").mkdir(exist_ok=True)
    (HERE / "build/fonts.css").write_text(css())
    frames = HERE / "build" / f"frames-{name}"
    shutil.rmtree(frames, ignore_errors=True); frames.mkdir()
    n = int(seconds * fps)
    prof = tempfile.mkdtemp()

    def shoot(i):
        subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={W},{H}", "--allow-file-access-from-files", f"--user-data-dir={prof}/{i}",
                        "--virtual-time-budget=500", f"--screenshot={frames}/f{i:04d}.png",
                        f"file://{HERE}/anim/{name}.html?t={i / fps:.4f}"], capture_output=True, check=True)

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(shoot, range(n)))
    for k in range(int(fps * 2.5)):                       # hold the last frame
        shutil.copy(frames / f"f{n - 1:04d}.png", frames / f"f{n + k:04d}.png")
    out = HERE.parent / f"{name}.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", f"{frames}/f%04d.png", "-vf",
                    "split[a][b];[a]palettegen=max_colors=128:stats_mode=full[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    str(out)], check=True)
    shutil.rmtree(prof, ignore_errors=True)
    print(out.name, f"{out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 12)
