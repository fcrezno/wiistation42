# WiiStation 42

**Your own TV station on a Wii.** WiiStation 42 is a modified build of
**[WiiMC](https://github.com/dborth/wiimc)**, the Wii media player. It plays your videos
to a weekly schedule on the Wii's own clock. When you turn it on, the programme that should be
on air is already playing, at the correct second. Then it goes on to the next one by itself, with
station breaks, "up next" bumpers, a TV guide channel, a weather channel and a controls channel.
Press L / R to change channels, as on a cable box.

Made by **crezno** for a softmodded Wii on a CRT. It needs no internet on the Wii.

## Built on WiiMC

WiiStation 42 is **WiiMC with changes**. All the hard work (playing the videos, the menus, the file
browser, the drivers) is WiiMC's:

- **[WiiMC](https://github.com/dborth/wiimc)** by **dborth (Tantric)** and contributors, GPL-3.0.
  The build uses this repository at a fixed commit, which already has the WiiMC-SS changes.
- **[WiiMC-SS](https://github.com/SuperrSonic/WiiMC-SSLC)** by **SuperrSonic**: GameCube controller support and other improvements.
- **[FieldStation42](https://github.com/shane-mason/FieldStation42)** by shane-mason (MPL-2.0) gave
  the idea of the station model: the PC decides what plays and when, and the player only plays it.
  No FieldStation42 code is in this repo.

Because WiiMC is GPL-3.0, **WiiStation 42 is GPL-3.0 too** (see `LICENSE`).

## What is in this repo

| folder | what it is |
|---|---|
| `player/` | our changes to WiiMC: `src_add/` (new files: `tv.cpp` the schedule, `tvosd.cpp` the on-screen channel number, info bar, static and START menu) and `tools/` (scripts that edit WiiMC's source at build time) |
| `.github/workflows/build.yml` | builds WiiMC with our changes on GitHub Actions and gives you `wiimc.dol` |
| `planner/` | the PC side: a small local web app to build the week, and the tools that make the guide, weather, idents, "up next" bumpers, opening and controls videos |
| `stations/example.json` | an example station file |
| `apps/wiistation42/` | the Homebrew Channel folder (`meta.xml` starts WiiMC in TV mode) |
| `art/` | crezno's art: wordmark, pixel font, weather drawings, banner and icons, the station chime and menu music |

No videos are in this repo. You use your own.

## Build the player

1. Fork this repo.
2. On GitHub: **Actions → Build WiiStation 42 (WiiMC) → Run workflow**.
3. Download the artifact **wiistation42-dol** and rename `wiimc.dol` to `boot.dol`.

The workflow clones WiiMC, copies `player/src_add`, the art and the font into it, runs
`player/tools/mod_input.py` and `player/tools/mod_tv.py`, and builds in the libogc2 container.

## Put it on the SD card

```
sd:/apps/wiistation42/boot.dol      the build from above
sd:/apps/wiistation42/meta.xml      from this repo (argument tv=sd:/wiistation42)
sd:/apps/wiistation42/icon.png
sd:/wiistation42/channel1.txt ...   the channel files from the planner
sd:/videos/...                      your videos, as the channel files name them
```

Videos: WiiMC plays AVI/MP4 and more. For a smooth picture on a CRT, convert them to 640x480 or
smaller. Use an even frame rate and key frames every 2 seconds, so channel changes are quick.

## Make the schedule (on the PC)

You need Windows, Python 3 with Pillow (`pip install pillow`), and FFmpeg (WinGet `Gyan.FFmpeg`, or
set `WS42_FFMPEG_BIN` to the folder with `ffmpeg.exe` and `ffprobe.exe`).

```
set WS42_VIDEOS=D:\my videos
py -3 planner\server.py --open
```

The planner opens at `http://localhost:4242` (it listens on your PC only). It reads your video
folders, gets the length of each file, and you build the week. It writes `channelN.txt` files for
the Wii. One folder = one show (the folder name is the "tag" in a station file).

A channel file is plain text, one line per programme:

```
name My Station
# day start(hh:mm:ss) length(seconds) file   (day 0 = Sunday ... 6 = Saturday)
0 06:00:00 1440 sd:/videos/Cartoon A/Cartoon A 01.avi
```

The other tools in `planner/`:

| tool | makes |
|---|---|
| `stations.py` | channel files from a station file (`stations/example.json`): time slots, breaks, sign-off |
| `make_schedule.py` | a quick channel file: all shows in a rotation, one after the other |
| `guide_grid.py`, `guide.py` | the TV guide channel (a listings grid, one page per half hour) |
| `weather.py` | the weather channel from the US National Weather Service (no key). Set `WS42_LATLON=40.78,-73.97`, `WS42_WEATHER_STATION=KNYC` and `WS42_CONTACT=` your e-mail (the weather service asks for it) |
| `make_idents.py`, `make_upnext.py`, `make_open.py`, `make_controls.py` | station idents, "up next" bumpers, the opening, the controls card |
| `finish.py` | writes all channel files in one go |

## Controls (GameCube controller)

| button | does |
|---|---|
| L / R | channel down / up |
| L + R | start this programme again |
| D-pad left / right | tap = skip, hold = scan |
| C-stick left / right | smooth scan; push = speed |
| Z | skip the break |
| A / B | pause / show the bar |
| X / Y | volume down / up |
| START | the WiiStation 42 menu (back to TV, guide, media menu, exit) |

## A Wii Menu channel

To start WiiStation 42 from the Wii Menu, see the separate channel maker:
**[fcrezno/wiistation42-channels](https://github.com/fcrezno/wiistation42-channels)**. Its
`banner_from` option keeps the WiiStation 42 banner.

## Licence

GPL-3.0, the same as WiiMC (see `LICENSE`). The art in `art/`, `player/images` and `player/fonts`
is crezno's and is shared with the code under the same terms. Wii is a trademark of Nintendo. This
project has no connection to Nintendo.
