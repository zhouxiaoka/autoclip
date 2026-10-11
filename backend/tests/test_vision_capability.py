"""视觉能力识别：OpenAI 新一代型号（gpt-5.x、gpt-6.x）和 o 系列。1.5.7 Windows 验收 S3。"""
import pytest

from backend.core.model_catalog import supports_vision


@pytest.mark.parametrize("model", [
    "gpt-6", "gpt-6.1", "gpt-6.1-sol", "GPT-6.1-Sol", "openai/gpt-6.1-sol", "gpt-6.2-mini",
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-5.4", "gpt-5.5", "gpt-5.6-terra",
    "gpt-4o", "gpt-4o-mini", "gpt-4o-2024-08-06", "gpt-4.1", "gpt-4.1-nano",
    "o1", "o1-pro", "o3", "o3-pro", "o4-mini", "o4-mini-deep-research",
])
def test_openai_models_that_take_images(model):
    assert supports_vision(model)


@pytest.mark.parametrize("model", [
    "gpt-3.5-turbo", "gpt-4", "gpt-4-turbo",
    "o1-mini", "o1-preview", "o3-mini",
    "gpt-4o-transcribe", "gpt-4o-mini-tts", "gpt-4o-search-preview", "gpt-realtime",
    "gpt-6-audio", "gpt-image-1", "text-embedding-3-large",
])
def test_openai_models_without_image_input(model):
    assert not supports_vision(model)


def test_non_openai_names_are_unchanged():
    assert supports_vision("claude-sonnet-5-5") and supports_vision("qwen-vl-plus")
    assert not supports_vision("qwen-plus") and not supports_vision("deepseek-flash")
    assert not supports_vision("llama-o3x")


@pytest.mark.parametrize("model, usable", [("gpt-6.1-sol", True), ("gpt-5.5", True), ("o3-mini", False)])
def test_auto_mode_reuses_the_text_model_for_vision(monkeypatch, model, usable):
    from backend.services.studio import vision_settings
    endpoint = {"base_url": "https://api.example.com/v1", "api_key": "sk-test", "model": model}
    monkeypatch.setattr(vision_settings, "text_model_endpoint", lambda: dict(endpoint))
    resolved = vision_settings._with_text_model({})
    assert resolved["text_model"] == model
    assert (resolved["model"] == model) is usable
