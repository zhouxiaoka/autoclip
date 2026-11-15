"""Signed sponsor promotion: reject bad documents, keep saved profiles."""
from __future__ import annotations

import base64
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.settings import router
from backend.core import sponsor_promo
from backend.core.sponsor_promo import canonical_bytes
from backend.core.sponsor_promo_client import PromoConfig, SponsorPromoClient, load_packaged_config, parse_config
from backend.services.ai_model_settings import ModelSettings

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
PROFILES = (
    ("api88", "https://api.88api.ai/v1", "qwen3.8-flash"),
    ("infistar", "https://infistar.cc/v1", "doubao-seed-2-1-turbo-260628"),
    ("apimart", "https://api.apimart.ai/v1", "qwen3.8-flash"),
    ("compatible", "https://gw.example.com/v1", "my-model"),
)


def _profile(provider, base_url, model):
    return {
        "version": 1,
        "connections": [{
            "id": "kept", "name": provider, "provider": provider, "base_url": base_url,
            "api_key": "fixture-key", "image_api": "auto", "image_base_url": "",
            "base_url_source": "user" if provider == "compatible" else "preset",
        }],
        "analysis": {"connection_id": "kept", "model": model, "capability": "auto", "model_source": "user"},
        "cover_enabled": False, "cover_follows_analysis": False, "analysis_mode": "auto",
    }


def _assert_profiles(snapshot):
    assert snapshot == [_profile(*item) for item in PROFILES]
    for provider, base_url, model in PROFILES:
        loaded = ModelSettings.model_validate(_profile(provider, base_url, model))
        assert loaded.connections[0].provider == provider
        assert loaded.connections[0].api_key == "fixture-key"
        assert loaded.connections[0].base_url == base_url
        assert loaded.analysis.model == model


@pytest.fixture()
def profiles():
    snapshot = [_profile(*item) for item in PROFILES]
    yield snapshot
    _assert_profiles(snapshot)


def _keys():
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )).decode()
    return private, public


def _payload(sequence=1, **extra):
    body = {
        "schema": sponsor_promo.SCHEMA,
        "sequence": sequence,
        "issued_at": "2026-11-15T11:00:00Z",
        "expires_at": "2026-12-15T00:00:00Z",
        "min_app": "1.5.9",
        "max_app": "1.5.9",
        "sponsors": [{
            "id": "apimart", "order": 1, "status": "healthy", "new_user_default": True,
            "notices": {"zh": "推荐 APIMart", "en": "APIMart"},
        }, {
            "id": "api88", "order": 2, "status": "healthy",
        }],
    }
    body.update(extra)
    return body


def _envelope(private, payload):
    signature = base64.b64encode(private.sign(canonical_bytes(payload))).decode()
    return {"payload": payload, "signature": signature}


def _client(tmp_path, private, public, http, clock=None, busy=None, **config):
    return SponsorPromoClient(
        PromoConfig(enabled=True, url="https://static.example/autoclip/sponsor-promo.json", public_key=public, **config),
        data_dir=tmp_path, app_version="1.5.9", http_get=http,
        now=clock or (lambda: NOW), busy=busy or (lambda: False),
    )


def test_packaged_config_does_not_fetch_and_catalog_stays_local(profiles):
    packaged = load_packaged_config()
    assert packaged.enabled is False
    assert packaged.url == ""
    assert packaged.public_key == ""
    source = Path("backend/core/provider_presets.py").read_text(encoding="utf-8")
    assert "out of scope" in source
    assert "sponsor_promo" not in source
    text = Path("backend/core/sponsor_promo.py").read_text(encoding="utf-8")
    assert "api_key" not in text
    assert "base_url" not in text
    bundled = Path("frontend/src/features/settings/firstRunGuidance.ts").read_text(encoding="utf-8")
    assert "FIRST_RUN_CHOICES = ['apimart', 'api88', 'other']" in bundled
    assert sponsor_promo.BUNDLED_CHOICES == ("apimart", "api88", "other")
    assert sponsor_promo.BUNDLED_DEFAULT == "apimart"


def test_disabled_config_ignores_cache_and_network(tmp_path, profiles):
    called = []
    (tmp_path / "sponsor-promo-cache.json").write_text("{}", encoding="utf-8")
    client = SponsorPromoClient(
        parse_config({"enabled": True, "url": "http://insecure.example/promo.json", "public_key": "abc"}),
        data_dir=tmp_path, app_version="1.5.9", http_get=lambda *a, **k: called.append(1),
    )
    assert client.config.enabled is False
    assert client.view(trigger="startup")["source"] == "bundled"
    assert client.refresh_sync() == "disabled"
    assert called == []


def test_signed_document_sets_order_default_and_keeps_cache_when_offline(tmp_path, profiles):
    private, public = _keys()
    calls = {"n": 0}

    def http(url, timeout, max_bytes):
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("offline")
        assert url.startswith("https://")
        assert timeout == 4
        return _envelope(private, _payload())

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    shown = client.view()
    assert shown["choices"] == ["apimart", "api88", "other"]
    assert shown["default"] == "apimart"
    assert shown["statuses"] == {"apimart": "healthy", "api88": "healthy"}
    assert shown["source"] == "cache"
    assert "base_url" not in shown
    assert client.refresh_sync() == "unreachable"
    assert client.view()["default"] == "apimart"


@pytest.mark.parametrize("mutate,reason", [
    ("corrupt", "corrupt"),
    ("unsigned", "unsigned"),
    ("expired", "expired"),
    ("incompatible", "incompatible"),
    ("endpoint", "sponsors"),
    ("deleted-default", "ok"),
])
def test_bad_documents_do_not_replace_a_good_cache(tmp_path, profiles, mutate, reason):
    private, public = _keys()
    state = {"body": _envelope(private, _payload())}

    def http(url, timeout, max_bytes):
        return state["body"]

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    if mutate == "corrupt":
        state["body"] = {"payload": [], "signature": "aa"}
    elif mutate == "unsigned":
        other, _public = _keys()
        state["body"] = _envelope(other, _payload(sequence=2))
    elif mutate == "expired":
        state["body"] = _envelope(private, _payload(sequence=2, expires_at="2026-11-15T11:30:00Z"))
    elif mutate == "incompatible":
        state["body"] = _envelope(private, _payload(sequence=2, min_app="9.0.0"))
    elif mutate == "endpoint":
        bad = _payload(sequence=2)
        bad["sponsors"][0]["base_url"] = "https://evil.example/v1"
        state["body"] = _envelope(private, bad)
    else:
        state["body"] = _envelope(private, _payload(sequence=2, sponsors=[{
            "id": "api88", "order": 1, "status": "fault", "notices": {"zh": "余额查询失败"},
        }]))
    assert client.refresh_sync() == reason
    shown = client.view()
    if mutate == "deleted-default":
        assert shown["choices"] == ["api88", "other"]
        assert shown["default"] == "api88"
        assert "apimart" not in shown["choices"]
        assert shown["statuses"]["api88"] == "fault"
    else:
        assert shown["default"] == "apimart"
        assert shown["choices"][0] == "apimart"


def test_out_of_service_is_hidden_and_register_host_must_match(tmp_path, profiles):
    private, public = _keys()
    hidden = _payload(sponsors=[
        {"id": "apimart", "order": 1, "status": "out_of_service", "new_user_default": True},
        {"id": "api88", "order": 2, "status": "healthy", "register_url": "https://88api.ai/sign-up?aff=ok"},
    ])
    foreign = _payload(sequence=2)
    foreign["sponsors"][0]["register_url"] = "https://keys.evil.example/steal"

    def http(url, timeout, max_bytes):
        return _envelope(private, hidden if not getattr(http, "second", False) else foreign)

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    shown = client.view()
    assert shown["choices"] == ["api88", "other"]
    assert shown["default"] == "api88"
    assert "apimart" not in shown["choices"]
    assert shown["statuses"]["apimart"] == "out_of_service"
    assert shown["register_urls"]["api88"].startswith("https://88api.ai/")
    http.second = True
    assert client.refresh_sync() == "sponsors"
    assert client.view()["default"] == "api88"


def test_replay_downgrade_and_authorized_rollback(tmp_path, profiles):
    private, public = _keys()
    stage = {"payload": _payload(sequence=5)}

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    assert client.refresh_sync() == "current"
    stage["payload"] = _payload(sequence=4)
    assert client.refresh_sync() == "downgrade"
    stage["payload"] = _payload(sequence=6, sponsors=[
        {"id": "api88", "order": 1, "status": "healthy", "new_user_default": True},
    ])
    assert client.refresh_sync() == "ok"
    assert client.view()["default"] == "api88"
    assert client.view()["sequence"] == 6
    stage["payload"] = _payload(sequence=5)
    assert client.refresh_sync() == "downgrade"


def test_unreachable_without_cache_uses_bundle_and_busy_skips_fetch(tmp_path, profiles):
    private, public = _keys()

    def explode(url, timeout, max_bytes):
        raise TimeoutError("offline")

    client = _client(tmp_path, private, public, explode)
    assert client.refresh_sync() == "unreachable"
    assert client.view()["source"] == "bundled"
    assert client.view()["choices"] == ["apimart", "api88", "other"]
    busy = _client(tmp_path, private, public, explode, busy=lambda: True)
    assert busy.refresh_sync() == "busy"
    assert busy.schedule("startup") is False


def test_infistar_status_is_a_notice_not_a_promotion(tmp_path, profiles):
    private, public = _keys()
    payload = _payload(sponsors=[
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True},
        {"id": "infistar", "order": 2, "status": "out_of_service", "notices": {"zh": "暂停服务", "en": "Paused"}},
    ])
    refused = _payload(sequence=2, sponsors=[
        {"id": "infistar", "order": 1, "status": "fault", "register_url": "https://www.infistar.cc/register?aff=1"},
    ])

    def http(url, timeout, max_bytes):
        return _envelope(private, refused if getattr(http, "second", False) else payload)

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    shown = client.view()
    assert "infistar" not in shown["choices"]
    assert shown["choices"][0] == "apimart"
    assert shown["statuses"]["infistar"] == "out_of_service"
    assert shown["notices"]["infistar"]["zh"] == "暂停服务"
    assert "infistar" not in shown["register_urls"]
    http.second = True
    assert client.refresh_sync() == "sponsors"
    assert shown["default"] == client.view()["default"]


def test_lower_sequence_stays_rejected_after_display_expiry_and_restart(tmp_path, profiles):
    private, public = _keys()
    clock = {"now": datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)}
    stage = {"payload": _payload(sequence=10, expires_at="2026-11-15T13:00:00Z")}

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(tmp_path, private, public, http, clock=lambda: clock["now"])
    assert client.refresh_sync() == "ok"
    assert client.refresh_sync() == "current"
    stage["payload"] = _payload(sequence=9, expires_at="2026-11-15T18:00:00Z")
    assert client.refresh_sync() == "downgrade"
    clock["now"] = datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    restarted = _client(tmp_path, private, public, http, clock=lambda: clock["now"])
    assert restarted.view()["source"] == "bundled"
    assert restarted.refresh_sync() == "downgrade"
    (tmp_path / "sponsor-promo-cache.json").write_text("{", encoding="utf-8")
    assert restarted.view()["source"] == "bundled"
    assert restarted.refresh_sync() == "downgrade"


def test_commit_is_atomic_and_exact_payload_repairs_without_replacing(tmp_path, profiles):
    private, public = _keys()
    stage = {"payload": _payload(sequence=20)}

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    original = (tmp_path / "sponsor-promo-state.json").read_bytes()

    def fail_write(path, body):
        raise OSError("between writes")

    client._atomic_write = fail_write
    stage["payload"] = _payload(sequence=21)
    assert client.refresh_sync() == "store"
    assert (tmp_path / "sponsor-promo-state.json").read_bytes() == original
    assert client.view()["sequence"] == 20
    del client._atomic_write
    writes = {"n": 0}
    real_write = client._atomic_write

    def partial(path, body):
        writes["n"] += 1
        if writes["n"] == 2:
            raise OSError("backup")
        real_write(path, body)

    client._atomic_write = partial
    stage["payload"] = _payload(sequence=22)
    assert client.refresh_sync() == "store"
    assert client.view()["sequence"] == 22
    del client._atomic_write
    assert client.refresh_sync() == "current"
    (tmp_path / "sponsor-promo-cache.json").write_text("corrupt-display", encoding="utf-8")
    assert client.view()["sequence"] == 22
    stage["payload"] = _payload(sequence=22, sponsors=[
        {"id": "api88", "order": 1, "status": "healthy", "new_user_default": True},
    ])
    assert client.refresh_sync() == "replay"
    assert client.view()["default"] == "apimart"
    stage["payload"] = _payload(sequence=22)
    assert client.refresh_sync() == "current"
    (tmp_path / "sponsor-promo-state.json").write_text("{", encoding="utf-8")
    restored = _client(tmp_path, private, public, http)
    assert restored.view()["sequence"] == 22
    stage["payload"] = _payload(sequence=21)
    assert restored.refresh_sync() == "downgrade"
    assert json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["high_water"] == 22


def test_malformed_ledger_does_not_reset_history(tmp_path, profiles):
    private, public = _keys()
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=8)))
    assert client.refresh_sync() == "ok"
    raw = '{"high_water": 8, "retired": 7, "accepted": null}'
    (tmp_path / "sponsor-promo-state.json").write_text(raw, encoding="utf-8")
    (tmp_path / "sponsor-promo-state.bak").unlink()
    damaged = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=1)))
    assert damaged.refresh_sync() == "downgrade"
    assert json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["high_water"] == 8
    typed = '{"high_water": "8", "retired": "nope", "accepted": null}'
    (tmp_path / "sponsor-promo-state.json").write_text(typed, encoding="utf-8")
    typed_client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=1)))
    assert typed_client.refresh_sync() == "downgrade"
    assert json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["high_water"] == 8
    for name in ("sponsor-promo-state.json", "sponsor-promo-state.bak", "sponsor-promo-checkpoint.json"):
        (tmp_path / name).write_text("{", encoding="utf-8")
    truncated = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=1)))
    assert truncated.view()["security_state"] == "error"
    assert truncated.refresh_sync() == "security_state"
    assert (tmp_path / "sponsor-promo-checkpoint.json").read_text(encoding="utf-8") == "{"


def test_unreadable_state_is_not_rewritten(tmp_path, profiles, monkeypatch):
    private, public = _keys()
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=8)))
    assert client.refresh_sync() == "ok"
    original = (tmp_path / "sponsor-promo-state.json").read_text(encoding="utf-8")
    real = Path.read_text

    def unreadable(self, *args, **kwargs):
        if self.name in {"sponsor-promo-state.json", "sponsor-promo-state.bak", "sponsor-promo-checkpoint.json"}:
            raise PermissionError("unreadable")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    blocked = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=1)))
    assert blocked.view()["security_state"] == "error"
    assert blocked.refresh_sync() == "security_state"
    monkeypatch.undo()
    restarted = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=8)))
    assert (tmp_path / "sponsor-promo-state.json").read_text(encoding="utf-8") == original
    assert restarted.view()["sequence"] == 8
    assert restarted.refresh_sync() == "current"


def test_checkpoint_keeps_high_water_above_a_stale_backup(tmp_path, profiles, monkeypatch):
    private, public = _keys()
    stage = {"payload": _payload(sequence=40)}

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    (tmp_path / "sponsor-promo-state.json").unlink()
    restarted = _client(tmp_path, private, public, http)
    assert restarted.view()["sequence"] == 40
    stage["payload"] = _payload(sequence=39)
    assert restarted.refresh_sync() == "downgrade"
    assert json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["high_water"] == 40

    stage["payload"] = _payload(sequence=50)
    assert restarted.refresh_sync() == "ok"
    writes = {"n": 0}
    real_write = restarted._atomic_write

    def fail_backup(path, body):
        writes["n"] += 1
        if writes["n"] == 3:
            raise OSError("backup")
        real_write(path, body)

    restarted._atomic_write = fail_backup
    stage["payload"] = _payload(sequence=52)
    assert restarted.refresh_sync() == "store"
    del restarted._atomic_write
    (tmp_path / "sponsor-promo-state.json").write_text("{", encoding="utf-8")
    stage["payload"] = _payload(sequence=51)
    assert restarted.refresh_sync() == "downgrade"
    assert json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["high_water"] == 52
    stage["payload"] = _payload(sequence=52)
    assert restarted.refresh_sync() == "current"
    backup = json.loads((tmp_path / "sponsor-promo-state.bak").read_text())
    assert backup["high_water"] == 52
    assert backup["accepted"]["digest"] == json.loads((tmp_path / "sponsor-promo-checkpoint.json").read_text())["accepted"]["digest"]

    import backend.core.sponsor_promo_client as client_mod

    def fail_fsync(_fd):
        raise OSError("fsync")

    monkeypatch.setattr(client_mod.os, "fsync", fail_fsync)
    stage["payload"] = _payload(sequence=53)
    assert restarted.refresh_sync() == "store"
    monkeypatch.undo()
    again = _client(tmp_path, private, public, http)
    assert again.view()["sequence"] == 52
    stage["payload"] = _payload(sequence=39)
    assert again.refresh_sync() == "downgrade"


def test_delayed_fetch_wakes_the_same_view_and_idle_resumes(tmp_path, profiles):
    import threading
    from backend.core.project_cancellation import bind

    private, public = _keys()
    release = threading.Event()
    calls = {"n": 0}

    def http(url, timeout, max_bytes):
        calls["n"] += 1
        if calls["n"] == 1:
            release.wait(2)
        return _envelope(private, _payload(sequence=50))

    client = _client(tmp_path, private, public, http)
    started = client.view(trigger="startup")
    assert started["pending"] is True
    assert started.get("sequence") in (None, 0)
    release.set()
    followed = client.wait_for_change(started["revision"], 2)
    assert followed["sequence"] == 50
    assert calls["n"] == 1
    release2 = threading.Event()

    def gated(url, timeout, max_bytes):
        calls["n"] += 1
        release2.set()
        return _envelope(private, _payload(sequence=51))

    idle = SponsorPromoClient(
        PromoConfig(enabled=True, url="https://static.example/autoclip/sponsor-promo.json", public_key=public),
        data_dir=tmp_path, app_version="1.5.9", http_get=gated, now=lambda: NOW,
    )
    with bind("still-running"):
        assert idle.view(trigger="startup")["pending"] is True
        assert calls["n"] == 1
    assert release2.wait(2)
    assert idle.wait_for_change(0, 2)["sequence"] == 51


def test_invalid_key_bad_port_and_store_failure_do_not_fetch_or_raise(tmp_path, profiles):
    called = []
    disabled = SponsorPromoClient(
        parse_config({"enabled": True, "url": "https://static.example/promo.json", "public_key": "not-base64"}),
        data_dir=tmp_path, app_version="1.5.9", http_get=lambda *a, **k: called.append(1),
    )
    assert disabled.config.enabled is False
    assert disabled.refresh_sync() == "disabled"
    assert called == []
    private, public = _keys()
    bad = _payload()
    bad["sponsors"][0]["register_url"] = "https://go.apimart.ai:bad/path"
    bad["sponsors"].append({"id": ["infistar"], "order": 2, "status": "healthy"})

    def http(url, timeout, max_bytes):
        return _envelope(private, bad)

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "sponsors"
    stage = {"sequence": 3}

    def good_http(url, timeout, max_bytes):
        return _envelope(private, _payload(sequence=stage["sequence"]))

    good = _client(tmp_path, private, public, good_http)
    assert good.refresh_sync() == "ok"

    def deny(*_args, **_kwargs):
        raise OSError("readonly")

    good._atomic_write = deny
    stage["sequence"] = 4
    assert good.refresh_sync() == "store"
    assert good.view()["sequence"] == 3


def test_bound_generation_defers_fetch_until_the_worker_finishes(tmp_path, profiles):
    from backend.core.project_cancellation import any_worker_bound, bind

    private, public = _keys()
    calls = {"n": 0}

    def http(url, timeout, max_bytes):
        calls["n"] += 1
        return _envelope(private, _payload())

    client = SponsorPromoClient(
        PromoConfig(enabled=True, url="https://static.example/autoclip/sponsor-promo.json", public_key=public),
        data_dir=tmp_path, app_version="1.5.9", http_get=http, now=lambda: NOW,
    )
    with bind("project-kept"):
        assert any_worker_bound() is True
        assert client.refresh_sync() == "busy"
        assert calls["n"] == 0
    assert any_worker_bound() is False
    assert client.refresh_sync() == "ok"
    assert calls["n"] == 1


def test_endpoint_follow_up_sees_the_delayed_accept(monkeypatch, tmp_path, profiles):
    import threading
    private, public = _keys()
    release = threading.Event()

    def http(url, timeout, max_bytes):
        release.wait(2)
        return _envelope(private, _payload(sequence=50))

    client = _client(tmp_path, private, public, http)
    monkeypatch.setattr("backend.core.sponsor_promo_client.get_client", lambda: client)
    app = FastAPI()
    app.include_router(router)
    api = TestClient(app)
    first = api.get("/settings/sponsor-promo", params={"trigger": "startup"})
    assert first.status_code == 200
    assert first.json()["pending"] is True
    assert first.json()["source"] == "bundled"
    release.set()
    followed = api.get("/settings/sponsor-promo", params={"after": first.json()["revision"], "wait": 2})
    assert followed.json()["sequence"] == 50
    assert followed.json()["pending"] is False


def test_endpoint_returns_bundle_without_saving_settings(monkeypatch, profiles):
    def refuse(*_args, **_kwargs):
        raise AssertionError("settings must not be saved")

    monkeypatch.setattr("backend.services.ai_model_settings.save", refuse)
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/settings/sponsor-promo")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "bundled"
    assert body["enabled"] is False
    assert body["default"] == "apimart"
    assert "api_key" not in json.dumps(body)
    assert "base_url" not in json.dumps(body)


def test_sign_script_refuses_a_private_key_inside_the_repo(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sponsor_promo_sign", Path("scripts/sponsor_promo_sign.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    with pytest.raises(SystemExit, match="inside the repository"):
        tool._generate(Path("backend/presets/not-a-production-key.pem"))
