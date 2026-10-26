"""WiiStation 42 hooks: py3 tools/mod_tv.py src

Adds a television channel mode to WiiMC. tv.cpp and tv.h hold the schedule
logic; this script connects them:

  wiimc.h     declares wiiSetStartTime
  mplayer.c   a file can start at a given second (the same path the resume
              feature uses, so it is a proven way to do it)
  wiimc.cpp   the argument tv=<channel file>, the start of the channel, and
              the next programme when one ends

Every edit is checked. If the upstream code has changed, the script stops
instead of writing something wrong.
"""
import os
import sys

root = sys.argv[1]


def patch(rel, edits):
    path = os.path.join(root, rel)
    # latin-1 maps every byte to itself: menu.cpp is not valid UTF-8 (it has a
    # Latin-1 byte 0xE7), and this way no byte of any file is ever changed.
    text = open(path, encoding="latin-1", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new, why in edits:
        o, n = old.replace("\n", nl), new.replace("\n", nl)
        if n in text:
            print("already there:", rel, "-", why)
            continue
        if o not in text:
            sys.exit("FAILED, upstream changed: " + rel + " - " + why)
        text = text.replace(o, n, 1)
        print("ok:", rel, "-", why)
    open(path, "w", encoding="latin-1", newline="").write(text)


patch("source/wiimc.h", [(
    "void wiiSeekPos(int sec);",
    "void wiiSeekPos(int sec);\nvoid wiiSetStartTime(int sec);\nvoid wiiNextFile(void);",
    "declare wiiSetStartTime and wiiNextFile")])

patch("source/mplayer/mplayer.c", [
    ("static double seek_to_sec;",
     "static double seek_to_sec;\nstatic double wii_start_sec = 0;\t// WiiStation 42: join a programme in progress",
     "add the start time"),
    ("void wiiSeekPos(int sec)\n{\n\twiiSeek(sec, 2);\n}",
     "void wiiSeekPos(int sec)\n{\n\twiiSeek(sec, 2);\n}\n\n"
     "void wiiSetStartTime(int sec)\n{\n\twii_start_sec = sec;\n}\n\n"
     "// End this file and ask the application what to play next. A channel\n"
     "// change uses this: the schedule then gives the programme of the new\n"
     "// channel, at the second it is at.\n"
     "void wiiNextFile(void)\n"
     "{\n"
     "\tif(!playing_file || controlledbygui == 2)\n"
     "\t\treturn;\n"
     "\tmp_cmd_t *cmd = (mp_cmd_t *)calloc(1, sizeof(*cmd));\n"
     "\tcmd->id = MP_CMD_PLAY_TREE_STEP;\n"
     "\tcmd->name = strdup(\"pt_step\");\n"
     "\tcmd->nargs = 2;\n"
     "\tcmd->args[0].v.i = 1;\n"
     "\tcmd->args[1].v.i = 1;\t// force: do not walk the play tree\n"
     "\tmp_input_queue_cmd(cmd);\n"
     "}",
     "add wiiSetStartTime and wiiNextFile"),
    ("\t\tseek_to_sec = load_restore_point(fileplaying, partitionlabelplaying) - 8;\n"
     "\t\tif(seek_to_sec < 0 || seek_to_sec+120 > demuxer_get_time_length(mpctx->demuxer))\n"
     "\t\t\tseek_to_sec = 0;",
     "\t\tseek_to_sec = load_restore_point(fileplaying, partitionlabelplaying) - 8;\n"
     "\t\tif(seek_to_sec < 0 || seek_to_sec+120 > demuxer_get_time_length(mpctx->demuxer))\n"
     "\t\t\tseek_to_sec = 0;\n\n"
     "\t\tif(wii_start_sec > 0)\t// WiiStation 42 asked for a start second\n"
     "\t\t{\n"
     "\t\t\tseek_to_sec = wii_start_sec;\n"
     "\t\t\twii_start_sec = 0;\n"
     "\t\t\tif(seek_to_sec + 5 > demuxer_get_time_length(mpctx->demuxer))\n"
     "\t\t\t\tseek_to_sec = 0;\n"
     "\t\t}",
     "use the start time when a file loads"),
])

patch("source/wiimc.cpp", [
    ('#include "wiimc.h"',
     '#include "wiimc.h"\n#include "tv.h"\n#include "tvosd.h"',
     "include tv.h and tvosd.h"),
    ("bool ExitRequested = false;",
     "bool ExitRequested = false;\nstatic char tvSchedule[512] = { 0 };\t// WiiStation 42 channel file\n"
     "static bool tvOff = false;\t// the argument notv keeps this a plain player",
     "add the channel file name"),
    ("\t\tfor(i=1; i<argc; ++i){\n\t\t\thandleConfigPair(argv[i]);\n\t\t}",
     "\t\tfor(i=1; i<argc; ++i){\n"
     "\t\t\tif(strncmp(argv[i], \"tv=\", 3) == 0)\t// WiiStation 42\n"
     "\t\t\t\tsnprintf(tvSchedule, sizeof(tvSchedule), \"%s\", argv[i]+3);\n"
     "\t\t\telse if(strcmp(argv[i], \"notv\") == 0)\t// a plain player, no station\n"
     "\t\t\t\ttvOff = true;\n"
     "\t\t\telse\n"
     "\t\t\t\thandleConfigPair(argv[i]);\n"
     "\t\t}",
     "read the tv= argument"),
    ("\t// create GUI thread\n \twhile(1)",
     "\t// WiiStation 42: the card is mounted now, so open the channel and join\n"
     "\t// the programme that should be on air at this minute.\n"
     "\t// tv= is either one channel file or a folder with channel1.txt, channel2.txt ...\n"
     "\t// WiiMC mounts the card as sd1:, NOT sd:, so the folder is looked for\n"
     "\t// on every device it can use. A channel on the Wii Menu cannot pass an\n"
     "\t// argument, so with no tv= the station still starts by itself.\n"
     "\tstatic const char * const tvRoots[] = {\n"
     "\t\t\"sd1:/wiistation42\", \"sd2:/wiistation42\",\n"
     "\t\t\"usb1:/wiistation42\", \"usb2:/wiistation42\", \"sd:/wiistation42\" };\n"
     "\tint tvFound = 0;\n"
     "\tif(!tvOff)\n"
     "\t{\n"
     "\t\tif(tvSchedule[0] != 0)\n"
     "\t\t\ttvFound = (TVLoadChannels(tvSchedule) > 0 || TVLoad(tvSchedule) > 0);\n"
     "\t\tfor(int r = 0; !tvFound && r < 5; r++)\n"
     "\t\t\tif(TVLoadChannels(tvRoots[r]) > 0)\n"
     "\t\t\t\ttvFound = 1;\n"
     "\t}\n\n"
     "\tif(tvFound)\n"
     "\t{\n"
     "\t\tint tvOffset = 0;\n"
     "\t\tif(TVCurrent(loadedFile, sizeof(loadedFile), &tvOffset))\n"
     "\t\t{\n"
     "\t\t\twiiSetStartTime(tvOffset);\n"
     "\t\t\tsnprintf(loadedFileDisplay, 127, \"%s\", TVName());\n"
     "\t\t\tTVOsdSetBooting(true);\t// black, not the WiiMC menu, until the opening plays\n"
     "\t\t}\n"
     "\t}\n\n"
     "\t// create GUI thread\n \twhile(1)",
     "start the channel"),
    ("\tif(controlledbygui == 0) // playing a video\n\t{\n\t\tif(!load)\n\t\t\treturn false;",
     "\tif(controlledbygui == 0) // playing a video\n\t{\n\t\tif(!load)\n\t\t\treturn false;\n\n"
     "\t\tif(TVActive())\t// WiiStation 42: the schedule says what comes next\n"
     "\t\t{\n"
     "\t\t\tint tvOffset = 0;\n"
     "\t\t\tif(!TVNextProgram(loadedFile, sizeof(loadedFile), &tvOffset))\n"
     "\t\t\t\treturn false;\n"
     "\t\t\twiiSetStartTime(tvOffset);\n"
     "\t\t\tchar *tvStart = strrchr(loadedFile, '/');\n"
     "\t\t\tsnprintf(loadedFileDisplay, 127, \"%s\", (tvStart && tvStart[1]) ? tvStart+1 : loadedFile);\n\n"
     "\t\t\t/* The player must be set up for the new file, exactly as the\n"
     "\t\t\t   normal path below does it. Without this the second programme\n"
     "\t\t\t   starts and then the player stops asking for anything. */\n"
     "\t\t\tchar tvExt[7];\n"
     "\t\t\tGetExt(loadedFile, tvExt);\n"
     "\t\t\tif(WiiSettings.skipLoop == 1 || strcasecmp(tvExt, \"dash\") == 0)\n"
     "\t\t\t\twiiDash();\n"
     "\t\t\telse\n"
     "\t\t\t\twiiElse();\n"
     "\t\t\tif(strcasecmp(tvExt, \"thp\") == 0)\n"
     "\t\t\t\twiiTHP();\n"
     "\t\t\tif(strcasecmp(tvExt, \"sfd\") == 0)\n"
     "\t\t\t{\n"
     "\t\t\t\tuse_lavf = 1;\n"
     "\t\t\t\twiiSFD();\n"
     "\t\t\t}\n"
     "\t\t\telse if(use_lavf == 1)\n"
     "\t\t\t{\n"
     "\t\t\t\tuse_lavf = 0;\n"
     "\t\t\t\twiiSFD();\n"
     "\t\t\t}\n"
     "\t\t\twiiSpecialLoops(WiiSettings.nativeLoops);\n\n"
     "\t\t\t/* Hand the file over, the way the tail of this function does.\n"
     "\t\t\t   Without it MPlayer waits for filename for ever: that is the\n"
     "\t\t\t   freeze after the first programme. */\n"
     "\t\t\twhile(WiiSettings.subtitleVisibility && !ParseDone())\n"
     "\t\t\t\tusleep(100);\n"
     "\t\t\twiiLoadFile(loadedFile, GetPartitionLabel(loadedFile));\n"
     "\t\t\tif(controlledbygui == 1)\n"
     "\t\t\t\tFindFile();\n"
     "\t\t\treturn true;\n"
     "\t\t}",
     "play the next programme of the schedule"),
])

# The channel overlay is drawn where WiiMC draws its seek bar over the video.
# While only the overlay is up, the seek bar is left out.
patch("source/menu.cpp", [
    ('#include "menu.h"',
     '#include "menu.h"\n#include "tv.h"\n#include "tvosd.h"',
     "include tv.h and tvosd.h"),
    # In the WiiMC menu, START closed the app. With the station on, START goes
    # back to the channel instead, the same as the menu's own Resume button.
    # The station menu has Exit for closing the app.
    ("static int guiHalt = 0;",
     "static int guiHalt = 0;\nstatic volatile bool tvResume = false;\t// WiiStation 42: START in the menu goes back to TV",
     "add the back-to-TV request"),
    ("\t\tif(userInput[0].wpad->btns_d & (WPAD_BUTTON_HOME | WPAD_CLASSIC_BUTTON_HOME) ||\n"
     "\t\t\t\tuserInput[0].pad.btns_d & PAD_BUTTON_START || userInput[0].cpad.data.down & CTR_BUTTON_START)\n"
     "\t\t\tExitRequested = true; // exit program\n",
     "\t\tif(userInput[0].wpad->btns_d & (WPAD_BUTTON_HOME | WPAD_CLASSIC_BUTTON_HOME) ||\n"
     "\t\t\t\tuserInput[0].pad.btns_d & PAD_BUTTON_START || userInput[0].cpad.data.down & CTR_BUTTON_START ||\n"
     "\t\t\t\tTVSelfTestStart())\t// a test run presses START here by itself\n"
     "\t\t{\n"
     "\t\t\tif(!TVActive() || !VideoImgVisible())\n"
     "\t\t\t\tExitRequested = true; // exit program\n"
     "\t\t\telse if(menuCurrent == MENU_BROWSE_VIDEOS || menuCurrent == MENU_BROWSE_MUSIC ||\n"
     "\t\t\t\tmenuCurrent == MENU_BROWSE_ONLINEMEDIA)\n"
     "\t\t\t\ttvResume = true;\t// WiiStation 42: back to the channel\n"
     "\t\t}\n",
     "START in the menu goes back to TV"),
    ("\t\tif(backBtn.GetState() == STATE_CLICKED)\n"
     "\t\t{\n"
     "\t\t\tbackBtn.ResetState();\n"
     "\t\t\tResumeMPlayerFile(); // go back to MPlayer\n\n"
     "\t\t\t// wait until MPlayer is ready to take control (or return control)\n",
     "\t\tif(backBtn.GetState() == STATE_CLICKED || (tvResume && VideoImgVisible()))\n"
     "\t\t{\n"
     "\t\t\ttvResume = false;\n"
     "\t\t\tbackBtn.ResetState();\n"
     "\t\t\tResumeMPlayerFile(); // go back to MPlayer\n\n"
     "\t\t\t// wait until MPlayer is ready to take control (or return control)\n",
     "resume the channel on START"),
    ('extern "C" void DoMPlayerGuiDraw()\n{\n\tif(menuMode != 1)\n\t\treturn;\n\n\tmainWindow->Draw();',
     'extern "C" void DoMPlayerGuiDraw()\n{\n\tif(menuMode != 1)\n\t\treturn;\n\n'
     '\tif(TVOsdAlone())\t// WiiStation 42: the channel overlay on its own\n'
     '\t{\n'
     '\t\tTVOsdDraw();\n'
     '\t\treturn;\n'
     '\t}\n\n'
     '\tmainWindow->Draw();\n'
     '\tTVOsdDraw();\t// and over the seek bar when both are up',
     "draw the channel overlay"),
    # The start: WiiMC draws its menu while the first file loads. Its own
    # VIDEO_SetBlack does not hide it everywhere (Dolphin shows the menu for
    # 2 seconds), so while the station starts the GUI thread draws black.
    ("\t\tUpdatePads();\n\t\tmainWindow->Draw();\n\n"
     "\t\tif (mainWindow->GetState() != STATE_DISABLED)\n\t\t\tmainWindow->DrawTooltip();\n\n"
     "\t\tif(userInput[0].wpad->ir.valid)\n",
     "\t\tUpdatePads();\n"
     "\t\tbool tvBoot = TVOsdBooting();\t// WiiStation 42 is starting: black, not the menu\n"
     "\t\tif(tvBoot)\n"
     "\t\t\tMenu_DrawRectangle(0,0,screenwidth,screenheight,(GXColor){0, 0, 0, 255},1);\n"
     "\t\telse\n"
     "\t\t\tmainWindow->Draw();\n\n"
     "\t\tif (!tvBoot && mainWindow->GetState() != STATE_DISABLED)\n\t\t\tmainWindow->DrawTooltip();\n\n"
     "\t\tif(!tvBoot && userInput[0].wpad->ir.valid)\n",
     "draw black while the station starts"),
    ("void WiiMenu()\n{\n\tstatic bool firstboot = true;\n",
     "void WiiMenu()\n{\n\tstatic bool firstboot = true;\n"
     "\tTVGuiEntered();\t// WiiStation 42: a lost \"Media menu\" request is sent again until this counts\n",
     "count each time the WiiMC menu opens"),
    ("\t\t\tLoadNewFile();\n\n\t\t\tSuspendParseThread();\n\t\t\tSuspendGui();\n\t\t}\n",
     "\t\t\tLoadNewFile();\n\n\t\t\tSuspendParseThread();\n\t\t\tSuspendGui();\n"
     "\t\t\tTVOsdSetBooting(false);\t// the video has the screen now\n\t\t}\n",
     "stop drawing black once the video plays"),
])

# crezno's font in WiiMC's menus. The workflow puts fonts/font.ttf (made from crezno's
# bitmap strip by tools/make_font_ttf.py) in place of source/fonts/font.ttf.
# Its em is the 24 pixel cell, so every size is drawn at 24: one font pixel is
# one screen pixel, and all the menu text is the same size (crezno: "uniform").
# Hinting is off because the outlines already sit on the pixel grid; without
# NO_HINTING FreeType would run its auto-hinter on a font with no instructions.
patch("source/utils/FreeTypeGX.cpp", [
    ("void ChangeFontSize(FT_UInt pixelSize)\n{\n\tFT_Set_Pixel_Sizes(ftFace, 0, pixelSize);\n}",
     "void ChangeFontSize(FT_UInt pixelSize)\n{\n"
     "\t// WiiStation 42: crezno's pixel font has one true size, the 24 pixel cell\n"
     "\t(void)pixelSize;\n"
     "\tFT_Set_Pixel_Sizes(ftFace, 0, 24);\n}",
     "draw every size at the font's own 24 pixels"),
    ("FT_LOAD_DEFAULT | FT_LOAD_RENDER",
     "FT_LOAD_NO_HINTING | FT_LOAD_RENDER",
     "no hinting: the outlines sit on the pixel grid already"),
])

print("WiiStation 42 hooks done")
