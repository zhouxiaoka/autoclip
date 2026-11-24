from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from backend.services.obs import settings, worker

router = APIRouter()


class Connection(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    enabled: bool
    port: int = Field(4455, ge=1, le=65535)
    password: SecretStr | None = Field(None, max_length=1024)


class Automation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    revision: str = Field('', max_length=36)
    digest: str = Field('', max_length=64)
    max_calls: int = Field(50, ge=1, le=500)


@router.get('')
def status(request: Request):
    monitor = request.app.state.obs
    cfg = settings.read()
    try:
        recipients, digest = settings.overview()
    except (ValueError, OSError):
        recipients, digest = [], ''
    return {
        'enabled': cfg['enabled'],
        'has_password': cfg['has_password'],
        'port': cfg['port'],
        'revision': cfg['revision'],
        'connected': monitor.state == 'connected' and cfg['enabled'] and monitor.revision == cfg['revision'],
        'connection': monitor.state,
        'version': monitor.version,
        'phase': monitor.phase,
        'recording': monitor.recording,
        'supported': monitor.supported,
        'directory': monitor.directory,
        'automatic': bool(cfg['consent'] and cfg['consent'] == digest),
        'changed': bool(cfg['consent'] and cfg['consent'] != digest),
        'digest': digest,
        'max_calls': cfg['max_calls'],
        'latest': worker.latest(),
        'recipients': [{key: value for key, value in item.items() if key != 'base'} for item in recipients],
    }


@router.put('/connection')
async def connection(request: Request, body: Connection):
    import asyncio

    password = body.password.get_secret_value() if body.password is not None else None
    try:
        await asyncio.to_thread(settings.connect, body.enabled, body.port, password)
    except Exception:
        raise HTTPException(409, 'credential_store') from None
    request.app.state.obs.changed.set()
    return {'saved': True}


@router.put('/automation')
async def automation(request: Request, body: Automation):
    monitor = request.app.state.obs
    cfg = settings.read()
    if body.enabled and (
        not body.digest
        or not cfg['enabled']
        or cfg['revision'] != body.revision
        or monitor.revision != cfg['revision']
        or monitor.state != 'connected'
        or not monitor.supported
        or not monitor.directory
    ):
        raise HTTPException(409, 'connection_changed')
    try:
        settings.arm(monitor.directory, body.digest if body.enabled else '', body.max_calls, body.revision)
    except (ValueError, OSError):
        raise HTTPException(409, 'consent_changed') from None
    # Updating automation policy must not disconnect an active OBS session or drop live state.
    if monitor.state == 'connected' and monitor.revision == cfg['revision']:
        monitor.revision = settings.read()['revision']
    return {'saved': True}


@router.get('/replays')
def list_replays(request: Request):
    monitor = request.app.state.obs
    return {'connection': monitor.state, 'phase': monitor.phase, 'items': worker.replays()}


@router.post('/replays/{capture_id}/generate', status_code=202)
async def generate_replay(capture_id: str, request: Request):
    import asyncio

    if not await asyncio.to_thread(worker.request_manual, capture_id):
        raise HTTPException(409, 'replay_unavailable')
    request.app.state.obs.work.set()
    return {'accepted': True}
