"""视觉理解模型配置。

默认复用文本模型（mode=text_model）：同一个提供商、key、模型直接发图片消息，用户只配一次。
模型是否多模态由 model_catalog.supports_vision 判断；仅文字的模型视为「不能看画面」，
视觉分析与视觉初筛自动不启用，只用字幕。旧版独立视觉接口（mode=custom）仍然兼容。

兼容旧数据：已有 vision-settings.json 但没有 mode 字段的，视为 custom；
没保存过、但 .env 里配了 AUTOCLIP_VISION_BASE_URL 的（Docker），也按 custom 用环境变量。

能不能看图不靠猜：「测试图片理解」通过后记下 base_url + 模型，配置变了就回到未验证。
付费视觉调用仍由 analysis_preferences 的显式同意控制，这里只提供端点。
"""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator
from backend.core.path_utils import get_data_directory

_lock = threading.RLock()
VisionMode = Literal['text_model', 'custom']


class VisionSettingsInput(BaseModel):
    mode: VisionMode = 'custom'
    base_url: str = Field(default='', max_length=1000)
    model: str = Field(default='', max_length=200)
    api_key: str | None = Field(default=None, max_length=2000)
    clear_key: bool = False
    timeout: int = Field(default=180, ge=10, le=300)

    @field_validator('base_url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        if value.endswith('/chat/completions'):
            value = value[:-len('/chat/completions')]
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('请填写完整的 HTTP(S) 接口根地址，不包含密钥或查询参数')
        return value

    @model_validator(mode='after')
    def custom_needs_endpoint(self):
        self.model = self.model.strip()
        if self.mode == 'custom':
            if not self.base_url:
                raise ValueError('请填写完整的 HTTP(S) 接口根地址，不包含密钥或查询参数')
            if not self.model:
                raise ValueError('请填写模型名称')
        return self


def _path():
    return get_data_directory() / 'vision-settings.json'


def _saved():
    path = _path()
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    value.setdefault('mode', 'custom')
    return value


def _environment():
    from dotenv import dotenv_values
    from backend.core.path_utils import get_project_root
    env = {**dotenv_values(get_project_root() / '.env'), **os.environ}
    base = env.get('AUTOCLIP_VISION_BASE_URL') or env.get('SEEDANCE_BASE_URL', '')
    if not base:
        return None
    return {'mode': 'custom', 'base_url': base, 'api_key': env.get('AUTOCLIP_VISION_API_KEY') or env.get('SEEDANCE_API_KEY', ''),
            'model': env.get('AUTOCLIP_VISION_MODEL', 'doubao-seed-2-1-pro-260915'), 'timeout': 180, 'source': 'environment'}


def text_model_endpoint():
    """文本模型的 OpenAI 兼容端点；本地 / 未配置时返回 None。"""
    try:
        from backend.core.llm_manager import get_llm_manager
        return get_llm_manager().openai_compatible_endpoint()
    except Exception:  # noqa: BLE001 - 读设置失败时视为未配置，不影响字幕分析
        return None


def _with_text_model(stored):
    from backend.core.model_catalog import supports_vision
    endpoint = text_model_endpoint() or {'base_url': '', 'api_key': '', 'model': ''}
    text_model = endpoint.get('model', '')
    if not supports_vision(text_model):
        # 仅文字模型：不当成视觉端点，避免把图片发给不支持的模型
        endpoint = {'base_url': '', 'api_key': '', 'model': ''}
    return {**endpoint, 'mode': 'text_model', 'text_model': text_model, 'timeout': stored.get('timeout', 180),
            'verified': stored.get('verified')}


def effective():
    from backend.services import ai_model_settings as ai
    settings = ai.load()
    if settings:
        endpoint = ai.vision_endpoint(settings)
        binding = settings.vision or settings.analysis
        return {**(endpoint or {'base_url': '', 'api_key': '', 'model': ''}),
                'mode': 'custom' if settings.vision else 'text_model', 'source': 'connections',
                'text_model': binding.model if binding else '', 'timeout': settings.vision_timeout}
    saved = _saved()
    if saved is not None:
        if saved['mode'] == 'text_model':
            return {**_with_text_model(saved), 'source': 'saved'}
        return {**saved, 'source': 'saved'}
    env = _environment()
    if env is not None:
        return env
    return {**_with_text_model({}), 'source': 'default'}


def _fingerprint(config):
    return f"{(config.get('base_url') or '').rstrip('/')}|{config.get('model') or ''}"


def public(config=None):
    value = config or effective()
    verified = value.get('verified') or {}
    return {
        'mode': value.get('mode', 'custom'),
        'base_url': value.get('base_url', ''),
        'model': value.get('model', ''),
        'timeout': value.get('timeout', 180),
        'source': value.get('source', ''),
        'has_key': bool(value.get('api_key')),
        'configured': bool(value.get('base_url') and value.get('model')),
        # 跟随文本模型但它只能处理文字
        'text_only': value.get('mode') == 'text_model' and bool(value.get('text_model')) and not value.get('model'),
        # 当前端点测试通过过才算「能看图」；换了模型或地址就失效
        'verified': bool(verified) and verified.get('fingerprint') == _fingerprint(value),
        'verified_at': verified.get('at') if verified.get('fingerprint') == _fingerprint(value) else None,
    }


def merge(body: VisionSettingsInput):
    previous = _saved() or _environment() or {}
    if body.mode == 'text_model':
        return {'mode': 'text_model', 'timeout': body.timeout, 'verified': previous.get('verified')}
    value = body.model_dump(exclude={'api_key', 'clear_key'})
    old_key = previous.get('api_key', '') if previous.get('mode', 'custom') == 'custom' else ''
    value['api_key'] = '' if body.clear_key else body.api_key if body.api_key is not None else old_key
    value['verified'] = previous.get('verified')
    return value


def _write(config):
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def save(body):
    with _lock:
        _write(merge(body))
        return public(effective())


def _resolve(body):
    """测试用的完整端点：text_model 用当前已保存的文本模型，custom 用表单里的值。"""
    stored = merge(body)
    if body.mode == 'text_model':
        resolved = _with_text_model(stored)
        if not resolved['base_url'] or not resolved['model']:
            raise ValueError('当前文本模型不支持图片接口测试，请先保存 AI 模型设置，或另选视觉模型')
        return resolved
    return stored


def test(body):
    from backend.services.studio.intelligence import vision_call
    import base64, struct, zlib
    config = _resolve(body)
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\0\0' * 32) * 32)) + chunk(b'IEND', b'')
    result = vision_call([{'type': 'text', 'text': 'Identify the dominant color of this test image. Return only JSON: {"color":"red|green|blue|other"}.'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image).decode()}}], config=config)
    if result.get('color', '').lower() != 'red':
        raise ValueError('接口已响应，但图像识别测试未通过；请确认所选模型支持图片输入')
    # 记下通过验证的端点。只有已保存的配置才更新标记，未保存的表单值测试通过不落盘。
    with _lock:
        saved = _saved()
        if saved is not None and _fingerprint(_with_text_model(saved) if saved['mode'] == 'text_model' else saved) == _fingerprint(config):
            saved['verified'] = {'fingerprint': _fingerprint(config), 'at': datetime.now(timezone.utc).isoformat()}
            _write(saved)
    return {'ok': True, 'message': '连接与图片理解测试通过', 'model': config.get('model', '')}
