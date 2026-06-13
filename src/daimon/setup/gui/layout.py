"""Premium permission-row builder for the onboarding content view.

Builds NSTextField label + status dot + "Grant" NSButton rows into a given
NSView. All AppKit imports are deferred inside functions so a bare
``import daimon.setup.gui.layout`` on a non-macOS system (or in a test
runner) succeeds without any system-framework dependency.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def build_panel(controller, content_view) -> None:
    """Populate *content_view* with permission rows wired to *controller*.

    Each row contains:
    - a status dot (NSTextField, updated by the poller)
    - a human-readable label (NSTextField)
    - a "Grant" button whose action calls ``controller.grant(key)``

    The controller must expose ``_rows`` (dict) and a ``_make_target``
    helper so the button target is a proper Objective-C object.
    """
    from AppKit import (
        NSTextField,
        NSButton,
        NSMakeRect,
        NSTextAlignmentCenter,
        NSBezelStyleRounded,
    )
    from ..permissions import permissions_status, FakeBackend

    # We need the permission list to know the rows; we use a FakeBackend
    # just to get the Permission metadata (key/label) — the real backend
    # is on the controller and will be polled separately.
    fake = FakeBackend()
    perms = permissions_status(fake)

    row_height: float = 44.0
    margin: float = 20.0
    dot_w: float = 28.0
    label_w: float = 240.0
    btn_w: float = 72.0
    btn_h: float = 28.0
    y_start: float = 60.0  # bottom of last row (rows stack upward)

    for i, perm in enumerate(perms):
        y = y_start + i * row_height

        # --- Dot (🟢 / ⚪️) ---
        dot = NSTextField.alloc().initWithFrame_(
            NSMakeRect(margin, y, dot_w, btn_h)
        )
        dot.setStringValue_("⚪️")
        dot.setBezeled_(False)
        dot.setDrawsBackground_(False)
        dot.setEditable_(False)
        dot.setAlignment_(NSTextAlignmentCenter)
        content_view.addSubview_(dot)

        # --- Label ---
        label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(margin + dot_w + 6, y, label_w, btn_h)
        )
        label.setStringValue_(perm.label)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        content_view.addSubview_(label)

        # --- Grant button ---
        btn_x = margin + dot_w + 6 + label_w + 8
        btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(btn_x, y, btn_w, btn_h)
        )
        btn.setTitle_("Grant")
        btn.setBezelStyle_(NSBezelStyleRounded)

        # Wire target/action to a proper ObjC object (see window._make_target)
        key = perm.key
        target = controller._make_target(lambda k=key: controller.grant(k))
        btn.setTarget_(target)
        btn.setAction_("invoke:")
        content_view.addSubview_(btn)

        # Store the dot widget so the poller can update it
        controller._rows[perm.key] = {"dot": dot, "btn": btn, "target": target}

    # --- Title label ---
    title_y = y_start + len(perms) * row_height + 12
    title = NSTextField.alloc().initWithFrame_(
        NSMakeRect(margin, title_y, 420, 30)
    )
    title.setStringValue_("Daimon needs a few macOS permissions to work.")
    title.setBezeled_(False)
    title.setDrawsBackground_(False)
    title.setEditable_(False)
    content_view.addSubview_(title)
