"""W157-F5: a rejected write must not reset the connection before the client reads the 403.

The guard used to answer 403 without reading the request body. uvicorn then closed the socket
with the body still unread (or arriving a moment later), the OS answered with a TCP RST, and the
client got ConnectionResetError / WinError 10053 instead of the 403. The Windows smoke script
crashed on that, and its `finally: proc.terminate()` is what killed the desktop app (exit 1).
"""
from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI

from backend.core.local_origin_guard import LocalOriginGuard


HTTP = "httptools"


def _serve():
    app = FastAPI()

    @app.put("/api/v1/settings/privacy")
    async def privacy(body: dict):
        return body

    app.add_middleware(LocalOriginGuard, origins=["http://tauri.localhost"], enforce_local_host=True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, http=HTTP))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.02)
    return server, thread, sock.getsockname()[1]


@pytest.fixture()
def port():
    server, thread, port = _serve()
    yield port
    server.should_exit = True
    thread.join(5)


def _put(port: int, origin: str, body_delay: float) -> bytes:
    body = b'{"crash_reports":false}'
    head = (
        f"PUT /api/v1/settings/privacy HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: {origin}\r\n"
        f"Content-Type: application/json\r\nConnection: close\r\nContent-Length: {len(body)}\r\n\r\n"
    ).encode()
    with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
        conn.sendall(head)  # urllib sends headers and body in two writes, like this
        time.sleep(body_delay)
        try:
            conn.sendall(body)
        except OSError:
            pass
        time.sleep(0.2)  # let the server close first, as on the QA VM
        data = b""
        while True:
            chunk = conn.recv(65536)  # ConnectionResetError here was the bug
            if not chunk:
                return data
            data += chunk
            if b"\r\n\r\n" in data and data.rstrip().endswith(b"}"):
                return data


@pytest.mark.parametrize("delay", [0.0, 0.05, 0.3])
def test_rejected_write_returns_403_without_reset(port, delay):
    for _ in range(5):
        response = _put(port, "https://evil.example", delay)
        assert response.startswith(b"HTTP/1.1 403"), response[:200]
        assert b"origin_not_allowed" in response


def test_allowed_origin_still_passes(port):
    assert _put(port, "http://tauri.localhost", 0.05).startswith(b"HTTP/1.1 200")


def test_rejection_waits_for_request_body(port):
    """Deterministic on every OS: the 403 must not be sent (and the socket closed) before the body arrives."""
    body = b'{"crash_reports":false}'
    head = (
        f"PUT /api/v1/settings/privacy HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: https://evil.example\r\n"
        f"Content-Type: application/json\r\nConnection: close\r\nContent-Length: {len(body)}\r\n\r\n"
    ).encode()
    with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
        conn.sendall(head)
        conn.settimeout(0.5)
        with pytest.raises(socket.timeout):
            conn.recv(65536)  # before the fix the 403 + FIN arrived here, body still unsent
        conn.settimeout(5)
        conn.sendall(body)
        assert conn.recv(65536).startswith(b"HTTP/1.1 403")


def test_drain_body_is_bounded():
    import asyncio

    from backend.core import local_origin_guard as guard

    calls = 0

    async def endless():
        nonlocal calls
        calls += 1
        return {"type": "http.request", "body": b"x" * 65536, "more_body": True}

    asyncio.run(guard._drain_body(endless))
    assert calls == guard.DRAIN_LIMIT_BYTES // 65536 + 1
