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

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, field_validator, model_validator

from backend.core.path_utils import get_data_directory
from backend.services.model_settings_source import (
    NOTICE_PRESET_UPDATED,
    NOTICE_PURPOSE_RESET,
    annotate_document,
    current_catalog_version,
    infer_base_url_source,
    infer_model_source,
    known_notices,
    prepare_connections_for_save,
    preset_update_available,
    recommended_model,
    try_connection,
    usable_model,
)

_lock = threading.RLock()
Capability = Literal['auto', 'multimodal', 'text']
Source = Literal['preset', 'user']
ModelType = Literal['language', 'asr', 'tts', 'image', 'music', 'video']
Scenario = Literal['analysis', 'vision', 'transcription', 'cover']


class CustomModelOffer(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(default='', max_length=200)
    types: list[ModelType] = Field(default_factory=lambda: ['language'])
    vision: bool = False
    scenarios: list[Scenario] = Field(default_factory=list)
    enabled: bool = True

    @field_validator('id', 'display_name')
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('types', 'scenarios')
    @classmethod
    def unique_items(cls, value):
        seen: list[str] = []
        for item in value or []:
            if item not in seen:
                seen.append(item)
        return seen

    @model_validator(mode='after')
    def constrain(self):
        if not self.types:
            self.types = ['language']
        types = set(self.types)
        if 'language' not in types:
            self.vision = False
        allowed: list[Scenario] = []
        for scenario in self.scenarios:
            if scenario == 'transcription' and 'asr' not in types:
                continue
            if scenario == 'cover' and 'image' not in types:
                continue
            if scenario == 'analysis' and 'language' not in types:
                continue
            if scenario == 'vision' and ('language' not in types or not self.vision):
                continue
            allowed.append(scenario)
        self.scenarios = allowed
        return self


class Connection(BaseModel):
    # hide_input_in_errors: str(ValidationError) otherwise keeps the tail of a long api_key.
    model_config = ConfigDict(extra='ignore', hide_input_in_errors=True)
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    provider: str = 'openai'
    catalog_provider_id: str = ''
    base_url: str = ''
    api_key: str | None = Field(default=None, max_length=2000)
    image_api: Literal['auto', 'openai', 'seedream', 'dashscope', 'fal'] = 'auto'
    image_base_url: str = ''
    validation_status: Literal['ok', 'failed', 'unchecked', 'transient'] = 'unchecked'
    validation_error_type: str = ''
    # None = omitted (legacy file or old client). Inferred after validation.
    base_url_source: Source | None = None
    preset_version: int = Field(default=0, ge=0)
    custom_models: list[CustomModelOffer] = Field(default_factory=list, max_length=200)
    # OhMyGame-style visibility whitelist. None = never edited: the UI enables a small recommended set.
    enabled_model_ids: list[str] | None = Field(default=None, max_length=2000)

    @field_validator('enabled_model_ids')
    @classmethod
    def clean_enabled(cls, value):
        if value is None:
            return None
        return list(dict.fromkeys(str(item).strip()[:200] for item in value if str(item).strip()))

    @field_validator('provider')
    @classmethod
    def provider_supported(cls, value):
        from backend.core.cloud_presets import CLOUD_PRESETS
        if value not in {'dashscope', 'openai', 'compatible', 'gemini', 'siliconflow', 'ollama', 'lmstudio', *CLOUD_PRESETS}:
            raise ValueError('请选择支持的服务类型；自定义服务请选择 OpenAI 兼容')
        return value

    @model_validator(mode='after')
    def endpoint_catalog_identity(self):
        if self.catalog_provider_id:
            from backend.core.provider_presets import get_provider
            preset = get_provider(self.catalog_provider_id)
            if not preset or preset.base_url or preset.protocol == 'local' or self.provider != 'compatible':
                raise ValueError('请选择需要自定义接口地址的服务商')
        return self

    @field_validator('image_api', mode='before')
    @classmethod
    def known_image_api(cls, value):
        # A settings file written by a newer version may name an image API this one lacks:
        # fall back to auto instead of rejecting every connection (and every task) with it.
        return value if value in ('auto', 'openai', 'seedream', 'dashscope', 'fal') else 'auto'

    @field_validator('api_key')
    @classmethod
    def strip_key(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def custom_requires_url(self):
        if self.provider == 'compatible' and not self.base_url:
            raise ValueError('请填写自定义服务的接口地址')
        return self

    @field_validator('base_url', 'image_base_url')
    @classmethod
    def valid_url(cls, value):
        from backend.core.provider_url import cleanup_base_url
        from backend.core.provider_endpoint import is_console_host
        value = cleanup_base_url(value)
        if value:
            parsed = urlparse(value)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('请填写不含密钥或查询参数的 HTTP(S) 接口地址')
            if is_console_host(parsed.hostname):
                raise ValueError('这是控制台或官网地址，不是模型接口')
        return value

    @model_validator(mode='after')
    def normalize_provider_url(self):
        from backend.core.provider_url import normalize_provider_base_url
        if self.base_url:
            from backend.core.provider_endpoint import normalize_provider_base_url as line_b_normalize
            # Line B wraps provider_url: strip pasted /chat/completions, then
            # apply provider conventions. Cleanup only — never rejects.
            self.base_url = line_b_normalize(self.base_url, self.provider).url
        if self.image_base_url:
            self.image_base_url = normalize_provider_base_url(self.image_base_url, 'image')
        return self

    @field_validator('name', 'id')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('名称不能为空')
        return value.strip()

    @field_validator('validation_error_type')
    @classmethod
    def known_validation_type(cls, value):
        from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES
        text = (value or '').strip()
        if text and text not in UPSTREAM_ERROR_TYPES:
            return ''
        return text

    @model_validator(mode='after')
    def infer_url_source(self):
        if self.base_url_source is None:
            self.base_url_source = infer_base_url_source(self.provider, self.base_url)
        return self


class Assignment(BaseModel):
    model_config = ConfigDict(extra='ignore')
    connection_id: str
    model: str = Field(min_length=1, max_length=200)
    capability: Capability = 'auto'
    # Infer missing legacy sources through the shared P3 migration helper.
    model_source: Source | None = None

    @field_validator('model')
    @classmethod
    def model_not_blank(cls, value):
        if not value.strip():
            raise ValueError('请选择或输入模型 ID')
        return value.strip()

    @model_validator(mode='after')
    def infer_source(self):
        if self.model_source is None:
            self.model_source = infer_model_source(self.model)
        return self


class Transcription(BaseModel):
    provider: Literal['whisper_local', 'sensevoice_local', 'cloud'] = 'whisper_local'
    model: str = Field(default='base', min_length=1, max_length=200)
    connection_id: str | None = None
    model_source: Source = 'user'

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
    model_config = ConfigDict(hide_input_in_errors=True)
    _migration_warnings: list[str] = PrivateAttr(default_factory=list)
    version: Literal[1] = 1
    connections: list[Connection] = Field(default_factory=list, max_length=100)
    seen_notices: list[str] = Field(default_factory=list)
    acked_catalog_version: int = Field(default=0, ge=0)
    analysis: Assignment | None = None
    # None explicitly means reuse the analysis assignment, not an independently changing provider.
    vision: Assignment | None = None
    cover: Assignment | None = None
    transcription: Transcription | None = None
    cover_enabled: bool = False
    # Explicit "cover follows analysis". None only while reading a document written before the
    # flag existed: a cover on the analysis connection was the old "follow", anything else is
    # independent. Following covers move with analysis; independent ones never change provider.
    cover_follows_analysis: bool | None = None
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

    @field_validator('seen_notices')
    @classmethod
    def only_known_notices(cls, value):
        return known_notices(value or [])

    @model_validator(mode='wrap')
    @classmethod
    def apply_source_migration(cls, data, handler):
        warnings: list[str] = []
        if isinstance(data, dict):
            data, warnings = annotate_document(data)
        settings = handler(data)
        if warnings:
            settings._migration_warnings = list(dict.fromkeys([*settings._migration_warnings, *warnings]))
        return settings

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
        if self.cover_follows_analysis is None:
            self.cover_follows_analysis = bool(
                self.cover and self.analysis and self.cover.connection_id == self.analysis.connection_id)
        if (self.cover_follows_analysis and self.cover and self.analysis
                and self.cover.connection_id != self.analysis.connection_id):
            raise ValueError('跟随分析的封面必须使用分析服务连接')
        if self.cover_enabled and not self.cover:
            raise ValueError('请选择封面生图模型')
        if self.analysis_mode == 'subtitle':
            self.allow_visual_screening = False
        return self


COVER_CHOICE_VERSION = 1


def path():
    return get_data_directory() / 'ai-model-settings.json'


def _atomic_write_json(target, data) -> None:
    temp = target.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def load(*, persist_migration: bool = False) -> ModelSettings | None:
    with _lock:
        target = path()
        if not target.exists():
            return None
        raw_text = target.read_text(encoding='utf-8')
        settings = ModelSettings.model_validate_json(raw_text)
        try:
            raw = json.loads(raw_text)
        except ValueError:
            raw = {}
        if persist_migration and isinstance(raw, dict) and 'cover_follows_analysis' not in raw:
            # One-time migration when settings are opened: persist the inferred follow flag so it
            # never flips later. Runtime reads (pipeline readiness) never touch the file.
            raw['cover_follows_analysis'] = settings.cover_follows_analysis
            _atomic_write_json(target, raw)
        if settings.cover_choice_version < COVER_CHOICE_VERSION and settings.cover_enabled:
            settings = settings.model_copy(update={'cover_enabled': False})
        return settings


def for_editing() -> ModelSettings:
    """Offer repair in the UI without silently changing runtime routing or keys."""
    try:
        loaded = load(persist_migration=True)
        if loaded is not None:
            return loaded
        return migrate_legacy()
    except (ValidationError, ValueError, TypeError, OSError):
        settings = ModelSettings()
        settings._migration_warnings = ['settings_configuration_invalid']
        return settings


def endpoint_provider_ready(connection: Connection) -> bool:
    from backend.core.provider_presets import get_provider
    preset = get_provider(connection.catalog_provider_id or connection.provider)
    if not preset or preset.base_url or preset.protocol == 'local':
        return True
    return bool(connection.base_url.strip()) and connection.validation_status in ('ok', 'transient')


def connection_for(settings: ModelSettings, assignment: Assignment) -> Connection:
    connection = next((c for c in settings.connections if c.id == assignment.connection_id), None)
    if connection is None:
        raise ValueError('模型引用的服务连接已缺失，请到「设置 → 服务商与模型」重新选择并保存，完成修复后再生成。')
    if not endpoint_provider_ready(connection):
        raise ValueError('请填写服务商接口地址并通过连接验证后再生成。')
    return connection


def ensure_runtime_bindings(settings: ModelSettings, *, require_vision: bool = False) -> None:
    """A lost explicit assignment is never consent to borrow another provider."""
    if {'analysis_configuration_invalid', 'vision_configuration_invalid'} & set(settings._migration_warnings):
        raise ValueError('分析或视觉模型引用的服务连接已缺失或配置无效，请到「设置 → 服务商与模型」修复并保存后再生成。')
    for binding in (settings.analysis, settings.vision):
        if binding is not None:
            connection = connection_for(settings, binding)
            if connection.validation_status == 'failed' and (binding is settings.analysis or settings.analysis_mode == 'visual' or require_vision):
                raise ValueError('当前模型连接未通过校验。请到「设置 → 服务商与模型」修复密钥或地址后再生成。')


def require_analysis(settings: ModelSettings) -> Assignment:
    ensure_runtime_bindings(settings)
    if settings.analysis is None:
        raise ValueError('分析模型配置需要修复，请到「设置 → 服务商与模型」选择服务连接和模型并保存后再生成。')
    return settings.analysis


def chat_endpoint(connection: Connection, model: str) -> dict:
    from backend.core.provider_endpoint import locked_chat_url, normalize_provider_base_url, official_chat_url
    locked = locked_chat_url(connection.provider, connection.base_url)
    # The live catalog lock preserves accepted hosts and schemes, regardless of
    # preset_version. All chat-path rewriting goes through the shared helper.
    if locked:
        base = locked
    elif connection.base_url:
        base = normalize_provider_base_url(connection.base_url, connection.provider).url
    else:
        base = official_chat_url(connection.provider)
        if not base:
            raise ValueError('请填写服务商接口地址')
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
    """The one capability answer for a binding: readiness, the pipeline, save checks and
    the settings list all use this. A name classified as text-only stays text even when
    a live list or an explicit multimodal flag says otherwise. Other explicit
    multimodal/text choices win; auto asks the provider and catalog metadata first,
    then (for named providers, not a generic compatible gateway) the model-name rules
    in supports_vision (gpt-5.x, gpt-6.x, o1/o3/o4-mini ...). auto never turns an
    unknown name into "text": it stays None, which simply means "not confirmed to see images"."""
    from backend.core.model_catalog import known_text_only
    if known_text_only(assignment.model):
        return 'text'
    if assignment.capability != 'auto':
        return assignment.capability
    from backend.core.model_registry import lookup_capability
    known = lookup_capability(connection_for(settings, assignment), assignment.model)
    if known:
        return known
    connection = connection_for(settings, assignment)
    if connection is None or connection.provider == 'compatible':
        # A self-hosted "compatible" gateway can alias any name; keep requiring
        # provider metadata or an explicit choice there.
        return None
    from backend.core.model_catalog import supports_vision
    return 'multimodal' if supports_vision(assignment.model) else None


def sees_images(settings: ModelSettings, assignment: Assignment | None) -> bool:
    return bool(assignment and assignment.model and capability(settings, assignment) == 'multimodal')


def vision_follow_binding(settings: ModelSettings) -> Assignment | None:
    """The model visual understanding follows: an explicit vision assignment, else analysis."""
    return settings.vision or settings.analysis


def vision_follow_lacks_capability(settings: ModelSettings) -> bool:
    """True when explicit visual mode needs vision the followed model cannot provide.

    D7 / Kris「自动退字幕」: ``analysis_mode=auto`` with a known text-only model
    must NOT block readiness — the pipeline falls back to subtitles. Only an
    explicit ``visual`` mode raises ``vision_unsupported``. Unresolved ``auto``
    capability likewise stays open in smart mode.
    Save stays allowed; readiness and generation read this same answer.
    """
    if settings.analysis_mode == 'subtitle':
        return False
    binding = vision_follow_binding(settings)
    if not binding or not binding.model:
        return settings.analysis_mode == 'visual'
    known = capability(settings, binding)
    if known == 'multimodal':
        return False
    # text or unresolved: block only when the user demanded visual understanding
    return settings.analysis_mode == 'visual'


def vision_endpoint(settings: ModelSettings) -> dict | None:
    ensure_runtime_bindings(settings, require_vision=True)
    binding = vision_follow_binding(settings)
    if not sees_images(settings, binding):
        return None
    return chat_endpoint(connection_for(settings, binding), binding.model)


def public(settings: ModelSettings) -> dict:
    value = settings.model_dump()
    notices = [item for item in settings._migration_warnings if item not in settings.seen_notices]
    update_available = preset_update_available(settings)
    value['catalog_version'] = current_catalog_version()
    value['preset_update_available'] = update_available
    if update_available and NOTICE_PRESET_UPDATED not in settings.seen_notices:
        notices.append(NOTICE_PRESET_UPDATED)
    if notices:
        value['migration_warnings'] = list(dict.fromkeys(notices))
    if settings.transcription is None:
        from backend.core.desktop_config import get_desktop_config
        previous = get_desktop_config().speech_recognition.whisper_config.model_name
        try:
            value['transcription'] = Transcription(model=previous).model_dump()
        except ValidationError:
            value['transcription'] = Transcription().model_dump()
            value.setdefault('migration_warnings', []).append('transcription_configuration_invalid')
    value['saved'] = path().exists() and 'settings_configuration_invalid' not in settings._migration_warnings
    if settings.analysis and settings.analysis.model:
        from backend.core.model_recovery import substitution_notices
        pending = [
            item for item in substitution_notices('analysis')
            if item['saved_model'] == settings.analysis.model and item['replacement'] != settings.analysis.model
        ]
        if pending:
            value['model_substitutions'] = pending
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
        previous = for_editing()
        resolved = settings.model_copy(update={
            'connections': prepare_connections_for_save(
                [resolve_secret(c, previous) for c in settings.connections]
            ),
            'cover_choice_version': COVER_CHOICE_VERSION,
            'seen_notices': known_notices([*previous._migration_warnings, *settings.seen_notices, *previous.seen_notices]),
            'acked_catalog_version': max(settings.acked_catalog_version, previous.acked_catalog_version, current_catalog_version()),
        })
        if not resolved.analysis:
            raise ValueError('请选择高光分析模型')
        # Visual-follow without vision: persist (marked red) and block at generation.
        target = path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and 'settings_configuration_invalid' in previous._migration_warnings:
            # Only an explicit valid save may replace a damaged document. Keep
            # its exact bytes privately so omitted connections/keys are recoverable.
            backup = target.with_name('ai-model-settings.invalid.' + uuid.uuid4().hex + '.json')
            with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                stream.write(target.read_bytes())
        _atomic_write_json(target, resolved.model_dump())
        return public(resolved)


def _legacy_assignment(connection: Connection, model: str, purpose: str, capability: Capability = 'auto') -> tuple[Assignment | None, str | None]:
    """Keep a filled legacy model as user (Q16). Invalid models reset to the recommended default."""
    if usable_model(model):
        try:
            return Assignment(connection_id=connection.id, model=model, capability=capability, model_source='user'), None
        except ValidationError:
            pass
    recommended = recommended_model(connection.provider, purpose)
    if not recommended:
        return None, 'cover_configuration_invalid' if purpose == 'cover' else f'{purpose}_configuration_invalid'
    try:
        notice = NOTICE_PURPOSE_RESET if model else None
        return Assignment(connection_id=connection.id, model=recommended, capability=capability, model_source='preset'), notice
    except ValidationError:
        return None, 'cover_configuration_invalid' if purpose == 'cover' else f'{purpose}_configuration_invalid'


def migrate_legacy() -> ModelSettings:
    """Read-only migration: preserve keys; unmigratable purposes reset to recommended defaults."""
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
    connections = []
    migration_warnings = []
    analysis = None
    try:
        connection = Connection(id='legacy-analysis', name=provider, provider=provider,
                                base_url=base, api_key=endpoint.get('api_key', ''))
        analysis, warning = _legacy_assignment(connection, s.get('model_name') or '', 'analysis')
        connections.append(connection)
        if warning:
            migration_warnings.append(warning)
        if analysis is None:
            migration_warnings.append('analysis_configuration_invalid')
    except ValidationError:
        salvaged = try_connection(id='legacy-analysis', name=provider, provider=provider,
                                  base_url='', api_key=endpoint.get('api_key', ''))
        if salvaged:
            analysis, _warning = _legacy_assignment(salvaged, '', 'analysis')
            connections.append(salvaged)
            migration_warnings.append(NOTICE_PURPOSE_RESET if analysis else 'analysis_configuration_invalid')
        else:
            migration_warnings.append('analysis_configuration_invalid')
    v = vision_settings.effective()
    if analysis and v.get('mode') == 'text_model' and v.get('model'):
        # Preserve the already working legacy choice until refreshed metadata is available.
        analysis.capability = 'multimodal'
    vision = None
    if v.get('mode') == 'custom' and v.get('base_url') and v.get('model'):
        try:
            connection = Connection(id='legacy-vision', name='视觉服务', base_url=v['base_url'], api_key=v.get('api_key', ''))
            vision, warning = _legacy_assignment(connection, v.get('model') or '', 'vision', 'multimodal')
            connections.append(connection)
            if warning:
                migration_warnings.append(warning)
        except ValidationError:
            salvaged = try_connection(id='legacy-vision', name='视觉服务', base_url='', api_key=v.get('api_key', ''))
            if salvaged:
                vision, _warning = _legacy_assignment(salvaged, '', 'vision', 'multimodal')
                connections.append(salvaged)
                migration_warnings.append(NOTICE_PURPOSE_RESET if vision else 'vision_configuration_invalid')
            else:
                migration_warnings.append('vision_configuration_invalid')
    cfg = cover.load_config()
    cover_assignment = None
    if cfg.model:
        # Even formerly-following covers become explicit references, so changing
        # the analysis assignment never silently re-routes image generation.
        try:
            if cfg.mode == 'text_model':
                if analysis is None:
                    raise ValueError('invalid legacy analysis')
                cover_assignment, warning = _legacy_assignment(
                    next(c for c in connections if c.id == 'legacy-analysis'), cfg.model, 'cover')
                if warning:
                    migration_warnings.append(warning)
            else:
                kind = {'dashscope': 'dashscope', 'seedream': 'seed',
                        'gemini': 'gemini', 'grok': 'grok', 'glm': 'glm'}.get(cfg.provider, 'openai')
                try:
                    connection = Connection(
                        id='legacy-cover', name='封面服务', provider=kind,
                        api_key=cfg.api_key,
                        image_api='auto' if kind in {'gemini', 'grok', 'glm'} else cfg.provider,
                        base_url=cfg.base_url if kind != 'dashscope' else '',
                        image_base_url=cfg.base_url,
                    )
                    cover_assignment, warning = _legacy_assignment(connection, cfg.model, 'cover')
                    connections.append(connection)
                    if warning:
                        migration_warnings.append(warning)
                except ValidationError:
                    salvaged = try_connection(
                        id='legacy-cover', name='封面服务', provider=kind,
                        api_key=cfg.api_key,
                        image_api='auto' if kind in {'gemini', 'grok', 'glm'} else cfg.provider,
                        base_url='',
                        image_base_url='',
                    )
                    if salvaged is None:
                        raise ValueError('invalid legacy cover')
                    cover_assignment, _warning = _legacy_assignment(salvaged, '', 'cover')
                    connections.append(salvaged)
                    if cover_assignment:
                        migration_warnings.append(NOTICE_PURPOSE_RESET)
                    else:
                        raise ValueError('invalid legacy cover')
        except (ValidationError, ValueError, StopIteration):
            # An optional legacy cover must not block loading or repairing the AI settings.
            # Keep the old file untouched and never send its values in the warning.
            cover_assignment = None
            migration_warnings.append('cover_configuration_invalid')
    prefs = analysis_preferences.load()
    settings = ModelSettings(connections=connections, analysis=analysis, vision=vision,
                         cover=cover_assignment, cover_enabled=cfg.enabled and cover_assignment is not None,
                         allow_send_frame=cfg.allow_send_frame, analysis_mode=prefs.analysis_mode,
                         cover_ocr_model=cfg.ocr_model, vision_timeout=v.get('timeout', 180),
                         allow_visual_screening=prefs.allow_visual_screening,
                         chunk_size=s.get('chunk_size', 5000), min_score_threshold=s.get('min_score_threshold', .7),
                         max_clips_per_collection=s.get('max_clips_per_collection', 5))
    settings._migration_warnings = list(dict.fromkeys([*migration_warnings, *settings._migration_warnings]))
    return settings
