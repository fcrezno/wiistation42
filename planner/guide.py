"""WiiStation 42 guide channel: a listings page that scrolls, like cable TV.

For each day it draws the programmes of that day into a tall picture, then makes
a video where the picture scrolls upwards and wraps, so the channel can show it
all day. The planner calls make_guide(); it can also run on its own:

  py -3 guide.py            uses week.json beside this file
"""
import glob
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
# crezno's own menu theme, made to loop into itself by art/make the bed script
MUSIC = os.path.join(os.path.dirname(HERE), "art", "guide_music_loop.wav")

W, H = 640, 480            # the picture of the Wii
ROW = 38                   # one programme per row
GUIDE_SECONDS = 600        # how long one guide video runs
BG, HEAD, TEXT, TIME, ALT = (16, 24, 56), (30, 60, 120), (235, 240, 250), (255, 200, 80), (22, 32, 70)


def clock(sec):
    return f"{sec // 3600 % 24:02d}:{sec % 3600 // 60:02d}"


def draw_day(day, items, start, out_png, channel_name):
    """A tall picture: every programme of the day, one per row."""
    rows = [it for it in items if not it.get("isBreak")]
    height = max(H + ROW, len(rows) * ROW + 8)
    img = Image.new("RGB", (W, height), BG)
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 22)

    clock_at = start
    y = 4
    for i, it in enumerate(rows):
        if i % 2:
            d.rectangle([0, y, W, y + ROW - 2], fill=ALT)
        d.text((10, y + 7), clock(clock_at), font=mono, fill=TIME)
        name = it["name"]
        while d.textlength(name, font=mono) > W - 110 and len(name) > 4:
            name = name[:-2]
        d.text((100, y + 7), name, font=mono, fill=TEXT)
        clock_at += int(it["length"])
        y += ROW

    img.save(out_png)
    return height


def draw_header(day, channel_name, out_png):
    """The bar that stays at the top of the screen."""
    img = Image.new("RGBA", (W, 74), HEAD + (255,))
    d = ImageDraw.Draw(img)
    big = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 30)
    small = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18)
    d.text((14, 10), channel_name, font=big, fill=(255, 255, 255))
    d.text((16, 46), DAYS[day] + " - what is on today", font=small, fill=(180, 200, 240))
    d.line([(0, 72), (W, 72)], fill=(90, 140, 220), width=2)
    img.save(out_png)


def make_guide(week, day_start, channel_name, video_dir, wii_root="sd1:/videos"):
    """Writes guide-<day>.avi for every day. Returns the lines for a channel file."""
    out_dir = os.path.join(video_dir, "_guide")
    os.makedirs(out_dir, exist_ok=True)
    lines = []
    for day, items in enumerate(week):
        if not items:
            continue
        page = os.path.join(out_dir, f"page{day}.png")
        head = os.path.join(out_dir, f"head{day}.png")
        height = draw_day(day, items, day_start, page, channel_name)
        draw_header(day, channel_name, head)
        avi = os.path.join(out_dir, f"guide-{day}.avi")
        # MEASURED, not guessed: the scroll filter moves speed x page height x
        # frames per second pixels each second. A whole number of passes makes
        # the video loop without a jump, and about 14 px a second is readable.
        passes = max(1, round(GUIDE_SECONDS * 14 / height))
        speed = passes / (GUIDE_SECONDS * 24000 / 1001)
        cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
               "-loop", "1", "-i", page, "-i", head,
               *(("-stream_loop", "-1", "-i", MUSIC) if os.path.isfile(MUSIC)
               else ("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo")),
               "-t", str(GUIDE_SECONDS),
               "-filter_complex",
               f"[0:v]scroll=vertical={speed:.5f},crop={W}:{H}:0:0[s];[s][1:v]overlay=0:0[v]",
               "-map", "[v]", "-map", "2:a",
               "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "6", "-r", "24000/1001",
               "-af", "volume=1.4", "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000",
               avi]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("guide video failed: " + r.stderr.strip()[-300:])
        os.remove(page)
        os.remove(head)
        wii = f"{wii_root}/_guide/guide-{day}.avi"
        t = day_start
        while t < day_start + 86400:            # the guide runs all day, on repeat
            s = t % 86400
            lines.append(f"{day} {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d} {GUIDE_SECONDS} {wii}")
            t += GUIDE_SECONDS
    return lines


def read_channel_file(path):
    """Reads a built channel file back into days of programmes, so the guide
    shows exactly what the Wii will play. Break clips are left out."""
    name, number = os.path.basename(path), 0
    digits = "".join(c for c in os.path.basename(path) if c.isdigit())
    number = int(digits) if digits else 0
    days = [[] for _ in range(7)]
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("name "):
            name = line[5:].strip()
            continue
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ", 3)
        if len(parts) < 4:
            continue
        day, hhmmss, length, file = parts
        if "/_breaks/" in file or "/_guide/" in file:
            continue
        h, m, sec = (int(v) for v in hhmmss.split(":"))
        title = os.path.splitext(os.path.basename(file))[0]
        days[int(day)].append({"start": h * 3600 + m * 60 + sec,
                               "length": int(length), "name": title})
    return {"name": name, "number": number, "days": days}


def draw_day_all(day, channels, out_png):
    """One tall picture for the day: a block for every channel."""
    rows = []
    for ch in channels:
        items = sorted(ch["days"][day], key=lambda it: (it["start"] - 6 * 3600) % 86400)
        if not items:
            continue
        rows.append(("head", f"{ch['number']}  {ch['name']}"))
        rows += [("prog", clock(it["start"]), it["name"]) for it in items]
    # The bar at the top of the screen is 74 px tall and hides the start of the
    # page, so the first channel's header would never be seen. Leave room for it.
    TOP = 78
    height = max(H + ROW, len(rows) * ROW + 8 + TOP)
    img = Image.new("RGB", (W, height), BG)
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 22)
    head_font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)

    y, stripe = 4 + TOP, 0
    for row in rows:
        if row[0] == "head":
            d.rectangle([0, y, W, y + ROW - 2], fill=HEAD)
            d.text((12, y + 7), row[1], font=head_font, fill=(255, 255, 255))
            stripe = 0
        else:
            if stripe % 2:
                d.rectangle([0, y, W, y + ROW - 2], fill=ALT)
            d.text((10, y + 7), row[1], font=mono, fill=TIME)
            name = row[2]
            while d.textlength(name, font=mono) > W - 110 and len(name) > 4:
                name = name[:-2]
            d.text((100, y + 7), name, font=mono, fill=TEXT)
            stripe += 1
        y += ROW
    img.save(out_png)
    return height


def make_guide_all(channel_files, video_dir, wii_root="sd1:/videos", guide_name="WiiStation 42 guide"):
    """Builds guide-<day>.avi from the channel files themselves. Returns the
    lines of the guide channel."""
    channels = [read_channel_file(p) for p in channel_files]
    channels.sort(key=lambda c: c["number"])
    out_dir = os.path.join(video_dir, "_guide")
    os.makedirs(out_dir, exist_ok=True)
    lines = [f"name {guide_name}", "# the listings of every channel, made by guide.py"]
    for day in range(7):
        page = os.path.join(out_dir, f"page{day}.png")
        head = os.path.join(out_dir, f"head{day}.png")
        height = draw_day_all(day, channels, page)
        draw_header(day, guide_name, head)
        avi = os.path.join(out_dir, f"guide-{day}.avi")
        passes = max(1, round(GUIDE_SECONDS * 14 / height))
        speed = passes / (GUIDE_SECONDS * 24000 / 1001)
        cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
               "-loop", "1", "-i", page, "-i", head,
               *(("-stream_loop", "-1", "-i", MUSIC) if os.path.isfile(MUSIC)
                 else ("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo")),
               "-t", str(GUIDE_SECONDS),
               "-filter_complex",
               f"[0:v]scroll=vertical={speed:.8f},crop={W}:{H}:0:0[s];[s][1:v]overlay=0:0[v]",
               "-map", "[v]", "-map", "2:a",
               "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "6", "-r", "24000/1001",
               "-af", "volume=1.4", "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000",
               avi]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("guide video failed: " + r.stderr.strip()[-300:])
        os.remove(page)
        os.remove(head)
        print(f"day {day}: {height} px, {passes} passes, "
              f"{speed*height*24000/1001:.1f} px a second")
        t = 0
        while t < 86400:
            lines.append(f"{day} {t//3600:02d}:{t%3600//60:02d}:{t%60:02d} {GUIDE_SECONDS} "
                         f"{wii_root}/_guide/guide-{day}.avi")
            t += GUIDE_SECONDS
    return lines


if __name__ == "__main__":
    p = json.load(open(os.path.join(HERE, "week.json"), encoding="utf-8"))
    lines = make_guide(p["week"], p.get("dayStart", 6 * 3600), p.get("name", "WiiStation 42"),
                       os.environ.get("WS42_VIDEOS", "videos"))
    head = ["name Guide", "# the listings channel, made by guide.py"]
    open(os.path.join(HERE, "channel2.txt"), "w", encoding="utf-8", newline="\r\n").write(
        "\n".join(head + lines) + "\n")
    print(len(lines), "lines -> channel2.txt")
