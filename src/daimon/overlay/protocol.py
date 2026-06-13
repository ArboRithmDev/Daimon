"""Pure overlay command protocol — dataclasses ↔ newline-delimited JSON.

No macOS imports: the same commands are produced on the MCP-server side and
consumed in the overlay process. One JSON object per line; `cmd` tags the type.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Highlight:
    x: int; y: int; w: int; h: int
    label: str = ""
    style: str = "default"   # default|L1|L2|L3|gate
    cmd: str = field(default="highlight", init=False)


@dataclass(frozen=True)
class Spotlight:
    x: int; y: int; w: int; h: int
    cmd: str = field(default="spotlight", init=False)


@dataclass(frozen=True)
class Cursor:
    x: int; y: int
    cmd: str = field(default="cursor", init=False)


@dataclass(frozen=True)
class Ripple:
    x: int; y: int
    cmd: str = field(default="ripple", init=False)


@dataclass(frozen=True)
class Banner:
    text: str
    level: str = "L1"
    cmd: str = field(default="banner", init=False)


@dataclass(frozen=True)
class Clear:
    cmd: str = field(default="clear", init=False)


_BY_CMD = {klass.__dataclass_fields__["cmd"].default: klass
           for klass in (Highlight, Spotlight, Cursor, Ripple, Banner, Clear)}


def encode(command) -> str:
    return json.dumps(asdict(command), ensure_ascii=False) + "\n"


def decode(line: str):
    data = json.loads(line)
    cmd = data.pop("cmd", None)
    klass = _BY_CMD.get(cmd)
    if klass is None:
        raise ValueError(f"unknown overlay command: {cmd!r}")
    return klass(**data)
