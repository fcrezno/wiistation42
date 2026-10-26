/****************************************************************************
 * WiiStation 42 - a television channel for WiiMC
 *
 * Channel file (plain text, one program per line):
 *
 *   name My Channel
 *   # day  start  length  file
 *   *     06:00   1500    sd:/videos/Golden Boy/Golden Boy 01.avi
 *   1     20:00   1447    sd:/videos/Cowboy Bebop/Cowboy Bebop 01.avi
 *
 *   day    0 = Sunday ... 6 = Saturday, or * for every day
 *   start  hour and minute on the clock of the Wii
 *   length seconds
 *   file   the rest of the line, so spaces are allowed
 *
 * Lines that start with # and empty lines are ignored.
 ***************************************************************************/

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <gccore.h>
#include <dirent.h>
#include <ogc/lwp_watchdog.h>

#include "tv.h"
#include "tvosd.h"

typedef struct
{
	signed char day;	// 0-6, or -1 for every day
	int start;			// seconds after midnight
	int length;			// seconds
	char *file;
} TVPROGRAM;

// A week with breaks between the programmes can be a few thousand lines, so the
// list grows as the file is read instead of using a fixed size.
static TVPROGRAM *programs = NULL;
static int count = 0;
static int capacity = 0;
static char channelName[64] = "WiiStation 42";

#define TV_CHANNELS_MAX 32
static char channelFile[TV_CHANNELS_MAX][512];
static int channelCount = 0;
static int channelNow = 0;
static int channelWanted = -1;	// a button asked for this channel, not loaded yet
static volatile bool skipWanted = false;	// the Z button asked to skip the break
static volatile bool lastWasBreak = false;	// what is on air now, for the buttons
static void takeWantedSkip();	// defined below, used by TVNextProgram
static bool selfTest = false;	// selftest.txt on the card turns it on
static bool selfTestMenu = false;	// selftest.txt that says "menu"
static char tvLogPath[600] = { 0 };
static char tvDir[512] = { 0 };		// where the channel files were found
static bool openingDone = false;	// the opening plays once, at the start

// The card keeps writes in a cache until a file is closed, so every line is
// opened, written and closed. It is only for a test run, so the cost is fine.
static void tvSay(const char *fmt, ...)
{
	if(tvLogPath[0] == 0)
		return;
	FILE *f = fopen(tvLogPath, "a");
	if(!f)
		return;
	va_list ap;
	va_start(ap, fmt);
	vfprintf(f, fmt, ap);
	va_end(ap);
	fclose(f);
}	// a record of what the station did, for testing
static bool justSwitched = false;

// True when the card has a selftest.txt beside the channel files. A test run
// then changes channel by itself, so the crash that a button used to cause can
// be found without anybody pressing anything.
bool TVSelfTest()
{
	return selfTest;
}

bool TVSelfTestMenu()
{
	return selfTestMenu;
}

void TVLog(const char *text)
{
	tvSay("%s\n", text);
}

const char *TVName()
{
	return channelName;
}

bool TVActive()
{
	return count > 0;
}

static void trim(char *s)
{
	int n = strlen(s);
	while(n > 0 && (s[n-1] == '\r' || s[n-1] == '\n' || s[n-1] == ' ' || s[n-1] == '\t'))
		s[--n] = 0;
}

static bool addProgram(signed char day, int start, int length, const char *file)
{
	if(count == capacity)
	{
		int grow = capacity ? capacity * 2 : 256;
		TVPROGRAM *bigger = (TVPROGRAM *)realloc(programs, grow * sizeof(TVPROGRAM));
		if(!bigger)
			return false;
		programs = bigger;
		capacity = grow;
	}
	programs[count].file = strdup(file);
	if(!programs[count].file)
		return false;
	programs[count].day = day;
	programs[count].start = start;
	programs[count].length = length;
	count++;
	return true;
}

int TVLoad(const char *path)
{
	for(int i = 0; i < count; i++)
		free(programs[i].file);
	count = 0;

	FILE *f = fopen(path, "rb");
	if(!f)
		return 0;

	char line[700];
	while(fgets(line, sizeof(line), f))
	{
		trim(line);
		char *p = line;
		while(*p == ' ' || *p == '\t') p++;
		if(*p == 0 || *p == '#')
			continue;

		if(strncmp(p, "name ", 5) == 0)
		{
			snprintf(channelName, sizeof(channelName), "%s", p + 5);
			continue;
		}

		// day
		signed char day = -1;
		if(*p == '*')
			p++;
		else if(*p >= '0' && *p <= '6')
			day = (signed char)(*p++ - '0');
		else
			continue;
		while(*p == ' ' || *p == '\t') p++;

		// start, as hh:mm or hh:mm:ss (breaks are only seconds long)
		int hh = 0, mm = 0, ss = 0;
		int got = sscanf(p, "%d:%d:%d", &hh, &mm, &ss);
		if(got < 2 || hh < 0 || hh > 23 || mm < 0 || mm > 59 || ss < 0 || ss > 59)
			continue;
		while(*p && *p != ' ' && *p != '\t') p++;
		while(*p == ' ' || *p == '\t') p++;

		// length in seconds
		int length = atoi(p);
		if(length <= 0)
			continue;
		while(*p && *p != ' ' && *p != '\t') p++;
		while(*p == ' ' || *p == '\t') p++;

		if(*p == 0)
			continue;

		if(!addProgram(day, hh * 3600 + mm * 60 + ss, length, p))
			break;
	}
	fclose(f);
	return count;
}

// Every channel is a file in one folder. Only the channel you watch is held in
// memory; changing channel reads that file, which takes a moment on the card.
int TVLoadChannels(const char *dir)
{
	channelCount = 0;
	channelNow = 0;

	DIR *d = opendir(dir);
	if(!d)
		return 0;

	struct dirent *e;
	while(channelCount < TV_CHANNELS_MAX && (e = readdir(d)) != NULL)
	{
		const char *n = e->d_name;
		int len = strlen(n);
		if(len < 5 || strncasecmp(n, "channel", 7) != 0 || strcasecmp(n + len - 4, ".txt") != 0)
			continue;
		snprintf(channelFile[channelCount], sizeof(channelFile[0]), "%s/%s", dir, n);
		channelCount++;
	}
	closedir(d);

	// channel1, channel2, channel10 ... in the order of their names
	for(int i = 0; i < channelCount; i++)
		for(int j = i + 1; j < channelCount; j++)
			if(strcasecmp(channelFile[j], channelFile[i]) < 0)
			{
				char tmp[512];
				snprintf(tmp, sizeof(tmp), "%s", channelFile[i]);
				snprintf(channelFile[i], sizeof(channelFile[0]), "%s", channelFile[j]);
				snprintf(channelFile[j], sizeof(channelFile[0]), "%s", tmp);
			}

	// A record of what the station does, next to the channel files. It makes a
	// test run readable without watching the screen.
	if(channelCount > 0 && tvLogPath[0] == 0)
	{
		char logpath[600];
		snprintf(logpath, sizeof(logpath), "%s/selftest.txt", dir);
		FILE *st = fopen(logpath, "rb");
		if(st)
		{
			// "menu" in the file tests the station menu instead of the channels
			char what[64] = "";
			if(!fgets(what, sizeof(what), st))
				what[0] = 0;
			if(strstr(what, "menu"))
				selfTestMenu = true;
			else
				selfTest = true;
			fclose(st);
		}
		snprintf(tvLogPath, sizeof(tvLogPath), "%s/tv.log", dir);
		snprintf(tvDir, sizeof(tvDir), "%s", dir);
		TVOsdLoadFont(dir);	// crezno's font, for the channel overlay
		FILE *fresh = fopen(tvLogPath, "w");	// every run starts with an empty log
		if(fresh)
			fclose(fresh);
		tvSay("%d channels in %s\n", channelCount, dir);
		for(int i = 0; i < channelCount; i++)
			tvSay("  %s\n", channelFile[i]);
	}

	// Open on channel1, the first station, so the viewer arrives in the middle
	// of a programme instead of on the listings page.
	channelNow = 0;
	for(int i = 0; i < channelCount; i++)
	{
		const char *slash = strrchr(channelFile[i], '/');
		if(slash && strncasecmp(slash + 1, "channel1.", 9) == 0)
		{
			channelNow = i;
			break;
		}
	}
	if(channelCount > 0)
		TVLoad(channelFile[channelNow]);
	return channelCount;
}

int TVChannelCount()
{
	return channelCount;
}

int TVChannel()
{
	return channelNow;
}

// The buttons run on the thread that reads the pad. Reading a channel file
// there frees the list while the player is using it, and it reads the card
// while the player streams from it. That is how the Wii was made to crash.
// So a button only leaves a note; the player picks it up in TVNextProgram.
bool TVChannelStep(int step)
{
	if(channelCount < 2)
		return false;
	int from = (channelWanted >= 0) ? channelWanted : channelNow;
	channelWanted = (from + step + channelCount) % channelCount;
	return true;
}

// The channel whose file is channel0.txt, the listings, or -1.
int TVGuideChannel()
{
	for(int i = 0; i < channelCount; i++)
	{
		const char *slash = strrchr(channelFile[i], '/');
		if(slash && strncasecmp(slash + 1, "channel0.", 9) == 0)
			return i;
	}
	return -1;
}

// Go straight to one channel. The same rule as TVChannelStep: only a note.
// False when it is the channel already on, so the programme does not restart.
bool TVChannelTo(int index)
{
	if(index < 0 || index >= channelCount)
		return false;
	int from = (channelWanted >= 0) ? channelWanted : channelNow;
	if(index == from)
		return false;
	channelWanted = index;
	return true;
}

// Called on the player thread only.
static void takeWantedChannel()
{
	if(channelWanted < 0)
		return;
	int want = channelWanted;
	channelWanted = -1;
	if(want != channelNow && TVLoad(channelFile[want]) > 0)
	{
		channelNow = want;
		justSwitched = true;
	}
}

// The clock of the Wii, as day of the week and seconds after midnight.
static void clockNow(int *day, int *sec)
{
	time_t t = time(NULL);
	struct tm *lt = localtime(&t);
	if(!lt)
	{
		*day = 0;
		*sec = 0;
		return;
	}
	*day = lt->tm_wday;
	*sec = lt->tm_hour * 3600 + lt->tm_min * 60 + lt->tm_sec;
}

static bool onToday(const TVPROGRAM *p, int day)
{
	return p->day < 0 || p->day == day;
}

static int lastPlayed = -1;
static int pending = -1;	// set by TVSkipBreak, used by the next request

// A break clip lives in the _breaks folder, so the path says what it is.
static bool isBreak(int index)
{
	if(index < 0 || index >= count)
		return false;
	return strstr(programs[index].file, "/_breaks/") != NULL
		|| strstr(programs[index].file, "\\_breaks\\") != NULL;
}

bool TVInBreak()
{
	return lastWasBreak;	// read a flag, never the list: the pad thread asks this
}

// Which line is on air at this moment, or -1.
static int findNow(int day, int now)
{
	for(int i = 0; i < count; i++)
	{
		if(!onToday(&programs[i], day))
			continue;
		if(now >= programs[i].start && now < programs[i].start + programs[i].length)
			return i;
	}
	return -1;
}

// The line that starts next after this moment, or the first line of the list.
static int findNext(int day, int now)
{
	int best = -1;
	for(int i = 0; i < count; i++)
	{
		if(!onToday(&programs[i], day) || programs[i].start <= now)
			continue;
		if(best < 0 || programs[i].start < programs[best].start)
			best = i;
	}
	if(best < 0)
		for(int i = 0; i < count; i++)
			if(best < 0 || programs[i].start < programs[best].start)
				best = i;
	return best;
}

static bool give(int index, int now, char *file, int len, int *offset)
{
	if(index < 0)
		return false;
	int into = now - programs[index].start;
	if(into < 0 || into >= programs[index].length)
		into = 0;
	snprintf(file, len, "%s", programs[index].file);
	*offset = into;
	lastPlayed = index;
	lastWasBreak = isBreak(index);
	tvSay("%s +%ds  %s\n", channelName, into, programs[index].file);
	return true;
}

// When the player was last given a file. While MPlayer opens a file it
// handles queued commands another way, and a "go to the menu" is lost.
static volatile u64 handedAt = 0;

int TVMsSinceNewFile()
{
	u64 at = handedAt;
	return at == 0 ? 1000000 : (int)diff_msec(at, gettime());
}

bool TVCurrent(char *file, int len, int *offset)
{
	handedAt = gettime();
	if(count == 0)
		return false;

	// The opening (open.avi beside the channel files) plays once when the
	// station starts. After it the station joins whatever is on air then.
	if(!openingDone)
	{
		openingDone = true;
		char path[600];
		snprintf(path, sizeof(path), "%s/open.avi", tvDir);
		FILE *o = tvDir[0] ? fopen(path, "rb") : NULL;
		if(o)
		{
			fclose(o);
			snprintf(file, len, "%s", path);
			*offset = 0;
			lastWasBreak = false;
			justSwitched = true;	// so the next request joins the programme on air
			tvSay("opening  %s\n", path);
			return true;
		}
	}
	int day, now;
	clockNow(&day, &now);
	int i = findNow(day, now);
	return give(i >= 0 ? i : findNext(day, now), now, file, len, offset);
}

// When a programme ends, the channel asks the clock again. So it stays on the
// schedule even if a file was a little shorter or longer than its line says.
// The name a viewer should see: the file name without its folder or ending.
static void titleOf(int i, char *out, int size)
{
	const char *f = programs[i].file;
	const char *slash = strrchr(f, '/');
	snprintf(out, size, "%s", slash ? slash + 1 : f);
	char *dot = strrchr(out, '.');
	if(dot)
		*dot = 0;
}

static int nextShow(int from)
{
	for(int i = from + 1; i < count; i++)
		if(!isBreak(i))
			return i;
	return -1;
}

static void clockText(int sec, char *out, int size)
{
	sec %= 86400;
	snprintf(out, size, "%02d:%02d", sec / 3600, sec % 3600 / 60);
}

// Fills in the channel overlay for what is on air now.
static void announce()
{
	if(lastPlayed < 0 || lastPlayed >= count)
		return;

	char number[8] = "";
	const char *base = strrchr(channelFile[channelNow], '/');
	base = base ? base + 1 : channelFile[channelNow];
	int n = 0;
	for(const char *p = base; *p && n < 6; p++)
		if(*p >= '0' && *p <= '9')
			number[n++] = *p;
	number[n] = 0;

	int show = isBreak(lastPlayed) ? nextShow(lastPlayed) : lastPlayed;
	char name[160] = "", title[176] = "", when[32] = "", next[176] = "";
	if(show >= 0)
	{
		titleOf(show, name, sizeof(name));
		if(show != lastPlayed)
			snprintf(title, sizeof(title), "Coming up: %s", name);
		else
			snprintf(title, sizeof(title), "%s", name);
		char a[8], b[8];
		clockText(programs[show].start, a, sizeof(a));
		clockText(programs[show].start + programs[show].length, b, sizeof(b));
		snprintf(when, sizeof(when), "%s - %s", a, b);
		int after = nextShow(show);
		if(after >= 0)
		{
			char later[160];
			titleOf(after, later, sizeof(later));
			snprintf(next, sizeof(next), "Next: %s", later);
		}
	}
	TVOsdRequest(number, channelName, title, when, next);
	tvSay("overlay  %s %s | %s | %s\n", number, channelName, title, when);
}

bool TVNextProgram(char *file, int len, int *offset)
{
	handedAt = gettime();
	takeWantedChannel();	// a button may have asked for another channel
	takeWantedSkip();	// or to skip the break
	if(count == 0)
		return false;
	int day, now;
	clockNow(&day, &now);

	if(pending >= 0)	// the viewer skipped the break
	{
		int i = pending;
		pending = -1;
		snprintf(file, len, "%s", programs[i].file);
		*offset = 0;
		lastPlayed = i;
		return true;
	}

	if(justSwitched)	// a new channel: join whatever it is showing
	{
		justSwitched = false;
		lastPlayed = -1;
		bool ok = TVCurrent(file, len, offset);
		if(ok)
			announce();	// the overlay: which channel, what is on
		return ok;
	}

	int i = findNow(day, now);
	if(i >= 0 && i != lastPlayed)
		return give(i, now, file, len, offset);		// on the clock: join it

	// The same line is still on air. For a clip from _breaks that means a short
	// file is filling a long slot (the off air pattern, the sign off), so play
	// it again from the start. Never for a programme: an episode that started a
	// little early ends a little early, and it must not play twice.
	if(i >= 0 && i == lastPlayed && isBreak(i) && programs[i].start + programs[i].length - now > 5)
	{
		snprintf(file, len, "%s", programs[i].file);
		*offset = 0;
		return true;
	}

	if(lastPlayed >= 0 && lastPlayed + 1 < count)	// the file ended early
		return give(lastPlayed + 1, now, file, len, offset);

	return give(findNext(day, now), now, file, len, offset);
}

// Skip the break: remember the next line that is not a break clip. The channel
// gives it when the player asks for the next file, so it starts at once. The
// channel is then ahead of the clock and lines up again when that programme
// ends, the same as a recorder that skips the adverts.
// The pad thread only asks; the player thread finds the programme.
bool TVSkipBreak()
{
	if(count == 0 || !lastWasBreak)
		return false;
	skipWanted = true;
	return true;
}

// Called on the player thread only.
static void takeWantedSkip()
{
	if(!skipWanted)
		return;
	skipWanted = false;
	int day, now;
	clockNow(&day, &now);
	int from = lastPlayed >= 0 ? lastPlayed : findNow(day, now);
	if(from < 0)
		return;
	for(int i = from + 1; i < count; i++)
		if(!isBreak(i))
		{
			pending = i;
			return;
		}
}
