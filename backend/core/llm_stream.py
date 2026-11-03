"""Consume OpenAI-compatible streams so a long think does not sit on a silent socket.

Text and vision completions ask for ``stream: true`` and assemble the deltas.
A host that rejects the flag, or answers HTTP 200 with one JSON body, is read
as a normal completion. The clip-job budget still applies: each chunk checks
the cap, and a watchdog closes a stalled socket once the cap is already spent.
Connection probes stay non-stream; that path is owned by provider validation.
"""
from __future__ import annotations

import contextvars
import json
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from backend.core.failure_logging import failure_logger

logger = failure_logger(__name__)

_REJECT_STATUS = frozenset({400, 404, 405, 406, 415, 422, 501})
_REJECT_PHRASES = (
    "not support",
    "unsupported",
    "does not support",
    "doesn't support",
    "do not support",
    "is not supported",
    "isn't supported",
    "not supported",
    "unrecognized",
    "unknown parameter",
    "unknown field",
    "unexpected",
    "must be false",
    "cannot be true",
    "not allowed",
    "不支持",
    "未支持",
    "不能使用流式",
    "无法流式",
)
_REQUIRED_PHRASES = (
    "must be true",
    "stream is required",
    "requires stream",
    "需要流式",
    "必须开启流式",
    "必须为 true",
    "must be enabled",
)


class StreamError(RuntimeError):
    """A provider error frame inside an otherwise open stream."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body if body is not None else message


class StreamRejected(Exception):
    """The host refused ``stream: true`` before any answer text arrived."""

    def __init__(self, error: BaseException) -> None:
        super().__init__("stream rejected")
        self.error = error
        self.status_code = _status_of(error)
        self.body = getattr(error, "body", None)


class CollectedChat:
    def __init__(self, content: str | None, usage: dict | None, finish_reason: str | None, model: str | None = None) -> None:
        self.content = content
        self.usage = usage
        self.finish_reason = finish_reason
        self.model = model

    def as_completion(self) -> dict[str, Any]:
        choice: dict[str, Any] = {
            "index": 0,
            "message": {"role": "assistant", "content": self.content},
            "finish_reason": self.finish_reason,
        }
        out: dict[str, Any] = {"choices": [choice]}
        if self.usage is not None:
            out["usage"] = self.usage
        if self.model:
            out["model"] = self.model
        return out


def stream_rejected(status: int | None, body: Any) -> bool:
    """True when this error is about the stream flag, not another 400."""
    if status not in _REJECT_STATUS:
        return False
    text = _flatten(body).lower()
    if "stream" not in text and "text/event-stream" not in text:
        return False
    if any(phrase in text for phrase in _REQUIRED_PHRASES):
        return False
    return any(phrase in text for phrase in _REJECT_PHRASES)


def exception_rejects_stream(error: BaseException) -> bool:
    status = _status_of(error)
    body = getattr(error, "body", None)
    if body is None:
        body = str(error)
    if status is not None:
        return stream_rejected(status, body)
    text = _flatten(body).lower()
    if "stream" not in text:
        return False
    if any(phrase in text for phrase in _REQUIRED_PHRASES):
        return False
    return any(phrase in text for phrase in (
        "not support", "unsupported", "not supported", "does not support",
        "unrecognized", "unknown parameter", "不支持",
    ))


def merge_text(current: str, piece: str) -> str:
    """Append a delta. A strictly longer prefix replaces it (cumulative hosts)."""
    if not piece:
        return current
    if current and piece.startswith(current) and len(piece) > len(current):
        return piece
    return current + piece


def text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                part = item.get("text")
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
            else:
                part = getattr(item, "text", None)
                if isinstance(part, str):
                    parts.append(part)
        return "".join(parts)
    return ""


def collect_sse(lines: Any) -> CollectedChat:
    """Assemble one chat completion from SSE lines. A single JSON body also works."""
    if isinstance(lines, (str, bytes)):
        text = lines.decode("utf-8", "replace") if isinstance(lines, bytes) else lines
        stripped = text.lstrip()
        if stripped.startswith("{") and not stripped.startswith("data:"):
            return from_chat_json(json.loads(stripped))
        lines = text.splitlines()
    content = ""
    usage = None
    finish = None
    model = None
    saw_reasoning = False
    buffer: list[str] = []
    state = {"guard": 0.0, "kind": "", "note_at": 0.0, "note_chars": -1}

    def emit(parts: list[str]) -> bool:
        nonlocal content, usage, finish, model, saw_reasoning
        payload = "\n".join(parts).strip()
        if not payload:
            return False
        if payload == "[DONE]":
            return True
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid stream event") from exc
        if not isinstance(data, dict):
            raise ValueError("invalid stream event")
        if data.get("error"):
            err = data["error"]
            status = _status_of_error_object(err)
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise StreamError(str(message or err), status_code=status, body=data)
        if isinstance(data.get("model"), str):
            model = data["model"]
        mapped = _usage(data.get("usage"))
        if mapped:
            usage = mapped
        for choice in data.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            index = choice.get("index")
            if index not in (None, 0):
                continue
            piece, reasoning, reason = _choice_text(choice)
            if reason:
                finish = reason
            if reasoning:
                saw_reasoning = True
            if piece:
                content = merge_text(content, piece)
        _note(state, chars=len(content), thinking=saw_reasoning and not content)
        return False

    for raw in lines:
        _guard(state)
        line = _decode_line(raw)
        if line is None:
            continue
        if line == "":
            if buffer and emit(buffer):
                break
            buffer = []
            continue
        if line.startswith(":"):
            if buffer and _flushable(buffer) and emit(buffer):
                break
            if buffer and _flushable(buffer):
                buffer = []
            _note(state, chars=len(content), thinking=not content)
            continue
        if line.startswith("data:"):
            value = line[5:]
            if value.startswith(" "):
                value = value[1:]
            if buffer and _flushable(buffer):
                if emit(buffer):
                    break
                buffer = []
            buffer.append(value)
            continue
        # event:, id:, retry: are ignored
    else:
        if buffer:
            emit(buffer)
    return CollectedChat(content, usage, finish, model)


def collect_sdk(response: Any) -> CollectedChat:
    """Read an SDK stream, or the completion object a host returned instead.

    Some hosts answer ``stream: true`` with one JSON document and
    ``application/json``. The SDK still hands back a stream handle; read that
    body as a normal completion instead of an empty event stream.
    """
    if not is_chunk_stream(response):
        return from_sdk_completion(response)
    if _is_json_http_body(response):
        with budget_watch(response):
            try:
                raw = response.response
                # The SDK leaves a streaming httpx response unread. json() needs the body.
                read = getattr(raw, "read", None)
                if callable(read):
                    read()
                data = raw.json()
            finally:
                _close(response)
        if not isinstance(data, dict):
            raise ValueError("completion was not an object")
        if data.get("error") and not data.get("choices"):
            err = data["error"]
            status = _status_of_error_object(err)
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise StreamError(str(message or err), status_code=status, body=data)
        return from_chat_json(data)
    with budget_watch(response):
        try:
            return _consume_chunks(response)
        finally:
            _close(response)


def from_chat_json(data: Any) -> CollectedChat:
    """One non-stream chat body. Missing choices raise, as the old indexing did."""
    if not isinstance(data, dict):
        raise ValueError("completion was not an object")
    choice = data["choices"][0]
    message = choice["message"]
    content = message["content"]
    if isinstance(content, list):
        content = text_of(content)
    usage = data.get("usage")
    if usage is not None and not isinstance(usage, dict):
        usage = _usage(usage)
    finish = choice.get("finish_reason") if isinstance(choice, dict) else None
    model = data.get("model") if isinstance(data.get("model"), str) else None
    return CollectedChat(content, usage if isinstance(usage, dict) else None, finish, model)


def from_sdk_completion(response: Any) -> CollectedChat:
    if isinstance(response, dict):
        return from_chat_json(response)
    choices = getattr(response, "choices", None) or []
    if not choices:
        try:
            text = getattr(response, "text", None)
        except Exception:  # noqa: BLE001 - Gemini raises when a chunk has no text part
            text = None
        if text is not None:
            return CollectedChat(text if isinstance(text, str) else text_of(text), None, getattr(response, "finish_reason", None))
        raise IndexError("choices")
    choice = choices[0]
    message = getattr(choice, "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if isinstance(content, list):
        content = text_of(content)
    return CollectedChat(
        content,
        _sdk_usage(getattr(response, "usage", None)),
        getattr(choice, "finish_reason", None),
        getattr(response, "model", None) if isinstance(getattr(response, "model", None), str) else None,
    )


def is_chunk_stream(response: Any) -> bool:
    if response is None or isinstance(response, (str, bytes, dict, list, tuple)):
        return False
    if getattr(response, "__stream__", None) is not None and hasattr(response, "__iter__"):
        return True
    if hasattr(response, "read") and hasattr(response, "readline") and not hasattr(response, "choices"):
        return False
    if hasattr(response, "status_code") and hasattr(response, "output") and not hasattr(response, "__next__"):
        return False
    if hasattr(response, "choices") and not hasattr(response, "__next__"):
        return False
    return hasattr(response, "__iter__") and hasattr(response, "__next__")


def read_completion_response(response: Any) -> dict[str, Any]:
    """HTTP body → the chat JSON vision already understands.

    ``text/event-stream`` is assembled. Anything else, including a 2xx JSON
    body and the header-less doubles tests use, is parsed as one document.
    """
    with budget_watch(response):
        ctype = _content_type(response)
        if "text/event-stream" in ctype:
            return collect_sse(_lines(response)).as_completion()
        raw = _read_bounded(response)
        if isinstance(raw, str):
            text = raw
        else:
            text = raw.decode("utf-8-sig", "replace")
        stripped = text.lstrip()
        if stripped.startswith("data:") or stripped.startswith("event:") or stripped.startswith(":"):
            return collect_sse(text.splitlines()).as_completion()
        if not stripped:
            raise ValueError("empty completion")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("completion was not an object")
        return data


def post_chat_completion(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: Any,
    refresh_timeout,
    post=None,
) -> CollectedChat:
    """POST ``stream: true``. One fallback to ``stream: false`` when the host refuses it."""
    import requests

    send = post or requests.post
    body = dict(payload)
    body["stream"] = True
    response = send(url, headers=headers, json=body, timeout=timeout, stream=True)
    rejected: BaseException | None = None
    try:
        with budget_watch(response):
            status = getattr(response, "status_code", 200)
            if status >= 400:
                err = _error_body(response)
                if body.get("stream") is True and stream_rejected(status, err):
                    rejected = _http_error(status, err)
                else:
                    raise _http_error(status, err)
            else:
                return _collect_requests(response)
    finally:
        _close(response)
    if rejected is None:
        raise RuntimeError("chat completion produced no response")
    from backend.core.llm_degrade import consume_chunk_call
    if not consume_chunk_call():
        raise rejected
    logger.info("上游不接受 stream，改回整包响应再试一次")
    fallback = dict(body)
    fallback["stream"] = False
    again = send(url, headers=headers, json=fallback, timeout=refresh_timeout(), stream=False)
    try:
        status = getattr(again, "status_code", 200)
        if status >= 400:
            raise _http_error(status, _error_body(again))
        return _collect_requests(again)
    finally:
        _close(again)


def create_openai_chat(client: Any, payload: dict[str, Any], timeout: Any, refresh_timeout) -> Any:
    """SDK create. A stream rejection retries once as a single JSON completion."""
    def once(body: dict[str, Any], limit: Any) -> Any:
        call = {} if limit is None else {"timeout": limit}
        return client.chat.completions.create(**body, **call)

    try:
        return once(payload, timeout)
    except Exception as error:  # noqa: BLE001 - only a stream refusal is retried here
        if payload.get("stream") is not True or not exception_rejects_stream(error):
            raise
        from backend.core.llm_degrade import consume_chunk_call
        if not consume_chunk_call():
            raise
        logger.info("上游不接受 stream，改回整包响应再试一次")
        fallback = dict(payload)
        fallback["stream"] = False
        return once(fallback, refresh_timeout())


@contextmanager
def budget_watch(response: Any) -> Iterator[None]:
    """Close a stalled stream once this clip job has spent its wall-clock cap."""
    from backend.core.job_budget import budget_expired, clip_job_active
    if response is None or not clip_job_active():
        yield
        return
    # A new thread starts with an empty context. Keep this job's budget visible.
    ctx = contextvars.copy_context()
    stop = threading.Event()

    def run() -> None:
        while not stop.is_set():
            if ctx.run(budget_expired):
                _close(response)
                return
            if stop.wait(0.25):
                return

    thread = threading.Thread(target=run, name="autoclip-llm-budget", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=1.0)


def _consume_chunks(response: Any) -> CollectedChat:
    content = ""
    usage = None
    finish = None
    model = None
    saw_reasoning = False
    started = False
    state = {"guard": 0.0, "kind": "", "note_at": 0.0, "note_chars": -1}
    try:
        for chunk in response:
            _guard(state)
            started = True
            if isinstance(getattr(chunk, "model", None), str):
                model = chunk.model
            mapped = _usage(getattr(chunk, "usage", None))
            if mapped:
                usage = mapped
            status = getattr(chunk, "status_code", None)
            if isinstance(status, int) and status != 200:
                code = getattr(chunk, "code", None)
                message = getattr(chunk, "message", None) or "stream error"
                raise StreamError(str(message), status_code=status, body={"code": code, "message": message})
            output = getattr(chunk, "output", None)
            choices = getattr(chunk, "choices", None)
            if choices:
                for choice in choices:
                    index = getattr(choice, "index", None)
                    if index not in (None, 0):
                        continue
                    piece, reasoning, reason = _choice_text(choice)
                    if reason:
                        finish = reason
                    if reasoning:
                        saw_reasoning = True
                    if piece:
                        content = merge_text(content, piece)
            elif output is not None:
                piece = _output_text(output)
                reason = _output_finish(output)
                if reason:
                    finish = reason
                if piece:
                    content = merge_text(content, piece)
                mapped = _usage(getattr(chunk, "usage", None))
                if mapped:
                    usage = mapped
            else:
                piece = _gemini_text(chunk)
                if piece:
                    content = merge_text(content, piece)
                reason = getattr(chunk, "finish_reason", None)
                if reason:
                    finish = reason
            _note(state, chars=len(content), thinking=saw_reasoning and not content)
    except StreamError:
        raise
    except Exception as error:  # noqa: BLE001 - a refusal before any chunk can fall back
        if not started and exception_rejects_stream(error):
            raise StreamRejected(error) from error
        raise
    return CollectedChat(content, usage, finish, model)


def _collect_requests(response: Any) -> CollectedChat:
    ctype = _content_type(response)
    if "text/event-stream" in ctype:
        lines = response.iter_lines(decode_unicode=True) if hasattr(response, "iter_lines") else _lines(response)
        return collect_sse(lines)
    if hasattr(response, "json"):
        try:
            data = response.json()
        except Exception:  # noqa: BLE001 - a mislabeled SSE body is not JSON
            data = None
        if isinstance(data, dict):
            if data.get("error") and not data.get("choices"):
                raise StreamError(str(data.get("error")), body=data)
            return from_chat_json(data)
    text = getattr(response, "text", None)
    if text is None and hasattr(response, "content"):
        raw = response.content
        text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
    stripped = (text or "").lstrip()
    if stripped.startswith("data:") or stripped.startswith(":"):
        return collect_sse(stripped.splitlines())
    if stripped.startswith("{"):
        return from_chat_json(json.loads(stripped))
    raise ValueError("invalid completion")


def _choice_text(choice: Any) -> tuple[str, str, Any]:
    delta = _field(choice, "delta") or {}
    message = _field(choice, "message") or {}
    content = text_of(_field(delta, "content"))
    if not content:
        content = text_of(_field(message, "content"))
    reasoning = text_of(_field(delta, "reasoning_content")) or text_of(_field(delta, "reasoning"))
    if not reasoning:
        reasoning = text_of(_field(message, "reasoning_content")) or text_of(_field(message, "reasoning"))
    return content, reasoning, _field(choice, "finish_reason")


def _output_text(output: Any) -> str:
    if isinstance(output, dict):
        text = output.get("text")
        if isinstance(text, str):
            return text
        return text_of(text)
    text = getattr(output, "text", None)
    return text if isinstance(text, str) else ""


def _output_finish(output: Any) -> Any:
    if isinstance(output, dict):
        return output.get("finish_reason")
    return getattr(output, "finish_reason", None)


def _field(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _gemini_text(chunk: Any) -> str:
    try:
        value = getattr(chunk, "text", None)
    except Exception:  # noqa: BLE001 - empty Gemini chunks raise on .text
        return ""
    return value if isinstance(value, str) else ""


def _usage(raw: Any) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        data = {key: value for key, value in raw.items() if value is not None}
        return data or None
    data: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"):
        value = getattr(raw, key, None)
        if value is not None:
            data[key] = value
    if not data and hasattr(raw, "model_dump"):
        try:
            dumped = raw.model_dump()
        except Exception:  # noqa: BLE001
            dumped = None
        if isinstance(dumped, dict):
            data = {key: value for key, value in dumped.items() if value is not None}
    return data or None


def _sdk_usage(raw: Any) -> dict | None:
    usage = _usage(raw)
    if not usage:
        return None
    if any(key in usage for key in ("prompt_tokens", "completion_tokens", "total_tokens")):
        return {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
    return usage


def _guard(state: dict[str, Any]) -> None:
    from backend.core.project_cancellation import checkpoint
    checkpoint()
    state["guard"] = state.get("guard", 0.0)


def _note(state: dict[str, Any], *, chars: int, thinking: bool) -> None:
    import time
    kind = "content" if chars > 0 else "thinking" if thinking else ""
    if not kind:
        return
    message = "模型思考中" if chars <= 0 else f"模型持续返回中（已接收 {chars} 字）"
    now = time.monotonic()
    if kind == state.get("kind") and now - float(state.get("note_at") or 0) < 2 and abs(chars - int(state.get("note_chars") or -1)) < 32:
        return
    state["kind"] = kind
    state["note_at"] = now
    state["note_chars"] = chars
    try:
        from backend.core.project_cancellation import current
        from backend.services.simple_progress import note_activity
        project_id = current()
        if project_id:
            note_activity(project_id, message)
    except Exception:  # noqa: BLE001 - a progress write must not fail the completion
        logger.debug("流式进度未写入", exc_info=True)


def _lines(response: Any):
    readline = getattr(response, "readline", None)
    if not callable(readline):
        raw = _read_bounded(response)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        yield from text.splitlines()
        return
    while True:
        line = readline()
        if not line:
            break
        yield line


def _read_bounded(response: Any) -> bytes:
    read = getattr(response, "read", None)
    if not callable(read):
        return b""
    parts: list[bytes] = []
    while True:
        from backend.core.project_cancellation import checkpoint
        checkpoint()
        chunk = read(8192)
        if not chunk:
            break
        if isinstance(chunk, str):
            chunk = chunk.encode()
        parts.append(chunk)
    return b"".join(parts)


def _is_json_http_body(response: Any) -> bool:
    raw = getattr(response, "response", None)
    if raw is None or raw is response or not callable(getattr(raw, "json", None)):
        return False
    ctype = _content_type(raw)
    return bool(ctype) and "text/event-stream" not in ctype and "json" in ctype


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return ""
    value = headers.get("Content-Type") or headers.get("content-type") or ""
    return str(value).lower()


def _decode_line(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        line = raw.decode("utf-8", "replace")
    else:
        line = str(raw)
    return line.rstrip("\r\n")


def _flushable(buffer: list[str]) -> bool:
    if len(buffer) != 1:
        return False
    text = buffer[0].strip()
    if text == "[DONE]":
        return True
    if not text or not text.startswith("{"):
        return False
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


def _error_body(response: Any) -> Any:
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        text = getattr(response, "text", None)
        if text is None:
            return ""
        return {"message": text}


def _http_error(status: int, body: Any) -> RuntimeError:
    error = RuntimeError(str(body))
    error.status_code = status  # type: ignore[attr-defined]
    error.body = body  # type: ignore[attr-defined]
    return error


def _close(obj: Any) -> None:
    close = getattr(obj, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:  # noqa: BLE001
        return


def _flatten(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body.decode("utf-8", "replace")
    if isinstance(body, str):
        return body
    try:
        return json.dumps(body, ensure_ascii=False)
    except TypeError:
        return str(body)


def _coerce_status(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    if isinstance(value, str) and value.isdigit():
        number = int(value)
        if 100 <= number <= 599:
            return number
    return None


def _status_of(error: BaseException) -> int | None:
    for attr in ("status_code", "status", "http_status"):
        found = _coerce_status(getattr(error, attr, None))
        if found is not None:
            return found
    code = getattr(error, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        found = _coerce_status(code)
        if found is not None:
            return found
    response = getattr(error, "response", None)
    if response is not None:
        return _coerce_status(getattr(response, "status_code", None))
    return None


def _status_of_error_object(err: Any) -> int | None:
    if not isinstance(err, dict):
        return None
    return _coerce_status(err.get("code")) or _coerce_status(err.get("status"))
