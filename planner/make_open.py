"""The opening: what you see when WiiStation 42 starts.

  py -3 make_open.py

Colour bars, crezno's wordmark on the navy plate, the chime. It fades up from
black, holds, and fades out, and the station then joins channel 1 in the middle
of whatever is on. Written to the staging folder and, if it is in, the card.
"""
import glob
import math
import os
import subprocess

from PIL import Image, ImageDraw

import pixelfont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), "art")
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
W, H, FPS, SECONDS = 640, 480, 24, 5.0
NAVY = (16, 24, 56)
BARS = [(192,192,192),(192,192,0),(0,192,192),(0,192,0),(192,0,192),(192,0,0),(0,0,192)]
STRIP = [(0,0,192),(17,17,17),(192,0,192),(17,17,17),(0,192,192),(17,17,17),(192,192,192)]


def card():
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = letter + ":" + chr(92)
        if all(os.path.isdir(os.path.join(root, d)) for d in ("apps", "videos", "wiistation42")):
            return root
    return None


def still():
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    top, mid = int(H * 0.67), int(H * 0.75)
    for i, c in enumerate(BARS):
        d.rectangle([round(W * i / 7), 0, round(W * (i + 1) / 7) - 1, top - 1], fill=c)
    for i, c in enumerate(STRIP):
        d.rectangle([round(W * i / 7), top, round(W * (i + 1) / 7) - 1, mid - 1], fill=c)
    d.rectangle([0, mid, W, H], fill=(17, 17, 17))

    word = Image.open(os.path.join(ART, "wordmark.png")).convert("RGBA")
    word_w = int(W * 0.8)
    word = word.resize((word_w, round(word_w * word.height / word.width)), Image.LANCZOS)
    white = Image.new("RGBA", word.size, (255, 255, 255, 255))
    white.putalpha(word.getchannel("A"))
    # the line under the wordmark is the one text size the station uses
    # everywhere (scale 2, as in the app's overlay and menu)
    box_h = word.height + 22 + 48 + 10
    top_y = (H - box_h) // 2
    x = (W - word_w) // 2
    d.rounded_rectangle([x - 22, top_y, W - x + 22, top_y + box_h], 26,
                        fill=NAVY, outline=(150, 200, 255), width=3)
    im.paste(white, (x, top_y + 22), white)
    pixelfont.draw(im, "your own television station", (W // 2, top_y + 22 + word.height + 4),
                   scale=2, colour=(200, 220, 255), centre=True)
    return im


def main():
    base = still()
    black = Image.new("RGB", (W, H))
    outs = [os.path.join(os.path.dirname(HERE), "card", "wiistation42", "open.avi")]
    c = card()
    if c:
        outs.append(os.path.join(c, "wiistation42", "open.avi"))

    chime = os.path.join(ART, "sound_chime.wav")
    first = outs[0]
    os.makedirs(os.path.dirname(first), exist_ok=True)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", chime, "-t", str(SECONDS), "-map", "0:v", "-map", "1:a", "-af", "apad",
           "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "4", "-g", "48",
           "-c:a", "libmp3lame", "-b:a", "128k", "-ac", "2", "-ar", "48000", first]
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    frames = int(SECONDS * FPS)
    for n in range(frames):
        t = n / FPS
        if t < 0.6:
            k = t / 0.6                               # up from black
        elif t > SECONDS - 0.8:
            k = max(0.0, (SECONDS - t) / 0.8)        # down into the channel
        else:
            k = 1.0
        pipe.stdin.write(Image.blend(black, base, k).tobytes())
    pipe.stdin.close()
    if pipe.wait() != 0:
        raise SystemExit("the opening failed")
    for extra in outs[1:]:
        with open(first, "rb") as a, open(extra, "wb") as b:
            b.write(a.read())
    print("opening written:", ", ".join(outs))


if __name__ == "__main__":
    main()
