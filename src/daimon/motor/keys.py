"""Key-name → macOS virtual keycode + modifier flag mapping. Pure (no imports
of pyobjc); the numeric constants mirror Carbon/CGEvent values so the actuator
can build keyboard events without a lookup table of its own."""

from __future__ import annotations

# Carbon virtual keycodes (kVK_*) for the keys an agent commonly needs.
KEYCODES: dict[str, int] = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "escape": 53, "esc": 53, "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121, "forwarddelete": 117,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28,
    "9": 25, "0": 29,
}

# CGEventFlags bit masks (mirror Quartz.kCGEventFlagMaskCommand etc.).
_MOD_FLAGS = {
    "cmd": 1 << 20, "command": 1 << 20,
    "shift": 1 << 17,
    "opt": 1 << 19, "option": 1 << 19, "alt": 1 << 19,
    "ctrl": 1 << 18, "control": 1 << 18,
}


def keycode_for(name: str) -> int:
    return KEYCODES[name.strip().lower()]


def modifier_mask(modifiers: list[str]) -> int:
    mask = 0
    for m in modifiers or []:
        mask |= _MOD_FLAGS[m.strip().lower()]
    return mask
