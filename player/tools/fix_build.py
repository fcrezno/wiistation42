"""Build fixes for newer devkitPPC: py3 tools/fix_build.py src/Makefile

This 2014 code was written for devkitPPC r26. On r30 (GCC 8.1):
  * MAXPATHLEN is gone. Every path field uses it, so struct BROWSER loses its
    members and filebrowser.cpp fails. 1024 is the value newlib used before.
  * stricmp / strnicmp are gone. They are strcasecmp / strncasecmp.
  * uint32_t is "long unsigned int" here, so libogc's u32* no longer converts
    to unsigned int*. -fpermissive makes those C++ conversions warnings again,
    which is what the code assumed.
  * std::prev exists from C++11 on, and several files say "using namespace std"
    while having their own prev, so build as C++98 like the original.
"""
import sys

CFLAGS_OLD = "CFLAGS\t\t=\t-g -O3 -Wall $(MACHDEP) $(INCLUDE)  \\"
CFLAGS_EXTRA = "-DMAXPATHLEN=1024 -Dstricmp=strcasecmp -Dstrnicmp=strncasecmp"
CFLAGS_NEW = "CFLAGS\t\t=\t-g -O3 -Wall $(MACHDEP) $(INCLUDE) " + CFLAGS_EXTRA + " \\"
CXX_OLD = "CXXFLAGS\t=\t$(CFLAGS)"
CXX_NEW = "CXXFLAGS\t=\t$(CFLAGS) -fpermissive -std=gnu++98"

path = sys.argv[1]
text = open(path, encoding="utf-8", newline="").read()
changed = False

if CFLAGS_EXTRA in text:
    print("already there:", CFLAGS_EXTRA)
elif CFLAGS_OLD in text:
    text, changed = text.replace(CFLAGS_OLD, CFLAGS_NEW, 1), True
    print("ok: added", CFLAGS_EXTRA)
else:
    sys.exit("FAILED: CFLAGS line not found in " + path)

if "-std=gnu++98" in text:
    print("already there: C++ flags")
elif CXX_OLD in text:
    text, changed = text.replace(CXX_OLD, CXX_NEW, 1), True
    print("ok: added -fpermissive -std=gnu++98")
else:
    sys.exit("FAILED: CXXFLAGS line not found in " + path)

if changed:
    open(path, "w", encoding="utf-8", newline="").write(text)
    print("written:", path)
