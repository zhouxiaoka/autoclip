"""Cloud ASR with real timestamps, bounded uploads, and no provider fallback."""
from __future__ import annotations

import base64
import json
import math
import os
import re
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
# DashScope sync ASR rejects a chunk at the 180s / 10MB edge. 150s stays under both.
CHUNK_SECONDS = 150
CHUNK_SAMPLES = 16000 * CHUNK_SECONDS


def _retryable(error: Exception) -> bool:
    """Classified first only transient upstream types are retried, never a user cause such as
    insufficient_quota behind a 429; a bare 429 / 5xx without a recognised body stays retryable."""
    if isinstance(error, CloudTranscriptionError):
        from backend.core.upstream_errors import is_retryable
        if error.upstream_error_type:
            return is_retryable(error.upstream_error_type)
        return error.http_status is not None and (error.http_status == 429 or error.http_status >= 500)
    return isinstance(error, httpx.RequestError)


from backend.core.failure_attribution import AttributedError, ModelResponseInvalid, ProviderTransportError, attributed


def _upstream_type(status, body):
    """Enum only: e.g. HTTP 429 + "insufficient balance" -> insufficient_quota (user cause), not rate_limited.
    The body is classified and dropped; it never leaves this function."""
    from backend.core.upstream_errors import classify_upstream_error
    kind = classify_upstream_error(status, body).error_type.value
    return '' if kind == 'unknown' else kind


def _check_status(response):
    """The one place an HTTP error is classified. Called while the (stream) response is still open, so the
    body is readable; only the enum and status leave this function, never the body."""
    if not response.is_error:
        return
    try:
        body = response.read().decode('utf-8', 'replace')
    except Exception:  # noqa: BLE001 - unreadable body: classify by status alone
        body = None
    status = response.status_code
    raise CloudTranscriptionError(f'云端转写请求失败（HTTP {status}），请检查密钥、额度和模型权限。',
                                  http_status=status, upstream_error_type=_upstream_type(status, body))


class CloudTranscriptionError(AttributedError, RuntimeError):
    """Safe public text only. ``http_status`` / ``upstream_error_type`` are enums/ints, never provider bodies.

    a provider failure carries the snapshot built from the original exception (``.attribution``)
    before ``from None``; a local one (no key, no audio) carries none. ``error_code`` is the coarse studio
    code (``studio_code_for``), so a rejected key stays ``llm_auth_invalid`` and the fine cause stays upstream."""

    def __init__(self, message: str = '', *, http_status: int | None = None, upstream_error_type: str = ''):
        super().__init__(message)
        self.http_status = http_status if type(http_status) is int and 400 <= http_status <= 599 else None
        if not upstream_error_type and self.http_status is not None:
            from backend.core.upstream_errors import classify_upstream_error
            upstream_error_type = classify_upstream_error(self.http_status).error_type.value
        self.upstream_error_type = '' if upstream_error_type in ('', 'unknown') else upstream_error_type
        if self.upstream_error_type or self.http_status is not None:
            from backend.core.llm_retry import studio_code_for
            code = studio_code_for(self.upstream_error_type or 'unknown', self.http_status)
            # a plain 429 stays provider_error; rate_limited is the upstream enum, not the studio code.
            self.error_code = 'provider_error' if code == 'rate_limited' else code


def _provider_failure(message: str, original: BaseException, identity: dict | None = None) -> CloudTranscriptionError:
    """The redaction boundary: ``original`` is already the content-free view built inside the ``except``
    (a ``ProviderTransportError`` with the type name and, when an HTTP response came back, its status; or
    a ``ModelResponseInvalid``). THE classifier decides it (no ``sent`` override); the snapshot,
    the HTTP status and the controlled error code are frozen on the safe error, which the
    caller raises ``from None``. ``identity`` is the transcription connection THIS call used,
    frozen once in ``transcribe`` (``connection_identity``), so the snapshot names who answered."""
    from backend.core.llm_emit import attribution_snapshot
    snap = attribution_snapshot(original, failure_stage='subtitle', phase_identity=identity)
    return attributed(CloudTranscriptionError(message), snap, http_status=getattr(original, 'http_status', None),
                      error_code=getattr(original, 'error_code', None))


def normalize_segments(items, offset=0.0, milliseconds=False, duration=None, identity=None):
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
        except (KeyError, TypeError, ValueError) as error:
            raise _provider_failure('转写服务未返回有效时间戳，无法生成准确字幕；请更换转写模型。',
                                    ModelResponseInvalid(type(error).__name__), identity) from None
        result.append({'start': start + offset, 'end': end + offset, 'text': text})
    return result


def _sse_failure(event: dict) -> CloudTranscriptionError:
    """A DashScope SSE error. The public sentence names the kind; the body stays here."""
    code = str(event.get('code') or '')
    token = re.sub(r'[^a-z0-9]', '', code.lower())
    kind = _upstream_type(None, {'code': code})
    if any(part in token for part in ('throttl', 'toomany', 'ratequota')):
        return CloudTranscriptionError('云端转写繁忙，请稍后重试。', upstream_error_type='rate_limited')
    if any(part in token for part in ('internal', 'unavailable', 'badgateway', 'gateway', 'timeout')):
        return CloudTranscriptionError('云端转写暂时不可用，请稍后重试。', upstream_error_type='upstream_unavailable')
    if any(part in token for part in ('invalidparameter', 'audiolength', 'audioduration')):
        return CloudTranscriptionError(
            '云端转写拒绝了这段音频（过长、过短或格式不符合该模型）。请更换转写模型，或改用较短的视频。',
            http_status=400,
            upstream_error_type=kind,
        )
    return CloudTranscriptionError(
        '云端转写失败，请检查账号权限、额度和模型。',
        upstream_error_type=kind,
    )


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
            _check_status(response)
            if 'text/event-stream' in response.headers.get('content-type', ''):
                events = (json.loads(line[5:].strip()) for line in response.iter_lines()
                          if line.startswith('data:') and line[5:].strip() not in {'', '[DONE]'})
            else:
                response.read()
                events = [response.json()]
            for event in events:
                if event.get('code') and event['code'] not in {'Success', '200'}:
                    raise _sse_failure(event)
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
    _check_status(response)
    payload = response.json()
    segments = payload.get('segments')
    if not isinstance(segments, list):
        raise CloudTranscriptionError('转写服务没有返回字幕时间戳，请使用支持 verbose_json 的模型。')
    return segments, False


def transcribe(video: Path, output: Path | None, settings, language='auto', timeout=0):
    selection = settings.transcription
    connection = next(c for c in settings.connections if c.id == selection.connection_id)
    if not connection.api_key and connection.provider != 'compatible':
        raise CloudTranscriptionError('请先在字幕转写设置中填写 API Key。', upstream_error_type='invalid_key')
    output = Path(output) if output else video.with_suffix('.srt')
    from backend.utils.speech_recognizer import SpeechRecognizer, srt_has_cue_text
    if output.exists() and srt_has_cue_text(output):
        return output
    # Each upload is <= 150 seconds / 4.8 MB PCM, including base64 < 10 MB.
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
        from backend.services.studio.failure_identity import connection_identity
        identity = connection_identity(connection, selection.model, full=True)  # this call's connection
        try:
            # Cut every chunk first, then upload them side by side: one request after another made a
            # three-hour talk ~60 sequential round trips. Offsets come from exact sample counts.
            chunks, offset = [], 0.0
            with wave.open(str(audio), 'rb') as source:
                while True:
                    samples = source.readframes(CHUNK_SAMPLES)
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
                        except (CloudTranscriptionError, httpx.RequestError) as error:
                            if attempt == CHUNK_ATTEMPTS - 1 or not _retryable(error):
                                raise
                            time.sleep(2 * 2 ** attempt)
                    return normalize_segments(items, start, milliseconds, duration, identity)

                from concurrent.futures import ThreadPoolExecutor
                pool = ThreadPoolExecutor(max_workers=UPLOAD_WORKERS, thread_name_prefix='asr-chunk')
                try:
                    for part in pool.map(one, chunks):
                        segments.extend(part)
                finally:
                    # On a failure, chunks not yet sent are dropped instead of spending more quota.
                    pool.shutdown(wait=True, cancel_futures=True)
        except CloudTranscriptionError as exc:
            if getattr(exc, 'attribution', None) is not None or not (exc.http_status or exc.upstream_error_type):
                raise  # already snapped, or a local sentence (no key, empty audio, unsupported model)
            transport = ProviderTransportError('HTTPStatus', http_status=exc.http_status)
            if getattr(exc, 'error_code', None):
                transport.error_code = exc.error_code
            safe = _provider_failure(str(exc), transport, identity)
            safe.upstream_error_type = exc.upstream_error_type
            raise safe from None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            safe = _provider_failure(f'云端转写请求失败（HTTP {status}），请检查密钥、额度和模型权限。',
                                     ProviderTransportError(type(exc).__name__, http_status=status), identity)
            raise safe from None
        except httpx.RequestError as exc:
            raise _provider_failure('云端转写连接失败或响应格式无效，请稍后重试。',
                                    ProviderTransportError(type(exc).__name__, timed_out=isinstance(exc, httpx.TimeoutException)),
                                    identity) from None
        except ValueError as exc:
            raise _provider_failure('云端转写连接失败或响应格式无效，请稍后重试。', ModelResponseInvalid(type(exc).__name__), identity) from None
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
