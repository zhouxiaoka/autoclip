"""P12: backend/presets/provider_presets.json is the only product catalog."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from backend.core import cloud_presets, local_presets, model_catalog, provider_presets

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "backend" / "presets" / "provider_presets.json"
PRODUCT_HOSTS = (
    "api.deepseek.com",
    "api.moonshot.cn",
    "open.bigmodel.cn",
    "api.x.ai",
    "infistar.cc",
    "api.88api.ai",
    "localhost:11434",
    "localhost:1234",
    "dashscope.aliyuncs.com",
    "api.siliconflow.cn",
)
CONSUMERS = (
    ROOT / "backend" / "core" / "cloud_presets.py",
    ROOT / "backend" / "core" / "local_presets.py",
    ROOT / "backend" / "core" / "model_catalog.py",
    ROOT / "frontend" / "src" / "features" / "settings" / "providers.ts",
    ROOT / "frontend" / "src" / "features" / "settings" / "modelDefaults.ts",
)


def test_catalog_has_forty_grouped_providers():
    catalog = provider_presets.get_catalog()
    assert catalog.schema_version == 1
    assert catalog.version >= 1
    assert catalog.path == CATALOG_PATH
    assert len(catalog.providers) == 40
    groups = {}
    for item in catalog.providers.values():
        groups[item.group] = groups.get(item.group, 0) + 1
    assert groups == {"recommended": 3, "popular": 10, "local": 4, "more": 23}
    assert set(catalog.providers) >= {
        "api88", "infistar", "apimart", "deepseek", "dashscope", "siliconflow", "seed", "glm",
        "kimi", "minimax-cn", "xiaomi", "openai", "gemini", "whisper", "sensevoice",
        "ollama", "lmstudio", "openrouter", "anthropic", "grok", "qianfan", "hunyuan",
    }


def test_existing_product_defaults_are_preserved():
    assert cloud_presets.CLOUD_PRESETS["deepseek"].base_url == "https://api.deepseek.com"
    assert cloud_presets.CLOUD_PRESETS["deepseek"].default_model == "deepseek-flash"
    assert cloud_presets.CLOUD_PRESETS["api88"].base_url == "https://api.88api.ai/v1"
    assert cloud_presets.CLOUD_PRESETS["api88"].default_model == ""
    assert cloud_presets.CLOUD_PRESETS["infistar"].base_url == "https://infistar.cc/v1"
    assert set(cloud_presets.CLOUD_PRESETS) == {"deepseek", "seed", "kimi", "glm", "grok", "infistar", "api88", "apimart"}
    assert local_presets.LOCAL_PRESETS["ollama"].base_url == "http://localhost:11434/v1"
    assert local_presets.LOCAL_PRESETS["ollama"].default_model == "qwen2.5:7b"
    assert local_presets.LOCAL_PRESETS["lmstudio"].base_url == "http://localhost:1234/v1"
    assert model_catalog.default_model_for("dashscope") == "qwen-plus"
    assert model_catalog.default_model_for("deepseek") == "deepseek-flash"
    assert model_catalog.CURATED_MODELS["dashscope"][0] == "qwen3.8-max"
    assert "siliconflow" not in model_catalog.CURATED_MODELS
    assert model_catalog.SILICONFLOW_BASE_URL == "https://api.siliconflow.cn/v1"
    assert provider_presets.candidates_for("dashscope", "analysis")[0] == "qwen3.8-flash"
    # Gateway defaults stay empty. Recommendations are preference order only.
    assert cloud_presets.CLOUD_PRESETS["infistar"].default_model == ""
    for provider, models in {
        "api88": ("qwen3.8-flash", "qwen3.8-max", "gemini-3.8-flash", "gemini-3.5-flash"),
        "infistar": (
            "doubao-seed-2-1-turbo-260628",
            "doubao-seed-2-1-pro-260628",
            "qwen3.8-flash",
            "qwen3.8-max",
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
        ),
    }.items():
        assert provider_presets.candidates_for(provider, "analysis") == models
        assert provider_presets.candidates_for(provider, "vision") == models
        assert provider_presets.candidates_for(provider, "image") == ()
        assert all(model_catalog.supports_vision(model) for model in models)
    assert provider_presets.candidates_for("apimart", "analysis") == (
        "qwen3.8-flash", "gemini-3.8-flash", "deepseek-v4-flash",
    )
    assert provider_presets.candidates_for("apimart", "vision") == (
        "qwen3.8-flash", "gemini-3.8-flash",
    )
    assert provider_presets.get_provider("apimart").default_model == ""
    assert provider_presets.get_provider("apimart").catalog == ()
    assert model_catalog.supports_vision("qwen3.8-flash")
    assert model_catalog.supports_vision("gemini-3.8-flash")
    assert not model_catalog.supports_vision("deepseek-v4-flash")
    dashscope = provider_presets.get_provider("dashscope")
    assert dashscope.candidates["asr"] == ("qwen-audio-3.1-asr-flash", "qwen-audio-3.0-asr-flash")
    assert provider_presets.get_provider("api88").candidates["asr"] == ()
    assert provider_presets.get_provider("infistar").candidates["asr"] == ()
    assert "asr" not in provider_presets.get_provider("api88").capabilities
    assert "asr" not in provider_presets.get_provider("infistar").capabilities
    assert provider_presets.get_provider("openai").candidates["asr"] == ("whisper-1",)
    assert dashscope.docs_url == "https://bailian.console.aliyun.com/"
    assert dashscope.referral == "https://www.aliyun.com/benefit?userCode=qmyj6jch"
    assert dashscope.sponsor is None


def test_unknown_schema_is_rejected_and_bad_rows_are_skipped(tmp_path):
    good = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    rejected = dict(good, schema_version=99)
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(rejected), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        provider_presets.load_provider_catalog(bad_path)

    skipped = {
        "schema_version": 1,
        "version": 2,
        "providers": {
            "deepseek": good["providers"]["deepseek"],
            "unknown-group": {**good["providers"]["deepseek"], "group": "secret"},
            "custom-row": {**good["providers"]["deepseek"], "kind": "custom"},
            "": good["providers"]["ollama"],
        },
    }
    skip_path = tmp_path / "skip.json"
    skip_path.write_text(json.dumps(skipped), encoding="utf-8")
    loaded = provider_presets.load_provider_catalog(skip_path)
    assert set(loaded.providers) == {"deepseek"}


def test_unknown_purpose_keys_are_ignored(tmp_path):
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    raw["providers"]["deepseek"]["candidates"]["video"] = ["should-ignore"]
    raw["providers"]["deepseek"]["candidates"]["analysis"] = ["deepseek-flash", "keep-me"]
    path = tmp_path / "extra-purpose.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = provider_presets.load_provider_catalog(path)
    assert "video" not in loaded.providers["deepseek"].candidates
    assert loaded.providers["deepseek"].candidates["analysis"] == ("deepseek-flash", "keep-me")


def test_packaged_layout_finds_json_next_to_backend(tmp_path):
    dest = tmp_path / "resources" / "backend" / "presets"
    dest.mkdir(parents=True)
    target = dest / "provider_presets.json"
    target.write_bytes(CATALOG_PATH.read_bytes())
    found = provider_presets.find_provider_presets_path(start=tmp_path / "resources" / "backend" / "core")
    assert found == target


def test_importlib_resources_finds_the_catalog():
    found = provider_presets._resource_presets_path()
    assert found == CATALOG_PATH
    catalog = provider_presets.load_provider_catalog()
    assert catalog.path == CATALOG_PATH
    assert len(catalog.providers) == 40


def test_installed_wheel_loads_catalog_outside_the_repo(tmp_path):
    """A wheel installed away from the checkout must still load 40 providers."""
    wheel_dir = tmp_path / "wheel"
    installed = tmp_path / "installed"
    elsewhere = tmp_path / "elsewhere"
    wheel_dir.mkdir()
    elsewhere.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(ROOT / "backend", source / "backend", ignore=shutil.ignore_patterns("__pycache__", "data", "logs"))
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(ROOT / name, source / name)
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir), str(source)],
        check=True,
        cwd=elsewhere,
    )
    wheels = list(wheel_dir.glob("autoclip_mcp-*-py3-none-any.whl"))
    assert wheels, list(wheel_dir.iterdir())
    with zipfile.ZipFile(wheels[0]) as archive:
        members = archive.namelist()
    assert "backend/presets/provider_presets.json" in members
    assert not any(name.startswith("backend/tests/") for name in members), "wheel must exclude backend test packages"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--target", str(installed), str(wheels[0])],
        check=True,
        cwd=elsewhere,
    )
    assert not (installed / "presets").exists()
    assert (installed / "backend" / "presets" / "provider_presets.json").is_file()
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "AUTOCLIP_PROVIDER_PRESETS"
    }
    env["PYTHONPATH"] = str(installed)
    probe = r"""
import os
import shutil
from pathlib import Path
os.environ.pop("AUTOCLIP_PROVIDER_PRESETS", None)
import backend
from backend.core import provider_presets
root = Path(%r).resolve()
assert Path(backend.__file__).resolve().is_relative_to(root)
assert Path(provider_presets.__file__).resolve().is_relative_to(root)
provider_presets.reset_catalog_cache()
catalog = provider_presets.get_catalog()
assert len(catalog.providers) == 40
assert catalog.path.resolve().is_relative_to(root)
resource = provider_presets._resource_presets_path()
assert resource is not None and resource.resolve().is_relative_to(root)
print(catalog.path)
""" % str(installed)
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=elsewhere,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "provider_presets.json" in completed.stdout


def test_hardcoded_product_hosts_left_the_six_consumers():
    catalog_text = CATALOG_PATH.read_text(encoding="utf-8")
    for host in PRODUCT_HOSTS:
        assert host in catalog_text, host
    for path in CONSUMERS:
        text = path.read_text(encoding="utf-8")
        for host in PRODUCT_HOSTS:
            assert host not in text, f"{path.name} still hard-codes {host}"
    defaults = (ROOT / "frontend" / "src" / "features" / "settings" / "modelDefaults.ts").read_text(encoding="utf-8")
    assert "PREFERRED" not in defaults
    assert "IMAGE_PREFERRED" not in defaults
    assert "qwen3.8-flash" not in defaults
    cloud = (ROOT / "backend" / "core" / "cloud_presets.py").read_text(encoding="utf-8")
    assert "CloudPreset(" not in cloud or "item.id" in cloud
    assert "https://api.deepseek.com" not in cloud
