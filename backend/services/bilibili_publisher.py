"""
把成片投稿到 B 站。配置方式和 Upload-Post 一样：密钥只留在本机，发布页直接选。

上传步骤对齐公开的创作中心流程（preupload → upos 分片 → web/add/v3）。
仅自己可见用 is_only_self，定时用 dtime（须晚于现在两小时）。
抖音 / 小红书 / 快手没有这条投稿接口，不在这里假装能发。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "bilibili.json"
REQUIRED_COOKIE_FIELDS = ("SESSDATA", "bili_jct", "DedeUserID")
TITLE_LIMIT = 80
DEFAULT_TID = 21  # 生活
SCHEDULE_LEAD_SEC = 2 * 60 * 60
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class BilibiliError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class BilibiliConfig:
    cookie: str = ""
    nickname: str = ""
    uid: str = ""
    source: str = "none"  # env / file / none

    @property
    def configured(self) -> bool:
        return bool(self.cookie)

    def public(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "source": self.source,
            "nickname": self.nickname,
            "uid": self.uid,
        }


@dataclass
class BilibiliPublishRequest:
    project_id: str
    clip_id: str
    title: str | None = None
    description: str | None = None
    subtitles: bool = True
    title_card: bool = True
    scheduled_date: str | None = None
    timezone: str | None = None
    visibility: str = "private"


def config_path() -> Path:
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / CONFIG_FILENAME


def parse_cookie(raw: str) -> dict[str, str]:
    """从请求头里的 Cookie 串取出投稿必需的三项。不接受换行，避免写进请求头。"""
    text = (raw or "").strip()
    if text.lower().startswith("cookie:"):
        text = text.split(":", 1)[1].strip()
    parsed: dict[str, str] = {}
    for part in text.split(";"):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or any(ch in key or ch in value for ch in "\r\n"):
            raise BilibiliError("Cookie 格式不正确")
        parsed[key] = value
    missing = [name for name in REQUIRED_COOKIE_FIELDS if not parsed.get(name)]
    if missing:
        raise BilibiliError("Cookie 缺少 " + "、".join(missing))
    return parsed


def cookie_header(parsed: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in parsed.items())


def load_config() -> BilibiliConfig:
    """环境变量 BILIBILI_COOKIE 优先于数据目录里的 bilibili.json。"""
    env_cookie = (os.getenv("BILIBILI_COOKIE") or "").strip()
    path = config_path()
    file_cookie, nickname, uid = "", "", ""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                file_cookie = str(data.get("cookie") or "").strip()
                nickname = str(data.get("nickname") or "").strip()
                uid = str(data.get("uid") or "").strip()
        except (OSError, ValueError) as exc:
            logger.warning("读取 %s 失败: %s", path, exc)
    if env_cookie:
        try:
            parsed = parse_cookie(env_cookie)
        except BilibiliError:
            logger.warning("环境变量 BILIBILI_COOKIE 缺少投稿所需字段")
            return BilibiliConfig(source="none")
        return BilibiliConfig(cookie=cookie_header(parsed), nickname=nickname, uid=uid or parsed.get("DedeUserID", ""), source="env")
    if file_cookie:
        return BilibiliConfig(cookie=file_cookie, nickname=nickname, uid=uid, source="file")
    return BilibiliConfig(source="none")


def save_config(cookie: str, nickname: str, uid: str) -> BilibiliConfig:
    """写入 bilibili.json，权限 0600。cookie 必须已经是校验过的请求头串。"""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "cookie": cookie,
        "nickname": nickname,
        "uid": uid,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return load_config()


def clear_config() -> None:
    path = config_path()
    if path.exists():
        path.unlink()


def _headers(cookie: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Cookie": cookie,
        "User-Agent": UA,
        "Referer": "https://member.bilibili.com/",
    }
    if extra:
        headers.update(extra)
    return headers


def _json_body(resp: requests.Response, what: str) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError as exc:
        raise BilibiliError(f"{what}失败（HTTP {resp.status_code}）") from exc
    if not isinstance(data, dict):
        raise BilibiliError(f"{what}失败")
    if resp.status_code >= 400:
        raise BilibiliError(str(data.get("message") or f"{what}失败（HTTP {resp.status_code}）"))
    return data


def verify_cookie(raw: str, session: requests.Session | None = None) -> dict[str, str]:
    """向 B 站 nav 接口确认登录态，返回昵称。不把 cookie 写进日志。"""
    parsed = parse_cookie(raw)
    header = cookie_header(parsed)
    resp = (session or requests.Session()).get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers=_headers(header, {"Referer": "https://www.bilibili.com/"}),
        timeout=15,
    )
    data = _json_body(resp, "校验 Cookie")
    info = data.get("data") if isinstance(data.get("data"), dict) else {}
    if data.get("code") != 0 or not info.get("isLogin"):
        raise BilibiliError("Cookie 无效或已过期", 401)
    nickname = str(info.get("uname") or "").strip() or "B站"
    uid = str(info.get("mid") or parsed["DedeUserID"])
    return {"cookie": header, "nickname": nickname, "uid": uid}


def schedule_unix(scheduled_date: str | None, timezone_name: str | None, now: float | None = None) -> int | None:
    """本地时间转 Unix 秒。B 站定时发布要晚于现在两小时。"""
    if not scheduled_date:
        return None
    text = scheduled_date.strip()
    if len(text) == 16:
        text += ":00"
    try:
        when = datetime.fromisoformat(text)
    except ValueError as exc:
        raise BilibiliError("选择发出的时间") from exc
    if when.tzinfo is None:
        try:
            zone = ZoneInfo(timezone_name or "UTC")
        except Exception as exc:
            raise BilibiliError(f"不认识的时区: {timezone_name or ''}") from exc
        when = when.replace(tzinfo=zone)
    stamp = int(when.timestamp())
    current = time.time() if now is None else now
    if stamp < current + SCHEDULE_LEAD_SEC:
        raise BilibiliError("B 站定时要晚于现在两小时。")
    return stamp


def build_submit(
    *,
    title: str,
    description: str,
    private: bool,
    dtime: int | None,
    csrf: str,
    filename: str,
    cid: int,
    tid: int = DEFAULT_TID,
    cover: str = "",
) -> dict[str, Any]:
    text = title.strip()[:TITLE_LIMIT].rstrip() or "切片"
    cover_url = (cover or "").strip()
    body: dict[str, Any] = {
        "copyright": 1,
        "videos": [{"filename": filename, "title": text, "desc": "", "cid": cid}],
        "cover": cover_url,
        "cover43": cover_url,
        "title": text,
        "tid": tid,
        "tag": "日常",
        "desc_format_id": 9999,
        "desc": (description or "")[:2000],
        "recreate": -1,
        "dynamic": "",
        "interactive": 0,
        "act_reserve_create": 0,
        "no_disturbance": 0,
        "no_reprint": 1,
        "subtitle": {"open": 0, "lan": ""},
        "dolby": 0,
        "lossless_music": 0,
        "up_selection_reply": False,
        "up_close_reply": False,
        "up_close_danmu": False,
        "web_os": 3,
        "csrf": csrf,
    }
    if private:
        body["is_only_self"] = 1
    if dtime:
        body["dtime"] = dtime
    return body


def extract_cover_jpeg(video_path: Path, at_sec: float = 0.5) -> bytes:
    """从成片截一帧 JPEG。投稿要用这张图上传封面，空封面在创作中心会被拦。"""
    from backend.services.cover import extract_frame_jpeg

    try:
        return extract_frame_jpeg(Path(video_path), at_sec=at_sec)
    except Exception as exc:  # noqa: BLE001
        raise BilibiliError(str(exc) or "从成片截封面失败") from exc


def upload_cover(
    cookie: str,
    jpeg: bytes,
    *,
    session: requests.Session | None = None,
) -> str:
    """POST /x/vu/web/cover/up，返回封面 URL。"""
    if not jpeg:
        raise BilibiliError("封面是空的")
    parsed = parse_cookie(cookie)
    header = cookie_header(parsed)
    import base64
    data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    resp = (session or requests.Session()).post(
        "https://member.bilibili.com/x/vu/web/cover/up",
        headers=_headers(header, {"Content-Type": "application/x-www-form-urlencoded"}),
        params={"ts": int(time.time() * 1000)},
        data={"csrf": parsed["bili_jct"], "cover": data_uri},
        timeout=60,
    )
    result = _json_body(resp, "上传封面")
    if result.get("code") != 0:
        raise BilibiliError(str(result.get("message") or "上传封面失败"))
    info = result.get("data") if isinstance(result.get("data"), dict) else {}
    url = str(info.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise BilibiliError("上传封面没有返回地址")
    return url


def _upload_url(preupload: dict[str, Any]) -> str:
    endpoint = str(preupload.get("endpoint") or "")
    if endpoint.startswith("//"):
        endpoint = "https:" + endpoint
    endpoint = endpoint.rstrip("/")
    upos = str(preupload.get("upos_uri") or "").removeprefix("upos://").lstrip("/")
    if not endpoint or not upos:
        raise BilibiliError("预上传没有返回上传地址")
    return f"{endpoint}/{upos}"


def upload_video(
    cookie: str,
    video_path: Path,
    *,
    title: str,
    description: str,
    private: bool,
    dtime: int | None,
    session: requests.Session | None = None,
    cover_jpeg: bytes | None = None,
    project_id: str | None = None,
    clip_id: str | None = None,
) -> dict[str, Any]:
    """把一个 mp4 投稿到 B 站，返回 bvid / aid。

    封面：优先调用方传入的设计封面 / 已落盘封面；没有就成片截帧。
    封面任一环节失败都不挡投稿。
    """
    parsed = parse_cookie(cookie)
    header = cookie_header(parsed)
    path = Path(video_path)
    size = path.stat().st_size
    if size <= 0:
        raise BilibiliError("成片是空的")
    http = session or requests.Session()
    pre = http.get(
        "https://member.bilibili.com/preupload",
        headers=_headers(header),
        params={
            "name": path.name,
            "size": size,
            "r": "upos",
            "profile": "ugcfx/bup",
            "ssl": 0,
            "version": "2.14.0",
            "build": "2140000",
            "upcdn": "bda2",
            "probe_version": "20221109",
        },
        timeout=30,
    )
    preupload = _json_body(pre, "预上传")
    if preupload.get("OK") != 1:
        raise BilibiliError(str(preupload.get("message") or "预上传失败"))
    url = _upload_url(preupload)
    auth = str(preupload.get("auth") or "")
    if not auth:
        raise BilibiliError("预上传没有返回凭证")
    chunk_size = int(preupload.get("chunk_size") or 10485760)
    biz_id = int(preupload["biz_id"])
    init = http.post(
        url,
        headers=_headers(header, {"X-Upos-Auth": auth}),
        params={
            "uploads": "",
            "output": "json",
            "profile": "ugcfx/bup",
            "filesize": size,
            "partsize": chunk_size,
            "biz_id": biz_id,
        },
        timeout=30,
    )
    started = _json_body(init, "开始上传")
    if started.get("OK") != 1 or not started.get("upload_id"):
        raise BilibiliError(str(started.get("message") or "开始上传失败"))
    upload_id = started["upload_id"]
    chunks = max(1, (size + chunk_size - 1) // chunk_size)
    with path.open("rb") as handle:
        for index in range(chunks):
            blob = handle.read(chunk_size)
            offset = index * chunk_size
            put = http.put(
                url,
                headers={"X-Upos-Auth": auth},
                params={
                    "partNumber": index + 1,
                    "uploadId": upload_id,
                    "chunk": index,
                    "chunks": chunks,
                    "size": len(blob),
                    "start": offset,
                    "end": offset + len(blob),
                    "total": size,
                },
                data=blob,
                timeout=120,
            )
            text = (put.text or "").strip()
            if put.status_code >= 400 or (text and text != "MULTIPART_PUT_SUCCESS"):
                raise BilibiliError(f"分片上传失败: {text or put.status_code}")
    merged = http.post(
        url,
        headers=_headers(header, {"X-Upos-Auth": auth, "Content-Type": "application/json"}),
        params={
            "output": "json",
            "name": path.name,
            "profile": "ugcfx/bup",
            "uploadId": upload_id,
            "biz_id": biz_id,
        },
        json={"parts": [{"partNumber": i, "eTag": "etag"} for i in range(1, chunks + 1)]},
        timeout=60,
    )
    done = _json_body(merged, "合并分片")
    if done.get("OK") != 1:
        raise BilibiliError(str(done.get("message") or "合并分片失败"))
    key = str(done.get("key") or preupload.get("upos_uri") or "")
    filename = os.path.splitext(key.removeprefix("upos://").lstrip("/"))[0]
    if not filename:
        raise BilibiliError("合并分片没有返回文件名")
    cover_url = ""
    try:
        jpeg = cover_jpeg
        if not jpeg and project_id and clip_id:
            from backend.services.cover import ensure_publish_cover_jpeg
            jpeg = ensure_publish_cover_jpeg(project_id, clip_id, platform="bilibili", video_path=path)
        if not jpeg:
            jpeg = extract_cover_jpeg(path)
        cover_url = upload_cover(cookie, jpeg, session=http)
    except BilibiliError as exc:
        # 封面失败不挡投稿：创作中心多数账号仍接受空封面，由平台自动截帧。
        logger.warning("B 站封面未上传，继续投稿: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("B 站封面未上传，继续投稿: %s", exc)
    body = build_submit(
        title=title,
        description=description,
        private=private,
        dtime=dtime,
        csrf=parsed["bili_jct"],
        filename=filename,
        cid=biz_id,
        cover=cover_url,
    )
    submitted = http.post(
        "https://member.bilibili.com/x/vu/web/add/v3",
        headers=_headers(header, {"Content-Type": "application/json"}),
        params={"csrf": parsed["bili_jct"], "ts": int(time.time() * 1000)},
        json=body,
        timeout=60,
    )
    result = _json_body(submitted, "投稿")
    if result.get("code") != 0:
        raise BilibiliError(str(result.get("message") or "投稿失败"))
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    bvid = str(data.get("bvid") or "")
    aid = data.get("aid")
    if not bvid:
        raise BilibiliError("投稿没有返回 BV 号")
    return {"bvid": bvid, "aid": aid, "url": f"https://www.bilibili.com/video/{bvid}"}


def _write_record(project_id: str, record: dict[str, Any]) -> None:
    from backend.services.upload_post_publisher import records_dir
    path = records_dir(project_id) / f"{record['request_id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def publish_clip(req: BilibiliPublishRequest, session: requests.Session | None = None) -> dict[str, Any]:
    """渲成 B 站横屏成片（命中缓存则不重渲）再投稿。"""
    from backend.services.publish_export import ExportRequest, export_clip, load_clip_meta

    cfg = load_config()
    if not cfg.configured:
        raise BilibiliError("还没有配置 B 站账号")
    clip = load_clip_meta(req.project_id, req.clip_id)
    title = (req.title or clip.get("generated_title") or clip.get("title") or clip.get("outline") or f"切片 {req.clip_id}").strip()
    if not title:
        title = f"切片 {req.clip_id}"
    dtime = schedule_unix(req.scheduled_date, req.timezone)
    export = export_clip(ExportRequest(
        project_id=req.project_id,
        clip_id=req.clip_id,
        preset="bilibili",
        subtitles=req.subtitles,
        title_card=req.title_card,
    ))
    video_path = Path(export["path"])
    uploaded = upload_video(
        cfg.cookie,
        video_path,
        title=title,
        description=req.description or "",
        private=req.visibility != "public",
        dtime=dtime,
        session=session,
        project_id=req.project_id,
        clip_id=req.clip_id,
    )
    request_id = str(uuid.uuid4())
    record = {
        "request_id": request_id,
        "provider": "bilibili",
        "job_id": str(uploaded.get("aid") or ""),
        "project_id": req.project_id,
        "clip_id": req.clip_id,
        "platforms": ["bilibili"],
        "title": title[:TITLE_LIMIT],
        "preset": export.get("preset", "bilibili"),
        "path": str(video_path),
        **({"studio_job_id": clip["studio_job_id"], "revision": clip["revision"]} if clip.get("source_type") == "studio" else {}),
        "scheduled_date": req.scheduled_date,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "scheduled" if dtime else "completed",
        "bvid": uploaded["bvid"],
        "aid": uploaded.get("aid"),
        "url": uploaded["url"],
    }
    _write_record(req.project_id, record)
    return record


def cancel_record(project_id: str, request_id: str, session: requests.Session | None = None) -> dict[str, Any]:
    """取消还没到点的 B 站定时稿。已经公开的不从这里删。"""
    from backend.services.upload_post_publisher import records_dir

    path = records_dir(project_id) / f"{request_id}.json"
    if not path.exists():
        raise BilibiliError("没有这条发布记录", 404)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BilibiliError(f"读不到这条发布记录: {exc}") from exc
    if not isinstance(record, dict) or record.get("provider") != "bilibili":
        raise BilibiliError("没有这条发布记录", 404)
    if record.get("status") != "scheduled":
        raise BilibiliError("只有还没发出的排期可以取消")
    aid = str(record.get("aid") or record.get("job_id") or "").strip()
    if not aid:
        raise BilibiliError("这条排期没有远端编号，不能取消")
    cfg = load_config()
    if not cfg.configured:
        raise BilibiliError("还没有配置 B 站账号")
    parsed = parse_cookie(cfg.cookie)
    resp = (session or requests.Session()).post(
        "https://member.bilibili.com/x/web/archive/delete",
        headers=_headers(cookie_header(parsed)),
        data={"aid": aid, "csrf": parsed["bili_jct"]},
        timeout=30,
    )
    data = _json_body(resp, "取消排期")
    if data.get("code") not in (0, None):
        raise BilibiliError(str(data.get("message") or "取消失败"))
    record["status"] = "cancelled"
    record["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "request_id": request_id, "status": "cancelled"}


def _jobs_dir() -> Path:
    from backend.core.path_utils import get_data_directory
    directory = get_data_directory() / "bilibili_jobs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _remember_job(job: dict[str, Any]) -> None:
    stored = dict(job)
    with _jobs_lock:
        _jobs[stored["job_id"]] = stored
        path = _jobs_dir() / f"{stored['job_id']}.json"
        path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")


def _read_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        cached = _jobs.get(job_id)
        if cached is not None:
            return dict(cached)
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def start_publish(req: BilibiliPublishRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    _remember_job({
        "job_id": job_id, "status": "queued", "project_id": req.project_id, "clip_id": req.clip_id,
        "provider": "bilibili",
    })
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True, name=f"bilibili-{job_id[:8]}").start()
    return {"ok": True, "job_id": job_id, "status": "queued"}


def _run_job(job_id: str, req: BilibiliPublishRequest) -> None:
    job = _read_job(job_id) or {"job_id": job_id, "project_id": req.project_id, "clip_id": req.clip_id}
    job.update(status="running", stage="export")
    _remember_job(job)
    try:
        record = publish_clip(req)
        status = record["status"]
        job.update(
            status=status,
            stage="submitted",
            request_id=record["request_id"],
            results=[{
                "platform": "bilibili",
                "success": True,
                "url": record.get("url"),
                "message": record.get("bvid"),
            }],
        )
    except Exception as exc:
        logger.exception("B 站投稿失败")
        job.update(status="failed", error=str(exc)[:500])
    _remember_job(job)


def get_publish_job(job_id: str) -> dict[str, Any] | None:
    job = _read_job(job_id)
    if not job or job.get("provider") != "bilibili":
        return None
    with _jobs_lock:
        alive = job_id in _jobs
    if not alive and job.get("status") in {"queued", "running"}:
        job["status"] = "failed"
        job["error"] = "发布进程已中断，请再发一次。"
        _remember_job(job)
    return job
