/****************************************************************************
 * WiiStation 42 - the channel overlay
 *
 * After a channel change the viewer sees the channel number in green at the
 * top right, and an info bar along the bottom: the channel, the programme,
 * its time and what comes next. It is drawn in crezno's bitmap font (font.png
 * beside the channel files) and goes away by itself after a few seconds.
 ***************************************************************************/

#ifndef _TVOSD_H_
#define _TVOSD_H_

// Main thread, before anything plays: reads font.png from the channel folder.
void TVOsdLoadFont(const char *dir);

// Player thread: asks for the overlay. The strings are copied.
void TVOsdRequest(const char *number, const char *channel, const char *title,
                  const char *when, const char *next);

// True while the overlay should be on screen.
bool TVOsdActive();

// Pad thread: whether the viewer asked for the normal seek bar as well.
void TVOsdSetBarWanted(bool wanted);

// True when only the overlay is drawn, without the seek bar.
bool TVOsdAlone();

// Drawing thread only: builds the pictures when they are new, and draws.
void TVOsdDraw();

// While the station starts, the WiiMC menu is not drawn: the screen stays
// black until the opening plays. It gives up after 20 seconds, so an error
// message can never stay hidden.
void TVOsdSetBooting(bool on);
bool TVOsdBooting();

// The station menu, opened with START while watching.
enum { TVMENU_NONE = -1, TVMENU_TV, TVMENU_GUIDE, TVMENU_MEDIA, TVMENU_EXIT };

// Pad thread: gives the menu this pass's buttons. True when the menu used
// them (it was open, or START opened it), so nothing else acts on them.
bool TVMenuKeys(bool start, bool back, bool up, bool down, bool choose);

// Pad thread: the item the viewer chose, once, or TVMENU_NONE.
int TVMenuTakeChoice();

// The WiiMC menu counts each time it opens. A request to go there that comes
// near the end or the start of a file is lost, so the pad thread sends it
// again until this count moves.
void TVGuiEntered();
int TVGuiEntries();

// A test run (selftest.txt says "menu") presses the menu buttons by itself.
// TVMenuSelfTest adds this pass's presses; TVSelfTestStart is START in the
// WiiMC menu, true once.
void TVMenuSelfTest(bool *start, bool *back, bool *up, bool *down, bool *choose);
bool TVSelfTestStart();

#endif
