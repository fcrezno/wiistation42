"""crezno's bitmap font as a TrueType file, for WiiMC's menus:
  py -3 tools/make_font_ttf.py <font.png> <font.json> fonts/font.ttf

WiiMC draws every word of its menus with one TrueType font (source/fonts/
font.ttf). This turns the Clanker Arena strip into that file, pixel for pixel:
every ink pixel (alpha > 80) is a square of 100 units, the em is the 24 pixel
cell, and each glyph is as wide as its own ink plus the 1 pixel of tracking,
the same measure the game and the WiiStation 42 overlay use. Drawn at 24
pixels (mod_tv.py fixes WiiMC to that size) one font pixel is one screen
pixel, so nothing is blurred.

The strip is used as drawn: the 1 pixel baseline drift stays.
"""
import json
import sys
import unicodedata

from PIL import Image
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

U = 100                 # font units per pixel
BASE_ROW = 18           # the last row above the baseline (font.json "baseline")

png, spec_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
spec = json.load(open(spec_path, encoding="utf-8"))
CW, CH, COLS, FIRST = spec["cellW"], spec["cellH"], spec["cols"], spec.get("first", 32)
TRACK = max(0, round(spec.get("tracking", 2) / 2))
SPACE = spec.get("spaceW", 4)
alpha = Image.open(png).convert("RGBA").getchannel("A")
ROWS = alpha.height // CH


def ink(code):
    """The ink pixels of one character as (x, row), x from the left edge of its ink."""
    i = code - FIRST
    if i < 0 or i >= COLS * ROWS:
        return None
    sx, sy = (i % COLS) * CW, (i // COLS) * CH
    px = [(x, y) for y in range(CH) for x in range(CW) if alpha.getpixel((sx + x, sy + y)) > 80]
    if not px:
        return []
    left = min(x for x, _ in px)
    return [(x - left, y) for x, y in px]


def outline(pixels):
    """Horizontal runs of each row become rectangles, drawn clockwise."""
    pen = TTGlyphPen(None)
    rows = {}
    for x, y in pixels:
        rows.setdefault(y, []).append(x)
    for y, xs in sorted(rows.items()):
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            top, bottom = (BASE_ROW + 1 - y) * U, (BASE_ROW - y) * U
            pen.moveTo((start * U, top))
            pen.lineTo(((prev + 1) * U, top))
            pen.lineTo(((prev + 1) * U, bottom))
            pen.lineTo((start * U, bottom))
            pen.closePath()
            if x is not None:
                start = prev = x
    return pen.glyph()


def width_of(pixels):
    return (max(x for x, _ in pixels) + 1) if pixels else SPACE


order, glyphs, metrics, cmap = [".notdef"], {}, {}, {}
empty = TTGlyphPen(None).glyph()
glyphs[".notdef"] = empty
metrics[".notdef"] = ((SPACE + TRACK) * U, 0)

for code in range(FIRST, FIRST + COLS * ROWS):
    px = ink(code)
    if px is None:
        continue
    name = f"c{code:02X}"
    order.append(name)
    glyphs[name] = outline(px) if px else empty
    metrics[name] = ((width_of(px) + TRACK) * U, 0)
    cmap[code] = name

# the ellipsis, drawn as three of the strip's own dots
dot = ink(ord("."))
if dot:
    w = width_of(dot)
    three = [(x + k * (w + TRACK), y) for k in range(3) for x, y in dot]
    order.append("ellipsis")
    glyphs["ellipsis"] = outline(three)
    metrics["ellipsis"] = ((3 * (w + TRACK)) * U, 0)
    cmap[0x2026] = "ellipsis"

# letters with accents use the plain letter, curly quotes and dashes the plain ones
for cp in list(range(0xA0, 0x180)) + [0x2018, 0x2019, 0x201C, 0x201D, 0x2013, 0x2014]:
    if cp in cmap:
        continue
    fold = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2013: "-", 0x2014: "-", 0xA0: " "}.get(cp)
    if fold is None:
        base = unicodedata.normalize("NFD", chr(cp))[0]
        fold = base if ord(base) < 128 and base.isalpha() else None
    if fold and ord(fold) in cmap:
        cmap[cp] = cmap[ord(fold)]

fb = FontBuilder(CH * U, isTTF=True)
fb.setupGlyphOrder(order)
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics(metrics)
ascent, descent = (BASE_ROW + 1) * U, -(CH - BASE_ROW - 1) * U
fb.setupHorizontalHeader(ascent=ascent, descent=descent)
fb.setupNameTable({"familyName": "WiiStation42 Pixel", "styleName": "Regular"})
fb.setupOS2(sTypoAscender=ascent, sTypoDescender=descent, sTypoLineGap=0,
            usWinAscent=ascent, usWinDescent=-descent, sxHeight=0, sCapHeight=0)
fb.setupPost()
fb.save(out)
print(f"{out}: {len(order)} glyphs, {len(cmap)} characters, em {CH * U}")
