"""Smoke the Windows face: launch a real pywebview (WebView2) panel, prove it
renders the built bundle, optionally grab a screenshot, then auto-close.

    python scripts/smoke_face_win.py [--surface panel|onboarding|overlay]
                                     [--shot PATH] [--seconds N]

Requires: the built bundle (`python build/make_face.py`), pywebview + pythonnet,
and the WebView2 runtime. Exits 0 on a clean open+close, non-zero on any error.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


# A decision-free brand state so the React surfaces render without the live organ.
_STATE = {
    "version": "0.0.10",
    "permissions": {"screen_recording": True, "accessibility": True},
    "clients": [
        {"name": "Claude Code", "registered": True},
        {"name": "GitHub Copilot", "registered": True},
        {"name": "Vibe", "registered": False},
    ],
    "ceiling": {"current": "READ",
                "settable": ["READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"],
                "l4_active": False},
    "overlay_on": False,
    "brand": {"style": "organic", "lead": "beside", "finish": "indigo",
              "presence": "#B66CFF", "companion": "#E8B23A"},
}


class _StubBridge:
    """The js_api the webview calls — get_state / invoke only, no authority."""

    def get_state(self):
        return _STATE

    def invoke(self, action_id, args=None):
        return {"ok": True, "reason": ""}


_TITLES = {"panel": "Daimon", "onboarding": "Welcome to Daimon",
           "overlay": "Daimon Overlay"}


def _hwnd(window, surface="panel"):
    """Best-effort HWND from a pywebview EdgeChromium window (WinForms Form),
    falling back to a top-level window lookup by title."""
    try:
        h = int(window.native.Handle)
        if h:
            return h
    except Exception:
        pass
    try:
        import win32gui
        return win32gui.FindWindow(None, _TITLES.get(surface, "Daimon")) or None
    except Exception:
        return None


def _grab(window, shot: Path, surface: str = "panel") -> bool:
    try:
        import win32gui
        from PIL import ImageGrab
        hwnd = _hwnd(window, surface)
        if not hwnd:
            print("screenshot skipped: no HWND")
            return False
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        rect = win32gui.GetWindowRect(hwnd)
        img = ImageGrab.grab(bbox=rect)
        shot.parent.mkdir(parents=True, exist_ok=True)
        img.save(shot)
        print(f"screenshot -> {shot} ({img.size})")
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort
        print(f"screenshot skipped: {exc}")
        return False


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--surface", default="panel",
                   choices=["panel", "onboarding", "overlay"])
    p.add_argument("--shot", default=None, help="save a screenshot to this path")
    p.add_argument("--seconds", type=float, default=4.0)
    args = p.parse_args(argv)

    import webview

    from daimon.face.host import FaceHost

    host = FaceHost(_StubBridge(), webview_module=webview)
    opener = {"panel": host.open_panel,
              "onboarding": host.open_onboarding,
              "overlay": host.open_overlay}[args.surface]
    window = opener()

    result = {"ok": True, "err": None}

    def watchdog():
        # Shoot late enough that the bridge's get_state has resolved and React has
        # mounted the full surface (an early grab catches the "connecting…" splash).
        shot_at = max(0.5, args.seconds - 1.0)
        time.sleep(shot_at)
        if args.shot:
            _grab(window, Path(args.shot), args.surface)
        time.sleep(max(0.0, args.seconds - shot_at))
        try:
            window.destroy()
        except Exception as exc:  # noqa: BLE001
            result["ok"], result["err"] = False, exc

    threading.Thread(target=watchdog, daemon=True).start()

    try:
        # http_server: serve over http://127.0.0.1 so the bundle's CSP 'self' allows it.
        webview.start(http_server=True)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: webview.start raised {exc!r}")
        return 1

    if not result["ok"]:
        print(f"FAIL: teardown raised {result['err']!r}")
        return 1
    print(f"OK: {args.surface} surface opened + closed cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
