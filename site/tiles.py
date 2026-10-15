"""A small picture for every test: what the water does, at a glance.

Every tile is an inline SVG on a 280 × 120 canvas drawn with a handful of
classes (styled in ``static/style.css`` for both themes):

``w``  water body          ``ws`` water surface line   ``g``  ground / bed
``gs`` ground outline      ``s``  structure (walls, pipes, valves)
``a``  accent (a breach, a valve, a pump: the thing that happens)
``x``  the exact answer (dashed)   ``f`` flow arrow   ``k`` faint detail

Profiles are side views (x along the flow, height up); plans are seen from
above. Shapes are computed where the physics fixes them (Ritter's
parabola, the bump, the backwater curve) so the pictures are honest
sketches, not decoration.
"""

from __future__ import annotations

import math

W, H = 280, 120


def _poly(pts, cls, close=True, extra=""):
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + (" Z" if close else "")
    return f'<path class="{cls}" d="{d}"{extra}/>'


def _line(pts, cls, extra=""):
    return _poly(pts, cls, close=False, extra=extra)


def _arrow(x0, y0, x1, y1, cls="f"):
    ang = math.atan2(y1 - y0, x1 - x0)
    a1 = (x1 - 7 * math.cos(ang - 0.5), y1 - 7 * math.sin(ang - 0.5))
    a2 = (x1 - 7 * math.cos(ang + 0.5), y1 - 7 * math.sin(ang + 0.5))
    return (f'<path class="{cls}" d="M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f}"/>'
            f'<path class="{cls}" d="M{a1[0]:.1f} {a1[1]:.1f} L{x1:.1f} {y1:.1f} L{a2[0]:.1f} {a2[1]:.1f}"/>')


def _profile(bed, surf, x0=0, x1=W, n=70, base=H):
    """Ground under ``bed(x)`` and water between ``bed`` and ``surf`` (both in px, y down)."""
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    ground = [(x, bed(x)) for x in xs] + [(x1, base), (x0, base)]
    top = [(x, min(surf(x), bed(x))) for x in xs]
    water = top + [(x, bed(x)) for x in reversed(xs)]
    return (_poly(water, "w") + _poly(ground, "g") + _line([(x, bed(x)) for x in xs], "gs")
            + _line([(x, y) for x, y in top if y < bed(x) - 0.4], "ws"))


def _bump(x):  # SWASHES bump on 0–25 m mapped to 0–280 px, bed at 100 px
    xm = x / W * 25.0
    z = 0.2 - 0.05 * (xm - 10) ** 2 if 8 < xm < 12 else 0.0
    return 100 - z * 150


def _pipe_section(cx, cy, r, frac):
    """A circular pipe filled to ``frac`` of its diameter."""
    y = cy + r - 2 * r * frac
    th = 2 * math.acos(max(-1.0, min(1.0, 1 - 2 * frac)))
    half = th / 2
    xa, xb = cx - r * math.sin(half), cx + r * math.sin(half)
    large = 1 if frac > 0.5 else 0
    water = f'<path class="w" d="M{xa:.1f} {y:.1f} A{r} {r} 0 {large} 0 {xb:.1f} {y:.1f} Z"/>'
    return water + f'<circle class="s" cx="{cx}" cy="{cy}" r="{r}"/>' + _line([(xa, y), (xb, y)], "ws")


def _manhole(x, top, bottom, w=10):
    return _line([(x - w / 2, top), (x - w / 2, bottom)], "s") + _line([(x + w / 2, top), (x + w / 2, bottom)], "s")


def _trace(pts, cls):
    return _line(pts, cls)


def _hydrograph(x0, y0, w, h, shift=0.0, cls="ws"):
    pts = []
    for i in range(41):
        t = i / 40
        v = math.exp(-((t - 0.35 - shift) / 0.16) ** 2)
        pts.append((x0 + w * t, y0 - h * v))
    return _line(pts, cls)


# ── the tiles ───────────────────────────────────────────────────────────────


def _ritter():
    def depth(x):
        sx = (x - 110) / 50.0  # position in units of c0 t, dam at 110 px
        if sx <= -1:
            return 1.0
        if sx >= 2:
            return 0.0
        return ((2 - sx) / 3) ** 2

    return (_profile(lambda x: 100, lambda x: 100 - 62 * depth(x)) + _line([(110, 30), (110, 100)], "x")
            + _arrow(214, 90, 256, 90))


def _stoker():
    def surf(x):
        if x < 70:
            return 38
        if x < 150:
            return 38 + (x - 70) / 80 * 30
        if x < 205:
            return 68
        return 88
    return _profile(lambda x: 100, surf) + _line([(110, 30), (110, 100)], "x")


def _jump():
    def surf(x):
        if x < 120:
            return 86
        if x < 150:
            return 86 - (x - 120) / 30 * 46 + 6 * math.sin((x - 120) / 30 * math.pi)
        return 40
    roller = '<path class="k" d="M128 64 c10 -14 26 -14 30 -2 c-8 -6 -18 -4 -22 6"/>'
    return _profile(lambda x: 100, surf) + roller + _arrow(20, 80, 60, 80)


def _junction():
    main = '<rect class="w" x="0" y="44" width="280" height="34"/>'
    side = '<rect class="w" x="140" y="0" width="34" height="46"/>'
    walls = (_line([(0, 44), (140, 44), (140, 0)], "s") + _line([(174, 0), (174, 44), (280, 44)], "s")
             + _line([(0, 78), (280, 78)], "s"))
    return main + side + walls + _arrow(20, 61, 70, 61) + _arrow(157, 6, 157, 34) + _arrow(200, 61, 260, 61)


def _smin(a, b, k=4.0):
    return -k * math.log(math.exp(-a / k) + math.exp(-b / k))


def _backwater():
    bed = lambda x: 50 + x * 0.18  # noqa: E731
    surf = lambda x: _smin(bed(x) - 12, 44 + 0.02 * x)  # noqa: E731  (the higher of normal depth and the held level)
    return (_profile(bed, surf) + '<rect class="sf" x="264" y="44" width="6" height="56"/>'
            + _line([(0, bed(0) - 12), (W, bed(W) - 12)], "x") + _arrow(16, 22, 60, 28))


def _bump_tile(kind):
    if kind == "sub":
        surf = lambda x: 40 + (12 * math.exp(-((x / W * 25 - 10) / 1.3) ** 2))  # noqa: E731
    elif kind == "trans":
        surf = lambda x: 46 + 44 / (1 + math.exp(-(x / W * 25 - 10) * 1.6))  # noqa: E731
    elif kind == "shock":
        def surf(x):
            xm = x / W * 25
            if xm < 11.67:
                return 70 + 22 / (1 + math.exp(-(xm - 10) * 2.2))
            return 64
    else:
        surf = lambda x: 80  # noqa: E731
    out = _profile(_bump, surf)
    if kind == "shock":
        out += '<path class="k" d="M128 70 c6 -8 14 -8 16 -2"/>'
    if kind != "still":
        out += _arrow(18, 30, 58, 30)
    return out


def _sewer_network():
    pts = [(30, 30), (80, 50), (130, 40), (170, 70), (220, 82), (262, 96), (100, 90), (60, 100)]
    pipes = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (6, 3), (7, 6)]
    out = "".join(_line([pts[a], pts[b]], "s") for a, b in pipes)
    out += "".join(f'<circle class="mh" cx="{x}" cy="{y}" r="5"/>' for x, y in pts)
    out += "".join(f'<path class="k" d="M{x} {y} l-4 9"/>' for x, y in ((40, 6), (90, 12), (150, 4), (200, 14), (240, 8)))
    return out


def _single_pipe():
    out = '<rect class="w" x="40" y="40" width="40" height="50"/>' + _line([(40, 30), (40, 90), (80, 90)], "s")
    out += '<rect class="s" x="80" y="70" width="190" height="16" rx="2"/><rect class="w" x="81" y="71" width="188" height="14"/>'
    out += _line([(60, 40), (270, 62)], "x") + _arrow(110, 78, 160, 78)
    return out


def _looped():
    n = {"R": (24, 30), "1": (80, 30), "2": (150, 30), "3": (80, 80), "4": (150, 80), "5": (220, 30), "6": (220, 80)}
    e = [("R", "1"), ("1", "2"), ("1", "3"), ("2", "4"), ("3", "4"), ("2", "5"), ("4", "6"), ("5", "6")]
    out = "".join(_line([n[a], n[b]], "s") for a, b in e)
    out += '<rect class="w" x="10" y="16" width="28" height="28"/>' + _line([(10, 16), (10, 44), (38, 44), (38, 16)], "s")
    out += "".join(f'<circle class="mh" cx="{x}" cy="{y}" r="5"/>' for k, (x, y) in n.items() if k != "R")
    out += _arrow(100, 22, 130, 22) + _arrow(88, 45, 88, 66)
    return out


def _hammer():
    return ('<rect x="20" y="50" width="240" height="24" rx="4" class="s"/><rect x="22" y="52" width="140" height="20" class="w"/>'
            '<rect x="162" y="52" width="96" height="20" class="a" fill-opacity="0.45"/><rect x="252" y="36" width="10" height="52" class="sf"/>'
            + _arrow(196, 44, 150, 44, "f"))


def _cavitation():
    bubbles = "".join(f'<circle class="k" cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in ((238, 60, 4), (228, 66, 3), (244, 66, 2.5), (218, 58, 2)))
    return ('<rect x="20" y="50" width="240" height="24" rx="4" class="s"/><rect x="22" y="52" width="200" height="20" class="w"/>'
            '<rect x="252" y="36" width="10" height="52" class="sf"/>' + bubbles + _arrow(60, 40, 110, 40))


def _tracer():
    stops = "".join(f'<rect class="a" x="{60 + i * 8}" y="52" width="8" height="20" fill-opacity="{max(0.05, 0.6 - i * 0.04):.2f}"/>' for i in range(14))
    return ('<rect x="20" y="50" width="240" height="24" rx="4" class="s"/><rect x="22" y="52" width="236" height="20" class="w" fill-opacity="0.25"/>'
            '<rect class="a" x="22" y="52" width="38" height="20" fill-opacity="0.6"/>' + stops + _arrow(30, 38, 80, 38))


def _part_full():
    return (_pipe_section(60, 62, 32, 0.25) + _pipe_section(140, 62, 32, 0.5) + _pipe_section(220, 62, 32, 0.77))


def _surcharged():
    out = '<rect class="s" x="20" y="78" width="240" height="18" rx="2"/><rect class="w" x="21" y="79" width="238" height="16"/>'
    levels = [22, 34, 46, 58, 70]
    for i, x in enumerate((40, 90, 140, 190, 240)):
        out += _manhole(x, 12, 78) + f'<rect class="w" x="{x - 5}" y="{levels[i]}" width="10" height="{78 - levels[i]}"/>'
    out += _line([(40, 22), (240, 70)], "x") + _arrow(60, 104, 110, 104)
    return out


def _tank():
    return ('<rect class="w" x="60" y="56" width="110" height="44"/>' + _line([(60, 20), (60, 100), (170, 100), (170, 20)], "s")
            + _line([(60, 34), (170, 34)], "x") + '<path class="s" d="M170 90 H200"/>'
            + '<path class="ws" d="M200 92 q20 2 30 24"/>' + _arrow(115, 44, 115, 60))


def _pump():
    return ('<path class="s" d="M30 30 V96 H110 V30"/><rect class="w" x="32" y="62" width="76" height="32"/>'
            '<circle class="sf" cx="150" cy="80" r="12"/><path class="ws" d="M110 86 H138"/><path class="ws" d="M162 80 H240 V22 H262"/>'
            '<rect class="w" x="240" y="14" width="30" height="10"/>' + _arrow(60, 22, 60, 50))


def _sewer_backwater():
    bed = lambda x: 40 + x * 0.22  # noqa: E731
    top = lambda x: bed(x) - 22  # noqa: E731
    surf = lambda x: min(bed(x) - 2, 38 + x * 0.07 + 8 * (1 - x / W))  # noqa: E731
    xs = [i * 4 for i in range(71)]
    out = _poly([(x, top(x)) for x in xs] + [(x, bed(x)) for x in reversed(xs)], "k")
    out += _poly([(x, surf(x)) for x in xs] + [(x, bed(x)) for x in reversed(xs)], "w")
    out += _line([(x, top(x)) for x in xs], "s") + _line([(x, bed(x)) for x in xs], "s")
    for x in (60, 120, 180, 240):
        out += _manhole(x, 6, top(x), 8)
    out += '<rect class="w" x="262" y="60" width="18" height="44"/>' + _line([(x, surf(x)) for x in xs], "ws")
    return out


def _bowl():
    bed = lambda x: 104 - 0.0034 * (x - 140) ** 2  # noqa: E731
    surf = lambda x: 70 + (x - 140) * 0.14  # noqa: E731
    return _profile(bed, surf) + '<path class="k" d="M112 58 q28 -12 56 0"/>' + _arrow(120, 50, 170, 44)


def _macdonald2d():
    bed = lambda x: 40 + x * 0.16 + 6 * math.sin(x / 26)  # noqa: E731
    surf = lambda x: bed(x) - 16 - 3 * math.sin(x / 40)  # noqa: E731
    return _profile(bed, surf) + _arrow(20, 16, 70, 22)


def _oblique():
    wall = '<path class="g" d="M0 120 L80 120 L280 66 L280 120 Z"/><path class="gs" d="M0 120 L80 120 L280 66"/>'
    flow = "".join(_arrow(10, y, 54, y) for y in (24, 50, 76))
    shock = _line([(80, 120), (230, 0)], "x")
    return '<rect class="w" x="0" y="0" width="280" height="120" fill-opacity="0.2"/>' + wall + flow + shock


def _malpasset():
    river = '<path class="w" d="M40 0 C60 30 30 50 70 70 S150 80 180 100 S250 110 280 108 L280 120 L170 120 C140 100 70 96 40 80 S10 30 20 0 Z"/>'
    dam = '<path class="a" d="M24 14 L56 8" stroke-width="5"/>'
    hills = '<path class="k" d="M120 10 q30 -10 60 4 M190 30 q30 -10 60 4 M90 40 q24 -8 40 2"/>'
    return river + dam + hills + _arrow(64, 50, 104, 70)


def _ea1():
    def bed(x):
        if x < 140:
            return 84 - 24 * (x / 140) ** 3
        return 60 + 40 * math.sin(min(1.0, (x - 140) / 75) * math.pi / 2) - (max(0.0, x - 215) * 0.5)
    surf = lambda x: 54 if x < 140 else 60  # noqa: E731
    return _profile(bed, surf) + _line([(140, 60), (270, 60)], "x") + _arrow(10, 44, 50, 50)


def _ea2():
    bed = lambda x: 70 + 18 * math.sin(x / 22) ** 2 * (1 if (x // 70) % 2 else 0.4)  # noqa: E731
    return _profile(bed, lambda x: 78) + _arrow(8, 50, 40, 62)


def _ea4():
    return ('<ellipse class="w" cx="72" cy="62" rx="92" ry="54" fill-opacity="0.35"/><ellipse class="w" cx="60" cy="62" rx="56" ry="40"/>'
            '<rect class="a" x="0" y="52" width="10" height="20"/>' + _arrow(110, 62, 170, 62))


def _ea5():
    contours = "".join(f'<path class="k" d="M0 {60 - k * 12} C80 {50 - k * 12} 200 {70 - k * 12} 280 {56 - k * 12}"/>' for k in range(1, 4))
    contours += "".join(f'<path class="k" d="M0 {60 + k * 12} C80 {70 + k * 12} 200 {50 + k * 12} 280 {64 + k * 12}"/>' for k in range(1, 4))
    flood = '<path class="w" d="M0 50 C80 42 200 66 280 52 L280 70 C200 80 80 62 0 72 Z"/>'
    return contours + flood + _arrow(20, 60, 70, 58)


def _city():
    out = '<rect class="w" x="0" y="0" width="120" height="120"/>'
    for i in range(4):
        for j in range(3):
            out += f'<rect class="sf" x="{140 + i * 34}" y="{12 + j * 36}" width="22" height="24" rx="2"/>'
    out += '<path class="ws" d="M120 0 C140 30 128 60 150 90 S136 120 140 120"/>' + _line([(118, 0), (118, 120)], "a")
    return out + _arrow(40, 60, 100, 60)


def _toce():
    valley = '<path class="g" d="M0 0 H280 V30 C200 40 120 26 0 36 Z M0 120 H280 V92 C200 82 120 96 0 86 Z"/>'
    water = '<path class="w" d="M0 36 C120 26 200 40 280 30 V92 C200 82 120 96 0 86 Z" fill-opacity="0.25"/>'
    houses = "".join(f'<rect class="sf" x="{x}" y="{y}" width="12" height="12"/>' for x, y in ((150, 52), (170, 60), (190, 50), (170, 74)))
    return valley + water + '<path class="w" d="M0 40 L110 44 L120 80 L0 82 Z"/>' + houses + _arrow(60, 60, 110, 60)


def _sill():
    bed = lambda x: 100 - (max(0, 26 - abs(x - 190) * 0.65) if 150 < x < 230 else 0)  # noqa: E731
    surf = lambda x: 44 if x < 60 else (44 + (x - 60) * 0.35 if x < 150 else 86)  # noqa: E731
    return _profile(bed, surf) + _line([(60, 36), (60, 100)], "x")


def _building():
    out = '<rect class="w" x="0" y="0" width="110" height="120"/><rect class="sf" x="170" y="44" width="30" height="30" rx="2"/>'
    out += '<path class="ws" d="M110 0 C126 30 160 36 166 44 M110 120 C126 90 160 84 166 74 M200 44 C220 30 240 30 260 20 M200 74 C220 90 240 90 260 100"/>'
    return out + _arrow(40, 60, 100, 60)


def _manhole_rig():
    out = _profile(lambda x: 56, lambda x: 46)
    out += '<rect class="s" x="20" y="92" width="240" height="16" rx="2"/><rect class="w" x="21" y="93" width="238" height="14"/>'
    out += _manhole(140, 56, 92, 14) + '<rect class="w" x="133" y="56" width="14" height="36"/>'
    return out + _arrow(140, 86, 140, 40) + _arrow(150, 40, 150, 70)


def _street():
    bed = lambda x: 40 + x * 0.12  # noqa: E731
    out = _profile(bed, lambda x: bed(x) - (0 if x < 54 else 6))
    out += '<rect class="s" x="0" y="96" width="70" height="12" rx="2"/><rect class="w" x="1" y="97" width="68" height="10"/>'
    out += _manhole(64, bed(64), 96, 12) + f'<rect class="w" x="58" y="{bed(64):.0f}" width="12" height="{96 - bed(64):.0f}"/>'
    out += '<path class="ws" d="M64 44 q-6 -16 0 -26 q6 10 0 26"/>' + _arrow(110, 40, 180, 50) + _line([(120, bed(120) - 6), (280, bed(280) - 6)], "x")
    return out


def _yard():
    out = '<rect class="g" x="0" y="64" width="280" height="56"/>' + _line([(0, 64), (280, 64)], "gs")
    out += '<rect class="w" x="10" y="26" width="260" height="38"/>' + _line([(10, 10), (10, 64)], "s") + _line([(270, 10), (270, 64)], "s")
    out += '<rect class="s" x="133" y="56" width="14" height="8"/>' + _manhole(140, 64, 100, 14)
    out += '<rect class="s" x="140" y="96" width="140" height="12" rx="2"/><rect class="w" x="141" y="97" width="138" height="10"/>'
    out += _line([(10, 56), (270, 56)], "x") + _arrow(140, 34, 140, 60) + _arrow(200, 102, 250, 102)
    return out


def _round_trip():
    bed = lambda x: 40 + abs(x - 140) * -0.25 + 50  # noqa: E731
    out = _profile(lambda x: 90 - abs(x - 140) * 0.28, lambda x: 72)
    out += _manhole(140, 90, 112, 12) + '<rect class="w" x="134" y="90" width="12" height="22"/>'
    out += _arrow(126, 104, 126, 64) + _arrow(154, 64, 154, 104)
    return out


def _epanet():
    n = [(30, 80), (80, 40), (140, 70), (200, 36), (250, 76)]
    out = "".join(_line([n[i], n[i + 1]], "s") for i in range(len(n) - 1)) + _line([n[1], n[3]], "s")
    out += "".join(f'<circle class="mh" cx="{x}" cy="{y}" r="5"/>' for x, y in n)
    out += '<rect class="w" x="236" y="12" width="28" height="22"/>' + _line([(236, 12), (236, 34), (264, 34), (264, 12)], "s")
    out += _hydrograph(20, 116, 240, 26, 0.0, "ws") + _hydrograph(20, 116, 240, 26, 0.02, "x")
    return out


def _extran():
    out = _sewer_backwater()
    return out + _hydrograph(20, 118, 240, 24, 0.0, "ws") + _hydrograph(20, 118, 240, 24, 0.03, "x")


def _rtc():
    return ('<path class="s" d="M30 30 V96 H110 V30"/><rect class="w" x="32" y="62" width="76" height="32"/>'
            '<circle class="sf" cx="150" cy="80" r="14"/><path class="ws" d="M164 80 H250 V40"/>'
            + _line([(30, 56), (110, 56)], "x") + _line([(30, 88), (110, 88)], "x")
            + '<path class="a" d="M180 30 h12 v-12 h12 v12 h12 v-12 h12 v12 h12" fill="none"/>')


TILES = {
    "A1F-001": _backwater, "A1F-010": _ritter, "A1F-011": _stoker, "A1F-020": _jump, "A1F-030": _junction,
    "A1F-040": lambda: _bump_tile("sub"), "A1F-041": lambda: _bump_tile("trans"), "A1F-042": lambda: _bump_tile("shock"),
    "A1F-043": lambda: _bump_tile("still"), "A1F-100": _sewer_network,
    "A1P-001": _single_pipe, "A1P-010": _looped, "A1P-020": _hammer, "A1P-021": _cavitation, "A1P-030": _tracer,
    "A1D-001": _part_full, "A1D-002": _surcharged, "A1D-003": _tank, "A1D-004": _pump, "A1D-005": _sewer_backwater,
    "A2A-001": _bowl, "A2A-010": _macdonald2d, "A2A-020": _oblique, "A2F-001": _malpasset,
    "A2C-EA1": _ea1, "A2C-EA2": _ea2, "A2C-EA4": _ea4, "A2C-EA5": _ea5,
    "A2L-010": _city, "A2L-011": _toce, "A2L-020": _sill, "A2L-EA6A": _building,
    "A12-001": _manhole_rig, "A12-010": _street, "A12-011": _yard, "A12-012": _round_trip,
    "B-EPANET-001": _epanet, "B-EXTRAN-001": _extran, "B-RTC-001": _rtc,
}


def tile_svg(sid: str, label: str = "", fit: str = "slice") -> str:
    """The tile for test ``sid`` as an inline SVG (decorative unless ``label`` is given)."""
    fn = TILES.get(sid)
    inner = fn() if fn else _profile(lambda x: 96, lambda x: 70)
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return f'<svg class="tile" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid {fit}" {aria}>{inner}</svg>'
