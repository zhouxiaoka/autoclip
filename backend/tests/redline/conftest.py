"""Offline red-line tests never use a developer's settings or telemetry."""
import socket

import pytest


@pytest.fixture(autouse=True)
def redline_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILE", str(tmp_path / "redline.log"))
    (tmp_path / "privacy.json").write_text(
        '{"analytics":false,"crash_reports":false}', encoding="utf-8")

    def offline(*args, **kwargs):
        raise AssertionError("red-line tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket.socket, "connect_ex", offline)
