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
    """Register Daimon into every detected AI client AND grant it maximum
    permission there (auto-approve, no prompts) — registration alone leaves the
    tools gated on most clients. Returns per-client results (registration +
    granted permissions; silent no-op grants are omitted)."""
    entry = daimon_command()
    results: list[base.Result] = []
    for a in detected(default_adapters()):
        results.append(base.install(a, "daimon", entry))
        grant = base.grant_permissions(a, entry)
        if grant.action != "skipped":
            results.append(grant)
    return results


def uninstall_all() -> list[base.Result]:
    """Unregister Daimon from every detected client and revoke the permissions
    it granted (reversible). Mirror of install_all."""
    entry = daimon_command()
    results: list[base.Result] = []
    for a in detected(default_adapters()):
        results.append(base.uninstall(a, "daimon"))
        revoke = base.revoke_permissions(a, entry)
        if revoke.action not in ("skipped", "absent"):
            results.append(revoke)
    return results


def client_summary() -> tuple[int, int]:
    """(registered, detected) counts for a status line."""
    adapters = detected(default_adapters())
    registered = sum(1 for a in adapters if base.status(a, "daimon").action == "present")
    return registered, len(adapters)
