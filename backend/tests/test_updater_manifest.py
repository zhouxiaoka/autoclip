"""Tauri updater latest.json 生成。"""
import importlib.util
import json
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


def test_build_manifest_strips_v_prefix():
    payload = _mod.build_manifest(
        version="v1.2.2",
        notes="hello",
        pub_date="2026-09-07T00:00:00Z",
        platforms={"darwin-aarch64": {"signature": "sig", "url": "https://example.com/a"}},
    )
    assert payload["version"] == "1.2.2"
    assert json.loads(json.dumps(payload))["version"] == "1.2.2"
