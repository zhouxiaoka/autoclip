"""Upload-Post 发布：配置优先级、表单拼装、错误映射、状态归一化、CLI / MCP / API 注册（不联网、不跑 ffmpeg）"""
import json
import os
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
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'test.db'}")
    for name in ("UPLOAD_POST_API_KEY", "UPLOAD_POST_USER", "UPLOAD_POST_API_BASE"):
        monkeypatch.delenv(name, raising=False)
    d.mkdir()
    return d


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Session:
    """记录请求、按顺序返回预设响应"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _take(self):
        return self.responses.pop(0) if self.responses else _Resp(200, {})

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._take()

    def post(self, url, **kw):
        # 文件句柄在 with 里会被关掉，先把表单快照下来
        self.calls.append(("POST", url, {k: v for k, v in kw.items() if k != "files"} | {"files": list(kw.get("files", {}).keys())}))
        return self._take()


def _fake_clip(data_dir: Path, project_id="p1", clip_id="2", title="高分片段") -> Path:
    from backend.core.path_utils import get_project_directory
    pdir = get_project_directory(project_id)
    (pdir / "metadata").mkdir(parents=True, exist_ok=True)
    (pdir / "metadata" / "clips_metadata.json").write_text(json.dumps([
        {"id": clip_id, "generated_title": title, "start_time": "00:00:01,000", "end_time": "00:00:20,000"}
    ], ensure_ascii=False), encoding="utf-8")
    exports = pdir / "output" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    out = exports / f"{clip_id}_shorts.mp4"
    out.write_bytes(b"\x00" * 1024)
    return out


# ---------------------------------------------------------------- config ---
def test_config_env_overrides_file(data_dir, monkeypatch):
    from backend.services import upload_post_publisher as up

    assert up.load_config().configured is False and up.load_config().source == "none"

    cfg = up.save_config(api_key="file-key-1234567890", user="file-profile")
    assert cfg.source == "file" and cfg.user == "file-profile" and cfg.masked_key() == "file…7890"
    if os.name != "nt":
        assert (up.config_path().stat().st_mode & 0o777) == 0o600

    monkeypatch.setenv("UPLOAD_POST_API_KEY", "env-key-0987654321")
    cfg = up.load_config()
    assert cfg.source == "env" and cfg.api_key == "env-key-0987654321"
    # 环境变量没给 user 时，沿用文件里的
    assert cfg.user == "file-profile"

    monkeypatch.setenv("UPLOAD_POST_USER", "env-profile")
    assert up.load_config().user == "env-profile"

    up.clear_config()
    monkeypatch.delenv("UPLOAD_POST_API_KEY")
    assert up.load_config().configured is False


def test_save_config_keeps_untouched_fields(data_dir):
    from backend.services import upload_post_publisher as up

    up.save_config(api_key="k1-abcdefghij", user="u1")
    cfg = up.save_config(user="u2")
    assert cfg.api_key == "k1-abcdefghij" and cfg.user == "u2"


def test_requires_key_before_any_call(data_dir):
    from backend.services import upload_post_publisher as up

    with pytest.raises(up.UploadPostError, match="UPLOAD_POST_API_KEY"):
        up.list_profiles()
    with pytest.raises(up.UploadPostError):
        up.get_status("abc")


# ---------------------------------------------------------------- platforms / preset ---
def test_normalize_platforms_and_pick_preset():
    from backend.services import upload_post_publisher as up

    assert up.normalize_platforms(["TikTok", "youtube,instagram", "twitter", "tiktok"]) == ["tiktok", "youtube", "instagram", "x"]
    with pytest.raises(ValueError, match="不支持的平台"):
        up.normalize_platforms(["douyin"])
    with pytest.raises(ValueError):
        up.normalize_platforms([])
    assert up.pick_preset(["tiktok", "linkedin"]) == "shorts"
    assert up.pick_preset(["linkedin", "x"]) == "original"


# ---------------------------------------------------------------- publish ---
def test_publish_clip_builds_multipart_and_writes_record(data_dir, monkeypatch):
    from backend.services import upload_post_publisher as up

    exported = _fake_clip(data_dir)
    calls = {}

    def fake_export(req):
        calls["export"] = req
        return {"ok": True, "path": str(exported), "cached": True, "warnings": ["没找到中文字体，已跳过标题卡"]}

    monkeypatch.setattr("backend.services.publish_export.export_clip", fake_export)
    session = _Session([_Resp(200, {"success": True, "request_id": "srv-req-1", "total_platforms": 2})])
    cfg = up.UploadPostConfig(api_key="k-1234567890", user="default-profile", base_url="https://api.example.test")

    r = up.publish_clip(up.PublishRequest(
        project_id="p1", clip_id="2", platforms=["tiktok", "youtube"], description="desc",
        extra={"privacy_level": "SELF_ONLY", "youtube_notify_subscribers": False, "user": "should-be-ignored"},
    ), config=cfg, session=session)

    # 预设按平台自动选，导出走的是既有 export_clip
    assert calls["export"].preset == "shorts" and calls["export"].clip_id == "2"

    method, url, kw = session.calls[0]
    assert method == "POST" and url == "https://api.example.test/api/upload"
    assert kw["headers"]["Authorization"] == "Apikey k-1234567890"
    assert kw["headers"]["Idempotency-Key"] == kw["data"]["request_id"]
    assert kw["files"] == ["video"]
    form = kw["data"]
    assert form["user"] == "default-profile"                      # extra 里的 user 不能覆盖
    assert form["platform[]"] == ["tiktok", "youtube"]              # 重复字段按 list 传
    assert form["title"] == "高分片段" and form["description"] == "desc"
    assert form["async_upload"] == "true"
    assert form["external_id"] == "autoclip:p1:2"
    assert form["privacy_level"] == "SELF_ONLY" and form["youtube_notify_subscribers"] == "false"
    assert "scheduled_date" not in form

    assert r["ok"] and r["request_id"] == "srv-req-1" and r["preset"] == "shorts" and r["export_warnings"]
    records = up.list_records("p1")
    assert len(records) == 1 and records[0]["request_id"] == "srv-req-1" and records[0]["platforms"] == ["tiktok", "youtube"]


def test_publish_clip_scheduled_and_explicit_user(data_dir, monkeypatch):
    from backend.services import upload_post_publisher as up

    exported = _fake_clip(data_dir, clip_id="3")
    monkeypatch.setattr("backend.services.publish_export.export_clip", lambda req: {"ok": True, "path": str(exported)})
    session = _Session([_Resp(202, {"success": True, "request_id": "r2", "job_id": "job-9"})])
    cfg = up.UploadPostConfig(api_key="k-1234567890", user="")

    r = up.publish_clip(up.PublishRequest(
        project_id="p1", clip_id="3", platforms=["linkedin"], user="brand", preset="original",
        title="自定义标题", scheduled_date="2026-10-01T09:00:00", timezone="Asia/Shanghai",
    ), config=cfg, session=session)
    form = session.calls[0][2]["data"]
    assert form["user"] == "brand" and form["title"] == "自定义标题"
    assert form["scheduled_date"] == "2026-10-01T09:00:00" and form["timezone"] == "Asia/Shanghai"
    assert r["job_id"] == "job-9" and r["status"] == "scheduled"


def test_publish_clip_without_user_fails_before_export(data_dir, monkeypatch):
    from backend.services import upload_post_publisher as up

    _fake_clip(data_dir)
    called = []
    monkeypatch.setattr("backend.services.publish_export.export_clip", lambda req: called.append(req))
    with pytest.raises(up.UploadPostError, match="profile"):
        up.publish_clip(up.PublishRequest("p1", "2", ["tiktok"]), config=up.UploadPostConfig(api_key="k-1234567890"))
    assert not called


def test_publish_clip_maps_http_errors(data_dir, monkeypatch):
    from backend.services import upload_post_publisher as up

    exported = _fake_clip(data_dir)
    monkeypatch.setattr("backend.services.publish_export.export_clip", lambda req: {"ok": True, "path": str(exported)})
    cfg = up.UploadPostConfig(api_key="bad", user="u")

    session = _Session([_Resp(401, {"success": False, "message": "Invalid or expired token"})])
    with pytest.raises(up.UploadPostError) as exc:
        up.publish_clip(up.PublishRequest("p1", "2", ["tiktok"]), config=cfg, session=session)
    assert exc.value.status_code == 401 and "Invalid or expired token" in str(exc.value)

    session = _Session([_Resp(200, {"success": False, "error": "tiktok_privacy_unavailable"})])
    with pytest.raises(up.UploadPostError, match="tiktok_privacy_unavailable"):
        up.publish_clip(up.PublishRequest("p1", "2", ["tiktok"]), config=cfg, session=session)
    assert up.list_records("p1") == []  # 失败不落记录


# ---------------------------------------------------------------- status / profiles ---
def test_get_status_normalizes_results_and_updates_record(data_dir):
    from backend.services import upload_post_publisher as up

    up._write_record("p1", {"request_id": "req-1", "clip_id": "2", "status": "submitted", "submitted_at": "2026-09-21T00:00:00+00:00"})
    session = _Session([_Resp(200, {
        "request_id": "req-1", "status": "completed", "completed": 3, "total": 3,
        "results": [
            {"platform": "tiktok", "success": True, "url": "https://www.tiktok.com/@a/video/1", "fallback_to_inbox": True},
            {"platform": "youtube", "success": False, "error": "quota"},
            {"platform": "linkedin", "success": True, "skipped": True, "skip_reason": "profile_platform_not_configured"},
        ],
    })])
    st = up.get_status("req-1", config=up.UploadPostConfig(api_key="k-1234567890"), session=session, project_id="p1")
    assert st["final"] is True and st["ok"] is True and st["completed"] == 3
    by = {r["platform"]: r for r in st["results"]}
    assert by["tiktok"]["url"].startswith("https://www.tiktok.com") and by["tiktok"]["fallback_to_inbox"] is True
    assert by["youtube"]["success"] is False and by["youtube"]["error"] == "quota"
    assert by["linkedin"]["skipped"] is True
    assert session.calls[0][2]["params"] == {"request_id": "req-1"}
    assert up.list_records("p1")[0]["status"] == "completed"

    session = _Session([_Resp(404, {"status": "not_found"})])
    st = up.get_status("nope", config=up.UploadPostConfig(api_key="k-1234567890"), session=session)
    assert st["status"] == "not_found" and st["final"] is True and st["ok"] is False


def test_list_profiles_marks_connected_platforms(data_dir):
    from backend.services import upload_post_publisher as up

    session = _Session([_Resp(200, {"success": True, "profiles": [
        {"username": "brand", "social_accounts": {"tiktok": {"display_name": "Brand"}, "youtube": ""}},
        {"username": "empty", "social_accounts": {}},
    ]})])
    profiles = up.list_profiles(up.UploadPostConfig(api_key="k-1234567890"), session=session)
    assert profiles[0]["username"] == "brand" and profiles[0]["connected_platforms"] == ["tiktok"]
    assert profiles[1]["connected_platforms"] == []
    assert session.calls[0][1].endswith("/api/uploadposts/users")


def test_verify_api_key(data_dir):
    from backend.services import upload_post_publisher as up

    session = _Session([_Resp(200, {"success": True, "email": "a@b.c", "plan": "Basic"})])
    assert up.verify_api_key(up.UploadPostConfig(api_key="k-1234567890"), session=session) == {"ok": True, "email": "a@b.c", "plan": "Basic"}
    session = _Session([_Resp(401, None, text="Unauthorized")])
    with pytest.raises(up.UploadPostError, match="401"):
        up.verify_api_key(up.UploadPostConfig(api_key="k-1234567890"), session=session)


# ---------------------------------------------------------------- cli / mcp / api ---
def test_cli_parser_publish():
    from backend.cli import build_parser

    a = build_parser().parse_args(["publish", "pid", "--clip", "2", "--platform", "tiktok", "--platform", "youtube",
                                   "--extra", "privacy_level=SELF_ONLY", "--wait", "--json"])
    assert a.cmd == "publish" and a.clip == ["2"] and a.platform == ["tiktok", "youtube"] and a.wait and a.json
    assert a.extra == ["privacy_level=SELF_ONLY"] and a.preset is None
    a = build_parser().parse_args(["publish", "--list-profiles"])
    assert a.project_id is None and a.list_profiles is True
    a = build_parser().parse_args(["publish", "--status", "req-1"])
    assert a.status == "req-1"


def test_cli_publish_refuses_bulk_without_yes(data_dir, capsys):
    from backend.cli import main
    from backend.core.path_utils import get_project_directory
    from backend.services import upload_post_publisher as up

    up.save_config(api_key="k-1234567890", user="u")
    pdir = get_project_directory("p1")
    (pdir / "metadata").mkdir(parents=True, exist_ok=True)
    (pdir / "metadata" / "clips_metadata.json").write_text(json.dumps([
        {"id": "1", "generated_title": "a", "final_score": 1}, {"id": "2", "generated_title": "b", "final_score": 2}]), encoding="utf-8")
    (pdir / "project.json").write_text("{}", encoding="utf-8")
    rc = main(["publish", "p1", "--platform", "tiktok"])
    assert rc == 2 and "--yes" in capsys.readouterr().err


def test_mcp_registers_publish_tools(data_dir):
    pytest.importorskip("mcp")
    import asyncio

    from backend import mcp_server

    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert {"publish_clip", "get_publish_status", "list_publish_profiles"} <= names
    r = mcp_server.list_publish_profiles()
    assert r["configured"] is False and "hint" in r
    r = mcp_server.publish_clip("p1", "2", ["tiktok"])
    assert r["ok"] is False and "UPLOAD_POST_API_KEY" in r["error"]


def test_api_config_roundtrip_and_publish_validation(data_dir, monkeypatch):
    import asyncio

    from fastapi import HTTPException

    from backend.api.v1 import publish as api
    from backend.services import upload_post_publisher as up

    cfg = asyncio.run(api.get_upload_post_config())
    assert cfg["configured"] is False and "tiktok" in cfg["platforms"]

    monkeypatch.setattr(up, "verify_api_key", lambda config=None, session=None: {"ok": True, "email": "a@b.c", "plan": "Basic"})
    r = asyncio.run(api.put_upload_post_config(api.UploadPostConfigBody(api_key="k-1234567890", user="brand")))
    assert r["configured"] and r["user"] == "brand" and r["account"]["email"] == "a@b.c" and r["api_key_masked"] == "k-12…7890"

    def bad_verify(config=None, session=None):
        raise up.UploadPostError("校验 API Key失败（HTTP 401）: Invalid", 401)
    monkeypatch.setattr(up, "verify_api_key", bad_verify)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.put_upload_post_config(api.UploadPostConfigBody(api_key="wrong")))
    assert exc.value.status_code == 401
    assert up.load_config().api_key == "k-1234567890"  # 坏 key 不覆盖好 key

    _fake_clip(data_dir)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.start_upload_post_publish("p1", "2", api.PublishBody(platforms=["douyin"])))
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.start_upload_post_publish("p1", "404", api.PublishBody(platforms=["tiktok"])))
    assert exc.value.status_code == 404

    started = []
    monkeypatch.setattr(up, "start_publish", lambda req: started.append(req) or {"ok": True, "job_id": "j1", "status": "queued"})
    r = asyncio.run(api.start_upload_post_publish("p1", "2", api.PublishBody(platforms=["TikTok", "youtube"], extra={"privacyStatus": "unlisted"})))
    assert r["job_id"] == "j1" and started[0].platforms == ["tiktok", "youtube"] and started[0].extra == {"privacyStatus": "unlisted"}

    with pytest.raises(HTTPException) as exc:
        asyncio.run(api.get_upload_post_job("missing"))
    assert exc.value.status_code == 404


def test_api_router_is_mounted():
    from backend.api.v1 import api_router

    def walk(router):
        for r in router.routes:
            if getattr(r, "path", None):
                yield r.path
            sub = getattr(r, "router", None) or getattr(r, "original_router", None)
            if sub is not None:
                yield from walk(sub)

    paths = set(walk(api_router))
    assert "/publish/upload-post/config" in paths
    assert "/publish/upload-post/{project_id}/clips/{clip_id}" in paths
    assert "/publish/upload-post/jobs/{job_id}" in paths
