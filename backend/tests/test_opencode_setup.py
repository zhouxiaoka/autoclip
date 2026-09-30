"""opencode 接入：配置路径 / 合并写入 / JSONC 与失败保护。全部落在 tmp_path，不碰真实用户配置。"""
import json
import os
import subprocess
import sys

import pytest

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


def test_reinstall_preserves_custom_entry_fields(tmp_path):
    """[review P2] 重装只更新安装器负责的字段，用户自定义的 environment / timeout 不能丢。"""
    target = tmp_path / "opencode.json"
    existing = {
        "$schema": opencode_setup.OPENCODE_SCHEMA,
        "mcp": {
            "autoclip": {
                "type": "local",
                "command": ["/old/venv/bin/autoclip", "mcp"],
                "enabled": True,
                "environment": {"AUTOCLIP_DATA_DIR": "D:/clips", "OPENAI_API_KEY": "sk-x"},
                "timeout": 30000,
            }
        },
    }
    target.write_text(json.dumps(existing), encoding="utf-8")

    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is True and report["action"] == "updated"
    entry = json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]
    assert entry["command"] == SERVER["command"]                      # 命令更新
    assert entry["timeout"] == 30000                                  # 用户字段保留
    assert entry["environment"] == {"AUTOCLIP_DATA_DIR": "D:/clips", "OPENAI_API_KEY": "sk-x"}


def test_module_fallback_merges_environment(tmp_path, monkeypatch):
    """[review P2] 模块回退写 PYTHONPATH 时要合并 environment，而不是整体覆盖。"""
    monkeypatch.setattr(opencode_setup.shutil, "which", lambda name: None)
    server = opencode_setup.detect_server()
    target = tmp_path / "opencode.json"
    existing = {"mcp": {"autoclip": {
        "type": "local", "command": ["python", "-m", "backend.mcp_server"],
        "enabled": True, "environment": {"OPENAI_API_KEY": "sk-x"},
    }}}
    target.write_text(json.dumps(existing), encoding="utf-8")

    report = opencode_setup.install_opencode(target, server=server)
    assert report["ok"] is True
    env = json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]["environment"]
    assert env["OPENAI_API_KEY"] == "sk-x"                            # 用户环境变量保留
    assert env["PYTHONPATH"]                                          # 回退所需的 PYTHONPATH 合并进来


def test_disabled_entry_stays_disabled_with_warning(tmp_path):
    target = tmp_path / "opencode.json"
    target.write_text(json.dumps({"mcp": {"autoclip": {
        "type": "local", "command": ["/old/venv/bin/autoclip", "mcp"], "enabled": False,
    }}}), encoding="utf-8")

    report = opencode_setup.install_opencode(target, server=SERVER)
    entry = json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]
    assert entry["enabled"] is False                                  # 不静默改用户的 enabled
    assert any("enabled=false" in w for w in report["warnings"])


def test_existing_jsonc_is_used_when_json_missing(tmp_path):
    """[review P2] 只有 opencode.jsonc 时直接写它；注释沿用非 --force 保护，不再多建一份不生效的 json。"""
    jsonc = tmp_path / "opencode.jsonc"
    jsonc.write_text('{\n  // opencode 支持注释\n  "mcp": {}\n}\n', encoding="utf-8")

    report = opencode_setup.install_opencode(tmp_path / "opencode.json", server=SERVER)
    assert report["ok"] is False and report["action"] == "manual"     # JSONC 默认不动

    report = opencode_setup.install_opencode(tmp_path / "opencode.json", server=SERVER, force=True)
    assert report["ok"] is True and report["action"] == "updated"
    assert report["path"].endswith("opencode.jsonc")
    data = json.loads(jsonc.read_text(encoding="utf-8"))
    assert data["mcp"]["autoclip"]["command"] == SERVER["command"]
    assert (tmp_path / "opencode.jsonc.bak").is_file()
    assert not (tmp_path / "opencode.json").exists()


def test_plain_jsonc_only_is_targeted(tmp_path):
    jsonc = tmp_path / "opencode.jsonc"
    jsonc.write_text('{"model": "anthropic/claude-sonnet-4-5"}', encoding="utf-8")

    report = opencode_setup.install_opencode(tmp_path / "opencode.json", server=SERVER)
    assert report["ok"] is True and report["action"] == "updated"
    assert report["path"].endswith("opencode.jsonc")
    assert json.loads(jsonc.read_text(encoding="utf-8"))["mcp"]["autoclip"]["enabled"] is True
    assert not (tmp_path / "opencode.json").exists()


def test_conflicting_jsonc_with_mcp_blocks_write(tmp_path):
    """[review P2] 两份配置都有且 jsonc 含 mcp 段时必须明确拒绝，不能报告成功但加载旧配置。"""
    json_file = tmp_path / "opencode.json"
    original = {"$schema": opencode_setup.OPENCODE_SCHEMA, "model": "x"}
    json_file.write_text(json.dumps(original), encoding="utf-8")
    (tmp_path / "opencode.jsonc").write_text(
        '{"mcp": {"autoclip": {"type": "local", "command": ["old"], "enabled": false}}}', encoding="utf-8")

    report = opencode_setup.install_opencode(json_file, server=SERVER)
    assert report["ok"] is False and report["action"] == "manual"
    assert "jsonc" in report["error"]
    assert json.loads(json_file.read_text(encoding="utf-8")) == original   # json 未被写
    assert report["snippet"]


def test_both_exist_jsonc_without_mcp_writes_json(tmp_path):
    json_file = tmp_path / "opencode.json"
    json_file.write_text(json.dumps({"model": "x"}), encoding="utf-8")
    jsonc = tmp_path / "opencode.jsonc"
    jsonc.write_text('{"theme": "dark"}', encoding="utf-8")

    report = opencode_setup.install_opencode(json_file, server=SERVER)
    assert report["ok"] is True and report["action"] == "updated"
    assert report["path"].endswith("opencode.json")
    assert json.loads(json_file.read_text(encoding="utf-8"))["mcp"]["autoclip"]["enabled"] is True
    assert json.loads(jsonc.read_text(encoding="utf-8")) == {"theme": "dark"}   # jsonc 未被改动


def test_utf8_bom_jsonc_conflict_still_detected(tmp_path):
    """Windows 编辑器常带 UTF-8 BOM，解析要容错，冲突判定不能因此失效。"""
    json_file = tmp_path / "opencode.json"
    json_file.write_text(json.dumps({"model": "x"}), encoding="utf-8")
    (tmp_path / "opencode.jsonc").write_text(
        '{"mcp": {"autoclip": {"type": "local", "command": ["old"], "enabled": false}}}', encoding="utf-8-sig")

    report = opencode_setup.install_opencode(json_file, server=SERVER)
    assert report["ok"] is False and report["action"] == "manual"
    assert "jsonc" in report["error"]


def test_utf8_bom_json_can_be_merged(tmp_path):
    target = tmp_path / "opencode.json"
    target.write_text(json.dumps({"model": "x"}), encoding="utf-8-sig")

    report = opencode_setup.install_opencode(target, server=SERVER)
    assert report["ok"] is True and report["action"] == "updated"
    assert json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]["enabled"] is True


@pytest.mark.parametrize("config_exists", [False, True])
def test_cli_explicit_config_does_not_discover_sibling_jsonc(tmp_path, monkeypatch, capsys, config_exists):
    from backend import cli

    target = tmp_path / "custom" / "opencode.json"
    target.parent.mkdir()
    if config_exists:
        target.write_text(json.dumps({"model": "original"}), encoding="utf-8")
    sibling = target.with_suffix(".jsonc")
    original_sibling = '{"mcp": {"other": {"type": "remote", "url": "https://example.com/mcp"}}}'
    sibling.write_text(original_sibling, encoding="utf-8")
    monkeypatch.setenv("OPENCODE_CONFIG", str(target))
    monkeypatch.setattr(opencode_setup, "detect_server", lambda: SERVER)

    args = cli.build_parser().parse_args(["mcp", "install", "opencode", "--json"])
    assert cli.cmd_mcp_install(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == str(target)
    assert report["action"] == ("updated" if config_exists else "created")
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["mcp"]["autoclip"]["command"] == SERVER["command"]
    if config_exists:
        assert data["model"] == "original"
    assert sibling.read_text(encoding="utf-8") == original_sibling


def test_cli_project_scope_discovers_jsonc_with_global_override(tmp_path, monkeypatch, capsys):
    from backend import cli

    global_config = tmp_path / "global" / "opencode.json"
    monkeypatch.setenv("OPENCODE_CONFIG", str(global_config))
    monkeypatch.setattr(opencode_setup, "detect_server", lambda: SERVER)
    project = tmp_path / "project"
    project.mkdir()
    jsonc = project / "opencode.jsonc"
    jsonc.write_text('{"mcp": {}}', encoding="utf-8")

    args = cli.build_parser().parse_args([
        "mcp", "install", "opencode", "--scope", "project", "--dir", str(project), "--json",
    ])
    assert cli.cmd_mcp_install(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["path"] == str(jsonc)
    assert json.loads(jsonc.read_text(encoding="utf-8"))["mcp"]["autoclip"]["command"] == SERVER["command"]
    assert not (project / "opencode.json").exists()
    assert not global_config.exists()


def test_module_reinstall_refreshes_paths_after_checkout_move(tmp_path):
    old_repo = tmp_path / "old-checkout"
    backend = old_repo / "backend"
    backend.mkdir(parents=True)
    (backend / "__init__.py").write_text("", encoding="utf-8")
    (backend / "mcp_server.py").write_text('print("current-checkout")\n', encoding="utf-8")
    extra_modules = tmp_path / "custom-modules"
    extra_modules.mkdir()
    target = tmp_path / "opencode.json"
    old_server = {
        "kind": "module", "command": [sys.executable, "-m", "backend.mcp_server"],
        "cwd": str(old_repo), "environment": {"PYTHONPATH": str(old_repo)},
    }
    assert opencode_setup.install_opencode(target, server=old_server)["ok"] is True
    data = json.loads(target.read_text(encoding="utf-8"))
    data["mcp"]["autoclip"]["environment"].update({
        "PYTHONPATH": os.pathsep.join([str(old_repo), str(extra_modules)]),
        "AUTOCLIP_DATA_DIR": str(tmp_path / "clips"),
    })
    target.write_text(json.dumps(data), encoding="utf-8")

    new_repo = tmp_path / "new-checkout"
    old_repo.rename(new_repo)
    new_server = dict(old_server, cwd=str(new_repo), environment={"PYTHONPATH": str(new_repo)})
    report = opencode_setup.install_opencode(target, server=new_server)
    assert report["ok"] is True and report["action"] == "updated"
    entry = json.loads(target.read_text(encoding="utf-8"))["mcp"]["autoclip"]
    assert entry["cwd"] == str(new_repo)
    paths = entry["environment"]["PYTHONPATH"].split(os.pathsep)
    assert paths[0] == str(new_repo)
    assert str(extra_modules) in paths
    assert entry["environment"]["AUTOCLIP_DATA_DIR"] == str(tmp_path / "clips")
    process = subprocess.run(
        entry["command"], cwd=entry["cwd"], env=dict(os.environ, **entry["environment"]),
        capture_output=True, text=True, timeout=10,
    )
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "current-checkout"
    assert opencode_setup.install_opencode(target, server=new_server)["action"] == "unchanged"
