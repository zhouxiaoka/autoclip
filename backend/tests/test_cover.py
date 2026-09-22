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
    # 合成一段短视频给 ffmpeg 截帧
    video = root / "raw" / "input.mp4"
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=gray:s=640x360:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True)
    return root


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


def test_local_overlay_and_frame_fallback_do_not_need_api(data_dir):
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

    session = _Session([_Resp(404, {"error": {"message": "Unknown URL"}})])
    with pytest.raises(ImageError) as exc:
        generate_openai(
            api_key="sk",
            base_url="http://127.0.0.1:9/v1",
            request=ImageRequest(prompt="hi", width=1280, height=720, reference=b"jpg", model="gpt-image-1"),
            session=session,
        )
    assert exc.value.unsupported_edit
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1].endswith("/images/edits")


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


def test_ensure_publish_cover_prefers_designed_then_frame(data_dir):
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


def test_model_failure_falls_back_to_local_or_frame(data_dir, monkeypatch):
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
