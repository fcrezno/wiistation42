"""WiiStation 42 guide as a cable-box grid, like the Time Warner Cable guide.

Channels go down the left side, the time goes across the top in half hours,
and every programme is a block as wide as it runs. One page is drawn for each
half hour of the week, so the guide channel always shows what is on now.

  py -3 guide_grid.py mock [<channel folder>]   draws one page for this minute
"""
import datetime
import os
import re
import sys

from PIL import Image, ImageDraw

import pixelfont
from guide import read_channel_file

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), "art")
W, H = 640, 480
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

NAVY = (16, 24, 56)
CHAN_BG = (22, 32, 70)
CELL = (30, 60, 120)
CELL_NOW = (40, 78, 150)
OFF = (24, 28, 44)
HEAD = (60, 90, 160)
LINE = (90, 140, 220)
WHITE = (240, 244, 252)
DIM = (170, 190, 230)
GREY = (120, 128, 150)
GREEN = (80, 235, 90)
GOLD = (255, 200, 80)

LEFT, RIGHT = 24, W - 24           # the picture a CRT really shows
CHAN_W = 158                      # the channel column
SLOT = 1800                       # half an hour
SLOTS = 3                         # half hours on one page
TOP_BAND, TIME_ROW = 100, 32
ROW_H, GAP = 46, 2

# Channels with no programmes of their own get a line that says what they are.
FIXED = {"guide": "What is on, all channels", "controls": "How to use the controls",
         "weatherbox": "Local forecast"}
TITLES = {"weather": "Local forecast", "controls": "How to use the controls"}


def clock12(sec):
    h, m = sec // 3600 % 24, sec % 3600 // 60
    return f"{(h + 11) % 12 + 1}:{m:02d} {'AM' if h < 12 else 'PM'}"


def split_title(title):
    """'The Simpsons S02E10 Bart Gets Hit by a Car' -> ('The Simpsons', 'Bart Gets Hit by a Car')."""
    m = re.match(r"^(.*?)\s+S(\d+)[EX](\d+)\s*-?\s*(.*)$", title)
    if m:
        show, s, e, name = m.groups()
        return show, name or f"Season {int(s)}, episode {int(e)}"
    m = re.match(r"^(.*?)\s+-\s+(.*)$", title)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^(.*?)\s+(\d{1,3})$", title)
    if m:
        return m.group(1), f"Episode {int(m.group(2))}"
    return title, ""


def fit(s, max_w, scale=1):
    """Cuts a line to fit the cell, with '...' when it had to be cut."""
    s = pixelfont.ascii_only(s)
    if pixelfont.width(s, scale) <= max_w:
        return s
    while s and pixelfont.width(s + "...", scale) > max_w:
        s = s[:-1]
    return s.rstrip() + "..." if s else ""


def blocks(channel, day, start, end):
    """The programmes of one channel between start and end (seconds of the
    week), each as (from, to, title). Gaps are Off Air. Same titles side by
    side are one block, so a looping weather page reads as one programme."""
    items = []
    for d in range(7):
        for it in channel["days"][d]:
            s = d * 86400 + it["start"]
            items.append((s, it["name"]))
    items.sort()
    week = 7 * 86400
    out = []
    for i, (s, name) in enumerate(items):
        nxt = items[i + 1][0] if i + 1 < len(items) else items[0][0] + week
        length = next(it["length"] for it in channel["days"][s // 86400 % 7]
                      if it["start"] == s % 86400)
        # a programme runs until the next one starts, breaks included, unless
        # the schedule leaves a gap (the station is off air then)
        stop = nxt if nxt - (s + length) < 600 else s + length
        for shift in (-week, 0, week):
            a, b = s + shift, stop + shift
            if b > start and a < end:
                out.append((max(a, start), min(b, end), TITLES.get(name.lower(), name),
                            a < start, b > end))
    out.sort()
    merged = []
    for blk in out:
        if merged and merged[-1][2] == blk[2] and merged[-1][1] >= blk[0] - 1:
            a = merged[-1]
            merged[-1] = (a[0], blk[1], a[2], a[3], blk[4])
        else:
            merged.append(blk)
    # fill the holes with Off Air
    filled, t = [], start
    for a, b, name, lcut, rcut in merged:
        if a > t:
            filled.append((t, a, None, False, False))
        filled.append((a, b, name, lcut, rcut))
        t = b
    if t < end:
        filled.append((t, end, None, False, False))
    return filled


def draw_page(channels, day, slot_sec, now_sec=None):
    """One page: the half hour that starts at slot_sec on this day, and the
    two after it."""
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)

    # the band at the top: the wordmark, the day and the time
    word = Image.open(os.path.join(ART, "wordmark.png")).convert("RGBA")
    ww = 230
    word = word.resize((ww, round(ww * word.height / word.width)), Image.LANCZOS)
    white = Image.new("RGBA", word.size, WHITE + (255,))
    white.putalpha(word.getchannel("A"))
    img.paste(white, (LEFT, 18 + (56 - word.height) // 2), white)
    # one text size on the whole page (crezno: "make the font uniform")
    pixelfont.draw(img, DAYS[day], (RIGHT, 18), scale=1, colour=GOLD, right=True)
    pixelfont.draw(img, clock12(slot_sec), (RIGHT, 42), scale=1, colour=WHITE, right=True)
    pixelfont.draw(img, "L / R  change channel     START  menu", (LEFT, 72), scale=1, colour=GREY)

    # the time row
    grid_x = LEFT + CHAN_W + GAP
    grid_w = RIGHT - grid_x
    y = TOP_BAND
    d.rectangle([LEFT, y, LEFT + CHAN_W - 1, y + TIME_ROW - 1], fill=HEAD)
    pixelfont.draw(img, "Today", (LEFT + 10, y + 3), scale=1, colour=WHITE)
    col_w = grid_w / SLOTS
    for i in range(SLOTS):
        x0 = round(grid_x + i * col_w)
        x1 = round(grid_x + (i + 1) * col_w) - GAP
        d.rectangle([x0, y, x1, y + TIME_ROW - 1], fill=HEAD)
        pixelfont.draw(img, clock12(slot_sec + i * SLOT), (x0 + 8, y + 3), scale=1,
                       colour=GOLD if i == 0 else WHITE)
    d.line([(LEFT, y + TIME_ROW), (RIGHT, y + TIME_ROW)], fill=LINE, width=2)

    start = day * 86400 + slot_sec
    end = start + SLOTS * SLOT
    y += TIME_ROW + 4
    for ch in channels:
        d.rectangle([LEFT, y, LEFT + CHAN_W - 1, y + ROW_H - 1], fill=CHAN_BG)
        pixelfont.draw(img, str(ch["number"]), (LEFT + 10, y + (ROW_H - 24) // 2), scale=1, colour=GREEN)
        pixelfont.draw(img, fit(ch["name"], CHAN_W - 42), (LEFT + 36, y + (ROW_H - 24) // 2),
                       scale=1, colour=WHITE)

        cells = blocks(ch, day, start, end)
        if not any(c[2] for c in cells) and ch["name"].lower() in FIXED:
            cells = [(start, end, FIXED[ch["name"].lower()], False, False)]
        for a, b, name, lcut, rcut in cells:
            x0 = round(grid_x + (a - start) / (end - start) * grid_w)
            x1 = round(grid_x + (b - start) / (end - start) * grid_w) - GAP
            if x1 - x0 < 4:
                continue
            on_now = now_sec is not None and a <= start + now_sec - slot_sec < b
            d.rectangle([x0, y, x1, y + ROW_H - 1], fill=OFF if name is None else (CELL_NOW if on_now else CELL))
            room = x1 - x0 - 16
            tx = x0 + 8
            if lcut:
                pixelfont.draw(img, "<", (x0 + 5, y + (ROW_H - 24) // 2), scale=1, colour=DIM)
                tx += 10
                room -= 10
            if rcut:
                pixelfont.draw(img, ">", (x1 - 5, y + (ROW_H - 24) // 2), scale=1, colour=DIM, right=True)
                room -= 10
            if name is None:
                pixelfont.draw(img, fit("Off Air", room), (tx, y + (ROW_H - 24) // 2), scale=1, colour=GREY)
                continue
            show, episode = split_title(name)
            if episode and room > 40:
                pixelfont.draw(img, fit(show, room), (tx, y + 2), scale=1, colour=WHITE)
                pixelfont.draw(img, fit(episode, room), (tx, y + 20), scale=1, colour=DIM)
            else:
                pixelfont.draw(img, fit(show, room), (tx, y + (ROW_H - 24) // 2), scale=1, colour=WHITE)
        y += ROW_H + GAP
    return img


def load_channels(folder):
    files = sorted(f for f in os.listdir(folder) if re.match(r"(?i)channel\d+\.txt$", f))
    chans = [read_channel_file(os.path.join(folder, f)) for f in files]
    chans.sort(key=lambda c: c["number"])
    return chans


MUSIC = os.path.join(ART, "guide_music_loop.wav")
CLIP = 63            # seconds: three passes of crezno's 21 second guide loop, so it never jumps
FFMPEG = None


def ffmpeg():
    global FFMPEG
    if FFMPEG is None:
        import glob
        FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
    return FFMPEG


def encode(png, avi):
    import subprocess
    cmd = [ffmpeg(), "-hide_banner", "-v", "error", "-y",
           "-loop", "1", "-framerate", "12", "-i", png,
           "-stream_loop", "-1", "-i", MUSIC, "-t", str(CLIP),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "4", "-g", "120", "-r", "12",
           "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000", avi]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("guide page failed: " + r.stderr.strip()[-300:])


def make_guide_grid(channel_files, video_dir, wii_root="sd1:/videos", guide_name="Guide", workers=4):
    """A page for every half hour of the week, from the channel files that
    will really play. Returns the lines of the guide channel."""
    from concurrent.futures import ThreadPoolExecutor
    channels = [read_channel_file(p) for p in channel_files]
    channels.sort(key=lambda c: c["number"])
    # the guide lists itself too, as channel 0
    if not any(c["number"] == 0 for c in channels):
        channels.insert(0, {"name": guide_name, "number": 0, "days": [[] for _ in range(7)]})
    out_dir = os.path.join(video_dir, "_guide", "grid")
    os.makedirs(out_dir, exist_ok=True)

    jobs, lines = [], [f"name {guide_name}",
                       "# the listings grid of every channel, made by guide_grid.py"]
    for day in range(7):
        for slot in range(0, 86400, SLOT):
            name = f"d{day}-{slot // 3600:02d}{slot % 3600 // 60:02d}"
            png = os.path.join(out_dir, name + ".png")
            draw_page(channels, day, slot, slot).save(png)
            jobs.append((png, os.path.join(out_dir, name + ".avi")))
            t = slot
            while t < slot + SLOT:            # the page loops for its half hour
                length = min(CLIP, slot + SLOT - t)
                lines.append(f"{day} {t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d} {length} "
                             f"{wii_root}/_guide/grid/{name}.avi")
                t += length

    def run(job):
        png, avi = job
        encode(png, avi)
        os.remove(png)

    with ThreadPoolExecutor(workers) as pool:
        for n, _ in enumerate(pool.map(run, jobs), 1):
            if n % 48 == 0:
                print(f"  guide pages: {n}/{len(jobs)}")
    return lines


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mock":
        folder = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(HERE), "card", "wiistation42")
        now = datetime.datetime.now()
        day = (now.weekday() + 1) % 7          # Python: Monday 0; the channel files: Sunday 0
        sec = now.hour * 3600 + now.minute * 60
        slot = sec // SLOT * SLOT
        page = draw_page(load_channels(folder), day, slot, sec)
        out = os.path.join(HERE, "guide_grid_mock.png")
        page.save(out)
        print("mock page:", out)
