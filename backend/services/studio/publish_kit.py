"""Version-owned Studio covers, copy and ZIP files for each output variant."""
from __future__ import annotations

import io
import json
import hashlib
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from backend.services import cover_brief as cb, cover_planner

logger = logging.getLogger(__name__)

def clip_id(job_id: str) -> str:
    return f'studio-{job_id}'


def _slot_name(strategy_id, variant_id):
    if not variant_id:
        return strategy_id
    digest = hashlib.sha256(variant_id.encode()).hexdigest()[:24]
    return f'{strategy_id}-{digest}'


def kit_cover_path(project_id: str, job_id: str, strategy_id: str, variant_id=None) -> Path:
    from backend.services import cover

    root = cover.cover_dir(project_id, clip_id(job_id))
    path = cd_meta_path(project_id, job_id, strategy_id, variant_id)
    if variant_id and not path.exists():
        return kit_cover_path(project_id, job_id, strategy_id)
    return cb.stored_path(path,root/f'kit-{strategy_id}.jpg')


def _metadata(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def cover_file(project_id, job_id, strategy_id, variant_id=None):
    path = kit_cover_path(project_id, job_id, strategy_id, variant_id)
    if path.is_file():
        meta = _metadata(cd_meta_path(project_id, job_id, strategy_id, variant_id))
        return path, "ai" if meta.get("result") == "model" else "design"
    return None,None


def design_cover(project_id, video, draft, job_id, strategy_id, post_title, variant_id=None):
    from backend.services.publish_export import _probe
    from backend.services.studio import cover_design as cd

    path = cd_meta_path(project_id, job_id, strategy_id, variant_id)
    from backend.services.studio import store
    with store.lock:
        old = _metadata(path)
        # A render job and variant identify an immutable output; keep its later user edits.
        if old.get("brief") and kit_cover_path(project_id, job_id, strategy_id, variant_id).is_file():
            return True
        token = cb.begin(path)
    source = dict(asset_id="raw/input")
    info = _probe(video)
    size = cd.size_for(strategy_id, info.get("width") or 1920, info.get("height") or 1080)
    proposed = (
        cb.join_lines((draft.get("packaging") or {}).get("title_lines") or [])
        or post_title
        or draft.get("title", "")
    )
    from backend.services.cover import load_config

    options = cb.Options.model_validate(old.get("options") or {"mode": load_config().design_mode})
    scene, rows = cover_scene(project_id, draft["scenes"], proposed)
    ctx = cover_planner.context(cb.choose_copy(proposed, rows, False), strategy_id, size, options)
    frame, centre, _ = cd.pick_frame(video, scene, rows, draft.get("packaging") or {}, trace=source, context=ctx)
    brief = cb.plan(
        frame,
        title=ctx["title"],
        locked=False,
        editorial_context=ctx,
        rows=rows,
        size=size,
        origin=source,
        options=options,
        centre=centre,
        strategy=strategy_id,
    )
    _deliver(project_id, job_id, strategy_id, frame, brief, options, token, False, variant_id)
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


def cover_scene(project_id, scenes, title, revision=0):
    """Prefer a scene that contains the approved words, then the existing version order."""
    ordered = scenes[revision % len(scenes):] + scenes[:revision % len(scenes)]
    rows = _scene_rows(project_id, {"start": min(s["start"] for s in scenes), "end": max(s["end"] for s in scenes)})
    best = None
    for scene in ordered:
        evidence = [r for r in rows if r["end"] > scene["start"] and r["start"] < scene["end"]]
        text = cb.norm(" ".join(r["text"] for r in evidence)).casefold()
        if title and cb.norm(title).casefold() in text:
            return scene, evidence
        if best is None:
            best = scene, evidence
    return best


def frame_path(project_id: str, job_id: str, strategy_id: str, variant_id=None) -> Path:
    from backend.services import cover

    root = cover.cover_dir(project_id, clip_id(job_id))
    path = cd_meta_path(project_id, job_id, strategy_id, variant_id)
    if variant_id and not path.exists():
        return frame_path(project_id, job_id, strategy_id)
    return cb.stored_path(path,root/f'frame-{strategy_id}.jpg','reference_file')


def cd_meta_path(project_id: str, job_id: str, strategy_id: str, variant_id=None) -> Path:
    from backend.services import cover

    return cover.cover_dir(project_id, clip_id(job_id)) / f'kit-{_slot_name(strategy_id,variant_id)}.json'


def reference_prompt(strategy_id: str, lines: list[str], palette: str | None = None, *, subtitle='', badge='') -> str:
    return cb.compat_prompt(strategy_id,lines,subtitle,badge)


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
                {'type': 'text', 'text': '读出这张封面上的全部显示文案，保留标点、重复和额外文字，原样返回，只返回 JSON：{"text":"..."}'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode()}}],
                {**effective(), 'quick_screening': True}) or {}
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(answer,dict) or 'text' not in answer:
        return None
    return cb.matches(answer.get('text',''),' '.join(lines))


def _deliver(
    project_id, job_id, strategy_id, frame, brief, options, token, allow_model, variant_id=None, *, allow_reference_once=False
):
    from backend.core.image_providers import generate_image
    from backend.services import cover

    cfg = cover.load_config()
    can_send = cfg.allow_send_frame or bool(allow_reference_once)

    def generate(req):
        return generate_image(provider=cfg.provider, api_key=cfg.api_key, base_url=cfg.base_url, request=req)

    try:
        data, audit = cb.make(
            brief,
            frame,
            cfg,
            can_send=can_send,
            allow_model=allow_model,
            generate=generate,
            check=_title_ok,
            previous=kit_cover_path(project_id, job_id, strategy_id, variant_id).is_file(),
        )
    except cb.Rejected as exc:
        cb.record_rejection(cd_meta_path(project_id, job_id, strategy_id, variant_id), token, exc)
        raise
    audit.update(
        planning_fingerprint=cb.fingerprint(brief, cfg.provider, cfg.model),
        variant_id=variant_id,
        options=options.model_copy(update={"change_frame": False, "frame_time": None}).model_dump(),
        lines=brief.copy_spec["lines"],
        layout_version=brief.design["revision"],
    )
    cb.save(cd_meta_path(project_id, job_id, strategy_id, variant_id), token, data, frame, audit)
    logger.info(
        "Studio cover delivered: project=%s job=%s strategy=%s allow_model=%s mode=%s allow_send_frame=%s allow_reference_once=%s result=%s attempts=%d fallback_reason=%s",
        project_id, job_id, strategy_id, allow_model, brief.permissions.get("mode"), cfg.allow_send_frame, bool(allow_reference_once),
        audit.get("result"), int(audit.get("attempts") or 0), audit.get("fallback_reason"),
    )
    return audit['result']


def _redesign(
    project_id,
    job_id,
    strategy_id,
    *,
    use_model,
    options=None,
    title=None,
    request_token=None,
    variant_id=None,
    reuse=False,
    allow_reference_once=False,
):
    from backend.services import cover
    from backend.services.studio import cover_design as cd, store
    from backend.services.studio.publishing import cover_source_frame

    path = cd_meta_path(project_id, job_id, strategy_id, variant_id)
    token = request_token or cb.begin(path)
    meta = _metadata(path) or _metadata(cd_meta_path(project_id, job_id, strategy_id))
    old = meta.get("brief") or {}
    if reuse and old and meta.get("result") == "model":
        cfg = cover.load_config()
        saved_brief = cb.CoverBrief.model_validate(old)
        if (
            (meta.get("model_fidelity") or {}).get("status") == "passed"
            and meta.get("fingerprint") == cb.fingerprint(saved_brief, cfg.provider, cfg.model)
            and kit_cover_path(project_id, job_id, strategy_id, variant_id).is_file()
        ):
            return "model"
    saved = frame_path(project_id, job_id, strategy_id, variant_id)
    revision = int(meta.get("layout_version", 0)) + 1
    opts = options or cb.Options.model_validate(meta.get("options") or {"mode": cover.load_config().design_mode})
    source = dict(old.get("source") or {})
    rows = (old.get("content") or {}).get("evidence", [])
    job = next(j for j in store.read(project_id)["jobs"] if j["job_id"] == job_id)
    result = job.get("result") or {}
    size = cd.size_for(strategy_id, result.get("width") or 1920, result.get("height") or 1080)
    previous_copy = old.get("copy") or {}
    locked = title is not None or previous_copy.get("mode") == "locked"
    proposed = (
        title
        if title is not None
        else previous_copy.get("exact_text") or cb.join_lines(meta.get("lines") or []) or job.get("title", "")
    )
    prior = "" if reuse else old.get("design", {}).get("composition_intent", "")
    ctx = cover_planner.context(proposed, strategy_id, size, opts, locked=locked, previous=prior)
    if source.get("allow_alternate_frame") is False and (opts.change_frame or opts.frame_time is not None):
        raise ValueError("本次封面已锁定参考帧")
    if opts.frame_time is not None:
        from backend.services.publish_export import find_source_video

        frame, centre = cb.selected_candidate(find_source_video(project_id), source, opts.frame_time)
    elif saved.is_file() and not opts.change_frame:
        frame = saved.read_bytes()
        centre = source.get("centre")
        if not source:
            source = dict(
                kind="saved_frame",
                asset_id="legacy",
                source_timestamp_sec=None,
                selection_reason="现有发布包参考帧",
            )
    else:
        source = {}
        from backend.core.project_cancellation import ProjectDeleted
        try:
            frame, centre = cover_source_frame(project_id, job_id, revision, source, context=ctx,
                                               exclude_time=old.get("source", {}).get("source_timestamp_sec") if opts.change_frame else None)
            rows = source.pop("evidence", [])
        except ProjectDeleted:
            raise
        except (FileNotFoundError, cover.CoverError, OSError, ValueError):
            video, at = cover.resolve_clip_frame(project_id, clip_id(job_id))
            frame = cover.extract_frame_jpeg(video, at_sec=at)
            centre = None
            source = dict(
                kind="export_frame",
                asset_id=job_id,
                source_timestamp_sec=at,
                selection_reason="从已导出的当前成片截取",
            )
    brief = cb.plan(
        frame,
        title=cb.choose_copy(proposed, rows, locked),
        rows=rows,
        locked=locked,
        origin=source,
        editorial_context=ctx,
        options=opts,
        centre=centre,
        strategy=strategy_id,
        size=size,
        revision=revision,
    )
    return _deliver(
        project_id, job_id, strategy_id, frame, brief, opts, token, use_model, variant_id,
        allow_reference_once=allow_reference_once,
    )


def redesign_local_cover(project_id, job_id, strategy_id, **kwargs):
    return _redesign(project_id,job_id,strategy_id,use_model=False,**kwargs)


def ai_cover(project_id, job_id, strategy_id, **kwargs):
    return _redesign(project_id,job_id,strategy_id,use_model=True,**kwargs)


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
