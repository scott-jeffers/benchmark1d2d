"""Tiny SVG chart kit for the benchmark1d2d site.

Every chart is inline SVG whose colours come from CSS custom properties, so
it follows the page's light/dark theme and needs no JavaScript. Each chart
carries a <title> and an aria-label for screen readers, and every data mark
has a <title> tooltip.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

W, H = 760, 340
PAD_L, PAD_R, PAD_T, PAD_B = 64, 20, 18, 46


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not math.isfinite(lo) or not math.isfinite(hi):
        return []
    if hi == lo:
        hi = lo + 1.0
    span = hi - lo
    raw = span / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + step * 1e-9:
        ticks.append(round(v, 12))
        v += step
    return ticks


def fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1e5:
        return f"{v:,.0f}"
    if a < 1e-3:
        return f"{v:.2g}"
    if a >= 100:
        return f"{v:,.0f}"
    if a >= 1:
        return f"{v:.4g}"
    return f"{v:.3g}"


@dataclass
class Series:
    x: Sequence[float]
    y: Sequence[float]
    label: str
    css: str = "s-water"  # class controlling stroke/fill colour
    kind: str = "line"  # line | dots | area | step
    dash: bool = False
    width: float = 2.0


@dataclass
class Axis:
    label: str
    log: bool = False
    lo: float | None = None
    hi: float | None = None
    ticks: list[float] | None = None


@dataclass
class Chart:
    title: str
    x: Axis
    y: Axis
    series: list[Series] = field(default_factory=list)
    hlines: list[tuple[float, str]] = field(default_factory=list)  # (y, label)
    vlines: list[tuple[float, str]] = field(default_factory=list)
    floor: list[tuple[Sequence[float], Sequence[float]]] = field(default_factory=list)  # bed polygons
    width: int = W
    height: int = H
    legend: bool = True
    note: str | None = None

    # ── scales ──────────────────────────────────────────────────────────────
    def _extent(self, axis: Axis, values: list[np.ndarray]) -> tuple[float, float]:
        finite = [v[np.isfinite(v)] for v in values if len(v)]
        finite = [v for v in finite if len(v)]
        if axis.log:
            finite = [v[v > 0] for v in finite]
        lo = axis.lo if axis.lo is not None else (min(float(v.min()) for v in finite) if finite else 0.0)
        hi = axis.hi if axis.hi is not None else (max(float(v.max()) for v in finite) if finite else 1.0)
        if hi == lo:
            hi = lo + (abs(lo) * 0.1 or 1.0)
        if not axis.log and axis.lo is None and axis.hi is None:
            pad = 0.04 * (hi - lo)
            lo, hi = lo - pad, hi + pad
        return lo, hi

    def render(self) -> str:
        xs = [np.asarray(s.x, float) for s in self.series] + [np.asarray(f[0], float) for f in self.floor]
        ys = [np.asarray(s.y, float) for s in self.series] + [np.asarray(f[1], float) for f in self.floor]
        ys += [np.array([h[0]]) for h in self.hlines]
        x0, x1 = self._extent(self.x, xs)
        y0, y1 = self._extent(self.y, ys)
        iw = self.width - PAD_L - PAD_R
        ih = self.height - PAD_T - PAD_B

        def sx(v):
            v = np.asarray(v, float)
            if self.x.log:
                return PAD_L + (np.log10(v) - math.log10(x0)) / (math.log10(x1) - math.log10(x0)) * iw
            return PAD_L + (v - x0) / (x1 - x0) * iw

        def sy(v):
            v = np.asarray(v, float)
            if self.y.log:
                return PAD_T + ih - (np.log10(v) - math.log10(y0)) / (math.log10(y1) - math.log10(y0)) * ih
            return PAD_T + ih - (v - y0) / (y1 - y0) * ih

        out = [
            f'<svg class="chart" viewBox="0 0 {self.width} {self.height}" role="img" aria-label="{esc(self.title)}" preserveAspectRatio="xMidYMid meet">',
            f"<title>{esc(self.title)}</title>",
        ]
        # grid + ticks
        xt = self.x.ticks or (_log_ticks(x0, x1) if self.x.log else nice_ticks(x0, x1, 6))
        yt = self.y.ticks or (_log_ticks(y0, y1) if self.y.log else nice_ticks(y0, y1, 5))
        out.append('<g class="grid">')
        for t in yt:
            if y0 <= t <= y1:
                yy = float(sy(t))
                out.append(f'<line x1="{PAD_L}" x2="{PAD_L + iw}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
                out.append(f'<text class="tick" x="{PAD_L - 8}" y="{yy + 4:.1f}" text-anchor="end">{esc(fmt(t))}</text>')
        for t in xt:
            if x0 <= t <= x1:
                xx = float(sx(t))
                out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{PAD_T}" y2="{PAD_T + ih}" class="v"/>')
                out.append(f'<text class="tick" x="{xx:.1f}" y="{PAD_T + ih + 18}" text-anchor="middle">{esc(fmt(t))}</text>')
        out.append("</g>")
        out.append(f'<text class="axis-label" x="{PAD_L + iw / 2:.0f}" y="{self.height - 6}" text-anchor="middle">{esc(self.x.label)}</text>')
        out.append(
            f'<text class="axis-label" transform="translate(14 {PAD_T + ih / 2:.0f}) rotate(-90)" text-anchor="middle">{esc(self.y.label)}</text>'
        )
        out.append(f'<clipPath id="clip-{id(self)}"><rect x="{PAD_L}" y="{PAD_T}" width="{iw}" height="{ih}"/></clipPath>')
        out.append(f'<g clip-path="url(#clip-{id(self)})">')
        for fx, fy in self.floor:
            fx = np.asarray(fx, float)
            fy = np.asarray(fy, float)
            pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(sx(fx), sy(fy)))
            out.append(
                f'<polygon class="bed" points="{float(sx(fx[0])):.1f},{PAD_T + ih} {pts} {float(sx(fx[-1])):.1f},{PAD_T + ih}"/>'
            )
        for k, s in enumerate(self.series):
            x = np.asarray(s.x, float)
            y = np.asarray(s.y, float)
            ok = np.isfinite(x) & np.isfinite(y)
            if self.x.log:
                ok &= x > 0
            if self.y.log:
                ok &= y > 0
            x, y = x[ok], y[ok]
            if not len(x):
                continue
            px, py = sx(x), sy(y)
            dash = ' stroke-dasharray="6 4"' if s.dash else ""
            if s.kind == "dots":
                out.append(f'<g class="{s.css} dots">')
                for a, b, vx, vy in zip(px, py, x, y):
                    out.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.2"><title>{esc(s.label)}: {fmt(vx)}, {fmt(vy)}</title></circle>')
                out.append("</g>")
            elif s.kind == "area":
                pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))
                base = float(sy(max(y0, 0.0) if not self.y.log else y0))
                out.append(f'<polygon class="{s.css} area" points="{px[0]:.1f},{base:.1f} {pts} {px[-1]:.1f},{base:.1f}"/>')
                out.append(f'<polyline class="{s.css} line" points="{pts}" style="stroke-width:{s.width}"{dash}/>')
            else:
                if s.kind == "step":
                    sxs, sys_ = [px[0]], [py[0]]
                    for i in range(1, len(px)):
                        sxs += [px[i], px[i]]
                        sys_ += [py[i - 1], py[i]]
                    px, py = np.array(sxs), np.array(sys_)
                pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))
                out.append(f'<polyline class="{s.css} line draw" style="--i:{k};stroke-width:{s.width}" points="{pts}"{dash}><title>{esc(s.label)}</title></polyline>')
        out.append("</g>")
        for i, (yv, lab) in enumerate(self.hlines):
            yy = float(sy(yv))
            out.append(f'<line class="ref-line" x1="{PAD_L}" x2="{PAD_L + iw}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
            # alternate sides so labels on nearby lines do not collide
            if i % 2 == 0:
                out.append(f'<text class="ref-label" x="{PAD_L + iw - 4}" y="{yy - 6:.1f}" text-anchor="end">{esc(lab)}</text>')
            else:
                out.append(f'<text class="ref-label" x="{PAD_L + 6}" y="{yy + 15:.1f}">{esc(lab)}</text>')
        for xv, lab in self.vlines:
            xx = float(sx(xv))
            out.append(f'<line class="ref-line" x1="{xx:.1f}" x2="{xx:.1f}" y1="{PAD_T}" y2="{PAD_T + ih}"/>')
            out.append(f'<text class="ref-label" x="{xx + 5:.1f}" y="{PAD_T + 12}">{esc(lab)}</text>')
        out.append(f'<rect class="frame" x="{PAD_L}" y="{PAD_T}" width="{iw}" height="{ih}"/>')
        out.append("</svg>")
        legend = ""
        if self.legend and len(self.series) > 1:
            items = "".join(
                f'<li><span class="key {s.css} {"key-dots" if s.kind == "dots" else ""} {"key-dash" if s.dash else ""}"></span>{esc(s.label)}</li>'
                for s in self.series
            )
            legend = f'<ul class="legend">{items}</ul>'
        note = f'<p class="chart-note">{esc(self.note)}</p>' if self.note else ""
        return f'<figure class="figure">{"".join(out)}{legend}{note}</figure>'


def _log_ticks(lo: float, hi: float) -> list[float]:
    a, b = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
    mult = (1, 2, 5) if b - a <= 3 else (1,)
    return [m * 10.0**k for k in range(a, b + 1) for m in mult if lo <= m * 10.0**k <= hi]


def hbars(title: str, rows: list[tuple[str, list[tuple[float, str, str]]]], unit: str = "", width: int = W, link: dict[str, str] | None = None) -> str:
    """Horizontal stacked bars: rows of (label, [(value, css, segment_label), …])."""
    row_h, gap, lab_w = 26, 10, 220
    height = len(rows) * (row_h + gap) + 10
    total_max = max((sum(v for v, _, _ in segs) for _, segs in rows), default=1) or 1
    iw = width - lab_w - 70
    out = [f'<svg class="chart bars" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>']
    for i, (label, segs) in enumerate(rows):
        y = 6 + i * (row_h + gap)
        lab = esc(label)
        if link and label in link:
            lab = f'<a href="{esc(link[label])}">{lab}</a>'
        out.append(f'<text class="bar-label" x="{lab_w - 10}" y="{y + row_h / 2 + 5}" text-anchor="end">{lab}</text>')
        x = lab_w
        for v, css, seg_label in segs:
            w = iw * v / total_max
            if w <= 0:
                continue
            out.append(f'<rect class="{css}" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{row_h}" rx="3"><title>{esc(seg_label)}: {fmt(v)}{esc(unit)}</title></rect>')
            if w > 26:
                out.append(f'<text class="bar-value" x="{x + w / 2:.1f}" y="{y + row_h / 2 + 5}" text-anchor="middle">{fmt(v)}</text>')
            x += w
        out.append(f'<text class="bar-total" x="{x + 8:.1f}" y="{y + row_h / 2 + 5}">{fmt(sum(v for v, _, _ in segs))}{esc(unit)}</text>')
    out.append("</svg>")
    return f'<figure class="figure">{"".join(out)}</figure>'


def legend(items: list[tuple[str, str]]) -> str:
    return '<ul class="legend">' + "".join(f'<li><span class="key {css}"></span>{esc(lab)}</li>' for lab, css in items) + "</ul>"
