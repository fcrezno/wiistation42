"""The station's own clips in _breaks, in crezno's font (crezno: "make this the same
font as the others").

  py -3 make_idents.py

Colour bars 10s / 60s, Please stand by 30s, Station ident 15s, Up next 20s.
Every clip keeps its length to the frame and its own sound (taken from the
copy in art/old-clips), so the channel files that name them stay right. All
the words are crezno's pixel font at one size (scale 2); the station name is the
wordmark, as in the opening.
"""
import glob
import os
import subprocess

from PIL import Image

import make_open
import pixelfont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), "art")
OLD = os.path.join(ART, "old-clips")
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
W, H = 640, 480
S = 2                                   # the one text size
GOLD, WHITE = (255, 200, 80), (240, 244, 252)
DARK = (14, 20, 30)


def lines(img, rows, top=None):
    """Centred lines of text; rows are (text, colour), and "" leaves a gap."""
    step = 34
    y = top if top is not None else (H - step * len(rows)) // 2 - 6
    for text, colour in rows:
        if text:
            pixelfont.draw(img, text, (W // 2, y), scale=S, colour=colour, centre=True)
        y += step
    return y


def wordmark(width, colour):
    word = Image.open(os.path.join(ART, "wordmark.png")).convert("RGBA")
    word = word.resize((width, round(width * word.height / word.width)), Image.LANCZOS)
    tint = Image.new("RGBA", word.size, colour + (255,))
    tint.putalpha(word.getchannel("A"))
    return tint


def please_stand_by():
    img = Image.new("RGB", (W, H), (0, 0, 0))
    lines(img, [("PLEASE STAND BY", WHITE)])
    return img


def station_ident():
    img = Image.new("RGB", (W, H), DARK)
    mark = wordmark(420, (90, 175, 245))
    img.paste(mark, ((W - mark.width) // 2, 150), mark)
    lines(img, [("we now return you", WHITE), ("to your programme", WHITE)], top=150 + mark.height + 40)
    return img


def up_next():
    img = Image.new("RGB", (W, H), DARK)
    lines(img, [("UP NEXT", GOLD), ("", WHITE), ("stay tuned", WHITE)])
    return img


CLIPS = {
    "Colour bars 10s": make_open.still,
    "Colour bars 60s": make_open.still,
    "Please stand by 30s": please_stand_by,
    "Station ident 15s": station_ident,
    "Up next 20s": up_next,
}


def length(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def make(name, picture, out_dir):
    old = os.path.join(OLD, name + ".avi")
    png = os.path.join(out_dir, "_ident.png")
    picture().save(png)
    avi = os.path.join(out_dir, name + ".avi")
    secs = length(old)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
           "-loop", "1", "-framerate", "24000/1001", "-i", png, "-i", old,
           "-map", "0:v", "-map", "1:a", "-t", f"{secs:.3f}",
           "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "4", "-r", "24000/1001",
           "-c:a", "copy", avi]
    subprocess.run(cmd, check=True)
    os.remove(png)
    print(f"  {name}: {length(avi):.2f} s (was {secs:.2f} s)")


def main():
    root = make_open.card()
    if not root:
        raise SystemExit("the card is not in the reader")
    out_dir = os.path.join(root, "videos", "_breaks")
    for name, picture in CLIPS.items():
        make(name, picture, out_dir)


if __name__ == "__main__":
    main()
