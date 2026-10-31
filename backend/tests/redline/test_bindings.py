"""RL: UI transitions -> HTTP save/reopen -> disk -> purpose routing."""
import json
from pathlib import Path
import subprocess

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.services import ai_model_settings as ai


@pytest.mark.parametrize("entry", ["legacy", "catalog", "smart", "fixed"])
@pytest.mark.parametrize("source", ["preset", "user"])
@pytest.mark.parametrize("binding_id", ["old", "independent"])
def test_purpose_providers_survive_switch_toggle_save_reopen(entry, source, binding_id, monkeypatch):
    from backend.api.v1.settings import router

    monkeypatch.setattr(ai, "migrate_legacy", lambda: ai.ModelSettings())
    config = ai.ModelSettings(
        connections=[ai.Connection(id=id_, name=id_, provider=provider, api_key="") for id_, provider in
                     [("old", "openai"), ("new", "lmstudio"), ("independent", "dashscope")]],
        analysis=ai.Assignment(connection_id="old", model="old-analysis", model_source=source),
        vision=ai.Assignment(connection_id=binding_id, model="own-vision", capability="multimodal", model_source=source),
        cover=ai.Assignment(connection_id=binding_id, model="own-cover", model_source=source),
        transcription=ai.Transcription(provider="cloud", connection_id=binding_id,
                                       model="whisper-1" if binding_id == "old" else "qwen-audio-3.0-asr-flash",
                                       model_source=source),
        cover_enabled=True, cover_choice_version=ai.COVER_CHOICE_VERSION,
        cover_follows_analysis=False,  # explicit independent cover (Kris: follow is an explicit flag)
    )
    script = """
const fs = require('node:fs')
const { transition } = require('./tests/redline-bindings.test.cjs')
process.stdout.write(JSON.stringify(transition(JSON.parse(fs.readFileSync(0, 'utf8')), process.argv[1], process.argv[2])))
"""
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.put("/settings/ai-models", json=config.model_dump()).status_code == 200
        for action in ("switch", "off", "on", "reopen"):
            public = client.get("/settings/ai-models").json()
            result = subprocess.run(
                ["node", "-e", script, entry, action], input=json.dumps(public),
                cwd=Path(__file__).resolve().parents[3] / "frontend",
                capture_output=True, text=True, timeout=30,
            )
            assert result.returncode == 0, "frontend RL transition failed"
            assert client.put("/settings/ai-models", json=json.loads(result.stdout)).status_code == 200
            reopened = client.get("/settings/ai-models").json()
            loaded = ai.load()
            assert loaded.analysis.connection_id == reopened["analysis"]["connection_id"] == "new"
            for role in ("vision", "cover", "transcription"):
                original = getattr(config, role)
                assert reopened[role] == original.model_dump()
                assert getattr(loaded, role) == original
                assert ai.connection_for(loaded, getattr(loaded, role)).provider == ai.connection_for(config, original).provider
            assert ai.vision_follow_binding(loaded).connection_id == binding_id
            assert loaded.cover_enabled == reopened["cover_enabled"] == (action != "off")
            assert loaded.allow_visual_screening == (action != "off")
