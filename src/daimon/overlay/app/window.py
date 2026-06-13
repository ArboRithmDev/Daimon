"""Transparent, click-through, capture-invisible overlay window."""

from __future__ import annotations


def make_overlay_window(anti_feedback: bool = True):
    from AppKit import (
        NSWindow, NSScreen, NSColor, NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered, NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary, NSScreenSaverWindowLevel,
        NSWindowSharingNone,
    )
    frame = NSScreen.mainScreen().frame()
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setLevel_(NSScreenSaverWindowLevel)          # above normal windows
    win.setIgnoresMouseEvents_(True)                  # click-through
    win.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
    if anti_feedback:
        win.setSharingType_(NSWindowSharingNone)      # invisible to screen capture
    win.contentView().setWantsLayer_(True)
    win.orderFrontRegardless()
    return win
