"""Entrypoint for the `daimon` binary (one executable, dispatches on argv).

Behaviours:
  * `daimon serve`                                  → MCP stdio server (clients)
  * `daimon setup|install|uninstall|status|onboard` → setup CLI
  * `daimon --gui`                                  → onboarding GUI
  * `daimon` (no args):
      - inside a frozen .app (double-clicked from Finder) → onboarding GUI
      - from source (`python -m daimon`)                 → MCP server (back-compat)

A single executable keeps the macOS .app bundle simple (PyInstaller does not
cleanly support two executables in one bundle). MCP clients are registered with
an explicit `serve` argument (see setup/invocation.py).
"""

from __future__ import annotations

import sys

_SUBCOMMANDS = {"setup", "install", "uninstall", "status", "onboard"}


def _run_server() -> int:
    from .server import main as server_main
    server_main()
    return 0


def _run_gui() -> int:
    from .setup.gui.__main__ import main as gui_main
    return gui_main()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == "serve":
        return _run_server()
    if argv and argv[0] in _SUBCOMMANDS:
        from .setup.cli import run_command
        return run_command(argv)
    if argv and "--gui" in argv:
        return _run_gui()
    if not argv:
        # Frozen .app launched from Finder → show the onboarding GUI.
        # Source `python -m daimon` with no args → start the server (back-compat).
        if getattr(sys, "frozen", False):
            return _run_gui()
        return _run_server()
    # Any other args → server (back-compat: clients historically passed none).
    return _run_server()


if __name__ == "__main__":
    raise SystemExit(main())
