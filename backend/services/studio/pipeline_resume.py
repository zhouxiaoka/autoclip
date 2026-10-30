"""Resume content pipeline from subtitle / step artifacts when stamps match."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STAMP_NAME = 'pipeline_stamp.json'

# Ordered model steps for the legacy four-step path (clips_only falls back here).
STEP_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ('step1', 'step1_outline.json'),
    ('step2', 'step2_timeline.json'),
    ('step3', 'step3_high_score_clips.json'),
    ('step4', 'step4_titles.json'),
)

RESUMED_FROM_VALUES = ('none', 'subtitle', 'step1', 'step2', 'step3', 'step4')


def source_fingerprint(video: Path) -> dict[str, Any]:
    video = Path(video)
    st = video.stat()
    return {
        'size': int(st.st_size),
        'mtime_ns': int(getattr(st, 'st_mtime_ns', int(st.st_mtime * 1_000_000_000))),
        'name': video.name,
    }


# P2 #12: workspace() polls resume_point often; avoid re-reading prompt files
# when path+mtime are unchanged. Keyed by frozenset of (key:path, mtime_ns).
_PROMPT_HASH_CACHE: dict[frozenset[tuple[str, int]], str] = {}


def clear_prompt_hash_cache() -> None:
    """Test helper / explicit invalidation."""
    _PROMPT_HASH_CACHE.clear()


def _prompt_file_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return -1


def _read_prompt_file_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:  # noqa: BLE001
        return str(path).encode('utf-8', errors='replace')


def prompt_hash(prompt_files: dict | None) -> str:
    files = prompt_files or {}
    entries: list[tuple[str, int]] = []
    ordered: list[tuple[str, Path]] = []
    for key in sorted(files.keys()):
        path = Path(files[key])
        entries.append((f'{key}:{path}', _prompt_file_mtime_ns(path)))
        ordered.append((key, path))
    cache_key = frozenset(entries)
    cached = _PROMPT_HASH_CACHE.get(cache_key)
    if cached is not None:
        return cached
    h = hashlib.sha256()
    for key, path in ordered:
        data = _read_prompt_file_bytes(path)
        h.update(key.encode('utf-8'))
        h.update(b'\0')
        h.update(data)
        h.update(b'\0')
    digest = h.hexdigest()[:32]
    _PROMPT_HASH_CACHE[cache_key] = digest
    return digest


def current_model_stamp(prompt_files: dict | None = None) -> dict[str, Any]:
    provider, model = '', ''
    try:
        from backend.core.llm_manager import get_llm_manager
        info = get_llm_manager().get_current_provider_info() or {}
        provider = str(info.get('provider') or '')
        model = str(info.get('model') or '')
    except Exception as error:  # noqa: BLE001
        logger.debug('pipeline stamp provider unavailable: %s', type(error).__name__)
    return {
        'provider': provider,
        'model': model,
        'prompt_hash': prompt_hash(prompt_files),
    }


def read_stamp(metadata_dir: Path) -> dict[str, Any] | None:
    path = Path(metadata_dir) / STAMP_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def write_stamp(metadata_dir: Path, *, video: Path, prompt_files: dict | None = None,
                extra: dict | None = None) -> dict[str, Any]:
    metadata_dir = Path(metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    prev = read_stamp(metadata_dir) or {}
    try:
        source = source_fingerprint(video)
    except OSError:
        # Tests / early failure paths may call write_stamp before the video exists.
        # Keep prior source fingerprint when present; otherwise omit source.
        source = (prev.get('source') if isinstance(prev.get('source'), dict) else None)
    stamp = {
        **({'source': source} if source is not None else {}),
        **current_model_stamp(prompt_files),
    }
    # P1 #6: keep srt_origin across step refreshes unless extra overrides it.
    if 'srt_origin' in prev and not (extra and 'srt_origin' in extra):
        stamp['srt_origin'] = prev['srt_origin']
    if extra:
        stamp.update(extra)
    (metadata_dir / STAMP_NAME).write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding='utf-8')
    return stamp


def record_srt_origin(metadata_dir: Path, origin: str, *, video: Path | None = None) -> dict[str, Any]:
    """Mark where raw/input.srt came from (asr | attached | platform).

    Called when the file is placed (upload / platform fetch) or right after ASR
    succeeds. clear_pipeline_cache only deletes the srt when origin == 'asr'.
    """
    metadata_dir = Path(metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    stamp = read_stamp(metadata_dir) or {}
    stamp['srt_origin'] = origin
    if video is not None:
        try:
            stamp['source'] = source_fingerprint(video)
        except OSError:
            pass
    (metadata_dir / STAMP_NAME).write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding='utf-8')
    return stamp


def source_matches(stamp: dict | None, video: Path) -> bool:
    if not stamp or not isinstance(stamp.get('source'), dict):
        return False
    try:
        current = source_fingerprint(video)
    except OSError:
        return False
    saved = stamp['source']
    return int(saved.get('size') or -1) == current['size'] and int(saved.get('mtime_ns') or -1) == current['mtime_ns']


def model_matches(stamp: dict | None, prompt_files: dict | None = None) -> bool:
    if not stamp:
        return False
    current = current_model_stamp(prompt_files)
    return (
        str(stamp.get('provider') or '') == current['provider']
        and str(stamp.get('model') or '') == current['model']
        and str(stamp.get('prompt_hash') or '') == current['prompt_hash']
    )


def srt_reusable(video: Path, srt: Path | None, stamp: dict | None) -> bool:
    """True when input.srt exists and matches the stamped source (or legacy: srt exists, no stamp)."""
    if not srt or not Path(srt).is_file():
        return False
    if stamp is None:
        # Legacy projects without a stamp: keep prior behavior (use existing srt).
        return True
    return source_matches(stamp, Path(video))


def step_artifact_path(metadata_dir: Path, step: str) -> Path:
    for name, filename in STEP_ARTIFACTS:
        if name == step:
            return Path(metadata_dir) / filename
    raise KeyError(step)


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def first_missing_step(metadata_dir: Path) -> str | None:
    """Return the first step id whose artifact is missing or empty; None if all present."""
    metadata_dir = Path(metadata_dir)
    for step, filename in STEP_ARTIFACTS:
        path = metadata_dir / filename
        if not path.is_file():
            return step
        try:
            data = load_json(path)
        except Exception:  # noqa: BLE001
            return step
        if data in (None, [], {}, ''):
            return step
    return None


def decide_resume(
    *,
    video: Path,
    srt: Path | None,
    metadata_dir: Path,
    prompt_files: dict | None = None,
    fresh: bool = False,
    clips_only: bool = False,
) -> dict[str, Any]:
    """Decide what to skip.

    Returns:
      resumed_from: none|subtitle|step1|…
      skip_transcription: bool
      start_step: step1|step2|step3|step4|done|None (None = run one-pass / from step1)
      reuse_steps: frozenset of step ids whose artifacts can be loaded as-is

    When clips_only=True (Studio one-pass), a non-empty step4_titles.json plus a
    matching stamp means start_step='done' even if step1–3 were never written.
    """
    metadata_dir = Path(metadata_dir)
    video = Path(video)
    if fresh:
        return {
            'resumed_from': 'none',
            'skip_transcription': False,
            'start_step': 'step1',
            'reuse_steps': frozenset(),
            'stamp_ok': False,
        }

    stamp = read_stamp(metadata_dir)
    skip_transcription = srt_reusable(video, srt, stamp)
    stamp_ok = model_matches(stamp, prompt_files)

    if not stamp_ok:
        # P1 #7: invalidate stale step2/3/4 from the previous model/prompt.
        # Keep SRT + stamp (stamp is rewritten after the next successful step).
        clear_step_artifacts(metadata_dir)

    if not skip_transcription:
        return {
            'resumed_from': 'none',
            'skip_transcription': False,
            'start_step': 'step1',
            'reuse_steps': frozenset(),
            'stamp_ok': stamp_ok,
        }

    if not stamp_ok:
        # X2 switched model (or prompt changed): keep subtitle, re-run all model steps.
        return {
            'resumed_from': 'subtitle',
            'skip_transcription': True,
            'start_step': 'step1',
            'reuse_steps': frozenset(),
            'stamp_ok': False,
        }

    # P2 #11: Studio clips_only one-pass only writes step4_titles.json. If that
    # artifact is present and the stamp matches, model work is done — do not ask
    # first_missing_step (which would report step1 missing and degrade resume to
    # 「只从字幕继续」). Four-step fallback mid-run still falls through below.
    if clips_only:
        step4_path = metadata_dir / 'step4_titles.json'
        step4_ok = False
        if step4_path.is_file():
            try:
                data = load_json(step4_path)
                step4_ok = data not in (None, [], {}, '')
            except Exception:  # noqa: BLE001
                step4_ok = False
        if step4_ok:
            return {
                'resumed_from': 'step4',
                'skip_transcription': True,
                'start_step': 'done',
                'reuse_steps': frozenset({'step4'}),
                'stamp_ok': True,
            }

    missing = first_missing_step(metadata_dir)
    if missing is None:
        # All four legacy steps present — model work complete.
        reuse = frozenset(name for name, _ in STEP_ARTIFACTS)
        return {
            'resumed_from': 'step4',
            'skip_transcription': True,
            'start_step': 'done',
            'reuse_steps': reuse,
            'stamp_ok': True,
        }

    # Have artifacts for every step before `missing`.
    reuse = []
    for name, _ in STEP_ARTIFACTS:
        if name == missing:
            break
        reuse.append(name)

    if not reuse:
        resumed = 'subtitle'
    else:
        resumed = missing  # continue from the first missing/failed step

    return {
        'resumed_from': resumed,
        'skip_transcription': True,
        'start_step': missing,
        'reuse_steps': frozenset(reuse),
        'stamp_ok': True,
    }


def clear_step_artifacts(metadata_dir: Path) -> None:
    """P1 #7: drop model step products only; keep stamp and SRT.

    Used when the stamp's provider/model/prompt no longer matches so a retry
    cannot treat leftover step2/3/4 from the old model as complete after step1
    rewrites the stamp.
    """
    metadata_dir = Path(metadata_dir)
    if not metadata_dir.is_dir():
        return
    for _, filename in STEP_ARTIFACTS:
        path = metadata_dir / filename
        if path.is_file():
            path.unlink()
    scored = metadata_dir / 'step3_all_scored.json'
    if scored.is_file():
        scored.unlink()


def clear_pipeline_cache(metadata_dir: Path, *, raw_dir: Path | None = None) -> None:
    """「从头重做」: drop step artifacts and stamp; only delete ASR-generated input.srt.

    P1 #6: user-attached / platform captions must survive a fresh restart. Read
    srt_origin before unlinking the stamp; unlink raw/input.srt only when it is
    ``asr``. Missing / attached / platform / anything else → keep the file.
    """
    metadata_dir = Path(metadata_dir)
    stamp = read_stamp(metadata_dir) if metadata_dir.is_dir() else None
    srt_origin = str((stamp or {}).get('srt_origin') or '')
    clear_step_artifacts(metadata_dir)
    if metadata_dir.is_dir():
        stamp_path = metadata_dir / STAMP_NAME
        if stamp_path.is_file():
            stamp_path.unlink()
    if raw_dir is not None and srt_origin == 'asr':
        srt = Path(raw_dir) / 'input.srt'
        if srt.is_file():
            srt.unlink()


def resume_point_for_project(project_id: str) -> dict[str, Any] | None:
    """Live workspace hint for FailureActions button copy. None → plain 「重试」."""
    try:
        from backend.core.path_utils import get_project_directory
        from backend.services.publish_export import find_source_video
        video = find_source_video(project_id)
        if video is None:
            return None
        project_dir = get_project_directory(project_id)
        metadata_dir = project_dir / 'metadata'
        srt = Path(video).parent / 'input.srt'
        prompt_files = None
        try:
            from backend.core.shared_config import get_prompt_files
            prompt_files = get_prompt_files()
        except Exception:  # noqa: BLE001
            prompt_files = None
        # Studio always runs clips_only; pass True so step4-only one-pass can
        # surface as done / step resume rather than 「只从字幕继续」 (P2 #11).
        decision = decide_resume(
            video=Path(video),
            srt=srt if srt.is_file() else None,
            metadata_dir=metadata_dir,
            prompt_files=prompt_files,
            fresh=False,
            clips_only=True,
        )
    except Exception as error:  # noqa: BLE001
        logger.debug('resume_point unavailable: %s', type(error).__name__)
        return None

    point = decision['resumed_from']
    if point == 'none':
        return None
    if point == 'subtitle':
        return {'point': 'subtitle', 'label': '已有字幕，从分析开始'}
    if point.startswith('step') and point[-1:].isdigit():
        n = point[-1]
        return {'point': point, 'label': f'从第 {n} 步继续'}
    return {'point': point, 'label': '从断点继续'}
