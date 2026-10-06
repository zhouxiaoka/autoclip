"""封面：提示词、OCR 校对、本地排版、截帧兜底、生图 HTTP 替身。不连真生图服务。"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(d))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(d))
    monkeypatch.delenv("IMAGE_API_KEY", raising=False)
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.delenv("IMAGE_BASE_URL", raising=False)
    d.mkdir()
    return d


def _jpeg(color=(80, 80, 78), size=(640, 360)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _project(data_dir: Path, project_id: str = "p1", clip_id: str = "1") -> Path:
    root = data_dir / "projects" / project_id
    (root / "raw").mkdir(parents=True)
    (root / "metadata").mkdir(parents=True)
    (root / "metadata" / "clips_metadata.json").write_text(json.dumps([{
        "id": clip_id,
        "generated_title": "为什么大厂都在裁员，普通人该怎么办？",
        "start_time": "00:00:01,000",
        "end_time": "00:00:20,000",
    }]), encoding="utf-8")
    # CI 没有 ffmpeg；测试用假成片 + 假截帧，不连真编码器。
    (root / "raw" / "input.mp4").write_bytes(b"mp4")
    return root


@pytest.fixture
def fake_frame(monkeypatch):
    jpeg = _jpeg()
    monkeypatch.setattr("backend.services.cover.extract_frame_jpeg", lambda *_a, **_k: jpeg)
    return jpeg


class _Resp:
    def __init__(self, status_code=200, payload=None, content=b"", text=""):
        self.status_code = status_code
        self._payload = payload
        self.content = content
        self.text = text if text or payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _take(self, method, url, kw):
        self.calls.append((method, url, {k: v for k, v in kw.items() if k != "files"}))
        return self.responses.pop(0) if self.responses else _Resp(200, {})

    def get(self, url, **kw):
        return self._take("GET", url, kw)

    def post(self, url, **kw):
        return self._take("POST", url, kw)


def test_split_title_and_prompt_keep_chinese_verbatim():
    from backend.services.cover import build_prompt, split_title, title_matches

    lines = split_title("为什么大厂都在裁员，普通人该怎么办？")
    assert len(lines) == 2
    prompt = build_prompt(
        title_lines=lines, subtitle="3个真实案例", badge="职场观察",
        platform="bilibili", content_type="knowledge", has_reference=True,
    )
    assert "为什么大厂都在裁员" in prompt
    assert "普通人该怎么办" in prompt
    assert "参考图" in prompt
    assert title_matches("为什么大厂都在裁员\n普通人该怎么办？", lines)
    assert not title_matches("为什么大厂都在裁人", lines)


def test_config_file_is_private(data_dir):
    from backend.services import cover as cover_svc

    saved = cover_svc.save_config(
        enabled=True, provider="openai", model="gpt-image-1",
        api_key="sk-test-cover-key", allow_send_frame=False,
    )
    assert saved.configured and saved.enabled
    assert "sk-test" not in json.dumps(saved.public())
    mode = (data_dir / "cover.json").stat().st_mode & 0o777
    assert mode == 0o600


def test_local_overlay_and_frame_fallback_do_not_need_api(data_dir, fake_frame):
    from backend.services import cover as cover_svc

    _project(data_dir)
    result = cover_svc.generate_cover(
        project_id="p1", clip_id="1", platform="bilibili",
        title="越努力越焦虑", subtitle="心理学解释", badge="科普",
        force_local=True,
    )
    assert result["ok"] and result["method"] in ("local_overlay", "frame")
    path = Path(result["path"])
    assert path.exists() and path.stat().st_size > 500
    img = Image.open(path)
    assert img.size == (1146, 717)


def test_openai_provider_uses_edits_then_falls_back_on_unsupported(data_dir):
    from backend.core.image_providers import ImageError, ImageRequest, generate_openai

    session = _Session([_Resp(404, {"error": {"message": "Unknown URL"}}), _Resp(404, {"error": {"message": "Unknown URL"}})])
    with pytest.raises(ImageError):
        generate_openai(
            api_key="sk",
            base_url="http://127.0.0.1:9/v1",
            request=ImageRequest(prompt="hi", width=1280, height=720, reference=b"jpg", model="gpt-image-1"),
            session=session,
        )
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1].endswith("/images/edits")


def test_gpt_image_2_gets_the_platform_ratio_and_falls_back_to_the_legacy_one(data_dir):
    import base64
    from backend.core.image_providers import ImageRequest, generate_openai, openai_size

    assert openai_size(1080, 1920, "gpt-image-2.5-flare") == "1088x1920"
    assert openai_size(1920, 1080, "gpt-image-2.5-flare") == "1920x1088"
    assert openai_size(1080, 1920, "gpt-image-1") == "1024x1536"
    buf = io.BytesIO()
    Image.new("RGB", (32, 32)).save(buf, format="PNG")
    ok = _Resp(200, {"data": [{"b64_json": base64.b64encode(buf.getvalue()).decode("ascii")}]})
    session = _Session([_Resp(400, {"error": {"message": "Invalid size '1088x1920'"}}), ok])
    generate_openai(api_key="sk", base_url="http://127.0.0.1:9/v1", session=session,
                    request=ImageRequest(prompt="hi", width=1080, height=1920, reference=b"jpg", model="gpt-image-2.5-flare"))
    assert [call[2]["data"]["size"] for call in session.calls] == ["1088x1920", "1024x1536"]


def test_seedream_uses_generations_with_image_field(data_dir):
    from backend.core.image_providers import ImageRequest, generate_image, is_seedream, seedream_size

    assert is_seedream(provider="seedream")
    assert is_seedream(model="doubao-seedream-5-0-260128")
    assert is_seedream(base_url="https://ark.cn-beijing.volces.com/api/v3")
    assert seedream_size(1280, 720) == "2560x1440"
    assert seedream_size(720, 1280) == "1440x2560"

    png = Image.new("RGB", (32, 32), (10, 10, 10))
    buf = io.BytesIO()
    png.save(buf, format="PNG")
    import base64
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    session = _Session([_Resp(200, {"data": [{"b64_json": b64}]})])
    out = generate_image(
        provider="seedream",
        api_key="ark-key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        request=ImageRequest(
            prompt="封面标题",
            width=1280,
            height=720,
            reference=b"\xff\xd8\xffframe",
            model="doubao-seedream-5-0-260128",
        ),
        session=session,
    )
    assert out
    method, url, snap = session.calls[0]
    assert method == "POST"
    assert url.endswith("/images/generations")
    body = snap["json"]
    assert body["model"] == "doubao-seedream-5-0-260128"
    assert body["size"] == "2560x1440"
    assert str(body["image"]).startswith("data:image/jpeg;base64,")
    assert body.get("watermark") is False
    assert "n" not in body


def test_image_urls_from_a_remote_provider_never_reach_this_machine(data_dir):
    from backend.core.image_providers import ImageError, _download

    for url in ("http://127.0.0.1:8000/api/v1/settings", "http://localhost/x.png", "http://10.0.0.5/x.png",
                "http://169.254.169.254/latest", "file:///etc/passwd"):
        session = _Session([_Resp(200, content=b"img")])
        with pytest.raises(ImageError):
            _download(session, url)
        assert session.calls == [], url
    redirected = _Session([_Resp(302, content=b""), _Resp(200, content=b"img")])
    redirected.responses[0].headers = {"location": "http://127.0.0.1/x.png"}
    with pytest.raises(ImageError):
        _download(redirected, "https://cdn.example.com/x.png")
    assert len(redirected.calls) == 1, "the redirect to a local address is not followed"
    local = _Session([_Resp(200, content=b"img")])
    local.autoclip_local = True
    assert _download(local, "http://127.0.0.1:7860/out.png") == b"img", "a local image server may serve local URLs"


def test_seedream_text_to_image_skips_n_and_uses_url(data_dir):
    from backend.core.image_providers import ImageRequest, generate_openai

    session = _Session([
        _Resp(200, {"data": [{"url": "https://ark-cdn.example.com/out.png"}]}),
        _Resp(200, content=b"PNGDATA"),
    ])
    out = generate_openai(
        api_key="ark",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        request=ImageRequest(prompt="横屏封面", width=1280, height=720, model="doubao-seedream-4-5-251128"),
        session=session,
        force_seedream=True,
    )
    assert out == b"PNGDATA"
    body = session.calls[0][2]["json"]
    assert body["response_format"] == "url"
    assert body["size"] == "2560x1440"
    assert "n" not in body


def test_openai_generations_returns_b64(data_dir):
    from backend.core.image_providers import ImageRequest, generate_openai

    img = Image.new("RGB", (64, 64), (20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    session = _Session([_Resp(200, {"data": [{"b64_json": b64}]})])
    out = generate_openai(
        api_key="sk",
        base_url="http://127.0.0.1:9/v1",
        request=ImageRequest(prompt="封面", width=1280, height=720, model="gpt-image-1"),
        session=session,
    )
    assert out.startswith(b"\x89PNG") or len(out) > 10


def test_ensure_publish_cover_prefers_designed_then_frame(data_dir, fake_frame):
    from backend.services import cover as cover_svc

    _project(data_dir)
    designed = cover_svc.generate_cover(
        project_id="p1", clip_id="1", force_local=True, title="设计封面",
    )
    jpeg = cover_svc.ensure_publish_cover_jpeg("p1", "1", platform="bilibili")
    assert jpeg == Path(designed["path"]).read_bytes()

    Path(designed["path"]).unlink()
    jpeg2 = cover_svc.ensure_publish_cover_jpeg("p1", "1", platform="bilibili")
    assert jpeg2 and len(jpeg2) > 100


def test_model_failure_falls_back_to_local_or_frame(data_dir, fake_frame, monkeypatch):
    from backend.core.image_providers import ImageError
    from backend.services import cover as cover_svc

    _project(data_dir)
    cover_svc.save_config(enabled=True, provider="openai", api_key="sk-x", allow_send_frame=True)

    def boom(**kwargs):
        raise ImageError("upstream down")

    monkeypatch.setattr("backend.services.cover.generate_image", boom)
    result = cover_svc.generate_cover(
        project_id="p1", clip_id="1", title="翻盘高光", content_type="game",
    )
    assert result["ok"]
    assert result["method"] in ("local_overlay", "frame")
    assert result.get("warning")


class _TextSettings:
    def __init__(self, settings):
        self.settings = settings


def _text_keys(monkeypatch, **keys):
    from backend.core import llm_manager
    monkeypatch.setattr(llm_manager, "get_llm_manager", lambda: _TextSettings(keys))


def test_cover_reuses_same_family_text_key_without_persisting(data_dir, monkeypatch):
    from backend.services import cover
    for name in ("IMAGE_API_KEY", "IMAGE_PROVIDER", "IMAGE_BASE_URL", "IMAGE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    _text_keys(monkeypatch, dashscope_api_key="sk-dashscope-text", seed_api_key="ark-seed", infistar_api_key="sk-infistar")
    cover.save_config(enabled=True, provider="dashscope", model="wanx2.1-t2i-turbo", mode="custom")
    cfg = cover.load_config()
    assert cfg.api_key == "sk-dashscope-text" and cfg.key_source == "text_model"
    assert "sk-dashscope-text" not in cover.config_path().read_text()
    cover.save_config(provider="seedream")
    assert cover.load_config().api_key == "ark-seed"
    cover.save_config(provider="openai", base_url="https://infistar.cc/v1")
    assert cover.load_config().api_key == "sk-infistar"
    # 自己填的 key 优先，且会保存
    cover.save_config(api_key="sk-own-cover-key")
    cfg = cover.load_config()
    assert cfg.api_key == "sk-own-cover-key" and cfg.key_source == "own"


def test_cover_title_check_uses_vision_model_unless_overridden(data_dir, monkeypatch):
    from backend.services import cover
    from backend.services.studio import vision_settings
    monkeypatch.setattr(vision_settings, "effective", lambda: {"base_url": "https://infistar.cc/v1", "api_key": "sk-v", "model": "gemini-3.8-flash"})
    cfg = cover.CoverConfig(provider="seedream", model="doubao-seedream-5-0-260128", api_key="ark", base_url="https://ark.cn-beijing.volces.com/api/v3")
    assert cover.verify_endpoint(cfg) == {"provider": "openai", "api_key": "sk-v", "base_url": "https://infistar.cc/v1", "model": "gemini-3.8-flash"}
    cfg.ocr_model = "doubao-1.5-vision-pro-32k"
    assert cover.verify_endpoint(cfg)["model"] == "doubao-1.5-vision-pro-32k"



def test_cover_follows_text_model_service(data_dir, monkeypatch):
    from backend.services import cover
    for name in ("IMAGE_API_KEY", "IMAGE_PROVIDER", "IMAGE_BASE_URL", "IMAGE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    # 没保存过：跟随模型，但默认不开
    _text_keys(monkeypatch, llm_provider="openai", cloud_preset="seed", seed_api_key="ark-seed")
    cfg = cover.load_config()
    assert cfg.mode == "text_model" and not cfg.enabled
    cover.save_config(enabled=True, model="doubao-seedream-5-0-260128", mode="text_model")
    cfg = cover.load_config()
    assert (cfg.provider, cfg.api_key, cfg.enabled, cfg.configured) == ("seedream", "ark-seed", True, True)
    assert "ark-seed" not in cover.config_path().read_text()
    # 换成 Infistar：跟着换到 OpenAI 兼容 images + Infistar 的 key
    _text_keys(monkeypatch, llm_provider="openai", cloud_preset="infistar", infistar_api_key="sk-inf", openai_base_url="https://infistar.cc/v1")
    cfg = cover.load_config()
    assert (cfg.provider, cfg.base_url, cfg.api_key) == ("openai", "https://infistar.cc/v1", "sk-inf")
    # 88API uses its own credentials and gateway when following the text service.
    _text_keys(monkeypatch, llm_provider="openai", cloud_preset="api88", api88_api_key="sk-88", openai_base_url="https://88api.ai/v1")
    cfg = cover.load_config()
    assert (cfg.provider, cfg.base_url, cfg.api_key) == ("openai", "https://88api.ai/v1", "sk-88")
    assert cover._text_model_key("openai", "https://88api.ai/v1") == "sk-88"
    assert cover._text_model_key("openai", "https://88api.ai.evil.example/v1") == ""
    # 换成没有生图的 DeepSeek：自动关掉，封面走截帧
    _text_keys(monkeypatch, llm_provider="openai", cloud_preset="deepseek", deepseek_api_key="sk-ds")
    cfg = cover.load_config()
    assert not cfg.enabled and not cfg.configured


def test_model_catalog_marks_vision_and_image_models():
    from backend.core import model_catalog as mc
    assert mc.supports_vision("gemini-3.8-flash") and mc.supports_vision("claude-sonnet-5-5")
    assert mc.supports_vision("doubao-seed-2-1-lite-260915") and mc.supports_vision("qwen-vl-plus")
    assert not mc.supports_vision("deepseek-flash") and not mc.supports_vision("qwen-plus")
    assert mc.IMAGE_MODELS["dashscope"][0].startswith("wanx") and "deepseek" not in mc.IMAGE_MODELS


def test_gemini_cover_uses_native_multimodal_request():
    import base64
    from backend.core.image_providers import generate_image, ImageRequest
    image = _jpeg()
    session = _Session([_Resp(payload={'candidates': [{'content': {'parts': [{'text': 'caption'}, {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(image).decode()}}]}}]})])
    result = generate_image(provider='gemini', api_key='test-key', base_url='', request=ImageRequest('cover', 1920, 1080, reference=image, model='gemini-3.1-flash-image'), session=session)
    assert result == image
    method, url, args = session.calls[0]
    assert url.endswith('/models/gemini-3.1-flash-image:generateContent')
    assert args['headers']['x-goog-api-key'] == 'test-key'
    assert args['json']['contents'][0]['parts'][0]['inlineData']['data']
    assert args['json']['generationConfig']['responseModalities'] == ['TEXT', 'IMAGE']


@pytest.mark.parametrize('model,route,asynchronous', [('qwen-image-2.0', 'multimodal-generation', False), ('wan2.7-image', 'image-generation', True), ('wan2.6-t2i', 'image-generation', True)])
def test_modern_dashscope_routes_and_extracts_images(model, route, asynchronous):
    from backend.core.image_providers import generate_image, ImageRequest
    image = _jpeg()
    output = {'output': {'choices': [{'message': {'content': [{'image': 'https://image.example/cover.jpg'}]}}]}}
    responses = [_Resp(payload={'output': {'task_id': 'task', 'task_status': 'PENDING'}}), _Resp(payload=output)] if asynchronous else [_Resp(payload=output)]
    session = _Session(responses + [_Resp(content=image)])
    result = generate_image(provider='dashscope', api_key='test-key', base_url='', request=ImageRequest('cover', 1920, 1080, model=model), session=session, poll_interval=0)
    assert result == image
    args = session.calls[0][2]
    assert session.calls[0][1].endswith(f'/services/aigc/{route}/generation')
    assert ('X-DashScope-Async' in args['headers']) == asynchronous
    assert args['json']['input']['messages'][0]['content'] == [{'text': 'cover'}]
    assert args['json']['parameters']['n'] == 1


def test_grok_and_glm_use_vendor_image_parameters():
    import base64
    from backend.core.image_providers import generate_image, ImageRequest
    image = _jpeg()
    for provider, model in [('grok', 'grok-imagine-image-2.0'), ('glm', 'glm-image')]:
        session = _Session([_Resp(payload={'data': [{'b64_json': base64.b64encode(image).decode()}]})])
        assert generate_image(provider=provider, api_key='test-key', base_url='', request=ImageRequest('cover', 1920, 1080, model=model), session=session) == image
        body = session.calls[0][2]['json']
        if provider == 'grok':
            assert body['aspect_ratio'] == '16:9' and 'size' not in body
        else:
            assert body['size'] == '1728x960' and 'response_format' not in body


@pytest.mark.parametrize('failure', ['InvalidSchema', 'InvalidURL', 'MissingSchema', 'ConnectionError', 'Timeout'])
def test_request_failure_still_produces_local_cover_without_private_error(data_dir, fake_frame, failure):
    import requests
    from backend.services import cover
    _project(data_dir)
    cover.save_config(enabled=True, provider='openai', api_key='synthetic-key', allow_send_frame=True)
    calls = []
    class BrokenSession:
        def post(self, *args, **kwargs):
            calls.append(1)
            raise getattr(requests.exceptions, failure)('private-url synthetic-key private-provider-body')
    result = cover.generate_cover(project_id='p1', clip_id='1', title='采访观点', session=BrokenSession())
    assert result['ok'] and result['method'] in ('local_overlay', 'frame')
    assert Path(result['path']).read_bytes().startswith(b'\xff\xd8')
    assert len(calls) == 1  # A failed paid request is not replayed automatically.
    assert result['warning'] and 'private-' not in result['warning'] and 'synthetic-key' not in result['warning']


def test_ocr_connection_failure_preserves_already_generated_cover(data_dir, fake_frame):
    import requests
    import base64
    from backend.services import cover
    _project(data_dir)
    cover.save_config(enabled=True, provider='openai', api_key='synthetic-key', allow_send_frame=True)
    calls = []
    class InterruptedOCR:
        def post(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                return _Resp(200, {'data': [{'b64_json': base64.b64encode(_jpeg()).decode()}]})
            raise requests.exceptions.ConnectionError('private-url synthetic-key')
    result = cover.generate_cover(project_id='p1', clip_id='1', title='采访观点', session=InterruptedOCR())
    assert result['ok'] and result['method'] == 'model'
    assert len(calls) == 2
    assert Path(result['path']).read_bytes().startswith(b'\xff\xd8')


def test_unexpected_image_programming_failure_is_not_hidden_as_network(data_dir, fake_frame):
    from backend.core.image_providers import generate_image, ImageRequest
    class DefectiveSession:
        def post(self, *args, **kwargs):
            raise RuntimeError('synthetic programming defect')
    with pytest.raises(RuntimeError, match='synthetic programming defect'):
        generate_image(provider='openai', api_key='synthetic-key', base_url='',
                       request=ImageRequest('cover', 1080, 1920), session=DefectiveSession())
