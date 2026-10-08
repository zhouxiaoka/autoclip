"""Local models get smaller clip_finder windows; cloud windows stay exactly as before (RC156 Win QA #14b)."""
import pytest

from backend.core import local_presets
from backend.pipeline import clip_finder
from backend.pipeline.quality import to_srt_time


def _rows(minutes, row_sec=3.0, text='这是一句用来测试窗口切分的中文字幕内容。'):
    return [{'start': i * row_sec, 'end': (i + 1) * row_sec, 'text': text} for i in range(int(minutes * 60 / row_sec))]


def _legacy_windows(rows):
    """origin/main 13b1929a `clip_finder.windows`, verbatim apart from the constants."""
    if not rows:
        return []
    out, first = [], 0
    while first < len(rows):
        start, chars, last = rows[first]['start'], 0, first
        while last + 1 < len(rows) and rows[last + 1]['end'] - start <= 3600 and chars + len(rows[last + 1]['text']) <= 70_000:
            last += 1
            chars += len(rows[last]['text'])
        out.append((first, last))
        if last + 1 >= len(rows):
            break
        back = last
        while back > first and rows[last]['end'] - rows[back]['start'] < 240:
            back -= 1
        first = max(back, first + 1)
    return out


def test_cloud_window_is_unchanged():
    assert (clip_finder.WINDOW_SEC, clip_finder.OVERLAP_SEC, clip_finder.WINDOW_CHARS) == (3600, 240, 70_000)
    assert clip_finder.CLOUD_WINDOW == clip_finder.WindowSize(3600, 240, 70_000, 'cloud')
    for rows in (_rows(35), _rows(150, row_sec=5.0, text='x'), _rows(120), _rows(240, text='长' * 60), _rows(2)):
        assert clip_finder.windows(rows) == clip_finder.windows(rows, clip_finder.CLOUD_WINDOW) == _legacy_windows(rows)


def test_local_window_is_about_twenty_minutes_or_twelve_thousand_characters_with_proportional_overlap():
    size = clip_finder.LOCAL_WINDOW
    assert (size.seconds, size.chars, size.kind) == (1200, 12_000, 'local')
    assert size.overlap == pytest.approx(80) and size.overlap / size.seconds == pytest.approx(240 / 3600)
    for rows in (_rows(35), _rows(120), _rows(120, text='长' * 60)):
        spans = clip_finder.windows(rows, size)
        assert spans[0][0] == 0 and spans[-1][1] == len(rows) - 1 and len(spans) > 1
        for first, last in spans:
            assert rows[last]['end'] - rows[first]['start'] <= size.seconds
            assert sum(len(rows[i]['text']) for i in range(first + 1, last + 1)) <= size.chars
        for (_, last), (first, _) in zip(spans, spans[1:]):
            assert first < last and rows[last]['end'] - rows[first]['start'] >= size.overlap - 3
    # The 35-minute Win QA source was one 46K-token cloud call; local now splits it.
    assert len(clip_finder.windows(_rows(35))) == 1
    assert clip_finder.windows(_rows(5), size) == [(0, 99)]


def _entries(minutes, row_sec=3.0):
    return [{'index': i + 1, 'start_time': to_srt_time(i * row_sec), 'end_time': to_srt_time((i + 1) * row_sec),
             'text': f'第{i}句，这是一句用来测试窗口切分的中文字幕。'} for i in range(int(minutes * 60 / row_sec))]


def _record_calls():
    sent = []

    def call(prompt, data):
        sent.append(data['rows'])
        first = int(data['rows'].split('|', 1)[0])
        return {'clips': [{'start': first + 2, 'end': first + 40, 'title': '一个完整的观点', 'reason': '观点鲜明', 'score': 0.9}]}
    return sent, call


@pytest.mark.parametrize('settings, local', [
    ({'llm_provider': 'openai', 'llm_provider_preset': 'ollama', 'openai_base_url': 'http://localhost:11434/v1'}, True),
    ({'llm_provider': 'openai', 'llm_provider_preset': 'lmstudio', 'openai_base_url': 'http://localhost:1234/v1'}, True),
    ({'llm_provider': 'openai', 'connection_provider': 'ollama', 'openai_base_url': 'http://192.168.1.20:11434/v1'}, True),
    ({'llm_provider': 'openai', 'connection_provider': 'lmstudio', 'openai_base_url': 'http://localhost:1234/v1'}, True),
    ({'llm_provider': 'openai', 'connection_provider': 'compatible', 'openai_base_url': 'http://127.0.0.1:8080/v1'}, True),
    ({'llm_provider': 'openai', 'connection_provider': 'compatible', 'openai_base_url': 'http://10.0.0.5:8000/v1'}, True),
    ({'llm_provider': 'openai', 'connection_provider': 'compatible', 'openai_base_url': 'https://openrouter.ai/api/v1'}, False),
    ({'llm_provider': 'openai', 'connection_provider': 'deepseek', 'openai_base_url': 'https://api.deepseek.com'}, False),
    ({'llm_provider': 'openai', 'connection_provider': 'infistar', 'openai_base_url': 'https://infistar.cc/v1'}, False),
    ({'llm_provider': 'dashscope', 'model_name': 'qwen-plus'}, False),
    ({'llm_provider': 'gemini'}, False),
    ({}, False),
])
def test_local_model_detection(settings, local):
    assert local_presets.is_local_model(settings) is local


class _Manager:
    def __init__(self, settings):
        self.settings = settings

    def get_current_provider_info(self):
        return {'available': True}


@pytest.mark.parametrize('settings, kind', [
    ({'llm_provider': 'openai', 'llm_provider_preset': 'ollama', 'openai_base_url': 'http://localhost:11434/v1'}, 'local'),
    ({'llm_provider': 'dashscope', 'model_name': 'qwen-plus'}, 'cloud'),
])
def test_window_size_follows_the_active_analysis_model(monkeypatch, settings, kind):
    import backend.core.llm_manager as llm_manager
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: _Manager(settings))
    assert clip_finder.window_size().kind == kind


def test_window_size_falls_back_to_cloud_when_the_manager_is_unavailable(monkeypatch):
    import backend.core.llm_manager as llm_manager

    def broken():
        raise RuntimeError('settings unreadable')
    monkeypatch.setattr(llm_manager, 'get_llm_manager', broken)
    assert clip_finder.window_size() is clip_finder.CLOUD_WINDOW


def test_local_model_sends_the_35_minute_transcript_in_small_windows(monkeypatch, tmp_path):
    import backend.core.llm_manager as llm_manager
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: _Manager({'llm_provider': 'openai', 'llm_provider_preset': 'ollama',
                                                                          'openai_base_url': 'http://localhost:11434/v1'}))
    sent, call = _record_calls()
    clip_finder.find_clips(_entries(35), call, threshold=0.5, metadata_dir=tmp_path)
    assert len(sent) == 2
    for rows in sent:
        lines = rows.split('\n')
        assert sum(len(line.split('|', 2)[2]) for line in lines[1:]) <= clip_finder.LOCAL_WINDOW.chars
    import json
    report = json.loads((tmp_path / 'quality_report.json').read_text(encoding='utf-8'))
    assert report['clip_finder']['window'] == 'local' and report['clip_finder']['windows'] == 2


def test_cloud_model_still_sends_the_35_minute_transcript_in_one_call(monkeypatch):
    import backend.core.llm_manager as llm_manager
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: _Manager({'llm_provider': 'dashscope', 'model_name': 'qwen-plus'}))
    sent, call = _record_calls()
    clip_finder.find_clips(_entries(35), call, threshold=0.5)
    assert len(sent) == 1


def test_local_presets_carry_a_context_hint():
    presets = {item['key']: item for item in local_presets.presets_as_dicts()}
    assert set(presets) == {'ollama', 'lmstudio'}
    assert 'OLLAMA_CONTEXT_LENGTH' in presets['ollama']['context_hint'] and 'num_ctx' in presets['ollama']['context_hint']
    assert 'Context Length' in presets['lmstudio']['context_hint']
    for item in presets.values():
        assert '16384' in item['context_hint']
    assert '16384' in local_presets.LOCAL_CONTEXT_HINT


@pytest.mark.parametrize('settings, expected', [
    ({'llm_provider': 'openai', 'llm_provider_preset': 'ollama', 'openai_base_url': 'http://localhost:11434/v1'}, 'OLLAMA_CONTEXT_LENGTH'),
    ({'llm_provider': 'openai', 'connection_provider': 'lmstudio', 'openai_base_url': 'http://localhost:1234/v1'}, 'Context Length'),
    ({'llm_provider': 'openai', 'connection_provider': 'compatible', 'openai_base_url': 'http://192.168.1.9:8000/v1'}, '本机或局域网模型'),
    ({'llm_provider': 'openai', 'connection_provider': 'deepseek', 'openai_base_url': 'https://api.deepseek.com'}, ''),
])
def test_context_hint_for_the_active_model(settings, expected):
    hint = local_presets.context_hint_for(settings)
    assert (expected in hint) if expected else hint == ''


def test_doctor_connection_check_carries_the_hint_for_local_models(monkeypatch):
    import backend.core.llm_manager as llm_manager
    from backend.services import local_runner

    class Provider:
        def test_connection(self):
            return True

    class Manager(_Manager):
        current_provider = Provider()

        def get_current_provider_info(self):
            return {'provider': self.settings.get('connection_provider'), 'model': 'm', 'available': True}

    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: Manager({'llm_provider': 'openai', 'connection_provider': 'deepseek'}))
    assert 'context_hint' not in local_runner.check_llm_connection()
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: Manager({'llm_provider': 'openai', 'llm_provider_preset': 'ollama',
                                                                       'connection_provider': 'ollama'}))
    assert 'OLLAMA_CONTEXT_LENGTH' in local_runner.check_llm_connection()['context_hint']
