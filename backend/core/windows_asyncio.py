"""CPython 3.13 Proactor shutdown workaround for PYTHON-FASTAPI-3.

Keep the bundled Windows runtime's cleanup sequence, but tolerate a peer reset
from socket.shutdown(). Do not change loop policy: Proactor is required for
asyncio subprocess support on Windows. Sentry drops ConnectionResetError
(WinError 10054), ConnectionAbortedError (10053) and BrokenPipeError (109)
only when the stack is asyncio.proactor_events (sentry_setup). The same
types raised anywhere else are reported.

Based on CPython's Lib/asyncio/proactor_events.py (PSF license).
Revisit this private-API compatibility shim when upgrading bundled Python.
"""

import errno
import socket
import sys

_BENIGN_SHUTDOWN_ERRNOS = frozenset({
    errno.ENOTCONN,
    errno.EBADF,
    10038,  # WSAENOTSOCK
    10053,  # WSAECONNABORTED
    10054,  # WSAECONNRESET
    10057,  # WSAENOTCONN
})


def _is_benign_shutdown_error(exc: OSError) -> bool:
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return True
    return exc.errno in _BENIGN_SHUTDOWN_ERRNOS or getattr(exc, "winerror", None) in _BENIGN_SHUTDOWN_ERRNOS


def _call_connection_lost(self, exc):
    if self._called_connection_lost:
        return
    try:
        self._protocol.connection_lost(exc)
    finally:
        if hasattr(self._sock, "shutdown") and self._sock.fileno() != -1:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError as shutdown_exc:
                if not _is_benign_shutdown_error(shutdown_exc):
                    raise
                # The peer or socket is already gone (e.g. WinError 10054 / 10057 / 10038).
                # Still close the local socket and detach from the server so wait_closed() finishes.
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
