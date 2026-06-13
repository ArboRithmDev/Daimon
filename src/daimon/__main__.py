"""Entrypoint: `python -m daimon` (MCP server) or `daimon <subcommand>` (setup).

No-arg keeps the long-standing behaviour MCP clients rely on: start the stdio
server. A known subcommand routes to the setup CLI instead."""

from __future__ import annotations

import sys

_SUBCOMMANDS = {"setup", "install", "uninstall", "status", "onboard"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in _SUBCOMMANDS:
        from .setup.cli import run_command
        rc = run_command(argv)
        return rc if isinstance(rc, int) else 0
    from .server import main as server_main
    server_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
