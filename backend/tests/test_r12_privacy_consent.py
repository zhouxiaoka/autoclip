"""R12 #392 items 17, 18, 20."""
import asyncio
import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.api.v1 import settings as settings_api
from backend.core import sentry_setup
from backend.services.studio.qa import telemetry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    telemetry.set_runtime_analytics_off(False)
    yield
    telemetry.set_runtime_analytics_off(False)


def _put(enabled):
    return asyncio.run(settings_api.put_analytics_consent(settings_api.AnalyticsConsent(enabled=enabled)))


def test_off_disables_in_process_and_clears_identity_before_disk_write(monkeypatch):
    order = []
    monkeypatch.setattr(sentry_setup, 'clear_anonymous_user', lambda: order.append(('clear', telemetry._analytics_allowed())))

    def write(**kw):
        order.append(('write', telemetry._analytics_allowed()))
        raise OSError('disk full')

    monkeypatch.setattr(sentry_setup, 'write_privacy', write)
    with pytest.raises(HTTPException):
        _put(False)
    # collection was already off when the identity was cleared and when the write ran
    assert order == [('clear', False), ('write', False)]
    # write failed: stays off (in-process, so API + worker threads)
    assert telemetry._analytics_allowed() is False


def test_on_after_off_re_enables_only_after_successful_write(tmp_path):
    _put(False)
    assert telemetry._analytics_allowed() is False
    _put(True)
    assert telemetry._analytics_allowed() is True
    assert json.loads((tmp_path / 'privacy.json').read_text())['analytics'] is True


@pytest.mark.parametrize('toggle,other', [('analytics', 'crash_reports'), ('crash_reports', 'analytics')])
def test_corrupt_privacy_defaults_both_off_and_changes_only_requested_toggle(tmp_path, toggle, other):
    (tmp_path / 'privacy.json').write_text('{broken', encoding='utf-8')
    assert sentry_setup.crash_reports_enabled() is False
    assert telemetry._analytics_allowed() is False
    sentry_setup.write_privacy(**{toggle: True})
    data = json.loads((tmp_path / 'privacy.json').read_text())
    assert data[toggle] is True and data[other] is False


def test_single_writer_only_backend_api_writes_privacy_json():
    callers = []
    for path in (ROOT / 'backend').rglob('*.py'):
        if 'tests' in path.parts:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if re.search(r'\bwrite_privacy\(', text) and path.name != 'sentry_setup.py':
            callers.append(path.relative_to(ROOT).as_posix())
    assert callers == ['backend/api/v1/settings.py']
    assert 'Single writer: only the backend API process writes privacy.json' in (ROOT / 'backend/core/sentry_setup.py').read_text(encoding='utf-8')
