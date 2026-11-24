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
