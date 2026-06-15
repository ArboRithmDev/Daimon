"""Key-name → Windows Virtual-Key code mapping. Pure (no ctypes here).

Mirrors ``keys.py`` (the macOS Carbon table) for the same key names an agent
uses, but emits Windows VK_* codes. Unlike macOS — where modifiers are a flag
mask OR-ed onto one event — Windows modifiers are *real keys* the actuator must
press down before, and release after, the main key. So this module exposes the
modifier **VK codes to hold** rather than a flag mask.

Note on ``cmd``/``command``: macOS's Command key has no Windows equivalent; it
maps to the Windows logo key (VK_LWIN). Cross-platform agents driving Windows
should send ``ctrl`` for shortcuts, not ``cmd``.
"""

from __future__ import annotations

# Windows Virtual-Key codes for the keys an agent commonly needs.
# Names kept identical to keys.py so the same agent vocabulary works on both OSes.
VK: dict[str, int] = {
    "return": 0x0D, "enter": 0x0D, "tab": 0x09, "space": 0x20,
    "delete": 0x08,        # macOS "delete" == Backspace
    "forwarddelete": 0x2E,  # the forward Delete key
    "escape": 0x1B, "esc": 0x1B,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
# Letters a–z → 0x41–0x5A; digits 0–9 → 0x30–0x39 (VK codes == ASCII upper).
VK.update({chr(c): c - 0x20 for c in range(ord("a"), ord("z") + 1)})  # 'a'->0x41
VK.update({str(d): 0x30 + d for d in range(10)})

# Modifier name → VK code to hold down around the main key.
_MOD_VK = {
    "ctrl": 0x11, "control": 0x11,            # VK_CONTROL
    "shift": 0x10,                            # VK_SHIFT
    "alt": 0x12, "opt": 0x12, "option": 0x12,  # VK_MENU
    "cmd": 0x5B, "command": 0x5B, "win": 0x5B,  # VK_LWIN (no true Command on Windows)
}


def vk_for(name: str) -> int:
    """VK code for a key name (case-insensitive). Raises KeyError if unknown."""
    return VK[name.strip().lower()]


def modifier_vks(modifiers: list[str]) -> list[int]:
    """VK codes for the given modifier names, to be held around the main key."""
    out: list[int] = []
    for m in modifiers or []:
        out.append(_MOD_VK[m.strip().lower()])
    return out
