"""Build and run the permission onboarding wizard (front-end-agnostic)."""

from __future__ import annotations

from .permissions import permissions_status, Permission
from .wizard import IO, Step, Wizard


class ConsoleIO:
    def say(self, message: str) -> None:
        print(message)
    def wait(self, seconds: float) -> None:
        import time
        time.sleep(seconds)


def _step_for(backend, perm: Permission) -> Step:
    def act():
        if perm.key == "screen_recording":
            backend.request_screen_recording()
        else:
            backend.request_accessibility()
        backend.open_pane(perm.pane)
    def check():
        return {p.key: p.granted for p in permissions_status(backend)}[perm.key]
    return Step(id=perm.key, title=perm.label, check=check, act=act,
                guidance=f"{perm.how_to} Grant it in the window that opens, then I'll verify.")


def build_wizard(backend) -> Wizard:
    return Wizard([_step_for(backend, p) for p in permissions_status(backend)])


def run_onboarding(*, backend=None, io: IO | None = None, max_polls: int = 30) -> int:
    if backend is None:
        from .. import backends as _b
        backend = _b.build_permissions_backend()
    io = io or ConsoleIO()
    ok = build_wizard(backend).run(io, max_polls=max_polls)
    io.say("Daimon is ready." if ok else "Some permissions are still missing — re-run `daimon onboard`.")
    return 0 if ok else 1
