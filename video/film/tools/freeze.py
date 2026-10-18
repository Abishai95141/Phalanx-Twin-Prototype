"""Freeze a scripted product screen into a static HyperFrames sub-composition.

usage: python3 tools/freeze.py <page.html[?query]> <key>   (run from video/film/, screens server on :8137)

- loads http://127.0.0.1:8137/<page> in headless Chrome, lets its scripts run, dumps the DOM;
- strips every <script>, inlines app.css + page <style>s (font URLs rewritten to assets/fonts/);
- prefixes every element id with "<key>-" (icon sprite ids `i-*` are left alone) and fixes #refs;
- removes WebGL canvases (the director mounts a live twin into `#<key>-vp` instead);
- wraps the body in <div data-composition-id="<key>" data-no-timeline> (parent timeline drives it).
"""
import re, subprocess, sys
from pathlib import Path

FILM = Path(__file__).resolve().parents[1]
SCREENS = FILM.parent / "screens"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def dump(url: str) -> str:
    r = subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--window-size=1920,1080",
                        "--force-device-scale-factor=1", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                        "--virtual-time-budget=6000", "--dump-dom", url], capture_output=True, text=True, timeout=120)
    return r.stdout


def main(page: str, key: str) -> None:
    html = dump(f"http://127.0.0.1:8137/{page}")
    if "<body" not in html:
        sys.exit(f"empty dump for {page}")
    head = html[: html.index("<body")]
    body = html[html.index(">", html.index("<body")) + 1: html.rindex("</body>")]
    styles = re.findall(r"<style[^>]*>(.*?)</style>", head, flags=re.S)
    app = (SCREENS / "assets/app.css").read_text()
    css = "\n".join([app] + styles)
    css = css.replace('url("fonts/', 'url("assets/fonts/')
    css = re.sub(r"(?<![-\w])transition\s*:[^;}]+;?", "", css)
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<canvas\b[^>]*>.*?</canvas>", "", body, flags=re.S)
    body = re.sub(r"<canvas\b[^>]*/?>", "", body)

    def pid(m):
        v = m.group(2)
        return m.group(0) if v.startswith("i-") else f'{m.group(1)}="{key}-{v}"'
    body = re.sub(r'\b(id)="([^"]+)"', pid, body)
    body = re.sub(r'\b(href|xlink:href)="#([^"]+)"', lambda m: m.group(0) if m.group(2).startswith("i-") else f'{m.group(1)}="#{key}-{m.group(2)}"', body)
    body = re.sub(r'url\(#([^)]+)\)', lambda m: f"url(#{key}-{m.group(1)})", body)
    # page-level CSS that targets ids must follow the prefix
    css = re.sub(r"#([A-Za-z][\w-]*)", lambda m: m.group(0) if re.fullmatch(r"[0-9A-Fa-f]{3,8}", m.group(1)) or m.group(1).startswith("i-") else f"#{key}-{m.group(1)}", css)
    out = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>
{css}
</style></head><body>
<div id="{key}-root" class="phx-screen" data-composition-id="{key}" data-width="1920" data-height="1080" data-no-timeline>
{body}
</div>
</body></html>
"""
    dst = FILM / "screens" / f"{key}.html"
    dst.write_text(out)
    print(dst, len(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
