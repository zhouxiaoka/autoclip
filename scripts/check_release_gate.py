#!/usr/bin/env python3
"""Decide whether a pre-release may become latest.

Regular releases need both platform UIs, the captioned path, the no-subtitle
path, and 24 hours of observation. Hotfixes may skip the unaffected platform
and the no-subtitle path, and may observe for 4 hours. There is no
"ship now" override.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REGULAR_HOURS = 24
HOTFIX_HOURS = 4


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    raise ValueError(f"无法解析布尔值: {value!r}")


def parse_hours(value: object) -> float:
    try:
        hours = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"观察小时数无效: {value!r}") from exc
    if hours < 0:
        raise ValueError("观察小时数不能为负")
    return hours


def evaluate(record: dict) -> list[str]:
    """Return human-readable failures. An empty list means the gate passes."""
    kind = str(record.get("kind") or "regular").strip().lower()
    if kind not in {"regular", "hotfix"}:
        return [f"kind 只能是 regular 或 hotfix，收到 {kind!r}"]

    try:
        windows_ui = parse_bool(record.get("windows_ui"))
        macos_ui = parse_bool(record.get("macos_ui"))
        captioned = parse_bool(record.get("captioned_path"))
        no_subtitle = parse_bool(record.get("no_subtitle_path"))
        hours = parse_hours(record.get("observation_hours", 0))
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    if not captioned:
        errors.append("有字幕出片（G2）未在安装包上通过")

    if kind == "hotfix":
        if not windows_ui and not macos_ui:
            errors.append("热修至少要在一个受影响平台上做完界面冒烟")
        if hours < HOTFIX_HOURS:
            errors.append(f"热修观察期至少 {HOTFIX_HOURS} 小时，当前 {hours:g}")
        return errors

    if not windows_ui:
        errors.append("Windows 界面冒烟未通过；没有真机就用虚拟机，不能用 CI 无界面冒烟代替")
    if not macos_ui:
        errors.append("macOS 界面冒烟未通过")
    if not no_subtitle:
        errors.append("无字幕转写（G3）未在安装包上通过")
    if hours < REGULAR_HOURS:
        errors.append(f"常规版观察期至少 {REGULAR_HOURS} 小时，当前 {hours:g}")
    return errors


def load_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_record(args: argparse.Namespace) -> dict:
    overlays = {
        "kind": args.kind,
        "windows_ui": args.windows_ui,
        "macos_ui": args.macos_ui,
        "captioned_path": args.captioned_path,
        "no_subtitle_path": args.no_subtitle_path,
        "observation_hours": args.observation_hours,
    }
    if args.from_json:
        record = load_record(args.from_json)
        for key, value in overlays.items():
            if value is not None:
                record[key] = value
        return record
    record = {key: value for key, value in overlays.items() if value is not None}
    record.setdefault("kind", "regular")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发版转正门禁")
    parser.add_argument("--from-json", type=Path, help="读取 docs/acceptance/vX.Y.Z.json")
    parser.add_argument("--kind", choices=("regular", "hotfix"))
    parser.add_argument("--windows-ui")
    parser.add_argument("--macos-ui")
    parser.add_argument("--captioned-path")
    parser.add_argument("--no-subtitle-path")
    parser.add_argument("--observation-hours")
    args = parser.parse_args(argv)

    if args.from_json is None and all(
        value is None
        for value in (
            args.kind,
            args.windows_ui,
            args.macos_ui,
            args.captioned_path,
            args.no_subtitle_path,
            args.observation_hours,
        )
    ):
        parser.error("请提供 --from-json 或门禁参数")

    try:
        record = build_record(args)
        errors = evaluate(record)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    version = record.get("version") or "unspecified"
    if errors:
        print(f"::error::{version} 不能转正：")
        for item in errors:
            print(f"::error::{item}")
        return 1

    print(f"{version} 通过转正门禁（{record.get('kind', 'regular')}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
