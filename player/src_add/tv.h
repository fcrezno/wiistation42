/****************************************************************************
 * WiiStation 42 - a television channel for WiiMC
 *
 * The channel plays to a schedule, and it uses the clock of the Wii. When you
 * start it, the show that should be on air is already running, at the correct
 * second, like a real television station.
 ***************************************************************************/

#ifndef _TV_H_
#define _TV_H_

// Reads a channel file. Returns the number of programs, or 0.
int TVLoad(const char *path);

// True when a channel file is loaded.
bool TVActive();

// The program for this minute. offset = seconds into that program.
// If nothing is on air, it gives the next program with offset 0.
bool TVCurrent(char *file, int len, int *offset);

// The program that follows the one on air now. offset is always 0.
bool TVNextProgram(char *file, int len, int *offset);

// Name of the channel, from the "name" line of the channel file.
const char *TVName();

// Opens every channel file in a folder (channel1.txt, channel2.txt, ...).
int TVLoadChannels(const char *dir);

// How many channels, and which one is showing (0 based).
int TVChannelCount();
int TVChannel();

// Moves one channel up (+1) or down (-1). True when the channel changed.
bool TVChannelStep(int step);

// The guide (channel0.txt) as a channel index, or -1 when there is none.
int TVGuideChannel();

// Goes straight to one channel. False when it is already on.
bool TVChannelTo(int index);

// True when the card has selftest.txt: a test run changes channel by itself.
bool TVSelfTest();

// True when selftest.txt says "menu": a test run works the station menu.
bool TVSelfTestMenu();

// Adds one line to tv.log (a test run only).
void TVLog(const char *text);

// Milliseconds since the player was last given a file.
int TVMsSinceNewFile();

// True when a break clip is on air (a file from the _breaks folder).
bool TVInBreak();

// Asks for the next real programme, so the break is skipped. The channel
// hands it over the next time the player wants a file.
bool TVSkipBreak();

#endif
