"""X2: analytics off in the UI -> backend Sentry never attaches user.id, in any process."""
import asyncio

import pytest
import sentry_sdk

from backend.core import sentry_setup

ID = '018f6b2a-7c3d-7b2a-8c11-111111111111'
EVENT = {'user': {'id': ID}, 'exception': {'values': [{'type': 'RuntimeError', 'value': 'x'}]}}


@pytest.fixture
def scope(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_ANONYMOUS_DEVICE_ID', ID)
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    s = sentry_sdk.get_global_scope()
    previous = s._user
    yield s
    s.set_user(previous)


def _consent(enabled):
    from backend.api.v1.settings import AnalyticsConsent, put_analytics_consent
    return asyncio.run(put_analytics_consent(AnalyticsConsent(enabled=enabled)))


def test_opt_out_clears_scope_and_every_event(scope):
    from backend.services.studio.qa.telemetry import remember_distinct_id
    assert remember_distinct_id(ID)
    assert scope._user == {'id': ID}
    assert sentry_setup.before_send(dict(EVENT))['user'] == {'id': ID}

    _consent(False)
    assert scope._user is None
    # A worker whose scope still carries the id (or the launch env fallback) rereads privacy.json.
    assert 'user' not in sentry_setup.before_send(dict(EVENT))
    # A late identity PUT while opted out must not re-attach the id.
    remember_distinct_id(ID)
    assert scope._user is None
    assert 'user' not in sentry_setup.before_send(dict(EVENT))

    _consent(True)
    assert scope._user == {'id': ID}
    assert sentry_setup.before_send(dict(EVENT))['user'] == {'id': ID}


def test_write_privacy_keeps_crash_reports_when_writing_analytics(scope):
    sentry_setup.write_privacy(crash_reports=False)
    sentry_setup.write_privacy(analytics=False)
    assert sentry_setup.crash_reports_enabled() is False
