"""User-configured vision endpoint, isolated from the text-model settings."""
import json
import os
import threading
import uuid
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator
from backend.core.path_utils import get_data_directory

_lock = threading.RLock()

class VisionSettingsInput(BaseModel):
    base_url: str = Field(max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=2000)
    clear_key: bool = False
    timeout: int = Field(default=180, ge=10, le=300)

    @field_validator('base_url')
    @classmethod
    def validate_url(cls, value):
        value = value.strip().rstrip('/')
        if value.endswith('/chat/completions'):
            value = value[:-len('/chat/completions')]
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('请填写完整的 HTTP(S) 接口根地址，不包含密钥或查询参数')
        return value

    @field_validator('model')
    @classmethod
    def validate_model(cls, value):
        if not value.strip():
            raise ValueError('请填写模型名称')
        return value.strip()

def effective():
    path = get_data_directory() / 'vision-settings.json'
    if path.exists():
        value = json.loads(path.read_text(encoding='utf-8'))
        return {**value, 'source': 'saved'}
    from dotenv import dotenv_values
    from backend.core.path_utils import get_project_root
    env = {**dotenv_values(get_project_root() / '.env'), **os.environ}
    return {'base_url': env.get('AUTOCLIP_VISION_BASE_URL') or env.get('SEEDANCE_BASE_URL', ''), 'api_key': env.get('AUTOCLIP_VISION_API_KEY') or env.get('SEEDANCE_API_KEY', ''), 'model': env.get('AUTOCLIP_VISION_MODEL', 'doubao-seed-2-1-pro-260915'), 'timeout': 180, 'source': 'environment'}

def public(config=None):
    value = config or effective()
    return {k: v for k, v in value.items() if k != 'api_key'} | {'has_key': bool(value.get('api_key')), 'configured': bool(value.get('base_url') and value.get('model'))}

def merge(body: VisionSettingsInput):
    value = body.model_dump(exclude={'api_key', 'clear_key'})
    value['api_key'] = '' if body.clear_key else body.api_key if body.api_key is not None else effective().get('api_key', '')
    return value

def save(body):
    with _lock:
        config = merge(body)
        path = get_data_directory() / 'vision-settings.json'
        temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, ensure_ascii=False, indent=2)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return public({**config, 'source': 'saved'})

def test(body):
    from backend.services.studio.intelligence import vision_call
    import base64, struct, zlib
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\0\0' * 32) * 32)) + chunk(b'IEND', b'')
    result = vision_call([{'type': 'text', 'text': 'Identify the dominant color of this test image. Return only JSON: {"color":"red|green|blue|other"}.'}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(image).decode()}}], config=merge(body))
    if result.get('color', '').lower() != 'red':
        raise ValueError('接口已响应，但图像识别测试未通过；请确认所选模型支持图片输入')
    return {'ok': True, 'message': '连接与图片理解测试通过'}
