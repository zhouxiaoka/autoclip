"""opencode 接入：配置路径 / 合并写入 / JSONC 与失败保护。全部落在 tmp_path，不碰真实用户配置。"""
import json

from backend.services import opencode_setup

SERVER = {"command": ["/opt/venv/bin/autoclip", "mcp"], "cwd": None, "environment": None, "kind": "autoclip"}


def test_global_path_respects_xdg_and_opencode_config(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert opencode_setup.opencode_config_path("global") == tmp_path / "opencode" / "opencode.json"

    custom = tmp_path / "custom-opencode.json"
    monkeypatch.setenv("OPENCODE_CONFIG", str(custom))
    assert opencode_setup.opencode_config_path("global") == custom


def test_creates_new_config(tmp_path):
    target = tmp_path / "opencode.json"
    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is True
    assert report["action"] == "created"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["$schema"] == opencode_setup.OPENCODE_SCHEMA
    assert data["mcp"]["autoclip"] == {
        "type": "local",
        "command": ["/opt/venv/bin/autoclip", "mcp"],
        "enabled": True,
    }


def test_merge_preserves_other_keys_and_backs_up(tmp_path):
    target = tmp_path / "opencode.json"
    original = {
        "$schema": opencode_setup.OPENCODE_SCHEMA,
        "model": "anthropic/claude-sonnet-4-5",
        "mcp": {"other": {"type": "remote", "url": "https://example.com/mcp"}},
    }
    target.write_text(json.dumps(original, indent=2), encoding="utf-8")

    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is True and report["action"] == "updated"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["model"] == "anthropic/claude-sonnet-4-5"
    assert data["mcp"]["other"] == original["mcp"]["other"]
    assert data["mcp"]["autoclip"]["command"] == SERVER["command"]
    assert json.loads((tmp_path / "opencode.json.bak").read_text(encoding="utf-8")) == original


def test_second_run_unchanged(tmp_path):
    target = tmp_path / "opencode.json"
    assert opencode_setup.install_opencode(target, server=SERVER)["action"] == "created"
    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is True and report["action"] == "unchanged"


def test_jsonc_config_not_touched_without_force(tmp_path):
    target = tmp_path / "opencode.json"
    original = '{\n  // opencode 支持注释\n  "mcp": {},\n}\n'
    target.write_text(original, encoding="utf-8")

    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is False and report["action"] == "manual"
    assert target.read_text(encoding="utf-8") == original

    report = opencode_setup.install_opencode(target, server=SERVER, force=True)
    assert report["ok"] is True and report["action"] == "updated"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcp"]["autoclip"]["enabled"] is True
    assert (tmp_path / "opencode.json.bak").is_file()
    assert any("注释" in w for w in report["warnings"])


def test_broken_config_never_overwritten(tmp_path):
    target = tmp_path / "opencode.json"
    target.write_text("{不是 JSON", encoding="utf-8")
    report = opencode_setup.install_opencode(target, server=SERVER, force=True)
    assert report["ok"] is False and report["action"] == "manual"
    assert target.read_text(encoding="utf-8") == "{不是 JSON"
    assert not (tmp_path / "opencode.json.bak").exists()


def test_project_scope_and_module_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(opencode_setup.shutil, "which", lambda name: None)
    server = opencode_setup.detect_server()
    assert server["kind"] == "module"
    assert server["command"][1:] == ["-m", "backend.mcp_server"]
    assert server["environment"]["PYTHONPATH"]

    target = opencode_setup.opencode_config_path("project", tmp_path)
    assert target == tmp_path / "opencode.json"
    report = opencode_setup.install_opencode(target, server=server)
    assert report["ok"] is True
    entry = json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]
    assert entry["cwd"]
    assert entry["environment"]["PYTHONPATH"]
    assert any("回退" in w for w in report["warnings"])
