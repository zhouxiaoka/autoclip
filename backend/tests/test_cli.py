"""autoclip CLI / local_runner：参数解析、项目目录准备、结果汇总、进度监听（不跑真流水线、不联网）"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """独立数据目录 + 独立 SQLite，避免碰用户真实目录"""
    d = tmp_path / "data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(d))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'test.db'}")
    d.mkdir()
    return d


def _fake_project(data_dir: Path, project_id: str = "p1", name: str = "示例") -> Path:
    pdir = data_dir / "projects" / project_id
    (pdir / "metadata").mkdir(parents=True)
    (pdir / "output" / "clips").mkdir(parents=True)
    (pdir / "project.json").write_text(json.dumps({"project_name": name, "source": {"via": "cli"}}), encoding="utf-8")
    clips = [
        {"id": "1", "generated_title": "低分", "start_time": "00:00:01,000", "end_time": "00:00:05,000", "final_score": 0.62},
        {"id": "2", "generated_title": "高分", "start_time": "00:01:00,000", "end_time": "00:01:30,000", "final_score": 9.1},
    ]
    (pdir / "metadata" / "clips_metadata.json").write_text(json.dumps(clips, ensure_ascii=False), encoding="utf-8")
    (pdir / "metadata" / "collections_metadata.json").write_text(
        json.dumps([{"id": "1", "collection_title": "合集甲", "clip_ids": ["1", "2"]}], ensure_ascii=False), encoding="utf-8")
    clip_paths = [str(pdir / "output" / "clips" / "1_低分.mp4"), str(pdir / "output" / "clips" / "2_高分.mp4")]
    (pdir / "output" / "step6_video_output.json").write_text(
        json.dumps({"clip_paths": clip_paths, "collection_paths": [str(pdir / "output" / "collections" / "合集甲.mp4")]}, ensure_ascii=False),
        encoding="utf-8")
    return pdir


# ---------------------------------------------------------------- parser ---
def test_parser_run_accepts_provider_presets():
    from backend.cli import build_parser

    args = build_parser().parse_args(["run", "v.mp4", "--provider", "ollama", "--model", "qwen2.5:7b", "--min-score", "0.5", "--json"])
    assert args.cmd == "run" and args.provider == "ollama" and args.min_score == 0.5 and args.json is True

    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "v.mp4", "--provider", "nope"])

    exp = build_parser().parse_args(["export", "pid", "--preset", "douyin", "--clip", "2", "--no-title"])
    assert exp.cmd == "export" and exp.preset == "douyin" and exp.clip == ["2"] and exp.no_title is True


def test_cli_help_runs_without_backend(data_dir):
    p = subprocess.run([sys.executable, "-m", "backend.cli", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0
    assert "autoclip" in p.stdout and "--provider ollama" in p.stdout


# ---------------------------------------------------------------- runner ---
def test_summarize_project_normalizes_scores_and_paths(data_dir):
    from backend.services.local_runner import summarize_project

    _fake_project(data_dir)
    s = summarize_project("p1")

    assert s["name"] == "示例"
    assert s["counts"] == {"clips": 2, "collections": 1}
    # 0–1 与 0–10 两种口径都归一到 0–100，且按分数倒序
    assert [c["score_100"] for c in s["clips"]] == [91, 62]
    assert s["clips"][0]["file"].endswith("2_高分.mp4")
    assert s["collections"][0]["file"].endswith("合集甲.mp4")


def test_list_projects_reads_filesystem(data_dir):
    from backend.services.local_runner import list_projects

    _fake_project(data_dir, "p1", "甲")
    _fake_project(data_dir, "p2", "乙")
    items = list_projects()
    assert {i["name"] for i in items} == {"甲", "乙"}
    assert all(i["status"] == "completed" and i["clips"] == 2 for i in items)


@pytest.fixture
def isolated_db(data_dir, monkeypatch):
    """backend.core.database 的 engine 是 import 时定死的，可能已被别的测试模块指到别处；这里换成临时库。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import backend.core.database as database
    from backend.models import project as _  # noqa: F401  确保模型注册到 Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_local)
    monkeypatch.setattr(database, "create_tables", lambda: None)
    return session_local


def test_prepare_project_links_video_and_registers_db(data_dir, tmp_path, isolated_db, monkeypatch):
    from backend.services import local_runner
    from backend.services.local_runner import RunRequest, prepare_project

    # 不真的调 ffmpeg 抽帧
    import backend.utils.thumbnail_generator as tg
    monkeypatch.setattr(tg, "generate_project_thumbnail", lambda *a, **k: None)

    video = tmp_path / "talk.mp4"
    video.write_bytes(b"\x00" * 1024)
    req = RunRequest(video=video, name="链接测试", register_db=True)
    target = prepare_project(req, link=True)

    assert target.exists() and target.name == "input.mp4"
    assert target.stat().st_size == 1024
    meta = json.loads((target.parent.parent / "project.json").read_text(encoding="utf-8"))
    assert meta["project_name"] == "链接测试" and meta["source"]["via"] == "cli"

    from backend.models.project import Project
    db = isolated_db()
    try:
        row = db.query(Project).filter(Project.id == req.project_id).first()
        assert row is not None and row.name == "链接测试"
        assert row.status.value == "processing"
    finally:
        db.close()

    # 状态回写
    local_runner._set_project_status(req.project_id, "completed")
    db = isolated_db()
    try:
        assert db.query(Project).filter(Project.id == req.project_id).first().status.value == "completed"
    finally:
        db.close()

    # 再跑一次不重复建行
    prepare_project(req, link=True)
    db = isolated_db()
    try:
        assert db.query(Project).filter(Project.id == req.project_id).count() == 1
    finally:
        db.close()


def test_prepare_project_missing_video(data_dir, tmp_path):
    from backend.services.local_runner import RunRequest, prepare_project

    with pytest.raises(FileNotFoundError):
        prepare_project(RunRequest(video=tmp_path / "nope.mp4", register_db=False))


def test_progress_listener_receives_payload(data_dir):
    from backend.services import simple_progress as sp

    got = []
    sp.add_progress_listener(got.append)
    try:
        sp.emit_progress("proj-x", "ANALYZE", "时间线提取完成", subpercent=50)
    finally:
        sp.remove_progress_listener(got.append)
    assert got and got[-1]["project_id"] == "proj-x" and got[-1]["stage"] == "ANALYZE"
    assert got[-1]["percent"] == sp.compute_percent("ANALYZE", 50)
    # 移除后不再收到
    sp.emit_progress("proj-x", "EXPORT", "x")
    assert len(got) == 1


def test_default_app_dir_follows_env(monkeypatch, tmp_path):
    from backend.services.local_runner import default_app_dir

    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path / "x"))
    assert default_app_dir() == tmp_path / "x"
    monkeypatch.delenv("AUTOCLIP_DATA_DIR")
    monkeypatch.delenv("AUTOCLIP_APP_DIR", raising=False)
    assert default_app_dir().name == "AutoClip"


# ---------------------------------------------------------------- mcp ---
def test_mcp_server_registers_tools(data_dir):
    pytest.importorskip("mcp")
    import asyncio
    from backend import mcp_server

    tools = asyncio.run(mcp_server.server.list_tools())
    names = {t.name for t in tools}
    assert {"clip_video", "start_clip_job", "get_job_status", "get_project", "list_projects", "list_providers", "check_environment", "export_clip"} <= names


def test_mcp_get_project_falls_back_to_disk(data_dir):
    pytest.importorskip("mcp")
    from backend import mcp_server

    _fake_project(data_dir, "p9", "磁盘项目")
    r = mcp_server.get_job_status("p9")
    assert r["ok"] is True and r["status"] == "completed" and r["result"]["name"] == "磁盘项目"
    assert mcp_server.get_job_status("missing")["ok"] is False
