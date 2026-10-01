"""Cloud ASR with real timestamps, bounded uploads, and no provider fallback."""
from __future__ import annotations

import base64
import json
import math
import os
import time
from pathlib import Path
import subprocess
import tempfile
import wave

import httpx

from backend.core.asr_model_catalog import adapter
from backend.services.ai_model_settings import chat_endpoint
from backend.utils.ffmpeg_utils import get_ffmpeg_path


def _workers() -> int:
    try:
        return max(1, int(os.getenv('AUTOCLIP_ASR_CONCURRENCY', '8') or 8))
    except ValueError:
        return 8


UPLOAD_WORKERS = _workers()  # parallel chunk uploads (16 gained only ~10 %)
CHUNK_ATTEMPTS = 3  # parallel uploads meet rate limits more often: a busy chunk waits and retries alone


def _retryable(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429 or error.response.status_code >= 500
    return isinstance(error, httpx.RequestError)


class CloudTranscriptionError(RuntimeError):
    pass


def normalize_segments(items, offset=0.0, milliseconds=False, duration=None):
    """Reject missing/invalid timing instead of inventing clip boundaries."""
    result = []
    scale = 1000 if milliseconds else 1
    for item in items:
        text = str(item.get('text') or '').strip()
        if not text:
            continue
        try:
            start = float(item['begin_time' if milliseconds else 'start']) / scale
            end = float(item['end_time' if milliseconds else 'end']) / scale
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
                raise ValueError()
            if duration is not None and end > duration + 1:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise CloudTranscriptionError('转写服务未返回有效时间戳，无法生成准确字幕；请更换转写模型。') from None
        result.append({'start': start + offset, 'end': end + offset, 'text': text})
    return result


def request_chunk(client, connection, model, audio, language):
    route = adapter(connection.provider, model)
    endpoint = chat_endpoint(connection, model)
    headers = {'Authorization': 'Bearer ' + endpoint['api_key']} if endpoint['api_key'] else {}
    if route == 'dashscope':
        base = (connection.base_url or 'https://dashscope.aliyuncs.com/compatible-mode/v1').removesuffix('/compatible-mode/v1').rstrip('/')
        if not base.endswith('/api/v1'):
            base += '/api/v1'
        params = {'format': 'wav', 'sample_rate': '16000'}
        if language != 'auto':
            params['language_hints'] = [language]
        if model == 'qwen-audio-3.1-asr-flash':
            params['speaker_diarization_enabled'] = True
        payload = {'model': model, 'input': {'messages': [{'role': 'user', 'content': [
            {'type': 'input_audio', 'input_audio': {'data': 'data:audio/wav;base64,' + base64.b64encode(audio.read_bytes()).decode()}}
        ]}]}, 'parameters': params}
        # SSE retains every completed sentence; the final non-stream response may only contain the last one.
        sentences = {}
        with client.stream('POST', base + '/services/aigc/multimodal-generation/generation',
                           headers={**headers, 'X-DashScope-SSE': 'enable'}, json=payload) as response:
            response.raise_for_status()
            if 'text/event-stream' in response.headers.get('content-type', ''):
                events = (json.loads(line[5:].strip()) for line in response.iter_lines()
                          if line.startswith('data:') and line[5:].strip() not in {'', '[DONE]'})
            else:
                response.read()
                events = [response.json()]
            for event in events:
                if event.get('code') and event['code'] not in {'Success', '200'}:
                    raise CloudTranscriptionError('云端转写失败，请检查账号权限、额度和模型。')
                output = event.get('output') or {}
                items = output.get('sentences') or [output.get('sentence') or {}]
                for item in items:
                    if item.get('sentence_end') is True:
                        sentences[(item.get('channel_id', 0), item.get('sentence_id', item.get('begin_time')))] = item
        return list(sentences.values()), True
    if route not in {'openai', 'diarized'}:
        raise CloudTranscriptionError('该转写模型尚未接入。')
    data = {'model': model, 'response_format': 'diarized_json' if route == 'diarized' else 'verbose_json'}
    if route == 'diarized':
        data['chunking_strategy'] = 'auto'
    else:
        data['timestamp_granularities[]'] = 'segment'
    if language != 'auto':
        data['language'] = language
    with audio.open('rb') as stream:
        response = client.post(endpoint['base_url'].rstrip('/') + '/audio/transcriptions', headers=headers,
                               data=data, files={'file': ('audio.wav', stream, 'audio/wav')})
    response.raise_for_status()
    payload = response.json()
    segments = payload.get('segments')
    if not isinstance(segments, list):
        raise CloudTranscriptionError('转写服务没有返回字幕时间戳，请使用支持 verbose_json 的模型。')
    return segments, False


def transcribe(video: Path, output: Path | None, settings, language='auto', timeout=0):
    selection = settings.transcription
    connection = next(c for c in settings.connections if c.id == selection.connection_id)
    if not connection.api_key and connection.provider != 'compatible':
        raise CloudTranscriptionError('请先在字幕转写设置中填写 API Key。')
    output = Path(output) if output else video.with_suffix('.srt')
    from backend.utils.speech_recognizer import SpeechRecognizer, srt_has_cue_text
    if output.exists() and srt_has_cue_text(output):
        return output
    # Each upload is <= 180 seconds / 5.76 MB PCM, including base64 < 10 MB.
    # Exact sample offsets avoid encoder delay/drift when merging long recordings.
    with tempfile.TemporaryDirectory(prefix='autoclip-asr-') as temp:
        audio = Path(temp) / 'source.wav'
        completed = subprocess.run([get_ffmpeg_path(), '-nostdin', '-y', '-i', str(video), '-vn',
                                    '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(audio)],
                                   capture_output=True, timeout=timeout or None)
        if completed.returncode:
            raise CloudTranscriptionError('无法提取视频音频，请检查视频是否包含音轨。')
        segments = []
        from backend.core.llm_providers import is_local_url
        try:
            # Cut every chunk first, then upload them side by side: one request after another made a
            # three-hour talk ~60 sequential round trips. Offsets come from exact sample counts.
            chunks, offset = [], 0.0
            with wave.open(str(audio), 'rb') as source:
                while True:
                    samples = source.readframes(16000 * 180)
                    if not samples:
                        break
                    chunk = Path(temp) / f'chunk-{len(chunks):04d}.wav'
                    with wave.open(str(chunk), 'wb') as target:
                        target.setparams(source.getparams())
                        target.writeframes(samples)
                    duration = len(samples) / 32000
                    chunks.append((chunk, offset, duration))
                    offset += duration
            with httpx.Client(timeout=timeout or 300, follow_redirects=False,
                              trust_env=not is_local_url(chat_endpoint(connection, '')['base_url'])) as client:
                def one(part):
                    chunk, start, duration = part
                    for attempt in range(CHUNK_ATTEMPTS):
                        try:
                            items, milliseconds = request_chunk(client, connection, selection.model, chunk, language)
                            break
                        except (httpx.HTTPStatusError, httpx.RequestError) as error:
                            if attempt == CHUNK_ATTEMPTS - 1 or not _retryable(error):
                                raise
                            time.sleep(2 * 2 ** attempt)
                    return normalize_segments(items, start, milliseconds, duration)

                from concurrent.futures import ThreadPoolExecutor
                pool = ThreadPoolExecutor(max_workers=UPLOAD_WORKERS, thread_name_prefix='asr-chunk')
                try:
                    for part in pool.map(one, chunks):
                        segments.extend(part)
                finally:
                    # On a failure, chunks not yet sent are dropped instead of spending more quota.
                    pool.shutdown(wait=True, cancel_futures=True)
        except httpx.HTTPStatusError as exc:
            raise CloudTranscriptionError(f'云端转写请求失败（HTTP {exc.response.status_code}），请检查密钥、额度和模型权限。') from None
        except (httpx.RequestError, ValueError) as exc:
            raise CloudTranscriptionError('云端转写连接失败或响应格式无效，请稍后重试。') from None
        if not segments:
            raise CloudTranscriptionError('转写结果为空，音频中可能没有可识别的人声。')
        segments.sort(key=lambda s: (s['start'], s['end']))
        output.parent.mkdir(parents=True, exist_ok=True)
        # Publish only the complete transcript; failed later chunks leave no partial subtitle.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as target:
            pending = Path(target.name)
            target.write(SpeechRecognizer._segments_to_srt(segments))
        try:
            os.replace(pending, output)
            from backend.utils.word_timing import sidecar_path
            sidecar_path(output).unlink(missing_ok=True)
        finally:
            pending.unlink(missing_ok=True)
    return output
