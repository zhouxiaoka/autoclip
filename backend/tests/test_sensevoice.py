"""CTC timing, complete text, route selection, dependency isolation and locking."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from backend.services.sensevoice_alignment import aligned_cues
from backend.services import sensevoice_runtime as runtime
from backend.services.ai_model_settings import ModelSettings, Transcription


def fixture(text='这是第一段。这里是第二段。最后一段用于验证音频末尾。'):
    words = list(text)
    return [{'text': '<|zh|><|NEUTRAL|>' + text, 'words': words,
             'timestamp': [[1050 + i * 800, 1550 + i * 800] for i in range(len(words))],
             'sentence_info': [{'sentence': text, 'start': 0, 'end': 30010}]}]


def test_ctc_avoids_coarse_vad_cues_and_preserves_all_text():
    raw = fixture()
    cues = aligned_cues(raw, 45100)
    assert len(cues) > 2
    assert ''.join(c['text'] for c in cues) == raw[0]['text'].split('>')[-1]
    assert cues[0]['start'] == 1.05
    assert cues[-1]['end'] == raw[0]['timestamp'][-1][1] / 1000
    from backend.utils.word_timing import valid_words
    assert all(valid_words(c) and c['end'] - c['start'] <= 8 for c in cues)


def test_spaces_numbers_and_punctuation_are_preserved():
    raw = [{'text': 'Hello, world. It was 19 years ago.',
            'words': ['Hello', ',', 'world', '.', 'It', 'was', '1', '9', 'years', 'ago', '.'],
            'timestamp': [[i * 500, i * 500 + 400] for i in range(11)]}]
    cues = aligned_cues(raw, 6000)
    assert [c['text'] for c in cues] == ['Hello, world.', 'It was 19 years ago.']
    assert ''.join(w['text'] for c in cues for w in c['words']) == raw[0]['text']


@pytest.mark.parametrize('broken', ['missing', 'partial', 'reverse', 'overlap', 'nan', 'beyond', 'text'])
def test_bad_alignment_never_fabricates_or_partially_writes(broken):
    raw = fixture()
    if broken == 'missing': raw[0].pop('timestamp')
    if broken == 'partial': raw[0]['words'].pop()
    if broken == 'reverse': raw[0]['timestamp'][0] = [2000, 1000]
    if broken == 'overlap': raw[0]['timestamp'][1] = [1100, 1600]
    if broken == 'nan': raw[0]['timestamp'][0][0] = float('nan')
    if broken == 'beyond': raw[0]['timestamp'][-1] = [46000, 47000]
    if broken == 'text': raw[0]['text'] += '丢失的正文'
    with pytest.raises(ValueError):
        aligned_cues(raw, 45100)


def test_multiple_vad_items_must_be_complete_and_monotonic():
    first = fixture('你好。')
    second = fixture('再见。')
    for time in second[0]['timestamp']:
        time[0] += 5000; time[1] += 5000
    cues = aligned_cues(first + second, 10000)
    assert [c['text'] for c in cues] == ['你好。', '再见。']
    with pytest.raises(ValueError): aligned_cues(second + first, 10000)


def test_local_selection_has_no_connection_and_validates_model(monkeypatch, tmp_path):
    selection = Transcription(provider='sensevoice_local', model='SenseVoiceSmall', connection_id='obsolete')
    assert selection.connection_id is None
    with pytest.raises(ValueError): Transcription(provider='sensevoice_local', model='base')
    from backend.services import ai_model_settings
    from backend.utils import speech_recognizer
    monkeypatch.setattr(ai_model_settings, 'load', lambda: ModelSettings(transcription=selection))
    calls = []
    def transcribe(*args):
        calls.append(args)
        return tmp_path / 'out.srt'
    monkeypatch.setattr(runtime, 'transcribe', transcribe)
    monkeypatch.setattr(speech_recognizer, 'SpeechRecognizer', lambda: pytest.fail('must not load Whisper'))
    assert speech_recognizer.generate_subtitle_for_video(tmp_path / 'video.mp4', model='tiny') == tmp_path / 'out.srt'
    assert calls[0][2:] == ('auto', 0)


def test_cross_process_lock_rejects_uninstall_and_releases(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    with runtime.operation():
        with pytest.raises(RuntimeError, match='正在准备或转写'): runtime.uninstall()
    assert runtime.uninstall()['status'] == 'not_installed'


def test_worker_uses_isolated_interpreter_not_parent_import_path(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path)
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, 'run', run)
    runtime.worker('transcribe', tmp_path / 'r.json', tmp_path / 'a.wav')
    assert calls[0][:2] == [sys.executable, '-S']
    assert calls[0][2].endswith('sensevoice_worker.py')
    assert '-m' not in calls[0]


def test_interrupted_install_is_retryable_after_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    runtime._state('installing')
    assert runtime.status()['status'] == 'error'
    with runtime.operation():
        assert runtime.status()['status'] == 'installing'


def test_status_api_is_lightweight_and_install_conflict_is_explicit(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.speech_recognition import router
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'sensevoice')
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/sensevoice/status').json()['status'] == 'not_installed'
        with runtime.operation():
            assert client.post('/sensevoice/prepare').status_code == 409
            assert client.delete('/sensevoice').status_code == 409


def test_transcribe_srt_and_real_word_sidecar_without_optional_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'root', lambda: tmp_path / 'runtime')
    monkeypatch.setattr(runtime, 'status', lambda: {'status': 'ready'})
    raw = fixture()
    def extract(cmd, **kw):
        with wave.open(cmd[-1], 'wb') as target:
            target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            target.writeframes(b'\0\0' * (16000 * 45))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, 'run', extract)
    def worker(action, result, *args): result.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setattr(runtime, 'worker', worker)
    output = tmp_path / '字幕.srt'
    runtime.transcribe(tmp_path / '源.mp4', output)
    from backend.utils.word_timing import load_word_timing
    assert load_word_timing(output)
    before = output.read_bytes()
    raw[0]['words'].pop()
    from backend.utils.speech_recognizer import SpeechRecognitionError
    with pytest.raises(SpeechRecognitionError): runtime.transcribe(tmp_path / '源.mp4', output)
    assert output.read_bytes() == before
    output.write_text('edited', encoding='utf-8')
    assert load_word_timing(output) is None


def test_sensevoice_error_does_not_point_to_whisper(monkeypatch):
    from backend.pipeline.failures import failure_from_speech_error
    from backend.services import whisper_runtime
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda: pytest.fail('unrelated Whisper probe'))
    failure = failure_from_speech_error('SenseVoice 词与时间戳未完整配对')
    assert failure.code == 'subtitle_setup' and 'SenseVoice' in failure.hint
    assert 'Whisper' not in failure.user_message()
