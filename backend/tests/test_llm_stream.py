"""Stream assembly, a clean fallback, and the clip-job budget during a live read."""
import io
import json
import threading
import urllib.error
from types import SimpleNamespace

import pytest

from backend.core.job_budget import JobDurationExceeded, bound_clip_job
from backend.core.llm_stream import (
    StreamError,
    budget_watch,
    collect_sse,
    stream_rejected,
)


def _event(content, **extra):
    choice = {"delta": {"content": content}}
    choice.update(extra)
    return "data: " + json.dumps({"choices": [choice]}) + "\n"


def test_sse_assembles_deltas_and_leaves_reasoning_out():
    body = "\n".join([
        ": keep-alive",
        "",
        "data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "先想清楚"}}]}),
        "",
        _event("你").rstrip("\n"),
        "",
        _event("好", finish_reason="stop").rstrip("\n"),
        "",
        "data: " + json.dumps({
            "choices": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
            "model": "slow-thinker",
        }),
        "",
        "data: [DONE]",
        "",
    ])
    got = collect_sse(body)
    assert got.content == "你好"
    assert "先想" not in got.content
    assert got.finish_reason == "stop"
    assert got.usage["total_tokens"] == 4
    assert got.model == "slow-thinker"


def test_repeated_delta_is_kept_and_a_longer_prefix_replaces():
    repeated = _event("哈") + "\n" + _event("哈") + "\n"
    assert collect_sse(repeated).content == "哈哈"
    cumulative = _event("哈") + "\n" + _event("哈哈") + "\n"
    assert collect_sse(cumulative).content == "哈哈"


def test_a_single_json_body_is_the_non_stream_fallback():
    got = collect_sse('{"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":1}}')
    assert got.content == "ok"
    assert got.finish_reason == "stop"
    assert got.usage == {"prompt_tokens": 1}


def test_a_broken_event_and_an_error_frame():
    with pytest.raises(ValueError):
        collect_sse("data: {not-json}\n\n")
    with pytest.raises(StreamError) as caught:
        collect_sse('data: {"error":{"message":"overloaded","code":503}}\n\n')
    assert caught.value.status_code == 503
    assert caught.value.body["error"]["message"] == "overloaded"


@pytest.mark.parametrize("status,body,expected", [
    (400, {"error": {"message": "stream is not supported for this model"}}, True),
    (422, {"error": {"message": "unknown parameter: stream"}}, True),
    (400, {"error": {"message": "stream must be true"}}, False),
    (400, {"error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens' instead."}}, False),
    (401, {"error": {"message": "stream is not supported"}}, False),
    (500, {"error": {"message": "stream is not supported"}}, False),
])
def test_stream_rejection_is_only_that_parameter(status, body, expected):
    assert stream_rejected(status, body) is expected


def test_a_flowing_stream_still_stops_when_the_job_budget_is_spent(monkeypatch):
    import backend.core.job_budget as budget
    clock = {"t": 0.0}
    monkeypatch.setattr(budget.time, "monotonic", lambda: clock["t"])

    def lines():
        yield _event("a")
        clock["t"] = 30
        yield _event("b")
        yield "data: [DONE]\n"

    with bound_clip_job(10):
        with pytest.raises(JobDurationExceeded):
            collect_sse(lines())


def test_budget_watch_closes_the_socket_once_the_cap_is_spent():
    closed = threading.Event()

    class Resp:
        def close(self):
            closed.set()

    with bound_clip_job(0):
        with budget_watch(Resp()):
            assert closed.wait(1)


def test_budget_watch_does_nothing_outside_a_job():
    closed = threading.Event()

    class Resp:
        def close(self):
            closed.set()

    with budget_watch(Resp()):
        pass
    assert closed.is_set() is False


def test_stream_notes_existing_progress_without_moving_the_bar(monkeypatch):
    from backend.core.project_cancellation import bind
    from backend.services import simple_progress as progress

    class Store:
        def __init__(self):
            self.row = {
                "project_id": "stream-progress",
                "stage": "ANALYZE",
                "percent": 45,
                "message": "正在通读全文挑选片段",
                "ts": 1,
            }
            self.saved = []

        def get(self, project_id):
            return dict(self.row) if project_id == self.row["project_id"] else None

        def save(self, project_id, stage, percent, message, ts):
            self.saved.append((stage, percent, message))
            self.row = {"project_id": project_id, "stage": stage, "percent": percent, "message": message, "ts": ts}

    store = Store()
    monkeypatch.setattr(progress, "store", store)
    monkeypatch.setattr(progress, "_listeners", [])
    body = _event("想" * 40) + "\n" + _event("好") + "\n"
    with bind("stream-progress"):
        assert collect_sse(body).content.startswith("想")
    assert store.saved
    assert {item[0] for item in store.saved} == {"ANALYZE"}
    assert {item[1] for item in store.saved} == {45}
    assert "已接收" in store.row["message"]
    assert "失败" not in store.row["message"]
    assert "错误" not in store.row["message"]


def test_a_failed_snapshot_and_a_call_without_a_project_are_left_alone(monkeypatch):
    from backend.services import simple_progress as progress

    class Store:
        def __init__(self):
            self.row = {"project_id": "p", "stage": "ANALYZE", "percent": 10, "message": "处理失败：超时", "ts": 1}

        def get(self, project_id):
            return dict(self.row)

        def save(self, *args):
            raise AssertionError("failed progress must stay")

    monkeypatch.setattr(progress, "store", Store())
    collect_sse(_event("ok") + "\n")
    from backend.core.project_cancellation import bind
    with bind("p"):
        assert collect_sse(_event("ok") + "\n").content == "ok"


def test_openai_stream_chunks_keep_the_shortened_read_timeout(monkeypatch):
    import sys
    import types
    import httpx
    from backend.core import llm_providers as providers

    def chunks():
        yield SimpleNamespace(
            choices=[SimpleNamespace(index=0, delta=SimpleNamespace(content="你", reasoning_content="想"), finish_reason=None)],
            usage=None, model="m",
        )
        yield SimpleNamespace(
            choices=[SimpleNamespace(index=0, delta=SimpleNamespace(content="好", reasoning_content=None), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5), model="m",
        )

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return chunks()

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    module = types.ModuleType("openai")
    module.OpenAI = Client
    monkeypatch.setitem(sys.modules, "openai", module)
    provider = providers.OpenAIProvider("sk-test", "gpt-4o-mini", base_url="https://example.test/v1")
    with bound_clip_job(9):
        reply = provider.call("hi")
    assert reply.content == "你好"
    assert reply.usage["total_tokens"] == 5
    assert calls[0]["stream"] is True
    assert isinstance(calls[0]["timeout"], httpx.Timeout)
    assert calls[0]["timeout"].read <= 9


def test_sdk_stream_handle_with_a_json_body_is_one_completion():
    class Handle:
        def __iter__(self):
            return self

        def __next__(self):
            raise AssertionError("a JSON body is not an event stream")

        def close(self):
            self.closed = True

        response = SimpleNamespace(
            headers={"Content-Type": "application/json; charset=utf-8"},
            json=lambda: {
                "choices": [{"message": {"content": "整包"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    from backend.core.llm_stream import collect_sdk
    handle = Handle()
    got = collect_sdk(handle)
    assert got.content == "整包"
    assert got.finish_reason == "stop"
    assert got.usage["total_tokens"] == 2
    assert handle.closed is True


def test_openai_reads_json_when_the_host_ignores_stream():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from backend.core.llm_providers import OpenAIProvider

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = json.dumps({
                "id": "chatcmpl-json",
                "object": "chat.completion",
                "created": 0,
                "model": "slow-thinker",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "整包仍在"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        reply = OpenAIProvider(
            "sk-test", "slow-thinker", base_url=f"http://127.0.0.1:{server.server_address[1]}/v1",
        ).call("想很久")
    finally:
        server.shutdown()
    assert reply.content == "整包仍在"
    assert reply.usage["total_tokens"] == 3


def test_openai_falls_back_when_the_host_rejects_stream(monkeypatch):
    import sys
    import types
    from backend.core import llm_providers as providers

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs.get("stream"))
            if kwargs.get("stream") is True:
                error = RuntimeError("stream is not supported for this model")
                error.status_code = 400
                error.body = {"error": {"message": "stream is not supported for this model"}}
                raise error
            message = SimpleNamespace(content="ok")
            choice = SimpleNamespace(message=message, finish_reason="stop")
            return SimpleNamespace(choices=[choice], usage=None)

    module = types.ModuleType("openai")
    module.OpenAI = lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setitem(sys.modules, "openai", module)
    reply = providers.OpenAIProvider("sk-test", "gpt-4o-mini", base_url="https://example.test/v1").call("hi")
    assert reply.content == "ok"
    assert calls == [True, False]


def test_dashscope_compatible_reads_sse_and_shrinks_the_timeout(monkeypatch):
    import requests
    from backend.core.llm_providers import DashScopeProvider

    sent = []

    class Resp:
        status_code = 200
        headers = {"Content-Type": "text/event-stream"}

        def iter_lines(self, decode_unicode=False):
            yield _event("片").rstrip("\n")
            yield ""
            yield "data: [DONE]"

        def close(self):
            return None

    def post(url, headers=None, json=None, timeout=None, **kwargs):
        sent.append((json, timeout))
        return Resp()

    monkeypatch.setattr(requests, "post", post)
    with bound_clip_job(8):
        reply = DashScopeProvider("sk-test", "qwen-plus", base_url="https://example.test/v1", mode="compatible").call("x")
    assert reply.content == "片"
    assert sent[0][0]["stream"] is True
    assert sent[0][1][1] <= 8


def test_http_fallback_retries_once_without_stream(monkeypatch):
    import requests
    from backend.core.llm_providers import SiliconFlowProvider

    sent = []

    def post(url, headers=None, json=None, timeout=None, **kwargs):
        sent.append(dict(json))
        if json.get("stream") is True:
            return SimpleNamespace(
                status_code=400,
                headers={},
                json=lambda: {"error": {"message": "stream is not supported"}},
                text="",
                close=lambda: None,
            )
        return SimpleNamespace(
            status_code=200,
            headers={"Content-Type": "application/json"},
            json=lambda: {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
            close=lambda: None,
        )

    monkeypatch.setattr(requests, "post", post)
    reply = SiliconFlowProvider("sk-test", "Qwen/Qwen2.5-7B-Instruct").call("x")
    assert reply.content == "ok"
    assert [item["stream"] for item in sent] == [True, False]


def test_vision_consumes_sse_and_falls_back_to_json(monkeypatch):
    from backend.services.studio import intelligence as vision

    first = json.dumps({"choices": [{"delta": {"content": '{"events": '}}]})
    second = json.dumps({"choices": [{"delta": {"content": "[]}"}, "finish_reason": "stop"}]})
    sse = f"data: {first}\n\ndata: {second}\n\ndata: [DONE]\n\n".encode()

    class Resp(io.BytesIO):
        def __init__(self, payload, content_type):
            super().__init__(payload)
            self.headers = {"Content-Type": content_type}

    calls = []
    mode = {"sse": True}

    def send(req, timeout=None):
        body = json.loads(req.data)
        calls.append(body)
        if body.get("stream") is True and mode["sse"]:
            mode["sse"] = False
            return Resp(sse, "text/event-stream")
        if body.get("stream") is True:
            raw = json.dumps({"error": {"message": "stream is not supported"}}).encode()
            raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(raw))
        return Resp(json.dumps({"choices": [{"message": {"content": '{"events": []}'}, "finish_reason": "stop"}]}).encode(), "application/json")

    monkeypatch.setattr(vision.urllib.request, "urlopen", send)
    config = {"base_url": "https://vision.example/v1", "model": "vision", "api_key": "k", "timeout": 10}
    assert vision.vision_call([], config=config) == {"events": []}
    assert calls[0]["stream"] is True

    calls.clear()
    assert vision.vision_call([], config=config) == {"events": []}
    assert [item["stream"] for item in calls] == [True, False]
