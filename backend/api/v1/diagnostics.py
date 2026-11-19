"""Local-only diagnostics consent and one-click submit. No public upload host is assumed."""
from __future__ import annotations

import ipaddress

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.services.diagnostics import queue
from backend.services.diagnostics.consent import load
from backend.services.diagnostics.service import (
    DiagnosticsError,
    delete_local,
    preview,
    set_consent,
    submit,
)
from backend.services.diagnostics.upload import endpoint

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host == "testclient":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="forbidden")


class ConsentBody(BaseModel):
    diagnostics: bool = False
    media: bool = False
    full_original: bool = False
    informed: bool = False


class SubmitBody(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    attempt_id: str = Field(default="", max_length=80)
    roles: list[str] = Field(default_factory=list)
    informed: bool = False
    full_original_ack: bool = False
    subtitle_ack: bool = False
    also_enable_background: bool = False
    save_local: bool = False


def _http(error: DiagnosticsError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.reason)


@router.get("/consent")
def get_consent(request: Request):
    _local(request)
    view = load().public()
    view["endpoint_configured"] = bool(endpoint())
    return view


@router.put("/consent")
def put_consent(body: ConsentBody, request: Request):
    _local(request)
    try:
        consent = set_consent(
            diagnostics=body.diagnostics, media=body.media,
            full_original=body.full_original, informed=body.informed,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=422, detail="informed_required") from exc
    view = consent.public()
    view["endpoint_configured"] = bool(endpoint())
    return view


@router.get("/preview")
def get_preview(request: Request, project_id: str = Query(min_length=1), attempt_id: str = Query(default="")):
    _local(request)
    try:
        return preview(project_id, attempt_id)
    except DiagnosticsError as exc:
        raise _http(exc) from exc


@router.post("/submit")
def post_submit(body: SubmitBody, request: Request):
    _local(request)
    try:
        return submit(
            body.project_id, body.attempt_id, roles=body.roles, informed=body.informed,
            full_original_ack=body.full_original_ack, subtitle_ack=body.subtitle_ack,
            also_enable_background=body.also_enable_background, save_local=body.save_local,
        )
    except DiagnosticsError as exc:
        raise _http(exc) from exc


@router.get("/cases")
def get_cases(request: Request):
    _local(request)
    from backend.services.diagnostics.service import _public_item
    return {"cases": [_public_item(item) for item in queue.list_items()]}


@router.get("/cases/{item_id}")
def get_case(item_id: str, request: Request):
    _local(request)
    from backend.services.diagnostics.service import _public_item
    item = queue.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="case")
    return _public_item(item)


@router.delete("/cases/{item_id}")
def delete_case(item_id: str, request: Request):
    _local(request)
    try:
        return delete_local(item_id)
    except DiagnosticsError as exc:
        raise _http(exc) from exc
