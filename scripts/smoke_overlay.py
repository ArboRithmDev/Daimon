"""Overlay smoke test — requires the overlay process (macOS, AppKit).

Launches the overlay helper if not already running, then sends a short demo
sequence to verify the socket channel and each command type.

    PYTHONPATH=src python scripts/smoke_overlay.py
"""

from __future__ import annotations

import time

from daimon.overlay import launcher
from daimon.overlay.client import OverlayClient
from daimon.overlay.protocol import Banner, Clear, Highlight, Ripple, Spotlight


def main() -> int:
    print("smoke_overlay: ensuring overlay process is running…")
    launcher.ensure_running()
    time.sleep(0.5)  # give the process a moment to bind its socket

    client = OverlayClient(launcher.socket_path())

    steps = [
        ("highlight (default) — full-screen centre rect",
         Highlight(x=600, y=400, w=200, h=80, label='AXButton "Demo"', style="default")),
        ("banner — info level",
         Banner(text="Daimon overlay smoke running…", level="L1")),
        ("ripple — confirm-style feedback at rect centre",
         Ripple(x=700, y=440)),
        ("highlight (gate style) — gate confirmation example",
         Highlight(x=600, y=400, w=200, h=80, label='AXButton "Confirm"', style="gate")),
        ("banner — gate level",
         Banner(text="CONFIRM • action requires human approval", level="L3")),
        ("clear — remove all drawings",
         Clear()),
    ]

    for description, command in steps:
        print(f"  → {description}")
        client.send(command)
        time.sleep(0.4)

    print("smoke_overlay: done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
