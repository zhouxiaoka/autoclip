"""root cause: a log line interleaved into "PORT=N<newline>" made the e2e harness miss the
port and time out ("desktop backend did not print PORT="). The fake backend below reproduces the
exact interleaving seen in CI and on the box: stdout "PORT=N", then a stderr log line, then "\n"."""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from provider_e2e.backend import DesktopBackend  # noqa: E402

FAKE = textwrap.dedent('''
    import http.server, json, socket, sys, threading
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    sys.stdout.write(f"PORT={port}"); sys.stdout.flush()
    sys.stderr.write("2026-10-16 18:56:01,826 - __main__ - INFO - API\\n"); sys.stderr.flush()
    sys.stdout.write("\\n"); sys.stdout.flush()
    srv.serve_forever()
''')


@pytest.mark.skipif(sys.platform == 'win32', reason='sh launcher')
def test_port_is_read_even_when_a_log_line_interleaves(tmp_path):
    script = tmp_path / 'fake_backend.py'
    script.write_text(FAKE)
    launcher = tmp_path / 'python'
    launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n')
    launcher.chmod(0o755)
    backend = DesktopBackend(tmp_path / 'data', python=str(launcher))
    try:
        url = backend.start(timeout=10)
        assert url.startswith('http://127.0.0.1:')
    finally:
        backend.kill()
    assert 'INFO - API' in backend.log_path.read_text()
