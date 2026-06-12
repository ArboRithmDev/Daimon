"""Tamper-evident append-only logs.

Two uses, same primitive:
  - the consent ledger (L4 engage/disengage) — the immutable proof of consent;
  - the session log (every destructive action authorized).

Each record carries prev_hash and hash = sha256(prev_hash + canonical_body).
Any edit to a past record breaks the chain, so verify() detects tampering.
Callers supply a "ts" field (kept injectable for deterministic tests).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_GENESIS = "0" * 64


class AppendOnlyLedger:
    def __init__(self, path) -> None:
        self.path = Path(path)

    def _records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _last_hash(self) -> str:
        records = self._records()
        return records[-1]["hash"] if records else _GENESIS

    @staticmethod
    def _compute(prev: str, body: dict) -> str:
        canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()

    def append(self, entry: dict) -> str:
        prev = self._last_hash()
        body = {**entry, "prev_hash": prev}
        h = self._compute(prev, body)
        record = {**body, "hash": h}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return h

    def verify(self) -> bool:
        prev = _GENESIS
        for record in self._records():
            stored = record.get("hash")
            body = {k: v for k, v in record.items() if k != "hash"}
            if body.get("prev_hash") != prev:
                return False
            if self._compute(prev, body) != stored:
                return False
            prev = stored
        return True
