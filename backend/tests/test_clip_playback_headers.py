"""Clip playback must be inline so macOS WKWebView will play the file."""

from pathlib import Path

from fastapi.responses import FileResponse


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
