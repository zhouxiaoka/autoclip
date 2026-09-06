"""
本地运行器：不起 FastAPI、不起 Celery，在当前进程里把一条视频跑完整条流水线。

给 `autoclip` CLI（backend/cli.py）和 MCP server（backend/mcp_server.py）共用。
复用的是桌面端真正在用的 `SimplePipelineAdapter`，产物目录、metadata、SQLite 记录
都和桌面应用一致——CLI 出的片，打开桌面应用也能看到。

注意：`configure_environment()` 必须在 import 任何 `backend.core.database` 相关模块之前调用，
因为 SQLAlchemy engine 在 import 时就按 `DATABASE_URL` 建好了。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

PROVIDER_CHOICES = ("dashscope", "openai", "gemini", "siliconflow", "ollama", "lmstudio")


# ---------------------------------------------------------------- environment ---
def default_app_dir() -> Path:
    """与桌面应用一致的数据目录：mac 为 ~/Library/Application Support/AutoClip。"""
    env = os.getenv("AUTOCLIP_DATA_DIR") or os.getenv("AUTOCLIP_APP_DIR")
    if env:
        return Path(env).expanduser()
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "AutoClip"
    if system == "Windows":
        base = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "AutoClip"
    xdg = os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg) / "AutoClip"


def configure_environment(data_dir: Optional[Path] = None, quiet: bool = True) -> Path:
    """
    设定数据目录 / 数据库 / 日志相关环境变量。返回实际数据目录。
    必须在 import backend.core.database 之前调用。
    """
    target = (data_dir or default_app_dir()).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    (target / "logs").mkdir(parents=True, exist_ok=True)
    os.environ["AUTOCLIP_APP_DIR"] = str(target)
    os.environ["AUTOCLIP_DATA_DIR"] = str(target)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{target / 'autoclip.db'}")
    os.environ.setdefault("LOG_FILE", str(target / "logs" / "cli.log"))
    # 流水线内部日志很吵；CLI 默认只看进度，日志落文件
    if quiet:
        os.environ.setdefault("AUTOCLIP_CLI_QUIET", "1")
    # 让 `backend.*` 可 import（从任意 cwd 运行 `python -m backend.cli`）
    root = str(Path(__file__).resolve().parent.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    return target


def setup_logging(verbose: bool = False) -> None:
    """CLI 日志策略：文件里全量，终端只在 --verbose 时输出 backend 日志。"""
    log_file = os.getenv("LOG_FILE")
    handlers: List[logging.Handler] = []
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers.append(fh)
    if verbose:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handlers.append(sh)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    if not verbose:
        # 第三方库的 WARNING 也不要刷屏
        for noisy in ("httpx", "openai", "urllib3", "faster_whisper", "sqlalchemy"):
            logging.getLogger(noisy).setLevel(logging.ERROR)


# ---------------------------------------------------------------- LLM config ---
@dataclass
class LLMOverride:
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    def is_empty(self) -> bool:
        return not any([self.provider, self.model, self.base_url, self.api_key])


def configure_llm(override: LLMOverride) -> Dict[str, Any]:
    """
    应用命令行给的 provider / model / base_url / api_key。
    没给任何覆盖 → 直接用桌面应用的 settings.json。
    给了 → 在数据目录下写一份 `cli-settings.json`（平铺格式，不动用户的正式设置），
          用它初始化全局 LLMManager。返回当前 provider 信息。
    """
    from backend.core.llm_manager import get_llm_manager, initialize_llm_manager
    from backend.core.local_presets import resolve_provider, LOCAL_PRESETS
    from backend.core.path_utils import get_data_directory

    if override.is_empty():
        return get_llm_manager().get_current_provider_info()

    base = get_llm_manager()  # 读取用户正式设置作为底稿（key 等）
    settings = dict(base.settings)
    settings.pop("llm_provider_preset", None)

    provider_in = (override.provider or settings.get("llm_provider") or "dashscope").lower()
    provider, base_url, preset = resolve_provider(provider_in, override.base_url or (settings.get("openai_base_url") if provider_in == "openai" else ""))
    settings["llm_provider"] = provider_in if preset else provider
    if provider == "openai":
        settings["openai_base_url"] = base_url
    if override.model:
        settings["model_name"] = override.model
    elif preset and LOCAL_PRESETS[preset].default_model and (override.provider or "").lower() in LOCAL_PRESETS:
        settings["model_name"] = LOCAL_PRESETS[preset].default_model
    if override.api_key is not None:
        key_field = {
            "dashscope": "dashscope_api_key", "openai": "openai_api_key",
            "gemini": "gemini_api_key", "siliconflow": "siliconflow_api_key",
        }.get(provider)
        if key_field:
            settings[key_field] = override.api_key

    cli_settings = get_data_directory() / "cli-settings.json"
    cli_settings.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    manager = initialize_llm_manager(cli_settings)
    info = manager.get_current_provider_info()
    if not info.get("available"):
        raise RuntimeError(
            f"LLM 提供商 {info.get('provider')} 未就绪：缺少 API Key（或本地服务地址）。"
            f" 用 --api-key / --base-url 指定，或先在桌面应用设置页配置。"
        )
    return info


def check_llm_connection() -> Dict[str, Any]:
    """用当前全局 LLMManager 发一条最短请求，返回 {ok, provider, model, error}."""
    from backend.core.llm_manager import get_llm_manager
    m = get_llm_manager()
    info = m.get_current_provider_info()
    if not m.current_provider:
        return {"ok": False, **info, "error": "未配置 API Key / 本地服务地址"}
    base_url = info.get("base_url")
    if base_url:
        # 本地 / 自建服务先探一下地址，避免 SDK 重试半天只留下一句「连接失败」
        try:
            import httpx
            from backend.core.llm_providers import is_local_url
            httpx.get(f"{base_url.rstrip('/')}/models", timeout=2.0, headers={"Authorization": "Bearer EMPTY"},
                      trust_env=not is_local_url(base_url))
        except Exception as e:  # noqa: BLE001
            from backend.core.local_presets import LOCAL_PRESETS
            preset = LOCAL_PRESETS.get(info.get("provider") or "")
            tip = f"请先启动 {preset.display_name.split('（')[0]}（{preset.docs_url}）" if preset else "请检查地址是否正确、服务是否已启动"
            return {"ok": False, **info, "error": f"{base_url} 不可达：{type(e).__name__}。{tip}"}
    try:
        ok = bool(m.current_provider.test_connection())
        return {"ok": ok, **info, "error": None if ok else "连接测试失败"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, **info, "error": str(e)[:300]}


# ---------------------------------------------------------------- project ---
@dataclass
class RunRequest:
    video: Path
    srt: Optional[Path] = None
    name: Optional[str] = None
    category: str = "default"
    min_score: Optional[float] = None
    whisper_model: str = "base"
    register_db: bool = True
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def _write_project_json(project_dir: Path, req: RunRequest, extra: Optional[Dict[str, Any]] = None) -> None:
    """`DataSyncService` 会读 project.json 拿名字；顺手把来源记下来。"""
    meta = {
        "project_name": req.name or req.video.stem,
        "description": f"由 autoclip CLI 从 {req.video} 创建",
        "created_at": datetime.now().isoformat(),
        "source": {"video": str(req.video), "srt": str(req.srt) if req.srt else None, "via": "cli"},
        "video_category": req.category,
        **(extra or {}),
    }
    (project_dir / "project.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _register_project(req: RunRequest, video_path: Path) -> None:
    """在 SQLite 里建项目行，这样桌面应用首页能直接看到并进入详情页。"""
    from backend.core.database import SessionLocal, create_tables
    from backend.models.project import Project, ProjectStatus, ProjectType

    create_tables()
    db = SessionLocal()
    try:
        if db.query(Project).filter(Project.id == req.project_id).first():
            return
        try:
            ptype = ProjectType(req.category)
        except ValueError:
            ptype = ProjectType.DEFAULT if hasattr(ProjectType, "DEFAULT") else list(ProjectType)[0]
        thumbnail = None
        try:
            # 桌面首页卡片要缩略图；和上传流程一样用 ffmpeg 抽一帧转 base64
            from backend.utils.thumbnail_generator import generate_project_thumbnail
            thumbnail = generate_project_thumbnail(req.project_id, video_path)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"缩略图生成失败: {e}")
        project = Project(
            id=req.project_id,
            name=req.name or req.video.stem,
            description=f"由 autoclip CLI 从 {req.video.name} 创建",
            project_type=ptype,
            status=ProjectStatus.PROCESSING,
            video_path=str(video_path),
            thumbnail=thumbnail,
            processing_config={"source": "cli"},
            project_metadata={"source_url": None, "via": "cli", "original_video": str(req.video)},
        )
        db.add(project)
        db.commit()
    finally:
        db.close()


def _set_project_status(project_id: str, status: str, error: Optional[str] = None) -> None:
    try:
        from backend.core.database import SessionLocal
        from backend.models.project import Project, ProjectStatus

        db = SessionLocal()
        try:
            p = db.query(Project).filter(Project.id == project_id).first()
            if not p:
                return
            p.status = ProjectStatus(status)
            p.updated_at = datetime.utcnow()
            if status == "completed":
                p.completed_at = datetime.utcnow()
            if error is not None and hasattr(p, "error_message"):
                p.error_message = error[:2000]
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"更新项目状态失败: {e}")


def prepare_project(req: RunRequest, link: bool = True) -> Path:
    """
    建项目目录、把视频放进 raw/（默认硬链接，失败则复制；`link=False` 强制复制）。
    返回 raw 里的视频路径。
    """
    from backend.core.path_utils import get_project_directory

    req.video = req.video.expanduser().resolve()
    if not req.video.exists():
        raise FileNotFoundError(f"视频不存在: {req.video}")
    if req.srt:
        req.srt = req.srt.expanduser().resolve()
        if not req.srt.exists():
            raise FileNotFoundError(f"字幕不存在: {req.srt}")

    project_dir = get_project_directory(req.project_id)
    raw_dir = project_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / f"input{req.video.suffix.lower() or '.mp4'}"
    if not target.exists():
        linked = False
        if link:
            try:
                os.link(req.video, target)
                linked = True
            except OSError:
                linked = False
        if not linked:
            shutil.copy2(req.video, target)
    if req.srt:
        srt_target = raw_dir / "input.srt"
        if not srt_target.exists():
            shutil.copy2(req.srt, srt_target)
    _write_project_json(project_dir, req)
    if req.register_db:
        _register_project(req, target)
    return target


ProgressFn = Callable[[Dict[str, Any]], None]


def run_pipeline(req: RunRequest, video_in_raw: Path, on_progress: Optional[ProgressFn] = None) -> Dict[str, Any]:
    """同步跑完整条流水线（阻塞）。返回 adapter 的结果 dict（status: succeeded / failed）。"""
    from backend.services.simple_progress import add_progress_listener, remove_progress_listener
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter

    if req.min_score is not None:
        # step3 的阈值是模块常量（设置页的值目前也没接进去），CLI 这里直接覆盖
        import backend.pipeline.step3_scoring as step3
        step3.MIN_SCORE_THRESHOLD = float(req.min_score)

    srt_in_raw = video_in_raw.parent / "input.srt"
    srt_arg = str(srt_in_raw) if srt_in_raw.exists() else ""

    listener = None
    if on_progress:
        def listener(payload: Dict[str, Any]) -> None:  # noqa: E306
            if payload.get("project_id") == req.project_id:
                on_progress(payload)
        add_progress_listener(listener)
    try:
        adapter = SimplePipelineAdapter(req.project_id, task_id=f"cli-{req.project_id[:8]}")
        result = asyncio.run(adapter.process_project_sync(str(video_in_raw), srt_arg))
    finally:
        if listener:
            remove_progress_listener(listener)

    if req.register_db:
        if result.get("status") == "succeeded":
            _set_project_status(req.project_id, "completed")
        else:
            _set_project_status(req.project_id, "failed", result.get("error"))
    return result


# ---------------------------------------------------------------- results ---
def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def normalize_score(score: Any) -> Optional[int]:
    """流水线评分有 0–1 / 0–10 两种口径，统一成 0–100 整数（与前端 ClipCard 一致）。"""
    if not isinstance(score, (int, float)):
        return None
    s = float(score)
    if s <= 1:
        s *= 100
    elif s <= 10:
        s *= 10
    return int(round(max(0, min(100, s))))


def summarize_project(project_id: str) -> Dict[str, Any]:
    """从项目目录读出切片 / 合集 / 文件路径，给 CLI --json 和 MCP 返回。"""
    from backend.core.path_utils import get_projects_directory

    project_dir = get_projects_directory() / project_id
    if not project_dir.exists():
        raise FileNotFoundError(f"项目不存在: {project_id}")
    meta_dir = project_dir / "metadata"
    out_dir = project_dir / "output"
    project_meta = _load_json(project_dir / "project.json", {})
    if not project_meta.get("project_name"):
        row = _db_projects().get(project_id)
        if row:
            project_meta["project_name"] = row.get("name")
    clips_meta: List[Dict[str, Any]] = _load_json(meta_dir / "clips_metadata.json", [])
    collections_meta: List[Dict[str, Any]] = _load_json(meta_dir / "collections_metadata.json", [])
    video_out = _load_json(out_dir / "step6_video_output.json", {})
    clip_paths: List[str] = video_out.get("clip_paths", []) or []
    collection_paths: List[str] = video_out.get("collection_paths", []) or []

    def find_path(prefix: str, pool: List[str]) -> Optional[str]:
        for p in pool:
            if Path(p).name.startswith(prefix):
                return p
        return None

    clips = []
    for c in clips_meta:
        cid = str(c.get("id"))
        clips.append({
            "id": cid,
            "title": c.get("generated_title") or c.get("title") or c.get("outline"),
            "outline": c.get("outline"),
            "start_time": c.get("start_time"),
            "end_time": c.get("end_time"),
            "score": c.get("final_score"),
            "score_100": normalize_score(c.get("final_score")),
            "reason": c.get("recommend_reason"),
            "file": find_path(f"{cid}_", clip_paths),
        })
    clips.sort(key=lambda x: -(x["score_100"] or 0))
    collections = []
    for col in collections_meta:
        title = col.get("collection_title") or ""
        collections.append({
            "id": str(col.get("id")),
            "title": title,
            "summary": col.get("collection_summary"),
            "clip_ids": [str(x) for x in col.get("clip_ids", [])],
            "file": next((p for p in collection_paths if title and title[:12] in Path(p).name), None),
        })
    return {
        "project_id": project_id,
        "name": project_meta.get("project_name") or project_id[:8],
        "project_dir": str(project_dir),
        "clips_dir": str(out_dir / "clips"),
        "collections_dir": str(out_dir / "collections"),
        "clips": clips,
        "collections": collections,
        "counts": {"clips": len(clips), "collections": len(collections)},
        "source": project_meta.get("source"),
    }


def _db_projects() -> Dict[str, Dict[str, Any]]:
    """SQLite 里的项目（桌面应用建的项目没有 project.json，名字 / 状态在这里）。读不到就返回空。"""
    try:
        from backend.core.database import SessionLocal
        from backend.models.project import Project

        db = SessionLocal()
        try:
            rows = db.query(Project).all()
            out = {}
            for p in rows:
                status = p.status.value if hasattr(p.status, "value") else str(p.status or "")
                out[p.id] = {"name": p.name, "status": status.lower(), "video_path": p.video_path,
                             "clips": len(getattr(p, "clips", []) or [])}
            return out
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"读取数据库项目失败: {e}")
        return {}


def list_projects(limit: int = 50) -> List[Dict[str, Any]]:
    """数据目录下的项目（按修改时间倒序），名字 / 状态优先取 SQLite，其次看文件。"""
    from backend.core.path_utils import get_projects_directory

    db_rows = _db_projects()
    items = []
    for d in get_projects_directory().iterdir():
        if not d.is_dir():
            continue
        meta = _load_json(d / "project.json", {})
        clips = _load_json(d / "metadata" / "clips_metadata.json", [])
        video_out = _load_json(d / "output" / "step6_video_output.json", {})
        fs_status = "completed" if video_out.get("clip_paths") else ("processed" if clips else "pending")
        row = db_rows.get(d.name, {})
        items.append({
            "project_id": d.name,
            "name": meta.get("project_name") or row.get("name") or d.name[:8],
            "status": row.get("status") or fs_status,
            "clips": len(clips) or row.get("clips", 0),
            "updated_at": datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="seconds"),
            "via": (meta.get("source") or {}).get("via") if isinstance(meta.get("source"), dict) else None,
        })
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items[:limit]


# ---------------------------------------------------------------- doctor ---
def environment_report() -> Dict[str, Any]:
    """ffmpeg / whisper 运行时 / LLM 配置 / 数据目录一览，给 `autoclip doctor` 和 MCP 用。"""
    from backend.core.path_utils import get_data_directory
    from backend.services import whisper_runtime

    report: Dict[str, Any] = {"data_dir": str(get_data_directory()), "python": sys.version.split()[0]}
    try:
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        ff = get_ffmpeg_path()
        report["ffmpeg"] = {"ok": bool(ff and (Path(ff).exists() or shutil.which(ff))), "path": ff}
    except Exception as e:  # noqa: BLE001
        report["ffmpeg"] = {"ok": False, "error": str(e)}
    try:
        st = whisper_runtime.get_status()
        report["whisper"] = {"ok": st.get("status") == "installed", "status": st.get("status"), "models_dir": str(whisper_runtime.get_models_dir())}
    except Exception as e:  # noqa: BLE001
        report["whisper"] = {"ok": False, "error": str(e)}
    report["llm"] = check_llm_connection()
    return report


def as_dict(obj: Any) -> Dict[str, Any]:
    return asdict(obj) if hasattr(obj, "__dataclass_fields__") else dict(obj)
