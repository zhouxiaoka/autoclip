"""Behavioral acceptance for runtime recovery and processing settings (#123)."""
import importlib
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from backend.services import whisper_runtime
from backend.pipeline.step1_outline import OutlineExtractor
from backend.pipeline.step5_clustering import ClusteringEngine
from backend.utils.text_processor import TextProcessor


def test_runtime_with_broken_native_dependency_is_not_installed(monkeypatch):
    monkeypatch.setattr(whisper_runtime, 'ensure_on_path', lambda: None)
    def broken(name):
        raise ImportError('DLL load failed')
    monkeypatch.setattr(importlib, 'import_module', broken)
    monkeypatch.setattr(whisper_runtime, '_runtime_import_error', '')
    assert not whisper_runtime.is_installed()
    assert '依赖加载失败' in whisper_runtime.get_status()['message']
    assert whisper_runtime.get_status()['status'] == 'error'


def test_duplicate_runtime_install_does_not_spawn_two_pip_processes(monkeypatch):
    calls = []
    monkeypatch.setattr(whisper_runtime, 'is_installed', lambda: False)
    class Thread:
        def __init__(self, **kwargs): calls.append(kwargs)
        def start(self): pass
    monkeypatch.setattr(whisper_runtime.threading, 'Thread', Thread)
    whisper_runtime._set_state(status='unknown')
    try:
        assert whisper_runtime.start_install()['started']
        assert not whisper_runtime.start_install()['started']
        assert len(calls) == 1
    finally:
        whisper_runtime._set_state(status='unknown', message='', progress=0, log_tail='')


@pytest.mark.parametrize('fenced', [False, True])
def test_outline_accepts_actual_category_json_contract(fenced):
    obj = OutlineExtractor.__new__(OutlineExtractor)
    data = [{'title':'演讲主题','subtopics':['第一点', '第二点']}]
    text = json.dumps(data)
    if fenced: text = '```json\n' + text + '\n```'
    assert obj._parse_outline_response(text, 3) == [{**data[0], 'chunk_index': 3}]


def test_every_category_outline_example_is_supported():
    import re
    obj = OutlineExtractor.__new__(OutlineExtractor)
    paths = list(Path('backend/prompt').glob('*/大纲.txt'))
    assert paths
    for path in paths:
        source = path.read_text()
        examples = re.findall(r'```json\s*(\[.*?\])\s*```', source, re.S)
        for example in examples:
            assert obj._parse_outline_response(example, 0), path


def test_chunk_limit_keeps_cues_and_absolute_times():
    entries = [{'text': 'x'*600, 'start_time': f'00:0{i}:00,000', 'end_time': f'00:0{i}:30,000'} for i in range(4)]
    chunks = [{'srt_entries': entries}]
    small = TextProcessor.limit_srt_chunk_size(chunks, 1000)
    large = TextProcessor.limit_srt_chunk_size(chunks, 3000)
    assert len(small) == 4 and len(large) == 1
    assert [cue for chunk in small for cue in chunk['srt_entries']] == entries
    assert small[-1]['end_time'] == entries[-1]['end_time']
    assert [c['chunk_index'] for c in small] == list(range(4))


def test_collection_limit_and_valid_small_collection_are_preserved(monkeypatch, tmp_path):
    from backend.pipeline import settings, step5_clustering
    saved = {'max_clips_per_collection': 2}
    monkeypatch.setattr(settings, 'get_llm_manager', lambda: SimpleNamespace(get_processing_setting=lambda name, default: saved.get(name, default)))
    clips = [dict(id=str(i), outline=f'title {i}', generated_title=f'title {i}', final_score=.9) for i in range(5)]
    llm = SimpleNamespace(call_with_retry=lambda *a: 'answer', parse_json_response=lambda r: [{'collection_title':'group','collection_summary':'summary','clips':[c['outline'] for c in clips]}])
    monkeypatch.setattr(step5_clustering, 'LLMClient', lambda: llm)
    prompt = tmp_path/'prompt'; prompt.write_text('cluster')
    engine = ClusteringEngine(tmp_path, {'clustering': prompt})
    assert engine.cluster_clips(clips)[0]['clip_ids'] == ['0', '1']
    assert len(engine._create_default_collections(clips)[0]['clip_ids']) == 2
    assert len(engine._create_collections_from_pre_clusters({'theme': [c['id'] for c in clips]}, clips)[0]['clip_ids']) == 2
    saved['max_clips_per_collection'] = 4
    next_engine = ClusteringEngine(tmp_path, {'clustering': prompt})
    assert len(next_engine.cluster_clips(clips)[0]['clip_ids']) == 4


def test_youtube_subtitle_and_format_failures_recover_with_bounded_attempts(monkeypatch):
    from backend.utils import download_recovery as module
    calls = []
    class Downloader:
        def __init__(self, opts): self.opts = dict(opts)
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def download(self, urls):
            calls.append(self.opts)
            if len(calls) == 1: raise module.yt_dlp.utils.DownloadError('Unable to download subtitles: HTTP Error 429')
            if len(calls) == 2: raise module.yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden')
            return 0
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    opts = {'writesubtitles': True, 'writeautomaticsub': True, 'format': 'best'}
    module.download_with_recovery('https://youtube.com/watch?v=sample', opts)
    assert len(calls) == 3
    assert not calls[1]['writesubtitles']
    assert 'm3u8' in calls[2]['format']
    assert opts['writesubtitles'] is True
    assert all(c['skip_unavailable_fragments'] is False and c['fragment_retries'] == 2 for c in calls)


def test_youtube_permanent_failure_is_not_silently_successful(monkeypatch):
    from backend.utils import download_recovery as module
    calls = []
    class Downloader:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def download(self, urls):
            calls.append(urls)
            raise module.yt_dlp.utils.DownloadError('HTTP Error 403: Forbidden')
    monkeypatch.setattr(module.yt_dlp, 'YoutubeDL', Downloader)
    with pytest.raises(module.yt_dlp.utils.DownloadError):
        module.download_with_recovery('https://youtube.com/watch?v=sample', {})
    assert len(calls) == 2


def test_completion_uses_actual_step6_counter_names(tmp_path):
    from backend.services.data_sync_service import DataSyncService
    from backend.models.project import ProjectStatus
    project = SimpleNamespace(status=ProjectStatus.PROCESSING)
    query = SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: project))
    service = DataSyncService.__new__(DataSyncService)
    service.db = SimpleNamespace(query=lambda *a: query, commit=lambda: None)
    output = tmp_path/'output';output.mkdir()
    (output/'step6_video_output.json').write_text(json.dumps({'clips_generated': 2, 'collections_generated': 1, 'clip_paths':['a','b']}))
    service._update_project_status_if_completed('fixture',tmp_path)
    assert project.total_clips == 2 and project.total_collections == 1
