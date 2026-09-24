"""设置页的分块大小与合集上限应热重载并贯穿 Step 1 / Step 5（#123）。"""

import json
import os

from backend.utils.text_processor import TextProcessor


def _write_settings(path, chunk_size, max_clips):
    path.write_text(
        json.dumps(
            {
                "api": {"api_keys": {}, "api_model": "qwen-plus"},
                "processing": {
                    "processing_chunk_size": chunk_size,
                    "processing_max_clips": max_clips,
                },
            }
        ),
        encoding="utf-8",
    )


def test_pipeline_settings_reload_between_runs(monkeypatch, tmp_path):
    from backend.core import llm_manager as manager_module
    from backend.pipeline import step1_outline as step1
    from backend.pipeline import step5_clustering as step5

    monkeypatch.setattr(
        manager_module.config_sync_service, "is_sync_needed", lambda: False
    )
    settings_file = tmp_path / "settings.json"
    _write_settings(settings_file, 3000, 7)
    manager = manager_module.LLMManager(settings_file=settings_file)
    monkeypatch.setattr(manager_module, "get_llm_manager", lambda: manager)

    assert step1.resolve_chunk_size() == 3000
    assert step5.resolve_max_clips_per_collection() == 7

    _write_settings(settings_file, 4500, 9)
    mtime = settings_file.stat().st_mtime
    os.utime(settings_file, (mtime, mtime + 5))

    assert step1.resolve_chunk_size() == 4500
    assert step5.resolve_max_clips_per_collection() == 9


def test_invalid_pipeline_settings_use_defaults(monkeypatch):
    from backend.pipeline import step1_outline as step1
    from backend.pipeline import step5_clustering as step5

    values = {"chunk_size": "invalid", "max_clips_per_collection": 0}

    class FakeManager:
        def get_processing_setting(self, name):
            return values[name]

    from backend.core import llm_manager as manager_module

    monkeypatch.setattr(manager_module, "get_llm_manager", lambda: FakeManager())

    assert step1.resolve_chunk_size() == step1.CHUNK_SIZE
    assert step5.resolve_max_clips_per_collection() == step5.MAX_CLIPS_PER_COLLECTION


def test_srt_chunking_respects_character_limit_without_dropping_cues():
    entries = [
        {
            "start_time": "00:00:01,000",
            "end_time": "00:00:02,000",
            "text": "aaaaa",
            "index": 1,
        },
        {
            "start_time": "00:00:02,000",
            "end_time": "00:00:03,000",
            "text": "bbbbb",
            "index": 2,
        },
        {
            "start_time": "00:00:03,000",
            "end_time": "00:00:04,000",
            "text": "ccccc",
            "index": 3,
        },
        {
            "start_time": "00:00:04,000",
            "end_time": "00:00:05,000",
            "text": "ddddd",
            "index": 4,
        },
    ]

    chunks = TextProcessor().chunk_srt_data(entries, interval_minutes=30, max_chars=11)

    assert [[entry["index"] for entry in chunk["srt_entries"]] for chunk in chunks] == [
        [1, 2],
        [3, 4],
    ]
    assert all(len(chunk["text"]) <= 11 for chunk in chunks)
    assert [entry for chunk in chunks for entry in chunk["srt_entries"]] == entries

    oversized = TextProcessor().chunk_srt_data([entries[0]], max_chars=3)
    assert [entry["index"] for entry in oversized[0]["srt_entries"]] == [1]


def test_step1_passes_saved_chunk_size_to_srt_chunker(monkeypatch, tmp_path):
    from backend.pipeline import step1_outline as step1

    prompt_file = tmp_path / "outline.txt"
    prompt_file.write_text("提取大纲", encoding="utf-8")
    srt_file = tmp_path / "input.srt"
    srt_file.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nfirst\n\n"
        "2\n00:00:02,000 --> 00:00:03,000\nsecond\n",
        encoding="utf-8",
    )

    class FakeLLM:
        def call_with_retry(self, prompt, input_data=None, **kwargs):
            return "1. **Topic**\n- Detail"

    monkeypatch.setattr(step1, "LLMClient", FakeLLM)
    monkeypatch.setattr(step1, "resolve_chunk_size", lambda: 4321)
    extractor = step1.OutlineExtractor(
        metadata_dir=tmp_path / "metadata",
        prompt_files={"outline": prompt_file},
    )
    captured = {}

    def chunk_srt_data(data, interval_minutes, max_chars=None):
        captured["max_chars"] = max_chars
        return [
            {
                "chunk_index": 0,
                "text": " ".join(entry["text"] for entry in data),
                "start_time": data[0]["start_time"],
                "end_time": data[-1]["end_time"],
                "srt_entries": data,
            }
        ]

    monkeypatch.setattr(extractor.text_processor, "chunk_srt_data", chunk_srt_data)

    outlines = extractor.extract_outline(srt_file)

    assert captured["max_chars"] == 4321
    assert [outline["title"] for outline in outlines] == ["Topic"]


def test_step5_applies_collection_limit_to_all_fallback_paths(monkeypatch, tmp_path):
    from backend.pipeline import step5_clustering as step5

    prompt_file = tmp_path / "clustering.txt"
    prompt_file.write_text("聚类", encoding="utf-8")
    monkeypatch.setattr(step5, "LLMClient", lambda: object())
    monkeypatch.setattr(step5, "resolve_max_clips_per_collection", lambda: 3)
    engine = step5.ClusteringEngine(
        metadata_dir=tmp_path / "metadata",
        prompt_files={"clustering": prompt_file},
    )
    clips = [
        {
            "id": str(index),
            "outline": f"outline-{index}",
            "generated_title": f"title-{index}",
            "final_score": 0.9,
        }
        for index in range(6)
    ]

    validated = engine._validate_collections(
        [
            {
                "collection_title": "Collection",
                "collection_summary": "Summary",
                "clips": [clip["generated_title"] for clip in clips],
            }
        ],
        clips,
    )
    pre_clustered = engine._create_collections_from_pre_clusters(
        {"投资理财": [clip["id"] for clip in clips]},
        clips,
    )
    default = engine._create_default_collections(clips)

    assert validated[0]["clip_ids"] == ["0", "1", "2"]
    assert pre_clustered[0]["clip_ids"] == ["0", "1", "2"]
    assert default[0]["clip_ids"] == ["0", "1", "2"]


def test_step5_uses_saved_limit_in_llm_prompt_and_minimum(monkeypatch, tmp_path):
    from backend.pipeline import step5_clustering as step5

    prompt_file = tmp_path / "clustering.txt"
    prompt_file.write_text("聚类", encoding="utf-8")
    captured = {}

    class FakeLLM:
        def call_with_retry(self, prompt):
            captured["prompt"] = prompt
            return json.dumps(
                [
                    {
                        "collection_title": f"Collection-{index}",
                        "collection_summary": "Summary",
                        "clips": ["title-0", "title-1"],
                    }
                    for index in range(3)
                ]
            )

        def parse_json_response(self, response):
            return json.loads(response)

    monkeypatch.setattr(step5, "LLMClient", FakeLLM)
    monkeypatch.setattr(step5, "resolve_max_clips_per_collection", lambda: 1)
    engine = step5.ClusteringEngine(
        metadata_dir=tmp_path / "metadata",
        prompt_files={"clustering": prompt_file},
    )
    clips = [
        {
            "id": str(index),
            "outline": f"outline-{index}",
            "generated_title": f"title-{index}",
            "final_score": 0.9,
        }
        for index in range(2)
    ]

    collections = engine.cluster_clips(clips)

    assert "每个合集至少包含1条切片，最多包含1条切片" in captured["prompt"]
    assert len(collections) == 3
    assert all(collection["clip_ids"] == ["0"] for collection in collections)
