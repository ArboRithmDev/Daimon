"""Tiny file logger for the GUI processes (tray, onboarding).

A windowed PyInstaller .app has no stdout/stderr, so `traceback.print_exc()`
goes nowhere (and can itself raise on a None stream). Route diagnostics to a
file under the user data dir instead, so failures are always recoverable.
"""

from __future__ import annotations


def log_path():
    """Path to the GUI app log file under the user data dir."""
    from .userdata import logs_dir
    return logs_dir() / "daimon-app.log"


def log_exception(context: str) -> None:
    """Append the current exception traceback to the app log. Never raises."""
    import traceback
    try:
        from datetime import datetime, timezone
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with p.open("a", encoding="utf-8") as f:
            f.write(f"\n--- {ts}  {context} ---\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def log_message(message: str) -> None:
    """Append a plain line to the app log. Never raises."""
    try:
        from datetime import datetime, timezone
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{ts}  {message}\n")
    except Exception:
        pass
