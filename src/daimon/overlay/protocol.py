"""Pure overlay command protocol — dataclasses ↔ newline-delimited JSON.

No macOS imports: the same commands are produced on the MCP-server side and
consumed in the overlay process. One JSON object per line; `cmd` tags the type.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Highlight:
    """Draw a styled rectangle (and optional label) around a target."""
    x: int; y: int; w: int; h: int
    label: str = ""
    style: str = "default"   # default|L1|L2|L3|gate
    cmd: str = field(default="highlight", init=False)


@dataclass(frozen=True)
class Spotlight:
    """Dim the screen except for a clear hole over the given region."""
    x: int; y: int; w: int; h: int
    cmd: str = field(default="spotlight", init=False)


@dataclass(frozen=True)
class Cursor:
    """Place the synthetic cursor marker at a point."""
    x: int; y: int
    cmd: str = field(default="cursor", init=False)


@dataclass(frozen=True)
class Ripple:
    """One-shot expanding-fade pulse at a point, marking a completed action."""
    x: int; y: int
    cmd: str = field(default="ripple", init=False)


@dataclass(frozen=True)
class Banner:
    """Show a level-coloured status banner with the given text."""
    text: str
    level: str = "L1"
    cmd: str = field(default="banner", init=False)


@dataclass(frozen=True)
class Clear:
    """Wipe all current overlay marks from the screen."""
    cmd: str = field(default="clear", init=False)


_BY_CMD = {klass.__dataclass_fields__["cmd"].default: klass
           for klass in (Highlight, Spotlight, Cursor, Ripple, Banner, Clear)}


def encode(command) -> str:
    """Serialise a command dataclass to one newline-terminated JSON line."""
    return json.dumps(asdict(command), ensure_ascii=False) + "\n"


def decode(line: str):
    """Parse one JSON line back into its command dataclass; raise if unknown."""
    data = json.loads(line)
    cmd = data.pop("cmd", None)
    klass = _BY_CMD.get(cmd)
    if klass is None:
        raise ValueError(f"unknown overlay command: {cmd!r}")
    return klass(**data)
