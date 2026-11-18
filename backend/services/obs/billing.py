"""Write-ahead receipts at the actual model transport boundary for OBS projects."""

import hashlib
import json
import uuid

from sqlalchemy import text
from backend.core.database import session_scope
from backend.core.project_cancellation import current
from . import settings
from .models import ObsCall, ObsCapture

# A private UUID namespace identifies OBS workers without DB reads for ordinary projects.
_NODE = '0b5a07c11e01'
_PROCESS = str(uuid.uuid4())


def project_id(session_id):
    return str(uuid.uuid5(uuid.NAMESPACE_OID, session_id))[:-12] + _NODE


def is_obs(pid=None):
    pid = pid if pid is not None else current()
    return bool(pid and pid.endswith(_NODE) and pid[14:15] == '5')


class CallPaused(RuntimeError):
    pass


def run(role, base, model, inputs, send):
    pid = current()
    if not is_obs(pid):
        return send()
    recipients, digest = settings.overview()
    signature = hashlib.sha256(
        json.dumps([role, base, model, inputs], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with session_scope() as db:
        # Serialize budget reservation, enable/disable and cache checks across workers.
        db.execute(text('BEGIN IMMEDIATE'))
        cfg = settings.config(db)
        receipt = db.query(ObsCapture).filter_by(project_id=pid).one()
        if receipt.status not in ('dispatching', 'submitted'):
            raise CallPaused('OBS automation paused')
        if (
            not cfg.consent
            or digest != cfg.consent
            or receipt.epoch != cfg.consent_epoch
            or not any(
                r['role'] == role and r['model'] == model and r['base'] == base.rstrip('/')
                for r in recipients
            )
        ):
            receipt.status = 'paused'
            db.commit()
            raise CallPaused('OBS model consent changed')
        if (
            db.query(ObsCall)
            .filter(ObsCall.project_id == pid, ObsCall.result.is_(None), ObsCall.process != _PROCESS)
            .first()
        ):
            receipt.status = 'uncertain'
            db.commit()
            raise CallPaused('OBS model response unknown after restart')
        cached = db.query(ObsCall).filter_by(project_id=pid, signature=signature).first()
        if cached:
            if cached.result is not None:
                return json.loads(cached.result)
            raise CallPaused('OBS model response pending')
        if db.query(ObsCall).filter_by(project_id=pid).count() >= cfg.max_calls:
            receipt.status = 'limit'
            db.commit()
            raise CallPaused('OBS model call limit reached')
        db.add(ObsCall(project_id=pid, signature=signature, process=_PROCESS))
        db.commit()
    try:
        result = send()
        serialized = json.dumps(result, ensure_ascii=False)
        with session_scope() as db:
            db.query(ObsCall).filter_by(project_id=pid, signature=signature).update({'result': serialized})
            db.commit()
        return result
    except BaseException:
        with session_scope() as db:
            db.query(ObsCapture).filter_by(project_id=pid).update({'status': 'uncertain'})
            db.commit()
        raise


def chat(role, base, body, key, timeout):
    import requests
    from backend.core.llm_stream import budget_watch
    from backend.core.llm_providers import http_chat_body

    def send():
        with requests.post(
            base.rstrip('/') + '/chat/completions',
            json=http_chat_body(body),
            headers={'Authorization': 'Bearer ' + key} if key else {},
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code != 200:
                raise CallPaused(f'OBS model HTTP {response.status_code}')
            response.encoding = 'utf-8'
            with budget_watch(response):
                # Reuse the Studio SSE / JSON parser, including its size and time limits.
                from backend.core.llm_stream import _collect_requests

                return _collect_requests(response).as_completion()

    return run(role, base, body['model'], body, send)
