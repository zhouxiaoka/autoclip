"""Tauri updater latest.json 生成。"""
import importlib.util
import json
import re
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "write_updater_manifest.py"
_SPEC = importlib.util.spec_from_file_location("write_updater_manifest", _SCRIPT)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_mod)


def test_github_asset_url_replaces_spaces():
    url = _mod.github_asset_url("zhouxiaoka/autoclip", "v1.2.2", "AutoClip Desktop_1.2.2_x64-setup.exe")
    assert url.endswith("/AutoClip.Desktop_1.2.2_x64-setup.exe")
    assert " " not in url


def test_collect_platforms_skips_unsigned(tmp_path: Path):
    artifact = tmp_path / "AutoClip.Desktop_1.2.2_aarch64.app.tar.gz"
    artifact.write_bytes(b"app")
    platforms = _mod.collect_platforms(
        repo="zhouxiaoka/autoclip",
        tag="v1.2.2",
        artifacts={"darwin-aarch64": artifact, "windows-x86_64": None},
    )
    assert platforms == {}


def test_collect_platforms_includes_signed(tmp_path: Path):
    artifact = tmp_path / "AutoClip.Desktop_1.2.2_aarch64.app.tar.gz"
    artifact.write_bytes(b"app")
    Path(str(artifact) + ".sig").write_text("minisign-signature\n", encoding="utf-8")
    platforms = _mod.collect_platforms(
        repo="zhouxiaoka/autoclip",
        tag="v1.2.2",
        artifacts={"darwin-aarch64": artifact},
    )
    assert platforms["darwin-aarch64"]["signature"] == "minisign-signature"
    assert platforms["darwin-aarch64"]["url"].endswith(
        "/releases/download/v1.2.2/AutoClip.Desktop_1.2.2_aarch64.app.tar.gz"
    )


def _notes_before_highlights(version: str, changelog: Path, limit: int = 1200) -> str:
    """2026-10-21 之前的截取：版本段全文，超过 limit 时在字符处截断。"""
    text = changelog.read_text(encoding="utf-8")
    ver = version.lstrip("v")
    match = re.search(
        rf"^## \[{re.escape(ver)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return ""
    body = match.group(1).strip()
    if len(body) <= limit:
        return body
    return body[:limit].rstrip() + "…"


def test_changelog_notes_uses_only_highlights(tmp_path: Path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text(
        "## [1.5.7] - 2026-10-21\n\n"
        "### 要点\n\n"
        "给用户看的说明。\n\n"
        "- 第一条\n"
        "- 第二条\n\n"
        "### 详细改动\n\n"
        "- 工程细节 llm_auth_invalid\n\n"
        "## [1.5.6] - 2026-10-01\n\n"
        "- 旧版本\n",
        encoding="utf-8",
    )
    notes = _mod.changelog_notes("1.5.7", log)
    assert notes == "给用户看的说明。\n\n- 第一条\n- 第二条"
    assert "### 要点" not in notes
    assert "llm_auth_invalid" not in notes
    assert "旧版本" not in notes


def test_changelog_notes_without_highlights_matches_the_old_window(tmp_path: Path):
    body = "- 旧行为 " + ("甲" * 2000)
    log = tmp_path / "CHANGELOG.md"
    log.write_text(
        "## [1.5.7] - 2026-10-21\n\n"
        f"{body}\n\n"
        "## [1.5.6] - 2026-10-01\n\n"
        "- 下一段\n",
        encoding="utf-8",
    )
    notes = _mod.changelog_notes("v1.5.7", log)
    assert notes == _notes_before_highlights("v1.5.7", log)
    assert notes == body[:1200].rstrip() + "…"
    assert "下一段" not in notes


def test_changelog_notes_caps_a_long_highlights_block(tmp_path: Path):
    highlights = "测" * 1500
    log = tmp_path / "CHANGELOG.md"
    log.write_text(
        "## [1.5.7] - 2026-10-21\n\n"
        "### 要点\n\n"
        f"{highlights}\n\n"
        "### 详细改动\n\n"
        "- 不要出现\n",
        encoding="utf-8",
    )
    notes = _mod.changelog_notes("1.5.7", log)
    assert notes == ("测" * 1200) + "…"
    assert len(notes) == 1201
    assert "不要出现" not in notes
    assert "### 要点" not in notes


def test_changelog_notes_uses_only_that_version(tmp_path: Path):
    log = tmp_path / "CHANGELOG.md"
    log.write_text(
        "## [1.4.0] - 2026-09-22\n\n- 应用内更新提示\n\n## [1.3.1] - 2026-09-21\n\n- 旧版本\n",
        encoding="utf-8",
    )
    notes = _mod.changelog_notes("v1.4.0", log)
    assert "应用内更新提示" in notes
    assert "旧版本" not in notes
    assert _mod.changelog_notes("9.9.9", log) == ""


def test_build_manifest_strips_v_prefix():
    payload = _mod.build_manifest(
        version="v1.2.2",
        notes="hello",
        pub_date="2026-09-07T00:00:00Z",
        platforms={"darwin-aarch64": {"signature": "sig", "url": "https://example.com/a"}},
    )
    assert payload["version"] == "1.2.2"
    assert json.loads(json.dumps(payload))["version"] == "1.2.2"
