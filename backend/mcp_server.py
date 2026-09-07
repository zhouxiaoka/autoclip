"""
AutoClip MCP server（stdio）——让 Cursor / Claude Code / 任何 MCP 客户端直接调 AutoClip 出片。

启动：
    autoclip mcp                       # 装了包
    python -m backend.mcp_server       # 仓库内

客户端配置示例（Cursor `~/.cursor/mcp.json` / Claude `claude mcp add`）：
    { "mcpServers": { "autoclip": { "command": "autoclip", "args": ["mcp"] } } }
    或 { "command": "/path/to/autoclip/venv/bin/python", "args": ["-m", "backend.mcp_server"],
         "env": { "PYTHONPATH": "/path/to/autoclip" } }

工具：
    clip_video          同步出片（几分钟到几十分钟，带进度通知）
    start_clip_job      后台出片，立刻返回 project_id
    get_job_status      查进度 / 拿结果
    get_project         已完成项目的切片、合集与文件路径
    list_projects       最近项目
    list_providers      可用模型提供商与本地预设（ollama / lmstudio）
    check_environment   ffmpeg / Whisper / 模型连接体检

依赖 `mcp` Python SDK（requirements.txt 已含；兼容 1.x FastMCP 与 2.x MCPServer）。
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.services.local_runner import (
    LLMOverride,
    RunRequest,
    configure_environment,
    setup_logging,
)

logger = logging.getLogger(__name__)

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server, Context  # type: ignore
except ImportError:  # mcp 1.x
    try:
        from mcp.server.fastmcp import FastMCP as _Server, Context  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit("缺少 mcp SDK：pip install mcp") from e

INSTRUCTIONS = """AutoClip 把长视频（讲座 / 访谈 / 播客录像）切成带标题、带评分的高光片段，并按主题串成合集。
典型用法：用户给一个本地视频路径 → 调 clip_video（或 start_clip_job + get_job_status 轮询）→
把返回的切片列表（标题 / 时间段 / 评分 / 文件路径）整理给用户。
没有字幕时会用本地 Whisper 转写，首次较慢。想省钱或离线：provider="ollama"（需本机装 Ollama）。
切片为 0 通常是评分阈值过高，用 min_score=0.5 重试。"""

server = _Server(
    name="autoclip",
    instructions=INSTRUCTIONS,
)

# ---------------------------------------------------------------- job registry ---
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_pipeline_lock = threading.Lock()  # 全局 LLM 配置是进程级的，任务串行跑


def _job_update(project_id: str, **fields: Any) -> None:
    with _jobs_lock:
        _jobs.setdefault(project_id, {})
        _jobs[project_id].update(fields)


def _run_job(req: RunRequest, override: LLMOverride, link: bool) -> Dict[str, Any]:
    """阻塞执行；在线程里调用。"""
    from backend.services.local_runner import configure_llm, prepare_project, run_pipeline, summarize_project

    with _pipeline_lock:
        try:
            info = configure_llm(override)
            video_in_raw = prepare_project(req, link=link)
            _job_update(req.project_id, status="running", llm=info, percent=0, stage="INGEST", message="开始")

            def on_progress(p: Dict[str, Any]) -> None:
                _job_update(req.project_id, percent=p.get("percent", 0), stage=p.get("stage"), message=p.get("message"))

            result = run_pipeline(req, video_in_raw, on_progress=on_progress)
            if result.get("status") != "succeeded":
                _job_update(req.project_id, status="failed", error=result.get("error") or "处理失败")
                return _jobs[req.project_id]
            summary = summarize_project(req.project_id)
            _job_update(req.project_id, status="completed", percent=100, stage="DONE", message="完成", result=summary)
            return _jobs[req.project_id]
        except Exception as e:  # noqa: BLE001
            logger.exception("MCP 任务失败")
            _job_update(req.project_id, status="failed", error=str(e)[:500])
            return _jobs[req.project_id]


def _make_request(video_path: str, srt_path: Optional[str], name: Optional[str], category: str,
                  min_score: Optional[float]) -> RunRequest:
    return RunRequest(
        video=Path(video_path),
        srt=Path(srt_path) if srt_path else None,
        name=name,
        category=category or "default",
        min_score=min_score,
    )


def _make_override(provider: Optional[str], model: Optional[str], base_url: Optional[str], api_key: Optional[str]) -> LLMOverride:
    return LLMOverride(provider=provider, model=model, base_url=base_url, api_key=api_key)


# ---------------------------------------------------------------- tools ---
@server.tool(
    name="clip_video",
    description=(
        "把一条本地视频切成高光片段（同步，耗时数分钟到数十分钟，期间会发进度）。"
        "返回切片列表（标题 / 起止时间 / 评分 / mp4 路径）与合集。"
        "provider 可选 dashscope / openai / gemini / siliconflow / ollama / lmstudio；不填用桌面应用里已配置的模型。"
    ),
)
async def clip_video(
    video_path: str,
    ctx: Context,
    srt_path: Optional[str] = None,
    name: Optional[str] = None,
    category: str = "default",
    min_score: Optional[float] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    req = _make_request(video_path, srt_path, name, category, min_score)
    override = _make_override(provider, model, base_url, api_key)
    _job_update(req.project_id, status="queued", percent=0, video=str(req.video))

    task = asyncio.create_task(asyncio.to_thread(_run_job, req, override, True))
    last_percent = -1
    while not task.done():
        await asyncio.sleep(1.0)
        job = _jobs.get(req.project_id, {})
        pct = int(job.get("percent") or 0)
        if pct != last_percent:
            last_percent = pct
            try:
                await ctx.report_progress(pct, 100, f"{job.get('stage', '')} {job.get('message', '')}".strip())
            except Exception:  # noqa: BLE001
                pass
    job = task.result()
    if job.get("status") != "completed":
        return {"ok": False, "project_id": req.project_id, "error": job.get("error", "处理失败")}
    return {"ok": True, **job["result"], "llm": job.get("llm")}


@server.tool(
    name="start_clip_job",
    description="后台开始出片，立刻返回 project_id；之后用 get_job_status 轮询进度和结果。适合客户端对单次工具调用有超时限制的情况。",
)
def start_clip_job(
    video_path: str,
    srt_path: Optional[str] = None,
    name: Optional[str] = None,
    category: str = "default",
    min_score: Optional[float] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    req = _make_request(video_path, srt_path, name, category, min_score)
    if not req.video.expanduser().exists():
        return {"ok": False, "error": f"视频不存在: {req.video}"}
    override = _make_override(provider, model, base_url, api_key)
    _job_update(req.project_id, status="queued", percent=0, video=str(req.video))
    t = threading.Thread(target=_run_job, args=(req, override, True), daemon=True, name=f"autoclip-{req.project_id[:8]}")
    t.start()
    return {"ok": True, "project_id": req.project_id, "status": "queued", "hint": "用 get_job_status 轮询；一般每 10–20 秒查一次即可。"}


@server.tool(name="get_job_status", description="查询 start_clip_job 开始的任务：status（queued / running / completed / failed）、percent、stage、message；完成后附带 result。")
def get_job_status(project_id: str) -> Dict[str, Any]:
    job = _jobs.get(project_id)
    if not job:
        # 可能是上次进程里的项目：直接从磁盘读
        try:
            from backend.services.local_runner import summarize_project
            return {"ok": True, "project_id": project_id, "status": "completed", "result": summarize_project(project_id)}
        except FileNotFoundError:
            return {"ok": False, "project_id": project_id, "error": "没有这个任务 / 项目"}
    return {"ok": job.get("status") != "failed", "project_id": project_id, **job}


@server.tool(name="get_project", description="读取一个已处理项目的切片（标题 / 时间 / 评分 / 文件）、合集与输出目录。")
def get_project(project_id: str) -> Dict[str, Any]:
    from backend.services.local_runner import summarize_project

    try:
        return {"ok": True, **summarize_project(project_id)}
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}


@server.tool(name="list_projects", description="列出最近的 AutoClip 项目（与桌面应用共用数据目录）。")
def list_projects(limit: int = 20) -> List[Dict[str, Any]]:
    from backend.services.local_runner import list_projects as _list

    return _list(limit=limit)


@server.tool(name="list_providers", description="可用的模型提供商与本地预设（ollama / lmstudio 的默认地址与模型），以及当前正在用的配置。")
def list_providers() -> Dict[str, Any]:
    from backend.core.llm_manager import get_llm_manager
    from backend.core.local_presets import presets_as_dicts

    return {
        "current": get_llm_manager().get_current_provider_info(),
        "cloud": ["dashscope", "openai", "gemini", "siliconflow"],
        "local_presets": presets_as_dicts(),
    }


@server.tool(
    name="export_clip",
    description=(
        "把一条已切好的片段渲成可直接发布的成片：9:16（抖音/小红书/Shorts）、烧字幕、标题卡。"
        "preset: douyin / xiaohongshu / shorts / bilibili / original。"
        "返回成片路径；同参数再导会走缓存。"
    ),
)
def export_clip(
    project_id: str,
    clip_id: str,
    preset: str = "douyin",
    subtitles: bool = True,
    title_card: bool = True,
) -> Dict[str, Any]:
    from backend.services.publish_export import ExportRequest, export_clip as _export
    try:
        return _export(ExportRequest(project_id, clip_id, preset, subtitles, title_card))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}


@server.tool(name="check_environment", description="体检：ffmpeg、Whisper 运行时、模型连接是否就绪。出片前先调一次能少踩坑。")
def check_environment(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    from backend.services.local_runner import configure_llm, environment_report

    override = _make_override(provider, model, base_url, api_key)
    try:
        configure_llm(override)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    rep = environment_report()
    rep["ok"] = bool(rep["ffmpeg"]["ok"] and rep["llm"]["ok"])
    return rep


# ---------------------------------------------------------------- entry ---
async def _serve_stdio() -> None:
    """
    stdout 是 MCP 协议通道。流水线里散落着 print()，一旦落到 stdout 就会把协议打坏，
    所以把真正的 stdout 交给 MCP 传输层，再把 sys.stdout 指到 stderr。
    """
    import io
    import anyio
    from mcp.server.stdio import stdio_server

    real_stdout = anyio.wrap_file(io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True))
    real_stdin = anyio.wrap_file(io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
    sys.stdout = sys.stderr

    lowlevel = getattr(server, "_lowlevel_server", None) or getattr(server, "_mcp_server")
    async with stdio_server(stdin=real_stdin, stdout=real_stdout) as (read_stream, write_stream):
        await lowlevel.run(read_stream, write_stream, lowlevel.create_initialization_options())


def main() -> int:
    configure_environment()
    setup_logging(verbose=False)  # 日志只进文件，终端（stderr）保持安静
    import anyio

    anyio.run(_serve_stdio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
