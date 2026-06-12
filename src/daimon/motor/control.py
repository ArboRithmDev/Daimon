"""Human, out-of-band control of the motor ceiling. NEVER an MCP tool.

Usage (typed by the human at a terminal):
    python -m daimon.motor.control status
    python -m daimon.motor.control engage      # prompts for the engagement phrase
    python -m daimon.motor.control disengage    # prompts for the disengagement phrase
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from .audit import AppendOnlyLedger
from .consent import ConsentManager
from .types import Level


def run_command(command: str, *, typed: str | None, config_ceiling: Level,
                engagement_phrase: str, disengagement_phrase: str,
                ledger_path, state_path) -> int:
    manager = ConsentManager(
        config_ceiling=config_ceiling,
        engagement_phrase=engagement_phrase,
        disengagement_phrase=disengagement_phrase,
        ledger=AppendOnlyLedger(ledger_path),
        state_path=state_path,
    )
    ts = datetime.now(timezone.utc).isoformat()

    if command == "status":
        print(f"Daimon motor ceiling: {manager.current_ceiling().name}")
        return 0
    if command == "engage":
        ok = manager.engage(typed or "", ts=ts)
        print("L4 ENGAGED." if ok else "Refused: phrase mismatch.")
        return 0 if ok else 1
    if command == "disengage":
        ok = manager.disengage(typed or "", ts=ts)
        print("L4 disengaged." if ok else "Refused: phrase mismatch.")
        return 0 if ok else 1
    print(f"Unknown command: {command}")
    return 2


def main(argv: list[str] | None = None) -> int:
    from ..config import load_motor_config
    from .factory import _LOGS, _STATE

    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: python -m daimon.motor.control [status|engage|disengage]")
        return 2
    command = argv[0]
    mcfg = load_motor_config()
    typed = None
    if command in {"engage", "disengage"}:
        typed = input("Type the phrase to confirm: ")
    _LOGS.mkdir(exist_ok=True)
    return run_command(
        command, typed=typed,
        config_ceiling=mcfg.ceiling,
        engagement_phrase=mcfg.engagement_phrase,
        disengagement_phrase=mcfg.disengagement_phrase,
        ledger_path=_LOGS / "consent.jsonl",
        state_path=_STATE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
