"""Durable, at-most-once receipts for explicitly keyed local-video imports.

A reservation is committed before invoking the existing import route. If the process
fails before saving its receipt, the operation remains uncertain: never replay it.
This small separate ledger needs no migration of existing project/user databases.
"""
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from sqlalchemy.exc import IntegrityError
from backend.models.project import Project
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from backend.services.studio import store


_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
_LEDGER_VERSION = 2  # v2 binds new operations to project primary keys; unreleased v1 is not auto-migrated.
_INITIALIZED = b'STUDIO_IMPORT_RECEIPTS_V2\n'


def uncertain(status=409):
    return HTTPException(status, {'import_state': 'unknown',
        'message': '导入回执尚未确定，请先核对已有项目，不要重复上传。'})


def ledger_path() -> Path:
    return store.get_projects_directory().parent / 'studio-import-receipts.sqlite3'


def operation_project_id(key: str) -> str:
    """A project PK is the last side-effect guard even if receipt rows are lost."""
    digest = hashlib.sha256(('studio-import-operation-v1:' + key).encode()).digest()
    return str(uuid.UUID(bytes=digest[:16], version=4))


def initialized_marker(path: Path) -> Path:
    return path.with_suffix('.initialized')


def ensure_initialized_marker(path: Path):
    marker = initialized_marker(path)
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    except FileExistsError:
        if marker.is_symlink() or marker.read_bytes() != _INITIALIZED:
            raise sqlite3.DatabaseError('receipt initialization marker invalid')
        return
    try:
        os.write(fd, _INITIALIZED)
        os.fsync(fd)
    finally:
        os.close(fd)
    if os.name != 'nt':
        parent = os.open(marker.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise OSError('receipt ledger must not be a symlink')
    if not path.exists() and os.path.lexists(initialized_marker(path)):
        raise sqlite3.DatabaseError('initialized receipt ledger missing')
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        created = True
    except FileExistsError:
        fd = os.open(path, os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0))
        created = False
    try:
        if not created and os.fstat(fd).st_size == 0:
            raise sqlite3.DatabaseError('existing receipt ledger is empty')
    finally:
        os.close(fd)
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute('PRAGMA synchronous=FULL')
        marker = conn.execute('PRAGMA application_id').fetchone()[0]
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if created:
            if marker != 0 or version != 0 or tables:
                raise sqlite3.DatabaseError('new receipt ledger identity mismatch')
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('PRAGMA application_id=1094928722')
            conn.execute(f'PRAGMA user_version={_LEDGER_VERSION}')
            conn.execute('CREATE TABLE import_receipts (operation TEXT PRIMARY KEY, payload TEXT NOT NULL, receipt TEXT)')
            conn.commit()
        else:
            if marker != 1094928722 or version != _LEDGER_VERSION or tables != {'import_receipts'}:
                raise sqlite3.DatabaseError('existing receipt ledger structure invalid')
            columns = [(row[1], row[2], row[3], row[5]) for row in conn.execute('PRAGMA table_info(import_receipts)')]
            if columns != [('operation', 'TEXT', 0, 1), ('payload', 'TEXT', 1, 0), ('receipt', 'TEXT', 0, 0)]:
                raise sqlite3.DatabaseError('existing receipt ledger columns invalid')
        ensure_initialized_marker(path)
    except BaseException:
        conn.close()
        raise
    return conn


def valid_receipt(value):
    return bool(isinstance(value, dict) and set(value) == {'project_id', 'analysis_run_id'}
        and isinstance(value['project_id'], str) and _ID.fullmatch(value['project_id'])
        and (value['analysis_run_id'] is None or isinstance(value['analysis_run_id'], str)
             and _ID.fullmatch(value['analysis_run_id'])))


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate receipt field')
        result[key] = value
    return result


def claim(path, operation, payload):
    conn = connect(path)
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT payload, receipt FROM import_receipts WHERE operation=?', (operation,)).fetchone()
        if row:
            if row[0] != payload or row[1] is None:
                raise uncertain()
            try:
                receipt = json.loads(row[1], object_pairs_hook=unique_fields)
            except (ValueError, TypeError):
                raise uncertain(503) from None
            if not valid_receipt(receipt):
                raise uncertain(503)
            return receipt
        conn.execute('INSERT INTO import_receipts(operation, payload) VALUES (?,?)', (operation, payload))
        conn.commit()
        return None
    finally:
        conn.close()


def complete(path, operation, payload, receipt):
    if not valid_receipt(receipt):
        raise uncertain(503)
    conn = connect(path)
    try:
        updated = conn.execute('UPDATE import_receipts SET receipt=? WHERE operation=? AND payload=? AND receipt IS NULL',
            (json.dumps(receipt, sort_keys=True), operation, payload)).rowcount
        if updated != 1:
            raise uncertain(503)
        conn.commit()
    finally:
        conn.close()


async def fingerprint(values):
    """Hash bounded chunks, not multipart boundaries. Never store names, media or settings."""
    material = {key: value for key, value in values.items()
                if key not in ('request', 'db', 'video', 'subtitle', 'import_operation_id')}
    form = await values['request'].form()
    material['wire_fields'] = [(key, value) for key, value in form.multi_items()
                              if key != 'import_operation_id' and not isinstance(value, UploadFile)]
    for key in ('video', 'subtitle'):
        file = values.get(key)
        if file is None:
            continue
        digest = hashlib.sha256()
        count = 0
        while chunk := await file.read(1024 * 1024):
            count += len(chunk)
            if key == 'subtitle' and count > 2 * 1024 * 1024:
                raise HTTPException(422, '字幕文件为空或超过 2 MB')
            digest.update(chunk)
        await file.seek(0)
        if not count:
            raise HTTPException(422, '上传文件为空，请重新选择')
        material[key] = {'sha256': digest.hexdigest(), 'size': count,
                         'name': file.filename, 'type': file.content_type}
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def idempotent_import(fn):
    @functools.wraps(fn)
    async def wrapped(*args, **kwargs):
        key = kwargs.get('import_operation_id')
        request = kwargs.get('request')
        form = await request.form() if hasattr(request, 'form') else {}
        if key is None and 'import_operation_id' not in form:
            return await fn(*args, **kwargs)
        files = [kwargs.get('video'), kwargs.get('subtitle')]
        try:
            if (not isinstance(key, str) or not _ID.fullmatch(key)
                    or len(form.getlist('import_operation_id')) != 1
                    or kwargs.get('video') is None or any(
                    kwargs.get(field) for field in ('url', 'obs_capture_id', 'twitch_video_id', 'channel_replay_id'))):
                raise HTTPException(422, '仅本地视频上传支持导入操作回执')
            operation = hashlib.sha256(key.encode()).hexdigest()
            payload = await fingerprint(kwargs)
            path = ledger_path()
            project_id = operation_project_id(key)
            db = kwargs['db']
            if not path.exists():
                exists = db.get(Project, project_id) is not None
                db.rollback()  # A read-only probe must not hold a SQLite snapshot during creation.
                if exists or store.directory(project_id).exists():
                    raise uncertain(503)
            try:
                receipt = await run_in_threadpool(claim, path, operation, payload)
            except (OSError, sqlite3.Error):
                raise uncertain(503) from None
            if receipt is not None:
                return receipt
            exists = db.get(Project, project_id) is not None
            db.rollback()
            if exists or store.directory(project_id).exists():
                raise uncertain(503)  # Missing receipt rows are not permission to repeat a known project.
            # Do not release this reservation on exceptions: project/dispatch may already exist.
            try:
                receipt = await fn(*args, **kwargs)
            except IntegrityError:
                # Another worker/data-directory may have won the project's unique PK.
                raise uncertain(503) from None
            try:
                await run_in_threadpool(complete, path, operation, payload, receipt)
            except (OSError, sqlite3.Error):
                raise uncertain(503) from None
            return receipt
        finally:
            for file in files:
                if file is not None:
                    await file.close()
    return wrapped
