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


def test_packaged_config_uses_valid_https_worker_and_catalog_stays_local(profiles):
    packaged = load_packaged_config()
    assert packaged.enabled is True
    assert packaged.url == "https://autoclip-sponsor-promo.autoclip-val-3f71ee83.workers.dev/sponsor-promo.json"
    assert packaged.fallback_urls == (
        "https://autoclip-config-1311545920.cos.ap-shanghai.myqcloud.com/sponsor-promo.json",
    )
    assert packaged.v2_url == "https://autoclip-sponsor-promo.autoclip-val-3f71ee83.workers.dev/sponsor-promo-v2.json"
    assert packaged.v2_fallback_urls == (
        "https://autoclip-config-1311545920.cos.ap-shanghai.myqcloud.com/sponsor-promo-v2.json",
    )
    assert len(base64.b64decode(packaged.public_key, validate=True)) == 32
    assert "PRIVATE" not in packaged.public_key
    assert packaged.min_sequence >= 1
    source = Path("backend/core/provider_presets.py").read_text(encoding="utf-8")
    assert "out of scope" in source
    assert "sponsor_promo" not in source
    text = Path("backend/core/sponsor_promo.py").read_text(encoding="utf-8")
    assert "api_key" not in text
    assert "base_url" not in sponsor_promo.SPONSOR_KEYS
    bundled = Path("frontend/src/features/settings/firstRunGuidance.ts").read_text(encoding="utf-8")
    assert "FIRST_RUN_CHOICES = ['apimart', 'other']" in bundled
    assert sponsor_promo.BUNDLED_CHOICES == ("apimart", "other")
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
    assert "api88" in shown["choices"]
    assert "api88" not in shown["register_urls"]
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
        {"id": "api88", "order": 2, "status": "healthy"},
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
    assert "api88" in shown["choices"]
    assert shown["statuses"]["apimart"] == "out_of_service"
    assert "api88" not in shown["register_urls"]
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
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True},
        {"id": "api88", "order": 2, "status": "fault", "notices": {"zh": "余额查询失败"}},
    ])
    assert client.refresh_sync() == "ok"
    assert client.view()["default"] == "apimart"
    assert "api88" in client.view()["choices"]
    assert client.view()["statuses"]["api88"] == "fault"
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
    assert client.view()["choices"] == ["apimart", "other"]
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
        {"id": "infistar", "order": 1, "status": "fault", "register_url": "https://evil.example/register"},
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


def test_higher_sequence_restores_trusted_host_then_withdraws(tmp_path, profiles):
    private, public = _keys()
    stage = {"payload": _payload(sequence=3, sponsors=[
        {
            "id": "api88", "order": 1, "status": "healthy", "new_user_default": True,
            "register_url": "https://88api.ai/sign-up?aff=2PIc",
        },
        {
            "id": "infistar", "order": 2, "status": "healthy",
            "register_url": "https://www.infistar.cc/register?aff=1",
        },
        {"id": "apimart", "order": 3, "status": "fault"},
    ])}

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    shown = client.view()
    assert shown["choices"] == ["api88", "infistar", "apimart", "other"]
    assert shown["default"] == "api88"
    assert shown["register_urls"]["api88"] == "https://88api.ai/sign-up?aff=2PIc"
    assert shown["register_urls"]["infistar"] == "https://www.infistar.cc/register?aff=1"
    assert "apimart" not in shown["register_urls"]
    stage["payload"] = _payload(sequence=4, sponsors=[
        {"id": "other-gateway", "order": 1, "status": "healthy"},
    ])
    assert client.refresh_sync() == "sponsors"
    assert client.view()["default"] == "api88"
    stage["payload"] = _payload(sequence=5, sponsors=[
        {"id": "api88", "order": 1, "status": "healthy", "register_url": "https://api.88api.ai/sign-up"},
    ])
    assert client.refresh_sync() == "sponsors"
    assert client.view()["register_urls"]["api88"] == "https://88api.ai/sign-up?aff=2PIc"
    stage["payload"] = _payload(sequence=6, sponsors=[
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True,
         "register_url": "https://go.apimart.ai/tw-autoclip"},
        {"id": "api88", "order": 2, "status": "out_of_service", "notices": {"zh": "暂停"}},
        {"id": "infistar", "order": 3, "status": "out_of_service"},
    ])
    assert client.refresh_sync() == "ok"
    withdrawn = client.view()
    assert withdrawn["choices"] == ["apimart", "other"]
    assert withdrawn["default"] == "apimart"
    assert withdrawn["statuses"]["api88"] == "out_of_service"
    assert withdrawn["statuses"]["infistar"] == "out_of_service"
    assert "api88" not in withdrawn["register_urls"]
    assert "infistar" not in withdrawn["register_urls"]
    assert withdrawn["notices"]["api88"]["zh"] == "暂停"


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


def test_endpoint_returns_bundle_without_saving_settings(monkeypatch, tmp_path, profiles):
    def refuse(*_args, **_kwargs):
        raise AssertionError("settings must not be saved")

    monkeypatch.setattr("backend.services.ai_model_settings.save", refuse)
    offline = SponsorPromoClient(
        PromoConfig(enabled=False, url="", public_key=""),
        data_dir=tmp_path,
        app_version="1.5.9",
        http_get=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    monkeypatch.setattr("backend.core.sponsor_promo_client.get_client", lambda: offline)
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


def test_restarted_process_keeps_sequence_and_replaces_the_revision_epoch(tmp_path, profiles):
    private, public = _keys()
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=11)))
    assert client.refresh_sync() == "ok"
    opened = client.view()
    assert opened["sequence"] == 11
    assert opened["revision"] == 0
    assert isinstance(opened["instance"], str) and opened["instance"]
    restarted = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=11)))
    again = restarted.view()
    assert again["sequence"] == 11
    assert again["revision"] == 0
    assert again["instance"] != opened["instance"]
    assert restarted.refresh_sync() == "current"
    assert restarted.view()["sequence"] == 11


def test_undecodable_copy_falls_through_to_another_signed_copy(tmp_path, profiles):
    private, public = _keys()
    stage = {"body": _envelope(private, _payload(sequence=11))}

    def http(url, timeout, max_bytes):
        return stage["body"]

    client = _client(tmp_path, private, public, http)
    assert client.refresh_sync() == "ok"
    (tmp_path / "sponsor-promo-state.bak").write_bytes(b"\xff\xfe")
    assert client.view()["sequence"] == 11
    (tmp_path / "sponsor-promo-state.json").write_bytes(b"\xff\xfe\x00\x00")
    (tmp_path / "sponsor-promo-state.bak").unlink()
    shown = client.view()
    assert shown["sequence"] == 11
    assert shown.get("security_state") != "error"
    (tmp_path / "sponsor-promo-state.json").write_bytes(b"\xff\xfe")
    (tmp_path / "sponsor-promo-checkpoint.json").write_bytes(b"\xff\xfe")
    backup_only = client.view()
    assert backup_only["sequence"] == 11
    stage["body"] = {"payload": _payload(sequence=12), "signature": "aa"}
    assert client.refresh_sync() == "unsigned"
    assert client.view()["sequence"] == 11
    stage["body"] = _envelope(private, _payload(sequence=10))
    assert client.refresh_sync() == "downgrade"
    assert client.view()["sequence"] == 11
    for name in ("sponsor-promo-state.json", "sponsor-promo-state.bak", "sponsor-promo-checkpoint.json"):
        (tmp_path / name).write_bytes(b"\xff\xfe")
    blocked = _client(tmp_path, private, public, http)
    assert blocked.view()["security_state"] == "error"
    assert blocked.view()["source"] == "bundled"
    assert blocked.refresh_sync() == "security_state"


def test_sign_script_refuses_a_private_key_inside_the_repo(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sponsor_promo_sign", Path("scripts/sponsor_promo_sign.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    with pytest.raises(SystemExit, match="inside the repository"):
        tool._generate(Path("backend/presets/not-a-production-key.pem"))


def test_locale_routing_disjoint_defaults_and_localized_register_urls(monkeypatch, tmp_path, profiles):
    private, public = _keys()
    overseas = ["en", "ja", "ko", "es", "fr", "pt", "ru", "id", "tr", "vi", "de", "it", "pl", "th", "nl", "uk", "hi", "ar"]
    payload = _payload(sequence=15, sponsors=[
        {
            "id": "apimart",
            "order": 1,
            "status": "healthy",
            "new_user_default": True,
            "locales": ["zh"],
            "register_urls": {"zh": "https://go.apimart.ai/cn-autoclip"},
        },
        {
            "id": "api88",
            "order": 2,
            "status": "healthy",
            "new_user_default": True,
            "locales": overseas,
            "register_urls": {
                "en": "https://88api.ai/sign-up?aff=global",
                "ja": "https://88api.ai/sign-up?aff=jp",
            },
        },
    ])
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, payload))
    assert client.refresh_sync() == "ok"

    zh_view = client.view(locale="zh-CN")
    assert zh_view["choices"] == ["apimart", "other"]
    assert zh_view["default"] == "apimart"
    assert zh_view["register_urls"] == {"apimart": "https://go.apimart.ai/cn-autoclip"}
    assert zh_view["by_locale"]["en"]["choices"] == ["api88", "other"]
    assert zh_view["by_locale"]["en"]["default"] == "api88"
    assert zh_view["by_locale"]["en"]["register_urls"] == {"api88": "https://88api.ai/sign-up?aff=global"}
    assert zh_view["by_locale"]["ja"]["register_urls"] == {"api88": "https://88api.ai/sign-up?aff=jp"}
    assert zh_view["by_locale"]["ko"]["register_urls"] == {"api88": "https://88api.ai/sign-up?aff=global"}

    en_view = client.view(locale="en-US")
    assert en_view["choices"] == ["api88", "other"]
    assert en_view["default"] == "api88"
    assert en_view["register_urls"] == {"api88": "https://88api.ai/sign-up?aff=global"}

    monkeypatch.setattr("backend.core.sponsor_promo_client.get_client", lambda: client)
    app = FastAPI()
    app.include_router(router)
    api = TestClient(app)
    res_zh = api.get("/settings/sponsor-promo", params={"locale": "zh"}).json()
    res_en = api.get("/settings/sponsor-promo", params={"locale": "en"}).json()
    assert res_zh["default"] == "apimart"
    assert res_zh["choices"] == ["apimart", "other"]
    assert res_en["default"] == "api88"
    assert res_en["choices"] == ["api88", "other"]

    # zh-only sponsor leaves overseas cleanly on "other"
    zh_only = _payload(sequence=16, sponsors=[
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "locales": ["zh"]},
    ])
    client_zh_only = _client(tmp_path / "zh_only", private, public, lambda url, timeout, max_bytes: _envelope(private, zh_only))
    assert client_zh_only.refresh_sync() == "ok"
    assert client_zh_only.view(locale="en")["choices"] == ["other"]
    assert client_zh_only.view(locale="en")["default"] == "other"
    assert client_zh_only.view(locale="zh")["choices"] == ["apimart", "other"]


@pytest.mark.parametrize("bad_sponsors", [
    [
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "locales": ["zh", "en"]},
        {"id": "api88", "order": 2, "status": "healthy", "new_user_default": True, "locales": ["en"]},
    ],
    [
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "locales": ["sv"]},
        {"id": "api88", "order": 2, "status": "healthy", "new_user_default": True, "locales": ["sv"]},
    ],
    [
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True},
        {"id": "api88", "order": 2, "status": "healthy", "new_user_default": True, "locales": ["sv"]},
    ],
    [{"id": "apimart", "order": 1, "status": "healthy", "locales": []}],
    [{"id": "apimart", "order": 1, "status": "healthy", "locales": ["zh", "zh"]}],
    [{"id": "apimart", "order": 1, "status": "healthy", "locales": ["../zh"]}],
    [{"id": "apimart", "order": 1, "status": "healthy", "locales": ["EN"]}],
    [{"id": "apimart", "order": 1, "status": "healthy", "register_urls": {"en": "https://evil.example/steal"}}],
    [{"id": "apimart", "order": 1, "status": "healthy", "register_urls": {"sv": "https://evil.example/steal"}}],
    [{"id": "apimart", "order": 1, "status": "healthy", "register_urls": {}}],
    [{"id": "apimart", "order": 1, "status": "healthy", "notices": {"sv": "<script>bad</script>"}}],
])
def test_locale_routing_rejects_overlapping_defaults_and_bad_localized_fields(tmp_path, profiles, bad_sponsors):
    private, public = _keys()
    client = _client(
        tmp_path,
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, _payload(sequence=20, sponsors=bad_sponsors)),
    )
    assert client.refresh_sync() == "sponsors"
    assert client.view()["source"] == "bundled"


def test_forward_compatible_future_iso_locales_and_dynamic_provider_locales(tmp_path, profiles):
    private, public = _keys()
    payload = _payload(
        sequence=21,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[
            _dynamic_provider(
                id="cloudgw",
                name={"en": "CloudGW", "zh": "云网关", "sv": "MolnGW"},
                hint={"en": "Global gateway", "sv": "Svensk text"},
                offer={"sv": "50 kr"},
                locales=["en", "it", "sv"],
            ),
            _dynamic_provider(
                id="nordicgw",
                name={"en": "NordicGW", "no": "NordiskGW"},
                base_url="https://router.nordicgw.example/v1",
                register_url="https://www.nordicgw.example/?ref=1",
                docs_url="https://docs.nordicgw.example/",
                locales=["no"],
            ),
        ],
        sponsors=[
            {
                "id": "cloudgw",
                "order": 1,
                "status": "healthy",
                "new_user_default": True,
                "locales": ["en", "it", "sv"],
                "notices": {"en": "Degraded", "sv": "Tillfälligt långsam"},
                "register_urls": {
                    "en": "https://www.cloudgw.example/?ref=en",
                    "sv": "https://www.cloudgw.example/?ref=sv",
                },
            },
            {
                "id": "nordicgw",
                "order": 2,
                "status": "healthy",
                "new_user_default": True,
                "locales": ["no"],
            },
        ],
    )
    client = _client(
        tmp_path / "fwd",
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, payload),
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )
    assert client.refresh_sync() == "ok"
    en_view = client.view(locale="en")
    it_view = client.view(locale="it")
    zh_view = client.view(locale="zh")
    no_locale_view = client.view()

    assert en_view["choices"] == ["cloudgw", "other"]
    assert it_view["choices"] == ["cloudgw", "other"]
    assert zh_view["choices"] == ["other"]
    assert "nordicgw" not in no_locale_view["choices"]
    assert en_view["notices"]["cloudgw"] == {"en": "Degraded"}
    by_id = {p["id"]: p for p in en_view["providers"]}
    assert by_id["cloudgw"]["locales"] == ["en", "it"]
    assert by_id["cloudgw"]["name"] == {"en": "CloudGW", "zh": "云网关"}
    assert "offer" not in by_id["cloudgw"]
    assert by_id["nordicgw"]["locales"] == []

    # Invalid dynamic provider locales must still be rejected
    for bad_locales in ([], ["zh", "zh"], ["../zh"], ["123"]):
        bad_payload = _payload(
            sequence=22,
            schema=sponsor_promo.SCHEMA_V2,
            providers=[_dynamic_provider(locales=bad_locales)],
            sponsors=[{"id": "apimart", "order": 1, "status": "healthy"}],
        )
        bad_client = _client(
            tmp_path / f"bad-{abs(hash(str(bad_locales)))}",
            private,
            public,
            lambda url, timeout, max_bytes, p=bad_payload: _envelope(private, p),
            v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
        )
        assert bad_client.refresh_sync() == "providers"


def test_sponsor_cloud_configurable_badges_and_security_validation(tmp_path, profiles):
    private, public = _keys()
    payload = _payload(
        sequence=25,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[_dynamic_provider(id="cloudgw")],
        sponsors=[
            {
                "id": "apimart",
                "order": 1,
                "status": "healthy",
                "new_user_default": True,
                "badge": "",
            },
            {
                "id": "cometapi",
                "order": 2,
                "status": "healthy",
                "badge": {"zh": "赞助", "en": "Sponsor", "sv": "Sponsor SV"},
            },
            {
                "id": "cloudgw",
                "order": 3,
                "status": "healthy",
                "badge": "¥5 free credit",
            },
        ],
    )
    client = _client(
        tmp_path / "badges",
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, payload),
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )
    assert client.refresh_sync() == "ok"
    view = client.view(locale="en")
    assert view["badges"] == {
        "apimart": "",
        "cometapi": {"zh": "赞助", "en": "Sponsor"},
        "cloudgw": {"en": "¥5 free credit"},
    }

    for bad_badge in ("<script>x</script>", "https://evil.example", {}, {"../zh": "x"}, "x" * 60):
        bad_payload = _payload(
            sequence=26,
            sponsors=[{"id": "apimart", "order": 1, "status": "healthy", "badge": bad_badge}],
        )
        bad_client = _client(
            tmp_path / f"bad-badge-{abs(hash(str(bad_badge)))}",
            private,
            public,
            lambda url, timeout, max_bytes, p=bad_payload: _envelope(private, p),
        )
        assert bad_client.refresh_sync() == "sponsors"


def test_sponsor_first_run_flag_decouples_first_run_modal_from_settings_recommended(tmp_path, profiles):
    private, public = _keys()
    payload = _payload(
        sequence=27,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[_dynamic_provider(id="cloudgw")],
        sponsors=[
            {
                "id": "apimart",
                "order": 1,
                "status": "healthy",
                "new_user_default": True,
                "locales": ["zh", "en"],
            },
            {
                "id": "cloudgw",
                "order": 2,
                "status": "healthy",
                "locales": ["zh", "en"],
                "first_run": True,
            },
            {
                "id": "cometapi",
                "order": 3,
                "status": "healthy",
                "locales": ["en"],
                "first_run": False,
                "register_url": "https://www.cometapi.com/?ref=kris",
            },
            {
                "id": "novita",
                "order": 4,
                "status": "healthy",
                "locales": ["en"],
                "first_run": False,
                "register_url": "https://novita.ai/?ref=nzvindf",
            },
        ],
    )
    client = _client(
        tmp_path / "fr",
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, payload),
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )
    assert client.refresh_sync() == "ok"
    en = client.view(locale="en")
    assert en["choices"] == ["apimart", "cloudgw", "cometapi", "novita", "other"]
    assert en["default"] == "apimart"
    assert en["first_run_choices"] == ["apimart", "cloudgw", "other"]
    assert en["first_run_default"] == "apimart"
    assert en["by_locale"]["en"]["first_run_choices"] == ["apimart", "cloudgw", "other"]
    assert en["by_locale"]["zh"]["first_run_choices"] == ["apimart", "cloudgw", "other"]
    assert en["register_urls"]["cometapi"] == "https://www.cometapi.com/?ref=kris"

    # When the default sponsor itself has first_run=False, first_run_default falls back to the first visible modal choice.
    fallback_payload = _payload(
        sequence=28,
        sponsors=[
            {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "first_run": False},
            {"id": "cometapi", "order": 2, "status": "healthy", "first_run": True},
        ],
    )
    fb_client = _client(
        tmp_path / "fr-fallback",
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, fallback_payload),
    )
    assert fb_client.refresh_sync() == "ok"
    fb = fb_client.view(locale="en")
    assert fb["choices"] == ["apimart", "cometapi", "other"]
    assert fb["default"] == "apimart"
    assert fb["first_run_choices"] == ["cometapi", "other"]
    assert fb["first_run_default"] == "cometapi"

    # Non-boolean first_run must be rejected.
    bad_payload = _payload(
        sequence=29,
        sponsors=[{"id": "apimart", "order": 1, "status": "healthy", "first_run": "no"}],
    )
    bad_client = _client(
        tmp_path / "fr-bad",
        private,
        public,
        lambda url, timeout, max_bytes: _envelope(private, bad_payload),
    )
    assert bad_client.refresh_sync() == "sponsors"


def test_cometapi_is_trusted_for_overseas_promo_and_rejects_foreign_host(tmp_path, profiles):
    assert sponsor_promo.builtin_sponsor_hosts()["cometapi"] == "www.cometapi.com"
    private, public = _keys()
    overseas = ["en", "ja", "ko", "es", "fr", "pt", "ru", "id", "tr", "vi", "de", "it", "pl", "th", "nl", "uk", "hi", "ar"]
    good = _payload(sequence=30, sponsors=[
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "locales": ["zh"]},
        {
            "id": "cometapi",
            "order": 2,
            "status": "healthy",
            "new_user_default": True,
            "locales": overseas,
            "register_url": "https://www.cometapi.com/?ref=kris",
        },
    ])
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, good))
    assert client.refresh_sync() == "ok"
    assert client.view(locale="en")["choices"] == ["cometapi", "other"]
    assert client.view(locale="en")["default"] == "cometapi"
    assert client.view(locale="en")["register_urls"] == {"cometapi": "https://www.cometapi.com/?ref=kris"}
    assert client.view(locale="zh")["choices"] == ["apimart", "other"]

    bad = _payload(sequence=31, sponsors=[
        {"id": "cometapi", "order": 1, "status": "healthy", "register_url": "https://evil.example/?ref=kris"},
    ])
    bad_client = _client(tmp_path / "bad", private, public, lambda url, timeout, max_bytes: _envelope(private, bad))
    assert bad_client.refresh_sync() == "sponsors"


def test_novita_and_poyo_are_trusted_for_overseas_promo(tmp_path, profiles):
    hosts = sponsor_promo.builtin_sponsor_hosts()
    assert hosts["novita"] == "novita.ai"
    assert hosts["poyo"] == "poyo.ai"
    private, public = _keys()
    overseas = ["en", "ja", "ko", "es", "fr", "pt", "ru", "id", "tr", "vi", "de", "it", "pl", "th", "nl", "uk", "hi", "ar"]
    good = _payload(sequence=32, sponsors=[
        {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True, "locales": ["zh"]},
        {
            "id": "novita",
            "order": 2,
            "status": "healthy",
            "new_user_default": True,
            "locales": overseas,
            "register_url": "https://novita.ai/?ref=nzvindf&utm_source=affiliate",
        },
        {
            "id": "poyo",
            "order": 3,
            "status": "healthy",
            "locales": overseas,
            "register_url": "https://poyo.ai/?affiliate_code=christ520482&open_signup=1",
        },
    ])
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, good))
    assert client.refresh_sync() == "ok"
    en = client.view(locale="en")
    assert en["choices"] == ["novita", "poyo", "other"]
    assert en["default"] == "novita"
    assert en["register_urls"]["novita"] == "https://novita.ai/?ref=nzvindf&utm_source=affiliate"
    assert en["register_urls"]["poyo"] == "https://poyo.ai/?affiliate_code=christ520482&open_signup=1"


def _dynamic_provider(**overrides):
    spec = {
        "id": "cloudgw",
        "name": {"zh": "云网关", "en": "CloudGW"},
        "base_url": "https://router.cloudgw.example/api/v1",
        "register_url": "https://www.cloudgw.example/?from=AutoClip",
        "docs_url": "https://console.cloudgw.example/keys",
        "hint": {"zh": "测试云网关。", "en": "Test cloud gateway."},
        "offer": {"zh": "送5元", "en": "$5 credit"},
        "icon_url": "https://cdn.cloudgw.example/icon.png",
        "capabilities": ["language", "image", "video"],
        "candidates": {"analysis": ["gpt-5-mini"], "vision": ["gpt-5-mini"]},
        "group": "popular",
    }
    spec.update(overrides)
    return spec


def test_v2_dynamic_provider_signed_promotion_and_v2_fallback(tmp_path, profiles):
    private, public = _keys()
    v2_payload = _payload(
        sequence=40,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[_dynamic_provider()],
        sponsors=[
            {
                "id": "cloudgw",
                "order": 1,
                "status": "healthy",
                "new_user_default": True,
                "locales": ["zh"],
                "register_url": "https://www.cloudgw.example/?from=AutoClip",
            },
            {
                "id": "apimart",
                "order": 2,
                "status": "healthy",
                "new_user_default": True,
                "locales": ["en"],
            },
        ],
    )
    requested = []

    def http_v2(url, timeout, max_bytes):
        requested.append(url)
        return _envelope(private, v2_payload)

    client = _client(
        tmp_path / "v2",
        private,
        public,
        http_v2,
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )
    assert client.refresh_sync() == "ok"
    assert requested == ["https://static.example/autoclip/sponsor-promo-v2.json"]
    zh_view = client.view(locale="zh")
    assert zh_view["choices"] == ["cloudgw", "other"]
    assert zh_view["default"] == "cloudgw"
    assert zh_view["register_urls"]["cloudgw"] == "https://www.cloudgw.example/?from=AutoClip"
    assert len(zh_view["providers"]) == 1
    assert zh_view["providers"][0]["id"] == "cloudgw"
    assert zh_view["providers"][0]["base_url"] == "https://router.cloudgw.example/api/v1"
    en_view = client.view(locale="en")
    assert en_view["choices"] == ["apimart", "other"]
    assert en_view["default"] == "apimart"

    # When v2_url fails (e.g., 404 before v2 is published), client falls back cleanly to v1 url.
    fallback_urls = []
    v1_payload = _payload(sequence=41)

    def http_fallback(url, timeout, max_bytes):
        fallback_urls.append(url)
        if url.endswith("sponsor-promo-v2.json"):
            raise OSError("404 not found")
        return _envelope(private, v1_payload)

    fb_client = _client(
        tmp_path / "fallback",
        private,
        public,
        http_fallback,
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )
    assert fb_client.refresh_sync() == "ok"
    assert fallback_urls == [
        "https://static.example/autoclip/sponsor-promo-v2.json",
        "https://static.example/autoclip/sponsor-promo.json",
    ]
    assert fb_client.view()["default"] == "apimart"
    assert "providers" not in fb_client.view()


@pytest.mark.parametrize("bad_payload,expected_reason", [
    # v1 schema must reject providers[]
    (_payload(sequence=50, providers=[_dynamic_provider()]), "schema"),
    # Built-in provider IDs can never be shadowed by dynamic providers
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(id="openai")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(id="apimart")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(id="dashscope")]), "providers"),
    # Non-HTTPS, loopback, private IP, and /chat/completions endpoints must be rejected
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(base_url="http://router.cloudgw.example/v1")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(base_url="https://localhost/v1")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(base_url="https://127.0.0.1/v1")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(base_url="https://10.0.0.1/v1")]), "providers"),
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(base_url="https://router.cloudgw.example/v1/chat/completions")]), "providers"),
    # HTML / script injection in localized strings must be rejected
    (_payload(sequence=50, schema=sponsor_promo.SCHEMA_V2, providers=[_dynamic_provider(name={"zh": "<script>x</script>", "en": "Bad"})]), "providers"),
    # Mismatched register_url host in sponsors[] for dynamic provider must be rejected
    (_payload(
        sequence=50,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[_dynamic_provider()],
        sponsors=[{"id": "cloudgw", "order": 1, "status": "healthy", "register_url": "https://evil.example/?from=AutoClip"}],
    ), "sponsors"),
])
def test_v2_dynamic_provider_security_rejections(tmp_path, profiles, bad_payload, expected_reason):
    private, public = _keys()
    client = _client(tmp_path, private, public, lambda url, timeout, max_bytes: _envelope(private, bad_payload))
    assert client.refresh_sync() == expected_reason
    assert client.view()["source"] == "bundled"


def test_v2_dynamic_provider_crud_and_hot_update(tmp_path, profiles):
    """Cloud v2 config supports full Create / Read / Update / Delete hot-updates without app restart."""
    private, public = _keys()
    secondary = _dynamic_provider(
        id="cloudgw2",
        name={"zh": "云网关二号", "en": "CloudGW2"},
        base_url="https://api.cloudgw2.example/v1",
        register_url="https://www.cloudgw2.example/?from=AutoClip",
        docs_url="https://docs.cloudgw2.example/keys",
    )
    stage = {
        "payload": _payload(
            sequence=60,
            schema=sponsor_promo.SCHEMA_V2,
            providers=[_dynamic_provider(), secondary],
            sponsors=[
                {
                    "id": "cloudgw",
                    "order": 1,
                    "status": "healthy",
                    "new_user_default": True,
                    "register_url": "https://www.cloudgw.example/?from=AutoClip",
                },
                {"id": "apimart", "order": 2, "status": "healthy"},
            ],
        )
    }

    def http(url, timeout, max_bytes):
        return _envelope(private, stage["payload"])

    client = _client(
        tmp_path / "crud",
        private,
        public,
        http,
        v2_url="https://static.example/autoclip/sponsor-promo-v2.json",
    )

    # Create + Read: both promoted and catalog-only dynamic providers are returned
    assert client.refresh_sync() == "ok"
    created = client.view(locale="zh")
    assert [p["id"] for p in created["providers"]] == ["cloudgw", "cloudgw2"]
    assert created["default"] == "cloudgw"
    assert created["choices"] == ["cloudgw", "apimart", "other"]

    # Update (hot-update on sequence+1): mutate fields, candidates, notice, and drop cloudgw2
    updated_primary = _dynamic_provider(
        name={"zh": "云网关 Pro", "en": "CloudGW Pro"},
        base_url="https://v2.cloudgw.example/api/v1",
        offer={"zh": "送20元", "en": "$20 credit"},
        candidates={"analysis": ["gpt-5"], "vision": ["gpt-5"]},
        group="recommended",
    )
    stage["payload"] = _payload(
        sequence=61,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[updated_primary],
        sponsors=[
            {
                "id": "cloudgw",
                "order": 1,
                "status": "fault",
                "notices": {"zh": "短暂维护", "en": "Brief maintenance"},
                "register_url": "https://www.cloudgw.example/?from=AutoClip",
            },
            {"id": "apimart", "order": 2, "status": "healthy", "new_user_default": True},
        ],
    )
    assert client.refresh_sync() == "ok"
    updated = client.view(locale="zh")
    assert [p["id"] for p in updated["providers"]] == ["cloudgw"]
    assert updated["providers"][0]["name"]["zh"] == "云网关 Pro"
    assert updated["providers"][0]["base_url"] == "https://v2.cloudgw.example/api/v1"
    assert updated["providers"][0]["offer"]["zh"] == "送20元"
    assert updated["providers"][0]["candidates"]["analysis"] == ["gpt-5"]
    assert updated["statuses"]["cloudgw"] == "fault"
    assert updated["notices"]["cloudgw"]["zh"] == "短暂维护"
    assert updated["default"] == "apimart"

    # Delete (hot-update on sequence+2): remove all dynamic providers cleanly
    stage["payload"] = _payload(
        sequence=62,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[],
        sponsors=[
            {"id": "apimart", "order": 1, "status": "healthy", "new_user_default": True},
        ],
    )
    assert client.refresh_sync() == "ok"
    deleted = client.view(locale="zh")
    assert "providers" not in deleted
    assert deleted["choices"] == ["apimart", "other"]
    assert deleted["default"] == "apimart"


def test_fsync_dir_skips_directory_open_on_windows(tmp_path, profiles, monkeypatch):
    """Windows forbids os.open(directory, O_RDONLY); _commit must still persist cleanly."""
    import backend.core.sponsor_promo_client as client_mod

    private, public = _keys()
    real_open = client_mod.os.open

    def win_open(path, flags, *args, **kwargs):
        if Path(path).is_dir():
            raise PermissionError(13, "Permission denied", str(path))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(client_mod.sys, "platform", "win32")
    monkeypatch.setattr(client_mod.os, "open", win_open)
    payload = _payload(
        sequence=70,
        schema=sponsor_promo.SCHEMA_V2,
        providers=[_dynamic_provider()],
        sponsors=[
            {"id": "cloudgw", "order": 1, "status": "healthy", "new_user_default": True, "register_url": "https://www.cloudgw.example/?from=AutoClip"},
        ],
    )
    client = _client(tmp_path / "win", private, public, lambda url, timeout, max_bytes: _envelope(private, payload))
    assert client.refresh_sync() == "ok"
    shown = client.view(locale="zh")
    assert shown["default"] == "cloudgw"
    assert [p["id"] for p in shown["providers"]] == ["cloudgw"]


def test_v2_fallback_mirror_recovers_when_primary_times_out(tmp_path, profiles):
    """When primary workers.dev v2_url times out (e.g. China mainland), client falls back to v2_fallback_urls."""
    private, public = _keys()
    payload = _payload(
        sequence=80,
        schema=sponsor_promo.SCHEMA_V2,
        max_app="1.9.9",
        providers=[_dynamic_provider()],
        sponsors=[
            {"id": "cloudgw", "order": 1, "status": "healthy", "new_user_default": True, "register_url": "https://www.cloudgw.example/?from=AutoClip"},
            {"id": "apimart", "order": 2, "status": "healthy", "new_user_default": False},
        ],
    )
    seen_urls: list[str] = []

    def http_get(url, timeout, max_bytes):
        seen_urls.append(url)
        if "workers.dev" in url:
            raise TimeoutError("simulated workers.dev timeout")
        return _envelope(private, payload)

    cfg = PromoConfig(
        enabled=True,
        url="https://promo.workers.dev/sponsor-promo.json",
        fallback_urls=("https://cos.example/sponsor-promo.json",),
        v2_url="https://promo.workers.dev/sponsor-promo-v2.json",
        v2_fallback_urls=("https://cos.example/sponsor-promo-v2.json",),
        public_key=public,
        min_sequence=1,
        timeout_seconds=3,
    )
    client = SponsorPromoClient(cfg, data_dir=tmp_path, app_version="1.6.2", http_get=http_get, now=lambda: NOW, busy=lambda: False)
    assert client.refresh_sync() == "ok"
    assert seen_urls == [
        "https://promo.workers.dev/sponsor-promo-v2.json",
        "https://cos.example/sponsor-promo-v2.json",
    ]
    shown = client.view(locale="zh")
    assert shown["source"] == "cache"
    assert shown["sequence"] == 80
    assert shown["default"] == "cloudgw"
    assert [p["id"] for p in shown["providers"]] == ["cloudgw"]


def test_fallback_urls_reject_insecure_and_duplicate_entries():
    _, public = _keys()
    cfg = parse_config({
        "enabled": True,
        "url": "https://primary.example/v1.json",
        "v2_url": "https://primary.example/v2.json",
        "fallback_urls": [
            "http://insecure.example/v1.json",
            "https://user:pass@cred.example/v1.json",
            "https://primary.example/v1.json",
            "https://mirror1.example/v1.json",
            "https://mirror1.example/v1.json",
        ],
        "v2_fallback_urls": [
            "http://insecure.example/v2.json",
            "https://primary.example/v2.json",
            "https://mirror1.example/v2.json",
            "https://mirror2.example/v2.json",
        ],
        "public_key": public,
    })
    assert cfg.enabled is True
    assert cfg.fallback_urls == ("https://mirror1.example/v1.json",)
    assert cfg.v2_fallback_urls == ("https://mirror1.example/v2.json", "https://mirror2.example/v2.json")


def test_fallback_mirror_still_enforces_signature_and_watermark(tmp_path, profiles):
    private, public = _keys()
    good = _payload(
        sequence=85,
        schema=sponsor_promo.SCHEMA_V2,
        max_app="1.9.9",
        providers=[_dynamic_provider()],
        sponsors=[{"id": "cloudgw", "order": 1, "status": "healthy", "new_user_default": True, "register_url": "https://www.cloudgw.example/?from=AutoClip"}],
    )
    good_env = _envelope(private, good)
    bad_payload = json.loads(json.dumps({**good, "sequence": 86}))
    bad = _envelope(private, bad_payload)
    bad["payload"]["sponsors"][0]["id"] = "tampered"
    stage = {"doc": good_env}

    def http_get(url, timeout, max_bytes):
        if "workers.dev" in url:
            raise TimeoutError("unreachable")
        return stage["doc"]

    cfg = PromoConfig(
        enabled=True,
        url="https://promo.workers.dev/sponsor-promo.json",
        v2_url="https://promo.workers.dev/sponsor-promo-v2.json",
        v2_fallback_urls=("https://cos.example/sponsor-promo-v2.json",),
        public_key=public,
        min_sequence=1,
    )
    client = SponsorPromoClient(cfg, data_dir=tmp_path, app_version="1.6.2", http_get=http_get, now=lambda: NOW, busy=lambda: False)
    assert client.refresh_sync() == "ok"
    stage["doc"] = bad
    assert client.refresh_sync() == "unsigned"
    assert client.view(locale="zh")["sequence"] == 85
