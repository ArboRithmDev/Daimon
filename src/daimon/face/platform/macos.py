"""macOS native window traits for the face, via pyobjc. pywebview exposes the
underlying NSWindow as `window.native` (set once the window is created); with
`transparent=True` pywebview already draws the WKWebView with a transparent
background, so a NSVisualEffectView placed behind it shows real desktop blur
through the page's transparent areas and the semi-transparent panel card.

These bodies run only on a real Mac (validated live); they no-op safely if the
native handle isn't available yet."""

from __future__ import annotations


def _nswindow(window):
    return getattr(window, "native", None)


class MacOSFaceAdapter:
    def run_on_main(self, fn) -> None:
        """Schedule fn on the AppKit main thread. pywebview fires window events on
        a background thread, but NSWindow management (setFrame/setLevel/…) asserts
        main-thread — calling off-main is a hard SIGTRAP crash."""
        from PyObjCTools import AppHelper
        AppHelper.callAfter(fn)

    def apply_vibrancy(self, window, *, dark: bool = True, radius: int = 20) -> None:
        """Put a rounded NSVisualEffectView behind the (transparent) web content
        so the panel reads as a frosted, floating macOS surface."""
        import AppKit

        nswin = _nswindow(window)
        if nswin is None:
            return
        content = nswin.contentView()  # the WKWebView pywebview installed
        if content is None:
            return

        effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.bounds())
        effect.setMaterial_(AppKit.NSVisualEffectMaterialPopover)
        effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        effect.setState_(AppKit.NSVisualEffectStateActive)
        effect.setAppearance_(AppKit.NSAppearance.appearanceNamed_(
            AppKit.NSAppearanceNameVibrantDark if dark else AppKit.NSAppearanceNameVibrantLight))
        effect.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(radius)
        effect.layer().setMasksToBounds_(True)

        # Swap the web content to sit on top of the effect view.
        nswin.setContentView_(effect)
        effect.addSubview_(content)
        content.setFrame_(effect.bounds())

        # Restore a soft window shadow (pywebview drops it for transparent windows).
        nswin.setHasShadow_(True)

    def exclude_from_capture(self, window) -> None:
        """Exclude the window from screen capture (the overlay must never appear
        in a screenshot/recording)."""
        import AppKit

        nswin = _nswindow(window)
        if nswin is not None:
            nswin.setSharingType_(AppKit.NSWindowSharingNone)

    def set_click_through(self, window) -> None:
        """Let all mouse events pass through to the apps below (the overlay face
        is presentational; the user interacts with what's underneath)."""
        nswin = _nswindow(window)
        if nswin is not None:
            nswin.setIgnoresMouseEvents_(True)

    def fit_to_screen(self, window) -> None:
        """Size the window to the full main screen — the overlay is a screen-wide
        transparent canvas (room for the companion + future AI drawing)."""
        import AppKit

        nswin = _nswindow(window)
        screen = AppKit.NSScreen.mainScreen()
        if nswin is not None and screen is not None:
            nswin.setFrame_display_(screen.frame(), True)
            nswin.setLevel_(AppKit.NSStatusWindowLevel)  # float above normal windows

    def anchor_under_statusitem(self, window, statusitem) -> None:
        """Position the panel just below a status-item button. `statusitem` is an
        NSStatusItem; we read its button's screen frame and place the window
        under it, right-aligned. No-op if geometry isn't available yet."""
        import AppKit

        nswin = _nswindow(window)
        button = getattr(statusitem, "button", lambda: None)()
        if nswin is None or button is None:
            return
        bwin = button.window()
        if bwin is None:
            return
        bframe = bwin.convertRectToScreen_(button.convertRect_toView_(button.bounds(), None))
        wframe = nswin.frame()
        x = bframe.origin.x + bframe.size.width - wframe.size.width
        y = bframe.origin.y - wframe.size.height - 4  # a few px gap below the menu bar
        nswin.setFrameOrigin_(AppKit.NSPoint(x, y))
