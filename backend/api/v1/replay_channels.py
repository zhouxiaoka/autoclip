from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services import replay_channels as channels

router = APIRouter()
Provider = Literal['twitch', 'youtube']


@router.get('/availability')
def availability():
    # Rendering the picker must not open the keychain or contact a platform.
    result = {}
    for provider in ('twitch', 'youtube'):
        try:
            result[provider] = bool(channels.config(provider)[0])
        except HTTPException:
            result[provider] = False
    return result


@router.get('/{provider}')
def status(provider: Provider):
    return channels.state(provider)


@router.post('/{provider}/connect')
def connect(provider: Provider):
    return channels.begin(provider)


@router.post('/{provider}/connect/{attempt}')
def poll(provider: Provider, attempt: str):
    return channels.poll(provider, attempt)


@router.delete('/{provider}/connect/{attempt}')
def cancel(provider: Provider, attempt: str):
    with channels.locks[provider]:
        if channels.pending.get(provider, {}).get('id') == attempt:
            channels.cancel(provider)
    return {'cancelled': True}


@router.delete('/{provider}')
def disconnect(provider: Provider):
    return channels.disconnect(provider)


@router.get('/{provider}/archives')
def archives(provider: Provider, cursor: str = Query('', max_length=2048), db: Session = Depends(get_db)):
    return channels.list_archives(provider, cursor, db)


class Selection(BaseModel):
    archive_id: UUID | None


@router.put('/{provider}/selection')
def select(provider: Provider, selection: Selection, db: Session = Depends(get_db)):
    channels.select_archive(provider, str(selection.archive_id) if selection.archive_id else None, db)
    return {'saved': True}
