"""Pure onboarding wizard engine: ordered steps with check()/act()/verify, over
an injected IO so both the CLI and GUI front-ends reuse one logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class Step:
    """One onboarding step: check() is satisfied, else act() then re-poll."""
    id: str
    title: str
    check: Callable[[], bool]
    act: Callable[[], None]
    guidance: str = ""


class IO(Protocol):
    """Front-end output channel: a line emitter plus a blocking wait."""
    def say(self, message: str) -> None: ...
    def wait(self, seconds: float) -> None: ...


class RecordingIO:
    """Test IO: records lines, wait() is a no-op."""
    def __init__(self): self.lines: list[str] = []
    def say(self, message: str) -> None: self.lines.append(message)
    def wait(self, seconds: float) -> None: pass


class Wizard:
    """Runs an ordered list of steps over an injected IO; front-end-agnostic."""
    def __init__(self, steps: list[Step]) -> None:
        self._steps = steps

    def run(self, io: IO, *, max_polls: int = 30, poll_seconds: float = 1.0) -> bool:
        """Run each step, polling check() after act(); True if all satisfied."""
        all_ok = True
        for step in self._steps:
            io.say(f"STEP {step.title}")
            if step.check():
                io.say(f"OK {step.title}")
                continue
            if step.guidance:
                io.say(step.guidance)
            step.act()
            satisfied = False
            for _ in range(max_polls):
                if step.check():
                    satisfied = True
                    break
                io.wait(poll_seconds)
            io.say(("OK " if satisfied else "PENDING ") + step.title)
            all_ok = all_ok and satisfied
        return all_ok
