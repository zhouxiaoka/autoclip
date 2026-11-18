"""Stage a positively attributed recording, atomically register it, then dispatch once."""

import hashlib
import math
import os
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import psutil
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend.core.database import session_scope
from backend.core.path_utils import get_data_directory
from backend.models.project import Project
from backend.services.project_service import ProjectService
from backend.services.studio import jobs, preflight, readiness, store
from backend.services.studio.models import ImportOptions, import_project_data
from backend.utils.ffmpeg_utils import get_ffmpeg_path
from . import billing, settings
from .models import ObsCall, ObsCapture


def save(capture, epoch):
    with session_scope() as db:
        if db.get(ObsCapture, capture.session_id):
            return
        db.add(
            ObsCapture(
                id=capture.session_id,
                path=capture.path,
                start=capture.start,
                end=capture.end,
                duration=capture.duration,
                created=time.time(),
                epoch=epoch,
                status='waiting',
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()


def recover():
    # An abandoned dispatch might already have reached Studio or a paid provider.
    # Only pre-dispatch receipts are replayable. Other desktop instances can still own live work.
    with session_scope() as db:
        for row in db.query(ObsCapture).filter(ObsCapture.status.in_(['dispatching', 'submitted'])):
            try:
                if (
                    row.dispatcher_pid
                    and psutil.Process(row.dispatcher_pid).create_time() == row.dispatcher_start
                ):
                    continue
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                continue
            unknown_call = db.query(ObsCall).filter_by(project_id=row.project_id, result=None).first()
            if row.status == 'dispatching' or unknown_call:
                row.status = 'uncertain'
        db.commit()


def latest():
    with session_scope() as db:
        row = db.query(ObsCapture).order_by(ObsCapture.created.desc()).first()
        if row:
            return {
                'status': row.status,
                'project_id': row.project_id if row.project_id and db.get(Project, row.project_id) else None,
            }


def pending():
    with session_scope() as db:
        return [
            row[0]
            for row in db.query(ObsCapture.id)
            .filter(ObsCapture.status.in_(['waiting', 'ready']))
            .order_by(ObsCapture.created)
            .all()
        ]


def mark(cid, expected, status):
    with session_scope() as db:
        changed = db.query(ObsCapture).filter_by(id=cid, status=expected).update({'status': status})
        db.commit()
        return changed == 1


def stat_key(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def copy_recording(path, folder, target, stopping=lambda: False):
    # Copy from the checked file handle and re-check its identity after copying.
    if not path.is_absolute() or path.suffix.lower() not in {'.mkv', '.mp4', '.mov', '.webm', '.avi'}:
        raise ValueError('unsupported recording')
    root = Path(folder).resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError('outside recording directory')
    before = stat_key(resolved.stat())
    time.sleep(0.6)
    digest = hashlib.sha256()
    with resolved.open('rb') as source, target.open('xb') as output:
        if not before[2] or stat_key(os.fstat(source.fileno())) != before:
            raise OSError('file changing')
        while block := source.read(2**20):
            if stopping():
                raise InterruptedError()
            output.write(block)
            digest.update(block)
        if (
            stat_key(os.fstat(source.fileno())) != before
            or path.resolve(strict=True) != resolved
            or stat_key(resolved.stat()) != before
        ):
            raise OSError('file changed during import')
    # Equal content in two distinct recording files may belong to different broadcasts.
    return hashlib.sha256(repr((str(resolved), before, digest.hexdigest())).encode()).hexdigest()


def inspect_media(path, capture, stopping=lambda: False):
    probe = preflight.probe_material(path)
    duration = probe.duration or 0
    if not probe.width or not probe.height or not math.isfinite(duration) or duration <= 0:
        raise ValueError('invalid video')
    if abs(duration - capture.duration) > 3:
        raise ValueError('unconfirmed recording timeline')
    ffmpeg = get_ffmpeg_path()
    for seek in (0, max(0, duration - 1)):
        checked = subprocess.run(
            [
                ffmpeg,
                '-nostdin',
                '-v',
                'error',
                '-ss',
                str(seek),
                '-i',
                str(path),
                '-map',
                '0:v:0',
                '-frames:v',
                '1',
                '-vf',
                'scale=2:2',
                '-f',
                'rawvideo',
                '-',
            ],
            capture_output=True,
            timeout=45,
        )
        if checked.returncode or not checked.stdout:
            raise ValueError('incomplete recording')
    if capture.start > 0 or capture.end < capture.duration:
        # Decode to precise frame boundaries before any frame or audio can leave the device.
        # Allow for OBS output startup/stop latency by trimming inward at external boundaries.
        margin = max(0.5, abs(duration - capture.duration))
        start = capture.start + margin if capture.start > 0 else 0
        end = min(duration, capture.end - margin) if capture.end < capture.duration else duration
        if end <= start:
            raise ValueError('overlap too short')
        trimmed = path.with_name('broadcast.mkv')
        cmd = [
            ffmpeg,
            '-nostdin',
            '-v',
            'error',
            '-ss',
            str(start),
            '-i',
            str(path),
            '-t',
            str(end - start),
            '-map',
            '0:v:0',
            '-map',
            '0:a?',
            '-map_metadata',
            '-1',
            '-c:v',
            'libx264',
            '-preset',
            'veryfast',
            '-c:a',
            'aac',
            str(trimmed),
        ]
        from backend.services import child_guard

        proc = child_guard.track(
            subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **child_guard.popen_kwargs()
            ),
            'obs-trim',
        )
        try:
            deadline = time.monotonic() + 7200
            while proc.poll() is None:
                if stopping():
                    raise InterruptedError()
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(cmd, 7200)
                time.sleep(0.2)
            if proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, cmd)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            child_guard.untrack(proc)
        path, probe = trimmed, preflight.probe_material(trimmed)
    from backend.pipeline.failures import PipelineFailure

    try:
        readiness.ensure_analysis_usable()
        preflight.check(preflight.ResolvedInputs(path, entry='studio', goal='auto'), probe=probe)
    except preflight.SourceRejected:
        raise
    except (ValueError, PipelineFailure) as exc:
        raise SetupRequired() from exc
    return path


class SetupRequired(Exception):
    """The media is valid but Studio requires a model or transcription configuration."""


def options():
    return ImportOptions(
        goal='auto',
        platforms=['original'],
        aspect='original',
        duration=45,
        auto_start=True,
        branding={'outro_enabled': False},
    )


def process(cid, stopping=lambda: False):
    with session_scope() as db:
        row = db.get(ObsCapture, cid)
        if not row or row.status not in ('waiting', 'ready'):
            return
        cfg = settings.config(db)
        if not cfg.consent or cfg.consent_epoch != row.epoch or settings.overview()[1] != cfg.consent:
            mark(cid, row.status, 'paused')
            return
        directory = cfg.directory
        db.expunge(row)
    if row.status == 'ready':
        dispatch(row)
        return
    staging = get_data_directory() / 'import-staging'
    staging.mkdir(exist_ok=True, parents=True)
    try:
        with tempfile.TemporaryDirectory(dir=staging, prefix='obs-') as temp:
            source = Path(row.path)
            staged = Path(temp) / ('recording' + source.suffix.lower())
            key = copy_recording(source, directory, staged, stopping)
            staged = inspect_media(staged, row, stopping)
            if stopping():
                return
            pid = billing.project_id(cid)
            raw = store.directory(pid) / 'raw'
            path = raw / ('input' + staged.suffix)
            name = 'OBS · ' + datetime.fromtimestamp(row.created).strftime('%Y-%m-%d %H.%M')
            data = import_project_data(name, options())
            data.settings['import_source'] = 'obs'
            with session_scope() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                current = db.get(ObsCapture, cid)
                if current.status != 'waiting':
                    return
                cfg = settings.config(db)
                if not cfg.consent or cfg.consent_epoch != row.epoch or settings.overview()[1] != cfg.consent:
                    current.status = 'paused'
                elif db.query(ObsCapture).filter_by(file_key=key).first():
                    current.status = 'duplicate'
                else:
                    fields = ProjectService.project_fields(data)
                    fields['video_path'] = str(path)
                    db.add(Project(id=pid, **fields))
                    current.project_id, current.file_key, current.status = pid, key, 'ready'
                    db.flush()
                    raw.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged), str(path))
                db.commit()
    except InterruptedError:
        return
    except (OSError, subprocess.TimeoutExpired):
        if time.time() - row.created > 120:
            mark(cid, 'waiting', 'file_error')
    except SetupRequired:
        mark(cid, 'waiting', 'setup_required')
    except (ValueError, subprocess.CalledProcessError):
        mark(cid, 'waiting', 'file_error')


def dispatch(row):
    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        current = db.get(ObsCapture, row.id)
        if current.status != 'ready':
            return
        cfg = settings.config(db)
        if not db.get(Project, row.project_id) or not cfg.consent or cfg.consent_epoch != row.epoch:
            current.status = 'paused'
            db.commit()
            return
        current.status = 'dispatching'
        current.dispatcher_pid = os.getpid()
        current.dispatcher_start = psutil.Process().create_time()
        db.commit()
    try:
        jobs.inspect_project(row.project_id, options(), None, None)
        mark(row.id, 'dispatching', 'submitted')
    except Exception:
        # Studio may have already accepted work. Never submit this receipt again.
        mark(row.id, 'dispatching', 'uncertain')
