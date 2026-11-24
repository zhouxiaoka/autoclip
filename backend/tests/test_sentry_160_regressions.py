"""Regression tests for v1.6.0 Sentry issues: PYTHON-FASTAPI-6K, -70, -78."""
from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.core import llm_stream, windows_asyncio
from backend.services.studio import framing


def test_python_fastapi_6k_dissolve_cuts_skips_cleanly_without_numpy(monkeypatch, tmp_path):
    """PYTHON-FASTAPI-6K: Windows portable bundle without optional numpy must not crash detect_cuts."""
    real_import = builtins.__import__

    def no_numpy(name, *args, **kwargs):
        if name == "numpy" or name.startswith("numpy."):
            raise ModuleNotFoundError("No module named 'numpy'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_numpy)
    dummy_video = tmp_path / "sample.mp4"
    dummy_video.write_bytes(b"")
    assert framing._dissolve_cuts(dummy_video, 0.0, 5.0) == []


def test_python_fastapi_70_windows_proactor_tolerates_shutdown_oserror():
    """PYTHON-FASTAPI-70: socket.shutdown() raising OSError (e.g. WSAENOTCONN 10057) must still close & detach."""
    sock = MagicMock()
    sock.fileno.return_value = 42
    sock.shutdown.side_effect = OSError(10057, "Socket is not connected")
    server = MagicMock()
    protocol = MagicMock()

    class _FakeTransport:
        _called_connection_lost = False
        _sock = sock
        _server = server
        _protocol = protocol

    transport = _FakeTransport()
    windows_asyncio._call_connection_lost(transport, None)

    protocol.connection_lost.assert_called_once_with(None)
    sock.close.assert_called_once()
    server._detach.assert_called_once_with(transport)
    assert transport._sock is None
    assert transport._server is None
    assert transport._called_connection_lost is True


def test_python_fastapi_78_closed_chunked_response_converts_attribute_error_to_connection_error():
    """PYTHON-FASTAPI-78: HTTPResponse._peek_chunked raising AttributeError on closed fp becomes ConnectionError."""
    class _ClosedChunkedResponse:
        fp = None

        def readline(self):
            raise AttributeError("'NoneType' object has no attribute 'peek'")

    with pytest.raises(ConnectionError, match="HTTP stream closed mid-read"):
        list(llm_stream._lines(_ClosedChunkedResponse()))


def test_python_fastapi_78_unrelated_attribute_error_still_propagates():
    class _BrokenResponse:
        fp = object()

        def readline(self):
            raise AttributeError("unexpected bug")

    with pytest.raises(AttributeError, match="unexpected bug"):
        list(llm_stream._lines(_BrokenResponse()))


def test_python_fastapi_79_playwright_timeout_downgrades_as_over_budget_without_sentry_error(monkeypatch, tmp_path):
    """PYTHON-FASTAPI-79: playwright._impl._errors.TimeoutError does not subclass builtin TimeoutError."""
    from backend.services.studio import packaging_html

    class _PlaywrightTimeoutError(Exception):
        pass

    _PlaywrightTimeoutError.__name__ = "TimeoutError"

    reported = []
    monkeypatch.setattr(packaging_html, "report_overlay_failure", lambda err: reported.append(err))
    monkeypatch.setattr(packaging_html, "overlay_cache_path", lambda *a, **kw: tmp_path / "overlay.mkv")
    monkeypatch.setattr(packaging_html, "load_project_word_timing", lambda _pid: [])
    monkeypatch.setattr(packaging_html, "load_project_transcript", lambda _pid: [])

    async def boom(_frames, _fps):
        raise _PlaywrightTimeoutError("Page.screenshot: Timeout 30000ms exceeded.")

    job = packaging_html.prepare_overlay(
        project_id="p1",
        packaging={"title": "Demo", "captions": []},
        duration=2.0,
        template="editorial",
        features={"html_packaging": True},
        capture=boom,
    )
    assert job.downgraded is True
    assert job.downgrade_reason == "over_budget"
    assert reported == []
