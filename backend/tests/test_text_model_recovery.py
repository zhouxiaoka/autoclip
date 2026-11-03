"""A retired analysis model is substituted once on the real text call path.

Outline extraction goes through ``LLMManager.call_with_retry``. The saved id
can come from the settings document or from ``API_MODEL_NAME``. Nothing here
contacts a provider or writes the substitute back to settings.
"""
import json
import logging
from types import SimpleNamespace

import pytest

from backend.core.model_recovery import clear_remembered_models, remembered_model
from backend.core.provider_model_fetch import AccountModelList
from backend.services import ai_model_settings as ai


SECRET = "sk-live-secret-should-never-leak"
DEAD = "chatgpt-4o-latest"
ALT = "qwen3.8-flash"
LIVE = [
    "gpt-5-search-api",
    "omni-moderation-latest",
    "chatgpt-4o-latest",
    "other-chat",
    "qwen3.8-flash",
    "gemini-3.8-flash",
    "deepseek-v4-flash",
    "text-embedding-3-large",
]


class _Missing(Exception):
    def __init__(self):
        super().__init__("DeploymentNotFound")
        self.status_code = 404
        self.body = {"error": {"code": "DeploymentNotFound", "message": "DeploymentNotFound"}}


class _BadKey(Exception):
    def __init__(self):
        super().__init__("invalid api key")
        self.status_code = 401
        self.body = {"error": {"code": "invalid_api_key", "message": "Incorrect API key provided"}}


def _completion(text):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice], usage=None)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    monkeypatch.delenv("API_MODEL_NAME", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(ai, "migrate_legacy", lambda: ai.ModelSettings())
    clear_remembered_models()
    yield
    clear_remembered_models()


def _save_dead_analysis():
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(
            id="c1", name="APIMart", provider="apimart", api_key=SECRET, validation_status="ok",
        )],
        analysis=ai.Assignment(connection_id="c1", model=DEAD),
        analysis_mode="subtitle",
        allow_visual_screening=False,
    ))


def _manager(tmp_path):
    from backend.core.llm_manager import LLMManager
    return LLMManager(settings_file=tmp_path / "settings.json")


def _install(manager, reply, listed):
    sent = []

    def create(**params):
        sent.append(dict(params))
        model = params.get("model")
        if reply == "bad-key":
            raise _BadKey()
        if reply == "always-missing" or model == DEAD:
            raise _Missing()
        return _completion("三片")

    manager.current_provider.client.chat.completions.create = create

    def fake_list(**kwargs):
        listed["n"] += 1
        listed["provider"] = kwargs.get("provider")
        listed["base"] = kwargs.get("base_url")
        listed["key"] = kwargs.get("api_key")
        return AccountModelList(ok=True, models=list(LIVE))

    return sent, fake_list


def _capture(monkeypatch):
    from backend.core import llm_emit
    events = []
    original = llm_emit.request_finished

    def wrapped(**kwargs):
        props = original(**kwargs)
        events.append(props)
        return props

    monkeypatch.setattr(llm_emit, "request_finished", wrapped)
    return events


def test_saved_dead_analysis_model_retries_once_through_call_with_retry(tmp_path, monkeypatch, caplog):
    _save_dead_analysis()
    manager = _manager(tmp_path)
    listed = {"n": 0}
    sent, fake_list = _install(manager, "missing-once", listed)
    monkeypatch.setattr("backend.core.provider_model_fetch.list_account_models", fake_list)
    events = _capture(monkeypatch)

    with caplog.at_level(logging.INFO):
        assert manager.call_with_retry("提取大纲", {"rows": "1"}) == "三片"
        assert manager.call_with_retry("提取大纲", {"rows": "2"}) == "三片"

    assert [item["model"] for item in sent] == [DEAD, ALT, ALT]
    assert all(item.get("stream") is True for item in sent)
    assert listed["n"] == 1
    assert listed["provider"] == "apimart"
    assert listed["key"] == SECRET
    assert remembered_model("apimart", listed["base"], SECRET, DEAD) == ALT
    assert manager.settings["model_name"] == DEAD
    assert manager.current_provider.model_name == DEAD
    assert ai.load().analysis.model == DEAD
    blob = caplog.text + json.dumps(events, ensure_ascii=False)
    assert SECRET not in blob
    assert "DeploymentNotFound" not in json.dumps(events, ensure_ascii=False)
    failed = [item for item in events if item.get("outcome") == "error"]
    succeeded = [item for item in events if item.get("outcome") == "success"]
    assert [item.get("model") for item in failed] == [DEAD]
    assert failed[0]["upstream_error_type"] == "model_not_found"
    assert failed[0].get("retry_count", 0) == 0
    # The substitute request counts one retry. The later reuse does not 404 again.
    assert [item.get("model") for item in succeeded] == [ALT, ALT]
    assert succeeded[0]["retry_count"] == 1
    assert succeeded[1].get("retry_count", 0) == 0
    notice = ai.public(ai.load())["model_substitutions"]
    assert notice == [{"purpose": "analysis", "saved_model": DEAD, "replacement": ALT}]
    assert SECRET not in json.dumps(notice)


def test_api_model_name_uses_the_same_analysis_substitute(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "apimart")
    monkeypatch.setenv("API_APIMART_API_KEY", SECRET)
    monkeypatch.setenv("API_MODEL_NAME", DEAD)
    assert ai.load() is None
    manager = _manager(tmp_path)
    assert manager.settings["model_name"] == DEAD
    assert manager.get_current_provider_info()["provider"] == "apimart"
    listed = {"n": 0}
    sent, fake_list = _install(manager, "missing-once", listed)
    monkeypatch.setattr("backend.core.provider_model_fetch.list_account_models", fake_list)

    with caplog.at_level(logging.INFO):
        assert manager.call_with_retry("提取大纲") == "三片"

    # other-chat is earlier on the live list. Analysis candidates still win.
    assert [item["model"] for item in sent] == [DEAD, ALT]
    assert listed["provider"] == "apimart"
    assert SECRET not in caplog.text
    assert manager.settings["model_name"] == DEAD


def test_a_second_missing_analysis_model_is_not_remembered(tmp_path, monkeypatch):
    _save_dead_analysis()
    manager = _manager(tmp_path)
    listed = {"n": 0}
    sent, fake_list = _install(manager, "always-missing", listed)
    monkeypatch.setattr("backend.core.provider_model_fetch.list_account_models", fake_list)

    with pytest.raises(Exception):
        manager.call_with_retry("提取大纲")

    assert [item["model"] for item in sent] == [DEAD, ALT]
    assert listed["n"] == 1
    assert remembered_model("apimart", listed["base"], SECRET, DEAD) is None


def test_other_text_errors_do_not_fetch_a_substitute(tmp_path, monkeypatch, caplog):
    _save_dead_analysis()
    manager = _manager(tmp_path)
    listed = {"n": 0}
    sent, fake_list = _install(manager, "bad-key", listed)
    monkeypatch.setattr("backend.core.provider_model_fetch.list_account_models", fake_list)

    with caplog.at_level(logging.INFO):
        with pytest.raises(Exception) as caught:
            manager.call_with_retry("提取大纲")

    assert [item["model"] for item in sent] == [DEAD]
    assert listed["n"] == 0
    exposed = str(caught.value) + caplog.text
    assert SECRET not in exposed
