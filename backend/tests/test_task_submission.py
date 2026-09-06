"""
回归测试：docker-compose 路径上的任务提交与 LLM 输入构建（issue #88 / #53）
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.core.llm_providers import LLMProvider
from backend.utils import task_submission_utils


class _RedisDown:
    """模拟 Redis 不可达的 redis 模块。"""

    class Redis:
        @staticmethod
        def from_url(*_args, **_kwargs):
            raise ConnectionError("Error 111 connecting to localhost:6379. Connection refused.")


@pytest.fixture
def server_mode(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_DESKTOP_MODE", raising=False)
    monkeypatch.delenv("AUTOCLIP_MODE", raising=False)


def test_submit_pipeline_succeeds_even_if_queue_depth_probe_fails(server_mode, monkeypatch):
    """诊断用的队列深度读取失败，不能让已经 send_task 成功的项目被标记为失败。"""
    monkeypatch.setitem(__import__("sys").modules, "redis", _RedisDown)

    with patch.object(
        task_submission_utils.celery_app,
        "send_task",
        return_value=SimpleNamespace(id="task-123", state="PENDING"),
    ) as send_task:
        result = task_submission_utils.submit_video_pipeline_task("proj", "/v.mp4", "/v.srt")

    send_task.assert_called_once()
    assert result["success"] is True
    assert result["task_id"] == "task-123"


def test_queue_depth_probe_uses_redis_url(server_mode, monkeypatch):
    """队列深度探测必须走 REDIS_URL，而不是硬编码 localhost。"""
    seen = {}

    class _FakeRedis:
        @staticmethod
        def from_url(url, **_kwargs):
            seen["url"] = url
            return SimpleNamespace(llen=lambda _q: 7)

    monkeypatch.setitem(__import__("sys").modules, "redis", SimpleNamespace(Redis=_FakeRedis))
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")

    assert task_submission_utils._log_queue_depth("processing") == 7
    assert seen["url"] == "redis://redis:6379/0"


def test_submit_pipeline_reports_failure_when_broker_rejects(server_mode):
    with patch.object(
        task_submission_utils.celery_app,
        "send_task",
        side_effect=ConnectionError("broker down"),
    ):
        result = task_submission_utils.submit_video_pipeline_task("proj", "/v.mp4", "/v.srt")

    assert result["success"] is False
    assert "broker down" in result["error"]


class _StubProvider(LLMProvider):
    def call(self, prompt, input_data=None, **kwargs):  # pragma: no cover - not used
        raise NotImplementedError

    def get_available_models(self):  # pragma: no cover - not used
        return []

    def test_connection(self):  # pragma: no cover - not used
        return True


@pytest.mark.parametrize(
    "input_data",
    [
        {"a": 1, "b": "中文"},
        [{"id": 1, "text": "第一段"}, {"id": 2, "text": "第二段"}],
        ("x", "y"),
    ],
)
def test_build_full_input_serialises_containers_as_json(input_data):
    provider = _StubProvider(api_key="k", model_name="m")
    full = provider._build_full_input("PROMPT", input_data)

    assert full.startswith("PROMPT\n\n输入内容：\n")
    payload = full.split("输入内容：\n", 1)[1]
    assert json.loads(payload) == json.loads(json.dumps(input_data))
    assert "中文" in full or "第一段" in full or "x" in full


def test_build_full_input_passes_strings_through():
    provider = _StubProvider(api_key="k", model_name="m")
    assert provider._build_full_input("PROMPT", "raw text") == "PROMPT\n\n输入内容：\nraw text"
    assert provider._build_full_input("PROMPT", None) == "PROMPT"
