"""L4 engagement state machine.

L4 (full autonomy) is unlocked only by a human typing the exact engagement
phrase in the control CLI (out-of-band, never an MCP tool). Each engage/
disengage is recorded in the immutable consent ledger. The active flag lives in
a small state file so the human control process and the MCP server process agree
on the ceiling without sharing memory. Killing the server or deleting the state
file is the always-available physical override.
"""

from __future__ import annotations

import json
from pathlib import Path

from .audit import AppendOnlyLedger
from .types import Level


class ConsentManager:
    def __init__(
        self,
        config_ceiling: Level,
        engagement_phrase: str,
        disengagement_phrase: str,
        ledger: AppendOnlyLedger,
        state_path,
    ) -> None:
        self._config_ceiling = config_ceiling
        self._engagement_phrase = engagement_phrase
        self._disengagement_phrase = disengagement_phrase
        self._ledger = ledger
        self._state_path = Path(state_path)

    def _engaged(self) -> bool:
        if not self._state_path.exists():
            return False
        try:
            return bool(json.loads(self._state_path.read_text(encoding="utf-8")).get("engaged"))
        except (ValueError, OSError):
            return False

    def current_ceiling(self) -> Level:
        return Level.AUTONOMOUS if self._engaged() else self._config_ceiling

    def engage(self, typed: str, *, ts: str) -> bool:
        if typed.strip() != self._engagement_phrase:
            return False
        self._ledger.append({"event": "engage_l4", "ts": ts, "phrase": typed.strip()})
        self._state_path.write_text(json.dumps({"engaged": True, "ts": ts}), encoding="utf-8")
        return True

    def disengage(self, typed: str, *, ts: str) -> bool:
        if typed.strip() != self._disengagement_phrase:
            return False
        self._ledger.append({"event": "disengage_l4", "ts": ts})
        self._state_path.write_text(json.dumps({"engaged": False, "ts": ts}), encoding="utf-8")
        return True
