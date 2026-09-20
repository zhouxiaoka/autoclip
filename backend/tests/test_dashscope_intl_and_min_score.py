"""
#45 通义千问国际站 + 设置页「最低评分阈值」真正接到 step3。
"""

import json
import sys
import types

import pytest

from backend.core.llm_providers import (
    DASHSCOPE_CN_COMPATIBLE_BASE_URL,
    DASHSCOPE_INTL_COMPATIBLE_BASE_URL,
    DashScopeProvider,
)


@pytest.fixture
def fake_dashscope_sdk(monkeypatch):
    module = types.ModuleType("dashscope")
    module.Generation = types.SimpleNamespace(call=lambda **kw: None)
    monkeypatch.setitem(sys.modules, "dashscope", module)
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    monkeypatch.delenv("DASHSCOPE_MODE", raising=False)


def test_dashscope_defaults_to_native_cn(fake_dashscope_sdk):
    p = DashScopeProvider(api_key="sk-cn-1234567890")
    assert p.mode == "native"
    assert p.base_url == DASHSCOPE_CN_COMPATIBLE_BASE_URL
    assert p.is_international is False


def test_dashscope_intl_base_url_switches_to_compatible_mode(fake_dashscope_sdk):
    p = DashScopeProvider(api_key="sk-intl-1234567890", base_url=DASHSCOPE_INTL_COMPATIBLE_BASE_URL + "/")
    assert p.mode == "compatible"
    assert p.base_url == DASHSCOPE_INTL_COMPATIBLE_BASE_URL
    assert p.is_international is True


def test_dashscope_env_base_url_for_docker(fake_dashscope_sdk, monkeypatch):
    monkeypatch.setenv("DASHSCOPE_BASE_URL", DASHSCOPE_INTL_COMPATIBLE_BASE_URL)
    p = DashScopeProvider(api_key="sk-intl-1234567890")
    assert p.mode == "compatible" and p.is_international


def test_dashscope_compatible_call_hits_intl_endpoint(fake_dashscope_sdk, monkeypatch):
    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, payload=json)
        return _Resp()

    monkeypatch.setitem(sys.modules, "requests", types.SimpleNamespace(post=fake_post))
    p = DashScopeProvider(api_key="sk-intl-1234567890", model_name="qwen-plus", base_url=DASHSCOPE_INTL_COMPATIBLE_BASE_URL)

    resp = p.call("hi")

    assert resp.content == "ok"
    assert captured["url"] == DASHSCOPE_INTL_COMPATIBLE_BASE_URL + "/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-intl-1234567890"
    assert captured["payload"]["model"] == "qwen-plus"


# ------------------------------------------------------------ llm_manager ---

def _write(path, api=None, processing=None):
    data = {"api": {"api_keys": {"dashscope": "sk-1234567890ab", "openai": "", "gemini": "", "siliconflow": ""},
                    "api_model": "qwen-plus", **(api or {})}}
    if processing is not None:
        data["processing"] = processing
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def manager_env(monkeypatch, tmp_path, fake_dashscope_sdk):
    for name in ("LLM_PROVIDER", "API_MODEL_NAME", "OPENAI_BASE_URL", "API_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    from backend.core import llm_manager as m
    monkeypatch.setattr(m.config_sync_service, "is_sync_needed", lambda: False)
    return tmp_path / "settings.json"


def test_manager_routes_dashscope_intl_via_api_base_url(manager_env):
    from backend.core.llm_manager import LLMManager

    _write(manager_env, api={"api_provider": "dashscope", "api_base_url": DASHSCOPE_INTL_COMPATIBLE_BASE_URL})
    mgr = LLMManager(settings_file=manager_env)

    assert mgr.settings["dashscope_base_url"] == DASHSCOPE_INTL_COMPATIBLE_BASE_URL
    assert mgr.settings["openai_base_url"] == ""  # 不会串到 openai 那边
    assert mgr.current_provider.mode == "compatible"
    assert mgr.get_current_provider_info()["base_url"] == DASHSCOPE_INTL_COMPATIBLE_BASE_URL


def test_manager_openai_base_url_env_does_not_leak_into_dashscope(manager_env, monkeypatch):
    """Docker .env 里留着 OPENAI_BASE_URL 但 provider 是 dashscope：不能把通义切成兼容模式打别人的地址"""
    from backend.core.llm_manager import LLMManager

    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    _write(manager_env, api={"api_provider": "dashscope"})
    mgr = LLMManager(settings_file=manager_env)

    assert mgr.current_provider.mode == "native"
    assert "base_url" not in mgr.get_current_provider_info()


def test_manager_reads_processing_settings_from_settings_json(manager_env):
    from backend.core.llm_manager import LLMManager

    _write(manager_env, api={"api_provider": "dashscope"}, processing={"processing_min_score": 0.55, "processing_chunk_size": 3000})
    mgr = LLMManager(settings_file=manager_env)

    assert mgr.get_processing_setting("min_score_threshold") == 0.55
    assert mgr.get_processing_setting("chunk_size") == 3000
    assert mgr.get_processing_setting("max_clips_per_collection") == 5  # 未写时保留默认


# ------------------------------------------------------------------ step3 ---

def test_step3_threshold_priority(monkeypatch, manager_env):
    from backend.core import llm_manager as m
    from backend.pipeline import step3_scoring as step3

    _write(manager_env, api={"api_provider": "dashscope"}, processing={"processing_min_score": 0.6})
    mgr = m.LLMManager(settings_file=manager_env)
    monkeypatch.setattr(m, "get_llm_manager", lambda: mgr)
    monkeypatch.setattr(step3, "MIN_SCORE_OVERRIDE", None)

    assert step3.resolve_min_score_threshold() == 0.6          # 设置页的值

    monkeypatch.setattr(step3, "MIN_SCORE_OVERRIDE", 0.35)
    assert step3.resolve_min_score_threshold() == 0.35         # CLI 显式覆盖优先

    monkeypatch.setattr(step3, "MIN_SCORE_OVERRIDE", None)
    _write(manager_env, api={"api_provider": "dashscope"}, processing={"processing_min_score": 7})
    import os
    os.utime(manager_env, (manager_env.stat().st_atime, manager_env.stat().st_mtime + 5))
    assert step3.resolve_min_score_threshold() == step3.MIN_SCORE_THRESHOLD  # 非法值退回默认
