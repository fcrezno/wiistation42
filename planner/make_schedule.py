"""WiiStation 42: build a channel file from the videos on the card.

  py -3 make_schedule.py <folder with the converted videos> <output channel file>

It reads the real length of every video, then fills each day of the week from
06:00 to 06:00 with a rotation of the shows, one episode after the other. No
gaps: every programme starts when the one before it ends. The Wii then joins
whatever should be on air, at the right second.

Line format (read by tv.cpp):
  day  start  length  file
  day    0 = Sunday ... 6 = Saturday
  start  hour:minute
  length seconds
  file   the path as the Wii sees it (sd:/videos/...)
"""
import glob
import json
import os
import subprocess
import sys

BIN = (glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0]
FFPROBE = os.path.join(BIN, "ffprobe.exe")

DAY_START = 6 * 3600          # the broadcast day starts at 06:00
DAY_LENGTH = 24 * 3600
WII_ROOT = "sd:/videos"       # how the Wii sees the folder


def length_of(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8")
    return int(float(json.loads(r.stdout)["format"]["duration"]))


def collect(root):
    """{show: [(wii path, length), ...]} for every folder of videos."""
    shows = {}
    for dirpath, _, files in os.walk(root):
        vids = sorted(f for f in files if f.lower().endswith((".avi", ".mp4", ".mkv")))
        if not vids:
            continue
        rel = os.path.relpath(dirpath, root).replace("\\", "/")
        show = rel.split("/")[0]
        items = shows.setdefault(show, [])
        for v in vids:
            full = os.path.join(dirpath, v)
            wii = WII_ROOT + "/" + (rel + "/" if rel != "." else "") + v
            items.append((wii, length_of(full)))
    return shows


def main():
    root, out = sys.argv[1], sys.argv[2]
    shows = collect(root)
    if not shows:
        sys.exit("no videos found in " + root)

    order = sorted(shows)                     # the rotation: one episode per show, in turn
    pos = {s: 0 for s in order}
    for s in order:
        print(f"{s:34s} {len(shows[s]):3d} programmes")

    lines = ["name WiiStation 42",
             "# made by make_schedule.py - day, start, length in seconds, file",
             "# day 0 = Sunday ... 6 = Saturday"]
    total = 0
    for day in range(7):
        clock = DAY_START
        while clock < DAY_START + DAY_LENGTH:
            show = order[total % len(order)]
            item, length = shows[show][pos[show] % len(shows[show])]
            pos[show] += 1
            total += 1
            start = clock % DAY_LENGTH
            lines.append(f"{day} {start // 3600:02d}:{start % 3600 // 60:02d}:{start % 60:02d} {length} {item}")
            clock += length

    open(out, "w", encoding="utf-8", newline="\r\n").write("\n".join(lines) + "\n")
    print(f"\n{total} programmes over 7 days -> {out}")
    print("first lines:")
    for l in lines[3:8]:
        print("  ", l)


if __name__ == "__main__":
    main()
