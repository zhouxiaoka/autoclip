from backend.core import path_utils


def test_is_desktop_mode_from_desktop_flag(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DESKTOP_MODE", "TrUe")
    monkeypatch.delenv("AUTOCLIP_MODE", raising=False)
    assert path_utils.is_desktop_mode() is True


def test_is_desktop_mode_from_mode_flag(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_DESKTOP_MODE", raising=False)
    monkeypatch.setenv("AUTOCLIP_MODE", "desktop")
    assert path_utils.is_desktop_mode() is True


def test_get_data_directory_prefers_explicit_env(monkeypatch, tmp_path):
    custom_data = tmp_path / "custom-data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(custom_data))
    result = path_utils.get_data_directory()
    assert result == custom_data
    assert result.exists()


def test_get_data_directory_in_desktop_mode(monkeypatch, tmp_path):
    app_dir = tmp_path / "desktop-app-dir"
    monkeypatch.delenv("AUTOCLIP_DATA_DIR", raising=False)
    monkeypatch.setenv("AUTOCLIP_DESKTOP_MODE", "1")
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(app_dir))

    result = path_utils.get_data_directory()
    assert result == app_dir
    assert result.exists()


def test_get_log_file_path_respects_explicit_log_file(monkeypatch, tmp_path):
    log_file = tmp_path / "logs" / "custom.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))
    result = path_utils.get_log_file_path()
    assert result == log_file
    assert result.parent.exists()


def test_get_log_file_path_uses_data_logs_in_desktop_mode(monkeypatch, tmp_path):
    app_dir = tmp_path / "desktop-dir"
    monkeypatch.delenv("LOG_FILE", raising=False)
    monkeypatch.setenv("AUTOCLIP_DESKTOP_MODE", "yes")
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(app_dir))
    monkeypatch.delenv("AUTOCLIP_DATA_DIR", raising=False)

    result = path_utils.get_log_file_path()
    assert result == app_dir / "logs" / "backend.log"
    assert result.parent.exists()
