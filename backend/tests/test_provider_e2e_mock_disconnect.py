"""the mock provider must stop on client disconnect instead of writing into a closed
socket (BrokenPipe traceback in mock-e2e logs)."""
import http.client
import io
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from provider_e2e import mock_openai  # noqa: E402


def _post_and_drop(port, path, wait):
    sock = socket.create_connection(('127.0.0.1', port))
    body = b'{"model":"mock-gpt","messages":[{"role":"user","content":"hi"}]}'
    sock.sendall(b'POST ' + path.encode() + b' HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n'
                 b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
    time.sleep(wait)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')  # RST on close
    sock.close()


def test_slow_fault_stops_when_client_disconnects(monkeypatch):
    errors = io.StringIO()
    monkeypatch.setattr(sys, 'stderr', errors)
    server, root = mock_openai.start()
    try:
        server.state.slow_seconds = 3.0
        port = server.server_address[1]
        started = time.monotonic()
        _post_and_drop(port, '/fault/slow/v1/chat/completions', 0.3)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not server.state.snapshot()['events']:
            time.sleep(0.05)
        events = server.state.snapshot()['events']
        assert events and events[-1].get('client_disconnected') is True, events
        assert time.monotonic() - started < 2.5, 'handler must stop early, not sleep the full slow delay'
        # A normal request still works afterwards.
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/v1/models')
        assert conn.getresponse().status == 200
    finally:
        mock_openai.stop(server)
    assert 'BrokenPipe' not in errors.getvalue() and 'Traceback' not in errors.getvalue(), errors.getvalue()


def test_write_after_disconnect_is_recorded_not_raised(monkeypatch):
    errors = io.StringIO()
    monkeypatch.setattr(sys, 'stderr', errors)
    server, root = mock_openai.start()
    try:
        handler_cls = mock_openai.MockHandler
        real = handler_cls.end_headers

        def broken(self):
            real(self)
            raise BrokenPipeError(32, 'Broken pipe')

        monkeypatch.setattr(handler_cls, 'end_headers', broken)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
        try:
            conn.request('GET', '/v1/models')
            conn.getresponse().read()
        except (http.client.HTTPException, OSError):
            pass
        time.sleep(0.2)
        assert any(e.get('client_disconnected') for e in server.state.snapshot()['events'])
    finally:
        mock_openai.stop(server)
    assert 'Traceback' not in errors.getvalue(), errors.getvalue()
