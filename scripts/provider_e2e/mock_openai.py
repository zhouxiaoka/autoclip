"""Local OpenAI-compatible server with one-shot fault injection."""
from __future__ import annotations

import json
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from backend.core.upstream_errors import ClassifiedUpstreamError, classify_upstream_error

# Bodies match docs/SUCCESS_RATE_CONTRACT.md / upstream_errors examples so
# classify_upstream_error() returns the injected UpstreamErrorType.
FAULT_BODIES: dict[str, dict[str, Any]] = {
    '429': {
        'error': {
            'message': 'Rate limit reached',
            'type': 'rate_limit_error',
            'code': 'rate_limit_exceeded',
        },
    },
    '503': {
        'error': {
            'message': 'Server is overloaded',
            'type': 'server_error',
        },
    },
}


def classify_injected_fault(fault: str) -> ClassifiedUpstreamError | None:
    """Map a mock fault id to the contract UpstreamErrorType."""
    if fault == '429':
        return classify_upstream_error(429, FAULT_BODIES['429'])
    if fault == '503':
        return classify_upstream_error(503, FAULT_BODIES['503'])
    if fault == 'disconnect':
        return classify_upstream_error(None, 'Connection error.', error_name='APIConnectionError')
    return None


def classify(text: str) -> str:
    if 'final_score' in text or 'recommend_reason' in text:
        return 'scores'
    if 'title_hint' in text or '为 platforms' in text:
        return 'posts'
    if 'start_time' in text and 'end_time' in text:
        return 'timeline'
    if '标题党' in text or '最佳标题' in text:
        return 'titles'
    return 'outline'


def _ids_from(text: str) -> list[str]:
    try:
        marker = '输入内容：'
        raw = text.split(marker, 1)[1] if marker in text else text
        start = raw.find('[')
        end = raw.rfind(']')
        if start < 0 or end <= start:
            return ['1']
        data = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return ['1']
    if not isinstance(data, list):
        return ['1']
    ids = [str(item.get('id')) for item in data if isinstance(item, dict) and item.get('id') is not None]
    return ids or ['1']


def _titles_from(text: str) -> list[str]:
    try:
        marker = '输入内容：'
        raw = text.split(marker, 1)[1] if marker in text else text
        start = raw.find('[')
        end = raw.rfind(']')
        data = json.loads(raw[start:end + 1]) if start >= 0 and end > start else []
    except (ValueError, TypeError):
        data = []
    titles = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            title = item.get('outline') or item.get('title')
            if isinstance(title, str) and title.strip():
                titles.append(title.strip())
    return titles or ['测试话题']


def completion_body(text: str) -> str:
    kind = classify(text)
    if kind == 'outline':
        return json.dumps([
            {'title': '测试话题：完整观点', 'subtopics': ['引入主题', '核心结论']},
        ], ensure_ascii=False)
    if kind == 'timeline':
        title = _titles_from(text)[0]
        return json.dumps([
            {'outline': title, 'start_time': '00:00:00,000', 'end_time': '00:00:20,000'},
        ], ensure_ascii=False)
    if kind == 'scores':
        return json.dumps([
            {'id': clip_id, 'outline': '测试话题：完整观点', 'final_score': 0.92,
             'recommend_reason': '结构完整，适合切成一条成片。'}
            for clip_id in _ids_from(text)
        ], ensure_ascii=False)
    if kind == 'titles':
        return json.dumps({clip_id: f'测试成片标题 {clip_id}' for clip_id in _ids_from(text)}, ensure_ascii=False)
    return json.dumps({
        'posts': {
            'original': {
                'title': '测试成片标题',
                'description': '本地 mock 生成的发布文案。',
                'tags': ['测试', '回归', '出片'],
            }
        }
    }, ensure_ascii=False)


def chat_payload(content: str, model: str) -> dict[str, Any]:
    return {
        'id': 'chatcmpl-mock-e2e',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model,
        'choices': [{
            'index': 0,
            'message': {'role': 'assistant', 'content': content},
            'finish_reason': 'stop',
        }],
        'usage': {'prompt_tokens': 12, 'completion_tokens': 24, 'total_tokens': 36},
    }


class MockState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.fault_hits: dict[str, int] = {}
        self.events: list[dict[str, Any]] = []
        self.slow_seconds = 45.0

    def hit(self, fault: str) -> int:
        with self.lock:
            count = self.fault_hits.get(fault, 0) + 1
            self.fault_hits[fault] = count
            return count

    def record(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.append(event)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {'fault_hits': dict(self.fault_hits), 'events': list(self.events)}


def _fault_from(path: str) -> str | None:
    if path.startswith('/fault/429/'):
        return '429'
    if path.startswith('/fault/503/'):
        return '503'
    if path.startswith('/fault/disconnect/'):
        return 'disconnect'
    if path.startswith('/fault/slow/'):
        return 'slow'
    return None


def _is_chat(path: str) -> bool:
    return path.rstrip('/').endswith('/chat/completions')


def _is_models(path: str) -> bool:
    return path.rstrip('/').endswith('/models')


class MockHandler(BaseHTTPRequestHandler):
    server: 'MockServer'

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if _is_models(path):
            self._json(200, {
                'object': 'list',
                'data': [{'id': 'mock-gpt', 'object': 'model', 'owned_by': 'autoclip-e2e'}],
            })
            return
        self._json(404, {'error': {'message': 'not found', 'type': 'invalid_request_error'}})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(length) if length else b''
        try:
            payload = json.loads(raw.decode('utf-8') or '{}')
        except ValueError:
            payload = {}
        messages = payload.get('messages') if isinstance(payload, dict) else None
        text = ''
        if isinstance(messages, list):
            text = '\n'.join(str((item or {}).get('content') or '') for item in messages if isinstance(item, dict))
        fault = _fault_from(path)
        event = {
            'path': path,
            'fault': fault,
            'kind': classify(text) if text else None,
            'bytes': length,
            'upstream_error_type': None,
        }
        if not _is_chat(path):
            self.server.state.record(event)
            self._json(404, {'error': {'message': 'not found', 'type': 'invalid_request_error'}})
            return
        if fault == '429' and self.server.state.hit('429') == 1:
            classified = classify_injected_fault('429')
            event['upstream_error_type'] = classified.error_type.value if classified else None
            event['http_status'] = 429
            self.server.state.record(event)
            self._json(429, FAULT_BODIES['429'], extra={'Retry-After': '1'})
            return
        if fault == '503' and self.server.state.hit('503') == 1:
            classified = classify_injected_fault('503')
            event['upstream_error_type'] = classified.error_type.value if classified else None
            event['http_status'] = 503
            self.server.state.record(event)
            self._json(503, FAULT_BODIES['503'])
            return
        if fault == 'disconnect' and self.server.state.hit('disconnect') == 1:
            classified = classify_injected_fault('disconnect')
            event['upstream_error_type'] = classified.error_type.value if classified else None
            self.server.state.record(event)
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return
        if fault == 'slow':
            self.server.state.hit('slow')
            # Stop as soon as the client goes away (backend killed / client timeout) instead of
            # sleeping blind and then writing into a closed socket (BrokenPipe traceback, #59).
            if not self._wait_or_disconnect(self.server.state.slow_seconds):
                event['client_disconnected'] = True
                self.server.state.record(event)
                self.close_connection = True
                return
        self.server.state.record(event)
        model = str((payload or {}).get('model') or 'mock-gpt')
        self._json(200, chat_payload(completion_body(text), model))

    def _client_gone(self) -> bool:
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            return bool(readable) and self.connection.recv(1, socket.MSG_PEEK) == b''
        except (OSError, ValueError):
            return True

    def _wait_or_disconnect(self, seconds: float) -> bool:
        """Sleep up to ``seconds``; False as soon as the peer has closed the connection."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self._client_gone():
                return False
            time.sleep(min(0.2, max(0.0, deadline - time.monotonic())))
        return not self._client_gone()

    def _json(self, status: int, payload: dict[str, Any], extra: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode('utf-8')
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The client already disconnected; nothing to deliver. Count it, never traceback.
            self.server.state.record({'path': self.path, 'client_disconnected': True, 'status': status})
            self.close_connection = True


class MockServer(ThreadingHTTPServer):
    def __init__(self, host: str = '127.0.0.1', port: int = 0) -> None:
        super().__init__((host, port), MockHandler)
        self.state = MockState()


def start(host: str = '127.0.0.1', port: int = 0) -> tuple[MockServer, str]:
    server = MockServer(host, port)
    thread = threading.Thread(target=server.serve_forever, name='provider-e2e-mock', daemon=True)
    thread.start()
    server.thread = thread  # type: ignore[attr-defined]
    bound = f'http://{server.server_address[0]}:{server.server_address[1]}'
    return server, bound


def stop(server: MockServer) -> None:
    server.shutdown()
    server.server_close()


def base_url(root: str, fault: str | None = None) -> str:
    if not fault or fault == 'kill':
        return root.rstrip('/') + '/v1'
    return f'{root.rstrip("/")}/fault/{fault}/v1'
