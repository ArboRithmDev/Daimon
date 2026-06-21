"""Entrypoint for the `daimon` binary (one executable, dispatches on argv).

Behaviours:
  * `daimon serve`                                  → MCP stdio server (clients)
  * `daimon setup|install|uninstall|status|onboard` → setup CLI
  * `daimon --gui`                                  → onboarding GUI
  * `daimon` (no args):
      - inside a frozen .app (double-clicked from Finder) → resident menu-bar tray
      - from source (`python -m daimon`)                 → MCP server (back-compat)

A single executable keeps the macOS .app bundle simple (PyInstaller does not
cleanly support two executables in one bundle). MCP clients are registered with
an explicit `serve` argument (see setup/invocation.py).

NOTE: imports below are ABSOLUTE (`daimon.…`), not relative. PyInstaller runs
this file as the top-level `__main__` script with no package context, so
relative imports (`from .server …`) raise "attempted relative import with no
known parent package" in the frozen .app. Absolute imports work both frozen and
under `python -m daimon`.
"""

from __future__ import annotations

import sys

_SUBCOMMANDS = {"setup", "install", "uninstall", "status", "onboard"}


def _run_server() -> int:
    from daimon.server import main as server_main
    server_main()
    return 0


def _run_overlay() -> int:
    # The overlay helper. MUST be a real subcommand: in the frozen .app the
    # spawn target is the Daimon binary (sys.executable), not python, so
    # `Daimon -m daimon.overlay.app` would land in the default branch below and
    # launch ANOTHER TRAY instead of the overlay — every overlay spawn then
    # piled up a duplicate menu-bar Daimon. Routing an explicit `overlay`
    # argument fixes that for both frozen and source launches.
    from daimon.overlay.app.__main__ import main as overlay_main
    overlay_main()
    return 0


def _run_gui() -> int:
    from daimon.setup.gui.__main__ import main as gui_main
    return gui_main()


def _run_panel() -> int:
    """The webview face PANEL as its own process (the Duo charte UI). The Windows
    tray toggles it on glyph click — pywebview (WebView2) and the Qt tray each own
    an incompatible GUI loop, so the panel runs standalone here and owns its own.

    A frozen-reachable `face` subcommand: in the frozen exe the spawn target is
    Daimon.exe (sys.executable), so it must dispatch on an explicit arg.
    """
    import os

    import webview

    from daimon.face.bridge import FaceBridge
    from daimon.face.host import FaceHost
    from daimon.face.native_win import confirm_l4, open_onboarding
    from daimon.tray.actions import ActionRouter
    from daimon.tray.actions_impl import TrayActions
    from daimon.tray.state import gather

    holder: dict = {}

    def push():
        host = holder.get("host")
        if host is not None:
            host.push_state()

    def quit_all():
        # "Quit Daimon" from the panel must stop the owning tray too, not just
        # this panel process. The tray passes its PID in the environment.
        owner = os.environ.get("DAIMON_TRAY_PID")
        if owner:
            try:
                os.kill(int(owner), 9)
            except Exception:
                pass
        for w in list(getattr(webview, "windows", [])):
            try:
                w.destroy()
            except Exception:
                pass

    handlers = TrayActions(
        on_change=push,
        confirm_l4=confirm_l4,
        open_onboarding=open_onboarding,
        on_quit=quit_all,
    )
    from daimon.face.platform import get_adapter
    adapter = get_adapter()
    bridge = FaceBridge(ActionRouter(handlers), gather)
    host = FaceHost(bridge, webview_module=webview, adapter=adapter)
    holder["host"] = host
    win = host.open_panel()

    def _place():
        # Pin the panel to the tray corner. Corner rounding is left to DWM (smooth,
        # native Win11) over the square card — a GDI SetWindowRgn would jag the edge
        # and clash with the card's antialiased corner.
        adapter.anchor_under_statusitem(win, None)

    def _dismiss():
        for w in list(getattr(webview, "windows", [])):
            try:
                w.destroy()
            except Exception:
                pass

    def _on_shown():
        _place()
        adapter.focus(win)
        # Dismiss-on-blur: a click outside the panel closes it (the process exits;
        # the tray re-spawns it on the next glyph click).
        adapter.watch_outside_click(win, None, _dismiss)

    # Re-round + re-anchor after the web layer fits the window to its content
    # height (the panel auto-resizes), so the corner stays pinned with no gap and
    # the rounded region tracks the new size.
    bridge.set_resizer(lambda w, h: (win.resize(w, h), _place()))
    events = getattr(win, "events", None)
    if events is not None and hasattr(events, "shown"):
        events.shown += _on_shown
    else:
        _on_shown()

    # http_server: serve the bundle over http://127.0.0.1 so its CSP 'self' allows it.
    webview.start(http_server=True)
    return 0


def _face_tray_available() -> bool:
    """Whether the integrated webview "face" tray can run here: pywebview importable
    AND the built web bundle present. A single seam so dispatch is deterministic +
    testable.

    macOS-only for now: `face.tray` hosts the panel + NSStatusItem on the shared
    NSApplication run loop (AppKit). On Windows the panel renders fine in WebView2,
    but the tray-glyph→panel integration isn't built yet, so dispatch falls back to
    the native Qt tray (which carries the coloured Duo glyph) even though pywebview
    is now installed — otherwise this would route to the AppKit-only face tray and
    crash on launch."""
    if sys.platform != "darwin":
        return False
    try:
        import webview  # noqa: F401
        from daimon.face.host import _dist_dir
        return (_dist_dir() / "panel" / "index.html").exists()
    except Exception:
        return False


def _run_tray() -> int:
    # Prefer the webview "face" tray (the glyph opens the frosted panel); fall back
    # to the native NSMenu tray if pywebview or the built bundle is missing, so the
    # app always has a menu-bar presence.
    if _face_tray_available():
        from daimon.face.tray import run as face_run
        return face_run()
    from daimon.tray.app.__main__ import main as tray_main
    return tray_main()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    # Explicit commands win, in any mode.
    if argv and argv[0] == "serve":
        return _run_server()
    if argv and argv[0] == "overlay":
        return _run_overlay()
    if argv and argv[0] == "face":
        return _run_panel()
    if argv and argv[0] in _SUBCOMMANDS:
        from daimon.setup.cli import run_command
        return run_command(argv)
    if argv and "--gui" in argv:
        return _run_gui()

    # Default (no explicit command):
    #   * frozen .app → the resident menu-bar tray. LaunchServices may pass stray
    #     args (e.g. `-psn_0_12345`), so the tray is the default for ANY non-command
    #     argv when frozen — never fall through to the stdio server, which would
    #     just wait on absent stdin and show nothing.
    #   * from source → the MCP server (back-compat for `python -m daimon`).
    if getattr(sys, "frozen", False):
        return _run_tray()
    return _run_server()


if __name__ == "__main__":
    raise SystemExit(main())
