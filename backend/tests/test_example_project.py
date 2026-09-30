"""The bundled example project: idempotent, complete, playable, and clearly link-sourced."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(d))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(d))
    d.mkdir()
    return d


@pytest.fixture
def session(data_dir, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.core import database
    from backend.models import project as _p  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def test_manifest_and_media_are_bundled():
    from backend.services import example_project

    assert example_project.available()
    manifest = example_project.load_manifest()
    assert manifest["project"]["source_url"].startswith("https://www.youtube.com/watch?v=")
    assert (example_project.ASSETS / manifest["project"]["source"]).stat().st_size > 1_000_000
    assert (example_project.ASSETS / manifest["project"]["subtitles"]).read_text(encoding="utf-8").startswith("1\n00:00:00,000")
    assert len(manifest["clips"]) >= 2
    previous_end = 0.0
    for clip in manifest["clips"]:
        assert clip["title"] and 0 < clip["final_score"] <= 1
        start, end = example_project._seconds(clip["start_time"]), example_project._seconds(clip["end_time"])
        assert abs(start - previous_end) < 0.01, "passages are stitched back to back"
        assert end > start
        assert clip["original_start_time"], "the position in the original interview is kept for reference"
        previous_end = end
    assert abs(previous_end - manifest["project"]["video_duration"]) < 1


def test_create_is_idempotent_and_playable(session, data_dir):
    from backend.models.clip import Clip
    from backend.services import example_project

    project = example_project.create(session)
    again = example_project.create(session)
    assert again.id == project.id, "a second call must not create a duplicate"

    assert project.status.value == "completed"
    assert project.processing_config["example"] is True
    assert project.project_metadata["source_url"] == example_project.load_manifest()["project"]["source_url"]
    assert project.thumbnail.startswith("data:image/jpeg;base64,")

    root = data_dir / "projects" / project.id
    assert (root / "raw" / "input.mp4").exists() and (root / "raw" / "input.srt").exists(), "the editor and export need raw/input.*"
    assert project.video_path == str(root / "raw" / "input.mp4")

    clips = session.query(Clip).filter(Clip.project_id == project.id).all()
    assert len(clips) == len(example_project.load_manifest()["clips"])
    for clip in clips:
        path = Path(clip.video_path)
        assert path.exists() and path.parent == data_dir / "projects" / project.id / "output" / "clips"
        assert path.name.startswith(f"{clip.id}_"), "the clip endpoint looks files up by <clip_id>_*.mp4"
        assert clip.duration == clip.end_time - clip.start_time > 0
        assert clip.clip_metadata["recommend_reason"]
        assert path.stat().st_size > 500_000, "clip files are cut from the stitched source"

    metadata = json.loads((root / "metadata" / "clips_metadata.json").read_text(encoding="utf-8"))
    assert {m["id"] for m in metadata} == {c.id for c in clips}, "export looks clips up by database id"

    from backend.services.publish_export import (
        find_source_srt,
        find_source_video,
        load_clip_meta,
    )
    assert find_source_video(project.id) == root / "raw" / "input.mp4"
    assert find_source_srt(project.id) == root / "raw" / "input.srt"
    assert load_clip_meta(project.id, clips[0].id)["title"] == clips[0].title


def test_endpoints_report_and_create(session, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.v1 import example_project as api
    from backend.core.database import get_db

    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: session
    client = TestClient(app)

    assert client.get("/api/v1/example-project").json() == {"available": True, "project_id": None}
    created = client.post("/api/v1/example-project/create").json()
    assert created["project_id"]
    assert client.get("/api/v1/example-project").json()["project_id"] == created["project_id"]
    assert client.post("/api/v1/example-project/create").json()["project_id"] == created["project_id"]
