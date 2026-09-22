#!/usr/bin/env python3
"""
autoclip — 命令行出片。

    autoclip run video.mp4                         # 用桌面应用里配好的模型
    autoclip run video.mp4 --provider ollama       # 本地 Ollama（默认 qwen2.5:7b，无需 key）
    autoclip run video.mp4 --provider lmstudio --model qwen2.5-7b-instruct
    autoclip run video.mp4 --provider openai --base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key sk-...
    autoclip run video.mp4 --srt video.srt --min-score 0.6 --json
    autoclip list / show <project_id> / providers / doctor
    autoclip publish <project_id> --clip 2 --platform tiktok --platform youtube   # 经 Upload-Post 发到海外平台

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
    g.add_argument("--provider", choices=PROVIDER_CHOICES, help="dashscope / openai / gemini / deepseek / kimi / glm / grok，或本地预设 ollama / lmstudio")
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
        ("deepseek", "DeepSeek", "需要 key；官方接口，deepseek-flash"),
        ("kimi", "Kimi（月之暗面）", "需要 key；国内直连"),
        ("glm", "智谱 GLM", "需要 key；国内直连"),
        ("grok", "Grok（xAI）", "需要 key"),
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


# ---------------------------------------------------------------- export ---
def cmd_export(args: argparse.Namespace) -> int:
    from backend.services.publish_export import ExportRequest, export_clip, list_presets, load_clip_meta
    from backend.services.local_runner import summarize_project

    if args.list_presets:
        rows = list_presets()
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for p in rows:
                print(f"{p['key']:<14} {p['label']:<16} {p.get('w') or '-'}x{p.get('h') or '-'}  {p.get('layout')}")
        return 0

    clip_ids = list(args.clip or [])
    if not clip_ids:
        try:
            summary = summarize_project(args.project_id)
        except FileNotFoundError as e:
            _err(str(e))
            return 2
        clip_ids = [c["id"] for c in summary["clips"]]
        if not clip_ids:
            _err("这个项目没有切片")
            return 2

    results = []
    for cid in clip_ids:
        try:
            load_clip_meta(args.project_id, cid)
            r = export_clip(ExportRequest(
                project_id=args.project_id, clip_id=cid, preset=args.preset,
                subtitles=not args.no_subtitles, title_card=not args.no_title,
            ))
            results.append(r)
            if not args.json:
                print(f"{'cached' if r.get('cached') else 'ok':<8} {cid}  {r.get('path')}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "clip_id": cid, "error": str(e)[:400]})
            _err(f"{cid}: {e}")

    if args.json:
        print(json.dumps({"ok": all(r.get("ok") for r in results), "exports": results}, ensure_ascii=False, indent=2))
    return 0 if all(r.get("ok") for r in results) else 1


# ---------------------------------------------------------------- publish ---
def _print_publish_status(st: Dict[str, Any]) -> None:
    print(f"{st.get('status')}  {st.get('completed') or 0}/{st.get('total') or '?'}  {_dim(st.get('request_id') or st.get('job_id') or '')}", file=sys.stderr)
    for r in st.get("results") or []:
        if r.get("skipped"):
            mark, detail = _dim("-"), "profile 没连这个平台，跳过"
        elif r.get("success"):
            mark, detail = _c("32", "✓"), r.get("url") or r.get("message") or ""
            if r.get("fallback_to_inbox"):
                detail += "  （已进 TikTok 收件箱草稿，需在 App 里发布）"
        else:
            mark, detail = _c("31", "✗"), r.get("error") or r.get("message") or r.get("status") or ""
        print(f"  {mark} {r.get('platform', ''):<12} {detail}", file=sys.stderr)


def cmd_publish(args: argparse.Namespace) -> int:
    from backend.services import upload_post_publisher as up

    # 保存配置
    if args.save:
        if not (args.api_key or args.user):
            _err("--save 需要配合 --api-key 和/或 --user")
            return 2
        if args.api_key:
            try:
                acct = up.verify_api_key(up.UploadPostConfig(api_key=args.api_key, base_url=up.load_config().base_url))
            except up.UploadPostError as e:
                _err(str(e))
                return 2
            print(_dim(f"API Key 有效：{acct.get('email')} · {acct.get('plan')}"), file=sys.stderr)
        cfg = up.save_config(api_key=args.api_key, user=args.user)
        print(f"已保存到 {up.config_path()}  key={cfg.masked_key()} user={cfg.user or '-'}", file=sys.stderr)
        if cfg.source == "env":
            print(_dim("注意：当前环境变量 UPLOAD_POST_API_KEY 优先于文件"), file=sys.stderr)
        return 0

    cfg = up.load_config()
    if args.api_key:
        cfg = up.UploadPostConfig(api_key=args.api_key, user=args.user or cfg.user, base_url=cfg.base_url, source="cli")

    if args.list_profiles:
        try:
            profiles = up.list_profiles(cfg)
        except up.UploadPostError as e:
            _err(str(e))
            return 2
        if args.json:
            print(json.dumps(profiles, ensure_ascii=False, indent=2))
            return 0
        if not profiles:
            print(_dim("这个 API Key 下还没有 profile。到 https://app.upload-post.com/manage-users 创建并连接账号。"))
        for pr in profiles:
            mark = "●" if pr["username"] == cfg.user else " "
            connected = ", ".join(pr["connected_platforms"]) or "未连接任何平台"
            reconnect = ", ".join(pr.get("reconnect_platforms") or [])
            extra = f"  （需重连: {reconnect}）" if reconnect else ""
            print(f"{mark} {pr['username']:<24} {_dim(connected + extra)}")
        return 0

    if args.status:
        try:
            st = up.wait_for_status(args.status, config=cfg, project_id=args.project_id,
                                    on_update=None if args.json else _print_publish_status) if args.wait \
                else up.get_status(args.status, config=cfg, project_id=args.project_id)
        except up.UploadPostError as e:
            _err(str(e))
            return 2
        if args.json:
            print(json.dumps(st, ensure_ascii=False, indent=2))
        elif not args.wait:
            _print_publish_status(st)
        return 0 if st.get("status") not in ("failed", "not_found") else 1

    if not args.project_id:
        _err("需要 project_id（或 --list-profiles / --status）")
        return 2
    if not args.platform:
        _err("至少一个 --platform，如 --platform tiktok --platform youtube")
        return 2
    try:
        platforms = up.normalize_platforms(args.platform)
    except ValueError as e:
        _err(str(e))
        return 2

    clip_ids = list(args.clip or [])
    if not clip_ids:
        from backend.services.local_runner import summarize_project
        try:
            summary = summarize_project(args.project_id)
        except FileNotFoundError as e:
            _err(str(e))
            return 2
        clip_ids = [c["id"] for c in summary["clips"]]
        if not clip_ids:
            _err("这个项目没有切片")
            return 2
        if len(clip_ids) > 1 and not args.yes:
            _err(f"没指定 --clip，将把 {len(clip_ids)} 条切片全部发到 {', '.join(platforms)}；确认请加 --yes")
            return 2

    extra: Dict[str, Any] = {}
    for kv in args.extra or []:
        if "=" not in kv:
            _err(f"--extra 格式应为 key=value: {kv}")
            return 2
        k, v = kv.split("=", 1)
        extra[k.strip()] = v.strip()

    results = []
    for cid in clip_ids:
        req = up.PublishRequest(
            project_id=args.project_id, clip_id=cid, platforms=platforms, user=args.user, preset=args.preset,
            title=args.title, description=args.description, subtitles=not args.no_subtitles,
            title_card=not args.no_title, scheduled_date=args.schedule, timezone=args.timezone, extra=extra,
        )
        try:
            r = up.publish_clip(req, config=cfg)
            results.append(r)
            if not args.json:
                print(f"{_c('32', 'submitted')} {cid}  {r['title']}  {_dim(r['request_id'])}", file=sys.stderr)
                for w in r.get("export_warnings") or []:
                    print(_dim(f"         {w}"), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            results.append({"ok": False, "clip_id": cid, "error": str(e)[:400]})
            _err(f"{cid}: {e}")

    if args.wait:
        for r in results:
            if not r.get("ok"):
                continue
            st = up.wait_for_status(r["request_id"], timeout_sec=args.timeout, config=cfg, project_id=args.project_id)
            r["status"] = st.get("status")
            r["results"] = st.get("results")
            r["ok"] = st.get("status") != "failed"
            if not args.json:
                print(_bold(f"{r['clip_id']}  {r['title']}"), file=sys.stderr)
                _print_publish_status(st)

    if args.json:
        print(json.dumps({"ok": all(r.get("ok") for r in results), "published": results}, ensure_ascii=False, indent=2))
    elif not args.wait:
        print(_dim("查看结果：autoclip publish --status <request_id>（加 --wait 可等到终态）"), file=sys.stderr)
    return 0 if all(r.get("ok") for r in results) else 1


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

    e = sub.add_parser("export", help="把切片渲成可发布成片（9:16 / 烧字幕 / 标题卡）")
    e.add_argument("project_id")
    e.add_argument("--preset", default="douyin", choices=["douyin", "xiaohongshu", "shorts", "bilibili", "original"])
    e.add_argument("--clip", action="append", help="切片 id，可重复；不填则导出全部")
    e.add_argument("--no-subtitles", action="store_true")
    e.add_argument("--no-title", action="store_true")
    e.add_argument("--list-presets", action="store_true")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_export)

    pu = sub.add_parser("publish", help="经 Upload-Post 把切片发到 TikTok / Instagram / YouTube Shorts / X 等海外平台")
    pu.add_argument("project_id", nargs="?")
    pu.add_argument("--clip", action="append", help="切片 id，可重复；不填则全部（需 --yes）")
    pu.add_argument("--platform", action="append", help="平台，可重复或逗号分隔：tiktok, instagram, youtube, facebook, linkedin, x, threads, pinterest, bluesky …")
    pu.add_argument("--user", help="Upload-Post profile（默认用已保存的）")
    pu.add_argument("--preset", choices=["douyin", "xiaohongshu", "shorts", "bilibili", "original"],
                    help="发布导出预设；不填按平台自动选（竖屏平台 shorts，否则 original）")
    pu.add_argument("--title", help="标题（默认切片标题）")
    pu.add_argument("--description", help="描述（YouTube / LinkedIn / Facebook / Pinterest）")
    pu.add_argument("--no-subtitles", action="store_true")
    pu.add_argument("--no-title", action="store_true", help="不加标题卡")
    pu.add_argument("--schedule", help="定时发布，ISO-8601，如 2026-10-01T09:00:00")
    pu.add_argument("--timezone", help="IANA 时区，配合 --schedule，如 Asia/Shanghai")
    pu.add_argument("--extra", action="append", metavar="KEY=VALUE",
                    help="平台专属字段透传，如 privacy_level=SELF_ONLY、privacyStatus=unlisted、facebook_page_id=…")
    pu.add_argument("--wait", action="store_true", help="提交后等到各平台出结果")
    pu.add_argument("--timeout", type=float, default=600, help="--wait 的最长等待秒数")
    pu.add_argument("--yes", action="store_true", help="不指定 --clip 时确认发全部切片")
    pu.add_argument("--api-key", help="临时指定 API Key（配合 --save 可保存）")
    pu.add_argument("--save", action="store_true", help="把 --api-key / --user 保存到数据目录的 upload_post.json")
    pu.add_argument("--list-profiles", action="store_true", help="列出 API Key 下的 profile 和已连接平台")
    pu.add_argument("--status", metavar="REQUEST_ID", help="查询一次发布的各平台结果")
    pu.add_argument("--json", action="store_true")
    pu.set_defaults(func=cmd_publish)
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
