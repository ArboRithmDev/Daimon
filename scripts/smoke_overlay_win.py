"""Live overlay smoke (Windows) — spawns the Qt overlay helper and draws on it.

    .venv-win\\Scripts\\python.exe scripts/smoke_overlay_win.py

You should see, on top of everything: a HUD banner, a highlighted rectangle with
a label, a cursor halo, and a few click ripples — none of which intercept your
clicks (the overlay is click-through). Then take a screenshot (Win+Shift+S): the
overlay must be ABSENT from it (SetWindowDisplayAffinity / WDA_EXCLUDEFROMCAPTURE).
The helper auto-quits a few seconds after this script disconnects.
"""

from __future__ import annotations

import time

from daimon.overlay.launcher_win import ensure_running, make_client
from daimon.overlay.protocol import Banner, Clear, Cursor, Highlight, Ripple


def main() -> int:
    ensure_running()
    time.sleep(1.2)  # let the helper bind its port + open the window
    c = make_client()
    c.send(Banner(text="Daimon overlay smoke — invisible to capture", level="L2"))
    c.send(Highlight(x=200, y=200, w=320, h=140, label="target", style="L2"))
    c.send(Cursor(x=360, y=270))
    for _ in range(6):
        c.send(Ripple(x=360, y=270))
        time.sleep(0.25)
    time.sleep(2.0)
    c.send(Clear())
    print("overlay smoke sent — confirm it showed AND is absent from a screenshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
