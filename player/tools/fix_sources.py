"""Source fixes for a newer libogc: py3 tools/fix_sources.py src

The 2014 libogc.a cannot be linked by the newer binutils (R_PPC_SDAREL16 in
gu_psasm.o), so the build uses the libogc of the container. A few libogc calls
changed since 2014 and are corrected here.

Each fix says what it looks for. If a fix no longer applies, it is skipped, and
the build shows the real error instead of a wrong edit.
"""
import os
import sys

root = sys.argv[1]

FIXES = [
    # if_config took 4 arguments in libogc 1.8.12; it now takes a retry count.
    ("source/utils/ftp_devoptab.c",
     "if_config(myIP, NULL, NULL, true)",
     "if_config(myIP, NULL, NULL, true, 20)",
     "if_config needs a retry count"),
]

for rel, old, new, why in FIXES:
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        print("skip, file gone:", rel)
        continue
    text = open(path, encoding="utf-8", newline="").read()
    if new in text:
        print("already there:", why)
    elif old in text:
        open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new, 1))
        print("ok:", why)
    else:
        print("skip, code changed:", why)
