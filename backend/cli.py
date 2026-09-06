#!/usr/bin/env python3
"""
autoclip — 命令行出片。

    autoclip run video.mp4                         # 用桌面应用里配好的模型
    autoclip run video.mp4 --provider ollama       # 本地 Ollama（默认 qwen2.5:7b，无需 key）
    autoclip run video.mp4 --provider lmstudio --model qwen2.5-7b-instruct
    autoclip run video.mp4 --provider openai --base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key sk-...
    autoclip run video.mp4 --srt video.srt --min-score 0.6 --json
    autoclip list / show <project_id> / providers / doctor

产物与桌面应用共用同一个数据目录（mac: ~/Library/Application Support/AutoClip），
跑完在桌面应用首页就能看到。用 --data-dir 或 AUTOCLIP_DATA_DIR 可以换目录。

不装包也能用：`python -m backend.cli ...`；`pip install -e .` 之后有 `autoclip` 命令。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# 只 import 不触发数据库 / 模型初始化的东西；重活放在子命令里、configure_environment 之后
from backend.services.local_runner import (
    PROVIDER_CHOICES,
    LLMOverride,
    RunRequest,
    configure_environment,
    setup_logging,
)

STAGE_NAMES = {
    "INGEST": "准备", "SUBTITLE": "字幕", "ANALYZE": "分析",
    "HIGHLIGHT": "选段", "EXPORT": "导出", "DONE": "完成",
}
_TTY = sys.stderr.isatty()


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _TTY else s


def _dim(s: str) -> str:
    return _c("2", s)


def _bold(s: str) -> str:
    return _c("1", s)


def _err(msg: str) -> None:
    print(_c("31", "error: ") + msg, file=sys.stderr)


def _add_llm_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("模型（不填则用桌面应用设置页里的配置）")
    g.add_argument("--provider", choices=PROVIDER_CHOICES, help="dashscope / openai / gemini / siliconflow，或本地预设 ollama / lmstudio")
    g.add_argument("--model", help="模型名，如 qwen-plus、gpt-4o-mini、qwen2.5:7b")
    g.add_argument("--base-url", help="OpenAI 兼容接口地址（provider=openai 时用；ollama/lmstudio 有默认值）")
    g.add_argument("--api-key", help="API Key（本地模型可不填）。也可用环境变量 AUTOCLIP_API_KEY")


def _llm_override(args: argparse.Namespace) -> LLMOverride:
    return LLMOverride(
        provider=getattr(args, "provider", None),
        model=getattr(args, "model", None),
        base_url=getattr(args, "base_url", None),
        api_key=getattr(args, "api_key", None) or os.getenv("AUTOCLIP_API_KEY"),
    )


# ---------------------------------------------------------------- run ---
def cmd_run(args: argparse.Namespace) -> int:
    from backend.services.local_runner import configure_llm, prepare_project, run_pipeline, summarize_project

    t0 = time.time()
    try:
        info = configure_llm(_llm_override(args))
    except Exception as e:  # noqa: BLE001
        _err(str(e))
        return 2

    req = RunRequest(
        video=Path(args.video),
        srt=Path(args.srt) if args.srt else None,
        name=args.name,
        category=args.category,
        min_score=args.min_score,
        register_db=not args.no_db,
    )
    try:
        video_in_raw = prepare_project(req, link=not args.copy)
    except FileNotFoundError as e:
        _err(str(e))
        return 2

    if not args.json:
        model_desc = f"{info.get('provider')} · {info.get('model')}"
        if info.get("base_url"):
            model_desc += f" · {info['base_url']}"
        print(_bold(req.name or req.video.stem) + _dim(f"  {req.project_id}"), file=sys.stderr)
        print(_dim(f"模型 {model_desc}"), file=sys.stderr)
        if not req.srt:
            print(_dim("没有字幕文件，将用本地 Whisper 转写（首次会下载模型）"), file=sys.stderr)

    last = {"line": ""}

    def on_progress(p: Dict[str, Any]) -> None:
        if args.json:
            return
        stage = STAGE_NAMES.get(p.get("stage", ""), p.get("stage", ""))
        line = f"[{p.get('percent', 0):3d}%] {stage:<3} {p.get('message', '')}"
        if line != last["line"]:
            print(line, file=sys.stderr)
            last["line"] = line

    result = run_pipeline(req, video_in_raw, on_progress=on_progress)
    elapsed = time.time() - t0

    if result.get("status") != "succeeded":
        if args.json:
            print(json.dumps({"ok": False, "project_id": req.project_id, "error": result.get("error")}, ensure_ascii=False))
        else:
            _err(result.get("error") or "处理失败")
            print(_dim(f"日志：{os.getenv('LOG_FILE')}"), file=sys.stderr)
        return 1

    summary = summarize_project(req.project_id)
    summary["elapsed_sec"] = round(elapsed, 1)
    summary["llm"] = {k: info.get(k) for k in ("provider", "model", "base_url") if info.get(k)}
    if args.json:
        print(json.dumps({"ok": True, **summary}, ensure_ascii=False, indent=2))
        return 0

    print(file=sys.stderr)
    n_clips, n_cols = summary["counts"]["clips"], summary["counts"]["collections"]
    print(_bold(f"完成  {n_clips} 切片 · {n_cols} 合集 · {elapsed:.0f}s"), file=sys.stderr)
    for c in summary["clips"]:
        score = str(c["score_100"]) if c.get("score_100") is not None else "-"
        print(f"  {score:>4}  {c['start_time']} → {c['end_time']}  {c['title']}", file=sys.stderr)
    if n_clips == 0:
        print(_dim("  没有片段达到评分阈值，可以试试 --min-score 0.5"), file=sys.stderr)
    print(_dim(f"输出目录 {summary['clips_dir']}"), file=sys.stderr)
    # stdout 只放项目 id，方便 shell 里接管道
    print(req.project_id)
    return 0


# ---------------------------------------------------------------- list / show ---
def cmd_list(args: argparse.Namespace) -> int:
    from backend.services.local_runner import list_projects

    items = list_projects(limit=args.limit)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    if not items:
        print(_dim("还没有项目。autoclip run <video> 开始。"))
        return 0
    for it in items:
        print(f"{it['project_id']}  {it['status']:<9} {it['clips']:>3} 切片  {it['updated_at'][:16]}  {it['name']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from backend.services.local_runner import summarize_project

    try:
        s = summarize_project(args.project_id)
    except FileNotFoundError as e:
        _err(str(e))
        return 2
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    print(_bold(s["name"]) + _dim(f"  {s['project_id']}"))
    print(_dim(f"{s['counts']['clips']} 切片 · {s['counts']['collections']} 合集 · {s['project_dir']}"))
    for c in s["clips"]:
        score = str(c["score_100"]) if c.get("score_100") is not None else "-"
        print(f"  {score:>4}  {c['start_time']} → {c['end_time']}  {c['title']}")
        if c.get("file"):
            print(_dim(f"        {c['file']}"))
    for col in s["collections"]:
        print(f"  合集  {col['title']}  {_dim('切片 ' + ', '.join(col['clip_ids']))}")
        if col.get("file"):
            print(_dim(f"        {col['file']}"))
    return 0


# ---------------------------------------------------------------- providers / doctor ---
def cmd_providers(args: argparse.Namespace) -> int:
    from backend.core.local_presets import LOCAL_PRESETS
    from backend.core.llm_manager import get_llm_manager

    rows = [
        ("dashscope", "阿里通义千问", "需要 key；国内直连，qwen-plus 性价比高"),
        ("openai", "OpenAI / 兼容接口", "需要 key；--base-url 可指向 DeepSeek / 智谱 / OpenRouter / vLLM"),
        ("gemini", "Google Gemini", "需要 key"),
        ("siliconflow", "硅基流动", "需要 key；DeepSeek / Qwen 开源模型"),
    ] + [
        (p.key, p.display_name, f"无需 key；默认 {p.base_url}" + (f"，默认模型 {p.default_model}" if p.default_model else ""))
        for p in LOCAL_PRESETS.values()
    ]
    info = get_llm_manager().get_current_provider_info()
    if args.json:
        print(json.dumps({"current": info, "providers": [dict(zip(("key", "name", "note"), r)) for r in rows]}, ensure_ascii=False, indent=2))
        return 0
    for key, name, note in rows:
        mark = "●" if key == info.get("provider") else " "
        print(f"{mark} {key:<12} {name:<18} {_dim(note)}")
    cur = f"{info.get('provider')} · {info.get('model')}" + (f" · {info['base_url']}" if info.get("base_url") else "")
    print(_dim(f"\n当前：{cur}  ({'可用' if info.get('available') else '未配置 key'})"))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from backend.services.local_runner import configure_llm, environment_report

    try:
        configure_llm(_llm_override(args))
    except Exception as e:  # noqa: BLE001
        _err(str(e))
    rep = environment_report()
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ffmpeg"]["ok"] and rep["llm"]["ok"] else 1

    def line(ok: Optional[bool], label: str, detail: str) -> None:
        mark = _c("32", "✓") if ok else _c("31", "✗")
        print(f"{mark} {label:<8} {detail}")

    print(_dim(f"数据目录 {rep['data_dir']} · Python {rep['python']}"))
    line(rep["ffmpeg"]["ok"], "ffmpeg", rep["ffmpeg"].get("path") or rep["ffmpeg"].get("error", ""))
    w = rep["whisper"]
    line(w["ok"], "whisper", ("faster-whisper 已安装" if w["ok"] else "未安装（无字幕的视频需要；桌面应用 设置 → 转写 一键安装）"))
    llm = rep["llm"]
    llm_desc = f"{llm.get('provider')} · {llm.get('model')}" + (f" · {llm['base_url']}" if llm.get("base_url") else "")
    line(llm["ok"], "模型", llm_desc + ("" if llm["ok"] else f"  {_dim(llm.get('error') or '')}"))
    return 0 if rep["ffmpeg"]["ok"] and llm["ok"] else 1


# ---------------------------------------------------------------- mcp ---
def cmd_mcp(args: argparse.Namespace) -> int:
    from backend.mcp_server import main as mcp_main

    return mcp_main()


# ---------------------------------------------------------------- parser ---
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autoclip",
        description="AutoClip 命令行：一条命令把长视频切成高光片段。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1] if __doc__ else None,
    )
    p.add_argument("--data-dir", help="数据目录（默认与桌面应用共用；也可用 AUTOCLIP_DATA_DIR）")
    p.add_argument("-v", "--verbose", action="store_true", help="在终端输出后端日志")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="处理一条视频，输出切片与合集")
    r.add_argument("video", help="视频文件路径")
    r.add_argument("--srt", help="已有字幕文件（没有则本地 Whisper 转写）")
    r.add_argument("--name", help="项目名（默认取文件名）")
    r.add_argument("--category", default="default",
                   choices=["default", "knowledge", "business", "opinion", "experience", "speech", "content_review", "entertainment"],
                   help="内容类型，影响提示词")
    r.add_argument("--min-score", type=float, help="最低评分阈值 0–1（默认 0.7；切片为 0 时调低）")
    r.add_argument("--copy", action="store_true", help="把视频复制进项目目录（默认硬链接，不占双份空间）")
    r.add_argument("--no-db", action="store_true", help="不写 SQLite（桌面应用里就看不到这个项目）")
    r.add_argument("--json", action="store_true", help="以 JSON 输出结果（给脚本 / agent 用）")
    _add_llm_args(r)
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("list", help="列出项目")
    l.add_argument("--limit", type=int, default=30)
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="查看一个项目的切片与文件路径")
    s.add_argument("project_id")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_show)

    pr = sub.add_parser("providers", help="列出可用的模型提供商与本地预设")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_providers)

    d = sub.add_parser("doctor", help="检查 ffmpeg / Whisper / 模型连接")
    d.add_argument("--json", action="store_true")
    _add_llm_args(d)
    d.set_defaults(func=cmd_doctor)

    m = sub.add_parser("mcp", help="以 MCP server（stdio）方式运行，供 Cursor / Claude 调用")
    m.set_defaults(func=cmd_mcp)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_environment(Path(args.data_dir) if args.data_dir else None)
    setup_logging(verbose=args.verbose)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        _err("已中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
