"""RC156 Win QA #3: /health reported a hard-coded "1.0.0" while the app was 1.5.6."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mode', ['desktop', 'web'])
def test_health_endpoints_report_package_version(tmp_path, mode):
    # create_app mutates os.environ and logging; keep it in a separate interpreter.
    script = r'''
import json, sys
from fastapi.testclient import TestClient
from backend import __version__
from backend.app_factory import create_app
app = create_app(sys.argv[1])
client = TestClient(app, base_url="http://127.0.0.1")  # loopback for the desktop host guard; no context manager: skip startup DB/key side effects
out = {"package": __version__, "openapi": app.version}
for path in ("/health", "/api/health/", "/api/v1/health/"):
    r = client.get(path)
    out[path] = [r.status_code, r.json().get("version")]
print(json.dumps(out))
'''
    env = dict(os.environ)
    env.pop('AUTOCLIP_APP_VERSION', None)
    env.update(AUTOCLIP_APP_DIR=str(tmp_path), AUTOCLIP_DATA_DIR=str(tmp_path), SENTRY_DSN='',
               DATABASE_URL='sqlite:///' + str(tmp_path / 'isolated.sqlite'),
               LOG_FILE=str(tmp_path / 'test.log'), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', '-c', script, mode], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    version = out['package']
    assert version != '1.0.0'
    assert out['openapi'] == version
    for path in ('/health', '/api/health/', '/api/v1/health/'):
        assert out[path] == [200, version], (path, out)


def test_package_version_matches_desktop_fallback(monkeypatch):
    # bump_version.py keeps these in sync; /health and the settings page must agree.
    from backend import __version__
    from backend.core.desktop_config import DesktopConfig
    monkeypatch.delenv('AUTOCLIP_APP_VERSION', raising=False)
    assert DesktopConfig.app_version.fget(object()) == __version__
