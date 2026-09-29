"""把 AutoClip 接入 opencode CLI（opencode.json 的 mcp 配置）。

opencode（https://opencode.ai）的本地 MCP server 写在配置文件的 mcp 段：

    {
      "mcp": {
        "autoclip": { "type": "local", "command": ["/abs/path/autoclip", "mcp"], "enabled": true }
      }
    }

- 全局配置：`~/.config/opencode/opencode.json`（`OPENCODE_CONFIG` / `XDG_CONFIG_HOME` 可改路径）
- 项目配置：`<项目>/opencode.json`；opencode 会合并多处配置，项目覆盖全局

对应 CLI：`autoclip mcp install opencode`（`--scope project` 写项目配置、`--print` 只打印片段）。
本模块只做配置读写与命令探测，不 import 后端重依赖，方便 CLI 与测试单独使用。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

OPENCODE_SCHEMA = "https://opencode.ai/config.json"
DEFAULT_SERVER_NAME = "autoclip"


def detect_server() -> Dict[str, Any]:
    """探测用什么命令启动 MCP server：PATH 里的 autoclip → autoclip-mcp → python -m backend.mcp_server。"""
    exe = shutil.which("autoclip")
    if exe:
        return {"command": [exe, "mcp"], "cwd": None, "environment": None, "kind": "autoclip"}
    exe = shutil.which("autoclip-mcp")
    if exe:
        return {"command": [exe], "cwd": None, "environment": None, "kind": "autoclip-mcp"}
    repo_root = Path(__file__).resolve().parents[2]
    env = {"PYTHONPATH": str(repo_root)}
    cwd = str(repo_root) if (repo_root / "backend" / "mcp_server.py").is_file() else None
    return {
        "command": [sys.executable or "python", "-m", "backend.mcp_server"],
        "cwd": cwd,
        "environment": env,
        "kind": "module",
    }


def opencode_config_path(scope: str = "global", project_dir: Optional[Path] = None) -> Path:
    """目标配置文件：global → ~/.config/opencode/opencode.json；project → <目录>/opencode.json。"""
    if scope == "project":
        base = Path(project_dir).expanduser() if project_dir else Path.cwd()
        return base / "opencode.json"
    override = os.environ.get("OPENCODE_CONFIG")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    config_home = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return config_home / "opencode" / "opencode.json"


def build_entry(server: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """opencode `mcp` 段里的 autoclip 条目（type=local）。"""
    server = server or detect_server()
    entry: Dict[str, Any] = {"type": "local", "command": list(server["command"]), "enabled": True}
    if server.get("cwd"):
        entry["cwd"] = server["cwd"]
    if server.get("environment"):
        entry["environment"] = dict(server["environment"])
    return entry


def render_snippet(entry: Dict[str, Any], name: str = DEFAULT_SERVER_NAME) -> str:
    """手动合并进 opencode 配置时用的 JSON 片段。"""
    return json.dumps({"mcp": {name: entry}}, ensure_ascii=False, indent=2)


def _strip_comments(text: str) -> str:
    """去掉 // 与 /* */ 注释；字符串（含转义）里的内容不动。"""
    out: List[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strip_trailing_commas(text: str) -> str:
    """去掉对象 / 数组结尾多余的逗号；字符串里的逗号不动。"""
    out: List[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_config_text(text: str) -> Tuple[Dict[str, Any], bool]:
    """解析 opencode 配置文本，返回 (data, 是否走了 JSONC 宽松模式)。

    先按严格 JSON 解析；失败再容忍注释与尾随逗号（opencode 官方支持 JSONC）。
    两种都失败时抛 json.JSONDecodeError。
    """
    try:
        data = json.loads(text)
        lenient = False
    except json.JSONDecodeError:
        data = json.loads(_strip_trailing_commas(_strip_comments(text)))
        lenient = True
    if not isinstance(data, dict):
        raise json.JSONDecodeError("opencode 配置顶层必须是 JSON 对象", text, 0)
    return data, lenient


def install_opencode(
    target: Path,
    *,
    server: Optional[Dict[str, Any]] = None,
    name: str = DEFAULT_SERVER_NAME,
    force: bool = False,
) -> Dict[str, Any]:
    """把 autoclip 写进 opencode 配置（合并写入，不动其它键）。

    返回报告：ok / action / path / entry / snippet / backup / warnings / error / hint。
    action 取值 created / updated / unchanged / manual；manual = 没有写文件，
    需要用户手动合并 snippet（配置解析失败，或带注释又没给 force）。
    """
    server = server or detect_server()
    entry = build_entry(server)
    report: Dict[str, Any] = {
        "ok": False,
        "action": "manual",
        "path": str(target),
        "entry": entry,
        "snippet": render_snippet(entry, name=name),
        "backup": None,
        "warnings": [],
        "error": None,
        "hint": None,
    }

    exists = target.is_file()
    data: Dict[str, Any] = {}
    lenient = False
    if exists:
        try:
            data, lenient = parse_config_text(target.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            report.update(error=f"现有配置无法解析：{e}", hint="为免误删，请手动把下面的片段合并进配置")
            return report
        if lenient and not force:
            report.update(
                error="现有配置带注释 / 尾随逗号（JSONC），重写会丢注释，没有动它",
                hint=f"确认可接受时重跑并加 --force（会先备份为 {target.name}.bak）",
            )
            return report

    mcp = data.get("mcp")
    if mcp is not None and not isinstance(mcp, dict):
        report.update(action="error", error="配置里的 mcp 字段不是对象，未改动", hint="请手动清理 mcp 字段后重试")
        return report
    mcp = dict(mcp or {})

    if exists and mcp.get(name) == entry:
        report.update(ok=True, action="unchanged")
        return report

    data.setdefault("$schema", OPENCODE_SCHEMA)
    mcp[name] = entry
    data["mcp"] = mcp

    backup: Optional[Path] = None
    if exists:
        backup = target.with_name(target.name + ".bak")
        shutil.copy2(target, backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if lenient:
        report["warnings"].append(f"原配置的注释 / 尾随逗号未保留，已重写为纯 JSON（备份：{backup}）")
    if target.name == "opencode.json" and (target.parent / "opencode.jsonc").is_file():
        report["warnings"].append("同目录还有 opencode.jsonc，建议只保留一份配置，避免改错文件")
    if server.get("kind") == "module":
        report["warnings"].append("PATH 里没有 autoclip 命令，已回退到 python -m backend.mcp_server（依赖 cwd / PYTHONPATH）")

    report.update(ok=True, action="updated" if exists else "created", backup=str(backup) if backup else None)
    return report


