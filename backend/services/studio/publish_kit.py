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


# One house style for every AI cover: an editorial magazine cover for interview content.
# Layout per platform slot; colour from the clip's own palette so cover and video match.
AI_LAYOUT = {
    'xiaohongshu': ('3:4 vertical Xiaohongshu note cover', 'title stacked in the top 40%, subject below and slightly off-centre'),
    'douyin': ('9:16 vertical Douyin video cover', 'title stacked in the upper third, subject filling the lower two thirds'),
    'tiktok': ('9:16 vertical TikTok cover', 'title stacked in the upper third, subject filling the lower two thirds'),
    'instagram_reels': ('9:16 vertical Instagram Reels cover', 'title stacked in the upper third, subject filling the lower two thirds'),
    'youtube_shorts': ('9:16 vertical YouTube Shorts cover', 'title stacked in the upper third, subject filling the lower two thirds'),
    'youtube_long': ('16:9 YouTube thumbnail', 'subject on one side (head and shoulders, large), title stacked on the other side'),
    'bilibili': ('16:10 Bilibili video cover', 'subject on one side (head and shoulders, large), title stacked on the other side'),
}


def ai_prompt(strategy_id: str, lines: list[str], accent: int, name: str, palette: str | None = None) -> str:
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio.packaging_render import PALETTES
    slot, layout = AI_LAYOUT.get(strategy_id, AI_LAYOUT['douyin'])
    colour = '#' + PALETTES.get(palette or 'azure', PALETTES['azure'])[0]
    keyword = lines[accent] if 0 <= accent < len(lines) and len(lines) > 1 else lines[-1]
    english = platform_strategy(strategy_id).audience_language == 'en'
    title = ' / '.join(lines)
    return (
        f'Design a {slot} in a premium editorial magazine-cover style for an interview clip. '
        f'Subject: the person in the reference image{" (" + name + ")" if name else ""} — keep their face, hair, age and clothing exactly; '
        f'never replace, restyle or beautify them. Cut the subject out cleanly, head and shoulders large and sharp, with a soft rim light; '
        f'background replaced by a deep, near-black gradient with subtle film grain, no clutter. Layout: {layout}. '
        f'Typography: a heavy condensed sans-serif headline, {"set in English" if english else "set in Simplified Chinese"}, '
        f'stacked in short lines exactly reading "{title}"; the words "{keyword}" sit on a solid {colour} colour block (or in {colour}), '
        f'the rest in off-white; strong hierarchy, generous margins, nothing touching the edges, the face never covered. '
        f'Keep every letter inside the central 88% of the width and below the top 5% of the height; never crop or cut off text. '
        f'Do not write any names or labels; the only text is the headline. '
        f'Spell every character exactly as given; no other words, no watermark, no logo, no subtitles, no UI elements. '
        f'High contrast, crisp and clean, designed to stand out in a feed and earn the click.'
    )


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
    return squash(''.join(lines)) in squash(answer.get('text', ''))


def _fit(image, size: tuple[int, int]):
    """Pad, never crop: a model that ignores the size must not lose the edges of its headline.

    The gap is filled by stretching the image's outermost pixels, blurred and feathered into it, so a
    2:3 image on a 9:16 cover reads as one picture instead of sitting between flat bars. Only an
    edge a few pixels deep is reused: mirroring more would echo the headline into the gap.
    """
    from PIL import Image, ImageFilter, ImageOps
    width, height = size
    contained = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    x, y = (width - contained.width) // 2, (height - contained.height) // 2
    if (x, y) == (0, 0):
        return contained.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', size)
    canvas.paste(contained, (x, y))
    edge, cw, ch = 4, contained.width, contained.height
    if y:
        bottom = height - y - ch
        canvas.paste(contained.crop((0, 0, cw, edge)).resize((cw, y)), (x, 0))
        canvas.paste(contained.crop((0, ch - edge, cw, ch)).resize((cw, bottom)), (x, y + ch))
    else:
        right = width - x - cw
        canvas.paste(contained.crop((0, 0, edge, ch)).resize((x, ch)), (0, y))
        canvas.paste(contained.crop((cw - edge, 0, cw, ch)).resize((right, ch)), (x + cw, y))
    blurred = canvas.filter(ImageFilter.GaussianBlur(28)).point(lambda value: int(value * .8))
    feather = max(8, min(48, (y or x) // 2))
    mask = Image.new('L', size, 255)
    sharp = (x, y + feather, x + cw, y + ch - feather) if y else (x + feather, y, x + cw - feather, y + ch)
    mask.paste(0, sharp)
    mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    return Image.composite(blurred, canvas, mask)


def ai_cover(project_id: str, job_id: str, strategy_id: str) -> bool:
    """Generate the AI cover for one variant from its designed cover's frame and title; True when stored."""
    from PIL import Image
    from backend.core.image_providers import ImageRequest, generate_image
    from backend.services import cover
    from backend.services.studio import cover_design as cd
    cfg = cover.load_config()
    frame_file, meta_file = frame_path(project_id, job_id, strategy_id), cd_meta_path(project_id, job_id, strategy_id)
    if not (cfg.enabled and cfg.configured) or not frame_file.is_file() or not meta_file.is_file():
        return False
    if not cfg.allow_send_frame:
        # Without the frame the model would invent a face, then carry the real guest's nameplate.
        return False
    meta = json.loads(meta_file.read_text(encoding='utf-8'))
    width, height = cd.size_for(strategy_id)
    request = ImageRequest(prompt=ai_prompt(strategy_id, meta['lines'], meta['accent'], meta.get('name', ''), meta.get('palette')), width=width, height=height,
                           reference=frame_file.read_bytes(), model=cfg.model)
    image = None
    for attempt in range(2):
        try:
            image = generate_image(provider=cfg.provider, api_key=cfg.api_key, base_url=cfg.base_url, request=request)
        except Exception as error:  # noqa: BLE001 - the designed cover stays
            logger.warning('AI cover failed: %s', type(error).__name__)
            return False
        if _title_ok(image, meta['lines']) is not False:
            break
        request = ImageRequest(prompt=request.prompt + ' The previous attempt misspelled the headline: render it character by character exactly.', width=width, height=height,
                               reference=request.reference, model=cfg.model)
    else:
        return False  # the title stayed wrong twice: keep the designed cover
    generated = Image.open(io.BytesIO(image)).convert('RGB')
    fitted = _fit(generated, (width, height))
    if meta.get('guest') and meta.get('name'):
        fitted = cd.nameplate(fitted, meta['name'], meta.get('role', ''), meta.get('palette'))
    out = io.BytesIO()
    fitted.save(out, format='JPEG', quality=92)
    _atomic_write(kit_cover_path(project_id, job_id, strategy_id), out.getvalue())
    if height != 1440:  # the publish slot is 9:16 / 16:9; Xiaohongshu's 3:4 stays kit-only
        slot = _publish_slot(strategy_id)
        _atomic_write(cover.cover_path(project_id, clip_id(job_id), slot), out.getvalue())
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
