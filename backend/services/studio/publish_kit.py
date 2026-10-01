"""Publish kit of an output variant: designed cover, post copy, and the zip that bundles them.

Covers are designed right after a variant renders (cover_design: local, free, matches the video).
An AI cover made from the output card (services/cover.py, clip id `studio-<job>`) takes
precedence wherever a cover is used — publishing reads the same files.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AI_METHODS = ('model', 'model_bg')


def clip_id(job_id: str) -> str:
    return f'studio-{job_id}'


def _publish_slot(strategy_id: str) -> str:
    """The orientation slot services/cover.py keeps for publishing (vertical 'douyin' / landscape 'bilibili')."""
    from backend.services.platform_strategy import platform_strategy
    return 'bilibili' if platform_strategy(strategy_id).aspect == 'landscape' else 'douyin'


def kit_cover_path(project_id: str, job_id: str, strategy_id: str) -> Path:
    from backend.services import cover
    return cover.cover_dir(project_id, clip_id(job_id)) / f'kit-{strategy_id}.jpg'


def cover_file(project_id: str, job_id: str, strategy_id: str) -> tuple[Path | None, str | None]:
    """(path, 'ai' | 'design') of the cover to show and ship: an AI cover first, else the design."""
    from backend.services import cover
    slot = _publish_slot(strategy_id)
    ai = cover.cover_path(project_id, clip_id(job_id), slot)
    meta = cover.read_cover_meta(project_id, clip_id(job_id), slot) or {}
    if ai.is_file() and meta.get('method') in AI_METHODS:
        return ai, 'ai'
    designed = kit_cover_path(project_id, job_id, strategy_id)
    return (designed, 'design') if designed.is_file() else (None, None)


def design_cover(project_id: str, video: Path, draft: dict[str, Any], job_id: str, strategy_id: str, post_title: str) -> bool:
    """Design and store the variant's cover; also fill the publish slot unless an AI cover is there."""
    from backend.services import cover
    from backend.services.publish_export import _probe
    from backend.services.studio import cover_design as cd
    scene = draft['scenes'][0]
    info = _probe(video)
    source_w, source_h = int(info.get('width') or 1920), int(info.get('height') or 1080)
    at, position = cd.frame_time(scene)
    centre = cd.speaker_centre(position, draft.get('layout') or 'crop', source_w, source_h)
    frame = cover.extract_frame_jpeg(video, at_sec=at, max_width=1920)
    packaging = draft.get('packaging') or {}
    lines, accent = cd.title_lines_for(draft, post_title or draft.get('title', ''), strategy_id)
    width, height = cd.size_for(strategy_id, source_w, source_h)
    data = cd.design(frame, width=width, height=height, title_lines=lines, accent_line=accent,
                     palette=packaging.get('palette'), speaker=cd.cover_speaker(packaging), crop_centre=centre)
    kit_cover_path(project_id, job_id, strategy_id).write_bytes(data)
    slot = _publish_slot(strategy_id)
    meta = cover.read_cover_meta(project_id, clip_id(job_id), slot) or {}
    if meta.get('method') not in AI_METHODS and cd.size_for(strategy_id, source_w, source_h)[1] != 1440:
        # Xiaohongshu's 3:4 design stays kit-only; the vertical publish slot expects 9:16.
        cover.cover_path(project_id, clip_id(job_id), slot).write_bytes(data)
        cover.write_cover_meta(project_id, clip_id(job_id), slot, {'method': 'design', 'title': ' '.join(lines)})
    return True


def caption_text(post: dict[str, Any]) -> str:
    tags = ' '.join(f'#{tag}' for tag in post.get('tags') or [])
    return '\n\n'.join(part for part in (post.get('title', ''), post.get('description', ''), tags) if part)


def _safe_name(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\n\r\t]+', ' ', text).strip()[:60] or 'autoclip'


def kit_zip(video: Path, cover: Path | None, post: dict[str, Any], platform_label: str) -> tuple[bytes, str]:
    """(zip bytes, file name): the video, its cover and the post copy for one platform."""
    name = _safe_name(post.get('title') or video.stem)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:  # mp4/jpg are already compressed
        archive.write(video, f'{name}.mp4')
        if cover is not None:
            archive.write(cover, f'{name} 封面.jpg')
        archive.writestr(f'{name} 发布文案.txt', f'平台：{platform_label}\n\n{caption_text(post)}\n')
    return buffer.getvalue(), f'{name}.zip'
