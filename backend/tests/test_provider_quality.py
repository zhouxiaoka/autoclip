"""F1: static provider success / latency tiers. No live PostHog call."""
import json
import os
import subprocess
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.cloud_presets import CLOUD_PRESETS
from backend.core.local_presets import presets_as_dicts
from backend.core.provider_presets import get_provider
from backend.core.provider_quality import (
    REFRESH_HOGQL,
    Thresholds,
    display_catalog_group,
    latency_tier,
    public_payload,
    quality_for,
    recommended_provider_ids,
    success_tier,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPECTED = {
    "deepseek": (0.91, 1.8, "high", "under_5m", None),
    "dashscope": (0.81, 3.9, "high", "under_5m", None),
    "compatible": (0.80, 5.2, "high", "mid_5_20m", None),
    "api88": (0.71, 16.5, "mid", "mid_5_20m", None),
    "ollama": (0.66, 15.6, "mid", "mid_5_20m", None),
    "lmstudio": (0.78, 16, "mid", "mid_5_20m", None),
    "gemini": (0.44, 44, "low", "over_20m", "settings.providers.caveat.gemini_free_rpm"),
    "openai": (0.36, 12, "low", "mid_5_20m", "settings.providers.caveat.openai_network"),
}


def test_seeded_rates_map_to_the_measured_tiers():
    for provider_id, (rate, minutes, tier, latency, caveat) in EXPECTED.items():
        row = quality_for(provider_id)
        assert row is not None, provider_id
        assert row.success_rate == pytest.approx(rate)
        assert row.success_p50_minutes == pytest.approx(minutes)
        assert row.success_tier == tier
        assert row.latency_tier == latency
        assert row.caveat_key == caveat
        assert row.as_public() == {
            "success_tier": tier,
            "latency_tier": latency,
            "caveat_key": caveat,
        }


def test_unmeasured_providers_have_no_tier():
    for provider_id in ("seed", "kimi", "glm", "grok", "infistar", "apimart", "siliconflow", "whisper"):
        assert quality_for(provider_id) is None
        preset = get_provider(provider_id)
        assert preset is not None
        assert preset.success_tier is None
        assert preset.latency_tier is None
        assert preset.caveat_key is None


@pytest.mark.parametrize("rate, expected", [
    (0.8, "high"),
    (1, "high"),
    (0.91, "high"),
    (0.799, "mid"),
    (0.6, "mid"),
    (0.66, "mid"),
    (0.599, "low"),
    (0, "low"),
    (0.44, "low"),
    (-0.01, None),
    (1.01, None),
])
def test_success_tier_thresholds(rate, expected):
    assert success_tier(rate, Thresholds()) == expected


@pytest.mark.parametrize("minutes, expected", [
    (0, "under_5m"),
    (1.8, "under_5m"),
    (4.999, "under_5m"),
    (5, "mid_5_20m"),
    (5.2, "mid_5_20m"),
    (16, "mid_5_20m"),
    (20, "mid_5_20m"),
    (20.001, "over_20m"),
    (44, "over_20m"),
    (-1, None),
])
def test_latency_tier_thresholds(minutes, expected):
    assert latency_tier(minutes, Thresholds()) == expected


def test_low_tier_stays_out_of_recommended_and_sponsors_stay_first():
    assert display_catalog_group("recommended", sponsor=False, success_tier_value="low") == "popular"
    assert display_catalog_group("recommended", sponsor=True, success_tier_value="low") == "popular"
    assert display_catalog_group("popular", sponsor=False, success_tier_value="low") == "popular"
    assert display_catalog_group("local", sponsor=False, success_tier_value="mid") == "local"
    assert display_catalog_group("popular", sponsor=False, success_tier_value="high") == "recommended"
    assert display_catalog_group("recommended", sponsor=True, success_tier_value=None) == "recommended"
    ids = recommended_provider_ids()
    assert ids == ["apimart", "api88", "infistar", "deepseek", "dashscope"]
    assert "gemini" not in ids
    assert "openai" not in ids
    assert "ollama" not in ids
    assert "lmstudio" not in ids


def test_cloud_and_local_presets_expose_tier_fields():
    assert CLOUD_PRESETS["deepseek"].success_tier == "high"
    assert CLOUD_PRESETS["deepseek"].latency_tier == "under_5m"
    assert CLOUD_PRESETS["deepseek"].caveat_key is None
    assert CLOUD_PRESETS["api88"].success_tier == "mid"
    assert CLOUD_PRESETS["api88"].latency_tier == "mid_5_20m"
    assert CLOUD_PRESETS["seed"].success_tier is None
    assert CLOUD_PRESETS["seed"].latency_tier is None
    assert CLOUD_PRESETS["seed"].caveat_key is None
    local = {item["key"]: item for item in presets_as_dicts()}
    assert local["ollama"]["success_tier"] == "mid"
    assert local["ollama"]["latency_tier"] == "mid_5_20m"
    assert local["ollama"]["caveat_key"] is None
    assert local["lmstudio"]["success_tier"] == "mid"
    assert local["lmstudio"]["latency_tier"] == "mid_5_20m"
    deepseek = get_provider("deepseek")
    gemini = get_provider("gemini")
    assert deepseek.success_tier == "high" and deepseek.latency_tier == "under_5m"
    assert gemini.caveat_key == "settings.providers.caveat.gemini_free_rpm"
    assert gemini.success_tier == "low" and gemini.latency_tier == "over_20m"


def test_settings_provider_quality_api_returns_tiers_and_recommended_order():
    import sys
    import types
    from pathlib import Path

    if "backend.api.v1.settings" not in sys.modules:
        package = types.ModuleType("backend.api.v1")
        package.__path__ = [str(Path(__file__).resolve().parents[1] / "api" / "v1")]
        package.__package__ = "backend.api.v1"
        sys.modules["backend.api.v1"] = package
    from backend.api.v1.settings import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/settings/provider-quality")
    assert response.status_code == 200
    body = response.json()
    assert body["recommended"] == ["apimart", "api88", "infistar", "deepseek", "dashscope"]
    assert body["providers"]["deepseek"] == {
        "success_tier": "high",
        "latency_tier": "under_5m",
        "caveat_key": None,
    }
    assert body["providers"]["gemini"]["caveat_key"] == "settings.providers.caveat.gemini_free_rpm"
    assert body["providers"]["openai"]["success_tier"] == "low"
    assert "seed" not in body["providers"]
    assert body == public_payload()
    with TestClient(app) as client:
        local = client.get("/settings/local-presets").json()
    assert {row["key"]: row["success_tier"] for row in local["presets"]} == {"ollama": "mid", "lmstudio": "mid"}
    assert all("latency_tier" in row and "caveat_key" in row for row in local["presets"])


def test_refresh_script_prints_hogql_without_posthog_credentials():
    assert "person_id" in REFRESH_HOGQL
    assert "INTERVAL 14 DAY" in REFRESH_HOGQL
    assert "success_p50_minutes" in REFRESH_HOGQL
    assert "properties.provider" in REFRESH_HOGQL
    env = {key: value for key, value in os.environ.items() if key not in {"POSTHOG_PERSONAL_API_KEY", "POSTHOG_API_KEY"}}
    completed = subprocess.run(
        [sys.executable, str(os.path.join(ROOT, "scripts", "provider_quality_report.py"))],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "INTERVAL 14 DAY" in completed.stdout
    assert "provider_quality.json" in completed.stdout
    with open(os.path.join(ROOT, "backend", "presets", "provider_quality.json"), encoding="utf-8") as handle:
        raw = json.load(handle)
    assert set(raw["providers"]) == set(EXPECTED)
