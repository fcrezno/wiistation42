"""WiiStation 42 planner - a local app to organise episodes and build the schedule.

  py -3 server.py            then open http://localhost:4242
  py -3 server.py --open     also opens your browser

It reads your video folders (the length of every file comes from ffprobe, and is
cached), lets you build the week, and writes the channel files that the Wii reads.

Nothing leaves the PC: the server listens on localhost only.
"""
import glob
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "lengths.json")
PROJECT = os.path.join(HERE, "week.json")
STATIONS = os.path.join(os.path.dirname(HERE), "stations")
FFPROBE = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffprobe.exe")

LIBRARY_ROOTS = os.environ.get("WS42_VIDEOS", "videos").split(os.pathsep)   # your video folders
WII_ROOT = "sd1:/videos"
PORT = 4242

lengths = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}


def probe_length(path):
    if path in lengths:
        return lengths[path]
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        lengths[path] = int(float(json.loads(r.stdout)["format"]["duration"]))
    except Exception:
        lengths[path] = 0
    return lengths[path]


def scan():
    """[{show, items:[{name, file (as the Wii sees it), length}]}] sorted by show."""
    shows = {}
    for root in LIBRARY_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            vids = sorted(f for f in files if f.lower().endswith((".avi", ".mp4", ".mkv")))
            if not vids:
                continue
            rel = os.path.relpath(dirpath, root).replace("\\", "/")
            if rel == ".":
                continue
            show = rel.split("/")[0]
            group = shows.setdefault(show, {})
            for v in vids:
                wii = f"{WII_ROOT}/{rel}/{v}"
                if wii in group:
                    continue
                group[wii] = {"name": os.path.splitext(v)[0],
                              "file": wii,
                              "length": probe_length(os.path.join(dirpath, v))}
        break  # the first root that exists wins, so both cards give the same paths
    json.dump(lengths, open(CACHE, "w", encoding="utf-8"))
    return [{"show": s, "items": [group[k] for k in sorted(group)]} for s, group in sorted(shows.items())]


def split_breaks(shows):
    """A folder named _breaks holds the short clips between programmes."""
    breaks, rest = [], []
    for s in shows:
        name = s["show"].lower()
        if name in ("_breaks", "breaks", "commercials"):
            breaks = s["items"]
        elif name.startswith("_"):
            continue        # _guide and anything else that is not a show
        else:
            rest.append(s)
    return rest, breaks


def wii_card():
    """The Wii card, found by what is on it: apps, videos and wiistation42
    all together. The camera card has DCIM and none of these, so it can never
    be picked by mistake. (The old test ran fsutil, which needs administrator
    rights and quietly failed.)"""
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = letter + ":" + chr(92)
        if all(os.path.isdir(os.path.join(root, d))
               for d in ("apps", "videos", "wiistation42")):
            return root
    return None


def write_lines(lines, name):
    """Writes a channel file beside the planner and, if it is there, on the card."""
    text = "\n".join(lines) + "\n"
    card = wii_card()
    targets = [os.path.join(HERE, name)]
    if card:
        targets.append(os.path.join(card, "wiistation42", name))
    for target in targets:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, "w", encoding="utf-8", newline="\r\n").write(text)
    return targets, card


def channel_lines(week, name):
    """One line per programme: day, start with seconds, length, file."""
    lines = [f"name {name}",
             "# made by the WiiStation 42 planner",
             "# day start(hh:mm:ss) length(seconds) file   (day 0 = Sunday ... 6 = Saturday)"]
    for day, items in enumerate(week):
        clock = items[0].get("dayStart", 6 * 3600) if items else 6 * 3600
        for it in items:
            start = clock % 86400
            lines.append(f"{day} {start // 3600:02d}:{start % 3600 // 60:02d}:{start % 60:02d} "
                         f"{int(it['length'])} {it['file']}")
            clock += int(it["length"])
    return lines


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = open(os.path.join(HERE, "index.html"), "rb").read()
            return self.send(page, ctype="text/html; charset=utf-8")
        if self.path == "/api/library":
            shows, breaks = split_breaks(scan())
            return self.send({"shows": shows, "breaks": breaks, "card": wii_card()})
        if self.path == "/api/project":
            if os.path.exists(PROJECT):
                return self.send(json.load(open(PROJECT, encoding="utf-8")))
            return self.send({"week": [[] for _ in range(7)], "name": "WiiStation 42", "dayStart": 6 * 3600})
        return self.send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n) or b"{}")

        if self.path == "/api/project":
            json.dump(data, open(PROJECT, "w", encoding="utf-8"), indent=1)
            return self.send({"saved": PROJECT})

        if self.path == "/api/guide":
            import guide
            root = next((r for r in LIBRARY_ROOTS if os.path.isdir(r)), LIBRARY_ROOTS[0])
            lines = guide.make_guide(data["week"], data.get("dayStart", 6 * 3600),
                                     data.get("name", "WiiStation 42"), root)
            head = ["name Guide", "# the listings channel, made by the planner"]
            targets, card = write_lines(head + lines, "channel2.txt")
            return self.send({"lines": len(lines), "targets": targets, "card": card,
                              "videos": os.path.join(root, "_guide")})

        if self.path == "/api/stations":
            # the FieldStation42 model: one station file per channel, the PC
            # turns it into the flat channel file that the Wii reads
            import random
            import stations
            out = []
            for conf_path in sorted(glob.glob(os.path.join(STATIONS, "*.json"))):
                conf = json.load(open(conf_path, encoding="utf-8"))
                catalog = stations.Catalog(conf.get("content_dir", LIBRARY_ROOTS[0]), probe_length)
                seq = stations.Sequences(os.path.join(HERE, "sequences.json"))
                lines = stations.build(conf, catalog, seq, random.Random())
                seq.save()
                number = int(conf.get("channel_number", len(out) + 1))
                targets, card = write_lines(lines, f"channel{number}.txt")
                out.append({"station": os.path.basename(conf_path),
                            "name": conf.get("network_name"),
                            "channel": number,
                            "programmes": len(lines) - 3,
                            "targets": targets})
            return self.send({"built": out, "card": wii_card()})

        if self.path == "/api/write":
            lines = channel_lines(data["week"], data.get("name", "WiiStation 42"))
            targets, card = write_lines(lines, "channel1.txt")
            programmes = len(lines) - 3
            return self.send({"written": [{"path": t, "programmes": programmes} for t in targets],
                              "card": card})

        return self.send({"error": "not found"}, 404)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"WiiStation 42 planner: http://localhost:{PORT}   (Ctrl+C to stop)")
    card = wii_card()
    print("Wii card:", card if card else "not in the reader (you can still build the week)")
    if "--open" in sys.argv:   # only when you start it yourself
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
