"""Minimal dependency-free SVG line charts (the build environment has no plotting library).

`panel(...)` returns an SVG group for one chart; `page(panels, ...)` lays groups out on a grid and returns the
document text. Axes may be logarithmic. Colours are fixed per series index.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

COLOURS = ("#1f5fa8", "#c2410c", "#15803d", "#7c3aed", "#6b7280", "#b91c1c", "#0e7490")


def _ticks(lo: float, hi: float, log: bool) -> list[float]:
    if log:
        a, b = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
        mult = (1, 2, 5) if b - a <= 2 else (1,)
        return [m * 10.0**e for e in range(a, b + 1) for m in mult]
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / 4)) if span > 0 else 1.0
    for m in (1, 2, 5, 10):
        if span / (step * m) <= 6:
            step *= m
            break
    start = math.ceil(lo / step) * step
    return [round(start + i * step, 10) for i in range(int((hi - start) / step) + 1)]


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    if abs(v) >= 1000 or abs(v) < 0.01:
        return f"{v:.0e}"
    return f"{v:g}"


def panel(
    series: Sequence[tuple[str, np.ndarray, np.ndarray]],
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    xlog: bool = False,
    ylog: bool = False,
    ylim: tuple[float, float] | None = None,
    hlines: Sequence[tuple[str, float]] = (),
    w: int = 460,
    h: int = 300,
) -> str:
    """One chart as an SVG <g> (origin at 0, 0; size w x h)."""
    L, R, T, B = 62, 12, 26, 44
    xs = np.concatenate([np.asarray(s[1], float) for s in series])
    ys = np.concatenate([np.asarray(s[2], float) for s in series] + [np.array([v for _, v in hlines])])
    ok_x = np.isfinite(xs) & ((xs > 0) if xlog else True)
    ok_y = np.isfinite(ys) & ((ys > 0) if ylog else True)
    x0, x1 = float(xs[ok_x].min()), float(xs[ok_x].max())
    if ylim is None:
        y0, y1 = float(ys[ok_y].min()), float(ys[ok_y].max())
        if not ylog:
            pad = 0.05 * (y1 - y0 or 1.0)
            y0, y1 = y0 - pad, y1 + pad
    else:
        y0, y1 = ylim

    def fx(v):
        a, b, u = (math.log10(x0), math.log10(x1), math.log10(v)) if xlog else (x0, x1, v)
        return L + (u - a) / ((b - a) or 1) * (w - L - R)

    def fy(v):
        a, b, u = (math.log10(y0), math.log10(y1), math.log10(v)) if ylog else (y0, y1, v)
        return h - B - (u - a) / ((b - a) or 1) * (h - T - B)

    out = [f'<rect x="{L}" y="{T}" width="{w - L - R}" height="{h - T - B}" fill="none" stroke="#999"/>']
    out.append(
        f'<text x="{w / 2}" y="16" text-anchor="middle" font-size="13" font-weight="600">{title}</text>'
    )
    out.append(f'<text x="{(L + w - R) / 2}" y="{h - 8}" text-anchor="middle" font-size="11">{xlabel}</text>')
    out.append(
        f'<text x="14" y="{(T + h - B) / 2}" text-anchor="middle" font-size="11" '
        f'transform="rotate(-90 14 {(T + h - B) / 2})">{ylabel}</text>'
    )
    for t in _ticks(x0, x1, xlog):
        if x0 <= t <= x1:
            X = fx(t)
            out.append(f'<line x1="{X:.1f}" y1="{h - B}" x2="{X:.1f}" y2="{h - B + 4}" stroke="#666"/>')
            out.append(
                f'<text x="{X:.1f}" y="{h - B + 15}" text-anchor="middle" font-size="10">{_fmt(t)}</text>'
            )
    for t in _ticks(y0, y1, ylog):
        if y0 <= t <= y1:
            Y = fy(t)
            out.append(f'<line x1="{L - 4}" y1="{Y:.1f}" x2="{w - R}" y2="{Y:.1f}" stroke="#eee"/>')
            out.append(f'<text x="{L - 6}" y="{Y + 3:.1f}" text-anchor="end" font-size="10">{_fmt(t)}</text>')
    for k, (name, v) in enumerate(hlines):
        if y0 <= v <= y1:
            Y = fy(v)
            out.append(
                f'<line x1="{L}" y1="{Y:.1f}" x2="{w - R}" y2="{Y:.1f}" stroke="{COLOURS[k % 7]}" '
                'stroke-dasharray="4 3"/>'
            )
            out.append(f'<text x="{w - R - 2}" y="{Y - 3:.1f}" text-anchor="end" font-size="9">{name}</text>')
    for k, (name, x, y) in enumerate(series):
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        m = np.isfinite(x) & np.isfinite(y) & ((x > 0) if xlog else True) & ((y > 0) if ylog else True)
        m &= (y >= y0) & (y <= y1)
        pts = " ".join(f"{fx(a):.1f},{fy(b):.1f}" for a, b in zip(x[m], y[m], strict=True))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{COLOURS[k % 7]}" stroke-width="1.4"/>')
        out.append(
            f'<text x="{L + 6}" y="{T + 13 + 12 * k}" font-size="10" fill="{COLOURS[k % 7]}">{name}</text>'
        )
    return "\n".join(out)


def page(panels: Sequence[str], cols: int = 2, w: int = 460, h: int = 300, title: str = "") -> str:
    rows = math.ceil(len(panels) / cols)
    top = 24 if title else 0
    W, H = cols * w, rows * h + top
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
    ]
    if title:
        parts.append(f'<text x="{W / 2}" y="17" text-anchor="middle" font-size="14">{title}</text>')
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        parts.append(f'<g transform="translate({c * w},{top + r * h})">{p}</g>')
    parts.append("</svg>")
    return "\n".join(parts)
