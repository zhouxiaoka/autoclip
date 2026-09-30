"""Bundled example project: a finished, link-imported project users can open before configuring anything.

The bundled "source" is the three selected passages of the original interview stitched back to back
(see backend/assets/example/manifest.json), with subtitles rebased to that timeline. That keeps the
download small while every downstream step — editor, re-cut, render, cover, publish — runs on real
files. Clip files are cut from the stitched source on creation. Creating it is idempotent and needs
no model key.
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.core.path_utils import get_project_directory
from backend.models.clip import Clip, ClipStatus
from backend.models.project import Project, ProjectStatus, ProjectType

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'example'
MANIFEST = ASSETS / 'manifest.json'
EXAMPLE_FLAG = 'example'


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding='utf-8'))


def available() -> bool:
    if not MANIFEST.exists():
        return False
    meta = load_manifest()['project']
    return (ASSETS / meta['source']).exists() and (ASSETS / meta['subtitles']).exists()


def find_existing(db: Session) -> Project | None:
    # JSON columns differ across SQLite/Postgres; a small scan of completed projects is enough here.
    for project in db.query(Project).filter(Project.status == ProjectStatus.COMPLETED).all():
        if (project.processing_config or {}).get(EXAMPLE_FLAG):
            return project
    return None


def _seconds(timestamp: str) -> float:
    hours, minutes, rest = timestamp.split(':')
    return int(hours) * 3600 + int(minutes) * 60 + float(rest.replace(',', '.'))


def _safe_title(title: str) -> str:
    safe = ''.join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return safe.replace(' ', '_')


def _cover_data_url(name: str | None) -> str | None:
    if not name or not (ASSETS / name).exists():
        return None
    return 'data:image/jpeg;base64,' + base64.b64encode((ASSETS / name).read_bytes()).decode('ascii')


def cut_clip(source: Path, start: float, end: float, target: Path) -> None:
    """Stream-copy one passage. Passage boundaries are keyframes (each was a separate file before stitching)."""
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    command = [get_ffmpeg_path(), '-v', 'error', '-y', '-ss', f'{start:.3f}', '-to', f'{end:.3f}', '-i', str(source),
               '-c', 'copy', '-avoid_negative_ts', 'make_zero', '-movflags', '+faststart', str(target)]
    subprocess.run(command, check=True, capture_output=True, timeout=120)


def create(db: Session) -> Project:
    """Create the example project once; return the existing one on later calls."""
    existing = find_existing(db)
    if existing:
        return existing
    if not available():
        raise FileNotFoundError('示例项目资源缺失')
    manifest = load_manifest()
    meta = manifest['project']
    now = datetime.now(timezone.utc)  # completed_at is stored in UTC like every other timestamp

    project = Project(
        name=meta['name'],
        description=meta.get('description'),
        status=ProjectStatus.COMPLETED,
        project_type=ProjectType.DEFAULT,
        video_duration=meta.get('video_duration'),
        thumbnail=_cover_data_url(meta.get('cover')),
        processing_config={
            EXAMPLE_FLAG: True,
            'example_version': manifest.get('version', 1),
            'analysis_mode': meta.get('analysis_mode', 'subtitle'),
            'video_category': meta.get('video_category', 'default'),
        },
        project_metadata={'source_url': meta['source_url'], EXAMPLE_FLAG: True},
        completed_at=now,
    )
    db.add(project)
    db.flush()

    root = get_project_directory(project.id)
    raw = root / 'raw'
    clips_dir = root / 'output' / 'clips'
    for folder in (raw, clips_dir, root / 'metadata'):
        folder.mkdir(parents=True, exist_ok=True)
    source = raw / 'input.mp4'
    shutil.copyfile(ASSETS / meta['source'], source)
    shutil.copyfile(ASSETS / meta['subtitles'], raw / 'input.srt')
    if meta.get('cover') and (ASSETS / meta['cover']).exists():
        shutil.copyfile(ASSETS / meta['cover'], raw / 'input_cover.jpg')
    project.video_path = str(source)
    project.subtitle_path = str(raw / 'input.srt')

    records = []
    for entry in manifest['clips']:
        start, end = _seconds(entry['start_time']), _seconds(entry['end_time'])
        clip = Clip(
            project_id=project.id,
            title=entry['title'],
            description=entry.get('recommend_reason', ''),
            start_time=int(start),
            end_time=int(end),
            duration=int(end) - int(start),
            score=entry.get('final_score'),
            tags=[],
            status=ClipStatus.COMPLETED,
        )
        db.add(clip)
        db.flush()
        target = clips_dir / f"{clip.id}_{_safe_title(entry['title'])}.mp4"
        cut_clip(source, start, end, target)
        clip.video_path = str(target)
        # The export path looks clips up in clips_metadata.json by the database id.
        record = {
            'id': clip.id,
            'outline': entry.get('outline', ''),
            'content': entry.get('content', []),
            'recommend_reason': entry.get('recommend_reason', ''),
            'generated_title': entry['title'],
            'title': entry['title'],
            'start_time': entry['start_time'],
            'end_time': entry['end_time'],
            'original_start_time': entry.get('original_start_time'),
            'original_end_time': entry.get('original_end_time'),
            'final_score': entry.get('final_score'),
            'video_path': str(target),
            EXAMPLE_FLAG: True,
        }
        clip.clip_metadata = record
        records.append(record)

    (root / 'metadata' / 'clips_metadata.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'project.json').write_text(json.dumps({
        'project_name': meta['name'], 'description': meta.get('description'), 'created_at': now.isoformat(),
        'source': {'url': meta['source_url'], 'video': str(source), 'srt': str(raw / 'input.srt'), 'via': 'example'},
        'video_category': meta.get('video_category', 'default'), EXAMPLE_FLAG: True,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    db.commit()
    db.refresh(project)
    return project
