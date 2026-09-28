"""CPython 3.13 Proactor shutdown workaround for PYTHON-FASTAPI-3.

Keep the bundled Windows runtime's cleanup sequence, but tolerate a peer reset
from socket.shutdown(). Do not filter ConnectionResetError in Sentry or change
loop policy: Proactor is required for asyncio subprocess support on Windows.

Based on CPython's Lib/asyncio/proactor_events.py (PSF license).
Revisit this private-API compatibility shim when upgrading bundled Python.
"""

import socket
import sys


def _call_connection_lost(self, exc):
    if self._called_connection_lost:
        return
    try:
        self._protocol.connection_lost(exc)
    finally:
        if hasattr(self._sock, "shutdown") and self._sock.fileno() != -1:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except ConnectionResetError:
                # The peer is already gone. Still close the local socket and
                # detach from the server so wait_closed() can finish.
                pass
        self._sock.close()
        self._sock = None
        server = self._server
        if server is not None:
            server._detach(self)
            self._server = None
        self._called_connection_lost = True


def install_windows_proactor_cleanup() -> bool:
    """Install once, only on the desktop's supported CPython 3.13 runtime."""
    if sys.platform != "win32" or sys.version_info[:2] != (3, 13):
        return False
    from asyncio.proactor_events import _ProactorBasePipeTransport

    if _ProactorBasePipeTransport._call_connection_lost is _call_connection_lost:
        return True
    _ProactorBasePipeTransport._call_connection_lost = _call_connection_lost
    return True
