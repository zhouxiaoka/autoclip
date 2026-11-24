import hashlib
import json
import time
import uuid
from pathlib import Path
from sqlalchemy import text
from urllib.parse import urlsplit
from backend.core.database import session_scope
from backend.core.path_utils import get_data_directory
from backend.services import ai_model_settings as ai
from .models import ObsSettings


def keychain():
    # Choose the OS credential store explicitly. Never fall back to a plaintext backend.
    import sys

    if sys.platform == 'darwin':
        from keyring.backends.macOS import Keyring
    elif sys.platform == 'win32':
        from keyring.backends.Windows import WinVaultKeyring as Keyring
    else:
        raise RuntimeError('credential_store')
    return Keyring()


def credential_id():
    return hashlib.sha256(str(get_data_directory().resolve()).encode()).hexdigest()


def config(db):
    return db.get(ObsSettings, 1) or ObsSettings(
        id=1,
        enabled=False,
        port=4455,
        has_password=False,
        revision='',
        directory='',
        consent='',
        consent_epoch='',
        consent_at=0,
        max_calls=50,
    )


def overview():
    model = ai.load()
    if not model or not model.analysis:
        return [], ''
    connections = {c.id: c for c in model.connections}
    roles = [('analysis', model.analysis)]
    vision = ai.vision_follow_binding(model)
    if ai.sees_images(model, vision):
        roles.append(('vision', vision))
    if model.transcription and model.transcription.provider == 'cloud':
        roles.append(('audio', model.transcription))
    recipients, identity = [], []
    for role, binding in roles:
        c = connections.get(binding.connection_id)
        if not c:
            return [], ''
        # Full destination affects consent. Only the hostname is shown or returned.
        base = ai.chat_endpoint(c, binding.model)['base_url'].rstrip('/')
        recipients.append(
            {
                'role': role,
                'provider': c.provider,
                'host': urlsplit(base).hostname or c.provider,
                'model': binding.model,
                'base': base,
            }
        )
        identity.append((role, binding.model, binding.connection_id, base, c.provider))
    identity.extend(
        [
            model.analysis_mode,
            model.allow_visual_screening,
            model.transcription.model_dump() if model.transcription else None,
            model.analysis.model_dump(),
            model.vision.model_dump() if model.vision else None,
            'obs-v1',
        ]
    )
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return recipients, digest


def read():
    with session_scope() as db:
        row = config(db)
        return {
            key: getattr(row, key)
            for key in (
                'enabled',
                'has_password',
                'port',
                'revision',
                'directory',
                'consent',
                'consent_epoch',
                'max_calls',
            )
        }


def connect(enabled: bool, port: int, password: str | None):
    with session_scope() as db:
        row = config(db)
        if password:
            keychain().set_password('AutoClip OBS', credential_id(), password)
            row.has_password = True
        elif password == '' and row.has_password:
            keychain().delete_password('AutoClip OBS', credential_id())
            row.has_password = False
        if row.port != port:
            row.consent = row.consent_epoch = ''
        row.enabled, row.port, row.revision = enabled, port, str(uuid.uuid4())
        db.add(row)
        db.commit()


def arm(directory: str, digest: str, max_calls: int, revision: str | None = None):
    with session_scope() as db:
        db.execute(text('BEGIN IMMEDIATE'))
        row = config(db)
        if digest:
            if revision is not None and (row.revision != revision or not row.enabled):
                raise ValueError('connection_changed')
            path = Path(directory).expanduser()
            if not path.is_absolute() or not path.is_dir() or digest != overview()[1]:
                raise ValueError('consent_changed')
            row.directory = str(path.resolve())
        row.consent, row.max_calls = digest, max_calls
        row.consent_epoch = str(uuid.uuid4()) if digest else ''
        row.consent_at, row.revision = time.time(), str(uuid.uuid4())
        db.add(row)
        db.commit()
