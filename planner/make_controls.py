"""Draws the controls card and makes it a channel you can tune to.

  py -3 make_controls.py

Two pages, 30 seconds each: the buttons, then the picture settings that the
player already has in its own menu (nothing is forced; they are yours to set).
It writes videos/_guide/controls.avi and planner/channel4.txt, so the card can
be reached like any other channel. Run it again whenever the buttons change.
"""
import glob
import os
import subprocess

from PIL import Image, ImageDraw

import pixelfont

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
VIDEO_DIR = os.environ.get("WS42_VIDEOS", "videos")   # the folder with your videos
# crezno's own menu theme, made to loop into itself by art/make the bed script
MUSIC = os.path.join(os.path.dirname(HERE), "art", "guide_music_loop.wav")
PAGE = 30             # seconds for each page
LENGTH = PAGE * 2     # one showing, then the channel plays it again

BUTTONS = [
    ("D-pad left / right", "tap = skip, hold = scan"),
    ("C-stick left / right", "smooth scan; push = speed"),
    ("L / R", "channel down / up"),
    ("L + R together", "start this programme again"),
    ("Z", "skip the break"),
    ("A", "pause"),
    ("B", "show the bar"),
    ("X / Y", "volume down / up"),
    ("START", "the WiiStation 42 menu"),
    ("#", "In that menu: D-pad up / down, A to choose, B to go back"),
]

PICTURE = [
    ("#", "Press START, choose Media menu, then Settings"),
    ("#", "Settings - Global"),
    ("Double Strike", "240p, the picture a tube wants"),
    ("Night Filter", "warmer colours, late at night"),
    ("Screen Burn-in Reduction", "dims a still picture"),
    ("#", "Settings - Videos"),
    ("Screen Zoom", "how big the picture is"),
    ("Screen Position", "move it left, right, up or down"),
    ("Aspect Ratio", "the shape of the picture"),
    ("Deflicker", "smooth 480i; off at 240p"),
    ("Set VI Width to 720", "all the pixels the Wii sends"),
]


def draw(path, subtitle, rows, key_x, what_x, row_h, top):
    """Every word in crezno's font at one size (scale 1: this card is a dense
    table); the station name is the wordmark."""
    img = Image.new("RGB", (640, 480), (16, 24, 56))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, 640, 74], fill=(30, 60, 120))
    word = Image.open(os.path.join(os.path.dirname(HERE), "art", "wordmark.png")).convert("RGBA")
    word = word.resize((200, round(200 * word.height / word.width)), Image.LANCZOS)
    white = Image.new("RGBA", word.size, (255, 255, 255, 255))
    white.putalpha(word.getchannel("A"))
    img.paste(white, (32, 12), white)
    pixelfont.draw(img, subtitle, (32, 44), scale=1, colour=(180, 200, 240))
    d.line([(0, 72), (640, 72)], fill=(90, 140, 220), width=2)

    y = top
    stripe = 0
    for key, what in rows:
        if key == "#":
            pixelfont.draw(img, what, (32, y), scale=1, colour=(120, 190, 255))
            stripe = 0
        else:
            if stripe % 2:
                d.rectangle([0, y - 3, 640, y + row_h - 5], fill=(22, 32, 70))
            pixelfont.draw(img, key, (key_x, y), scale=1, colour=(255, 200, 80))
            pixelfont.draw(img, what, (what_x, y), scale=1, colour=(235, 240, 250))
            stripe += 1
        y += row_h
    pixelfont.draw(img, "0 Guide  1 AniBox  2 AniBoxEX  3 LaffBox  4 WeatherBox  9 Controls",
                   (32, 440), scale=1, colour=(141, 151, 171))
    img.save(path)


def main():
    out_dir = os.path.join(VIDEO_DIR, "_guide")
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, "controls1.png")
    p2 = os.path.join(out_dir, "controls2.png")
    avi = os.path.join(out_dir, "controls.avi")
    draw(p1, "the buttons on the GameCube controller", BUTTONS, 34, 250, 33, 86)
    draw(p2, "the picture settings, in the menu of the player", PICTURE, 34, 300, 31, 84)

    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
           "-loop", "1", "-t", str(PAGE), "-i", p1,
           "-loop", "1", "-t", str(PAGE), "-i", p2,
           *(("-stream_loop", "-1", "-i", MUSIC) if os.path.isfile(MUSIC)
               else ("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo")),
           "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
           "-map", "[v]", "-map", "2:a", "-t", str(LENGTH),
           "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "6", "-r", "24000/1001",
           "-af", "volume=1.25", "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000", avi]
    subprocess.run(cmd, check=True)
    os.remove(p1)
    os.remove(p2)

    lines = ["name Controls", "# the controls card, made by make_controls.py"]
    for day in range(7):
        t = 0
        while t < 86400:
            lines.append(f"{day} {t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d} "
                         f"{LENGTH} sd1:/videos/_guide/controls.avi")
            t += LENGTH
    open(os.path.join(HERE, "channel9.txt"), "w", encoding="utf-8", newline="\r\n").write("\n".join(lines) + "\n")
    print("made", avi, f"({os.path.getsize(avi)/1e6:.1f} MB) and channel9.txt with {len(lines)-2} lines")


if __name__ == "__main__":
    main()
