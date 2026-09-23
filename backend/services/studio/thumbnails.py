"""Small, bounded, project-scoped still previews; never invoke a model or mutate a draft."""
from functools import lru_cache
from pathlib import Path
import json
import math
import subprocess
import threading

from backend.services.studio import store, jobs, intelligence
from backend.services.studio.models import Draft
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

_slots = threading.BoundedSemaphore(2)


@lru_cache(maxsize=128)
def _frame(path: str, modified_ns: int, size: int, timestamp: float) -> bytes:
    # Stat fields invalidate cached frames if a source is replaced in place.
    if not _slots.acquire(timeout=10):
        raise ValueError('缩略图生成繁忙，请稍后重试')
    try:
        result = subprocess.run([
            get_ffmpeg_path(), '-v', 'error', '-nostdin', '-ss', str(timestamp),
            '-i', path, '-frames:v', '1', '-an', '-sn',
            '-vf', 'scale=640:640:force_original_aspect_ratio=decrease',
            '-threads', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', 'pipe:1',
        ], capture_output=True, check=True, timeout=15)
        if not result.stdout.startswith(b'\xff\xd8'):
            raise ValueError('无法生成缩略图，请打开编辑器查看原片')
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise ValueError('无法生成缩略图，请打开编辑器查看原片') from None
    finally:
        _slots.release()


@lru_cache(maxsize=128)
def _duration(path: str, modified_ns: int, size: int) -> float:
    if not _slots.acquire(timeout=10):
        raise ValueError('缩略图生成繁忙，请稍后重试')
    try:
        result = subprocess.run([get_ffprobe_path(), '-v', 'error', '-show_entries',
                                 'format=duration', '-of', 'json', path],
                                capture_output=True, check=True, timeout=10)
        duration = float(json.loads(result.stdout)['format']['duration'])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError
        return duration
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        raise ValueError('无法读取视频画面') from None
    finally:
        _slots.release()


def draft_frame(project_id: str, draft_id: str, revision: int, job_id: str | None = None) -> bytes:
    state = store.read(project_id)
    raw = next((d for d in state['drafts'] if d['id'] == draft_id), None)
    if raw is None:
        raise FileNotFoundError('草稿不存在')
    draft = Draft.model_validate(raw)
    if draft.revision != revision:
        raise store.ConflictError('草稿版本已更新，请刷新缩略图')
    if job_id:
        job = next((j for j in state['jobs'] if j['job_id'] == job_id and j['draft_id'] == draft_id
                    and j['revision'] == revision and j['status'] == 'completed'), None)
        if job is None:
            raise FileNotFoundError('当前版本没有此导出成片')
        # Resolve the expected project-owned output, never a saved result.path.
        import re
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('无效导出 ID')
        video = store.directory(project_id) / 'output' / 'studio' / f'{job_id}.mp4'

    else:
        video = jobs.source(project_id)

    video = Path(video)
    stat = video.stat()
    if not stat.st_size:
        raise ValueError('无法读取视频画面')
    duration = _duration(str(video.resolve()), stat.st_mtime_ns, stat.st_size)
    if job_id:
        timestamp = min(.6, duration / 2)
    else:
        intelligence.validate_scenes(draft.scenes, duration)
        scene = draft.scenes[0]
        timestamp = scene.start + min(.1, (scene.end - scene.start) / 2)
    return _frame(str(video.resolve()), stat.st_mtime_ns, stat.st_size, round(timestamp, 3))
