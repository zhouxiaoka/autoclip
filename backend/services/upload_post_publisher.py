"""
发布到海外平台：把「发布导出」渲好的成片通过 Upload-Post 一次发到 TikTok / Instagram / YouTube Shorts 等。

流程：export_clip（已有，走缓存）→ POST https://api.upload-post.com/api/upload（multipart，async）
     → 拿 request_id → GET /api/uploadposts/status 轮询每个平台的结果。

视频处理仍全部在本地；只有成片文件本身发给 Upload-Post。B 站投稿沿用原来的 bilibili_service，这里不碰。

配置（优先级从高到低）：
    1. 环境变量 UPLOAD_POST_API_KEY / UPLOAD_POST_USER（Docker / CLI）
    2. <数据目录>/upload_post.json（PUT /publish/upload-post/config 或 `autoclip publish --api-key … --save` 写入）

API 文档：https://docs.upload-post.com/api/upload-video
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

# Upload-Post 支持的视频平台（platform[] 的取值）
PLATFORMS: list[str] = [
    "tiktok", "instagram", "youtube", "facebook", "linkedin", "x", "threads",
    "pinterest", "bluesky", "reddit", "discord", "telegram", "google_business", "mastodon", "wordpress",
]
# 竖屏短视频平台默认用 9:16 crop 预设；其他平台保留原画
VERTICAL_PLATFORMS = {"tiktok", "instagram", "youtube", "facebook", "threads", "pinterest"}

# 不允许透传的多余字段（避免覆盖我们自己填的必填项）
_RESERVED_FORM_FIELDS = {"user", "platform[]", "platform", "video", "async_upload", "request_id", "external_id"}


class UploadPostError(RuntimeError):
    """Upload-Post 返回了错误（HTTP 4xx/5xx 或 success=false）"""

    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


# ---------------------------------------------------------------- config ---
@dataclass
class UploadPostConfig:
    api_key: str = ""
    user: str = ""          # Upload-Post 里的 profile 名；不填时请求里必须显式给 user
    base_url: str = DEFAULT_API_BASE
    source: str = "none"    # env / file / none

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
    """环境变量优先，其次数据目录里的 upload_post.json。"""
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
            logger.warning(f"读取 {path} 失败: {e}")

    user = env_user or file_user  # user 单独取优先级：环境变量 > 文件
    if env_key:
        return UploadPostConfig(api_key=env_key, user=user, base_url=base_url, source="env")
    if file_key:
        return UploadPostConfig(api_key=file_key, user=user, base_url=base_url, source="file")
    return UploadPostConfig(user=user, base_url=base_url, source="none")


def save_config(api_key: str | None = None, user: str | None = None) -> UploadPostConfig:
    """写 <数据目录>/upload_post.json；传 None 的字段保留原值。文件权限 0600。"""
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
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # Windows 上可能不支持
        pass
    return load_config()


def clear_config() -> None:
    path = config_path()
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------- http ---
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


def _raise_for_response(resp: requests.Response, what: str) -> dict[str, Any]:
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": (resp.text or "")[:500]}
    if resp.status_code >= 400:
        msg = None
        if isinstance(payload, dict):
            msg = payload.get("message") or payload.get("error") or payload.get("detail")
            if isinstance(msg, dict):
                msg = msg.get("message") or json.dumps(msg, ensure_ascii=False)
        if resp.status_code == 401:
            msg = msg or "API Key 无效或已过期"
        raise UploadPostError(f"{what}失败（HTTP {resp.status_code}）: {msg or payload}", resp.status_code, payload)
    if isinstance(payload, dict) and payload.get("success") is False:
        raise UploadPostError(f"{what}失败: {payload.get('message') or payload.get('error') or payload}", resp.status_code, payload)
    return payload if isinstance(payload, dict) else {"data": payload}


def verify_api_key(config: UploadPostConfig | None = None, session: requests.Session | None = None) -> dict[str, Any]:
    """GET /api/uploadposts/me：校验 key，返回账号邮箱与套餐。"""
    cfg = _require(config)
    s = session or requests.Session()
    resp = s.get(f"{cfg.base_url}/api/uploadposts/me", headers=_headers(cfg), timeout=30)
    data = _raise_for_response(resp, "校验 API Key")
    return {"ok": True, "email": data.get("email"), "plan": data.get("plan")}


def list_profiles(config: UploadPostConfig | None = None, session: requests.Session | None = None) -> list[dict[str, Any]]:
    """GET /api/uploadposts/users：API Key 下的 profile 及各自已连接的平台。"""
    cfg = _require(config)
    s = session or requests.Session()
    resp = s.get(f"{cfg.base_url}/api/uploadposts/users", headers=_headers(cfg), timeout=30)
    data = _raise_for_response(resp, "读取 profile 列表")
    out: list[dict[str, Any]] = []
    for p in data.get("profiles") or []:
        accounts = p.get("social_accounts") or {}
        connected = []
        for platform, info in accounts.items():
            # 已连接的平台是一个 dict（display_name 等）；只是占位的是空字符串
            if isinstance(info, dict) and (info.get("display_name") or info.get("username") or info):
                connected.append(platform)
        out.append({
            "username": p.get("username"),
            "connected_platforms": sorted(connected),
            "created_at": p.get("created_at"),
        })
    return out


# ---------------------------------------------------------------- publish ---
@dataclass
class PublishRequest:
    project_id: str
    clip_id: str
    platforms: Sequence[str]
    user: str | None = None            # 不填用配置里的默认 profile
    preset: str | None = None          # 发布导出预设；不填按平台自动选（竖屏平台 shorts，其余 original）
    title: str | None = None           # 不填用切片标题
    description: str | None = None     # YouTube / LinkedIn / Facebook / Pinterest 用
    subtitles: bool = True
    title_card: bool = True
    scheduled_date: str | None = None  # ISO-8601，定时发布
    timezone: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # 平台专属字段透传：privacy_level / privacyStatus / facebook_page_id / pinterest_board_id …


def normalize_platforms(platforms: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for raw in platforms:
        for p in str(raw).replace(";", ",").split(","):
            p = p.strip().lower()
            if not p:
                continue
            if p == "twitter":
                p = "x"
            if p not in PLATFORMS:
                raise ValueError(f"不支持的平台: {p}（可选 {', '.join(PLATFORMS)}）")
            if p not in seen:
                seen.append(p)
    if not seen:
        raise ValueError("至少要指定一个平台")
    return seen


def pick_preset(platforms: Sequence[str]) -> str:
    """没指定预设时：只要有一个竖屏短视频平台就渲 9:16（shorts 预设，≤60s crop），否则原画重编码。"""
    return "shorts" if any(p in VERTICAL_PLATFORMS for p in platforms) else "original"


def records_dir(project_id: str) -> Path:
    from backend.core.path_utils import get_project_directory
    d = get_project_directory(project_id) / "output" / "publish"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_record(project_id: str, record: dict[str, Any]) -> Path:
    path = records_dir(project_id) / f"{record['request_id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_records(project_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in records_dir(project_id).glob("*.json"):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    out.sort(key=lambda r: r.get("submitted_at") or "", reverse=True)
    return out


def build_form(req: PublishRequest, platforms: list[str], user: str, title: str, request_id: str) -> dict[str, Any]:
    """multipart 表单（不含 video 文件）。platform[] 是重复字段，requests 会按 list 逐个编码。"""
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
    for k, v in (req.extra or {}).items():
        if k in _RESERVED_FORM_FIELDS or v is None:
            continue
        form[k] = "true" if v is True else "false" if v is False else v
    return form


def publish_clip(req: PublishRequest, config: UploadPostConfig | None = None,
                 session: requests.Session | None = None) -> dict[str, Any]:
    """
    同步：导出成片（走缓存）→ 提交 Upload-Post（async_upload=true）→ 返回 request_id。
    返回 {ok, request_id, platforms, user, title, path, preset, status_hint}。
    真正的发布结果用 get_status(request_id) 查。
    """
    from backend.services.publish_export import (
        ExportRequest,
        export_clip,
        load_clip_meta,
    )

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
    headers["Idempotency-Key"] = request_id  # 超时重试也不会发两遍

    s = session or requests.Session()
    logger.info("Upload-Post 提交: clip=%s platforms=%s user=%s preset=%s file=%s",
                req.clip_id, platforms, user, preset, video_path.name)
    with video_path.open("rb") as fh:
        resp = s.post(
            f"{cfg.base_url}/api/upload",
            headers=headers,
            data=form,
            files={"video": (video_path.name, fh, "video/mp4")},
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
        "hint": "用 get_status(request_id) / `autoclip publish --status <request_id>` 查看各平台结果，一般 10 秒查一次。",
    }


# ---------------------------------------------------------------- status ---
FINAL_STATUSES = {"completed", "failed", "not_found"}


def get_status(request_id: str | None = None, job_id: str | None = None,
               config: UploadPostConfig | None = None, session: requests.Session | None = None,
               project_id: str | None = None) -> dict[str, Any]:
    """GET /api/uploadposts/status：汇总各平台结果。有 project_id 时顺带更新本地记录。"""
    if not request_id and not job_id:
        raise ValueError("request_id 或 job_id 必填一个")
    cfg = _require(config)
    s = session or requests.Session()
    params = {"request_id": request_id} if request_id else {"job_id": job_id}
    resp = s.get(f"{cfg.base_url}/api/uploadposts/status", params=params, headers=_headers(cfg), timeout=30)
    if resp.status_code == 404:
        return {"ok": False, "request_id": request_id, "job_id": job_id, "status": "not_found", "final": True,
                "results": [], "message": "Upload-Post 没有这个请求（id 写错，或不是这个 API Key 提交的）"}
    data = _raise_for_response(resp, "查询发布状态")

    results = []
    for r in data.get("results") or []:
        # 私密 / 草稿发布时 url 字段是一句说明（"Post uploaded as Private. No public URL available."），不是链接
        raw_url = r.get("url") or r.get("post_url")
        url = raw_url if isinstance(raw_url, str) and raw_url.startswith(("http://", "https://")) else None
        message = r.get("message") or (raw_url if raw_url and not url else None)
        results.append({
            "platform": r.get("platform"),
            "success": bool(r.get("success")),
            "status": r.get("status") or ("completed" if r.get("success") else "failed"),
            "url": url,
            "message": message,
            "error": r.get("error"),
            "skipped": bool(r.get("skipped")),
            "fallback_to_inbox": bool(r.get("fallback_to_inbox")),
        })
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
    """轮询到终态或超时（文档建议 processing 阶段 10 秒一次）。"""
    deadline = time.monotonic() + timeout_sec
    last: dict[str, Any] = {}
    while True:
        last = get_status(request_id, config=config, project_id=project_id)
        if on_update:
            on_update(last)
        if last.get("final") or time.monotonic() >= deadline:
            return last
        time.sleep(poll_sec)


# ---------------------------------------------------------------- jobs (API 用) ---
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def start_publish(req: PublishRequest) -> dict[str, Any]:
    """后台线程跑 publish_clip（导出可能要几十秒）；API 用 get_publish_job 轮询。"""
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "status": "queued", "project_id": req.project_id, "clip_id": req.clip_id}
    t = threading.Thread(target=_run_job, args=(job_id, req), daemon=True, name=f"publish-{job_id[:8]}")
    t.start()
    return {"ok": True, "job_id": job_id, "status": "queued"}


def _run_job(job_id: str, req: PublishRequest) -> None:
    with _jobs_lock:
        _jobs[job_id].update(status="running", stage="export")
    try:
        result = publish_clip(req)
        with _jobs_lock:
            _jobs[job_id].update(status="submitted", stage="submitted", request_id=result["request_id"], result=result)
    except Exception as e:
        logger.exception("Upload-Post 发布失败")
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=str(e)[:500])


def get_publish_job(job_id: str, refresh_remote: bool = True) -> dict[str, Any] | None:
    """本地任务状态；已提交的顺带查一次 Upload-Post 的平台结果（remote）。"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        job = dict(job) if job else None
    if not job:
        return None
    if refresh_remote and job.get("status") == "submitted" and job.get("request_id"):
        try:
            job["remote"] = get_status(job["request_id"], project_id=job.get("project_id"))
        except Exception as e:  # noqa: BLE001
            job["remote"] = {"ok": False, "status": "unknown", "message": str(e)[:300]}
    return job
