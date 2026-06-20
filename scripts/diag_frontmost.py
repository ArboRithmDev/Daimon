#!/usr/bin/env python3
"""Diagnostic — does the frontmost oracle lag after an async activation?

Root-cause probe for the AXE 4b focus bug: ensure_focus reports
`activated_but_not_frontmost` even though the screenshot pixels show the target
already frontmost. Hypothesis: `NSWorkspace.frontmostApplication()` is updated by
an AppKit notification that needs the run loop pumped, so a blocking `time.sleep`
settle reads a stale value forever — while the window server (CGWindowList) and
the AX system-wide focused app reflect reality immediately.

This script activates a target app exactly like Daimon's actuator does, then for
~2s polls THREE independent oracles every 30ms WITHOUT pumping the run loop
(mirroring the server worker thread). It prints, per oracle, at what elapsed time
(if ever) it first reports the target as frontmost.

Run on the real Mac with the same interpreter that has pyobjc, e.g.:
    /Users/Ben/.hfenv/bin/python scripts/diag_frontmost.py com.microsoft.VSCode

Before running: make the target NOT frontmost (click the terminal first), then
launch this — it activates the target and watches who notices, and when.
"""
import sys
import time

from AppKit import NSWorkspace
from ApplicationServices import (
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementGetPid,
)
from CoreFoundation import CFRunLoopRunInMode, kCFRunLoopDefaultMode
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowLayer,
    kCGWindowOwnerPID,
    kCGWindowOwnerName,
)

kCGNullWindow = 0  # not exported by this pyobjc build; the null CGWindowID is 0

POLL_DELAY = 0.03
BUDGET_S = 2.0


def _running_app(bundle):
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() == bundle:
            return app
    return None


def nsworkspace_front_bundle():
    """What MacOSFocusProbe / frontmost_bundle_id() currently use."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def cgwindow_front_pid():
    """Window-server truth: owner pid of the front-most on-screen window (layer 0)."""
    infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindow) or []
    for w in infos:
        if w.get(kCGWindowLayer) == 0:  # 0 = normal app windows, first = frontmost
            return int(w.get(kCGWindowOwnerPID, -1)), w.get(kCGWindowOwnerName)
    return None, None


def ax_systemwide_front_pid():
    """AX truth: pid of the system-wide focused application."""
    system = AXUIElementCreateSystemWide()
    err, app_el = AXUIElementCopyAttributeValue(system, "AXFocusedApplication", None)
    if err != 0 or app_el is None:
        return None
    err, pid = AXUIElementGetPid(app_el, None)
    if err != 0:
        return None
    return int(pid) if pid is not None else None


def main():
    if len(sys.argv) < 2:
        print("usage: diag_frontmost.py <bundle-id>   (e.g. com.microsoft.VSCode)")
        sys.exit(2)
    bundle = sys.argv[1]
    app = _running_app(bundle)
    if app is None:
        print(f"FAIL: no running app with bundle {bundle!r}")
        sys.exit(1)
    target_pid = int(app.processIdentifier())

    print(f"target: {bundle}  pid={target_pid}")

    # --- force the target OUT of the foreground first, so we observe a real
    # transition (the bug only shows when the target was NOT already frontmost).
    park = _running_app("com.apple.finder")
    if park is None or int(park.processIdentifier()) == target_pid:
        print("FAIL: need Finder running and != target to park the foreground")
        sys.exit(1)
    park.activateWithOptions_(1 << 1)
    # Pump the run loop so the parking activation genuinely lands (this is the
    # ONLY pump in the script — it sets up the precondition; the measured window
    # below uses plain time.sleep with no pump, mirroring the server worker).
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.8, False)
    print(f"PARKED to Finder. now front: nsworkspace={nsworkspace_front_bundle()!r}  "
          f"cgwindow={cgwindow_front_pid()}  ax_pid={ax_systemwide_front_pid()}")
    if nsworkspace_front_bundle() == bundle:
        print("WARN: target still frontmost after parking — transition not set up")

    # Activate exactly like the actuator's _activate does, then poll WITHOUT pump.
    app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
    t0 = time.monotonic()

    first = {"nsworkspace": None, "cgwindow": None, "ax": None}
    rows = []
    while time.monotonic() - t0 < BUDGET_S:
        elapsed = time.monotonic() - t0
        ns = nsworkspace_front_bundle()
        cg_pid, cg_name = cgwindow_front_pid()
        ax_pid = ax_systemwide_front_pid()
        ns_ok = ns == bundle
        cg_ok = cg_pid == target_pid
        ax_ok = ax_pid == target_pid
        if ns_ok and first["nsworkspace"] is None:
            first["nsworkspace"] = elapsed
        if cg_ok and first["cgwindow"] is None:
            first["cgwindow"] = elapsed
        if ax_ok and first["ax"] is None:
            first["ax"] = elapsed
        rows.append((elapsed, ns, ns_ok, cg_pid, cg_name, cg_ok, ax_pid, ax_ok))
        time.sleep(POLL_DELAY)  # plain blocking sleep — mirrors the server worker

    print("\nelapsed_ms | nsworkspace_bundle (ok) | cgwindow pid/name (ok) | ax_pid (ok)")
    for (el, ns, ns_ok, cg_pid, cg_name, cg_ok, ax_pid, ax_ok) in rows:
        print(f"{int(el*1000):>6}     | {str(ns):<28} {'Y' if ns_ok else '.'}  | "
              f"{cg_pid}/{cg_name} {'Y' if cg_ok else '.'}  | {ax_pid} {'Y' if ax_ok else '.'}")

    def fmt(v):
        return f"{int(v*1000)}ms" if v is not None else "NEVER (within %.0fms)" % (BUDGET_S * 1000)

    print("\n=== first time each oracle saw the target frontmost (no run-loop pump) ===")
    print(f"  NSWorkspace.frontmostApplication : {fmt(first['nsworkspace'])}")
    print(f"  CGWindowList front owner         : {fmt(first['cgwindow'])}")
    print(f"  AX system-wide focused app       : {fmt(first['ax'])}")
    print("\nReading:")
    print("  - If NSWorkspace=NEVER but CGWindow/AX=fast  -> root cause = wrong/stale oracle;")
    print("    fix = switch MacOSFocusProbe to the window-server/AX source (no run-loop dep).")
    print("  - If NSWorkspace updates but only at >180ms   -> settle budget too short on this Mac.")
    print("  - If ALL are NEVER                            -> activation itself did not take (env focus steal).")


if __name__ == "__main__":
    main()
