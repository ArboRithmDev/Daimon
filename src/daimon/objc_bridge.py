"""Shared Objective-C action target for menu items and buttons.

Objective-C class names are GLOBAL to the process. Defining a class named
`_ButtonTarget` in two modules (the tray and the onboarding window) raises
`objc.error: _ButtonTarget is overriding existing Objective-C class` as soon as
both run in the same process. So there is exactly ONE target class here, shared
by every caller. AppKit/objc imports are deferred so bare import stays clean.
"""

from __future__ import annotations


def make_target(callback):
    """Return an ObjC object whose `invoke:` selector calls *callback*.

    The NSObject subclass is defined once per process and cached.
    """
    from Foundation import NSObject
    import objc

    if not hasattr(make_target, "_cls"):
        class _DaimonActionTarget(NSObject):
            def init(self):
                self = objc.super(_DaimonActionTarget, self).init()
                if self is None:
                    return None
                self._cb = None
                return self

            @objc.python_method
            def _set_callback(self, cb):
                self._cb = cb

            def invoke_(self, sender):
                if self._cb is not None:
                    try:
                        self._cb()
                    except Exception:
                        from .applog import log_exception
                        log_exception("objc action target invoke")

        make_target._cls = _DaimonActionTarget

    instance = make_target._cls.alloc().init()
    instance._set_callback(callback)
    return instance
