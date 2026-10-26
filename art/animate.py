"""Two looks for the channel banner, as video:

  py -3 animate.py

  anim_static.mp4    black and white static, then the picture locks on and stays
  anim_parallax.mp4  the colour bars drift, each band at its own speed

The plate with crezno's wordmark sits in front in both.
"""
import glob
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
W, H, FPS = 608, 456, 24
MUSIC = "truemenu.mp3"
WORD = Image.open("wordmark.png").convert("RGBA")
NAVY = (16, 24, 56)
BARS = [(192,192,192),(192,192,0),(0,192,192),(0,192,0),(192,0,192),(192,0,0),(0,0,192)]
STRIP = [(0,0,192),(17,17,17),(192,0,192),(17,17,17),(0,192,192),(17,17,17),(192,192,192)]
BOTTOM = [((0,33,76), 5/7), ((255,255,255), 5/7), ((50,0,106), 5/7), ((17,17,17), 5/7),
          ((0,0,0), 1/3), ((17,17,17), 1/3), ((33,33,33), 1/3), ((17,17,17), 2)]
TOP_H, STRIP_H = int(H * 0.67), int(H * 0.75)


def row_top(w, h):
    """The seven bars, each exactly one seventh wide."""
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(BARS):
        d.rectangle([round(w * i / 7), 0, round(w * (i + 1) / 7) - 1, h], fill=c)
    return im


def row_strip(w, h):
    """The chroma strip under the bars: blue, black, magenta, black, cyan, black, grey."""
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(STRIP):
        d.rectangle([round(w * i / 7), 0, round(w * (i + 1) / 7) - 1, h], fill=c)
    return im


def row_bottom(w, h):
    """The bottom row of a 75% test card: -I, white, +Q, black, the three pluge
    steps of a third of a bar each, then black to the right edge."""
    unit = w / 7
    parts = [((0, 33, 76), 5 / 7), ((255, 255, 255), 5 / 7), ((50, 0, 106), 5 / 7),
             ((17, 17, 17), 5 / 7), ((0, 0, 0), 1 / 3), ((17, 17, 17), 1 / 3),
             ((33, 33, 33), 1 / 3)]
    parts.append(((17, 17, 17), 7 - sum(p for _, p in parts)))   # fills to the edge
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    x = 0.0
    for c, part in parts:
        d.rectangle([round(x), 0, round(x + unit * part) - 1, h], fill=c)
        x += unit * part
    return im


def tile(make, w, h):
    """The same pattern twice side by side, so it can scroll and wrap with the
    bars keeping their true width."""
    one = make(w, h)
    im = Image.new("RGB", (w * 2, h))
    im.paste(one, (0, 0))
    im.paste(one, (w, 0))
    return im


def bars_still():
    im = Image.new("RGB", (W, H))
    im.paste(row_top(W, TOP_H), (0, 0))
    im.paste(row_strip(W, STRIP_H - TOP_H), (0, TOP_H))
    im.paste(row_bottom(W, H - STRIP_H), (0, STRIP_H))
    return im


def plate_layer():
    """The navy plate and the wordmark, on its own transparent layer."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    word_w = int(W * 0.86)
    word = WORD.resize((word_w, round(word_w * WORD.height / WORD.width)), Image.LANCZOS)
    white = Image.new("RGBA", word.size, (255, 255, 255, 255))
    white.putalpha(word.getchannel("A"))
    box_h = word.height + round(H * 0.09) + round(H * 0.16)
    top = (H - box_h) // 2
    m = (W - word_w) // 2
    d.rounded_rectangle([m - 18, top, W - m + 18, top + box_h], 27,
                        fill=NAVY + (235,), outline=(150, 200, 255), width=3)
    im.alpha_composite(white, (m, top + round(H * 0.08)))
    f = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 25)
    d.text((W // 2, top + box_h - 41), "your own television station", font=f,
           fill=(200, 220, 255), anchor="mm")
    return im


def static_frame(rng, lock=0.0):
    """Black and white noise. As lock goes to 1 the noise gets weaker."""
    n = rng.integers(40, 235, size=(H // 2, W // 2), dtype=np.uint8)
    im = Image.fromarray(n, "L").resize((W, H), Image.NEAREST).convert("RGB")
    if lock:
        im = Image.blend(im, bars_still(), lock)
    return im


def write(frames, name, seconds, fade_out=0.4):
    tmp = os.path.join(os.environ["TEMP"], "ws42frames")
    os.makedirs(tmp, exist_ok=True)
    for f in glob.glob(os.path.join(tmp, "*.png")):
        os.remove(f)
    for i, im in enumerate(frames):
        im.convert("RGB").save(os.path.join(tmp, f"{i:04d}.png"))
    # the chime plays once at the start; the picture goes on in silence
    sound = "sound_chime.wav" if os.path.isfile("sound_chime.wav") else MUSIC
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
           "-framerate", str(FPS), "-i", os.path.join(tmp, "%04d.png"),
           "-i", sound, "-t", f"{seconds:.2f}",
           "-af", "apad",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-c:a", "aac", "-b:a", "160k", name]
    subprocess.run(cmd, check=True)
    print(name, f"{os.path.getsize(name)/1e6:.1f} MB, {len(frames)} frames")


def make_static(seconds=8.0):
    rng = np.random.default_rng(42)
    plate = plate_layer()
    bars = bars_still()
    out = []
    n = int(seconds * FPS)
    for i in range(n):
        t = i / FPS
        if t < 1.1:                                   # only noise
            im = static_frame(rng)
        elif t < 1.5:                                 # the picture fights through
            im = static_frame(rng, lock=(t - 1.1) / 0.4)
        elif t < 1.58:                                # the white flash of a lock
            im = Image.new("RGB", (W, H), (245, 245, 245))
        else:
            im = bars.copy()
        if t >= 1.58:                                 # the plate grows into place
            k = min(1.0, (t - 1.58) / 0.45)
            s = 0.82 + 0.18 * (1 - (1 - k) ** 3)
            lay = plate.resize((int(W * s), int(H * s)), Image.LANCZOS)
            a = lay.getchannel("A").point(lambda v: int(v * k))
            lay.putalpha(a)
            im = im.convert("RGBA")
            im.alpha_composite(lay, ((W - lay.width) // 2, (H - lay.height) // 2))
        out.append(im)
    write(out, "anim_static.mp4", seconds)


def make_parallax(seconds=8.0, name="anim_parallax.mp4", plate=None, bars_from=0.0,
                  frames_before=None, music_start=0.0, fade_out=0.4):
    """Each band of the test card moves at its own speed, so the picture has depth.
    The bars keep their true widths: the pattern is tiled, not stretched."""
    plate = plate or plate_layer()
    top = tile(row_top, W, TOP_H)
    strip = tile(row_strip, W, STRIP_H - TOP_H)
    bottom = tile(row_bottom, W, H - STRIP_H)
    speeds = (26, 58, 14)                              # pixels a second
    out = list(frames_before or [])
    n = int(seconds * FPS) - len(out)
    for i in range(max(0, n)):
        t = bars_from + i / FPS
        im = Image.new("RGB", (W, H))
        for src, y, sp in ((top, 0, speeds[0]), (strip, TOP_H, speeds[1]), (bottom, STRIP_H, speeds[2])):
            off = int(t * sp) % W
            im.paste(src.crop((off, 0, off + W, src.height)), (0, y))
        im = im.convert("RGBA")
        k = min(1.0, max(0.0, i / (0.45 * FPS)))       # the plate grows into place
        sc = 0.82 + 0.18 * (1 - (1 - k) ** 3)
        lay = plate.resize((int(W * sc), int(H * sc)), Image.LANCZOS)
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * k)))
        im.alpha_composite(lay, ((W - lay.width) // 2, (H - lay.height) // 2))
        out.append(im)
    write(out, name, seconds, fade_out)


def make_combined(seconds=10.0):
    """Static, the picture locks on, then the bars drift and never stop."""
    rng = np.random.default_rng(42)
    before = []
    for i in range(int(1.58 * FPS)):
        t = i / FPS
        if t < 1.1:
            before.append(static_frame(rng))
        elif t < 1.5:
            before.append(static_frame(rng, lock=(t - 1.1) / 0.4))
        else:
            before.append(Image.new("RGB", (W, H), (245, 245, 245)))
    make_parallax(seconds, "anim_combined.mp4", frames_before=before)


if __name__ == "__main__":
    make_static()
    make_parallax()
    make_combined()
