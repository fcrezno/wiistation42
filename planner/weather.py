"""WeatherBox: the weather, the way cable did it.

  py -3 weather.py

Takes the forecast from the United States weather service (no key needed),
draws three pages, and makes one minute of video that the channel repeats all
day. Run it again whenever the card is in the machine and the pages are new.

The Wii cannot fetch anything itself, so the pictures are made here. Every page
carries the time it was made, so nobody is fooled by an old forecast.
"""
import glob
import json
import math
import os
import subprocess
import time
import urllib.request

from PIL import Image, ImageDraw

import pixelfont                     # crezno's bitmap font

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.path.join((glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin")) or [os.environ.get("WS42_FFMPEG_BIN", "")])[0], "ffmpeg.exe")
MUSIC = os.path.join(os.path.dirname(HERE), "art", "guide_music_loop.wav")
# the US weather service asks for a contact in the User-Agent: set WS42_CONTACT to your e-mail or site
AGENT = "WiiStation42/1.0 (%s)" % os.environ.get("WS42_CONTACT", "https://github.com/fcrezno/wiistation42")
PLACE = tuple(float(v) for v in os.environ.get("WS42_LATLON", "40.7808,-73.9772").split(","))   # default: Central Park, NY
STATION = os.environ.get("WS42_WEATHER_STATION", "KNYC")         # the observation station near PLACE
W, H, PAGE = 640, 480, 20          # three pages, twenty seconds each
FPS, BOB, BOB_SECONDS = 12, 6, 2.4  # the sprites bob 6 px, once every 2.4 s
BG, HEAD, TEXT, GOLD, DIM = (16, 24, 56), (30, 60, 120), (235, 240, 250), (255, 200, 80), (141, 151, 171)
BARS = [(192,192,192),(192,192,0),(0,192,192),(0,192,0),(192,0,192),(192,0,0),(0,0,192)]
ICONS = os.path.join(os.path.dirname(HERE), "art", "weather")   # crezno's drawings
WORDMARK = os.path.join(os.path.dirname(HERE), "art", "wordmark.png")


def icon_for(text, day=True):
    """Which drawing fits what the weather service says."""
    t = (text or "").lower()
    if any(w in t for w in ("thunder", "tstorm", "storm")):
        return "storm"
    if any(w in t for w in ("snow", "sleet", "ice", "flurr", "wintry")):
        return "snow"
    if any(w in t for w in ("rain", "shower", "drizzle")):
        return "rain"
    if any(w in t for w in ("fog", "haze", "mist", "smoke")):
        return "fog"
    if any(w in t for w in ("wind", "breezy", "blustery")):
        return "wind"
    if any(w in t for w in ("partly", "mostly sunny", "mostly clear", "few clouds", "partly sunny")):
        return "partly cloudy" if day else "moon"   # the sun has no business at night
    if any(w in t for w in ("cloud", "overcast")):
        return "cloud"
    if any(w in t for w in ("clear", "sunny", "fair")):
        return "sun" if day else "moon"
    return "cloud"


def paste_icon(im, name, box, size):
    """Draws one icon. They are line drawings, so they are kept large: thin
    strokes disappear on an interlaced television."""
    path = os.path.join(ICONS, name + ".png")
    if not os.path.isfile(path):
        return
    art = Image.open(path).convert("RGBA")
    art = art.resize((size, size), Image.LANCZOS)
    im.paste(art, box, art)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    point = get(f"https://api.weather.gov/points/{PLACE[0]},{PLACE[1]}")["properties"]
    city = point["relativeLocation"]["properties"]
    periods = get(point["forecast"])["properties"]["periods"]
    try:
        now = get(f"https://api.weather.gov/stations/{STATION}/observations/latest")["properties"]
    except Exception:
        now = {}
    return {
        "place": f"{city['city']}, {city['state']}",
        "now": now,
        "periods": periods,
    }


def f_from_c(value):
    return None if value is None else round(value * 9 / 5 + 32)


def page(draw_body, subtitle):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for i, c in enumerate(BARS):                        # a strip of the test card
        d.rectangle([round(W * i / 7), 0, round(W * (i + 1) / 7) - 1, 6], fill=c)
    d.rectangle([0, 7, W, 74], fill=HEAD)
    pixelfont.draw(im, "WeatherBox", (30, 12), scale=2, colour=(255, 255, 255))
    pixelfont.draw(im, subtitle, (32, 50), scale=1, colour=(180, 200, 240))
    d.line([(0, 74), (W, 74)], fill=(90, 140, 220), width=2)
    draw_body(d, im)
    pixelfont.draw(im, "made " + time.strftime("%a %d %b, %H:%M"), (32, 446), scale=1, colour=DIM)
    return im


def page_now(data):
    p = data["now"]
    temp = f_from_c((p.get("temperature") or {}).get("value"))
    feels = f_from_c((p.get("windChill") or {}).get("value")) or \
            f_from_c((p.get("heatIndex") or {}).get("value"))
    hum = (p.get("relativeHumidity") or {}).get("value")
    wind = (p.get("windSpeed") or {}).get("value")

    def body(d, im):
        shown = f"{temp}" if temp is not None else "--"
        w = pixelfont.draw(im, shown, (38, 108), scale=5, colour=GOLD)
        pixelfont.draw(im, "F", (46 + w, 118), scale=2, colour=GOLD)
        pixelfont.draw(im, p.get("textDescription", "no reading"), (40, 244), scale=2, colour=TEXT)
        y = 312
        for label, value in (("wind", f"{round(wind * 0.621371)} mph" if wind else "calm"),
                             ("humidity", f"{round(hum)}%" if hum else "-"),
                             ("feels like", f"{feels} F" if feels else "-")):
            pixelfont.draw(im, label, (40, y), scale=1, colour=DIM)
            pixelfont.draw(im, value, (200, y), scale=1, colour=TEXT)
            y += 30
    im = page(body, data["place"] + " - conditions now")
    hour = int(time.strftime("%H"))
    name = icon_for(p.get("textDescription"), 6 <= hour < 19)
    return im, [(name, (386, 128), 208)]


def page_next(data, start, count, subtitle):
    periods = data["periods"][start:start + count]

    def body(d, im):
        y = 96
        for i, p in enumerate(periods):
            if i % 2:
                d.rectangle([0, y - 6, W, y + 62], fill=(22, 32, 70))
            pixelfont.draw(im, p["name"][:20], (124, y), scale=2, colour=GOLD)
            words, line = p["shortForecast"].split(), ""
            for w in words:                       # cut on a word, never mid-word
                if len(line) + len(w) + 1 > 32:
                    break
                line += (" " if line else "") + w
            pixelfont.draw(im, f"{p['temperature']}F   {line}", (124, y + 36), scale=1, colour=TEXT)
            y += 70
    im = page(body, subtitle)
    sprites, y = [], 96
    for p in periods:
        sprites.append((icon_for(p.get("shortForecast"), p.get("isDaytime", True)), (24, y - 8), 84))
        y += 70
    return im, sprites


def main():
    data = fetch()
    card = None
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = letter + ":" + chr(92)
        if all(os.path.isdir(os.path.join(root, d)) for d in ("apps", "videos", "wiistation42")):
            card = root
    if not card:
        raise SystemExit("the card is not in the reader")

    out_dir = os.path.join(card, "videos", "_weather")
    os.makedirs(out_dir, exist_ok=True)
    pages = [page_now(data),
             page_next(data, 0, 4, data["place"] + " - what is coming"),
             page_next(data, 4, 4, data["place"] + " - the days after")]

    avi = os.path.join(out_dir, "weather.avi")
    length = PAGE * len(pages)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-stream_loop", "-1", "-i", MUSIC, "-t", str(length),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "mpeg4", "-vtag", "XVID", "-q:v", "5", "-r", "24000/1001",
           "-af", "volume=1.2", "-c:a", "libmp3lame", "-b:a", "96k", "-ac", "2", "-ar", "48000", avi]
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    # The drawings bob gently, the way a weather map used to drift. The page
    # itself is drawn once; only the sprites move, so this stays quick.
    art = {}
    for page_im, sprites in pages:
        for name, xy, size in sprites:
            path = os.path.join(ICONS, name + ".png")
            if name not in art and os.path.isfile(path):
                art[name] = {}
            if name in art and size not in art[name]:
                art[name][size] = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)

    for index, (page_im, sprites) in enumerate(pages):
        base = page_im.convert("RGB")
        for frame in range(int(PAGE * FPS)):
            t = frame / FPS
            im = base.copy()
            for i, (name, (x, y), size) in enumerate(sprites):
                if name not in art:
                    continue
                # each sprite is a little out of step with the one above it
                lift = round(BOB * math.sin(2 * math.pi * (t / BOB_SECONDS) + i * 0.7))
                im.paste(art[name][size], (x, y + lift), art[name][size])
            pipe.stdin.write(im.tobytes())
    pipe.stdin.close()
    if pipe.wait() != 0:
        raise SystemExit("the weather video failed")

    lines = ["name WeatherBox", "# made by weather.py from the United States weather service"]
    for day in range(7):
        t = 0
        while t < 86400:
            lines.append(f"{day} {t//3600:02d}:{t%3600//60:02d}:{t%60:02d} {length} "
                         f"sd1:/videos/_weather/weather.avi")
            t += length
    text = "\n".join(lines) + "\n"
    for target in (os.path.join(HERE, "channel4.txt"),
                   os.path.join(card, "wiistation42", "channel4.txt")):
        open(target, "w", encoding="utf-8", newline="\r\n").write(text)
    temp = f_from_c((data["now"].get("temperature") or {}).get("value"))
    print(f"WeatherBox: {data['place']}, {temp}F {data['now'].get('textDescription','')}, "
          f"{os.path.getsize(avi)/1e6:.1f} MB, channel 4")


if __name__ == "__main__":
    main()
