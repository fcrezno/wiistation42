"""WiiStation 42 station model - the FieldStation42 idea, made for the Wii.

FieldStation42 (MPL-2.0, shane-mason/FieldStation42) splits the work: the PC
decides what plays and when, the player only plays it. We do the same. This file
reads a station file and writes the flat channel file that the Wii reads.

A station file (JSON, one per channel):

  {
    "network_name": "WiiStation 42",
    "channel_number": 1,
    "network_type": "standard",          standard | loop | guide
    "schedule_increment": 30,            slot in minutes, 0 = one after the other
    "break_strategy": "end",             end | none   (see the note below)
    "break_duration": 180,               seconds of breaks between programmes
    "commercial_free": false,
    "content_dir": "videos",
    "commercial_dir": "_breaks",
    "off_air_video": "_breaks/Colour bars 60s.avi",
    "sign_off_video": "_breaks/Please stand by 30s.avi",
    "day_templates": {
      "weekday": {
        "6":  {"tags": "Golden Boy"},
        "20": {"tags": "Cowboy Bebop", "sequence": "bebop"},
        "2":  {"event": "signoff"}
      }
    },
    "monday": "weekday", ... "sunday": {...}
  }

Tags are the folder names under content_dir, so a tag is a show. An hour with no
slot is off air: the off-air video runs until the next slot.

Note on breaks: the Wii plays whole files, so breaks go between programmes
("end"), not inside them. Cutting an episode into reels the way FieldStation42
does would need the files cut first, which is a later job.
"""
import json
import os
import random

DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
DAY_SECONDS = 86400


class Catalog:
    """Every video under content_dir, grouped by its folder name (the tag)."""

    def __init__(self, content_dir, lengths):
        self.by_tag = {}
        # the length cache is keyed by Windows paths, so normalise before asking
        content_dir = os.path.normpath(content_dir)
        self.dir = content_dir
        for dirpath, _, files in os.walk(content_dir):
            vids = sorted(f for f in files if f.lower().endswith((".avi", ".mp4", ".mkv")))
            if not vids:
                continue
            rel = os.path.relpath(dirpath, content_dir).replace("\\", "/")
            if rel == ".":
                continue
            # an Extras folder (clean openings, credits, music videos) is not
            # episodes: Cowboy Bebop's got scheduled as 2 minute "episodes"
            if any(part.lower() == "extras" for part in rel.split("/")[1:]):
                continue
            tag = rel.split("/")[0]
            items = self.by_tag.setdefault(tag, [])
            for v in vids:
                full = os.path.normpath(os.path.join(dirpath, v))
                items.append({"name": os.path.splitext(v)[0],
                              "file": f"sd1:/videos/{rel}/{v}",
                              "length": lengths(full)})

    def tags(self):
        return sorted(self.by_tag)

    def get(self, tag):
        return self.by_tag.get(tag, [])


class Sequences:
    """Remembers how far a show has been played, so episodes come in order."""

    def __init__(self, path):
        self.path = path
        self.pos = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

    def next(self, key, items):
        i = self.pos.get(key, 0) % max(1, len(items))
        self.pos[key] = i + 1
        return items[i]

    def save(self):
        json.dump(self.pos, open(self.path, "w", encoding="utf-8"), indent=1)


def resolve_days(conf):
    """Turns "monday": "weekday" into the real slot table for all 7 days."""
    templates = conf.get("day_templates", {})
    out = {}
    for day in DAYS:
        slots = conf.get(day, {})
        if isinstance(slots, str):
            slots = templates.get(slots, {})
        out[day] = {int(h): s for h, s in slots.items()}
    return out


def pick(slot, catalog, sequences, rng):
    """One programme for a slot: in order for a sequence, else at random."""
    tags = slot.get("tags")
    if isinstance(tags, list):
        tags = rng.choice(tags) if slot.get("random_tags") else tags[0]
    if not tags:
        return None
    items = catalog.get(tags)
    if not items:
        return None
    if slot.get("sequence"):
        return sequences.next(slot["sequence"], items)
    return rng.choice(items)


def build(conf, catalog, sequences, rng=None):
    """Returns the channel file lines for a whole week."""
    rng = rng or random.Random()
    name = conf.get("network_name", "WiiStation 42")
    increment = int(conf.get("schedule_increment", 30)) * 60
    break_len = 0 if conf.get("commercial_free") else int(conf.get("break_duration", 120))
    if conf.get("break_strategy", "end") == "none":
        break_len = 0
    every_break = catalog.get(conf.get("commercial_dir", "_breaks"))
    # the "up next" bumpers are never picked at random: each one names a show,
    # so the planner puts it at the end of the break before that show
    breaks = [b for b in every_break if "/_upnext/" not in b["file"]]
    upnext = {os.path.splitext(os.path.basename(b["file"]))[0]: b
              for b in every_break if "/_upnext/" in b["file"]}
    off_air = conf.get("off_air_video")
    sign_off = conf.get("sign_off_video")
    days = resolve_days(conf)

    lines = [f"name {name}",
             f"# station {conf.get('channel_number', 1)}, made by the WiiStation 42 planner",
             "# day start(hh:mm:ss) length(seconds) file   (day 0 = Sunday ... 6 = Saturday)"]

    def add(day, start, length, path):
        s = int(start) % DAY_SECONDS
        lines.append(f"{day} {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d} {int(length)} {path}")

    for day_no, day_name in enumerate(DAYS):
        slots = days[day_name]
        clock = 0
        while clock < DAY_SECONDS:
            hour = int(clock // 3600)
            slot = slots.get(hour)

            if slot is None:                       # nothing scheduled: off air
                if off_air:
                    add(day_no, clock, 3600 - clock % 3600, wii_path(off_air))
                clock = (hour + 1) * 3600
                continue

            if slot.get("event") == "signoff":     # the station closes down
                if sign_off:
                    add(day_no, clock, 3600 - clock % 3600, wii_path(sign_off))
                clock = (hour + 1) * 3600
                continue

            marathon = slot.get("marathon") or {}
            runs = 1
            if marathon and rng.random() < float(marathon.get("chance", 0)):
                runs = int(marathon.get("episodes", 3))

            for _ in range(runs):
                item = pick(slot, catalog, sequences, rng)
                if not item:
                    break
                add(day_no, clock, item["length"], item["file"])
                clock += item["length"]

                # fill up to the next slot, the way a station fills a break
                if increment:
                    # all the way to the next slot: capped at break_len it left
                    # 2 to 3 minutes of nothing before every half hour, and the
                    # Wii then started the next programme early
                    target = ((clock // increment) + 1) * increment
                    gap = target - clock if break_len else 0
                    after = slots.get(int(target // 3600) % 24)
                else:
                    gap = break_len
                    after = slots.get(int((clock + gap) // 3600) % 24)

                bump = upnext.get((after or {}).get("tags", ""))
                if bump and bump["length"] < gap:
                    clock += fill_break(lines, add, day_no, clock,
                                        gap - bump["length"], breaks, rng)
                    add(day_no, clock, bump["length"], bump["file"])
                    clock += bump["length"]
                else:
                    clock += fill_break(lines, add, day_no, clock, gap, breaks, rng)
                if increment:                      # start the next one on the slot
                    clock = ((clock + increment - 1) // increment) * increment
                if clock >= DAY_SECONDS:
                    break
    return lines


def fill_break(lines, add, day, clock, gap, breaks, rng):
    """Longest clip that fits, again and again, until the gap is used up."""
    if gap <= 0 or not breaks:
        return 0
    used = 0
    usable = [b for b in breaks if b["length"] > 2]
    if not usable:
        return 0
    shortest = min(b["length"] for b in usable)
    last = None
    while gap - used >= shortest:
        fits = [b for b in usable if b["length"] <= gap - used]
        # any clip that fits, not only the longest: with 48 shorts in the pool
        # the old rule played the same two all week. Never the same clip twice
        # running, if there is another one.
        choose = [b for b in fits if b["file"] != last] or fits
        pickb = choose[rng.randrange(len(choose))]
        add(day, clock + used, pickb["length"], pickb["file"])
        used += pickb["length"]
        last = pickb["file"]
    return used


def wii_path(rel):
    """A path inside the video folder, as the Wii sees it."""
    rel = rel.replace("\\", "/")
    return rel if rel.startswith("sd1:/") else "sd1:/videos/" + rel.lstrip("/")
