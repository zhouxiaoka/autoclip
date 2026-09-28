"""Explicit, bounded local H.264 preview conversion; source media is immutable."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import subprocess
import threading
import uuid

from backend.core.sentry_setup import capture_studio_exception
from backend.services.studio import jobs, store
from backend.utils.ffmpeg_utils import get_ffmpeg_path

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='source-preview')
_lock = threading.RLock()
_states = {}


def _paths(project_id):
    source = jobs.source(project_id)
    stat = source.stat()
    identity = f'{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}'
    token = hashlib.sha256(identity.encode()).hexdigest()[:24]
    output = store.directory(project_id) / 'output' / 'preview' / f'{token}.mp4'
    return source, output, token


def status(project_id):
    _, output, token = _paths(project_id)
    with _lock:
        if output.is_file() and output.stat().st_size:
            return {'status': 'completed', 'version': token}
        current = _states.get(token, {'status': 'idle'})
        # A deleted cache must be regeneratable in the same backend process.
        return {'status': 'idle'} if current['status'] == 'completed' else dict(current)


def start(project_id):
    with _lock:
        source, output, token = _paths(project_id)
        current = status(project_id)
        if current['status'] in ('queued', 'running', 'completed'):
            return current
        if any(s['status'] in ('queued', 'running') for s in _states.values()):
            raise ValueError('已有兼容预览正在生成，请稍后重试')
        while len(_states) >= 64:
            del _states[next(iter(_states))]
        _states[token] = {'status': 'queued'}
        try:
            _executor.submit(_convert, source, output, token)
        except Exception:
            _states.pop(token, None)
            raise ValueError('兼容预览未能启动，请重试') from None
        return dict(_states[token])


def ready_file(project_id):
    _, output, _ = _paths(project_id)
    if not output.is_file() or not output.stat().st_size:
        raise FileNotFoundError('兼容预览尚未生成')
    return output


def _convert(source: Path, output: Path, token: str):
    temporary = output.with_name(f'{output.stem}.{uuid.uuid4().hex}.tmp.mp4')
    with _lock:
        _states[token] = {'status': 'running'}
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            get_ffmpeg_path(), '-nostdin', '-v', 'error', '-i', str(source),
            '-map', '0:v:0', '-map', '0:a:0?', '-sn', '-dn',
            '-vf', "scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p',
            '-threads', '2', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
            '-y', str(temporary),
        ], capture_output=True, check=True, timeout=900)
        if not temporary.is_file() or not temporary.stat().st_size:
            raise ValueError('empty preview')
        if not source.exists() or not output.parent.exists():
            raise FileNotFoundError('source removed')
        temporary.replace(output)
        with _lock:
            _states[token] = {'status': 'completed', 'version': token}
    except Exception as error:
        capture_studio_exception(error, 'render')
        with _lock:
            _states[token] = {'status': 'failed', 'error': '兼容预览生成失败，请检查视频文件后重试'}
    finally:
        temporary.unlink(missing_ok=True)
