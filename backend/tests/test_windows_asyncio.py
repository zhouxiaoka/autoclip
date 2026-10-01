"""Exercise real CPython transport cleanup with a synthetic reset socket."""

import asyncio
from asyncio.proactor_events import _ProactorBasePipeTransport
from unittest.mock import Mock

import pytest

from backend.core import windows_asyncio

pytestmark = pytest.mark.stdlib_only


@pytest.fixture
def transport():
    sock = Mock(spec=["shutdown", "close", "fileno"])
    sock.fileno.return_value = 42
    item = _ProactorBasePipeTransport(Mock(), sock, Mock(), server=Mock())
    yield item, sock, item._protocol, item._server
    # Avoid destructor warnings in negative-path tests.
    item._sock = None


def test_original_runtime_reproduces_incomplete_cleanup(transport):
    item, sock, protocol, server = transport
    sock.shutdown.side_effect = ConnectionResetError(10054, "synthetic peer reset")
    with pytest.raises(ConnectionResetError):
        item._call_connection_lost(None)
    protocol.connection_lost.assert_called_once_with(None)
    sock.close.assert_not_called()
    server._detach.assert_not_called()
    assert not item._called_connection_lost


def test_reset_still_closes_and_detaches_once(transport):
    item, sock, protocol, server = transport
    sock.shutdown.side_effect = ConnectionResetError(10054, "synthetic peer reset")
    cause = ConnectionResetError("read failed")
    windows_asyncio._call_connection_lost(item, cause)
    windows_asyncio._call_connection_lost(item, cause)
    protocol.connection_lost.assert_called_once_with(cause)
    sock.close.assert_called_once()
    server._detach.assert_called_once_with(item)
    assert item._sock is None and item._server is None
    assert item._called_connection_lost


@pytest.mark.parametrize("kind", ["normal", "closed", "pipe"])
def test_other_cleanup_paths(transport, kind):
    item, sock, protocol, server = transport
    if kind == "closed":
        sock.fileno.return_value = -1
    elif kind == "pipe":
        del sock.shutdown
    windows_asyncio._call_connection_lost(item, None)
    sock.close.assert_called_once()
    server._detach.assert_called_once_with(item)
    assert item._called_connection_lost
    if kind == "closed":
        sock.shutdown.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("protocol failed"), ConnectionResetError("protocol reset")])
def test_protocol_failures_remain_visible_and_cleanup_finishes(transport, error):
    item, sock, protocol, server = transport
    protocol.connection_lost.side_effect = error
    sock.shutdown.side_effect = ConnectionResetError("shutdown reset")
    with pytest.raises(type(error)) as caught:
        windows_asyncio._call_connection_lost(item, None)
    assert caught.value is error
    sock.close.assert_called_once()
    server._detach.assert_called_once_with(item)


def test_unexpected_shutdown_failure_is_not_silenced(transport):
    item, sock, _, _ = transport
    sock.shutdown.side_effect = PermissionError("synthetic denial")
    with pytest.raises(PermissionError):
        windows_asyncio._call_connection_lost(item, None)


@pytest.mark.parametrize("platform,version,installed", [
    ("win32", (3, 13), True), ("darwin", (3, 13), False),
    ("linux", (3, 13), False), ("win32", (3, 14), False),
])
def test_installer_scope_and_idempotence(monkeypatch, platform, version, installed):
    original = _ProactorBasePipeTransport._call_connection_lost
    monkeypatch.setattr(_ProactorBasePipeTransport, "_call_connection_lost", original)
    monkeypatch.setattr(windows_asyncio.sys, "platform", platform)
    monkeypatch.setattr(windows_asyncio.sys, "version_info", version)
    assert windows_asyncio.install_windows_proactor_cleanup() is installed
    expected = windows_asyncio._call_connection_lost if installed else original
    assert _ProactorBasePipeTransport._call_connection_lost is expected
    assert windows_asyncio.install_windows_proactor_cleanup() is installed
    assert _ProactorBasePipeTransport._call_connection_lost is expected


def test_headless_startup_closes_reset_transport(tmp_path, monkeypatch, transport):
    """CLI/MCP startup must install cleanup before any application/SDK imports."""
    import importlib.util
    from pathlib import Path

    # This runtime-only suite installs just pytest. Load the stdlib-only runner
    # directly so importing backend.services doesn't bring in SQLAlchemy.
    spec = importlib.util.spec_from_file_location(
        'autoclip_runtime_runner', Path(__file__).parents[1] / 'services' / 'local_runner.py',
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(windows_asyncio.sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(_ProactorBasePipeTransport, '_call_connection_lost', _ProactorBasePipeTransport._call_connection_lost)
    monkeypatch.setattr(windows_asyncio.sys, 'platform', 'win32')
    monkeypatch.setattr(windows_asyncio.sys, 'version_info', (3, 13))
    for name in ('AUTOCLIP_APP_DIR', 'AUTOCLIP_DATA_DIR', 'LOG_FILE', 'DATABASE_URL', 'AUTOCLIP_CLI_QUIET'):
        monkeypatch.setenv(name, 'test')

    module.configure_environment(tmp_path)
    item, sock, protocol, server = transport
    sock.shutdown.side_effect = ConnectionResetError('peer reset during headless shutdown')
    item._call_connection_lost(None)
    sock.close.assert_called_once()
    server._detach.assert_called_once_with(item)
    assert item._called_connection_lost and item._sock is None


@pytest.mark.skipif(windows_asyncio.sys.platform != "win32", reason="Windows IOCP integration")
def test_windows_real_reset_and_subprocess():
    """Exercise actual Proactor sockets and retain subprocess support on Windows."""
    import socket
    import struct

    async def run():
        loop = asyncio.get_running_loop()
        errors = []
        loop.set_exception_handler(lambda _loop, context: errors.append(context))
        connected = asyncio.Event()
        released = asyncio.Event()

        class Protocol(asyncio.Protocol):
            def connection_made(self, transport):
                self.transport = transport
                connected.set()

            def connection_lost(self, exc):
                released.set()

        server = await loop.create_server(Protocol, "127.0.0.1", 0)
        try:
            for _ in range(20):
                connected.clear()
                released.clear()
                client = socket.socket()
                try:
                    client.connect(server.sockets[0].getsockname())
                    await asyncio.wait_for(connected.wait(), 5)
                    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("HH", 1, 0))
                finally:
                    client.close()  # RST, not a graceful FIN
                await asyncio.wait_for(released.wait(), 5)
            process = await asyncio.create_subprocess_exec(
                windows_asyncio.sys.executable, "-c", "print('ok')", stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), 10)
            assert process.returncode == 0 and stdout.strip() == b"ok"
        finally:
            server.close()
            await asyncio.wait_for(server.wait_closed(), 5)
        assert not errors

    original = _ProactorBasePipeTransport._call_connection_lost
    try:
        assert windows_asyncio.install_windows_proactor_cleanup()
        with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
            runner.run(run())
    finally:
        _ProactorBasePipeTransport._call_connection_lost = original
