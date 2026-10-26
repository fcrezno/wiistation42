"""Builds everything and puts it on the card, in one go.

  py -3 finish.py

  1. every station file becomes a channel file (1, 3, 5 ...)
  2. the guide channel is drawn from those channel files, so it shows what
     will really play, with a block for each channel
  3. the applications and the channel files go on the card
  4. every path that the channel files name is checked on the card
"""
import glob
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import guide_grid               # noqa: E402
import server                   # noqa: E402
import stations                 # noqa: E402

STATIONS = os.path.join(os.path.dirname(HERE), "stations")
APPS = os.path.join(os.path.dirname(HERE), "card", "apps")


def build_stations(card):
    """One channel file for each station file."""
    made = []
    for conf_path in sorted(glob.glob(os.path.join(STATIONS, "*.json"))):
        conf = json.load(open(conf_path, encoding="utf-8"))
        content = conf.get("content_dir", os.path.join(card, "videos"))
        catalog = stations.Catalog(content, server.probe_length)
        seq = stations.Sequences(os.path.join(HERE, "sequences.json"))
        lines = stations.build(conf, catalog, seq, random.Random())
        seq.save()
        number = int(conf.get("channel_number", len(made) + 1))
        name = f"channel{number}.txt"
        server.write_lines(lines, name)
        made.append((number, conf.get("network_name"), len(lines) - 3, name))
        print(f"  channel {number}: {conf.get('network_name')} - {len(lines)-3} programmes")
    return made


def build_guide(card, made):
    """The listings channel, from the channel files themselves: a cable-box
    grid, one page for every half hour of the week (guide_grid.py)."""
    files = [os.path.join(HERE, n) for _, _, _, n in made]
    # the weather and the controls are channels too, so the grid lists them
    for extra in ("channel4.txt", "channel9.txt"):
        if os.path.isfile(os.path.join(HERE, extra)):
            files.append(os.path.join(HERE, extra))
    lines = guide_grid.make_guide_grid(files, os.path.join(card, "videos"), guide_name="Guide")
    server.write_lines(lines, "channel0.txt")
    print(f"  guide: {len(lines)-2} lines, {7 * 48} pages")


def copy_apps(card):
    for app in os.listdir(APPS):
        src, dst = os.path.join(APPS, app), os.path.join(card, "apps", app)
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(src):
            shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
        print(f"  {app}: {len(os.listdir(dst))} files")
    # the controls channel is made by make_controls.py and lives beside the planner
    for extra in ("channel9.txt",):
        here = os.path.join(HERE, extra)
        if os.path.isfile(here):
            shutil.copy2(here, os.path.join(card, "wiistation42", extra))
            print(f"  {extra} copied")


def check(card):
    """Every file a channel names must be on the card."""
    bad = 0
    for ch in sorted(glob.glob(os.path.join(card, "wiistation42", "channel*.txt"))):
        want = set()
        for line in open(ch, encoding="utf-8", errors="replace"):
            parts = line.strip().split(" ", 3)
            if len(parts) == 4 and parts[3].startswith("sd1:/"):
                want.add(parts[3][5:])        # "sd1:/" is five characters
        missing = [p for p in want if not os.path.isfile(os.path.join(card, p.replace("/", os.sep)))]
        bad += len(missing)
        print(f"  {os.path.basename(ch)}: {len(want)} different files, {len(missing)} missing")
        for m in sorted(missing)[:5]:
            print("     MISSING", m)
    return bad


def main():
    card = server.wii_card()
    if not card:
        sys.exit("the card is not in the reader")
    print(f"card: {card}")
    print("stations:")
    made = build_stations(card)
    print("guide:")
    build_guide(card, made)
    print("applications:")
    copy_apps(card)
    print("checking the card:")
    bad = check(card)
    json.dump(server.lengths, open(server.CACHE, "w", encoding="utf-8"))
    free = shutil.disk_usage(card)[2] / 1e9
    print(f"\n{'ALL GOOD' if bad == 0 else str(bad) + ' FILES MISSING'} - {free:.1f} GB free on the card")


if __name__ == "__main__":
    main()
