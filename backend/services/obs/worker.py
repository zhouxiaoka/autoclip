"""Stage a positively attributed recording, atomically register it, then dispatch once."""

import hashlib
import math
import os
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
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
from .models import ObsCall, ObsCapture, ObsReplayFile


def recording_identity(path, st):
    return hashlib.sha256(repr((str(path), stat_key(st))).encode()).hexdigest()


def save_manual(capture, directory):
    try:
        root = Path(directory).resolve(strict=True)
        path = Path(capture.path).resolve(strict=True)
        info = path.stat()
        if not path.is_relative_to(root) or not stat.S_ISREG(info.st_mode) or not info.st_size:
            return
    except (OSError, RuntimeError):
        return
    replay = ObsReplayFile(capture_id=capture.session_id, directory=str(root), identity=recording_identity(path, info))
    save(capture, '', replay=replay)


def save(capture, epoch, *, replay=None):
    with session_scope() as db:
        if db.get(ObsCapture, capture.session_id):
            return
        if replay is not None:
            db.add(replay)
        db.add(
            ObsCapture(
                id=capture.session_id,
                path=capture.path,
                start=capture.start,
                end=capture.end,
                duration=capture.duration,
                created=time.time(),
                epoch=epoch,
                status='available' if replay is not None else 'waiting',
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
        for row in db.query(ObsCapture).filter_by(status='manual_importing'):
            if not row.project_id:
                row.status = 'available'
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


def replays():
    with session_scope() as db:
        rows = (db.query(ObsCapture, Project.id, ObsReplayFile.capture_id)
                .outerjoin(Project, Project.id == ObsCapture.project_id)
                .outerjoin(ObsReplayFile, ObsReplayFile.capture_id == ObsCapture.id)
                .order_by(ObsCapture.created.desc(), ObsCapture.id).limit(100))
        return [dict(id=c.id, saved_at=c.created, seconds=c.end - c.start, status=c.status,
                     project_id=project_id, selectable=bool(manual_id and c.status in ('available', 'setup_required')))
                for c, project_id, manual_id in rows]


_manual_requested_at: dict[str, float] = {}


def request_manual(cid):
    # Only an observed, manually selectable receipt can enter the worker queue.
    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row = db.get(ObsCapture, cid)
        if not row or not db.get(ObsReplayFile, cid):
            return False
        if row.status in ('available', 'setup_required'):
            row.status = 'manual_waiting'
            db.commit()
            _manual_requested_at[cid] = time.time()
            return True
        return row.status in ('manual_waiting', 'manual_ready', 'dispatching', 'submitted')


def pending():
    with session_scope() as db:
        return [
            row[0]
            for row in db.query(ObsCapture.id)
            .filter(ObsCapture.status.in_(['waiting', 'ready', 'manual_waiting', 'manual_ready']))
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


def copy_recording(path, folder, target, stopping=lambda: False, *, expected_identity=None):
    # Copy from the checked file handle and re-check its identity after copying.
    if not path.is_absolute() or path.suffix.lower() not in {'.mkv', '.mp4', '.mov', '.webm', '.avi'}:
        raise ValueError('unsupported recording')
    root = Path(folder).resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError('outside recording directory')
    observed = resolved.stat()
    if expected_identity and recording_identity(resolved, observed) != expected_identity:
        raise ValueError('recording replaced')
    before = stat_key(observed)
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


def _run_ffmpeg_tracked(cmd, stopping, timeout=7200):
    from backend.services import child_guard

    proc = child_guard.track(
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **child_guard.popen_kwargs()
        ),
        'obs-trim',
    )
    try:
        deadline = time.monotonic() + timeout
        while proc.poll() is None:
            if stopping():
                raise InterruptedError()
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(cmd, timeout)
            time.sleep(0.2)
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, cmd)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        child_guard.untrack(proc)


def _next_keyframe(path, start, end):
    """Find the first video keyframe at or after ``start`` for strict inward stream copy."""
    if start <= 0:
        return 0.0
    from backend.utils.ffmpeg_utils import get_ffprobe_path

    ffprobe = get_ffprobe_path()
    window = min(15.0, max(2.0, end - start))
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                '-v',
                'error',
                '-read_intervals',
                f'{max(0.0, start - 0.5):.3f}%+{window:.3f}',
                '-select_streams',
                'v:0',
                '-skip_frame',
                'nokey',
                '-show_entries',
                'frame=pts_time',
                '-of',
                'default=noprint_wrappers=1:nokey=1',
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        try:
            pts = float(line.strip())
        except ValueError:
            continue
        if start <= pts < end:
            return pts
    return None


def _trim_recording(path, start, end, ffmpeg, stopping):
    """Prefer lossless inward stream-copy to avoid multi-hour CPU re-encoding."""
    size = path.stat().st_size
    if shutil.disk_usage(path.parent).free < max(256 * 1024 * 1024, int(size * 1.15)):
        raise OSError('insufficient disk space')
    trimmed = path.with_name('broadcast' + path.suffix.lower())
    kf = _next_keyframe(path, start, end)
    # Only use stream copy when an inward keyframe exists promptly after ``start``.
    if kf is not None and kf - start <= min(10.0, max(2.0, (end - start) * 0.25)) and end - kf >= 1.0:
        copy_cmd = [
            ffmpeg,
            '-nostdin',
            '-v',
            'error',
            '-y',
            '-ss',
            f'{kf:.3f}',
            '-i',
            str(path),
            '-t',
            f'{end - kf:.3f}',
            '-map',
            '0:v:0',
            '-map',
            '0:a?',
            '-map_metadata',
            '-1',
            '-c',
            'copy',
            '-avoid_negative_ts',
            'make_zero',
            str(trimmed),
        ]
        try:
            _run_ffmpeg_tracked(copy_cmd, stopping, timeout=600)
            probed = preflight.probe_material(trimmed)
            probed_dur = probed.duration or 0
            if probed.width and probed.height and 0.5 <= probed_dur <= (end - kf) + 1.5:
                return trimmed, probed
        except InterruptedError:
            trimmed.unlink(missing_ok=True)
            raise
        except (OSError, ValueError, subprocess.SubprocessError):
            trimmed.unlink(missing_ok=True)
    # Fallback to frame-accurate re-encode only when stream-copy cannot safely align inward.
    trimmed = path.with_name('broadcast.mkv')
    encode_cmd = [
        ffmpeg,
        '-nostdin',
        '-v',
        'error',
        '-y',
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
    _run_ffmpeg_tracked(encode_cmd, stopping, timeout=7200)
    return trimmed, preflight.probe_material(trimmed)


def inspect_media(path, capture, stopping=lambda: False):
    probe = preflight.probe_material(path)
    duration = probe.duration or 0
    if not probe.width or not probe.height or not math.isfinite(duration) or duration <= 0:
        raise ValueError('invalid video')
    tolerance = max(5.0, capture.duration * 0.015)
    if abs(duration - capture.duration) > tolerance:
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
    # Ignore negligible OBS start/stop jitter (<= 1s) instead of needlessly re-muxing/re-encoding.
    needs_start_trim = capture.start > 1.0
    needs_end_trim = (capture.duration - capture.end) > 1.0
    if needs_start_trim or needs_end_trim:
        # Allow for OBS output startup/stop latency by trimming inward at external boundaries.
        margin = max(0.5, abs(duration - capture.duration))
        start = capture.start + margin if needs_start_trim else 0.0
        end = min(duration, capture.end - margin) if needs_end_trim else duration
        if end <= start:
            raise ValueError('overlap too short')
        path, probe = _trim_recording(path, start, end, ffmpeg, stopping)
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


def options(*, manual=False):
    return ImportOptions(
        goal='auto',
        replay_source='obs' if manual else None,
        platforms=['original'],
        aspect='original',
        duration=45,
        auto_start=True,
        branding={'outro_enabled': False},
    )


def process(cid, stopping=lambda: False):
    with session_scope() as db:
        row = db.get(ObsCapture, cid)
        if not row or row.status not in ('waiting', 'ready', 'manual_waiting', 'manual_ready'):
            return
        manual = row.status in ('manual_waiting', 'manual_ready')
        replay = db.get(ObsReplayFile, cid) if manual else None
        if manual and not replay:
            mark(cid, row.status, 'file_error')
            return
        cfg = settings.config(db)
        if not manual and (not cfg.consent or cfg.consent_epoch != row.epoch or settings.overview()[1] != cfg.consent):
            mark(cid, row.status, 'paused')
            return
        directory = replay.directory if manual else cfg.directory
        expected = replay.identity if manual else None
        db.expunge(row)
    if row.status in ('ready', 'manual_ready'):
        dispatch(row)
        return
    staging = get_data_directory() / 'import-staging'
    staging.mkdir(exist_ok=True, parents=True)
    try:
        with tempfile.TemporaryDirectory(dir=staging, prefix='obs-') as temp:
            source = Path(row.path)
            staged = Path(temp) / ('recording' + source.suffix.lower())
            key = copy_recording(source, directory, staged, stopping, expected_identity=expected)
            staged = inspect_media(staged, row, stopping)
            if stopping():
                return
            pid = str(uuid.uuid4()) if manual else billing.project_id(cid)
            raw = store.directory(pid) / 'raw'
            path = raw / ('input' + staged.suffix)
            name = 'OBS · ' + datetime.fromtimestamp(row.created).strftime('%Y-%m-%d %H.%M')
            data = import_project_data(name, options(manual=manual))
            data.settings['import_source'] = 'obs'
            with session_scope() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                current = db.get(ObsCapture, cid)
                if current.status != row.status:
                    return
                cfg = settings.config(db)
                if not manual and (not cfg.consent or cfg.consent_epoch != row.epoch or settings.overview()[1] != cfg.consent):
                    current.status = 'paused'
                elif db.query(ObsCapture).filter_by(file_key=key).first():
                    current.status = 'duplicate'
                else:
                    fields = ProjectService.project_fields(data)
                    fields['video_path'] = str(path)
                    db.add(Project(id=pid, **fields))
                    current.project_id, current.file_key, current.status = pid, key, 'manual_ready' if manual else 'ready'
                    db.flush()
                    raw.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(staged), str(path))
                db.commit()
    except InterruptedError:
        return
    except (OSError, subprocess.TimeoutExpired):
        anchor = _manual_requested_at.get(cid, row.created) if manual else row.created
        if time.time() - anchor > 120:
            mark(cid, row.status, 'file_error')
    except SetupRequired:
        mark(cid, row.status, 'setup_required')
    except (ValueError, subprocess.CalledProcessError):
        mark(cid, row.status, 'file_error')


def claim_manual_for_home(cid: str, prefs: ImportOptions, name: str = ''):
    """Atomically claim a selectable OBS replay for async staging + user-selected platforms."""
    from fastapi import HTTPException

    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row = db.get(ObsCapture, cid)
        if not row:
            raise HTTPException(409, 'replay_unavailable')
        if row.project_id and db.get(Project, row.project_id):
            return row.project_id, False
        replay = db.get(ObsReplayFile, cid)
        if not replay or row.status not in ('available', 'setup_required'):
            raise HTTPException(409, 'replay_unavailable')
        # Fast stat-only identity check before claiming so a replaced/deleted file never creates a project.
        try:
            root = Path(replay.directory).resolve(strict=True)
            resolved = Path(row.path).resolve(strict=True)
            observed = resolved.stat()
            if (
                not resolved.is_relative_to(root)
                or not stat.S_ISREG(observed.st_mode)
                or recording_identity(resolved, observed) != replay.identity
            ):
                row.status = 'file_error'
                db.commit()
                raise HTTPException(422, '录像文件已变更或不存在，请重新选择')
        except OSError:
            row.status = 'file_error'
            db.commit()
            raise HTTPException(422, '录像文件已变更或不存在，请重新选择') from None

        pid = str(uuid.uuid4())
        project_name = (name or '').strip() or ('OBS · ' + datetime.fromtimestamp(row.created).strftime('%Y-%m-%d %H.%M'))
        data = import_project_data(project_name, prefs)
        data.settings['import_source'] = 'obs'
        data.settings['obs_manual_replay'] = {
            'capture_id': cid,
            'path': row.path,
            'directory': replay.directory,
            'identity': replay.identity,
            'start': row.start,
            'end': row.end,
            'duration': row.duration,
        }
        fields = ProjectService.project_fields(data)
        db.add(Project(id=pid, **fields))
        row.project_id = pid
        row.status = 'dispatching'
        row.dispatcher_pid = os.getpid()
        row.dispatcher_start = psutil.Process().create_time()
        db.commit()
        return pid, True


def prepare_manual_recording(project_id: str, obs_replay: dict, *, checkpoint=None):
    """Copy, verify, and privacy-trim a claimed OBS replay asynchronously inside the Studio worker."""
    from .session import Capture
    from backend.core.failure_codes import UserFacingError

    cid = obs_replay['capture_id']
    capture_snap = Capture(
        cid,
        obs_replay['path'],
        float(obs_replay['start']),
        float(obs_replay['end']),
        float(obs_replay['duration']),
    )
    cancelled = [False]

    def stopping():
        if cancelled[0]:
            return True
        if checkpoint is not None:
            try:
                checkpoint()
            except BaseException:
                cancelled[0] = True
                return True
        return False

    staging = get_data_directory() / 'import-staging'
    staging.mkdir(exist_ok=True, parents=True)
    try:
        with tempfile.TemporaryDirectory(dir=staging, prefix='obs-') as temp:
            source = Path(capture_snap.path)
            staged = Path(temp) / ('recording' + source.suffix.lower())
            key = copy_recording(
                source,
                obs_replay['directory'],
                staged,
                stopping=stopping,
                expected_identity=obs_replay.get('identity'),
            )
            if checkpoint is not None:
                checkpoint()
            staged = inspect_media(staged, capture_snap, stopping=stopping)
            if checkpoint is not None:
                checkpoint()
            raw = store.directory(project_id) / 'raw'
            raw.mkdir(parents=True, exist_ok=True)
            target = raw / ('input' + staged.suffix)
            shutil.move(str(staged), str(target))
    except InterruptedError:
        if checkpoint is not None:
            checkpoint()
        raise
    except SetupRequired:
        mark(cid, 'dispatching', 'setup_required')
        raise UserFacingError('请检查模型和语音转写设置后重试。') from None
    except (ValueError, subprocess.CalledProcessError, preflight.SourceRejected) as exc:
        mark(cid, 'dispatching', 'file_error')
        raise UserFacingError(str(exc) or 'OBS 录像校验未通过，请手动导入查看原因。') from None
    except (OSError, subprocess.TimeoutExpired):
        mark(cid, 'dispatching', 'file_error')
        raise UserFacingError('读取或复制 OBS 录像失败，请确认磁盘空间充足且文件未被占用后重试。') from None

    with session_scope() as db:
        current = db.get(ObsCapture, cid)
        if current:
            if not db.query(ObsCapture).filter(ObsCapture.file_key == key, ObsCapture.id != cid).first():
                current.file_key = key
            current.status = 'submitted'
        p = db.get(Project, project_id)
        if p:
            p.video_path = str(target)
        db.commit()
    return target


def import_manual_with_options(cid: str, prefs: ImportOptions, name: str = '', *, features=None):
    """Import a manually selected OBS replay with user-chosen platforms and specs from Home."""
    from fastapi import HTTPException

    from .session import Capture

    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row = db.get(ObsCapture, cid)
        if not row:
            raise HTTPException(409, 'replay_unavailable')
        if row.project_id and db.get(Project, row.project_id):
            return row.project_id, None
        replay = db.get(ObsReplayFile, cid)
        if not replay or row.status not in ('available', 'setup_required'):
            raise HTTPException(409, 'replay_unavailable')
        prev_status = row.status
        capture_snap = Capture(row.id, row.path, row.start, row.end, row.duration)
        created_at = row.created
        directory, expected = replay.directory, replay.identity
        row.status = 'manual_importing'
        db.commit()

    staging = get_data_directory() / 'import-staging'
    staging.mkdir(exist_ok=True, parents=True)
    try:
        with tempfile.TemporaryDirectory(dir=staging, prefix='obs-') as temp:
            source = Path(capture_snap.path)
            staged = Path(temp) / ('recording' + source.suffix.lower())
            key = copy_recording(source, directory, staged, expected_identity=expected)
            staged = inspect_media(staged, capture_snap)
            pid = str(uuid.uuid4())
            raw = store.directory(pid) / 'raw'
            path = raw / ('input' + staged.suffix)
            project_name = (name or '').strip() or ('OBS · ' + datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H.%M'))
            data = import_project_data(project_name, prefs)
            data.settings['import_source'] = 'obs'
            with session_scope() as db:
                db.execute(text('BEGIN IMMEDIATE'))
                current = db.get(ObsCapture, cid)
                if not current or current.status != 'manual_importing':
                    raise HTTPException(409, 'replay_unavailable')
                existing = db.query(ObsCapture).filter_by(file_key=key).first()
                if existing and existing.project_id and db.get(Project, existing.project_id):
                    current.status = 'duplicate'
                    db.commit()
                    return existing.project_id, None
                fields = ProjectService.project_fields(data)
                fields['video_path'] = str(path)
                db.add(Project(id=pid, **fields))
                current.project_id = pid
                current.file_key = key
                current.status = 'dispatching'
                current.dispatcher_pid = os.getpid()
                current.dispatcher_start = psutil.Process().create_time()
                db.flush()
                raw.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staged), str(path))
                db.commit()
    except HTTPException:
        mark(cid, 'manual_importing', prev_status)
        raise
    except SetupRequired:
        mark(cid, 'manual_importing', 'setup_required')
        raise HTTPException(422, '请检查模型和语音转写设置后重试') from None
    except (ValueError, subprocess.CalledProcessError, preflight.SourceRejected) as exc:
        mark(cid, 'manual_importing', 'file_error')
        raise HTTPException(422, str(exc) or '录像或导入预检未通过') from None
    except (OSError, subprocess.TimeoutExpired):
        # Transient I/O issue: restore previous selectable status so the user can retry.
        mark(cid, 'manual_importing', prev_status)
        raise HTTPException(409, 'replay_unavailable') from None

    try:
        run_id = jobs.inspect_project(pid, prefs, None, None, features=features)
        mark(cid, 'dispatching', 'submitted')
        return pid, run_id
    except Exception:
        mark(cid, 'dispatching', 'uncertain')
        raise


def dispatch(row):
    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        current = db.get(ObsCapture, row.id)
        if current.status not in ('ready', 'manual_ready'):
            return
        cfg = settings.config(db)
        manual = current.status == 'manual_ready'
        if not db.get(Project, row.project_id) or (not manual and (not cfg.consent or cfg.consent_epoch != row.epoch)):
            current.status = 'paused'
            db.commit()
            return
        current.status = 'dispatching'
        current.dispatcher_pid = os.getpid()
        current.dispatcher_start = psutil.Process().create_time()
        db.commit()
    try:
        jobs.inspect_project(row.project_id, options(manual=manual), None, None)
        mark(row.id, 'dispatching', 'submitted')
    except Exception:
        # Studio may have already accepted work. Never submit this receipt again.
        mark(row.id, 'dispatching', 'uncertain')
