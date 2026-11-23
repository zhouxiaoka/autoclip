"""Publishing cover jobs and compatible reads of legacy and versioned artifacts."""
from __future__ import annotations

import io
import json
import logging
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.core.failure_codes import user_visible_error

COVER_IMAGE_FALLBACK = "生图失败，已改成本地排版或截帧"
COVER_TITLE_FALLBACK = "生图标题校对未通过，已改成本地排版"
COVER_FRAME_FALLBACK = "已用视频截帧作为封面"


from backend.core.image_providers import (
    ImageError,
    default_ocr_model,
    generate_image,
    read_image_text,
)
from backend.services import cover_brief as cb
from backend.services.publish_export import find_source_video, load_clip_meta, resolve_cjk_font, to_seconds

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "cover.json"
PLATFORMS = {
    "bilibili": {"width": 1146, "height": 717, "model_w": 1280, "model_h": 720, "label": "B站横屏"},
    "douyin": {"width": 1080, "height": 1920, "model_w": 720, "model_h": 1280, "label": "竖屏"},
}
CONTENT_TYPES = ("knowledge", "interview", "game", "vlog", "general")
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.RLock()
_active_requests: dict[tuple, str] = {}
_cancel: dict[str, threading.Event] = {}


class CoverError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ModelCoverRejected(CoverError):
    """The model result must not replace the current Studio cover."""


@dataclass
class CoverConfig:
    enabled: bool = False
    provider: str = "openai"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    ocr_model: str = ""
    design_mode: str = "crop_grade_text_only"
    allow_send_frame: bool = True
    source: str = "none"
    # own / env / text_model：密钥是封面自己填的、环境变量，还是复用了「AI 模型」里同一家的 key
    key_source: str = "none"
    # text_model：生图跟着「AI 分析 → 模型」的服务商走；custom：旧版单独配置的生图服务
    mode: str = "custom"

    @property
    def configured(self) -> bool:
        return bool(self.api_key) or bool(self.base_url)

    def public(self) -> dict[str, Any]:
        key = self.api_key
        masked = ""
        if key:
            masked = key[:4] + "…" + key[-4:] if len(key) > 8 else "••••"
        return {
            "enabled": self.enabled,
            "provider": self.provider or "openai",
            "model": self.model,
            "api_key_masked": masked,
            "base_url": self.base_url,
            "ocr_model": self.ocr_model,
            "allow_send_frame": self.allow_send_frame,
            "design_mode": self.design_mode,
            "configured": self.configured,
            "source": self.source,
            "key_source": self.key_source,
            "mode": self.mode,
        }


def config_path() -> Path:
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / CONFIG_FILENAME


def _text_model_key(provider: str, base_url: str) -> str:
    """生图提供商和文本模型是同一家时复用那边的 key，用户不用再填一遍。

    通义万相 ↔ 通义千问（dashscope），Seedream ↔ Seed（火山方舟），
    OpenAI 兼容 ↔ OpenAI 官方 / Infistar（按接口地址判断）。
    """
    try:
        from backend.core.llm_manager import get_llm_manager
        settings = get_llm_manager().settings
    except Exception:  # noqa: BLE001 - 读不到文本设置就当没有可复用的 key
        return ""
    kind = (provider or "openai").strip().lower()
    host = (base_url or "").lower()
    if kind == "dashscope":
        return str(settings.get("dashscope_api_key") or "")
    if kind == "seedream":
        return str(settings.get("seed_api_key") or "")
    from urllib.parse import urlparse
    from backend.core.cloud_presets import is_api88_host
    if is_api88_host(urlparse(base_url or "").hostname):
        return str(settings.get("api88_api_key") or "")
    if "infistar" in host:
        return str(settings.get("infistar_api_key") or "")
    if not host or "api.openai.com" in host:
        return str(settings.get("openai_api_key") or "")
    return ""


def text_model_image_service() -> dict[str, str] | None:
    """「AI 分析 → 模型」当前服务商对应的生图接口：provider / base_url / api_key / 服务商名。

    通义千问 → 通义万相，Seed（火山方舟）→ Seedream，OpenAI / Infistar → OpenAI 兼容 images。
    DeepSeek、Kimi、GLM、Grok、本地模型没有生图，返回 None（封面用视频截帧）。
    """
    try:
        from backend.core.llm_manager import get_llm_manager
        s = get_llm_manager().settings
    except Exception:  # noqa: BLE001
        return None
    provider = s.get("llm_provider", "dashscope")
    preset = s.get("cloud_preset")
    if provider == "dashscope":
        intl = "dashscope-intl" in str(s.get("dashscope_base_url") or "")
        return {"provider": "dashscope", "text_provider": "dashscope", "api_key": str(s.get("dashscope_api_key") or ""),
                "base_url": "https://dashscope-intl.aliyuncs.com/api/v1" if intl else ""}
    if provider != "openai" or s.get("llm_provider_preset"):
        return None
    if preset == "seed":
        return {"provider": "seedream", "text_provider": "seed", "api_key": str(s.get("seed_api_key") or ""), "base_url": ""}
    if preset in {"infistar", "api88"}:
        return {"provider": "openai", "text_provider": preset, "api_key": str(s.get(f"{preset}_api_key") or ""),
                "base_url": str(s.get("openai_base_url") or "")}
    if preset:
        return None
    return {"provider": "openai", "text_provider": "openai", "api_key": str(s.get("openai_api_key") or ""),
            "base_url": str(s.get("openai_base_url") or "")}


def verify_endpoint(cfg: "CoverConfig") -> dict[str, str]:
    """校对标题用哪个多模态模型读图。

    手动填过校对模型的沿用旧行为；否则用「视觉理解」那一套（默认就是文本模型），
    不再要求用户单独配一个校对模型。都没有时退回生图提供商的默认读图模型。
    """
    if cfg.ocr_model:
        return {"provider": cfg.provider, "api_key": cfg.api_key, "base_url": cfg.base_url, "model": cfg.ocr_model}
    try:
        from backend.services.studio.vision_settings import effective
        vision = effective()
    except Exception:  # noqa: BLE001
        vision = {}
    if vision.get("base_url") and vision.get("model"):
        return {"provider": vision.get("provider", "openai"), "api_key": vision.get("api_key", ""), "base_url": vision["base_url"], "model": vision["model"]}
    if cfg.source == 'connections':
        raise ImageError('未选择可用于封面校对的多模态模型，跳过校对')
    chosen = default_ocr_model(cfg.provider, cfg.model, cfg.base_url, api_key=cfg.api_key)
    if not chosen:
        raise ImageError('未选择可用于封面校对的多模态模型，跳过校对')
    return {"provider": cfg.provider, "api_key": cfg.api_key, "base_url": cfg.base_url, "model": chosen}


def load_config() -> CoverConfig:
    from backend.services import ai_model_settings as ai

    settings = ai.load()
    if settings:
        binding = settings.cover
        connection = ai.connection_for(settings, binding) if binding else None
        endpoint = ai.image_endpoint(connection) if connection else {}
        enabled = bool(binding and connection and settings.cover_enabled and not ai.failed_check(connection, 'cover', binding.model))
        return CoverConfig(enabled=enabled, model=binding.model if binding else '',
                           provider=endpoint.get('provider', 'openai'), base_url=endpoint.get('base_url', ''),
                           api_key=endpoint.get('api_key', ''), allow_send_frame=settings.allow_send_frame,
                           ocr_model=settings.cover_ocr_model, design_mode=settings.cover_design_mode,
                           source='connections', key_source='connection', mode='custom')
    env_key = (os.getenv("IMAGE_API_KEY") or "").strip()
    env_provider = (os.getenv("IMAGE_PROVIDER") or "").strip().lower()
    env_base = (os.getenv("IMAGE_BASE_URL") or "").strip()
    env_model = (os.getenv("IMAGE_MODEL") or "").strip()
    path = config_path()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError) as exc:
            logger.warning("读取 %s 失败: %s", path, exc)
    file_key = str(data.get("api_key") or "").strip()
    source = "file" if (file_key or data) else "none"
    api_key = env_key or file_key
    key_source = "env" if env_key else "own" if file_key else "none"
    if env_key:
        source = "env"
    elif not api_key and not data and not env_base and not env_provider:
        source = "none"
    provider = (env_provider or str(data.get("provider") or "openai")).strip().lower() or "openai"
    base_url = env_base or str(data.get("base_url") or "").strip()
    mode = (
        "custom"
        if (env_key or env_provider or env_base)
        else str(data.get("mode") or ("custom" if data else "text_model"))
    )
    if mode == "text_model":
        service = text_model_image_service()
        return CoverConfig(
            enabled=bool(data.get("enabled", False)) and service is not None,
            provider=service["provider"] if service else provider,
            model=env_model or str(data.get("model") or "").strip(),
            api_key=service["api_key"] if service else "",
            base_url=service["base_url"] if service else "",
            ocr_model="",
            allow_send_frame=bool(data.get("allow_send_frame", True)),
            source="file" if data else "none",
            key_source="text_model" if service and service["api_key"] else "none",
            mode="text_model",
        )
    if not api_key:
        api_key = _text_model_key(provider, base_url)
        if api_key:
            key_source = "text_model"
    return CoverConfig(
        enabled=bool(data.get("enabled", False)),
        provider=provider,
        model=env_model or str(data.get("model") or "").strip(),
        api_key=api_key,
        base_url=base_url,
        ocr_model=str(data.get("ocr_model") or "").strip(),
        allow_send_frame=bool(data.get("allow_send_frame", True)),
        source=source if (api_key or data or env_base or env_provider) else "none",
        key_source=key_source,
        mode="custom",
    )


def save_config(
    *,
    enabled: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    ocr_model: str | None = None,
    allow_send_frame: bool | None = None,
    mode: str | None = None,
) -> CoverConfig:
    current = load_config()
    path = config_path()
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, ValueError):
            existing = {}
    payload = {
        "enabled": current.enabled if enabled is None else bool(enabled),
        "provider": (provider if provider is not None else current.provider or "openai").strip().lower() or "openai",
        "model": (model if model is not None else current.model).strip(),
        # 复用来的文本模型 key 不写进封面配置：文本那边换了 key，这里跟着变
        "api_key": (current.api_key if current.key_source == "own" else "") if api_key is None else api_key.strip(),
        "base_url": (base_url if base_url is not None else current.base_url).strip().rstrip("/"),
        "ocr_model": (ocr_model if ocr_model is not None else current.ocr_model).strip(),
        "allow_send_frame": current.allow_send_frame if allow_send_frame is None else bool(allow_send_frame),
        # 没指明 mode 但传了服务商 / key / 地址（旧客户端、脚本）：就是单独配置
        "mode": mode or ("custom" if (provider or api_key or base_url) else current.mode) or "custom",
    }
    if payload["mode"] == "text_model":
        # 跟随模型：服务商、地址、key 都从「AI 分析 → 模型」推出来，不在这里保存
        payload.update(provider="", api_key="", base_url="", ocr_model="")
        if enabled is None and not existing:
            payload["enabled"] = False
    elif api_key is None and existing.get("api_key"):
        payload["api_key"] = str(existing["api_key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return load_config()


def clear_config() -> CoverConfig:
    path = config_path()
    if path.exists():
        path.unlink()
    return load_config()


def cover_dir(project_id: str, clip_id: str) -> Path:
    from backend.core.path_utils import get_project_directory
    path = get_project_directory(project_id) / "output" / "covers" / str(clip_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cover_path(project_id: str, clip_id: str, platform: str) -> Path:
    directory = cover_dir(project_id, clip_id)
    return cb.stored_path(directory / f"{platform}.json", directory / f"{platform}.jpg")


def meta_path(project_id: str, clip_id: str, platform: str) -> Path:
    return cover_dir(project_id, clip_id) / f"{platform}.json"


def normalize_platform(platform: str | None) -> str:
    key = (platform or "bilibili").strip().lower()
    if key in ("vertical", "shorts", "tiktok", "instagram", "youtube"):
        return "douyin"
    if key not in PLATFORMS:
        return "bilibili"
    return key


def split_title(title: str, *, max_lines: int = 2, max_chars: int = 18) -> list[str]:
    text = re.sub(r"\s+", " ", (title or "").strip())
    if not text:
        return ["切片"]
    for sep in (" / ", "/", "｜", "|", "：", ":", "——", "—", "，", ","):
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if 1 < len(parts) <= max_lines:
                return [p[:max_chars] for p in parts[:max_lines]]
    if len(text) <= max_chars:
        return [text]
    mid = len(text) // 2
    left = text[:mid].rstrip("的了呢吗吧与和，。！？ ")
    right = text[mid:].lstrip("的了呢吗吧与和，。！？ ")
    if not left or not right:
        return [text[:max_chars]]
    return [left[:max_chars], right[:max_chars]]


def infer_content_type(title: str, description: str = "") -> str:
    blob = f"{title} {description}".lower()
    rules = (
        ("game", ("翻盘", "高光", "1v", "游戏", "通关", "boss", "对局")),
        ("interview", ("对谈", "访谈", "对话", "第", "期", "ep.")),
        ("vlog", ("vlog", "日记", "住了", "第1天", "旅行", "日常")),
        ("knowledge", ("为什么", "解释", "科普", "陷阱", "案例", "普通人", "心理学")),
    )
    for kind, words in rules:
        if any(word.lower() in blob for word in words):
            return kind
    return "general"


def build_prompt(
    *,
    title_lines: list[str],
    subtitle: str,
    badge: str,
    platform: str,
    content_type: str,
    has_reference: bool,
) -> str:
    return cb.compat_prompt(normalize_platform(platform),title_lines,subtitle,badge)


def extract_frame_jpeg(video_path: Path, at_sec: float = 0.5, *, max_width: int = 1280) -> bytes:
    """从视频截一帧 JPEG。发布兜底和参考帧都用它。"""
    from backend.utils.ffmpeg_utils import get_ffmpeg_path

    path = Path(video_path)
    if not path.exists() or path.stat().st_size <= 0:
        raise CoverError("视频是空的")
    ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
    import tempfile

    with tempfile.TemporaryDirectory(prefix="autoclip-cover-frame-") as tmp:
        out = Path(tmp) / "frame.jpg"
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{max(0.0, float(at_sec)):.3f}",
            "-i", str(path),
            "-frames:v", "1",
            "-vf", f"scale='min({int(max_width)},iw)':-2",
            "-q:v", "3",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=30)
        if proc.returncode != 0 or not out.exists() or out.stat().st_size <= 0:
            cmd[cmd.index("-ss") + 1] = "0"
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=30)
        if proc.returncode != 0 or not out.exists() or out.stat().st_size <= 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise CoverError("截帧失败" + (f"：{detail[-1]}" if detail else ""))
        return out.read_bytes()


def _pil_font(size: int):
    from PIL import ImageFont

    font_path = resolve_cjk_font()
    if font_path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(font_path), size=size)
    except OSError:
        return ImageFont.load_default()


def overlay_title(
    background: bytes,
    *,
    title_lines: list[str],
    subtitle: str = "",
    badge: str = "",
    width: int,
    height: int,
    layout_version: int = 0,
) -> bytes:
    from PIL import Image, ImageDraw, ImageOps

    img = Image.open(io.BytesIO(background)).convert("RGB")
    img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
    # 底部渐隐，保证白字可读
    shade = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    for y in range(height // 2, height):
        alpha = int(180 * ((y - height / 2) / (height / 2)))
        shade_draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)
    title_size = max(36, int(width * 0.055))
    sub_size = max(22, int(width * 0.028))
    badge_size = max(18, int(width * 0.022))
    title_font = _pil_font(title_size)
    sub_font = _pil_font(sub_size)
    badge_font = _pil_font(badge_size)
    margin_x = int(width * 0.06)
    y = int(height * (0.58, 0.68, 0.52)[layout_version % 3])
    if layout_version % 3:
        accent = (242, 181, 68) if layout_version % 3 == 1 else (70, 211, 166)
        draw.rectangle((margin_x, y - 16, margin_x + title_size * 2, y - 10), fill=accent)
    for line in title_lines[:3]:
        draw.text((margin_x + 2, y + 2), line, font=title_font, fill=(0, 0, 0))
        draw.text((margin_x, y), line, font=title_font, fill=(255, 255, 255))
        bbox = draw.textbbox((margin_x, y), line, font=title_font)
        y = bbox[3] + int(title_size * 0.18)
    if subtitle.strip():
        draw.text((margin_x + 1, y + 8), subtitle.strip()[:40], font=sub_font, fill=(0, 0, 0))
        draw.text((margin_x, y + 7), subtitle.strip()[:40], font=sub_font, fill=(230, 230, 228))
    if badge.strip():
        draw.text((margin_x, int(height * 0.08)), badge.strip()[:24], font=badge_font, fill=(210, 210, 208))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def fit_jpeg(image: bytes, width: int, height: int) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image)).convert("RGB")
    img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def delivery_jpeg(image: bytes) -> bytes:
    """Keep the model's complete composition at native resolution for JPEG consumers."""
    from PIL import Image
    with Image.open(io.BytesIO(image)) as artwork:
        if artwork.format == 'JPEG':
            artwork.verify()
            return image
        out = io.BytesIO()
        artwork.convert('RGB').save(out, format='JPEG', quality=96, subsampling=0)
        return out.getvalue()


def title_matches(ocr_text: str, title_lines: list[str]) -> bool:
    return cb.matches(ocr_text, cb.join_lines(title_lines))


def resolve_clip_frame(project_id: str, clip_id: str) -> tuple[Path, float]:
    clip = load_clip_meta(project_id, clip_id)
    video = Path(clip['video_path']) if clip.get('source_type') == 'studio' else find_source_video(project_id)
    start = to_seconds(clip.get("start_time") or "0")
    end = to_seconds(clip.get("end_time") or clip.get("start_time") or "0")
    at = start + max(0.3, min(2.0, (end - start) * 0.2 if end > start else 0.5))
    return video, at


def write_cover_meta(project_id: str, clip_id: str, platform: str, meta: dict[str, Any]) -> None:
    meta_path(project_id, clip_id, platform).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def read_cover_meta(project_id: str, clip_id: str, platform: str) -> dict[str, Any] | None:
    path = meta_path(project_id, clip_id, platform)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def get_cover(project_id: str, clip_id: str, platform: str = "bilibili") -> dict[str, Any] | None:
    platform = normalize_platform(platform)
    path = cover_path(project_id, clip_id, platform)
    if not path.exists() or path.stat().st_size <= 0:
        return None
    meta = read_cover_meta(project_id, clip_id, platform) or {}
    return {
        "ok": True,
        "platform": platform,
        "path": str(path),
        "url": f"/api/v1/publish/covers/{project_id}/clips/{clip_id}/file?platform={platform}&t={path.stat().st_mtime_ns}",
        "method": meta.get("method") or "unknown",
        "title": meta.get("title") or "",
        "headline": meta.get("headline") or "",
        "subtitle": meta.get("subtitle") or "",
        "badge": meta.get("badge") or "",
        "content_type": meta.get("content_type") or "general",
        "options": meta.get("options"),
        "frame_locked": meta.get("brief", {}).get("source", {}).get("allow_alternate_frame") is False,
        "candidate_times": [
            item["time"] for item in meta.get("brief", {}).get("source", {}).get("candidates", [])
        ],
        "validation": meta.get("validation"),
        "warning": meta.get("warning"),
        "warning_detail": meta.get("warning_detail"),
    }


def ensure_publish_cover_jpeg(
    project_id: str,
    clip_id: str,
    *,
    platform: str = "bilibili",
    video_path: Path | None = None,
) -> bytes | None:
    """投稿用封面字节。优先已生成的设计封面；没有就截帧。失败返回 None，不抛。"""
    platform = normalize_platform(platform)
    existing = cover_path(project_id, clip_id, platform)
    if existing.exists() and existing.stat().st_size > 0:
        try:
            return existing.read_bytes()
        except OSError as exc:
            logger.warning("读取设计封面失败: %s", exc)
    path = Path(video_path) if video_path else None
    try:
        if path is None or not path.exists():
            path, at = resolve_clip_frame(project_id, clip_id)
        else:
            at = 0.5
        return extract_frame_jpeg(path, at_sec=at)
    except Exception as exc:  # noqa: BLE001
        logger.warning("投稿封面截帧失败，将空封面继续: %s", exc)
        return None


def generate_cover(
    *,
    project_id: str,
    clip_id: str,
    platform: str = "bilibili",
    title: str | None = None,
    subtitle: str | None = None,
    badge: str | None = None,
    content_type: str | None = None,
    force_local: bool = False,
    allow_reference_once: bool = False,
    session: Any = None,
    cancel: threading.Event | None = None,
    poll_interval: float = 1.5,
    design_options: str | None = None,
    request_token: str | None = None,
) -> dict[str, Any]:
    """生成并落盘封面。任何一步失败都尽量截帧兜底，仍失败才抛 CoverError。"""
    platform = normalize_platform(platform)
    spec = PLATFORMS[platform]
    path = meta_path(project_id, clip_id, platform)
    token = request_token or cb.begin(path)
    previous = read_cover_meta(project_id, clip_id, platform) or {}
    revision = int(previous.get("layout_version", -1)) + 1
    cfg = load_config()
    options = (
        cb.Options.model_validate_json(design_options)
        if design_options
        else cb.Options.model_validate(previous.get("options") or {"mode": cfg.design_mode})
    )
    clip = load_clip_meta(project_id, clip_id)
    proposed = (
        title
        if title is not None
        else previous.get("headline") or clip.get("generated_title") or clip.get("title") or ""
    )
    locked = title is not None or previous.get("brief", {}).get("copy", {}).get("mode") == "locked"
    if previous.get("brief", {}).get("source", {}).get("allow_alternate_frame") is False and (
        options.change_frame or options.frame_time is not None
    ):
        raise ModelCoverRejected("本次封面已锁定参考帧")
    from backend.services import cover_planner
    old_brief = previous.get("brief") or {}
    ctx = cover_planner.context(proposed, platform, (spec["width"], spec["height"]), options, locked=locked,
                                previous=old_brief.get("design", {}).get("composition_intent", ""))
    if force_local:
        ctx["local_only"] = True
    exclude_time = old_brief.get("source", {}).get("source_timestamp_sec") if options.change_frame else None
    source = {}
    frame = None
    centre = None
    saved = cb.stored_path(path, path.with_suffix(".frame.jpg"), "reference_file")
    if saved.is_file() and not options.change_frame:
        frame = saved.read_bytes()
        source = dict(previous.get("brief", {}).get("source", {}))
        source["evidence"] = previous.get("brief", {}).get("content", {}).get("evidence", [])
        centre = source.get("centre")
    if options.frame_time is not None:
        from backend.services.publish_export import find_source_video

        candidate_source = dict(previous.get("brief", {}).get("source", {}))
        try:
            frame, centre = cb.selected_candidate(
                find_source_video(project_id), candidate_source, options.frame_time
            )
        except ValueError as exc:
            raise ModelCoverRejected(str(exc)) from exc
        source = {**candidate_source, "evidence": previous.get("brief", {}).get("content", {}).get("evidence", [])}
    if frame is None and clip.get("source_type") == "studio":
        from backend.services.studio.publishing import cover_source_frame

        from backend.core.project_cancellation import ProjectDeleted
        try:
            frame, centre = cover_source_frame(project_id, clip["studio_job_id"], revision, source, context=ctx, exclude_time=exclude_time)
        except ProjectDeleted:
            raise
        except (FileNotFoundError, CoverError, OSError, ValueError):
            pass
    if frame is None:
        from backend.services.studio.publish_kit import _scene_rows

        start = to_seconds(clip.get("start_time") or "0")
        end = to_seconds(clip.get("end_time") or "0")
        video, at = resolve_clip_frame(project_id, clip_id)
        if options.change_frame and end > start:
            at = start + (end - start) * (0.36, 0.58, 0.75)[revision % 3]
        source = dict(
            kind="export_frame" if clip.get("source_type") == "studio" else "video_frame",
            asset_id=clip_id,
            source_timestamp_sec=at,
            selection_reason="从当前切片对应的视频截取",
            clip_range=[start, end],
            evidence=_scene_rows(project_id, dict(start=start, end=end)),
        )
        if end > start and clip.get("source_type") != "studio":
            frame, centre, _ = cb.cd.pick_frame(video, dict(start=start, end=end), source["evidence"],
                                                 local_revision=revision, context=ctx, trace=source,
                                                 exclude_time=exclude_time)
        else:
            frame = extract_frame_jpeg(video, at_sec=at)
    rows = source.pop("evidence", [])
    proposed = cb.choose_copy(proposed, rows, locked)
    if centre is None:
        centre = cb.cd._face_and_sharpness(frame)[0]
    brief = cb.plan(
        frame,
        title=proposed,
        editorial_context=ctx,
        strategy=platform,
        size=(spec["width"], spec["height"]),
        origin=source,
        rows=rows,
        options=options,
        centre=centre,
        locked=locked,
        secondary=(subtitle, badge),
        revision=revision,
    )

    def generate(req):
        if cancel is not None and cancel.is_set():
            raise CoverError("已取消")
        return generate_image(
            provider=cfg.provider,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            request=req,
            session=session,
            cancel=cancel,
            poll_interval=poll_interval,
        )

    def check(data, lines):
        try:
            observed = read_image_text(**verify_endpoint(cfg), image=data, session=session)
        except ImageError:
            return None
        return cb.matches(observed, " ".join(lines))

    try:
        data, audit = cb.make(
            brief,
            frame,
            cfg,
            can_send=not force_local and (cfg.allow_send_frame or allow_reference_once),
            generate=generate,
            check=check,
            previous=cover_path(project_id, clip_id, platform).is_file(),
        )
        if cancel is not None and cancel.is_set():
            raise CoverError("已取消")
        method = {"model": "model", "local_design": "local_overlay", "source_frame": "frame"}[audit["result"]]
        meta = dict(
            **audit,
            method=method,
            layout_version=revision,
            options=options.model_copy(update={"change_frame": False, "frame_time": None}).model_dump(),
            title=proposed,
            headline=proposed,
            subtitle=subtitle or "",
            badge=badge or "",
            content_type=content_type or "general",
            platform=platform,
            width=spec["width"],
            height=spec["height"],
            warning=COVER_IMAGE_FALLBACK
            if audit["fallback_reason"] in ("image_service_unavailable", "unsupported_edit")
            else audit["fallback_reason"],
        )
        cb.save(path, token, data, frame, meta)
    except cb.Rejected as exc:
        cb.record_rejection(path, token, exc)
        raise ModelCoverRejected(str(exc)) from exc
    except ValueError as exc:
        raise ModelCoverRejected(str(exc)) from exc
    return get_cover(project_id,clip_id,platform)


def _jobs_dir() -> Path:
    from backend.core.path_utils import get_data_directory
    directory = get_data_directory() / "cover_jobs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _remember_job(job: dict[str, Any]) -> None:
    stored = dict(job)
    with _jobs_lock:
        _jobs[stored["job_id"]] = stored
        path = _jobs_dir() / f"{stored['job_id']}.json"
        path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")


def _read_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        cached = _jobs.get(job_id)
        if cached is not None:
            return dict(cached)
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def get_job(job_id: str) -> dict[str, Any] | None:
    return _read_job(job_id)


def cancel_job(job_id: str) -> dict[str, Any]:
    event = _cancel.get(job_id)
    if event is not None:
        event.set()
    job = _read_job(job_id) or {"job_id": job_id}
    if job.get("status") in ("queued", "running"):
        job.update(status="cancelled", error="已取消")
        _remember_job(job)
    return job


def start_generate(
    *,
    project_id: str,
    clip_id: str,
    platform: str = "bilibili",
    title: str | None = None,
    subtitle: str | None = None,
    badge: str | None = None,
    content_type: str | None = None,
    force_local: bool = False,
    allow_reference_once: bool = False,
    design_options: str | None = None,
) -> dict[str, Any]:
    params = dict(
        project_id=project_id,
        clip_id=clip_id,
        platform=normalize_platform(platform),
        title=title,
        subtitle=subtitle,
        badge=badge,
        content_type=content_type,
        force_local=force_local,
    )
    if design_options:
        params["design_options"] = design_options
    if allow_reference_once:
        params["allow_reference_once"] = True
    key = tuple(params.items())
    with _jobs_lock:
        active = _jobs.get(_active_requests.get(key))
        if active and active["status"] in ("queued", "running"):
            return {"ok": True, "job_id": active["job_id"], "status": active["status"]}
        job_id = str(uuid.uuid4())
        _remember_job(
            dict(
                job_id=job_id, status="queued", project_id=project_id, clip_id=clip_id, platform=params["platform"]
            )
        )
        params["request_token"] = cb.begin(meta_path(project_id, clip_id, params["platform"]))
        _cancel[job_id] = threading.Event()
        _active_requests[key] = job_id
        try:
            threading.Thread(
                target=_run_job, args=(job_id, params), daemon=True, name=f"cover-{job_id[:8]}"
            ).start()
        except RuntimeError:
            _active_requests.pop(key, None)
            _cancel.pop(job_id, None)
            _remember_job({**_jobs[job_id], "status": "failed"})
            raise
    return {"ok": True, "job_id": job_id, "status": "queued"}


def _run_job(job_id: str, params: dict[str, Any]) -> None:
    job = _read_job(job_id) or {"job_id": job_id}
    job.update(status="running")
    _remember_job(job)
    try:
        result = generate_cover(cancel=_cancel.get(job_id), **params)
        job.update(status="completed", result=result)
        _remember_job(job)
    except ModelCoverRejected as exc:
        job.update(status="failed", error=user_visible_error(exc))
        _remember_job(job)
    except CoverError as exc:
        if str(exc) == "已取消":
            job.update(status="cancelled", error=str(exc))
        else:
            job.update(status="failed", error=user_visible_error(exc))
        _remember_job(job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("封面任务失败")
        job.update(status="failed", error=user_visible_error(exc))
        _remember_job(job)
    finally:
        with _jobs_lock:
            key = tuple((k, v) for k, v in params.items() if k != "request_token")
            if _active_requests.get(key) == job_id:
                _active_requests.pop(key)
            _cancel.pop(job_id, None)
