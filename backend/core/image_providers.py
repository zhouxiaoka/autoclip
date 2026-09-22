"""
生图提供商。和对话模型分开：封面只走这里。

支持两类接口，都用本地 HTTP 替身测过：
- OpenAI 兼容：POST {base}/images/generations，有参考帧时再试 {base}/images/edits
- 通义万相：异步 text2image，再轮询 /tasks/{id}

不能图生图的服务只出背景，调用方改用本地排版写标题。
"""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from backend.core.llm_providers import is_local_url, normalize_base_url

logger = logging.getLogger(__name__)

OPENAI_ROOT = "https://api.openai.com/v1"
DASHSCOPE_ROOT = "https://dashscope.aliyuncs.com/api/v1"
OPENAI_PLACEHOLDER_KEY = "EMPTY"


class ImageError(RuntimeError):
    def __init__(self, message: str, *, unsupported_edit: bool = False):
        super().__init__(message)
        self.unsupported_edit = unsupported_edit


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


def openai_size(width: int, height: int) -> str:
    """不要求模型吐出平台像素。横屏 / 竖屏各要一个它认识的比例。"""
    if height > width:
        return "1024x1536"
    return "1536x1024"


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
        message = message or str(data.get("message") or "")
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
        message = _error_message(resp)
        lowered = message.lower()
        unsupported = edit and (
            status in (404, 405)
            or any(word in lowered for word in ("not support", "unsupported", "unknown url", "not found", "invalid endpoint"))
        )
        raise ImageError(message or "生图失败", unsupported_edit=unsupported)
    return data


def _download(session: requests.Session, url: str) -> bytes:
    resp = session.get(url, timeout=60)
    status = int(getattr(resp, "status_code", 200) or 200)
    content = getattr(resp, "content", b"") or b""
    if status >= 400 or not content:
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


def _post_json(session: requests.Session, url: str, headers: dict[str, str], body: dict[str, Any]) -> Any:
    resp = session.post(url, headers={**headers, "Content-Type": "application/json"}, json=body, timeout=90)
    if int(getattr(resp, "status_code", 200) or 200) == 400:
        message = _error_message(resp).lower()
        retry = dict(body)
        changed = False
        if "response_format" in retry and "response_format" in message:
            retry.pop("response_format", None)
            changed = True
        if "size" in message and retry.get("size") not in (None, "1024x1024"):
            retry["size"] = "1024x1024"
            changed = True
        if changed:
            resp = session.post(url, headers={**headers, "Content-Type": "application/json"}, json=retry, timeout=90)
    return resp


def generate_openai(
    *,
    api_key: str,
    base_url: str,
    request: ImageRequest,
    session: requests.Session | None = None,
) -> bytes:
    root = openai_root(base_url)
    http = _session_for(root, session)
    headers = _bearer(api_key, base_url)
    size = openai_size(request.width, request.height)
    model = request.model.strip() or "gpt-image-1"
    if request.reference:
        resp = http.post(
            f"{root}/images/edits",
            headers=headers,
            data={"model": model, "prompt": request.prompt, "size": size, "n": "1"},
            files={"image": ("frame.jpg", request.reference, "image/jpeg")},
            timeout=90,
        )
        data = _raise_for_status(resp, edit=True)
        return _openai_image(data, http)
    resp = _post_json(http, f"{root}/images/generations", headers, {
        "model": model,
        "prompt": request.prompt,
        "size": size,
        "n": 1,
        "response_format": "b64_json",
    })
    return _openai_image(_raise_for_status(resp), http)


def _dashscope_bytes(data: dict[str, Any], session: requests.Session) -> bytes | None:
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    status = str(output.get("task_status") or "")
    if status in ("FAILED", "CANCELED", "UNKNOWN"):
        message = str(output.get("message") or data.get("message") or "生图失败")
        lowered = message.lower()
        unsupported = any(word in lowered for word in ("ref_img", "not support", "unsupported", "invalidparameter"))
        raise ImageError(message[:300], unsupported_edit=unsupported)
    results = output.get("results") if isinstance(output.get("results"), list) else []
    if results and isinstance(results[0], dict):
        item = results[0]
        if item.get("b64_image"):
            return _decode_b64(str(item["b64_image"]))
        url = str(item.get("url") or "")
        if url.startswith(("http://", "https://")):
            return _download(session, url)
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
    image_input: dict[str, Any] = {"prompt": request.prompt}
    if request.reference:
        image_input["ref_img"] = "data:image/jpeg;base64," + base64.b64encode(request.reference).decode("ascii")
    resp = http.post(
        f"{root}/services/aigc/text2image/image-synthesis",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "model": model,
            "input": image_input,
            "parameters": {"size": dashscope_size(request.width, request.height), "n": 1},
        },
        timeout=60,
    )
    data = _raise_for_status(resp, edit=bool(request.reference))
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
        polled = http.get(f"{root}/tasks/{task_id}", headers=_bearer(api_key, base_url), timeout=30)
        ready = _dashscope_bytes(_raise_for_status(polled), http)
        if ready is not None:
            return ready
    raise ImageError("生图超时")


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
    logger.info("封面生图 provider=%s model=%s reference=%s", kind, request.model or "-", bool(request.reference))
    if kind == "dashscope":
        return generate_dashscope(
            api_key=api_key,
            base_url=base_url,
            request=request,
            session=session,
            cancel=cancel,
            poll_interval=poll_interval,
        )
    return generate_openai(api_key=api_key, base_url=base_url, request=request, session=session)


def read_image_text(
    *,
    provider: str,
    api_key: str,
    base_url: str,
    model: str,
    image: bytes,
    session: requests.Session | None = None,
) -> str:
    """让多模态模型只读图上的字。失败抛 ImageError，调用方视为跳过校对。"""
    kind = (provider or "openai").strip().lower()
    data_uri = "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
    instruction = "只输出画面上的文字，保持原有换行。不要解释，不要补充画面里没有的字。"
    if kind == "dashscope":
        root = dashscope_root(base_url)
        http = _session_for(root, session)
        resp = http.post(
            f"{root}/services/aigc/multimodal-generation/generation",
            headers={**_bearer(api_key, base_url), "Content-Type": "application/json"},
            json={
                "model": model.strip() or "qwen-vl-plus",
                "input": {"messages": [{"role": "user", "content": [
                    {"image": data_uri},
                    {"text": instruction},
                ]}]},
            },
            timeout=60,
        )
        data = _raise_for_status(resp)
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
        text = str(output.get("text") or "")
        return text.strip()
    root = openai_root(base_url)
    http = _session_for(root, session)
    resp = _post_json(http, f"{root}/chat/completions", _bearer(api_key, base_url), {
        "model": model.strip() or "gpt-4o-mini",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]}],
    })
    data = _raise_for_status(resp)
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    if not choices or not isinstance(choices[0], dict):
        raise ImageError("没有读出画面上的字")
    message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
    return str(message.get("content") or "").strip()
