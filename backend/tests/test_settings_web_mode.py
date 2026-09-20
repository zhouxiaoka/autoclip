"""
设置端点在非桌面模式（Docker / 本地脚本）下必须可用（issue #100）。

以前 GET/PUT /settings、/test-api、/current-provider 等都被 check_desktop_mode() 拦成 400，
Docker 用户只能改 .env。这里直接调用端点函数验证：读、写、热重载、环境变量回显都能走通。
"""

import asyncio
import json

import pytest
from fastapi import HTTPException

from backend.core.desktop_config import DesktopPaths


@pytest.fixture
def web_mode(monkeypatch, tmp_path):
    for name in (
        "AUTOCLIP_DESKTOP_MODE", "AUTOCLIP_MODE", "TAURI_PLATFORM",
        "LLM_PROVIDER", "API_MODEL_NAME", "LLM_MODEL", "OPENAI_BASE_URL",
        "API_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY", "API_OPENAI_API_KEY", "OPENAI_API_KEY",
        "API_GEMINI_API_KEY", "GEMINI_API_KEY", "API_SILICONFLOW_API_KEY", "SILICONFLOW_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    from backend.api.v1 import settings as settings_api
    from backend.core import llm_manager as manager_module

    config = settings_api.get_desktop_config()
    monkeypatch.setattr(config, "paths", DesktopPaths(
        data_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        temp_dir=tmp_path / "temp",
        database_url=f"sqlite:///{tmp_path / 'autoclip.db'}",
    ))

    # LLM 管理器读同一份 settings.json，且不碰真实用户目录
    monkeypatch.setattr(manager_module.config_sync_service, "is_sync_needed", lambda: False)
    manager = manager_module.LLMManager(settings_file=tmp_path / "settings.json")
    monkeypatch.setattr(manager_module, "get_llm_manager", lambda: manager)

    assert settings_api.is_desktop_mode() is False
    return settings_api, tmp_path, manager


def _payload(settings_api, **api_overrides):
    api = {
        "api_keys": {"dashscope": "", "openai": "", "gemini": "AIza-test-key-1234567890", "siliconflow": ""},
        "api_provider": "gemini",
        "api_model": "gemini-2.5-flash",
    }
    api.update(api_overrides)
    return settings_api.DesktopSettings(api=settings_api.ApiSettings(**api))


def test_desktop_only_endpoints_still_guarded(web_mode):
    settings_api, _, _ = web_mode
    with pytest.raises(HTTPException) as exc:
        settings_api.check_desktop_mode()
    assert exc.value.status_code == 400


def test_get_settings_works_without_desktop_mode(web_mode):
    settings_api, tmp_path, _ = web_mode

    settings = asyncio.run(settings_api.get_settings())

    assert settings.api.api_provider == "dashscope"
    assert settings.paths is not None
    assert settings.paths.data_directory == str(tmp_path)


def test_get_settings_reflects_env_config_before_first_save(web_mode, monkeypatch):
    """Docker 用户在 .env 里写了 LLM_PROVIDER=gemini，设置页首屏就该显示 Gemini，而不是通义千问"""
    settings_api, _, manager = web_mode
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("API_MODEL_NAME", "gemini-2.5-flash")
    manager.settings = manager._load_settings()

    settings = asyncio.run(settings_api.get_settings())

    assert settings.api.api_provider == "gemini"
    assert settings.api.api_model == "gemini-2.5-flash"


def test_update_then_get_roundtrip_and_manager_reload(web_mode):
    settings_api, tmp_path, manager = web_mode
    assert manager.get_current_provider_info()["provider"] == "dashscope"

    result = asyncio.run(settings_api.update_settings(_payload(settings_api)))

    assert result["settings_file"] == str(tmp_path / "settings.json")
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["api"]["api_provider"] == "gemini"
    assert saved["api"]["api_keys"]["gemini"] == "AIza-test-key-1234567890"

    reloaded = asyncio.run(settings_api.get_settings())
    assert reloaded.api.api_provider == "gemini"
    assert reloaded.api.api_model == "gemini-2.5-flash"

    # API 进程内的 LLM 管理器立刻切换；worker 进程靠 mtime 走同一条重载逻辑
    info = manager.get_current_provider_info()
    assert info["provider"] == "gemini"
    assert info["model"] == "gemini-2.5-flash"


def test_current_provider_endpoint_works_without_desktop_mode(web_mode):
    settings_api, _, _ = web_mode
    asyncio.run(settings_api.update_settings(_payload(settings_api)))

    info = asyncio.run(settings_api.get_current_provider())

    assert info["provider"] == "gemini"
    assert info["model"] == "gemini-2.5-flash"


def test_test_api_endpoint_no_longer_requires_desktop_mode(web_mode):
    settings_api, _, _ = web_mode
    request = settings_api.TestApiRequest(provider="gemini", api_key="short")

    # 走到了业务校验（key 过短），而不是被 400 拦在门外
    result = asyncio.run(settings_api.test_api_connection(request))

    assert result["success"] is False
    assert "过短" in result["error"]
