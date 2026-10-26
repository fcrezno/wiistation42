"""Draws an "UP NEXT" bumper for every show.

  py -3 make_upnext.py

One clip per show, written to videos/_breaks/_upnext/<Show>.avi. The planner
puts the right one at the END of the break, so it plays just before the
programme it announces. They live under _breaks so that Z skips them like any
other break, but the planner keeps them out of the random filler.
"""
import glob
import os
import subprocess

from PIL import Image, ImageDraw

import pixelfont

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
MUSIC = os.path.join(os.path.dirname(HERE), "art", "truemenu.mp3")
W, H, LENGTH = 640, 480, 8
NAVY = (16, 24, 56)
BARS = [(192,192,192),(192,192,0),(0,192,192),(0,192,0),(192,0,192),(192,0,0),(0,0,192)]


def card(dir):
    """The Wii card: apps, videos and wiistation42 all on the same drive."""
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = letter + ":" + chr(92)
        if all(os.path.isdir(os.path.join(root, d)) for d in ("apps", "videos", "wiistation42")):
            return root
    return None


def wrap(text, max_w):
    """Words onto lines no wider than max_w: a long name wraps, it never shrinks."""
    out, line = [], ""
    for word in pixelfont.ascii_only(text).split():
        trial = (line + " " + word).strip()
        if line and pixelfont.width(trial, 2) > max_w:
            out.append(line)
            line = word
        else:
            line = trial
    return out + ([line] if line else [])


def draw(show, path):
    """crezno's font at one size (scale 2), like every other WiiStation 42 screen."""
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(BARS):                       # the test card behind
        d.rectangle([round(W * i / 7), 0, round(W * (i + 1) / 7) - 1, H], fill=c)
    names = wrap(show, W - 130)
    step = 34
    box_h = 36 + step * (2 + len(names)) + 16
    top = (H - box_h) // 2
    d.rounded_rectangle([40, top, W - 40, top + box_h], 26, fill=NAVY + (255,),
                        outline=(150, 200, 255), width=3)
    y = top + 24
    pixelfont.draw(im, "UP NEXT", (W // 2, y), scale=2, colour=(255, 200, 80), centre=True)
    y += step * 2
    for line in names:
        pixelfont.draw(im, line, (W // 2, y), scale=2, colour=(255, 255, 255), centre=True)
        y += step
    im.save(path)


def main():
    root = card(None)
    if not root:
        raise SystemExit("the card is not in the reader")
    videos = os.path.join(root, "videos")
    out_dir = os.path.join(videos, "_breaks", "_upnext")
    os.makedirs(out_dir, exist_ok=True)

    shows = sorted(n for n in os.listdir(videos)
                   if os.path.isdir(os.path.join(videos, n)) and not n.startswith("_"))
    png = os.path.join(out_dir, "frame.png")
    for show in shows:
        avi = os.path.join(out_dir, show + ".avi")
        draw(show, png)
        cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
               "-loop", "1", "-t", str(LENGTH), "-i", png,
               "-i", MUSIC, "-t", str(LENGTH),
               "-af", f"volume=1.4,afade=t=out:st={LENGTH-1.2}:d=1.2",
               "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "5", "-r", "24000/1001",
               "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000", avi]
        subprocess.run(cmd, check=True)
        print(f"  {show}: {os.path.getsize(avi)/1e6:.1f} MB")
    os.remove(png)
    print(f"{len(shows)} bumpers in {out_dir}")


if __name__ == "__main__":
    main()
