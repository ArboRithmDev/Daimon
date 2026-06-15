import sys
from pathlib import Path

import pytest

from daimon import userdata


@pytest.mark.skipif(sys.platform == "win32",
                    reason="userdata path is platform-specific; %APPDATA% + test land in W4")
def test_default_is_application_support(monkeypatch):
    monkeypatch.delenv("DAIMON_DATA_DIR", raising=False)
    d = userdata.data_dir()
    assert str(d).endswith("Library/Application Support/Daimon")
    assert userdata.config_dir() == d / "config"
    assert userdata.logs_dir() == d / "logs"


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path / "dd"))
    assert userdata.data_dir() == tmp_path / "dd"
    assert userdata.config_dir() == tmp_path / "dd" / "config"
