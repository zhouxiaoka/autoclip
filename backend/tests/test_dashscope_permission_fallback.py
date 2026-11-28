"""Regression test for Issue #602: Bailian (dashscope) preset candidate 403/quota fallback."""
from __future__ import annotations

from backend.core.provider_model_fetch import AccountModelList
from backend.core.upstream_errors import ClassifiedUpstreamError, UpstreamErrorType
from backend.services import provider_validation as pv


def _dashscope_conn() -> pv.ai_models.Connection:
    return pv.ai_models.Connection(
        id="ds1",
        name="阿里云百炼",
        provider="dashscope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-bailian-test-key",
    )


def test_dashscope_preset_permission_denied_falls_back_to_accessible_model(monkeypatch):
    """When Bailian /models lists all 198 models and the first preset candidate (qwen3.8-flash)
    returns 403 permission_denied, validation falls back to another accessible recommended model
    (e.g. qwen-plus) instead of failing the entire provider connection."""
    live = AccountModelList(
        ok=True,
        source="live",
        models=["qwen3.8-flash", "qwen3.8-max", "qwen-vl-plus", "qwen-plus"],
        recommended={"analysis": ["qwen3.8-flash", "qwen3.8-max", "qwen-vl-plus", "qwen-plus"]},
    )
    monkeypatch.setattr(pv, "_get_models", lambda *a, **k: (live.models, None, live))
    probed: list[str] = []

    def fake_probe(base, api_key, model, provider="compatible", *, options=None):
        probed.append(model)
        if model == "qwen-plus":
            return None
        return ClassifiedUpstreamError(
            UpstreamErrorType.PERMISSION_DENIED,
            retryable=False,
            hint_key="permission_denied",
        )

    monkeypatch.setattr(pv, "_probe", fake_probe)
    res = pv._validate_resolved(_dashscope_conn(), "qwen3.8-flash", purpose="analysis")
    assert res.ok is True
    assert res.validated_model == "qwen-plus"
    assert res.as_api()["validated_model"] == "qwen-plus"
    assert "qwen3.8-flash" in probed
    assert "qwen-plus" in probed


def test_dashscope_preset_quota_on_single_model_falls_back_to_working_default(monkeypatch):
    """Free-tier-exhausted error on qwen3.8-flash falls back when qwen-plus is callable."""
    live = AccountModelList(
        ok=True,
        source="live",
        models=["qwen3.8-flash", "qwen-plus"],
        recommended={"analysis": ["qwen3.8-flash", "qwen-plus"]},
    )
    monkeypatch.setattr(pv, "_get_models", lambda *a, **k: (live.models, None, live))

    def fake_probe(base, api_key, model, provider="compatible", *, options=None):
        if model == "qwen-plus":
            return None
        return ClassifiedUpstreamError(
            UpstreamErrorType.INSUFFICIENT_QUOTA,
            retryable=False,
            hint_key="insufficient_quota",
        )

    monkeypatch.setattr(pv, "_probe", fake_probe)
    res = pv._validate_resolved(_dashscope_conn(), "qwen3.8-flash", purpose="analysis")
    assert res.ok is True
    assert res.validated_model == "qwen-plus"


def test_dashscope_account_wide_permission_denied_still_fails(monkeypatch):
    """When every candidate returns 403, validation still fails with permission_denied."""
    live = AccountModelList(
        ok=True,
        source="live",
        models=["qwen3.8-flash", "qwen-plus"],
        recommended={"analysis": ["qwen3.8-flash", "qwen-plus"]},
    )
    monkeypatch.setattr(pv, "_get_models", lambda *a, **k: (live.models, None, live))
    monkeypatch.setattr(
        pv,
        "_probe",
        lambda *a, **k: ClassifiedUpstreamError(
            UpstreamErrorType.PERMISSION_DENIED,
            retryable=False,
            hint_key="permission_denied",
        ),
    )
    res = pv._validate_resolved(_dashscope_conn(), "qwen3.8-flash", purpose="analysis")
    assert res.ok is False
    assert res.error_type == "permission_denied"


def test_dashscope_user_explicit_non_preset_model_does_not_silently_fallback(monkeypatch):
    """If the user explicitly chose a non-preset model that returns 403, do not silently swap it."""
    live = AccountModelList(
        ok=True,
        source="live",
        models=["deepseek-v4.1-flash-1017", "qwen-plus"],
        recommended={"analysis": ["qwen-plus"]},
    )
    monkeypatch.setattr(pv, "_get_models", lambda *a, **k: (live.models, None, live))
    probed: list[str] = []

    def fake_probe(base, api_key, model, provider="compatible", *, options=None):
        probed.append(model)
        if model == "qwen-plus":
            return None
        return ClassifiedUpstreamError(
            UpstreamErrorType.PERMISSION_DENIED,
            retryable=False,
            hint_key="permission_denied",
        )

    monkeypatch.setattr(pv, "_probe", fake_probe)
    res = pv._validate_resolved(_dashscope_conn(), "deepseek-v4.1-flash-1017", purpose="analysis")
    assert res.ok is False
    assert res.error_type == "permission_denied"
    assert probed == ["deepseek-v4.1-flash-1017"]
