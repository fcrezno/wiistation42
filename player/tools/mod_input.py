"""Better seeking for WiiMC: py3 tools/mod_input.py src/source/input.cpp

D-pad Left/Right: a tap skips as before; HOLDING repeats the skip, so it scans.
C-stick (GameCube) Left/Right: a smooth scan. The further the stick is pushed,
the larger each step, from 1 second to 30 seconds, 5 steps a second. It seeks to
an absolute position, so it never runs past the end of the file.

The file uses CRLF, so every edit keeps the line ending of the file. Each edit is
checked, and the script stops if the upstream code has changed.
"""
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in text else "\n"


def edit(old, new, why):
    global text
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    if new in text:
        print("already there:", why)
        return
    if old not in text:
        sys.exit("FAILED, upstream code changed: " + why)
    text = text.replace(old, new, 1)
    print("ok:", why)


edit("#define RESIZE_DELAY\t\t\t5000",
     "#define RESIZE_DELAY\t\t\t5000\n"
     "#define SCAN_DELAY\t\t\t\t250000\t// hold the d-pad: 4 skips a second\n"
     "#define SCAN_TICK\t\t\t\t200000\t// c-stick: 5 steps a second\n"
     "#define SCAN_DEAD\t\t\t\t20\t\t// c-stick dead zone\n"
     "#define SCAN_STEP_MAX\t\t\t30\t\t// seconds per step at full push",
     "add the scan timings")

edit("static int resizeprev = 0, resizeinitial = 0;",
     "static int resizeprev = 0, resizeinitial = 0;\nstatic u64 scanprev = 0;",
     "add scanprev")

# the pad data already has substickX, but nothing filled it in
edit("\t\tuserInput[i].pad.stickY = PAD_StickY(i);",
     "\t\tuserInput[i].pad.stickY = PAD_StickY(i);\n"
     "\t\tuserInput[i].pad.substickX = PAD_SubStickX(i);\n"
     "\t\tuserInput[i].pad.substickY = PAD_SubStickY(i);",
     "read the c-stick")

edit("\tu16 down = PAD_ButtonsDown(cur_chan);\n\tu16 held = PAD_ButtonsHeld(cur_chan);",
     "\tu16 down = PAD_ButtonsDown(cur_chan);\n\tu16 held = PAD_ButtonsHeld(cur_chan);\n"
     "\ts8 cstick = PAD_SubStickX(cur_chan);",
     "read the c-stick position")

edit("""\t\telse if(userInput[0].wpad->btns_d & WPAD_BUTTON_RIGHT || down & PAD_BUTTON_RIGHT ||
\t\tuserInput[0].cpad.data.down & CTR_BUTTON_RIGHT)
\t\t{
\t\t\twiiFastForward();
\t\t}
\t\telse if(userInput[0].wpad->btns_d & WPAD_BUTTON_LEFT || down & PAD_BUTTON_LEFT ||
\t\t\tuserInput[0].cpad.data.down & CTR_BUTTON_LEFT)
\t\t{
\t\t\twiiRewind();
\t\t}""",
     """\t\telse if(cstick > SCAN_DEAD || cstick < -SCAN_DEAD)
\t\t{
\t\t\t/* C-stick: a smooth scan. The further the stick goes, the bigger
\t\t\t   each step, and the steps come 5 times a second. The position is
\t\t\t   absolute, so it stops at the start and at the end of the file. */
\t\t\tu64 scannow = gettime();
\t\t\tif(diff_usec(scanprev, scannow) > SCAN_TICK)
\t\t\t{
\t\t\t\tscanprev = scannow;
\t\t\t\tint push = (cstick > 0 ? cstick : -cstick) - SCAN_DEAD;
\t\t\t\tint step = 1 + (push * (SCAN_STEP_MAX - 1)) / 50;
\t\t\t\tif(step > SCAN_STEP_MAX) step = SCAN_STEP_MAX;
\t\t\t\tdouble pos = wiiGetTimePos();
\t\t\t\tdouble len = wiiGetTimeLength();
\t\t\t\tif(pos >= 0)
\t\t\t\t{
\t\t\t\t\tdouble target = pos + (cstick > 0 ? step : -step);
\t\t\t\t\tif(target < 0) target = 0;
\t\t\t\t\tif(len > 1 && target > len - 1) target = len - 1;
\t\t\t\t\twiiSeekPos((int)target);
\t\t\t\t}
\t\t\t}
\t\t}
\t\telse if(userInput[0].wpad->btns_h & WPAD_BUTTON_RIGHT || held & PAD_BUTTON_RIGHT ||
\t\tuserInput[0].cpad.data.down & CTR_BUTTON_RIGHT)
\t\t{
\t\t\t/* A tap does one skip. Holding it repeats the skip, so it scans. */
\t\t\tu64 scannow = gettime();
\t\t\tif(userInput[0].wpad->btns_d & WPAD_BUTTON_RIGHT || down & PAD_BUTTON_RIGHT ||
\t\t\t\tuserInput[0].cpad.data.down & CTR_BUTTON_RIGHT ||
\t\t\t\tdiff_usec(scanprev, scannow) > SCAN_DELAY)
\t\t\t{
\t\t\t\tscanprev = scannow;
\t\t\t\twiiFastForward();
\t\t\t}
\t\t}
\t\telse if(userInput[0].wpad->btns_h & WPAD_BUTTON_LEFT || held & PAD_BUTTON_LEFT ||
\t\t\tuserInput[0].cpad.data.down & CTR_BUTTON_LEFT)
\t\t{
\t\t\tu64 scannow = gettime();
\t\t\tif(userInput[0].wpad->btns_d & WPAD_BUTTON_LEFT || down & PAD_BUTTON_LEFT ||
\t\t\t\tuserInput[0].cpad.data.down & CTR_BUTTON_LEFT ||
\t\t\t\tdiff_usec(scanprev, scannow) > SCAN_DELAY)
\t\t\t{
\t\t\t\tscanprev = scannow;
\t\t\t\twiiRewind();
\t\t\t}
\t\t}""",
     "c-stick scan plus hold to scan")

edit('#include "menu.h"', '#include "menu.h"\n#include "tv.h"', "include tv.h")

# L and R change the channel. The scan block exists by now, so this goes in
# front of it and the chain stays: channel, then c-stick, then d-pad.
# Z is also the key that resizes the picture, and that branch sits earlier in
# the chain, so the skip has to go in front of it. It only acts during a break.
edit("\t\telse if (userInput[0].wpad->btns_h & WPAD_BUTTON_B || held & PAD_TRIGGER_Z)",
     "\t\telse if((down & PAD_TRIGGER_Z) && TVInBreak())\t// Z: skip the break\n"
     "\t\t{\n"
     "\t\t\tif(TVSkipBreak())\n"
     "\t\t\t\twiiNextFile();\n"
     "\t\t}\n"
     "\t\telse if (userInput[0].wpad->btns_h & WPAD_BUTTON_B || held & PAD_TRIGGER_Z)",
     "Z skips the break")

edit("\t\telse if(cstick > SCAN_DEAD || cstick < -SCAN_DEAD)",
     "\t\telse if((down & (PAD_TRIGGER_L | PAD_TRIGGER_R)) &&\n"
     "\t\t\t(held & PAD_TRIGGER_L) && (held & PAD_TRIGGER_R))\n"
     "\t\t{\n"
     "\t\t\t/* L and R together: start this programme again from the beginning,\n"
     "\t\t\t   the way a cable box does. */\n"
     "\t\t\twiiSeekPos(0);\n"
     "\t\t}\n"
     "\t\tif(TVSelfTest())\t// a test run changes channel on its own\n"
     "\t\t{\n"
     "\t\t\tstatic u64 tvtest = 0;\n"
     "\t\t\tif(tvtest == 0)\n"
     "\t\t\t\ttvtest = gettime();\n"
     "\t\t\telse if(diff_msec(tvtest, gettime()) > 12000)\n"
     "\t\t\t{\n"
     "\t\t\t\ttvtest = gettime();\n"
     "\t\t\t\tif(TVChannelStep(1))\n"
     "\t\t\t\t\twiiNextFile();\n"
     "\t\t\t}\n"
     "\t\t}\n"
     "\t\telse if(down & PAD_TRIGGER_R)\t// WiiStation 42: one channel up\n"
     "\t\t{\n"
     "\t\t\tif(TVChannelStep(1))\n"
     "\t\t\t\twiiNextFile();\n"
     "\t\t}\n"
     "\t\telse if(down & PAD_TRIGGER_L)\t// one channel down\n"
     "\t\t{\n"
     "\t\t\tif(TVChannelStep(-1))\n"
     "\t\t\t\twiiNextFile();\n"
     "\t\t}\n"
     "\t\telse if(cstick > SCAN_DEAD || cstick < -SCAN_DEAD)",
     "L and R change the channel")

# devkitPPC builds C++ as C++14, where <iterator> brings in std::prev. This file
# says "using namespace std", so its own static u64 prev[4] became ambiguous.
n = text.count("prev[")
text = text.replace("prev[", "rumbleprev[").replace("scanrumbleprev", "scanprev")
text = text.replace("rumblerumbleprev", "rumbleprev")
print("ok: renamed", n, "uses of prev[] to rumbleprev[]")

# The channel overlay (tvosd.cpp) is drawn by the same path as the seek bar.
# That path only runs while drawGui is set, so the overlay keeps it set until
# it has faded, and it is told whether the viewer asked for the bar as well.
edit('#include "tv.h"', '#include "tv.h"\n#include "tvosd.h"', "include tvosd.h")
edit("\tif(ir || BufferingStatusSet() || osdLevel)\n\t{\n\t\tdrawGui = true;",
     "\tTVOsdSetBarWanted(ir || BufferingStatusSet() || osdLevel);\t// WiiStation 42\n"
     "\tif(ir || BufferingStatusSet() || osdLevel || TVOsdActive())\n\t{\n\t\tdrawGui = true;",
     "keep drawing while the channel overlay is up")

# START opens the station menu (tvosd.cpp) instead of going straight to the
# WiiMC menu. While the menu is open it has every button, so nothing else acts.
# ExitRequested (the power button) always gets through.
edit("\tif(userInput[0].wpad->btns_d & WPAD_BUTTON_1 || down & PAD_BUTTON_B || userInput[0].cpad.data.down & CTR_BUTTON_B) {\n"
     "\t\tosdLevel ^= 1;",
     "\t// WiiStation 42: the station menu\n"
     "\t// \"Media menu\": a request to go to the WiiMC menu is lost when it comes\n"
     "\t// near the start or the end of a file. So it goes out 3 seconds into a\n"
     "\t// file, and again every 4 seconds until the WiiMC menu has opened.\n"
     "\tstatic bool tvMediaWanted = false;\n"
     "\tstatic int tvMediaMark = 0;\n"
     "\tstatic u64 tvMediaAt = 0;\n"
     "\tif(tvMediaWanted && TVGuiEntries() != tvMediaMark)\n"
     "\t\ttvMediaWanted = false;\t// it opened\n"
     "\tif(tvMediaWanted && !ExitRequested && TVMsSinceNewFile() > 3000 &&\n"
     "\t\t(tvMediaAt == 0 || diff_msec(tvMediaAt, gettime()) > 4000))\n"
     "\t{\n"
     "\t\ttvMediaAt = gettime();\n"
     "\t\tif(TVSelfTestMenu())\n"
     "\t\t\tTVLog(\"media menu asked for\");\n"
     "\t\tif(wiiIsPaused())\n"
     "\t\t\twiiPause();\n"
     "\t\twiiGotoGui();\n"
     "\t\treturn;\n"
     "\t}\n"
     "\tbool tvStart =(userInput[0].wpad->btns_d & WPAD_BUTTON_HOME) || (down & PAD_BUTTON_START) ||\n"
     "\t\t(userInput[0].cpad.data.down & CTR_BUTTON_START);\n"
     "\tbool tvBack = (userInput[0].wpad->btns_d & WPAD_BUTTON_B) || (down & PAD_BUTTON_B) ||\n"
     "\t\t(userInput[0].cpad.data.down & CTR_BUTTON_B);\n"
     "\tbool tvUp = (userInput[0].wpad->btns_d & WPAD_BUTTON_UP) || (down & PAD_BUTTON_UP) ||\n"
     "\t\t(userInput[0].cpad.data.down & CTR_BUTTON_UP);\n"
     "\tbool tvDown = (userInput[0].wpad->btns_d & WPAD_BUTTON_DOWN) || (down & PAD_BUTTON_DOWN) ||\n"
     "\t\t(userInput[0].cpad.data.down & CTR_BUTTON_DOWN);\n"
     "\tbool tvChoose = (userInput[0].wpad->btns_d & WPAD_BUTTON_A) || (down & PAD_BUTTON_A) ||\n"
     "\t\t(userInput[0].cpad.data.down & CTR_BUTTON_A);\n"
     "\tTVMenuSelfTest(&tvStart, &tvBack, &tvUp, &tvDown, &tvChoose);\t// a test run presses them itself\n"
     "\tif(!ExitRequested && TVActive() && TVMenuKeys(tvStart, tvBack, tvUp, tvDown, tvChoose))\n"
     "\t{\n"
     "\t\tint tvChoice = TVMenuTakeChoice();\n"
     "\t\tif(tvChoice == TVMENU_GUIDE)\n"
     "\t\t{\n"
     "\t\t\tif(TVChannelTo(TVGuideChannel()))\n"
     "\t\t\t\twiiNextFile();\n"
     "\t\t}\n"
     "\t\telse if(tvChoice == TVMENU_MEDIA)\t// what START did before: the WiiMC menu\n"
     "\t\t{\n"
     "\t\t\ttvMediaWanted = true;\t// asked for above, when the file has settled\n"
     "\t\t\ttvMediaMark = TVGuiEntries();\n"
     "\t\t\ttvMediaAt = 0;\n"
     "\t\t}\n"
     "\t\telse if(tvChoice == TVMENU_EXIT)\t// close the app the way an autoboot exit does\n"
     "\t\t{\n"
     "\t\t\tVIDEO_SetBlack(TRUE);\n"
     "\t\t\tExitRequested = true;\n"
     "\t\t}\n"
     "\t\tTVOsdSetBarWanted(false);\n"
     "\t\tdrawGui = true;\t// the menu is drawn where the seek bar is\n"
     "\t\treturn;\n"
     "\t}\n\n"
     "\tif(userInput[0].wpad->btns_d & WPAD_BUTTON_1 || down & PAD_BUTTON_B || userInput[0].cpad.data.down & CTR_BUTTON_B) {\n"
     "\t\tosdLevel ^= 1;",
     "START opens the station menu")

open(path, "w", encoding="utf-8", newline="").write(text)
print("written:", path)
