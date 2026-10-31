"""
生图提供商。和对话模型分开：封面只走这里。

支持：
- OpenAI 兼容：POST {base}/images/generations；参考帧优先 /images/edits
- Seedream（火山方舟）：同一 /images/generations，参考帧用 JSON 的 image 字段
- 通义万相：异步 text2image，再轮询 /tasks/{id}

不能图生图的服务只出背景，调用方改用本地排版写标题。
"""
from __future__ import annotations

import base64
import contextvars
import ipaddress
import logging
import re
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests

from backend.core.llm_providers import is_local_url, normalize_base_url
from backend.core.llm_telemetry import sanitize_model

logger = logging.getLogger(__name__)

OPENAI_ROOT = "https://api.openai.com/v1"
DASHSCOPE_ROOT = "https://dashscope.aliyuncs.com/api/v1"
IMAGE_TIMEOUT = 180  # high-quality image models (gpt-image, qwen-image) often take 60–120 s per cover
SEEDREAM_ROOT = "https://ark.cn-beijing.volces.com/api/v3"
SEEDREAM_DEFAULT_MODEL = "doubao-seedream-5-0-260128"
SEEDREAM_DEFAULT_OCR = "doubao-1.5-vision-pro-32k"
OPENAI_PLACEHOLDER_KEY = "EMPTY"
SEEDREAM_MODEL_MARKERS = ("seedream", "doubao-seedream")
SEEDREAM_HOST_MARKERS = ("volces.com", "bytepluses.com", "byteplus.com", "volcengine")


from backend.core.failure_attribution import (  # noqa: E402
    AttributedError, ModelResponseInvalid, ProviderTransportError, attributed, build_attribution)

# the identity of the image config the CURRENT call sent, frozen once by
# ``_image_transport_errors`` so every redaction point inside the call (transport and HTTP status) builds
# its snapshot with it, once.
_call_identity_var: contextvars.ContextVar[dict | None] = contextvars.ContextVar("image_call_identity", default=None)

# Errors requests raises BEFORE anything was sent (a malformed address or header, a body that cannot be
# serialized, no URL): decisively local (X10). ``JSONDecodeError`` subclasses InvalidJSONError
# but is a RESPONSE that failed to parse: the model's side.
_LOCAL_REQUEST_ERRORS = (requests.exceptions.InvalidSchema, requests.exceptions.InvalidURL,
                         requests.exceptions.MissingSchema, requests.exceptions.InvalidHeader,
                         requests.exceptions.InvalidJSONError, requests.exceptions.URLRequired)


def _cover_failure(message: str, original: BaseException, **kwargs) -> "ImageError":
    """THE cover redaction point: ``original`` is content-free (a ``ProviderTransportError`` with type name
    and status, or a ``ModelResponseInvalid``); THE factory builds the snapshot with this call's identity,
    and the status and controlled code are frozen by the same ``attributed`` call."""
    from backend.core.llm_emit import attribution_snapshot
    snap = attribution_snapshot(original, failure_stage='cover', phase_identity=_call_identity_var.get())
    return attributed(ImageError(message, **kwargs), snap, http_status=getattr(original, 'http_status', None),
                      error_code=getattr(original, 'error_code', None))


class ImageError(AttributedError, RuntimeError):
    """Safe text only. a provider transport failure carries the snapshot built from the original
    request exception (``.attribution``) before ``from None``; other ImageErrors carry none."""
    def __init__(self, message: str, *, unsupported_edit: bool = False):
        super().__init__(message)
        self.unsupported_edit = unsupported_edit


def _image_transport_errors(function):
    """Keep provider transport failures inside the local-cover recovery boundary."""
    @wraps(function)
    def call(*args, **kwargs):
        token = _call_identity_var.set(_call_identity(kwargs))
        try:
            return function(*args, **kwargs)
        except requests.exceptions.RequestException as error:
            invalid = (isinstance(error, _LOCAL_REQUEST_ERRORS)
                       and not isinstance(error, requests.exceptions.JSONDecodeError))
            if invalid:
                message = '封面服务接口地址无效，请检查模型设置中的 HTTP(S) 地址'
            elif isinstance(error, requests.exceptions.Timeout):
                message = '封面服务请求超时，请检查服务和网络后重试'
            else:
                message = '封面服务连接失败，请检查接口地址与网络后重试'
            # Request exceptions can include credentials, URLs and response bodies: the one snapshot is
            # built here, inside the boundary (a malformed address never left this machine = local; anything
            # else was sent toward the provider: a content-free ProviderTransportError that THE classifier
            # judges, ), the HTTP status is frozen with it, and the safe error goes out
            # without the chain.
            # the identity is the image config THIS call sent; the controlled error code is
            # frozen with the status.
            if invalid:
                snap = build_attribution(error, local=True, phase_identity=_call_identity_var.get(),
                                         failure_stage='cover')
                raise attributed(ImageError(message), snap) from None
            if isinstance(error, requests.exceptions.JSONDecodeError):
                raise _cover_failure('封面服务返回格式无效，请检查模型设置后重试',
                                     ModelResponseInvalid(type(error).__name__)) from None
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            transport = ProviderTransportError(type(error).__name__, http_status=status,
                                               timed_out=isinstance(error, requests.exceptions.Timeout))
            raise _cover_failure(message, transport) from None
        finally:
            _call_identity_var.reset(token)
    return call


def _call_identity(kwargs: dict) -> dict:
    """provider/config_source/model/host of the image config a call sent (no settings read)."""
    from backend.services.studio.failure_identity import sent_identity
    from backend.core.llm_telemetry import hostname_of_base_url
    request = kwargs.get('request')
    model = kwargs.get('model') or getattr(request, 'model', '') or ''
    base_url = kwargs.get('base_url') if isinstance(kwargs.get('base_url'), str) else ''
    identity = sent_identity(kwargs.get('provider'), base_url, model)
    try:
        host = hostname_of_base_url(base_url) if base_url else None
    except ValueError:
        host = None
    if host:
        identity['base_url_host'] = host
    if isinstance(model, str) and model.strip():
        identity['model'] = model.strip()
    return identity


@dataclass
class ImageRequest:
    prompt: str
    width: int
    height: int
    reference: bytes | None = None
    model: str = ""
    ocr_model: str = ""


def openai_root(base_url: str) -> str:
    root = normalize_base_url(base_url) or OPENAI_ROOT
    if root in ("https://api.openai.com", "http://api.openai.com"):
        return root + "/v1"
    return root


def dashscope_root(base_url: str) -> str:
    return normalize_base_url(base_url) or DASHSCOPE_ROOT


def seedream_root(base_url: str) -> str:
    return normalize_base_url(base_url) or SEEDREAM_ROOT


def is_seedream(*, provider: str = "", model: str = "", base_url: str = "") -> bool:
    kind = (provider or "").strip().lower()
    if kind == "seedream":
        return True
    blob = f"{model} {base_url}".lower()
    return any(m in blob for m in SEEDREAM_MODEL_MARKERS) or any(h in blob for h in SEEDREAM_HOST_MARKERS)


def openai_size(width: int, height: int, model: str = "") -> str:
    """不要求模型吐出平台像素。GPT Image 2.x 接受任意比例（边长为 16 的倍数），直接要平台比例，
    免得 2:3 补边成 9:16 时上下出现色块；更早的模型只认横屏 / 竖屏两种比例。"""
    if "gpt-image-2" in model.lower():
        scale = 1920 / max(width, height)
        return f"{round(width * scale / 16) * 16}x{round(height * scale / 16) * 16}"
    return legacy_openai_size(width, height)


def legacy_openai_size(width: int, height: int) -> str:
    if height > width:
        return "1024x1536"
    return "1536x1024"


def seedream_size(width: int, height: int) -> str:
    """Seedream 5.x 有 2K 像素下限；用接近 16:9 / 9:16 的显式尺寸。"""
    if height > width:
        return "1440x2560"
    return "2560x1440"


def dashscope_size(width: int, height: int) -> str:
    if height > width:
        return "720*1280"
    return "1280*720"


def _session_for(base_url: str, session: requests.Session | None) -> requests.Session:
    if session is not None:
        return session
    http = requests.Session()
    if is_local_url(base_url):
        http.trust_env = False
        http.autoclip_local = True  # a local image server may return its own local image URLs
    return http


def _error_message(resp: Any) -> str:
    data: Any = {}
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {}
    message = ""
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            message = str(err.get("message") or "")
        message = message or str(data.get("message") or data.get("message_") or "")
    if not message:
        text = getattr(resp, "text", "") or ""
        message = text.strip().splitlines()[0] if text.strip() else f"HTTP {getattr(resp, 'status_code', '')}"
    return message[:300]


def _raise_for_status(resp: Any, *, edit: bool = False) -> dict[str, Any]:
    status = int(getattr(resp, "status_code", 200) or 200)
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {}
    if status >= 400 or not isinstance(data, dict):
        # the provider's body only decides "this endpoint cannot edit"; it never becomes
        # the message (fixed text, chosen by status) nor leaves this function. An HTTP error is a
        # content-free ProviderTransportError with the frozen status; a 2xx that is not an object is the
        # model's invalid response. Both get THE snapshot (``_cover_failure``) instead of none (= LOCAL).
        lowered = _error_message(resp).lower()
        unsupported = edit and (
            status in (404, 405)
            or any(word in lowered for word in ("not support", "unsupported", "unknown url", "not found", "invalid endpoint"))
        )
        if status >= 400:
            raise _cover_failure(f'封面服务请求失败（HTTP {status}），请检查密钥、额度和模型权限',
                                 ProviderTransportError('HTTPStatus', http_status=status), unsupported_edit=unsupported)
        raise _cover_failure('封面服务返回格式无效，请检查模型设置后重试', ModelResponseInvalid('NotAnObject'),
                             unsupported_edit=unsupported)
    return data


MAX_IMAGE_BYTES = 40 * 1024 * 1024


def _check_image_url(url: str, allow_local: bool) -> None:
    """The image URL comes from the provider's response: never let it point the backend at this machine
    or its network (the app's own API listens on 127.0.0.1), unless the provider itself is local."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImageError("生图返回的图片地址无效")
    if allow_local:
        return
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ImageError("生图返回的图片地址无效")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified or ip.is_multicast:
        raise ImageError("生图返回的图片地址无效")


def _download(session: requests.Session, url: str) -> bytes:
    allow_local = bool(getattr(session, "autoclip_local", False))
    for _ in range(4):  # follow redirects by hand so every hop is checked
        _check_image_url(url, allow_local)
        resp = session.get(url, timeout=60, stream=True, allow_redirects=False)
        status = int(getattr(resp, "status_code", 200) or 200)
        location = (getattr(resp, "headers", None) or {}).get("location")
        if status in (301, 302, 303, 307, 308) and location:
            url = urljoin(url, location)
            continue
        break
    else:
        raise ImageError("下载生成图失败")
    if status >= 400:
        raise ImageError("下载生成图失败")
    if hasattr(resp, "iter_content"):
        content = bytearray()
        for chunk in resp.iter_content(1 << 16):
            content += chunk
            if len(content) > MAX_IMAGE_BYTES:
                raise ImageError("生成图过大")
        content = bytes(content)
    else:
        content = getattr(resp, "content", b"") or b""
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ImageError("下载生成图失败")
    return content


def _decode_b64(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except Exception as exc:  # noqa: BLE001
        raise ImageError("生图返回的图片无法解析") from exc


def _openai_image(data: dict[str, Any], session: requests.Session) -> bytes:
    items = data.get("data")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise ImageError("生图没有返回图片")
    item = items[0]
    if item.get("b64_json"):
        return _decode_b64(str(item["b64_json"]))
    url = str(item.get("url") or "")
    if url.startswith(("http://", "https://")):
        return _download(session, url)
    raise ImageError("生图没有返回图片")


def _bearer(api_key: str, base_url: str) -> dict[str, str]:
    key = (api_key or "").strip()
    if not key and base_url:
        key = OPENAI_PLACEHOLDER_KEY
    if not key:
        raise ImageError("还没有配置生图密钥")
    return {"Authorization": f"Bearer {key}"}


def _post_json(
    session: requests.Session,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    *,
    seedream: bool = False,
) -> Any:
    resp = session.post(url, headers={**headers, "Content-Type": "application/json"}, json=body, timeout=IMAGE_TIMEOUT)
    if int(getattr(resp, "status_code", 200) or 200) == 400:
        message = _error_message(resp).lower()
        retry = dict(body)
        changed = False
        if "response_format" in retry and "response_format" in message:
            retry.pop("response_format", None)
            changed = True
        if "n" in retry and ("n" in message or "parameter" in message) and seedream:
            retry.pop("n", None)
            changed = True
        if "size" in message:
            current = str(retry.get("size") or "")
            if seedream:
                fallback = "2K"
                if current != fallback:
                    retry["size"] = fallback
                    changed = True
            elif current not in (None, "", "1024x1024"):
                width, height = (int(n) for n in current.split("x")) if re.fullmatch(r"\d+x\d+", current) else (1, 1)
                legacy = legacy_openai_size(width, height) if width != height else "1024x1024"
                retry["size"] = legacy if current != legacy else "1024x1024"
                changed = True
        if "watermark" in message and "watermark" in retry:
            retry.pop("watermark", None)
            changed = True
        if changed:
            resp = session.post(url, headers={**headers, "Content-Type": "application/json"}, json=retry, timeout=IMAGE_TIMEOUT)
    return resp


def _reference_data_uri(reference: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(reference).decode("ascii")


def generate_openai(
    *,
    api_key: str,
    base_url: str,
    request: ImageRequest,
    session: requests.Session | None = None,
    force_seedream: bool = False,
) -> bytes:
    seedream = force_seedream or is_seedream(model=request.model, base_url=base_url)
    root = seedream_root(base_url) if seedream else openai_root(base_url)
    http = _session_for(root, session)
    headers = _bearer(api_key, base_url)
    model = request.model.strip() or (SEEDREAM_DEFAULT_MODEL if seedream else "gpt-image-1")
    size = seedream_size(request.width, request.height) if seedream else openai_size(request.width, request.height, model)

    if request.reference and seedream:
        body: dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
            "size": size,
            "image": _reference_data_uri(request.reference),
            "response_format": "url",
            "watermark": False,
        }
        resp = _post_json(http, f"{root}/images/generations", headers, body, seedream=True)
        return _openai_image(_raise_for_status(resp, edit=True), http)

    if request.reference:
        def edit(size: str):
            return http.post(
                f"{root}/images/edits",
                headers=headers,
                data={"model": model, "prompt": request.prompt, "size": size, "n": "1"},
                files={"image": ("frame.jpg", request.reference, "image/jpeg")},
                timeout=IMAGE_TIMEOUT,
            )
        resp = edit(size)
        legacy = legacy_openai_size(request.width, request.height)
        if int(getattr(resp, "status_code", 200) or 200) == 400 and size != legacy and "size" in _error_message(resp).lower():
            # A relay that maps the model to an older backend rejects the platform ratio: use its own.
            size = legacy
            resp = edit(size)
        try:
            data = _raise_for_status(resp, edit=True)
            return _openai_image(data, http)
        except ImageError as exc:
            if not exc.unsupported_edit:
                raise
            body = {
                "model": model,
                "prompt": request.prompt,
                "size": size,
                "image": _reference_data_uri(request.reference),
                "response_format": "b64_json",
            }
            retry = _post_json(http, f"{root}/images/generations", headers, body)
            return _openai_image(_raise_for_status(retry, edit=True), http)

    body = {
        "model": model,
        "prompt": request.prompt,
        "size": size,
        "response_format": "url" if seedream else "b64_json",
    }
    if seedream:
        body["watermark"] = False
    else:
        body["n"] = 1
    resp = _post_json(http, f"{root}/images/generations", headers, body, seedream=seedream)
    return _openai_image(_raise_for_status(resp), http)


def _dashscope_bytes(data: dict[str, Any], session: requests.Session) -> bytes | None:
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    status = str(output.get("task_status") or "")
    if status in ("FAILED", "CANCELED", "UNKNOWN"):
        message = str(output.get("message") or data.get("message") or "")
        lowered = message.lower()
        unsupported = any(word in lowered for word in ("ref_img", "not support", "unsupported", "invalidparameter"))
        if message:
            logger.warning("DashScope image task %s omitted from UI: %s", status, message[:300])
            from backend.core.failure_codes import sentence
            raise ImageError(sentence("unexpected"), unsupported_edit=unsupported)
        raise ImageError("生图失败", unsupported_edit=unsupported)
    results = output.get("results") if isinstance(output.get("results"), list) else []
    if results and isinstance(results[0], dict):
        item = results[0]
        if item.get("b64_image"):
            return _decode_b64(str(item["b64_image"]))
        url = str(item.get("url") or "")
        if url.startswith(("http://", "https://")):
            return _download(session, url)
    for choice in output.get('choices') or []:
        for part in (choice.get('message') or {}).get('content') or []:
            if isinstance(part, dict) and str(part.get('image', '')).startswith(('https://', 'http://')):
                return _download(session, part['image'])
    if status == "SUCCEEDED":
        raise ImageError("生图没有返回图片")
    return None


def generate_dashscope(
    *,
    api_key: str,
    base_url: str,
    request: ImageRequest,
    session: requests.Session | None = None,
    cancel: Any = None,
    poll_interval: float = 1.5,
) -> bytes:
    root = dashscope_root(base_url)
    http = _session_for(root, session)
    headers = {**_bearer(api_key, base_url), "X-DashScope-Async": "enable"}
    model = request.model.strip() or "wanx2.1-t2i-turbo"
    modern_qwen = model.startswith('qwen-image') or model == 'z-image-turbo'
    modern_wan = model.startswith(('wan2.7-image', 'wan2.6-image', 'wan2.6-t2i'))
    if modern_qwen or modern_wan:
        content = [{'text': request.prompt}]
        if request.reference:
            if model in {'qwen-image', 'z-image-turbo'} or model.startswith(('qwen-image-plus', 'qwen-image-max')):
                raise ImageError('该模型不支持参考帧', unsupported_edit=True)
            content.insert(0, {'image': _reference_data_uri(request.reference)})
        if modern_qwen:
            headers.pop('X-DashScope-Async', None)
        route = 'image-generation' if modern_wan else 'multimodal-generation'
        sizes = {'928*1664': 928 / 1664, '1140*1472': 1140 / 1472, '1328*1328': 1.0, '1472*1140': 1472 / 1140, '1664*928': 1664 / 928}
        size = min(sizes, key=lambda key: abs(sizes[key] - request.width / max(1, request.height)))
        if model.startswith('wan2.6-t2i'):
            size = '960*1696' if request.height > request.width else '1696*960'
        resp = http.post(f'{root}/services/aigc/{route}/generation',
            headers={**headers, 'Content-Type': 'application/json'},
            json={'model': model, 'input': {'messages': [{'role': 'user', 'content': content}]},
                  'parameters': {'size': size, 'n': 1}}, timeout=IMAGE_TIMEOUT)
    else:
        return _generate_legacy_dashscope(api_key=api_key, base_url=base_url, request=request, session=http,
                                         cancel=cancel, poll_interval=poll_interval)
    return _wait_dashscope(_raise_for_status(resp, edit=bool(request.reference)), http, root, api_key,
                          cancel=cancel, poll_interval=poll_interval)


def _generate_legacy_dashscope(*, api_key, base_url, request, session, cancel, poll_interval):
    root, http = dashscope_root(base_url), session
    headers = {**_bearer(api_key, base_url), 'X-DashScope-Async': 'enable'}
    model = request.model.strip() or 'wanx2.1-t2i-turbo'
    image_input: dict[str, Any] = {"prompt": request.prompt}
    if request.reference:
        image_input["ref_img"] = _reference_data_uri(request.reference)
    size = ('960*1696' if request.height > request.width else '1696*960') if model.startswith('wan2.5-t2i') else dashscope_size(request.width, request.height)
    resp = http.post(
        f"{root}/services/aigc/text2image/image-synthesis",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "model": model,
            "input": image_input,
            "parameters": {"size": size, "n": 1},
        },
        timeout=60,
    )
    data = _raise_for_status(resp, edit=bool(request.reference))
    return _wait_dashscope(data, http, root, api_key, cancel=cancel, poll_interval=poll_interval)


def _wait_dashscope(data, http, root, api_key, *, cancel, poll_interval):
    ready = _dashscope_bytes(data, http)
    if ready is not None:
        return ready
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    task_id = str(output.get("task_id") or "")
    if not task_id:
        raise ImageError("生图没有返回任务")
    for _ in range(40):
        if cancel is not None and cancel.is_set():
            raise ImageError("已取消")
        if poll_interval:
            time.sleep(poll_interval)
        if cancel is not None and cancel.is_set():
            raise ImageError("已取消")
        polled = http.get(f"{root}/tasks/{task_id}", headers=_bearer(api_key, root), timeout=30)
        ready = _dashscope_bytes(_raise_for_status(polled), http)
        if ready is not None:
            return ready
    raise ImageError("生图超时")


def generate_gemini(*, api_key, base_url, request, session=None):
    root = (normalize_base_url(base_url) or 'https://generativelanguage.googleapis.com/v1beta').removesuffix('/openai')
    http = _session_for(root, session)
    parts = [{'text': request.prompt}]
    if request.reference:
        parts.insert(0, {'inlineData': {'mimeType': 'image/jpeg', 'data': base64.b64encode(request.reference).decode('ascii')}})
    response = http.post(f'{root}/models/{quote(request.model, safe="")}:generateContent',
        headers={'x-goog-api-key': api_key, 'Content-Type': 'application/json'},
        json={'contents': [{'role': 'user', 'parts': parts}], 'generationConfig': {
            'responseModalities': ['TEXT', 'IMAGE'], 'imageConfig': {'aspectRatio': '9:16' if request.height > request.width else '16:9'}}}, timeout=120)
    data = _raise_for_status(response, edit=bool(request.reference))
    for candidate in data.get('candidates') or []:
        for part in (candidate.get('content') or {}).get('parts') or []:
            inline = part.get('inlineData') or part.get('inline_data') or {}
            if inline.get('data') and str(inline.get('mimeType') or inline.get('mime_type') or '').startswith('image/'):
                return _decode_b64(inline['data'])
    raise ImageError('生图没有返回图片')


def generate_vendor_image(*, provider, api_key, base_url, request, session=None):
    root = normalize_base_url(base_url) or ('https://api.x.ai/v1' if provider == 'grok' else 'https://open.bigmodel.cn/api/paas/v4')
    http = _session_for(root, session)
    body = {'model': request.model, 'prompt': request.prompt}
    route = 'generations'
    if provider == 'grok':
        body.update(aspect_ratio='9:16' if request.height > request.width else '16:9', response_format='b64_json', n=1)
        if request.reference:
            route = 'edits'
            body['image'] = {'url': _reference_data_uri(request.reference)}
    else:
        if request.reference:
            raise ImageError('该模型不支持参考帧', unsupported_edit=True)
        body['size'] = '960x1728' if request.height > request.width else '1728x960'
    response = http.post(f'{root}/images/{route}', headers={**_bearer(api_key, root), 'Content-Type': 'application/json'}, json=body, timeout=120)
    return _openai_image(_raise_for_status(response, edit=bool(request.reference)), http)


FAL_ROOT = "https://fal.run"


def generate_fal(*, api_key: str, base_url: str, request: ImageRequest, session: requests.Session | None = None) -> bytes:
    """fal.ai models (e.g. `openai/gpt-image-2.5/flare`): `/edit` with the reference frame, else `/text-to-image`.

    The exact output size is requested, so nothing has to be cropped off the generated layout.
    """
    root = (base_url or FAL_ROOT).rstrip("/")
    http = _session_for(root, session)
    model = request.model.strip().strip("/") or "openai/gpt-image-2.5/flare"
    if not model.endswith(("/edit", "/text-to-image")):
        model += "/edit" if request.reference else "/text-to-image"
    body: dict[str, Any] = {"prompt": request.prompt, "image_size": {"width": request.width, "height": request.height}}
    if request.reference:
        body["image_urls"] = [_reference_data_uri(request.reference)]
    resp = http.post(f"{root}/{model}", headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
                     json=body, timeout=IMAGE_TIMEOUT)
    data = _raise_for_status(resp, edit=bool(request.reference))
    images = data.get("images") or []
    url = (images[0] or {}).get("url") if images else None
    if not url:
        raise ImageError("fal 没有返回图片")
    if url.startswith("data:"):
        return _decode_b64(url.split(",", 1)[1])
    return _download(http, url)


@_image_transport_errors
def generate_image(
    *,
    provider: str,
    api_key: str,
    base_url: str,
    request: ImageRequest,
    session: requests.Session | None = None,
    cancel: Any = None,
    poll_interval: float = 1.5,
) -> bytes:
    kind = (provider or "openai").strip().lower()
    logger.info("封面生图 provider=%s model=%s reference=%s", kind, sanitize_model(request.model) or "-", bool(request.reference))
    if kind == 'gemini':
        return generate_gemini(api_key=api_key, base_url=base_url, request=request, session=session)
    if kind == 'fal':
        return generate_fal(api_key=api_key, base_url=base_url, request=request, session=session)
    if kind in {'grok', 'glm'}:
        return generate_vendor_image(provider=kind, api_key=api_key, base_url=base_url, request=request, session=session)
    if kind == "dashscope":
        return generate_dashscope(
            api_key=api_key,
            base_url=base_url,
            request=request,
            session=session,
            cancel=cancel,
            poll_interval=poll_interval,
        )
    return generate_openai(
        api_key=api_key,
        base_url=base_url,
        request=request,
        session=session,
        force_seedream=(kind == "seedream"),
    )


_OCR_SKIP = "未选择可用于封面校对的多模态模型，跳过校对"


def _ocr_catalog_endpoint(provider: str, base_url: str) -> tuple[str, str]:
    """Catalog slug and base for ``GET /models``.

    Bailian image calls stay on ``/api/v1``. The account list is the OpenAI-compatible
    catalog on the same official host. A relay or proxy is left exactly as entered.
    """
    from urllib.parse import urlparse

    from backend.core.llm_providers import (
        DASHSCOPE_CN_COMPATIBLE_BASE_URL,
        is_dashscope_endpoint,
    )

    kind = (provider or "").strip().lower()
    raw = (base_url or "").strip()
    if kind != "dashscope" and not is_dashscope_endpoint(raw):
        return kind or "compatible", raw
    if not raw:
        return "dashscope", DASHSCOPE_CN_COMPATIBLE_BASE_URL
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower()
    if host.endswith(".aliyuncs.com"):
        root = raw.rstrip("/")
        if "://" not in root:
            root = "https://" + root
        root = root.removesuffix("/compatible-mode/v1").removesuffix("/api/v1")
        return "dashscope", root + "/compatible-mode/v1"
    return "dashscope", raw.rstrip("/")


def default_ocr_model(
    provider: str,
    model: str = "",
    base_url: str = "",
    *,
    api_key: str = "",
    http=None,
) -> str:
    """OCR model when the caller did not choose one.

    Bailian asks the account list. Preset vision ids only order that list.
    An unreadable list returns ``""`` so the caller skips proofreading instead of
    sending a retired id. Seedream and other providers keep their existing defaults.
    """
    kind = (provider or "").strip().lower()
    from backend.core.llm_providers import is_dashscope_endpoint
    if kind == "dashscope" or is_dashscope_endpoint(base_url):
        from backend.core.model_recovery import (
            remembered_model,
            resolve_available_model,
        )
        catalog, models_base = _ocr_catalog_endpoint(kind or "dashscope", base_url)
        alt = resolve_available_model(
            base_url=models_base,
            api_key=api_key,
            provider=catalog,
            failed_model="",
            http=http,
        )
        if not alt:
            return ""
        cached = remembered_model(catalog, models_base, api_key, alt)
        return cached or alt
    if is_seedream(provider=kind, model=model, base_url=base_url):
        return SEEDREAM_DEFAULT_OCR
    return "gpt-4o-mini"


def _response_is_model_not_found(resp: Any) -> bool:
    status = int(getattr(resp, "status_code", 200) or 200)
    if status < 400:
        return False
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001 — classify from the text when JSON is unavailable
        body = getattr(resp, "text", "") or ""
    from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error
    return classify_upstream_error(status, body).error_type is UpstreamErrorType.MODEL_NOT_FOUND


def _dashscope_ocr_body(model: str, root: str, data_uri: str, instruction: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "input": {"messages": [{"role": "user", "content": [
            {"image": data_uri},
            {"text": instruction},
        ]}]},
    }
    if _qwen_thinking_off(model, root):
        body["parameters"] = {"enable_thinking": False}
    return body


def _compatible_ocr_body(model: str, root: str, data_uri: str, instruction: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]}],
        # Cover OCR is a short read and stays one JSON body. Analysis chat streams.
        "stream": False,
    }
    if _qwen_thinking_off(model, root):
        body["enable_thinking"] = False
    return body


def _text_from_dashscope_ocr(data: dict[str, Any]) -> str:
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    choices = output.get("choices") if isinstance(output.get("choices"), list) else []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts).strip()
    return str(output.get("text") or "").strip()


def _text_from_chat_ocr(data: dict[str, Any]) -> str:
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    if not choices or not isinstance(choices[0], dict):
        raise ImageError("没有读出画面上的字")
    message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
    return str(message.get("content") or "").strip()


def _qwen_thinking_off(model: str, root: str) -> bool:
    """Cover OCR on a Bailian Qwen3.5–3.8 hybrid model: no hidden reasoning (see llm_providers)."""
    from backend.core.llm_providers import disables_qwen_thinking
    return disables_qwen_thinking(model, root)


@_image_transport_errors
def read_image_text(
    *,
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    image: bytes,
    session: requests.Session | None = None,
    http=None,
) -> str:
    """让多模态模型只读图上的字。失败抛 ImageError，调用方视为跳过校对。

    A saved id the provider no longer offers is replaced once from the account
    list, in memory only. ``http`` is the optional ``GET /models`` transport.
    """
    kind = (provider or "openai").strip().lower()
    data_uri = _reference_data_uri(image)
    instruction = "只输出画面上的文字，保持原有换行。不要解释，不要补充画面里没有的字。"
    saved = (model or "").strip()
    catalog, models_base = _ocr_catalog_endpoint(kind, base_url)
    from backend.core.model_recovery import (
        remember_model,
        remembered_model,
        resolve_available_model,
    )
    if saved:
        current = remembered_model(catalog, models_base, api_key, saved) or saved
    else:
        current = default_ocr_model(kind, model=model, base_url=base_url, api_key=api_key, http=http)
    if not current:
        raise ImageError(_OCR_SKIP)
    tried_substitute = False
    replaced = ""
    resp: Any = None
    while True:
        if kind == "dashscope":
            root = dashscope_root(base_url)
            client = _session_for(root, session)
            resp = client.post(
                f"{root}/services/aigc/multimodal-generation/generation",
                headers={**_bearer(api_key, base_url), "Content-Type": "application/json"},
                json=_dashscope_ocr_body(current, root, data_uri, instruction),
                timeout=60,
            )
        else:
            seedream = is_seedream(provider=kind, model=model, base_url=base_url)
            root = seedream_root(base_url) if seedream or kind == "seedream" else openai_root(base_url)
            client = _session_for(root, session)
            resp = _post_json(
                client,
                f"{root}/chat/completions",
                _bearer(api_key, base_url),
                _compatible_ocr_body(current, root, data_uri, instruction),
                seedream=seedream or kind == "seedream",
            )
        if not tried_substitute and _response_is_model_not_found(resp):
            tried_substitute = True
            alt = resolve_available_model(
                base_url=models_base,
                api_key=api_key,
                provider=catalog,
                failed_model=current,
                exclude=(saved, current),
                http=http,
            )
            if alt and alt != current:
                replaced = current
                current = alt
                continue
        break
    data = _raise_for_status(resp)
    # Remember only an id that answered, so the next cover does not repeat the 404.
    if saved and current != saved:
        remember_model(catalog, models_base, api_key, saved, current)
    if replaced and replaced != current:
        remember_model(catalog, models_base, api_key, replaced, current)
    if kind == "dashscope":
        return _text_from_dashscope_ocr(data)
    return _text_from_chat_ocr(data)
