"""Deploy Daimon into detected AI clients — shared by the tray and onboarding.

One place that resolves the daimon command, walks the detected clients, and
registers Daimon into each. Both the menu-bar tray and the onboarding window
call this so the "deploy" logic isn't duplicated across the two front-ends.

For Antigravity, registering the server is only half the job: each surface's
Security Manager also needs every tool explicitly whitelisted in its own
settings.json (see clients/base.install_agy_permissions). That step is wired in
here too, driven by the live server's tool list so it never drifts.
"""

from __future__ import annotations

from pathlib import Path

from .clients import base
from .clients.registry import (
    agy_permission_surfaces_for_home,
    default_adapters,
    detected,
)
from .invocation import daimon_command


def daimon_tool_names() -> list[str]:
    """The MCP tool names the live server exposes — single source of truth (no drift)."""
    import asyncio

    from daimon.server import build_server

    tools = asyncio.run(build_server().list_tools())
    return sorted(t.name for t in tools)


def install_agy_permissions_all(*, ts: str = "0", workspace=None,
                                tools=None, surfaces=None) -> list[base.Result]:
    """Whitelist every daimon tool in each *present* AGY surface's settings.json."""
    if surfaces is None:
        surfaces = agy_permission_surfaces_for_home(Path.home())
    present = [(label, path) for label, path, det in surfaces if Path(det).exists()]
    if not present:
        return []
    if tools is None:
        try:
            tools = daimon_tool_names()
        except Exception:
            return []
    return [base.install_agy_permissions(label, path, "daimon", tools,
                                         workspace=workspace, ts=ts)
            for label, path in present]


def uninstall_agy_permissions_all(*, ts: str = "0", surfaces=None) -> list[base.Result]:
    """Remove daimon's tool whitelist from each *present* AGY surface (reversible)."""
    if surfaces is None:
        surfaces = agy_permission_surfaces_for_home(Path.home())
    out = []
    for label, path, det in surfaces:
        if Path(det).exists():
            out.append(base.uninstall_agy_permissions(label, path, "daimon", ts=ts))
    return out


def install_all() -> list[base.Result]:
    """Register Daimon into every detected AI client + whitelist AGY tools."""
    entry = daimon_command()
    results = [base.install(a, "daimon", entry) for a in detected(default_adapters())]
    results += install_agy_permissions_all(workspace=Path.cwd())
    return results


def client_summary() -> tuple[int, int]:
    """(registered, detected) counts for a status line."""
    adapters = detected(default_adapters())
    registered = sum(1 for a in adapters if base.status(a, "daimon").action == "present")
    return registered, len(adapters)
