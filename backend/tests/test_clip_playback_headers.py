"""Clip playback must be inline so macOS WKWebView will play the file."""

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.responses import FileResponse

from backend.utils.content_disposition import content_disposition_header


def test_content_disposition_header_is_latin1_for_non_ascii_names():
    from urllib.parse import quote

    filename = "切片_你好世界.mp4"
    header = content_disposition_header(filename, "inline")
    header.encode("latin-1")
    assert header.startswith("inline;")
    assert "filename*=UTF-8''" in header
    assert "你好" not in header
    # Same encoding the download endpoint used before this helper.
    assert header == f"inline; filename*=UTF-8''{quote(filename.encode('utf-8'))}"


def test_get_project_clip_non_ascii_filename_does_not_raise(tmp_path, monkeypatch):
    """Regression: non-ASCII on-disk clip names used to 500 in get_project_clip.

    Starlette latin-1-encodes response headers. Passing the raw filename into
    Content-Disposition raises UnicodeEncodeError.
    """
    clip_id = "clip123"
    filename = f"{clip_id}_中文标题.mp4"
    project_dir = tmp_path / "proj"
    clips_dir = project_dir / "output" / "clips"
    clips_dir.mkdir(parents=True)
    video = clips_dir / filename
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(
        "backend.core.path_utils.get_project_directory",
        lambda _project_id: project_dir,
    )
    from backend.api.v1.projects import get_project_clip

    response = asyncio.run(get_project_clip("project-1", clip_id, Mock()))
    from starlette.testclient import TestClient

    sent = TestClient(response).get("/")
    assert sent.status_code == 200
    assert sent.content.startswith(b"\x00\x00\x00\x18")
    disposition = sent.headers["content-disposition"]
    disposition.encode("latin-1")
    lowered = disposition.lower()
    assert lowered.startswith("inline")
    assert "attachment" not in lowered.split(";")[0]
    assert "filename*=" in lowered
    assert "中文" not in disposition
    assert sent.headers["content-type"].startswith("video/mp4")


def test_raw_non_ascii_content_disposition_raises_unicode_encode_error(tmp_path: Path):
    """The Sentry failure: latin-1 header encoding rejects a raw non-ASCII filename."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    with pytest.raises(UnicodeEncodeError):
        FileResponse(
            path=str(video),
            media_type="video/mp4",
            headers={"Content-Disposition": 'inline; filename="中文标题.mp4"'},
        )


def test_playback_response_is_inline_not_attachment(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    response = FileResponse(
        path=str(video),
        media_type="video/mp4",
        filename=video.name,
        content_disposition_type="inline",
    )
    disposition = response.headers["content-disposition"].lower()
    assert disposition.startswith("inline")
    assert "attachment" not in disposition.split(";")[0]


def test_clip_playback_routes_request_inline_disposition():
    root = Path(__file__).resolve().parents[2]
    projects = (root / "backend/api/v1/projects.py").read_text(encoding="utf-8")
    files = (root / "backend/api/v1/files.py").read_text(encoding="utf-8")
    clip = projects.split("async def get_project_clip(", 1)[1].split("\nasync def ", 1)[0]
    clip_video = files.split("async def get_project_clip_video(", 1)[1].split("\nasync def ", 1)[0]
    collection = files.split("async def get_project_collection_video(", 1)[1].split("\nasync def ", 1)[0]
    for name, body in (("clip", clip), ("clip_video", clip_video), ("collection", collection)):
        assert 'content_disposition_type="inline"' in body, name
