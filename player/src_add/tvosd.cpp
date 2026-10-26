/****************************************************************************
 * WiiStation 42 - the channel overlay
 *
 * Text is drawn in crezno's bitmap font, the same way the Clanker Arena game
 * draws it: a strip of 16x24 cells in ASCII order from 32, each glyph as wide
 * as its own ink, one pixel between glyphs, whole-number scales only.
 *
 * Threads: the player thread only fills in the request (strings and a count).
 * The drawing thread builds the textures and draws them, so a texture is
 * never freed while something else is drawing it.
 ***************************************************************************/

#include <gccore.h>
#include <malloc.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ogc/lwp_watchdog.h>

#include "video.h"
#include "libwiigui/gui.h"
#include "tv.h"
#include "tvosd.h"

enum { CELL_W = 16, CELL_H = 24, COLS = 16, FIRST = 32, GLYPHS = 96, TRACK = 1, SPACE_W = 4 };
#define TEXT_SCALE	2		// every word on screen is this size (crezno: "make the font uniform")
#define LINE_H		34		// one line of text at that size, ink with a small gap
#define OSD_MS		5000	// how long the overlay stays up
#define FADE_MS		600		// and how long it takes to go

typedef struct { int left, width; } GLYPH;
typedef struct { u8 *data; int w, h; } TEX;

static u8 *fontPng = NULL;			// the file, read before playback starts
static int fontPngSize = 0;
static GuiImageData *fontData = NULL;	// decoded on the drawing thread
static GLYPH glyphs[GLYPHS];

static char reqNumber[8], reqChannel[64], reqTitle[160], reqWhen[32], reqNext[160];
static volatile int wantGen = 0;	// raised by each request
static int builtGen = 0;
static volatile u64 shownAt = 0;
static volatile bool barWanted = false;
static volatile bool staticWanted = false;	// crezno: "a slight static when changing channels"

// prefixed: gui.h brings in std, and std::next would collide with a plain 'next'
static TEX osdNumber, osdLine1, osdWhen, osdTitle, osdNext;

void TVOsdLoadFont(const char *dir)
{
	char path[600];
	snprintf(path, sizeof(path), "%s/font.png", dir);
	FILE *f = fopen(path, "rb");
	if(!f)
		return;
	fseek(f, 0, SEEK_END);
	long n = ftell(f);
	fseek(f, 0, SEEK_SET);
	if(n > 0 && n < 1024 * 1024)
	{
		fontPng = (u8 *)malloc(n);
		if(fontPng && fread(fontPng, 1, n, f) == (size_t)n)
			fontPngSize = n;
	}
	fclose(f);
}

static void copyText(char *to, int size, const char *from)
{
	snprintf(to, size, "%s", from ? from : "");
}

void TVOsdRequest(const char *n, const char *channel, const char *t, const char *w, const char *nx)
{
	copyText(reqNumber, sizeof(reqNumber), n);
	copyText(reqChannel, sizeof(reqChannel), channel);
	copyText(reqTitle, sizeof(reqTitle), t);
	copyText(reqWhen, sizeof(reqWhen), w);
	copyText(reqNext, sizeof(reqNext), nx);
	shownAt = gettime();
	wantGen = wantGen + 1;
	staticWanted = true;	// a short burst of static, so the change is felt
}

// The station menu. The pad thread moves it; the drawing thread only reads it.
#define MENU_ITEMS	4
static const char *menuText[MENU_ITEMS] = { "Back to TV", "Guide", "Media menu", "Exit" };
static volatile bool menuOpen = false;
static volatile int menuSel = 0;
static volatile int menuChoice = TVMENU_NONE;

bool TVMenuKeys(bool start, bool back, bool up, bool down, bool choose)
{
	if(!menuOpen)
	{
		if(!start)
			return false;
		menuSel = 0;
		menuOpen = true;
		return true;
	}
	if(start || back)
		menuOpen = false;			// back to the channel
	else if(up)
		menuSel = (menuSel + MENU_ITEMS - 1) % MENU_ITEMS;
	else if(down)
		menuSel = (menuSel + 1) % MENU_ITEMS;
	else if(choose)
	{
		menuChoice = menuSel;
		menuOpen = false;
	}
	return true;
}

int TVMenuTakeChoice()
{
	int c = menuChoice;
	menuChoice = TVMENU_NONE;
	if(c != TVMENU_NONE && TVSelfTestMenu())
	{
		char line[48];
		snprintf(line, sizeof(line), "menu chose  %s", menuText[c]);
		TVLog(line);
	}
	return c;
}

// The test script, in milliseconds from the first pass: open the menu, go
// down to "Media menu" and choose it; START in the WiiMC menu (below) comes
// back; then the guide, "Back to TV", and last "Exit".
static const struct { u32 at; char key; } testScript[] = {
	{ 12000, 'S' }, { 14000, 'D' }, { 16000, 'D' }, { 18000, 'A' },
	{ 30000, 'S' }, { 32000, 'D' }, { 34000, 'A' },
	{ 42000, 'S' }, { 44000, 'A' },
	{ 50000, 'S' }, { 52000, 'U' }, { 54000, 'A' } };
#define TEST_WIIMC_START	24000
static volatile u64 testStart = 0;
static int testStep = 0;
static volatile bool testStartDone = false;

void TVMenuSelfTest(bool *start, bool *back, bool *up, bool *down, bool *choose)
{
	if(!TVSelfTestMenu())
		return;
	if(testStart == 0)
		testStart = gettime();
	if(testStep >= (int)(sizeof(testScript) / sizeof(testScript[0])) ||
		diff_msec(testStart, gettime()) < testScript[testStep].at)
		return;

	char key = testScript[testStep++].key;
	if(key == 'S') *start = true;
	if(key == 'B') *back = true;
	if(key == 'U') *up = true;
	if(key == 'D') *down = true;
	if(key == 'A') *choose = true;
	char line[32];
	snprintf(line, sizeof(line), "test key  %c", key);
	TVLog(line);
}

bool TVSelfTestStart()
{
	if(!TVSelfTestMenu() || testStartDone || testStart == 0 ||
		diff_msec(testStart, gettime()) < TEST_WIIMC_START)
		return false;
	testStartDone = true;
	TVLog("test key  START in the WiiMC menu");
	return true;
}

static volatile int guiEntries = 0;

void TVGuiEntered()
{
	guiEntries = guiEntries + 1;
	if(TVSelfTestMenu())
		TVLog("WiiMC menu opened");
}

int TVGuiEntries()
{
	return guiEntries;
}

static bool bannerUp()
{
	u64 at = shownAt;
	return at != 0 && diff_msec(at, gettime()) < OSD_MS;
}

static bool staticUp();

bool TVOsdActive()
{
	return menuOpen || bannerUp() || staticUp();
}

void TVOsdSetBarWanted(bool wanted)
{
	barWanted = wanted;
}

bool TVOsdAlone()
{
	return TVOsdActive() && !barWanted;
}

static volatile bool booting = false;
static volatile u64 bootAt = 0;
#define BOOT_MS		20000	// never hide the menu for longer than this

void TVOsdSetBooting(bool on)
{
	bootAt = gettime();
	booting = on;
}

bool TVOsdBooting()
{
	return booting && diff_msec(bootAt, gettime()) < BOOT_MS;
}

// GX keeps an RGBA8 texture in 4x4 tiles of 64 bytes: 32 bytes of alpha and
// red, then 32 bytes of green and blue.
static inline int tileAt(int w, int x, int y)
{
	return (((y >> 2) * (w >> 2) + (x >> 2)) << 6);
}

static inline u8 alphaAt(const u8 *tex, int w, int x, int y)
{
	return tex[tileAt(w, x, y) + ((((y & 3) << 2) | (x & 3)) << 1)];
}

static inline void putPixel(u8 *tex, int w, int x, int y, GXColor c, u8 a)
{
	int t = tileAt(w, x, y), i = (((y & 3) << 2) | (x & 3)) << 1;
	tex[t + i] = a;
	tex[t + i + 1] = c.r;
	tex[t + 32 + i] = c.g;
	tex[t + 32 + i + 1] = c.b;
}

// Each glyph is as wide as its own ink, the way the game measures it.
static void measure()
{
	const u8 *tex = fontData->GetImage();
	int w = fontData->GetWidth(), rows = fontData->GetHeight() / CELL_H;
	for(int i = 0; i < GLYPHS; i++)
	{
		glyphs[i].left = 0;
		glyphs[i].width = SPACE_W;
		if(i >= COLS * rows)
			continue;
		int sx = (i % COLS) * CELL_W, sy = (i / COLS) * CELL_H, lo = CELL_W, hi = -1;
		for(int y = 0; y < CELL_H; y++)
			for(int x = 0; x < CELL_W; x++)
				if(alphaAt(tex, w, sx + x, sy + y) > 80)
				{
					if(x < lo) lo = x;
					if(x > hi) hi = x;
				}
		if(hi >= 0)
		{
			glyphs[i].left = lo;
			glyphs[i].width = hi - lo + 1;
		}
	}
}

static int glyphFor(char ch)
{
	int code = (unsigned char)ch - FIRST;
	return (code < 0 || code >= GLYPHS) ? ('?' - FIRST) : code;
}

static void freeTex(TEX *t)
{
	if(t->data)
		free(t->data);
	t->data = NULL;
	t->w = t->h = 0;
}

static TEX makeText(const char *s, int scale, GXColor c)
{
	TEX t = { NULL, 0, 0 };
	if(!s || !s[0])
		return t;
	int pen = 0;
	for(const char *p = s; *p; p++)
		pen += glyphs[glyphFor(*p)].width + TRACK;
	pen -= TRACK;
	if(pen < 1)
		pen = 1;

	t.w = ((pen * scale) + 3) & ~3;			// GX wants multiples of 4
	t.h = ((CELL_H * scale) + 3) & ~3;
	t.data = (u8 *)memalign(32, t.w * t.h * 4);
	if(!t.data)
	{
		t.w = t.h = 0;
		return t;
	}
	memset(t.data, 0, t.w * t.h * 4);

	const u8 *font = fontData->GetImage();
	int fw = fontData->GetWidth(), at = 0;
	for(const char *p = s; *p; p++)
	{
		int code = glyphFor(*p);
		GLYPH g = glyphs[code];
		int sx = (code % COLS) * CELL_W + g.left, sy = (code / COLS) * CELL_H;
		if(*p != ' ')
			for(int y = 0; y < CELL_H; y++)
				for(int x = 0; x < g.width; x++)
				{
					u8 a = alphaAt(font, fw, sx + x, sy + y);
					if(a < 80)
						continue;
					for(int dy = 0; dy < scale; dy++)
						for(int dx = 0; dx < scale; dx++)
						{
							int px = (at + x) * scale + dx, py = y * scale + dy;
							if(px < t.w && py < t.h)
								putPixel(t.data, t.w, px, py, c, a);
						}
				}
		at += g.width + TRACK;
	}
	DCFlushRange(t.data, t.w * t.h * 4);		// GX reads memory, not the cache
	return t;
}

static int textWidth(const char *s, int scale)
{
	int pen = 0;
	for(const char *p = s; *p; p++)
		pen += glyphs[glyphFor(*p)].width + TRACK;
	if(pen > 0)
		pen -= TRACK;
	return pen * scale;
}

// Cuts a line to maxW pixels, ending with "..." when it had to be cut.
static void fitText(char *s, int size, int scale, int maxW)
{
	if(maxW <= 0 || textWidth(s, scale) <= maxW)
		return;
	char cut[200];
	for(int n = strlen(s) - 1; n >= 0; n--)
	{
		snprintf(cut, sizeof(cut), "%.*s...", n, s);
		if(textWidth(cut, scale) <= maxW)
			break;
	}
	snprintf(s, size, "%s", cut);
}

static void build()
{
	freeTex(&osdNumber);
	freeTex(&osdLine1);
	freeTex(&osdWhen);
	freeTex(&osdTitle);
	freeTex(&osdNext);

	// the lines must fit inside the bar, so long titles are cut
	int inner = screenwidth - 80 - 36;
	char head[96], title[176], next[176];
	snprintf(head, sizeof(head), "%s  %s", reqNumber, reqChannel);
	snprintf(title, sizeof(title), "%s", reqTitle);
	snprintf(next, sizeof(next), "%s", reqNext);
	fitText(head, sizeof(head), TEXT_SCALE, inner - textWidth(reqWhen, TEXT_SCALE) - 24);
	fitText(title, sizeof(title), TEXT_SCALE, inner);
	fitText(next, sizeof(next), TEXT_SCALE, inner);

	osdNumber = makeText(reqNumber, TEXT_SCALE, (GXColor){ 80, 235, 90, 255 });	// cable box green
	osdLine1 = makeText(head, TEXT_SCALE, (GXColor){ 255, 200, 80, 255 });
	osdWhen = makeText(reqWhen, TEXT_SCALE, (GXColor){ 200, 215, 245, 255 });
	osdTitle = makeText(title, TEXT_SCALE, (GXColor){ 240, 244, 252, 255 });
	osdNext = makeText(next, TEXT_SCALE, (GXColor){ 141, 151, 171, 255 });
}

static void drawTex(TEX *t, f32 x, f32 y, u8 alpha)
{
	if(t->data)
		Menu_DrawImg(x, y, t->w, t->h, t->data, 0, 1, 1, alpha, GX_TF_RGBA8);
}

// The menu text never changes, so it is made once.
static TEX osdMenuTitle, osdMenuHint, osdMarker, osdItem[MENU_ITEMS][2];
static bool menuBuilt = false;

static void drawMenu()
{
	if(!menuBuilt)
	{
		menuBuilt = true;
		osdMenuTitle = makeText("WiiStation 42", TEXT_SCALE, (GXColor){ 255, 200, 80, 255 });
		osdMenuHint = makeText("A: choose   B: back", TEXT_SCALE, (GXColor){ 141, 151, 171, 255 });
		osdMarker = makeText(">", TEXT_SCALE, (GXColor){ 80, 235, 90, 255 });
		for(int i = 0; i < MENU_ITEMS; i++)
		{
			osdItem[i][0] = makeText(menuText[i], TEXT_SCALE, (GXColor){ 240, 244, 252, 255 });
			osdItem[i][1] = makeText(menuText[i], TEXT_SCALE, (GXColor){ 80, 235, 90, 255 });
		}
	}

	// one line of text is LINE_H high everywhere; the panel is sized from it
	int w = osdMenuHint.w + 72;
	if(w < 340)
		w = 340;
	int h = 16 + LINE_H + 16 + MENU_ITEMS * LINE_H + 16 + LINE_H + 12;
	int x = (screenwidth - w) / 2, y = (screenheight - h) / 2;
	Menu_DrawRectangle(x, y, w, h, (GXColor){ 16, 24, 56, 235 }, 1);
	Menu_DrawRectangle(x, y, w, 3, (GXColor){ 90, 140, 220, 255 }, 1);
	drawTex(&osdMenuTitle, x + (w - osdMenuTitle.w) / 2, y + 12, 255);
	int sel = menuSel;
	for(int i = 0; i < MENU_ITEMS; i++)
	{
		int iy = y + 12 + LINE_H + 16 + i * LINE_H;
		if(i == sel)
			drawTex(&osdMarker, x + 34, iy, 255);
		drawTex(&osdItem[i][i == sel ? 1 : 0], x + 64, iy, 255);
	}
	drawTex(&osdMenuHint, x + (w - osdMenuHint.w) / 2, y + h - 12 - LINE_H, 255);
}

// Static after a channel change: grey snow over the new picture that fades
// out. It starts on the first frame drawn after the change, not when the
// button was pressed, so a slow file load does not use it up. A small
// texture is filled with new noise every frame and stretched over the screen.
#define STATIC_MS	600
#define NOISE_W		160
#define NOISE_H		120
static u64 staticAt = 0;
static u8 *noise = NULL;
static u32 noiseSeed = 0x2545F491;

static void drawStatic()
{
	if(staticWanted)
	{
		staticWanted = false;
		staticAt = gettime();
	}
	if(staticAt == 0)
		return;
	int ms = diff_msec(staticAt, gettime());
	if(ms >= STATIC_MS)
	{
		staticAt = 0;
		return;
	}
	if(!noise)
	{
		noise = (u8 *)memalign(32, NOISE_W * NOISE_H * 4);
		if(!noise)
			return;
	}

	// RGBA8 tiles: 16 alpha+red pairs, then 16 green+blue pairs
	u8 *t = noise;
	for(int k = 0; k < (NOISE_W / 4) * (NOISE_H / 4); k++, t += 64)
		for(int i = 0; i < 16; i++)
		{
			noiseSeed ^= noiseSeed << 13;
			noiseSeed ^= noiseSeed >> 17;
			noiseSeed ^= noiseSeed << 5;
			u8 v = (u8)(noiseSeed >> 24);
			t[2 * i] = 255;
			t[2 * i + 1] = v;
			t[32 + 2 * i] = v;
			t[32 + 2 * i + 1] = v;
		}
	DCFlushRange(noise, NOISE_W * NOISE_H * 4);

	// strong at first, gone at the end; drawn about its centre, stretched
	u8 alpha = (u8)(210 - 210 * ms / STATIC_MS);
	Menu_DrawImg(screenwidth / 2 - NOISE_W / 2, screenheight / 2 - NOISE_H / 2, NOISE_W, NOISE_H, noise,
		0, (f32)screenwidth / NOISE_W, (f32)screenheight / NOISE_H, alpha, GX_TF_RGBA8);
}

static bool staticUp()
{
	return staticWanted || staticAt != 0;
}

static void drawBanner();

void TVOsdDraw()
{
	if(!TVOsdActive())
		return;

	drawStatic();	// under the number and the bar

	if(!fontData && fontPng)
	{
		fontData = new GuiImageData(fontPng, fontPngSize, GX_TF_RGBA8);
		if(fontData && fontData->GetImage())
			measure();
	}
	if(!fontData || !fontData->GetImage())
		return;

	if(bannerUp())
		drawBanner();
	if(menuOpen)
		drawMenu();
}

static void drawBanner()
{
	int gen = wantGen;
	if(gen != builtGen)
	{
		builtGen = gen;
		build();
	}

	int ms = diff_msec(shownAt, gettime());
	u8 alpha = 255;
	if(ms > OSD_MS - FADE_MS)
		alpha = (u8)((OSD_MS - ms) * 255 / FADE_MS);

	// the channel number, top right, like a cable box
	drawTex(&osdNumber, screenwidth - 48 - osdNumber.w, 34, alpha);

	// the info bar along the bottom: three lines of the same size
	int barH = 8 + 3 * LINE_H + 8;
	int barX = 40, barW = screenwidth - 80, barY = screenheight - 36 - barH;
	Menu_DrawRectangle(barX, barY, barW, barH, (GXColor){ 16, 24, 56, (u8)(alpha * 7 / 8) }, 1);
	Menu_DrawRectangle(barX, barY, barW, 3, (GXColor){ 90, 140, 220, alpha }, 1);
	drawTex(&osdLine1, barX + 18, barY + 4, alpha);
	drawTex(&osdWhen, barX + barW - 18 - osdWhen.w, barY + 4, alpha);
	drawTex(&osdTitle, barX + 18, barY + 4 + LINE_H, alpha);
	drawTex(&osdNext, barX + 18, barY + 4 + 2 * LINE_H, alpha);
}
