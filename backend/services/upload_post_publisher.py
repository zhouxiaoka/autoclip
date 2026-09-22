"""
把本机渲好的成片交给 Upload-Post，发到 TikTok / Instagram / YouTube 等。

这条客户端是按 2026-09 的公开文档重写的，不沿用外部 PR 里的解析细节：
https://docs.upload-post.com/api/upload-video
https://docs.upload-post.com/api/upload-status
https://docs.upload-post.com/api/user-profiles

线上核对（无效 key）：下面四个地址都返回 HTTP 401、正文 {"success": false, "message": "Invalid API key"}，
鉴权头是 `Authorization: Apikey <key>`。

    POST https://api.upload-post.com/api/upload
    GET  https://api.upload-post.com/api/uploadposts/me
    GET  https://api.upload-post.com/api/uploadposts/users
    GET  https://api.upload-post.com/api/uploadposts/status

视频处理仍在本地。只有成片 mp4 会上传。B 站投稿不经过这里。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.upload-post.com"
CONFIG_FILENAME = "upload_post.json"
YOUTUBE_TITLE_LIMIT = 100

# OpenAPI VideoPlatformEnum（docs.upload-post.com/openapi.json）。
# reddit 在枚举里，但上传页写明 platform[]=reddit 固定 503 reddit_unavailable，不放进可选列表。
# 上传页示例仍写 twitter / mastodon / wordpress；模式里 X 的值是 x，后两个不在视频枚举中，不发送。
PLATFORMS: list[str] = [
    "tiktok", "instagram", "youtube", "facebook", "linkedin", "x", "threads",
    "pinterest", "bluesky", "discord", "telegram", "google_business",
]
VERTICAL_PLATFORMS = {"tiktok", "instagram", "youtube", "facebook", "threads", "pinterest"}
_RESERVED_FORM_FIELDS = {"user", "platform[]", "platform", "video", "async_upload", "request_id", "external_id"}
FINAL_STATUSES = {"completed", "failed", "not_found"}
_ACCOUNT_NAME_FIELDS = ("display_name", "username", "handle")


class UploadPostError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass
class UploadPostConfig:
    api_key: str = ""
    user: str = ""
    base_url: str = DEFAULT_API_BASE
    source: str = "none"  # env / file / none / cli

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def masked_key(self) -> str:
        return mask_key(self.api_key)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}…{key[-4:]}"


def config_path() -> Path:
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / CONFIG_FILENAME


def load_config() -> UploadPostConfig:
    """环境变量优先于数据目录里的 upload_post.json。user 也是环境变量优先。"""
    base_url = (os.getenv("UPLOAD_POST_API_BASE") or DEFAULT_API_BASE).rstrip("/")
    env_key = (os.getenv("UPLOAD_POST_API_KEY") or "").strip()
    env_user = (os.getenv("UPLOAD_POST_USER") or "").strip()
    file_key, file_user = "", ""
    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            file_key = str(data.get("api_key") or "").strip()
            file_user = str(data.get("user") or "").strip()
            if data.get("base_url") and not os.getenv("UPLOAD_POST_API_BASE"):
                base_url = str(data["base_url"]).rstrip("/")
        except (OSError, ValueError) as e:
            logger.warning("读取 %s 失败: %s", path, e)

    user = env_user or file_user
    if env_key:
        return UploadPostConfig(api_key=env_key, user=user, base_url=base_url, source="env")
    if file_key:
        return UploadPostConfig(api_key=file_key, user=user, base_url=base_url, source="file")
    return UploadPostConfig(user=user, base_url=base_url, source="none")


def save_config(api_key: str | None = None, user: str | None = None) -> UploadPostConfig:
    """写入 upload_post.json。传 None 的字段保留原值。权限 0600。"""
    path = config_path()
    current: dict[str, Any] = {}
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            current = {}
    if api_key is not None:
        current["api_key"] = api_key.strip()
    if user is not None:
        current["user"] = user.strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return load_config()


def clear_config() -> None:
    path = config_path()
    if path.exists():
        path.unlink()


def _headers(config: UploadPostConfig) -> dict[str, str]:
    version = os.getenv("AUTOCLIP_APP_VERSION", "dev")
    return {
        "Authorization": f"Apikey {config.api_key}",
        "User-Agent": f"autoclip/{version} (+https://github.com/zhouxiaoka/autoclip)",
    }


def _require(config: UploadPostConfig | None) -> UploadPostConfig:
    cfg = config or load_config()
    if not cfg.configured:
        raise UploadPostError(
            "没有配置 Upload-Post API Key：设置环境变量 UPLOAD_POST_API_KEY，"
            "或 `autoclip publish --api-key <key> --user <profile> --save`。"
            "Key 在 https://app.upload-post.com/api-keys 生成。"
        )
    return cfg


def _payload_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    msg = payload.get("message") or payload.get("error") or payload.get("detail")
    if isinstance(msg, dict):
        msg = msg.get("message") or json.dumps(msg, ensure_ascii=False)
    return str(msg) if msg else None


def _raise_for_response(resp: requests.Response, what: str) -> dict[str, Any]:
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": (resp.text or "")[:500]}
    if resp.status_code >= 400:
        msg = _payload_message(payload)
        if resp.status_code == 401:
            msg = msg or "API Key 无效或已过期"
        raise UploadPostError(f"{what}失败（HTTP {resp.status_code}）: {msg or payload}", resp.status_code, payload)
    if isinstance(payload, dict) and payload.get("success") is False:
        raise UploadPostError(
            f"{what}失败: {_payload_message(payload) or payload}",
            resp.status_code,
            payload,
        )
    return payload if isinstance(payload, dict) else {"data": payload}


def verify_api_key(config: UploadPostConfig | None = None, session: requests.Session | None = None) -> dict[str, Any]:
    """GET /api/uploadposts/me。无效 key 时线上返回 401 和 message=Invalid API key。"""
    cfg = _require(config)
    resp = (session or requests.Session()).get(
        f"{cfg.base_url}/api/uploadposts/me", headers=_headers(cfg), timeout=30,
    )
    data = _raise_for_response(resp, "校验 API Key")
    return {"ok": True, "email": data.get("email"), "plan": data.get("plan")}


def split_social_accounts(accounts: Any) -> tuple[list[str], list[str]]:
    """已连接的平台，和令牌过期、必须重连的平台。

    文档：social_accounts 的值是带 display_name / username / handle 的对象才算连上；
    空字符串、null、空对象只是占位。reauth_required=true 时发不出去。
    """
    connected: list[str] = []
    reconnect: list[str] = []
    if not isinstance(accounts, dict):
        return connected, reconnect
    for platform, info in accounts.items():
        if not isinstance(info, dict):
            continue
        named = any(isinstance(info.get(key), str) and str(info.get(key)).strip() for key in _ACCOUNT_NAME_FIELDS)
        if not named:
            continue
        if info.get("reauth_required") is True:
            reconnect.append(str(platform))
        else:
            connected.append(str(platform))
    return sorted(connected), sorted(reconnect)


def list_profiles(config: UploadPostConfig | None = None, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """GET /api/uploadposts/users。"""
    cfg = _require(config)
    resp = (session or requests.Session()).get(
        f"{cfg.base_url}/api/uploadposts/users", headers=_headers(cfg), timeout=30,
    )
    data = _raise_for_response(resp, "读取 profile 列表")
    out: list[dict[str, Any]] = []
    for profile in data.get("profiles") or []:
        if not isinstance(profile, dict):
            continue
        connected, reconnect = split_social_accounts(profile.get("social_accounts"))
        out.append({
            "username": profile.get("username"),
            "connected_platforms": connected,
            "reconnect_platforms": reconnect,
            "created_at": profile.get("created_at"),
        })
    return out


@dataclass
class PublishRequest:
    project_id: str
    clip_id: str
    platforms: Sequence[str]
    user: str | None = None
    preset: str | None = None
    title: str | None = None
    description: str | None = None
    subtitles: bool = True
    title_card: bool = True
    scheduled_date: str | None = None
    timezone: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def normalize_platforms(platforms: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for raw in platforms:
        for part in str(raw).replace(";", ",").split(","):
            name = part.strip().lower()
            if not name:
                continue
            if name == "twitter":
                name = "x"
            if name == "reddit":
                raise ValueError("Reddit 目前不能发视频：Upload-Post 会返回 reddit_unavailable")
            if name not in PLATFORMS:
                raise ValueError(f"不支持的平台: {name}（可选 {', '.join(PLATFORMS)}）")
            if name not in seen:
                seen.append(name)
    if not seen:
        raise ValueError("至少要指定一个平台")
    return seen


def pick_preset(platforms: Sequence[str]) -> str:
    """没指定预设时：有竖屏平台就用 9:16 的 shorts（最长约 60 秒），否则原画。"""
    return "shorts" if any(p in VERTICAL_PLATFORMS for p in platforms) else "original"


def records_dir(project_id: str) -> Path:
    from backend.core.path_utils import get_project_directory
    directory = get_project_directory(project_id) / "output" / "publish"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_record(project_id: str, record: dict[str, Any]) -> Path:
    path = records_dir(project_id) / f"{record['request_id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cancel_scheduled(job_id: str, config: UploadPostConfig | None = None,
                     session: requests.Session | None = None) -> dict[str, Any]:
    """DELETE /api/uploadposts/schedule/{job_id}。只取消还没发出去的排期。"""
    cfg = _require(config)
    resp = (session or requests.Session()).delete(
        f"{cfg.base_url}/api/uploadposts/schedule/{job_id}",
        headers=_headers(cfg),
        timeout=30,
    )
    _raise_for_response(resp, "取消排期")
    return {"ok": True, "job_id": job_id}


def cancel_record(project_id: str, request_id: str, config: UploadPostConfig | None = None,
                  session: requests.Session | None = None) -> dict[str, Any]:
    path = records_dir(project_id) / f"{request_id}.json"
    if not path.exists():
        raise UploadPostError("没有这条发布记录", 404)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise UploadPostError(f"读不到这条发布记录: {e}") from e
    if not isinstance(record, dict):
        raise UploadPostError("发布记录损坏了")
    if record.get("provider") == "bilibili":
        from backend.services.bilibili_publisher import cancel_record as cancel_bilibili
        return cancel_bilibili(project_id, request_id, session=session)
    if record.get("status") != "scheduled":
        raise UploadPostError("只有还没发出的排期可以取消")
    job_id = str(record.get("job_id") or "").strip()
    if not job_id:
        raise UploadPostError("这条排期没有远端编号，不能取消")
    cancel_scheduled(job_id, config=config, session=session)
    record["status"] = "cancelled"
    record["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "request_id": request_id, "status": "cancelled"}


def list_records(project_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in records_dir(project_id).glob("*.json"):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    out.sort(key=lambda record: record.get("submitted_at") or "", reverse=True)
    return out


def _form_value(value: Any) -> Any:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return value


def build_form(req: PublishRequest, platforms: list[str], user: str, title: str, request_id: str) -> dict[str, Any]:
    """multipart 字段（不含视频文件）。platform[] 用 list，requests 会编成重复字段。"""
    form: dict[str, Any] = {
        "user": user,
        "platform[]": list(platforms),
        "title": title,
        "async_upload": "true",
        "request_id": request_id,
        "external_id": f"autoclip:{req.project_id}:{req.clip_id}"[:255],
    }
    if req.description:
        form["description"] = req.description
    if req.scheduled_date:
        form["scheduled_date"] = req.scheduled_date
        if req.timezone:
            form["timezone"] = req.timezone
    # YouTube 标题上限 100。超长时只缩短 youtube_title，其它平台仍用完整标题。
    if "youtube" in platforms and len(title) > YOUTUBE_TITLE_LIMIT and "youtube_title" not in (req.extra or {}):
        form["youtube_title"] = title[:YOUTUBE_TITLE_LIMIT].rstrip()
    for key, value in (req.extra or {}).items():
        if key in _RESERVED_FORM_FIELDS or value is None or key in form:
            continue
        form[key] = _form_value(value)
    return form


def publish_clip(req: PublishRequest, config: UploadPostConfig | None = None,
                 session: requests.Session | None = None) -> dict[str, Any]:
    """导出成片（命中缓存则不重渲）→ POST /api/upload（async_upload=true）→ 返回 request_id。"""
    from backend.services.publish_export import ExportRequest, export_clip, load_clip_meta

    cfg = _require(config)
    platforms = normalize_platforms(req.platforms)
    user = (req.user or cfg.user or "").strip()
    if not user:
        raise UploadPostError(
            "没有指定 Upload-Post profile：传 user=…，或设置 UPLOAD_POST_USER / `autoclip publish --user <profile> --save`。"
            "profile 在 https://app.upload-post.com/manage-users 创建并连接社交账号。"
        )
    preset = req.preset or pick_preset(platforms)
    clip = load_clip_meta(req.project_id, req.clip_id)
    title = (req.title or clip.get("generated_title") or clip.get("title") or clip.get("outline") or f"切片 {req.clip_id}").strip()
    if not title:
        title = f"切片 {req.clip_id}"

    export = export_clip(ExportRequest(
        project_id=req.project_id, clip_id=req.clip_id, preset=preset,
        subtitles=req.subtitles, title_card=req.title_card,
    ))
    video_path = Path(export["path"])
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise UploadPostError(f"成片不存在或为空: {video_path}")

    request_id = str(uuid.uuid4())
    form = build_form(req, platforms, user, title, request_id)
    headers = _headers(cfg)
    headers["Idempotency-Key"] = request_id

    logger.info("Upload-Post 提交: clip=%s platforms=%s user=%s preset=%s file=%s",
                req.clip_id, platforms, user, preset, video_path.name)
    with video_path.open("rb") as handle:
        resp = (session or requests.Session()).post(
            f"{cfg.base_url}/api/upload",
            headers=headers,
            data=form,
            files={"video": (video_path.name, handle, "video/mp4")},
            timeout=(30, 900),
        )
    data = _raise_for_response(resp, "提交发布")
    record = {
        "request_id": data.get("request_id") or request_id,
        "job_id": data.get("job_id"),
        "project_id": req.project_id,
        "clip_id": req.clip_id,
        "platforms": platforms,
        "user": user,
        "title": title,
        "preset": preset,
        "path": str(video_path),
        "scheduled_date": req.scheduled_date,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "http_status": resp.status_code,
        "status": "scheduled" if req.scheduled_date else "submitted",
        "response": data,
    }
    _write_record(req.project_id, record)
    return {
        "ok": True,
        "request_id": record["request_id"],
        "job_id": record["job_id"],
        "project_id": req.project_id,
        "clip_id": req.clip_id,
        "platforms": platforms,
        "user": user,
        "title": title,
        "preset": preset,
        "path": str(video_path),
        "export_warnings": export.get("warnings") or [],
        "status": record["status"],
        "hint": "用 get_status(request_id) 查看各平台结果。处理中大约每 10 秒查一次。",
    }


def _http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def _parse_results(rows: Any) -> list[dict[str, Any]]:
    results = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        raw_url = row.get("url") or row.get("post_url")
        url = _http_url(raw_url)
        message = row.get("message") or (raw_url if raw_url and not url else None)
        results.append({
            "platform": row.get("platform"),
            "success": bool(row.get("success")),
            "status": row.get("status") or ("completed" if row.get("success") else "failed"),
            "url": url,
            "message": message,
            "error": row.get("error"),
            "skipped": bool(row.get("skipped")) or row.get("status") == "skipped",
            "fallback_to_inbox": bool(row.get("fallback_to_inbox")),
        })
    return results


def get_status(request_id: str | None = None, job_id: str | None = None,
               config: UploadPostConfig | None = None, session: requests.Session | None = None,
               project_id: str | None = None) -> dict[str, Any]:
    """GET /api/uploadposts/status。终态是 completed / failed / not_found。"""
    if not request_id and not job_id:
        raise ValueError("request_id 或 job_id 必填一个")
    cfg = _require(config)
    params = {"request_id": request_id} if request_id else {"job_id": job_id}
    resp = (session or requests.Session()).get(
        f"{cfg.base_url}/api/uploadposts/status", params=params, headers=_headers(cfg), timeout=30,
    )
    if resp.status_code == 404:
        return {
            "ok": False, "request_id": request_id, "job_id": job_id, "status": "not_found", "final": True,
            "results": [], "message": "Upload-Post 没有这个请求（id 写错，或不是这个 API Key 提交的）",
        }
    data = _raise_for_response(resp, "查询发布状态")
    results = _parse_results(data.get("results"))
    status = data.get("status") or "pending"
    out = {
        "ok": status != "failed",
        "request_id": data.get("request_id") or request_id,
        "job_id": data.get("job_id") or job_id,
        "status": status,
        "final": status in FINAL_STATUSES,
        "completed": data.get("completed"),
        "total": data.get("total"),
        "results": results,
        "message": data.get("message"),
        "last_update": data.get("last_update"),
    }
    if project_id and request_id:
        path = records_dir(project_id) / f"{request_id}.json"
        if path.exists():
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                record.update(status=status, results=results, last_update=out["last_update"])
                path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            except (OSError, ValueError):
                pass
    return out


def wait_for_status(request_id: str, timeout_sec: float = 600, poll_sec: float = 10,
                    config: UploadPostConfig | None = None, project_id: str | None = None,
                    on_update=None) -> dict[str, Any]:
    """文档建议 processing 阶段大约 10 秒查一次，终态就停。"""
    deadline = time.monotonic() + timeout_sec
    last: dict[str, Any] = {}
    while True:
        last = get_status(request_id, config=config, project_id=project_id)
        if on_update:
            on_update(last)
        if last.get("final") or time.monotonic() >= deadline:
            return last
        time.sleep(poll_sec)


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _jobs_dir() -> Path:
    from backend.core.path_utils import get_data_directory
    directory = get_data_directory() / "publish_jobs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _remember_job(job: dict[str, Any]) -> None:
    """内存给当前进程用，文件让进程重启后仍能查到已提交的任务。"""
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


def start_publish(req: PublishRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    _remember_job({
        "job_id": job_id, "status": "queued", "project_id": req.project_id, "clip_id": req.clip_id,
    })
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True, name=f"publish-{job_id[:8]}").start()
    return {"ok": True, "job_id": job_id, "status": "queued"}


def _run_job(job_id: str, req: PublishRequest) -> None:
    job = _read_job(job_id) or {"job_id": job_id, "project_id": req.project_id, "clip_id": req.clip_id}
    job.update(status="running", stage="export")
    _remember_job(job)
    try:
        result = publish_clip(req)
        job.update(status="submitted", stage="submitted", request_id=result["request_id"], result=result)
    except Exception as exc:
        logger.exception("Upload-Post 发布失败")
        job.update(status="failed", error=str(exc)[:500])
    _remember_job(job)


def get_publish_job(job_id: str, refresh_remote: bool = True) -> dict[str, Any] | None:
    job = _read_job(job_id)
    if not job:
        return None
    # 导出线程只活在当前进程。重启后磁盘上仍是 queued/running 的任务不会再往下走。
    with _jobs_lock:
        alive = job_id in _jobs
    if not alive and job.get("status") in {"queued", "running"}:
        job["status"] = "failed"
        job["error"] = "发布进程已中断，请再发一次。"
        _remember_job(job)
        return job
    if refresh_remote and job.get("status") == "submitted" and job.get("request_id"):
        try:
            job["remote"] = get_status(job["request_id"], project_id=job.get("project_id"))
        except Exception as exc:  # noqa: BLE001
            job["remote"] = {"ok": False, "status": "unknown", "message": str(exc)[:300]}
    return job
