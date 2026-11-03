"""Local models cap outline chunk_size at 2000; cloud keeps the configured value."""
import pytest

from backend.pipeline.failures import PipelineFailure
from backend.pipeline.settings import LOCAL_CHUNK_SIZE_CAP, effective_chunk_size
from backend.utils.text_processor import TextProcessor


class _Manager:
    def __init__(self, settings, chunk_size):
        self.settings = settings
        self.chunk_size = chunk_size

    def get_processing_setting(self, name, default=None):
        if name == 'chunk_size':
            return self.chunk_size
        return default


def _use(monkeypatch, settings, chunk_size):
    manager = _Manager(settings, chunk_size)
    import backend.pipeline.settings as pipeline_settings
    monkeypatch.setattr(pipeline_settings, 'get_llm_manager', lambda: manager)
    return manager


OLLAMA = {
    'llm_provider': 'openai',
    'llm_provider_preset': 'ollama',
    'openai_base_url': 'http://localhost:11434/v1',
}
LMSTUDIO = {
    'llm_provider': 'openai',
    'connection_provider': 'lmstudio',
    'openai_base_url': 'http://localhost:1234/v1',
}
LOCALHOST = {
    'llm_provider': 'openai',
    'connection_provider': 'compatible',
    'openai_base_url': 'http://127.0.0.1:8080/v1',
}
LOOPBACK = {
    'llm_provider': 'openai',
    'openai_base_url': 'http://localhost:8000/v1',
}
DASHSCOPE = {'llm_provider': 'dashscope', 'model_name': 'qwen-plus'}
DEEPSEEK = {
    'llm_provider': 'openai',
    'connection_provider': 'deepseek',
    'openai_base_url': 'https://api.deepseek.com',
}


@pytest.mark.parametrize('settings, configured, expected', [
    (OLLAMA, 5000, 2000),
    (LMSTUDIO, 5000, 2000),
    (OLLAMA, 8000, 2000),
    (OLLAMA, 10000, 2000),
    (LOCALHOST, 5000, 2000),
    (LOOPBACK, 10000, 2000),
    (DASHSCOPE, 5000, 5000),
    ({'llm_provider': 'gemini'}, 5000, 5000),
    (DEEPSEEK, 7500, 7500),
    (DASHSCOPE, 1000, 1000),
    (DASHSCOPE, 10000, 10000),
    (OLLAMA, 1500, 1500),
    (OLLAMA, 2000, 2000),
    (LOCALHOST, 1000, 1000),
    (DASHSCOPE, 1800, 1800),
    (OLLAMA, 12000, 2000),
    (DASHSCOPE, 12000, 5000),
    (DASHSCOPE, 500, 5000),
])
def test_effective_chunk_size_follows_the_active_model(monkeypatch, settings, configured, expected):
    _use(monkeypatch, settings, configured)
    assert effective_chunk_size() == expected


def test_unreadable_local_detection_keeps_the_configured_size(monkeypatch):
    from backend.core import local_presets

    _use(monkeypatch, OLLAMA, 6400)

    def broken(settings):
        raise RuntimeError('settings unreadable')

    monkeypatch.setattr(local_presets, 'is_local_model', broken)
    assert effective_chunk_size() == 6400


def test_local_cap_splits_a_block_the_cloud_default_keeps_together():
    entries = [
        {'text': '字' * 800, 'start_time': f'00:0{i}:00,000', 'end_time': f'00:0{i}:30,000'}
        for i in range(4)
    ]
    chunks = [{'srt_entries': entries}]
    cloud = TextProcessor.limit_srt_chunk_size(chunks, 5000)
    local = TextProcessor.limit_srt_chunk_size(chunks, LOCAL_CHUNK_SIZE_CAP)
    assert len(cloud) == 1
    assert len(local) == 2
    assert [cue for chunk in local for cue in chunk['srt_entries']] == entries


class _Processor:
    def __init__(self, seen):
        self.seen = seen

    def parse_srt(self, path):
        return [{'start_time': '00:00:00,000', 'end_time': '00:00:03,000', 'text': '你好'}]

    def chunk_srt_data(self, data, interval_minutes=30):
        return [{
            'chunk_index': 0,
            'text': '你好',
            'start_time': data[0]['start_time'],
            'end_time': data[-1]['end_time'],
            'srt_entries': data,
        }]

    def limit_srt_chunk_size(self, chunks, max_chars):
        self.seen.append(max_chars)
        return []


@pytest.mark.parametrize('settings, configured, expected', [
    (OLLAMA, 5000, 2000),
    (LOCALHOST, 8000, 2000),
    (DASHSCOPE, 8000, 8000),
    (OLLAMA, 1500, 1500),
])
def test_outline_step_applies_the_effective_chunk_size(monkeypatch, tmp_path, settings, configured, expected):
    from backend.core import llm_manager
    from backend.pipeline.step1_outline import OutlineExtractor

    manager = _use(monkeypatch, settings, configured)
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)

    seen = []
    extractor = OutlineExtractor.__new__(OutlineExtractor)
    extractor.text_processor = _Processor(seen)
    extractor.metadata_dir = tmp_path
    extractor.chunks_dir = tmp_path / 'step1_chunks'
    extractor.srt_chunks_dir = tmp_path / 'step1_srt_chunks'
    extractor.chunks_dir.mkdir()
    extractor.srt_chunks_dir.mkdir()
    extractor.outline_prompt = 'outline'

    with pytest.raises(PipelineFailure) as raised:
        extractor.extract_outline(tmp_path / 'input.srt')
    assert raised.value.code == 'invalid_response'
    assert seen == [expected]
