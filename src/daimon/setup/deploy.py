"""Deploy Daimon into detected AI clients — shared by the tray and onboarding.

One place that resolves the daimon command, walks the detected clients, and
registers Daimon into each. Both the menu-bar tray and the onboarding window
call this so the "deploy" logic isn't duplicated across the two front-ends.
"""

from __future__ import annotations

from .clients import base
from .clients.registry import default_adapters, detected
from .invocation import daimon_command


def install_all() -> list[base.Result]:
    """Register Daimon into every detected AI client. Returns per-client results."""
    entry = daimon_command()
    return [base.install(a, "daimon", entry) for a in detected(default_adapters())]


def client_summary() -> tuple[int, int]:
    """(registered, detected) counts for a status line."""
    adapters = detected(default_adapters())
    registered = sum(1 for a in adapters if base.status(a, "daimon").action == "present")
    return registered, len(adapters)
