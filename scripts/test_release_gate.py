#!/usr/bin/env python3
"""转正门禁的纯函数测试。不访问 GitHub。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_release_gate import evaluate, main  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V150 = ROOT / "docs" / "acceptance" / "v1.5.0.json"


def passing(**overrides) -> dict:
    record = {
        "kind": "regular",
        "windows_ui": True,
        "macos_ui": True,
        "captioned_path": True,
        "no_subtitle_path": True,
        "observation_hours": 24,
    }
    record.update(overrides)
    return record


def test_regular_release_needs_every_gate() -> None:
    assert evaluate(passing()) == []
    assert any("Windows" in item for item in evaluate(passing(windows_ui=False)))
    assert any("macOS" in item for item in evaluate(passing(macos_ui=False)))
    assert any("G2" in item for item in evaluate(passing(captioned_path=False)))
    assert any("G3" in item for item in evaluate(passing(no_subtitle_path=False)))
    assert any("24" in item for item in evaluate(passing(observation_hours=8)))


def test_hotfix_is_narrower() -> None:
    hotfix = passing(kind="hotfix", macos_ui=False, no_subtitle_path=False, observation_hours=4)
    assert evaluate(hotfix) == []
    assert evaluate(passing(kind="hotfix", windows_ui=False, macos_ui=False, observation_hours=4))
    assert any("4" in item for item in evaluate(passing(kind="hotfix", observation_hours=2)))


def test_v1_5_0_record_is_rejected() -> None:
    record = json.loads(V150.read_text(encoding="utf-8"))
    errors = evaluate(record)
    assert errors, "1.5.0 跳过了门禁，记录必须被拒绝"
    joined = " ".join(errors)
    assert "Windows" in joined
    assert "G3" in joined
    assert "24" in joined


def test_cli_reads_json_and_exits() -> None:
    assert main(["--from-json", str(V150)]) == 1
    assert main([
        "--kind", "regular",
        "--windows-ui", "true",
        "--macos-ui", "true",
        "--captioned-path", "true",
        "--no-subtitle-path", "true",
        "--observation-hours", "24",
    ]) == 0


def test_script_is_executable_as_file() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_gate.py"), "--from-json", str(V150)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "不能转正" in proc.stdout + proc.stderr


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok {test.__name__}")
    print(f"{len(tests)} passed")
