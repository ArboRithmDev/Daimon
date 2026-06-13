# tests/test_setup_invocation.py
from daimon.setup import invocation


def test_uses_console_script_when_present(monkeypatch):
    monkeypatch.setattr(invocation.shutil, "which", lambda n: "/usr/local/bin/daimon")
    entry = invocation.daimon_command()
    assert entry["command"] == "/usr/local/bin/daimon"
    assert entry["args"] == []
    assert entry["env"] == {}


def test_falls_back_to_python_module(monkeypatch):
    monkeypatch.setattr(invocation.shutil, "which", lambda n: None)
    monkeypatch.setattr(invocation.sys, "executable", "/opt/py/bin/python3.12")
    entry = invocation.daimon_command()
    assert entry["command"] == "/opt/py/bin/python3.12"
    assert entry["args"] == ["-m", "daimon"]
