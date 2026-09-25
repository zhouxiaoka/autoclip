"""片源下载进度必须能被下一次读取看见。

原地 dict.update() 不会让 SQLAlchemy 更新 JSON 列，进度会停在创建时的 0%。
项目卡又把没有下载字段的 pending 画成 5%，看起来像停在约 5%。
"""
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from backend.models.base import Base
import backend.models  # noqa: F401  注册关联表
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.services.download_progress import save_processing_config


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def _create_downloading_project(Session):
    db = Session()
    project = Project(
        name="yt",
        status=ProjectStatus.PENDING,
        project_type=ProjectType.DEFAULT,
        processing_config={
            "download_status": "downloading",
            "download_progress": 0.0,
            "youtube_info": {"title": "clip"},
        },
    )
    db.add(project)
    db.commit()
    project_id = project.id
    db.close()
    return project_id


def test_in_place_json_update_is_not_persisted():
    Session = _session()
    project_id = _create_downloading_project(Session)

    db = Session()
    project = db.query(Project).filter(Project.id == project_id).one()
    # 这是修复前 youtube/bilibili update_project_download_progress 的写法。
    project.processing_config.update({
        "download_progress": 30.0,
        "download_message": "正在下载视频...",
    })
    db.commit()
    db.close()

    db = Session()
    loaded = db.query(Project).filter(Project.id == project_id).one()
    assert loaded.processing_config["download_progress"] == 0.0
    db.close()


def test_save_processing_config_persists_progress_and_keeps_existing_fields():
    Session = _session()
    project_id = _create_downloading_project(Session)

    db = Session()
    project = db.query(Project).filter(Project.id == project_id).one()
    save_processing_config(project, {
        "download_progress": 30.0,
        "download_message": "正在下载视频...",
    })
    db.commit()
    db.close()

    db = Session()
    loaded = db.query(Project).filter(Project.id == project_id).one()
    assert loaded.processing_config["download_progress"] == 30.0
    assert loaded.processing_config["download_message"] == "正在下载视频..."
    assert loaded.processing_config["download_status"] == "downloading"
    assert loaded.processing_config["youtube_info"]["title"] == "clip"
    db.close()


def test_youtube_and_bilibili_download_routes_assign_a_new_config_dict():
    root = Path(__file__).resolve().parents[1] / "api" / "v1"
    for name in ("youtube.py", "bilibili.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "processing_config.update" not in text
        assert "save_processing_config" in text
