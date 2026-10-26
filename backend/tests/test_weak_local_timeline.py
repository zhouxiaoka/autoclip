"""#428: say when a small local model cannot return a timeline. Do not make 7B succeed."""
import json
from types import SimpleNamespace

import pytest

from backend.core.result_retry import MAX_ATTEMPTS
from backend.core.weak_local_timeline import (
    WEAK_LOCAL_TIMELINE_MARKER,
    empty_interval_hint,
    is_known_weak_local_timeline_model,
)
from backend.pipeline.failures import timeline_failure_from_report
from backend.pipeline.step2_timeline import TimelineExtractor


WEAK_HINT = (
    "这个模型经常无法返回可用的时间线，自动重试已经用完。"
    "请改用云端模型，或更大、能返回结构化时间区间的模型。"
    "这一步尚未进入评分或最短时长筛选。"
)


@pytest.mark.parametrize(
    "provider,model,base_url,weak",
    [
        ("ollama", "qwen2.5:7b", "http://127.0.0.1:11434/v1", True),
        ("Ollama", "Qwen2.5-7B-Instruct", None, True),
        ("lmstudio", "llama3.1:8b", None, True),
        ("ollama", "qwen2.5:0.5b", None, True),
        ("ollama", "phi3:mini", None, True),
        ("ollama", "tinyllama", None, True),
        ("compatible", "qwen2.5:7b", "http://localhost:8000/v1", True),
        ("openai", "qwen2.5:7b", "http://192.168.1.8:11434/v1", True),
        ("ollama", "qwen2.5:14b", None, False),
        ("ollama", "qwen2.5:32b", None, False),
        ("ollama", "qwen2.5:72b", None, False),
        ("ollama", "nomic-embed-text", None, False),
        ("ollama", "", None, False),
        ("dashscope", "qwen2.5:7b", "https://dashscope.aliyuncs.com/compatible-mode/v1", False),
        ("openai", "gpt-4o-mini", "https://api.openai.com/v1", False),
        ("compatible", "qwen2.5:7b", "https://example.com/v1", False),
        ("ollama", "mixtral:8x7b", None, False),
    ],
)
def test_known_weak_local_timeline_models(provider, model, base_url, weak):
    assert is_known_weak_local_timeline_model(provider, model, base_url) is weak


def _chunks(outcome="invalid_response", attempts=MAX_ATTEMPTS, source="model", count=14):
    return [
        {"index": index, "topics": 1, "attempts": attempts, "outcome": outcome, "rejected": {"malformed_json": 1}, "source": source}
        for index in range(count)
    ]


def test_issue_428_weak_local_copy_says_retries_are_already_spent():
    failure = timeline_failure_from_report(82, {
        "chunks": _chunks(), "parsed": 0, "output": 0, "weak_local_timeline": True,
    })
    text = failure.user_message()
    assert failure.code == "invalid_response"
    assert text == f"时间线模型回复没有有效时间区间（82 个话题，14 个字幕块）。 {WEAK_HINT}"
    assert WEAK_LOCAL_TIMELINE_MARKER in text
    assert "自动重试已经用完" in text
    assert "请改用云端模型，或更大、能返回结构化时间区间的模型。" in text
    assert "本地模型需支持当前字幕长度" not in text
    assert "11434" not in text and "http" not in text


def test_weak_local_without_a_spent_budget_does_not_claim_retries_finished():
    failure = timeline_failure_from_report(2, {
        "chunks": _chunks(outcome="empty_response", attempts=1, count=1),
        "parsed": 0, "weak_local_timeline": True,
    })
    text = failure.user_message()
    assert WEAK_LOCAL_TIMELINE_MARKER in text
    assert "自动重试已经用完" not in text
    assert "请改用云端模型，或更大、能返回结构化时间区间的模型。" in text


def test_cache_replay_keeps_the_reimport_hint_even_for_a_weak_local_model():
    failure = timeline_failure_from_report(1, {
        "chunks": _chunks(attempts=1, source="cache", count=1),
        "parsed": 0, "weak_local_timeline": True,
    })
    text = failure.user_message()
    assert "本次回放了项目中的模型缓存" in text
    assert WEAK_LOCAL_TIMELINE_MARKER not in text


def test_cloud_empty_intervals_keep_the_generic_hint():
    failure = timeline_failure_from_report(82, {"chunks": _chunks(), "parsed": 0, "output": 0})
    assert empty_interval_hint({}, _chunks()).startswith("请换用能稳定返回结构化时间线的模型")
    assert "本地模型需支持当前字幕长度" in failure.user_message()
    assert WEAK_LOCAL_TIMELINE_MARKER not in failure.user_message()


def test_extractor_stamps_only_a_boolean_for_qwen25_7b(tmp_path):
    obj = TimelineExtractor.__new__(TimelineExtractor)
    obj.metadata_dir = tmp_path
    obj.llm_client = SimpleNamespace(get_current_provider_info=lambda: {
        "provider": "ollama", "model": "qwen2.5:7b", "base_url": "http://127.0.0.1:11434/v1",
    })
    assert obj.extract_timeline([]) == []
    assert obj.extraction_report["weak_local_timeline"] is True
    saved = (tmp_path / "quality_report.json").read_text(encoding="utf-8")
    assert json.loads(saved)["step2_extraction"]["weak_local_timeline"] is True
    assert "11434" not in saved and "qwen2.5:7b" not in saved


def test_extractor_does_not_stamp_a_larger_local_model_or_a_broken_lookup(tmp_path):
    larger = TimelineExtractor.__new__(TimelineExtractor)
    larger.metadata_dir = tmp_path / "large"
    larger.llm_client = SimpleNamespace(get_current_provider_info=lambda: {"provider": "ollama", "model": "qwen2.5:32b"})
    larger.extract_timeline([])
    assert "weak_local_timeline" not in larger.extraction_report

    broken = TimelineExtractor.__new__(TimelineExtractor)
    broken.metadata_dir = tmp_path / "broken"
    broken.llm_client = SimpleNamespace(get_current_provider_info=lambda: (_ for _ in ()).throw(RuntimeError("settings")))
    assert broken.extract_timeline([]) == []
    assert "weak_local_timeline" not in broken.extraction_report

    silent = TimelineExtractor.__new__(TimelineExtractor)
    silent.metadata_dir = tmp_path / "silent"
    silent.llm_client = SimpleNamespace()
    silent.extract_timeline([])
    assert "weak_local_timeline" not in silent.extraction_report
