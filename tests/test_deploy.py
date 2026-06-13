import json

from daimon.setup import deploy
from daimon.setup.clients.base import ClientAdapter


def _adapters(tmp_path):
    a = ClientAdapter("Alpha", tmp_path / "a.json")
    b = ClientAdapter("Beta", tmp_path / "b.json")
    a.config_path.write_text("{}")  # detected
    b.config_path.write_text("{}")
    return [a, b]


def test_install_all_registers_each_detected(tmp_path, monkeypatch):
    adapters = _adapters(tmp_path)
    monkeypatch.setattr(deploy, "default_adapters", lambda: adapters)
    monkeypatch.setattr(deploy, "detected", lambda a: a)
    results = deploy.install_all()
    assert {r.action for r in results} == {"installed"}
    assert "daimon" in json.loads((tmp_path / "a.json").read_text())["mcpServers"]
    assert "daimon" in json.loads((tmp_path / "b.json").read_text())["mcpServers"]


def test_client_summary_counts(tmp_path, monkeypatch):
    adapters = _adapters(tmp_path)
    monkeypatch.setattr(deploy, "default_adapters", lambda: adapters)
    monkeypatch.setattr(deploy, "detected", lambda a: a)
    assert deploy.client_summary() == (0, 2)
    deploy.install_all()
    assert deploy.client_summary() == (2, 2)
