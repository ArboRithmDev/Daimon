import sys
from pathlib import Path

from daimon import userdata


def test_default_data_dir_is_os_appropriate(monkeypatch):
    monkeypatch.delenv("DAIMON_DATA_DIR", raising=False)
    d = userdata.data_dir()
    if sys.platform == "win32":
        assert d.name == "Daimon" and "Roaming" in str(d)
    elif sys.platform == "darwin":
        assert str(d).replace("\\", "/").endswith("Library/Application Support/Daimon")
    else:
        assert d.name == "Daimon"
    assert userdata.config_dir() == d / "config"
    assert userdata.logs_dir() == d / "logs"


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path / "dd"))
    assert userdata.data_dir() == tmp_path / "dd"
    assert userdata.config_dir() == tmp_path / "dd" / "config"
