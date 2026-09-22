"""B 站投稿：Cookie 只留本机、投稿体、分片顺序、定时两小时、取消排期。不连真站、不跑 ffmpeg。"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

COOKIE = "SESSDATA=sess; bili_jct=jct; DedeUserID=42"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(d))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(d))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{d / 'test.db'}")
    monkeypatch.delenv("BILIBILI_COOKIE", raising=False)
    d.mkdir()
    return d


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text or payload is None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _take(self, method, url, kw):
        snap = {k: v for k, v in kw.items() if k != "data" or not isinstance(v, (bytes, bytearray))}
        if isinstance(kw.get("data"), (bytes, bytearray)):
            snap["data_len"] = len(kw["data"])
        self.calls.append((method, url, snap))
        return self.responses.pop(0) if self.responses else _Resp(200, {})

    def get(self, url, **kw):
        return self._take("GET", url, kw)

    def post(self, url, **kw):
        return self._take("POST", url, kw)

    def put(self, url, **kw):
        return self._take("PUT", url, kw)


def test_cookie_requires_the_three_fields():
    from backend.services.bilibili_publisher import BilibiliError, parse_cookie

    parsed = parse_cookie("Cookie: SESSDATA=a; bili_jct=b; DedeUserID=9; extra=1")
    assert parsed["SESSDATA"] == "a" and parsed["bili_jct"] == "b"
    with pytest.raises(BilibiliError, match="SESSDATA"):
        parse_cookie("bili_jct=b; DedeUserID=9")
    with pytest.raises(BilibiliError, match="格式"):
        parse_cookie("SESSDATA=a\nb; bili_jct=b; DedeUserID=9")


def test_config_file_is_private_and_hides_the_cookie(data_dir, monkeypatch):
    from backend.services import bilibili_publisher as bili

    assert bili.load_config().configured is False
    saved = bili.save_config(COOKIE, "测试UP", "42")
    assert saved.configured and saved.nickname == "测试UP" and saved.source == "file"
    assert "SESSDATA" not in json.dumps(saved.public())
    mode = os.stat(bili.config_path()).st_mode & 0o777
    assert mode == 0o600
    monkeypatch.setenv("BILIBILI_COOKIE", "SESSDATA=env; bili_jct=envj; DedeUserID=7")
    env = bili.load_config()
    assert env.source == "env" and env.uid == "42"
    bili.clear_config()
    assert bili.load_config().source == "env"


def test_submit_body_is_private_by_default_and_truncates_title():
    from backend.services.bilibili_publisher import TITLE_LIMIT, build_submit, schedule_unix

    body = build_submit(
        title="标" * 90,
        description="说明",
        private=True,
        dtime=None,
        csrf="jct",
        filename="n2407",
        cid=11,
    )
    assert len(body["title"]) == TITLE_LIMIT
    assert body["is_only_self"] == 1
    assert body["videos"][0]["cid"] == 11
    assert body["tid"] == 21
    assert "dtime" not in body
    public = build_submit(title="公开", description="", private=False, dtime=1_900_000_000, csrf="jct", filename="f", cid=1)
    assert "is_only_self" not in public and public["dtime"] == 1_900_000_000
    from datetime import datetime, timezone
    target = datetime(2026, 9, 22, 6, 0, tzinfo=timezone.utc)
    with pytest.raises(Exception, match="两小时"):
        schedule_unix("2026-09-22T06:00:00", "UTC", now=target.timestamp() - 60)
    assert schedule_unix("2026-09-22T06:00:00", "UTC", now=target.timestamp() - 3 * 3600) == int(target.timestamp())


def test_upload_walks_preupload_chunks_and_submit(data_dir, tmp_path):
    from backend.services.bilibili_publisher import upload_video

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x" * 8)
    session = _Session([
        _Resp(200, {"OK": 1, "auth": "ak", "biz_id": 99, "chunk_size": 8, "endpoint": "//up.example", "upos_uri": "upos://ugc/abc.mp4"}),
        _Resp(200, {"OK": 1, "upload_id": "up-1"}),
        _Resp(200, None, text="MULTIPART_PUT_SUCCESS"),
        _Resp(200, {"OK": 1, "key": "/abc.mp4"}),
        _Resp(200, {"code": 0, "data": {"bvid": "BV1test", "aid": 555}}),
    ])
    uploaded = upload_video(COOKIE, video, title="把一句讲透", description="说明", private=True, dtime=None, session=session)
    assert uploaded["bvid"] == "BV1test" and uploaded["aid"] == 555
    methods = [call[0] for call in session.calls]
    assert methods == ["GET", "POST", "PUT", "POST", "POST"]
    submit = session.calls[-1][2]["json"]
    assert submit["is_only_self"] == 1
    assert submit["videos"][0]["filename"] == "abc"
    assert submit["csrf"] == "jct"
    assert "SESSDATA" not in json.dumps({k: v for k, v in session.calls[-1][2].items() if k != "headers"})


def test_publish_records_a_completed_bilibili_post(data_dir, monkeypatch, tmp_path):
    from backend.services import bilibili_publisher as bili

    bili.save_config(COOKIE, "测试UP", "42")
    video = tmp_path / "out.mp4"
    video.write_bytes(b"mp4")

    def fake_export(req):
        assert req.preset == "bilibili"
        return {"path": str(video), "warnings": []}

    monkeypatch.setattr("backend.services.publish_export.export_clip", fake_export)
    monkeypatch.setattr("backend.services.publish_export.load_clip_meta", lambda _p, _c: {"generated_title": "把一句讲透"})
    session = _Session([
        _Resp(200, {"OK": 1, "auth": "ak", "biz_id": 3, "chunk_size": 10485760, "endpoint": "https://up.example", "upos_uri": "upos://ugc/file.mp4"}),
        _Resp(200, {"OK": 1, "upload_id": "up-2"}),
        _Resp(200, None, text=""),
        _Resp(200, {"OK": 1, "key": "/file.mp4"}),
        _Resp(200, {"code": 0, "data": {"bvid": "BV1ok", "aid": 9}}),
    ])
    record = bili.publish_clip(bili.BilibiliPublishRequest(project_id="p1", clip_id="2", visibility="private"), session=session)
    assert record["provider"] == "bilibili"
    assert record["status"] == "completed"
    assert record["platforms"] == ["bilibili"]
    stored = json.loads((data_dir / "projects" / "p1" / "output" / "publish" / f"{record['request_id']}.json").read_text())
    assert stored["url"].endswith("BV1ok")
    assert "cookie" not in stored


def test_cancel_scheduled_deletes_the_manuscript(data_dir):
    from backend.services import bilibili_publisher as bili
    from backend.services.upload_post_publisher import cancel_record, records_dir

    bili.save_config(COOKIE, "测试UP", "42")
    path = records_dir("p1") / "req-1.json"
    path.write_text(json.dumps({
        "request_id": "req-1", "provider": "bilibili", "job_id": "9", "aid": 9,
        "status": "scheduled", "platforms": ["bilibili"],
    }), encoding="utf-8")
    session = _Session([_Resp(200, {"code": 0})])
    result = cancel_record("p1", "req-1", session=session)
    assert result["status"] == "cancelled"
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1].endswith("/x/web/archive/delete")
    assert session.calls[0][2]["data"]["aid"] == "9"
    assert json.loads(path.read_text())["status"] == "cancelled"


def test_api_saves_only_a_verified_cookie(data_dir, monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from backend.api.v1 import publish as api

    def fake_verify(cookie, session=None):
        assert "SESSDATA" in cookie
        return {"cookie": COOKIE, "nickname": "测试UP", "uid": "42"}

    monkeypatch.setattr(api.bili, "verify_cookie", fake_verify)
    saved = asyncio.run(api.put_bilibili_config(api.BilibiliConfigBody(cookie=COOKIE)))
    assert saved["nickname"] == "测试UP" and "SESSDATA" not in json.dumps(saved)
    view = asyncio.run(api.get_bilibili_config())
    assert view["configured"] is True and view["uid"] == "42"
