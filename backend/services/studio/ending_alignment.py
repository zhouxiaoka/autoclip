"""Bounded, local acoustic evidence for an already selected sentence ending."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import unicodedata

from backend.core import project_cancellation
from backend.core.job_budget import JobDurationExceeded, clip_job_read_timeout, ensure_clip_job_budget
from backend.services.studio.boundaries import ClipBounds

MAX_DRIFT = 1.5
TOTAL_SECONDS = 45


def tokens(text):
    return re.findall(r'[\u3400-\u9fff\u3040-\u30ff]|[^\W_]+', unicodedata.normalize('NFKC', text).casefold())


def align_ending(rows, bound, words, silences, *, limit=float('inf')):
    anchor = getattr(bound, 'end_anchor', None)
    fallback = ClipBounds(*bound, needs_review=True, end_anchor=anchor)
    if not anchor or not words:
        return fallback
    row, offset = anchor
    if not 0 <= row < len(rows) or not 0 < offset <= len(rows[row][2]):
        return fallback
    phrase = tokens(rows[row][2][:offset])[-12:]
    if len(phrase) < 3:
        return fallback
    flattened, clock = [], -1.
    for word in words:
        try:
            start, end = word['start'], word['end']
            if any(not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t) for t in (start, end)):
                return fallback
            if not 0 <= start <= end or start < clock - .01:
                return fallback
            clock = end
            probability = word.get('probability', 1.)
            if not isinstance(probability, (int, float)) or not math.isfinite(probability):
                return fallback
            flattened.extend((token, start, end, probability) for token in tokens(word['text']))
        except (KeyError, TypeError):
            return fallback
    estimate = rows[row][0] + (rows[row][1] - rows[row][0]) * offset / len(rows[row][2])
    flattened = [w for w in flattened if estimate - 24 <= w[1] <= estimate + 4]
    sequence = [word[0] for word in flattened]
    matches = [i for i in range(len(sequence) - len(phrase) + 1) if sequence[i:i+len(phrase)] == phrase]
    if len(matches) != 1:
        return fallback
    last = matches[0] + len(phrase) - 1
    matched = flattened[matches[0]:last+1]
    if any(word[1] >= word[2] or word[3] < .25 for word in matched):
        return fallback
    spoken_end = flattened[last][2]
    estimate = rows[row][0] + (rows[row][1] - rows[row][0]) * offset / len(rows[row][2])
    if abs(spoken_end - estimate) > MAX_DRIFT:
        return fallback
    next_start = flattened[last+1][1] if last+1 < len(flattened) else spoken_end + .4
    ceiling = min(limit, next_start - .02, spoken_end + .35)
    if ceiling < spoken_end + .02:
        return fallback
    cut = min(spoken_end + .08, ceiling)
    if silences is not None:
        pauses = [(a,b) for a,b in silences(spoken_end-.1, min(spoken_end+1, next_start+.1))
                  if a <= ceiling and b >= spoken_end+.02 and a <= spoken_end+.35]
        if pauses:
            a,b = min(pauses, key=lambda gap:abs(gap[0]-spoken_end))
            cut = min(ceiling, max(spoken_end+.02, a) + min(.08, (b-max(a,spoken_end))/2))
    if cut <= bound[0] or cut > limit:
        return fallback
    result = ClipBounds(bound[0], round(cut,3), needs_review=getattr(bound,'needs_review',False),
                        end_anchor=anchor, word_aligned=True)
    result.caption_end = {'row_start': rows[row][0], 'row_end': rows[row][1],
                          'text_sha256': hashlib.sha256(rows[row][2].encode()).hexdigest(),
                          'offset': offset, 'audio_end': result[1]}
    return result


def project_words(project_id):
    from backend.services.publish_export import find_source_srt
    from backend.utils.word_timing import load_word_timing
    srt = find_source_srt(project_id)
    segments = load_word_timing(srt) if srt else None
    return [word for segment in segments for word in segment['words']] if segments else None


def local_words(video, lo, hi, *, timeout=TOTAL_SECONDS):
    """Only use an installed local runtime/model. Never download or call cloud ASR."""
    from backend.services import whisper_runtime
    if not whisper_runtime.is_installed():
        return None
    from backend.services.whisper_model_manager import get_model_manager
    from backend.utils.speech_recognizer import configured_whisper_model
    model = get_model_manager().get_local_model_path(configured_whisper_model())
    if model is None:
        return None
    from backend.services.studio.qa.schedule import _interpreter
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    executable = _interpreter()
    if Path(executable).name.lower().startswith('autoclip'):
        return None  # no packaged Python available; never recursively launch the backend
    root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               PYTHONPATH=os.pathsep.join([str(root), str(whisper_runtime.get_install_dir()), env.get('PYTHONPATH','')]))
    result = project_cancellation.run([
        executable, '-m', 'backend.services.studio.ending_alignment_worker', str(model), str(video),
        str(max(0,lo)), str(min(24,hi-max(0,lo))), get_ffmpeg_path(),
    ], capture_output=True, timeout=clip_job_read_timeout(timeout), env=env, cwd=root, check=True)
    value = json.loads(result.stdout)
    return value['words'] if isinstance(value,dict) and isinstance(value.get('words'),list) else None


def align_project(project_id, rows, bounds, *, silences=None, limits=None):
    from backend.services.studio.jobs import source
    words = project_words(project_id)
    video = source(project_id)
    started = time.monotonic()
    results = []
    for index, bound in enumerate(bounds):
        project_cancellation.checkpoint(project_id)
        ensure_clip_job_budget()
        available = words
        anchor = getattr(bound,'end_anchor',None)
        remaining = TOTAL_SECONDS - (time.monotonic()-started)
        if available is None and anchor and remaining > .5:
            row, offset = anchor
            estimate = rows[row][0] + (rows[row][1]-rows[row][0])*offset/len(rows[row][2])
            try:
                available = local_words(video,max(0,estimate-18),estimate+3,timeout=remaining)
            except JobDurationExceeded:
                raise
            except (OSError, ValueError, subprocess.SubprocessError):
                available = None
        limit = limits[index] if limits is not None else float('inf')
        results.append(align_ending(rows,bound,available,silences,limit=limit))
    return results
