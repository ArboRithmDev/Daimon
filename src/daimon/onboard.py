"""`python -m daimon.onboard` — guided permission onboarding (CLI, or --gui)."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--gui" in argv:
        from .setup.gui.__main__ import main as gui_main
        return gui_main()
    from .setup.onboard_flow import run_onboarding
    return run_onboarding()


if __name__ == "__main__":
    raise SystemExit(main())
