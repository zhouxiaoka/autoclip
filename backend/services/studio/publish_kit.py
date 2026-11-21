"""Publish kit of an output variant: designed cover, post copy, and the zip that bundles them.

Covers are designed right after a variant renders (cover_design: local, free, matches the video).
An AI cover made from the output card (services/cover.py, clip id `studio-<job>`) takes
precedence wherever a cover is used — publishing reads the same files.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AI_METHODS = ('model', 'model_bg')


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    designed = kit_cover_path(project_id, job_id, strategy_id)
    # A portrait publish-slot image cannot replace the note's 3:4 cover.
    if ai.is_file() and meta.get('method') in AI_METHODS and not (strategy_id == 'xiaohongshu' and designed.is_file()):
        return ai, 'ai'
    return (designed, 'design') if designed.is_file() else (None, None)


def design_cover(project_id: str, video: Path, draft: dict[str, Any], job_id: str, strategy_id: str, post_title: str) -> bool:
    """Design and store the variant's cover; also fill the publish slot unless an AI cover is there."""
    from backend.services import cover
    from backend.services.publish_export import _probe
    from backend.services.studio import cover_design as cd
    scene = draft['scenes'][0]
    info = _probe(video)
    source_w, source_h = int(info.get('width') or 1920), int(info.get('height') or 1080)
    from backend.services.studio import store
    listing = (store.read(project_id).get('source_meta') or {}).get('title', '')
    frame, centre, guest_on_screen = cd.pick_frame(video, scene, _scene_rows(project_id, scene), draft.get('packaging') or {},
                                                   guest_hint=f'视频标题「{listing}」里的主角' if listing else '')
    if centre is None:
        _, position = cd.frame_time(scene)
        centre = cd.speaker_centre(position, draft.get('layout') or 'crop', source_w, source_h)
    packaging = draft.get('packaging') or {}
    lines, accent = cd.title_lines_for(draft, post_title or draft.get('title', ''), strategy_id)
    width, height = cd.size_for(strategy_id, source_w, source_h)
    # Name the guest only when the chosen frame is the guest's shot, never on a host frame.
    speaker = cd.cover_speaker(packaging) if guest_on_screen else None
    data = cd.design(frame, width=width, height=height, title_lines=lines, accent_line=accent,
                     palette=packaging.get('palette'), speaker=speaker, crop_centre=centre)
    _atomic_write(kit_cover_path(project_id, job_id, strategy_id), data)
    # The chosen frame is the AI cover's reference (same person, same moment).
    _atomic_write(frame_path(project_id, job_id, strategy_id), frame)
    _atomic_write(cd_meta_path(project_id, job_id, strategy_id), json.dumps({'guest': guest_on_screen, 'name': (speaker or ('', ''))[0],
                                                                          'role': (speaker or ('', ''))[1],
                                                                          'lines': lines, 'accent': accent, 'palette': packaging.get('palette')},
                                                                         ensure_ascii=False).encode('utf-8'))
    slot = _publish_slot(strategy_id)
    meta = cover.read_cover_meta(project_id, clip_id(job_id), slot) or {}
    if meta.get('method') not in AI_METHODS and cd.size_for(strategy_id, source_w, source_h)[1] != 1440:
        # Xiaohongshu's 3:4 design stays kit-only; the vertical publish slot expects 9:16.
        _atomic_write(cover.cover_path(project_id, clip_id(job_id), slot), data)
        cover.write_cover_meta(project_id, clip_id(job_id), slot, {'method': 'design', 'title': ' '.join(lines)})
    return True


def _scene_rows(project_id: str, scene: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from backend.pipeline.quality import to_seconds
        from backend.services.publish_export import _load_srt_entries
        rows = [{'start': to_seconds(e['start_time']), 'end': to_seconds(e['end_time']), 'text': str(e.get('text') or '')}
                for e in _load_srt_entries(project_id)]
    except Exception:  # noqa: BLE001 - without rows every shot counts as the guest's
        return []
    return [row for row in rows if row['end'] > scene['start'] and row['start'] < scene['end']]


def frame_path(project_id: str, job_id: str, strategy_id: str) -> Path:
    from backend.services import cover
    return cover.cover_dir(project_id, clip_id(job_id)) / f'frame-{strategy_id}.jpg'


def cd_meta_path(project_id: str, job_id: str, strategy_id: str) -> Path:
    from backend.services import cover
    return cover.cover_dir(project_id, clip_id(job_id)) / f'kit-{strategy_id}.json'


def reference_prompt(strategy_id: str, lines: list[str], palette: str | None = None, *, subtitle='', badge='') -> str:
    from backend.services.studio.packaging_render import PALETTES
    portrait = strategy_id not in ('bilibili', 'youtube_long', 'original')
    aspect = '3:4' if strategy_id == 'xiaohongshu' else '9:16' if portrait else '16:10' if strategy_id == 'bilibili' else '16:9'
    composition = ('以头肩近景构图，保留完整头顶和下巴，顺着视线方向留空间。'
                   '标题放在头顶上方原场景的暗部，字与发际线拉开距离。'
                   if portrait else '让主体和标题分别占据画面两侧；保持视线前方的空间，把标题放在原场景较安静的一侧。')
    title = ''.join(lines) if all(not re.search(r'[A-Za-z]', line) for line in lines) else ' '.join(lines)
    accent = PALETTES.get(palette or 'azure', PALETTES['azure'])[0]
    number = re.search(r'\d+(?:[.,]\d+)*', title)
    emphasis = f'仅把标题中的 {number.group()} 设为' if number else '仅给一个关键词使用'
    brief = [
        f'为随附的视频帧设计一张可直接发布的 {aspect} 专题封面。在同一张图里完成摄影构图、调色和最终排字。',
        f'主标题原文（只出现一次）：{title}',
        '把观众的注意力先引到画面主体，再读完这一句标题。访谈封面以参考帧中正在回答的人为主角；保留他的表情、视线、发型、衣着和身后的现场。素材没有人物时，保留画面中原本的主体。',
        composition + '保留背景里的光源、物体轮廓和冷暖层次。边缘需要扩展时延续同一场景。不要换成影棚、纯白背景或插画。',
        f'标题用粗无衬线字，短标题排一行，空间不足时按词意分成两行。字色用暖白，{emphasis} #{accent}。文字贴合原场景明暗，四周留出安全边距，脸部和发际线保持清晰。',
        '逐字保留标题中的数字、单位和标点。标题不要以副标题、英文翻译或背景装饰的形式重复。不要添加姓名、引号、平台标识、尺寸说明或水印。',
    ]
    if subtitle:
        brief.append('指定副标题（只出现一次）：' + subtitle)
    if badge:
        brief.append('指定角标（只出现一次）：' + badge)
    brief.append('交付一张已经排好字的完整封面。缩到手机卡片大小时，仍要能认出主体并一眼读清标题。')
    return '\n'.join(brief)


def _title_ok(image: bytes, lines: list[str]) -> bool | None:
    """Whether the generated cover shows the title exactly (vision model), None when it cannot check."""
    import base64
    from backend.services.studio import intelligence
    if not intelligence.ready():
        return None
    try:
        from backend.core import llm_usage
        from backend.services.studio.vision_settings import effective
        with llm_usage.stage('cover_check'):
            answer = intelligence.vision_call([
                {'type': 'text', 'text': '读出这张封面上的标题文字，原样返回，只返回 JSON：{"text":"..."}'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}}],
                {**effective(), 'quick_screening': True}) or {}
    except Exception:  # noqa: BLE001
        return None
    squash = lambda text: re.sub(r'[\s\W_]+', '', str(text)).lower()  # noqa: E731
    expected = squash(''.join(lines))
    return bool(expected and squash(answer.get('text', '')).count(expected) == 1)


def redesign_local_cover(project_id: str, job_id: str, strategy_id: str) -> None:
    """Render a new platform-sized design from the saved frame or the finished video."""
    from backend.services import cover
    from backend.services.studio import cover_design as cd, store
    from backend.services.studio.packaging_render import PALETTES

    state = store.read(project_id)
    job = next(row for row in state['jobs'] if row['job_id'] == job_id)
    result = job.get('result') or {}
    width, height = cd.size_for(strategy_id, result.get('width') or 1920, result.get('height') or 1080)
    saved_frame = frame_path(project_id, job_id, strategy_id)
    meta_path = cd_meta_path(project_id, job_id, strategy_id)
    meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.is_file() else {}
    revision = int(meta.get('layout_version') or 0) + 1
    from backend.services.studio.publishing import cover_source_frame
    guest = None
    centre = None
    try:
        frame, centre = cover_source_frame(project_id, job_id, revision)
    except (FileNotFoundError, cover.CoverError, OSError, ValueError):
        if saved_frame.is_file():
            frame = saved_frame.read_bytes()
            if meta.get('guest') and meta.get('name'):
                guest = (meta['name'], meta.get('role', ''))
        else:
            video, default_at = cover.resolve_clip_frame(project_id, clip_id(job_id))
            duration = result.get('duration') or 0
            at = duration * (0.35, 0.58, 0.72)[(revision - 1) % 3] if duration > 0 else default_at
            frame = cover.extract_frame_jpeg(video, at_sec=at)
    palettes = list(PALETTES)
    previous = meta.get('palette') or 'azure'
    palette = palettes[(palettes.index(previous) + 1) % len(palettes)] if previous in palettes else 'azure'
    if not meta.get('lines'):
        meta['lines'], meta['accent'] = cd.title_lines_for(job.get('snapshot') or {}, job['title'], strategy_id)
    jpeg = cd.design(frame, width=width, height=height, title_lines=meta['lines'], accent_line=meta['accent'],
                     palette=palette, speaker=guest, crop_centre=centre)
    _atomic_write(kit_cover_path(project_id, job_id, strategy_id), jpeg)
    _atomic_write(meta_path, json.dumps({**meta, 'palette': palette, 'layout_version': revision}, ensure_ascii=False).encode('utf-8'))
    if strategy_id != 'xiaohongshu':
        slot = _publish_slot(strategy_id)
        _atomic_write(cover.cover_path(project_id, clip_id(job_id), slot), jpeg)
        cover.write_cover_meta(project_id, clip_id(job_id), slot, {'method': 'design', 'title': ' '.join(meta['lines'])})


def ai_cover(project_id: str, job_id: str, strategy_id: str) -> bool:
    """Generate the AI cover for one variant from its designed cover's frame and title; True when stored."""
    from PIL import Image
    from backend.core.image_providers import ImageRequest, generate_image
    from backend.services import cover
    from backend.services.studio import cover_design as cd
    cfg = cover.load_config()
    frame_file, meta_file = frame_path(project_id, job_id, strategy_id), cd_meta_path(project_id, job_id, strategy_id)
    if not (cfg.enabled and cfg.configured):
        return False
    if meta_file.is_file():
        meta = json.loads(meta_file.read_text(encoding='utf-8'))
    else:
        from backend.services.studio import store
        job = next((j for j in store.read(project_id)['jobs'] if j['job_id'] == job_id), None)
        if not job:
            return False
        lines, accent = cd.title_lines_for(job.get('snapshot') or {}, job['title'], strategy_id)
        meta = {'lines': lines, 'accent': accent}
    width, height = cd.size_for(strategy_id)
    reference = frame_file.read_bytes() if cfg.allow_send_frame and frame_file.is_file() else None
    if reference is None:
        return False
    prompt = reference_prompt(strategy_id, meta['lines'], meta.get('palette'))
    request = ImageRequest(prompt=prompt, width=width, height=height, reference=reference, model=cfg.model)
    image = generate_image(provider=cfg.provider, api_key=cfg.api_key, base_url=cfg.base_url, request=request)
    with Image.open(io.BytesIO(image)) as artwork:
        if not cd.keeps_scene(reference, artwork):
            return False
    jpeg = cover.delivery_jpeg(image)
    if _title_ok(jpeg, meta['lines']) is False:
        return False
    _atomic_write(kit_cover_path(project_id, job_id, strategy_id), jpeg)
    if height != 1440:  # the publish slot is 9:16 / 16:9; Xiaohongshu's 3:4 stays kit-only
        slot = _publish_slot(strategy_id)
        _atomic_write(cover.cover_path(project_id, clip_id(job_id), slot), jpeg)
        cover.write_cover_meta(project_id, clip_id(job_id), slot, {'method': 'model', 'title': ' '.join(meta['lines'])})
    return True


def caption_text(post: dict[str, Any]) -> str:
    tags = ' '.join(f'#{tag}' for tag in post.get('tags') or [])
    return '\n\n'.join(part for part in (post.get('title', ''), post.get('description', ''), tags) if part)


def _safe_name(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\n\r\t]+', ' ', text).strip()[:60] or 'autoclip'


def _write_kit(target, video: Path, cover: Path | None, post: dict[str, Any], platform_label: str, *, english: bool) -> str:
    name = _safe_name(post.get('title') or video.stem)
    cover_name, copy_name, platform = ('cover', 'post', 'Platform: ') if english else ('封面', '发布文案', '平台：')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as archive:  # mp4/jpg are already compressed
        archive.write(video, f'{name}.mp4')
        if cover is not None:
            archive.write(cover, f'{name} {cover_name}.jpg')
        archive.writestr(f'{name} {copy_name}.txt', f'{platform}{platform_label}\n\n{caption_text(post)}\n')
    return f'{name}.zip'


def kit_file(video: Path, cover: Path | None, post: dict[str, Any], platform_label: str, *, english: bool = False) -> tuple[Path, str]:
    """Build on disk: a long video must not be duplicated into server memory for its download."""
    with tempfile.NamedTemporaryFile(prefix='autoclip-kit-', suffix='.zip', delete=False) as temporary:
        path = Path(temporary.name)
    try:
        return path, _write_kit(path, video, cover, post, platform_label, english=english)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def kit_zip(video: Path, cover: Path | None, post: dict[str, Any], platform_label: str, *, english: bool = False) -> tuple[bytes, str]:
    """In-memory helper for small callers; HTTP downloads use kit_file."""
    buffer = io.BytesIO()
    name = _write_kit(buffer, video, cover, post, platform_label, english=english)
    return buffer.getvalue(), name
