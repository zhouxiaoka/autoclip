import json
from pathlib import Path
from types import SimpleNamespace
import wave

import httpx
import pytest

from backend.services import cloud_transcription as asr
from backend.services.ai_model_settings import Connection, ModelSettings, Transcription


def test_timing_units_offsets_and_reject_fabricated_boundaries():
    assert asr.normalize_segments([{'begin_time': 500, 'end_time': 1700, 'text': '你好'}], 180, True) == [
        {'start': 180.5, 'end': 181.7, 'text': '你好'}]
    for segment in [{'text': 'hi'}, {'text': 'hi', 'start': -1, 'end': 1}, {'text': 'hi', 'start': 1, 'end': float('nan')}]:
        with pytest.raises(asr.CloudTranscriptionError):
            asr.normalize_segments([segment])


@pytest.mark.parametrize('model,format', [('whisper-1', 'verbose_json'), ('gpt-4o-transcribe-diarize', 'diarized_json')])
def test_openai_upload_and_timestamp_format(tmp_path, model, format):
    audio = tmp_path / 'audio.wav'; audio.write_bytes(b'fake-wav')
    def handler(request):
        assert request.url.path == '/v1/audio/transcriptions'
        assert request.headers['authorization'] == 'Bearer secret'
        assert format.encode() in request.content
        assert b'fake-wav' in request.content
        return httpx.Response(200, json={'segments': [{'start': .2, 'end': 1, 'text': 'Hello'}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items, milliseconds = asr.request_chunk(client, Connection(id='a', name='a', api_key='secret'), model, audio, 'auto')
    assert items[0]['text'] == 'Hello'
    assert not milliseconds


def test_dashscope_keeps_all_final_sentences_and_ignores_partial(tmp_path):
    audio = tmp_path / 'audio.wav'; audio.write_bytes(b'fake-wav')
    def handler(request):
        assert request.url.path == '/api/v1/services/aigc/multimodal-generation/generation'
        body = json.loads(request.content)
        assert body['input']['messages'][0]['content'][0]['input_audio']['data'].startswith('data:audio/wav;base64,')
        assert body['parameters']['language_hints'] == ['zh']
        events = [dict(sentence_id=1, sentence_end=False, text='partial'),
                  dict(sentence_id=1, sentence_end=True, begin_time=0, end_time=700, text='一'),
                  dict(sentence_id=2, sentence_end=True, begin_time=900, end_time=1800, text='二')]
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'},
            text='\n\n'.join('data: ' + json.dumps({'output': {'sentence': s}}) for s in events))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        items, milliseconds = asr.request_chunk(client, Connection(id='a', name='a', provider='dashscope'),
            'qwen-audio-3.0-asr-flash', audio, 'zh')
    assert [s['text'] for s in items] == ['一', '二']
    assert milliseconds


def test_long_audio_merges_offsets_and_failure_does_not_publish_partial(monkeypatch, tmp_path):
    import backend.utils.speech_recognizer  # keep unrelated optional imports outside the subprocess mock
    def extract(command, **kwargs):
        with wave.open(command[-1], 'wb') as audio:
            audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
            audio.writeframes(b'\0\0' * 16000 * 181)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(asr.subprocess, 'run', extract)
    monkeypatch.setattr(asr, 'get_ffmpeg_path', lambda: 'ffmpeg')
    selection = ModelSettings(connections=[Connection(id='a', name='a', api_key='secret')],
        transcription=Transcription(provider='cloud', model='whisper-1', connection_id='a'))
    chunks = []
    def response(*args):
        chunks.append(args[3].read_bytes())
        return [{'start': .1, 'end': .8, 'text': '字幕'}], False
    monkeypatch.setattr(asr, 'request_chunk', response)
    output = tmp_path / 'out.srt'
    asr.transcribe(tmp_path / 'video.mp4', output, selection)
    assert '00:03:00,100 --> 00:03:00,800' in output.read_text()
    assert len(chunks) == 2
    output.unlink(); chunks.clear()
    def fail(*args):
        chunks.append(1)
        if len(chunks) == 2: raise asr.CloudTranscriptionError('failure')
        return [{'start': .1, 'end': .8, 'text': '字幕'}], False
    monkeypatch.setattr(asr, 'request_chunk', fail)
    with pytest.raises(asr.CloudTranscriptionError):
        asr.transcribe(tmp_path / 'video.mp4', output, selection)
    assert not output.exists()


def test_missing_timestamps_not_treated_as_subtitles(tmp_path):
    audio = tmp_path / 'audio.wav'; audio.write_bytes(b'audio')
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'text': 'text only'}))) as client:
        with pytest.raises(asr.CloudTranscriptionError, match='时间戳'):
            asr.request_chunk(client, Connection(id='a', name='a'), 'whisper-1', audio, 'auto')


def test_rate_limits_and_server_errors_are_retried_but_auth_errors_are_not(monkeypatch):
    import httpx
    from backend.services import cloud_transcription as ct

    def status(code):
        request = httpx.Request('POST', 'https://asr.example.com')
        return httpx.HTTPStatusError('x', request=request, response=httpx.Response(code, request=request))
    assert ct._retryable(status(429)) and ct._retryable(status(503)) and ct._retryable(httpx.ConnectError('down'))
    assert not ct._retryable(status(401)) and not ct._retryable(status(400))
    for value, expected in (('0', 1), ('abc', 8), ('4', 4)):
        monkeypatch.setenv('AUTOCLIP_ASR_CONCURRENCY', value)
        assert ct._workers() == expected
