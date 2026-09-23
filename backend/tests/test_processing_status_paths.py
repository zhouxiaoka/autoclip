"""Processing-status path: project dirs must not depend on cwd, and expected HTTP errors stay expected."""

import asyncio
import logging
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from backend.api.v1.projects import get_processing_status
from backend.services.config_manager import ProjectConfigManager, resolve_project_directory


def _remove_cwd(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing-cwd"
    missing.mkdir()
    monkeypatch.chdir(missing)
    missing.rmdir()


def test_resolve_project_directory_uses_data_dir_when_cwd_is_gone(tmp_path, monkeypatch):
    data_dir = tmp_path / "desktop-data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(data_dir))
    _remove_cwd(monkeypatch, tmp_path)

    with pytest.raises(FileNotFoundError):
        Path("data/projects/project-1").mkdir(parents=True, exist_ok=True)

    project_dir = resolve_project_directory("project-1")

    assert project_dir == data_dir / "projects" / "project-1"
    assert project_dir.is_absolute()
    assert project_dir.is_dir()


def test_desktop_mode_uses_app_dir_without_explicit_data_dir(tmp_path, monkeypatch):
    app_dir = tmp_path / "Application Support" / "AutoClip"
    monkeypatch.delenv("AUTOCLIP_DATA_DIR", raising=False)
    monkeypatch.setenv("AUTOCLIP_DESKTOP_MODE", "1")
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(app_dir))
    _remove_cwd(monkeypatch, tmp_path)

    manager = ProjectConfigManager("clip-9")

    assert manager.project_dir == app_dir / "projects" / "clip-9"
    assert manager.config_path == manager.project_dir / "config.yaml"
    assert manager.project_dir.is_dir()


def test_absolute_directory_argument_is_unchanged(tmp_path):
    explicit = tmp_path / "explicit-project"
    manager = ProjectConfigManager(str(explicit))
    assert manager.project_dir == explicit
    assert explicit.is_dir()


def test_web_mode_stays_under_configured_data_dir_not_cwd(tmp_path, monkeypatch):
    data_dir = tmp_path / "docker-data"
    work = tmp_path / "somewhere-else"
    work.mkdir()
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(data_dir))
    monkeypatch.delenv("AUTOCLIP_DESKTOP_MODE", raising=False)
    monkeypatch.delenv("AUTOCLIP_MODE", raising=False)
    monkeypatch.chdir(work)

    project_dir = resolve_project_directory("web-project")

    assert project_dir == data_dir / "projects" / "web-project"
    assert work not in project_dir.parents


def test_status_404_is_not_rewritten(caplog):
    project_service = Mock()
    project_service.get.return_value = None
    processing_service = Mock()

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_processing_status("missing", project_service, processing_service))

    assert exc.value.status_code == 404
    processing_service.get_processing_status.assert_not_called()
    assert not any("获取处理状态失败" in record.message for record in caplog.records)


def test_status_unexpected_error_still_reports_and_returns_500(caplog):
    task = Mock()
    task.id = "task-1"
    task.created_at = 1
    project = Mock()
    project.tasks = [task]
    project_service = Mock()
    project_service.get.return_value = project
    processing_service = Mock()
    processing_service.get_processing_status.side_effect = RuntimeError("disk failed")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_processing_status("project-1", project_service, processing_service))

    assert exc.value.status_code == 500
    assert any("获取处理状态失败" in record.message for record in caplog.records)
    assert any(record.exc_info and record.exc_info[0] is RuntimeError for record in caplog.records)
