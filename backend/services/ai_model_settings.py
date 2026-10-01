"""Named connections and independent model assignments, saved as one atomic document.

Legacy settings remain untouched until the user saves this document. Runtime readers
use it when present, otherwise retain their original settings/environment behavior.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.core.path_utils import get_data_directory

_lock = threading.RLock()
Capability = Literal['auto', 'multimodal', 'text']


class Connection(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    provider: str = 'openai'
    base_url: str = ''
    api_key: str | None = Field(default=None, max_length=2000)
    image_api: Literal['auto', 'openai', 'seedream', 'dashscope', 'fal'] = 'auto'
    image_base_url: str = ''

    @field_validator('provider')
    @classmethod
    def provider_supported(cls, value):
        from backend.core.cloud_presets import CLOUD_PRESETS
        if value not in {'dashscope', 'openai', 'compatible', 'gemini', 'siliconflow', 'ollama', 'lmstudio', *CLOUD_PRESETS}:
            raise ValueError('请选择支持的服务类型；自定义服务请选择 OpenAI 兼容')
        return value

    @field_validator('image_api', mode='before')
    @classmethod
    def known_image_api(cls, value):
        # A settings file written by a newer version may name an image API this one lacks:
        # fall back to auto instead of rejecting every connection (and every task) with it.
        return value if value in ('auto', 'openai', 'seedream', 'dashscope', 'fal') else 'auto'

    @model_validator(mode='after')
    def custom_requires_url(self):
        if self.provider == 'compatible' and not self.base_url:
            raise ValueError('请填写自定义服务的接口地址')
        return self

    @field_validator('base_url', 'image_base_url')
    @classmethod
    def valid_url(cls, value):
        value = value.strip().rstrip('/')
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('请填写不含密钥或查询参数的 HTTP(S) 接口地址')
        return value

    @field_validator('name', 'id')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('名称不能为空')
        return value.strip()


class Assignment(BaseModel):
    connection_id: str
    model: str = Field(min_length=1, max_length=200)
    capability: Capability = 'auto'

    @field_validator('model')
    @classmethod
    def model_not_blank(cls, value):
        if not value.strip():
            raise ValueError('请选择或输入模型 ID')
        return value.strip()


class Transcription(BaseModel):
    provider: Literal['whisper_local', 'sensevoice_local', 'cloud'] = 'whisper_local'
    model: str = Field(default='base', min_length=1, max_length=200)
    connection_id: str | None = None

    @model_validator(mode='after')
    def valid_selection(self):
        self.model = self.model.strip()
        if not self.model:
            raise ValueError('请选择转写模型')
        if self.provider == 'whisper_local':
            if self.model not in {'tiny', 'base', 'small', 'medium', 'large', 'large-v3'}:
                raise ValueError('请选择本地 Whisper 模型')
            self.connection_id = None
        elif self.provider == 'sensevoice_local':
            if self.model != 'SenseVoiceSmall':
                raise ValueError('请选择本地 SenseVoiceSmall 模型')
            self.connection_id = None
        elif not self.connection_id:
            raise ValueError('请选择转写供应商')
        return self


class ModelSettings(BaseModel):
    version: Literal[1] = 1
    connections: list[Connection] = Field(default_factory=list, max_length=100)
    analysis: Assignment | None = None
    # None explicitly means reuse the analysis assignment, not an independently changing provider.
    vision: Assignment | None = None
    cover: Assignment | None = None
    transcription: Transcription | None = None
    cover_enabled: bool = False
    allow_send_frame: bool = False
    # 1 = saved by 1.5+, where AI covers are an explicit choice. 1.4 switched them on by itself at
    # first setup, and 1.5 generates one per output in the background (billed), so a file 1.4 wrote
    # reads with AI covers off; the chosen model stays, one click turns them back on.
    cover_choice_version: int = 0
    cover_ocr_model: str = ''
    vision_timeout: int = Field(default=180, ge=10, le=300)
    analysis_mode: Literal['auto', 'subtitle', 'visual'] = 'auto'
    allow_visual_screening: bool = True
    chunk_size: int = Field(default=5000, ge=1000, le=10000)
    min_score_threshold: float = Field(default=.7, ge=.1, le=1)
    max_clips_per_collection: int = Field(default=5, ge=1, le=20)

    @model_validator(mode='after')
    def consistent(self):
        ids = [c.id for c in self.connections]
        if len(ids) != len(set(ids)):
            raise ValueError('服务连接 ID 不能重复')
        for binding in (self.analysis, self.vision, self.cover):
            if binding and binding.connection_id not in ids:
                raise ValueError('模型引用的服务已被移除，请先重新选择模型')
        if self.transcription and self.transcription.provider == 'cloud':
            connection = next((c for c in self.connections if c.id == self.transcription.connection_id), None)
            if not connection:
                raise ValueError('转写模型引用的服务已被移除')
            from backend.core.asr_model_catalog import adapter
            if not adapter(connection.provider, self.transcription.model):
                raise ValueError('该 ASR 模型的字幕时间戳接口尚未适配，请选择其他转写模型')
        if self.cover_enabled and not self.cover:
            raise ValueError('请选择封面生图模型')
        if self.analysis_mode == 'subtitle':
            self.allow_visual_screening = False
        return self


COVER_CHOICE_VERSION = 1


def path():
    return get_data_directory() / 'ai-model-settings.json'


def load() -> ModelSettings | None:
    with _lock:
        target = path()
        if not target.exists():
            return None
        settings = ModelSettings.model_validate_json(target.read_text(encoding='utf-8'))
        if settings.cover_choice_version < COVER_CHOICE_VERSION and settings.cover_enabled:
            settings = settings.model_copy(update={'cover_enabled': False})
        return settings


def connection_for(settings: ModelSettings, assignment: Assignment) -> Connection:
    return next(c for c in settings.connections if c.id == assignment.connection_id)


def chat_endpoint(connection: Connection, model: str) -> dict:
    from backend.core.cloud_presets import CLOUD_PRESETS
    from backend.core.local_presets import LOCAL_PRESETS
    defaults = {
        'openai': 'https://api.openai.com/v1',
        'dashscope': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'siliconflow': 'https://api.siliconflow.cn/v1',
        **{key: preset.base_url for key, preset in CLOUD_PRESETS.items()},
        **{key: preset.base_url for key, preset in LOCAL_PRESETS.items()},
    }
    base = connection.base_url or defaults[connection.provider]
    if connection.provider == 'dashscope' and connection.base_url and (urlparse(base).hostname or '').endswith('.aliyuncs.com'):
        # Dedicated Bailian endpoints are pasted as a host or its native /api/v1 path; text models
        # use the OpenAI-compatible path on the same host (speech recognition uses /api/v1).
        # Other hosts (a relay or proxy someone set up in 1.4) are used exactly as entered.
        host = base.rstrip('/').removesuffix('/compatible-mode/v1').removesuffix('/api/v1')
        base = host + '/compatible-mode/v1'
    return {'base_url': base, 'api_key': connection.api_key or '', 'model': model}


def image_endpoint(connection: Connection) -> dict:
    kind = connection.image_api
    if kind == 'auto' and 'fal.run' in (connection.image_base_url or connection.base_url or ''):
        kind = 'fal'  # an OpenAI-compatible connection pointed at fal.run speaks fal's model API
    if kind == 'auto':
        kind = {'dashscope': 'dashscope', 'seed': 'seedream', 'gemini': 'gemini', 'grok': 'grok', 'glm': 'glm'}.get(connection.provider, 'openai')
    base = connection.image_base_url
    if not base:
        if connection.provider == 'dashscope' and kind == 'dashscope':
            base = ('https://dashscope-intl.aliyuncs.com/api/v1' if 'dashscope-intl' in connection.base_url
                    else 'https://dashscope.aliyuncs.com/api/v1')
        elif kind == 'gemini':
            base = connection.base_url.removesuffix('/openai') if connection.base_url else 'https://generativelanguage.googleapis.com/v1beta'
        elif kind == 'fal':
            base = 'https://fal.run'
        else:
            base = chat_endpoint(connection, '')['base_url']
    return {'provider': kind, 'base_url': base, 'api_key': connection.api_key or ''}


def capability(settings: ModelSettings, assignment: Assignment) -> str | None:
    if assignment.capability != 'auto':
        return assignment.capability
    from backend.core.model_registry import lookup_capability
    return lookup_capability(connection_for(settings, assignment), assignment.model)


def vision_endpoint(settings: ModelSettings) -> dict | None:
    binding = settings.vision or settings.analysis
    if not binding or capability(settings, binding) != 'multimodal':
        return None
    return chat_endpoint(connection_for(settings, binding), binding.model)


def public(settings: ModelSettings) -> dict:
    value = settings.model_dump()
    if settings.transcription is None:
        from backend.core.desktop_config import get_desktop_config
        previous = get_desktop_config().speech_recognition.whisper_config.model_name
        value['transcription'] = Transcription(model=previous).model_dump()
    value['saved'] = path().exists()
    for c in value['connections']:
        key = c.pop('api_key') or ''
        c['has_key'] = bool(key)
        c['api_key_masked'] = (key[:3] + '…' + key[-3:]) if len(key) > 8 else ('••••' if key else '')
    return value


def resolve_secret(connection: Connection, previous: ModelSettings | None = None) -> Connection:
    previous = previous if previous is not None else load()
    old = next((c for c in previous.connections if c.id == connection.id), None) if previous else None
    if connection.api_key is not None:
        return connection
    if old and old.api_key and (old.provider, old.base_url, old.image_base_url) != (connection.provider, connection.base_url, connection.image_base_url):
        raise ValueError('服务地址已改变，请重新填写 API Key')
    return connection.model_copy(update={'api_key': old.api_key if old else ''})


def save(settings: ModelSettings) -> dict:
    with _lock:
        settings = ModelSettings.model_validate(settings.model_dump())
        previous = load() or migrate_legacy()
        resolved = settings.model_copy(update={'connections': [resolve_secret(c, previous) for c in settings.connections],
                                               'cover_choice_version': COVER_CHOICE_VERSION})
        if not resolved.analysis:
            raise ValueError('请选择高光分析模型')
        if resolved.analysis_mode == 'visual' and not vision_endpoint(resolved):
            raise ValueError('画面分析需要多模态模型，请选择模型或在高级设置中确认自定义模型能力')
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(resolved.model_dump(), stream, ensure_ascii=False, indent=2)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return public(resolved)


def migrate_legacy() -> ModelSettings:
    """Read-only migration: preserve separate legacy vision/cover endpoints and keys."""
    from backend.core.llm_manager import get_llm_manager
    from backend.services.studio import vision_settings, analysis_preferences
    from backend.services import cover
    manager = get_llm_manager()
    manager._reload_if_settings_changed()
    s = manager.settings
    provider = s.get('cloud_preset') or s.get('llm_provider_preset') or s.get('llm_provider', 'dashscope')
    endpoint = manager.openai_compatible_endpoint() or {}
    base = endpoint.get('base_url', '')
    if provider == 'gemini':
        base = ''  # native listing API, compatible base derived by chat_endpoint
    connections = [Connection(id='legacy-analysis', name=provider, provider=provider,
                              base_url=base, api_key=endpoint.get('api_key', ''))]
    analysis = Assignment(connection_id='legacy-analysis', model=s.get('model_name') or 'qwen-plus')
    v = vision_settings.effective()
    if v.get('mode') == 'text_model' and v.get('model'):
        # Preserve the already working legacy choice until refreshed metadata is available.
        analysis.capability = 'multimodal'
    vision = None
    if v.get('mode') == 'custom' and v.get('base_url') and v.get('model'):
        connections.append(Connection(id='legacy-vision', name='视觉服务', base_url=v['base_url'], api_key=v.get('api_key', '')))
        vision = Assignment(connection_id='legacy-vision', model=v['model'], capability='multimodal')
    cfg = cover.load_config()
    cover_assignment = None
    if cfg.model:
        # Even formerly-following covers become explicit references, so changing
        # the analysis assignment never silently re-routes image generation.
        if cfg.mode == 'text_model':
            cover_assignment = Assignment(connection_id='legacy-analysis', model=cfg.model)
        else:
            kind = {'dashscope': 'dashscope', 'seedream': 'seed'}.get(cfg.provider, 'openai')
            connections.append(Connection(id='legacy-cover', name='封面服务', provider=kind,
                                          api_key=cfg.api_key, image_api=cfg.provider,
                                          base_url=cfg.base_url if kind in {'openai', 'seed'} else '',
                                          image_base_url=cfg.base_url))
            cover_assignment = Assignment(connection_id='legacy-cover', model=cfg.model)
    prefs = analysis_preferences.load()
    return ModelSettings(connections=connections, analysis=analysis, vision=vision,
                         cover=cover_assignment, cover_enabled=cfg.enabled and cover_assignment is not None,
                         allow_send_frame=cfg.allow_send_frame, analysis_mode=prefs.analysis_mode,
                         cover_ocr_model=cfg.ocr_model, vision_timeout=v.get('timeout', 180),
                         allow_visual_screening=prefs.allow_visual_screening,
                         chunk_size=s.get('chunk_size', 5000), min_score_threshold=s.get('min_score_threshold', .7),
                         max_clips_per_collection=s.get('max_clips_per_collection', 5))
