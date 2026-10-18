"""local-only endpoints the desktop shell calls; never part of the public /api/v1 surface."""
from __future__ import annotations

import hmac
import ipaddress

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from backend.core.launch_token import TOKEN_ENV  # noqa: F401 - re-exported for tests

router = APIRouter()


class ShutdownIntent(BaseModel):
    kind: str


def _loopback(request: Request) -> bool:
    host = request.client.host if request.client else ''
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _authorized(token: str | None) -> bool:
    from backend.core import launch_token
    expected = launch_token.get()
    return bool(expected) and bool(token) and hmac.compare_digest(token.encode(), expected.encode())


@router.post('/internal/shutdown-intent')
def shutdown_intent(body: ShutdownIntent, request: Request, x_autoclip_local_token: str | None = Header(default=None)):
    """Write the clean-quit marker, then return. Does NOT begin a shutdown: the shell kills us after 200."""
    if not _loopback(request) or not _authorized(x_autoclip_local_token):
        raise HTTPException(status_code=403, detail='forbidden')  # never echo or log the token
    from backend.services.studio.shutdown_marker import INTENT_KINDS, mark
    if body.kind not in INTENT_KINDS:
        raise HTTPException(status_code=422, detail='invalid kind')
    if not mark(body.kind):
        raise HTTPException(status_code=500, detail='marker not written')
    return {'ok': True}
