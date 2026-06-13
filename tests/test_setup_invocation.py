# tests/test_setup_invocation.py
from pathlib import Path

from daimon.setup import invocation


def _no_bundle(monkeypatch):
    monkeypatch.setattr(invocation, "_BUNDLE_DAIMON", Path("/nonexistent/Daimon.app/x"))


def test_uses_console_script_when_present(monkeypatch):
    _no_bundle(monkeypatch)
    monkeypatch.setattr(invocation.shutil, "which", lambda n: "/usr/local/bin/daimon")
    entry = invocation.daimon_command()
    assert entry["command"] == "/usr/local/bin/daimon"
    assert entry["args"] == []
    assert entry["env"] == {}


def test_falls_back_to_python_module(monkeypatch):
    _no_bundle(monkeypatch)
    monkeypatch.setattr(invocation.shutil, "which", lambda n: None)
    monkeypatch.setattr(invocation.sys, "executable", "/opt/py/bin/python3.12")
    entry = invocation.daimon_command()
    assert entry["command"] == "/opt/py/bin/python3.12"
    assert entry["args"] == ["-m", "daimon"]


def test_prefers_bundled_binary_when_installed(tmp_path, monkeypatch):
    bundled = tmp_path / "Daimon.app" / "Contents" / "MacOS" / "daimon"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("#!/bin/sh\n")
    monkeypatch.setattr(invocation, "_BUNDLE_DAIMON", bundled)
    monkeypatch.setattr(invocation.shutil, "which", lambda n: "/usr/local/bin/daimon")
    entry = invocation.daimon_command()
    assert entry["command"] == str(bundled)  # bundle wins over console script
