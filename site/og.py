"""Social preview images and result badges.

``og_image(...)`` draws the 1200 × 630 card a link to a test shows on LinkedIn,
Slack or X: the test's name, question and how many models pass, beside its
picture tile (rendered with cairosvg when it is installed; text only
otherwise). ``badge_svg(...)`` is the small "passes / fails" badge a solver's
developer can embed, linking back to the result.
"""

from __future__ import annotations

import io
from pathlib import Path

W, H = 1200, 630
BG, INK, INK2, WATER, PASS, FAIL, RULE = "#0B161E", "#E2EAF0", "#A3B4C1", "#5BA7DB", "#6BCB98", "#F08A5D", "#26394A"
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/freefont"]
FONT_FILES = {"bold": ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "FreeSansBold.ttf"],
              "regular": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "FreeSans.ttf"]}

TILE_STYLE = """
.w{fill:#5BA7DB;fill-opacity:.32}.ws{fill:none;stroke:#5BA7DB;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}
.g{fill:#3B2F1F}.gs{fill:none;stroke:#D1A35E;stroke-width:2}.s{fill:none;stroke:#A3B4C1;stroke-width:2}
.sf{fill:#A3B4C1}.mh{fill:#12212C;stroke:#A3B4C1;stroke-width:2}.a{fill:#F08A5D;stroke:#F08A5D;stroke-width:2.5}
.x{fill:none;stroke:#E2EAF0;stroke-width:1.5;stroke-dasharray:5 4;opacity:.7}.f{fill:none;stroke:#8CC4EE;stroke-width:2;stroke-linecap:round}
.k{fill:none;stroke:#A3B4C1;stroke-width:1.2;opacity:.55}
"""


def _font(kind: str, size: int):
    from PIL import ImageFont

    for d in FONT_DIRS:
        for f in FONT_FILES[kind]:
            p = Path(d) / f
            if p.is_file():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _tile_png(sid: str, width: int) -> "Image.Image | None":
    try:
        import cairosvg
        from PIL import Image

        import tiles
    except ImportError:
        return None
    inner = tiles.TILES[sid]() if sid in tiles.TILES else ""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 120" width="{width}" height="{int(width * 120 / 280)}">'
           f'<style>{TILE_STYLE}</style><rect width="280" height="120" fill="#102A3D"/>{inner}</svg>')
    try:
        png = cairosvg.svg2png(bytestring=svg.encode())
    except Exception:  # noqa: BLE001 - a picture is optional
        return None
    return Image.open(io.BytesIO(png)).convert("RGB")


def _wrap(text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def og_image(path: Path, sid: str, kicker: str, title: str, question: str, n_ok: int, n_run: int, site: str = "OpenHydro Bench",
             footer: str | None = None, n_unsure: int = 0) -> None:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    tile = _tile_png(sid, 520)
    text_w = (W - 60 - (tile.width if tile else 0) - 60 - 44) if tile else 1080
    x = 60
    d.text((x, 54), site, font=_font("bold", 30), fill=INK)
    d.line([(x, 104), (x + 64, 104)], fill=WATER, width=4)
    d.text((x, 130), kicker.upper() + ("" if footer else f"  ·  {sid}"), font=_font("bold", 22), fill=WATER)
    y = 172
    size = 52
    tf = _font("bold", size)
    lines = _wrap(title, tf, text_w)
    while len(lines) > 3 and size > 36:
        size -= 4
        tf = _font("bold", size)
        lines = _wrap(title, tf, text_w)
    for line in lines[:3]:
        d.text((x, y), line, font=tf, fill=INK)
        y += int(size * 1.18)
    y += 12
    qf = _font("regular", 26)
    for line in _wrap(question, qf, text_w)[:4]:
        d.text((x, y), line, font=qf, fill=INK2)
        y += 36
    # result bar
    by = H - 92
    if footer:
        d.text((x, by + 10), footer, font=_font("bold", 26), fill=INK)
    elif n_run:
        bw = text_w - 20
        d.rounded_rectangle([x, by, x + bw, by + 14], radius=7, fill=RULE)
        if n_ok:
            d.rounded_rectangle([x, by, x + int(bw * n_ok / n_run), by + 14], radius=7, fill=PASS)
        if n_ok + n_unsure < n_run:
            d.rounded_rectangle([x + int(bw * (n_ok + n_unsure) / n_run), by, x + bw, by + 14], radius=7, fill=FAIL)
        if n_unsure:
            d.rectangle([x + int(bw * n_ok / n_run), by, x + int(bw * (n_ok + n_unsure) / n_run), by + 14], fill=INK2)
        extra = f" · {n_unsure} inconclusive" if n_unsure else ""
        d.text((x, by + 26), f"{n_ok} of {n_run} model{'s' if n_run != 1 else ''} pass{extra}", font=_font("bold", 26), fill=INK)
    else:
        d.text((x, by + 10), "Not run yet: run it and add yours", font=_font("bold", 26), fill=INK)
    if tile:
        tx, ty = W - 60 - tile.width, (H - tile.height) // 2
        d.rounded_rectangle([tx - 2, ty - 2, tx + tile.width + 2, ty + tile.height + 2], radius=14, outline=RULE, width=2)
        im.paste(tile, (tx, ty))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG", optimize=True)


def badge_svg(label: str, verdict: str | bool) -> str:
    """A shields-style badge: label on the left, passes / fails / inconclusive on the right."""
    if isinstance(verdict, bool):
        verdict = "pass" if verdict else "fail"
    right = {"pass": "passes", "fail": "fails", "inconclusive": "inconclusive"}[verdict]
    lw, rw = 7 * len(label) + 14, 7 * len(right) + 14
    col = {"pass": "#1F7A4D", "fail": "#B5481A", "inconclusive": "#5D6D7E"}[verdict]
    w = lw + rw
    esc = label.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{esc}: {right}">'
            f'<title>{esc}: {right}</title><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
            f'<stop offset="1" stop-opacity=".1"/></linearGradient><clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>'
            f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#24323D"/><rect x="{lw}" width="{rw}" height="20" fill="{col}"/>'
            f'<rect width="{w}" height="20" fill="url(#s)"/></g><g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
            f'<text x="{lw / 2}" y="14">{esc}</text><text x="{lw + rw / 2}" y="14">{right}</text></g></svg>')
