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
    def __init__(self, message: str, *, uncertain: bool = False, code: str = 'provider_error', user_message: str = ''):
        super().__init__(message)
        self.uncertain = uncertain
        self.code = code
        self.user_message = user_message or 'OBS 自动出片已暂停，请到「设置 → 应用 → OBS Studio」查看状态。'


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
            raise CallPaused(
                'OBS model consent changed',
                user_message='模型配置或自动出片授权已变更，已暂停本次自动制作，请到 OBS 设置重新确认。',
            )
        if (
            db.query(ObsCall)
            .filter(ObsCall.project_id == pid, ObsCall.result.is_(None), ObsCall.process != _PROCESS)
            .first()
        ):
            receipt.status = 'uncertain'
            db.commit()
            raise CallPaused(
                'OBS model response unknown after restart',
                uncertain=True,
                user_message='应用重启前有模型请求尚未确认结果，为避免重复计费已停止自动重试。',
            )
        cached = db.query(ObsCall).filter_by(project_id=pid, signature=signature).first()
        if cached:
            if cached.result is not None:
                return json.loads(cached.result)
            raise CallPaused(
                'OBS model response pending',
                uncertain=True,
                user_message='模型请求结果待确认，为避免重复计费已停止自动重试。',
            )
        if db.query(ObsCall).filter_by(project_id=pid).count() >= cfg.max_calls:
            receipt.status = 'limit'
            db.commit()
            raise CallPaused(
                'OBS model call limit reached',
                code='rate_limited',
                user_message='已达到本场 OBS 自动出片的模型请求次数上限，可在 OBS 设置中调整上限后手动导入。',
            )
        db.add(ObsCall(project_id=pid, signature=signature, process=_PROCESS))
        db.commit()
    try:
        result = send()
        serialized = json.dumps(result, ensure_ascii=False)
        with session_scope() as db:
            db.query(ObsCall).filter_by(project_id=pid, signature=signature).update({'result': serialized})
            db.commit()
        return result
    except BaseException as exc:
        with session_scope() as db:
            if isinstance(exc, CallPaused) and not exc.uncertain:
                # Deterministic client/auth/rate-limit rejections did not complete a billable
                # reply; record an actionable capture state instead of masking it as uncertain.
                next_status = 'setup_required' if exc.code in ('authentication', 'permission_denied', 'bad_endpoint') else 'paused'
                db.query(ObsCall).filter_by(project_id=pid, signature=signature, result=None).delete()
                db.query(ObsCapture).filter_by(project_id=pid).update({'status': next_status})
            else:
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
                status = response.status_code
                if status == 401:
                    raise CallPaused(
                        f'OBS model HTTP {status}',
                        uncertain=False,
                        code='authentication',
                        user_message='模型 API Key 无效或已过期，请到模型设置更新后再试。',
                    )
                if status == 403:
                    raise CallPaused(
                        f'OBS model HTTP {status}',
                        uncertain=False,
                        code='permission_denied',
                        user_message='当前令牌没有该模型权限，请到模型设置核对后再试。',
                    )
                if status == 429:
                    raise CallPaused(
                        f'OBS model HTTP {status}',
                        uncertain=False,
                        code='rate_limited',
                        user_message='模型服务触发限流或额度不足，已停止自动重试。',
                    )
                if status in (400, 404):
                    raise CallPaused(
                        f'OBS model HTTP {status}',
                        uncertain=False,
                        code='bad_endpoint' if status == 404 else 'provider_error',
                        user_message='模型请求参数或接口地址被服务商拒绝，请检查模型设置。',
                    )
                raise CallPaused(f'OBS model HTTP {status}', uncertain=True)
            response.encoding = 'utf-8'
            with budget_watch(response):
                # Reuse the Studio SSE / JSON parser, including its size and time limits.
                from backend.core.llm_stream import _collect_requests

                return _collect_requests(response).as_completion()

    return run(role, base, body['model'], body, send)
