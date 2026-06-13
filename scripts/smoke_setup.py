"""Smoke script: print `daimon status` then a DRY-RUN of install.

Runs on the real Mac (no writes) to verify detection + invocation resolution.

Usage:
    python scripts/smoke_setup.py
"""
from __future__ import annotations

import sys
import os

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from daimon.setup.cli import run_command
from daimon.setup.clients.registry import default_adapters, detected
from daimon.setup.invocation import daimon_command


def main() -> None:
    # --- daimon status ---
    print("=== daimon status ===")
    run_command(["status"])
    print()

    # --- DRY-RUN of install (no writes) ---
    print("=== DRY-RUN: what `daimon install` would write ===")
    entry = daimon_command()
    adapters = detected(default_adapters())
    if not adapters:
        print("  (no AI clients detected)")
    for adapter in adapters:
        print(f"  {adapter.name}")
        print(f"    config_path : {adapter.config_path}")
        print(f"    entry       : {entry}")
    print()
    print("(Nothing was written — this is a dry run.)")


if __name__ == "__main__":
    main()
