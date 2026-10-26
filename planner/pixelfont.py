"""crezno's bitmap font (from the Clanker Arena game), drawn the same way the game draws it.

The strip is a grid of cells in ASCII order. A glyph's advance is the width of
its own ink, not the cell, so the spacing is proportional; the gap between
glyphs is the tracking from font.json. Scales are whole numbers and nearest
neighbour, because a pixel font at a fraction turns to mush.

Nothing here tidies the strip: the baseline in font.json is used as it is.

  from pixelfont import text, width
  img = text("AniBox", scale=2, colour=(255, 200, 80))
"""
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "art", "font")
_font = None


def load():
    global _font
    if _font:
        return _font
    spec = json.load(open(os.path.join(FONT_DIR, "font.json"), encoding="utf-8"))
    img = Image.open(os.path.join(FONT_DIR, "font.png")).convert("RGBA")
    cell_w, cell_h = spec["cellW"], spec["cellH"]
    cols, first = spec["cols"], spec.get("first", 32)
    space_w = spec.get("spaceW", round(cell_w * 0.45))
    alpha = img.getchannel("A")
    rows = img.height // cell_h

    # each glyph's advance is the width of its ink, like the game measures it
    metrics = []
    for i in range(cols * rows):
        sx, sy = (i % cols) * cell_w, (i // cols) * cell_h
        box = alpha.crop((sx, sy, sx + cell_w, sy + cell_h))
        ink = box.point(lambda v: 255 if v > 80 else 0).getbbox()
        metrics.append({"left": 0, "width": space_w} if not ink
                       else {"left": ink[0], "width": ink[2] - ink[0]})

    _font = {"img": img, "alpha": alpha, "cellW": cell_w, "cellH": cell_h,
             "cols": cols, "first": first, "rows": rows,
             "tracking": max(0, round(spec.get("tracking", 1) / 2)),
             "baseline": spec.get("baseline", cell_h), "metrics": metrics}
    return _font


FOLD = {"—": "-", "–": "-", "’": "'", "‘": "'",
        "“": '"', "”": '"', "…": "...", "×": "x"}


def ascii_only(s):
    """The strip covers ASCII 32..127; anything else would draw as nothing."""
    out = []
    for ch in str(s):
        ch = FOLD.get(ch, ch)
        out.append(ch if 32 <= ord(ch[0]) < 128 else "?")
    return "".join(out)


def text(s, scale=1, colour=(255, 255, 255)):
    """One line as an RGBA image, tinted, at a whole-number scale."""
    f = load()
    s = ascii_only(s)
    scale = max(1, int(round(scale)))
    places, pen = [], 0
    for ch in s:
        code = ord(ch) - f["first"]
        m = f["metrics"][code] if 0 <= code < len(f["metrics"]) else {"left": 0, "width": f["cellW"]}
        places.append((code, m, pen))
        pen += m["width"] + f["tracking"]
    w = max(1, pen - f["tracking"])
    out = Image.new("RGBA", (w, f["cellH"]), (0, 0, 0, 0))
    solid = Image.new("RGBA", (f["cellW"], f["cellH"]), colour + (255,))
    for code, m, at in places:
        if code < 0 or m["width"] <= 0:
            continue
        sx, sy = (code % f["cols"]) * f["cellW"], (code // f["cols"]) * f["cellH"]
        if sy + f["cellH"] > f["img"].height:
            continue
        mask = f["alpha"].crop((sx + m["left"], sy, sx + m["left"] + m["width"], sy + f["cellH"]))
        mask = mask.point(lambda v: v if v >= 80 else 0)
        out.paste(solid.crop((0, 0, m["width"], f["cellH"])), (at, 0), mask)
    if scale > 1:
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    return out


def width(s, scale=1):
    return text(s, scale).width


def draw(target, s, xy, scale=1, colour=(255, 255, 255), right=False, centre=False):
    """Puts a line on an image. xy is the top left, or the top right/centre."""
    img = text(s, scale, colour)
    x, y = xy
    if right:
        x -= img.width
    elif centre:
        x -= img.width // 2
    target.paste(img, (int(x), int(y)), img)
    return img.width


def line_height(scale=1):
    return load()["cellH"] * max(1, int(round(scale)))
