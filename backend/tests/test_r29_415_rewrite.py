"""R29 #415 increment (Dong 11:09): the rewrite route's checks on the model's own reply (a missing key, a
Draft that fails validation) are ModelResponseInvalid -> MODEL / invalid_response, snapshot only; neither the
HTTP response nor the Sentry payload carries the raw model text. Fails on 0b6da07a on an assertion."""
import json

import pytest

from backend.core import sentry_setup
from backend.core.failure_attribution import FailureKind, classify_failure
from backend.services.studio import intelligence
from backend.tests.test_studio import client, root, source  # noqa: F401

RAW = 'r29-raw-model-reply-PRIVATE'


@pytest.mark.parametrize('reply', [
    {'title': RAW},                                  # hook missing -> KeyError
    {'title': {'nested': RAW}, 'hook': RAW},         # Draft.model_validate fails (title is not a string)
    [RAW],                                           # not an object at all
], ids=['missing_key', 'fails_validation', 'not_an_object'])
def test_rewrite_route_invalid_model_reply_is_model_invalid_response_without_raw_text(client, monkeypatch, reply):
    import sentry_sdk
    from sentry_sdk.utils import event_from_exception
    draft = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    monkeypatch.setattr(intelligence, 'text_json', lambda *a, **k: reply)
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    monkeypatch.setattr(sentry_setup, 'crash_reports_enabled', lambda: True)
    captured = []

    def capture(exc):
        options = {**sentry_sdk.get_client().options, 'include_local_variables': False, 'include_source_context': False}
        event, _ = event_from_exception(exc, client_options=options)
        event['tags'] = dict(sentry_sdk.get_current_scope()._tags)
        raw_event = json.dumps(event, default=str)  # what the SDK builds before our scrubber
        captured.append((exc, raw_event, sentry_setup.before_send(event, {}) or event))
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)

    response = client.post('/studio/p1/rewrite', json={'draft': draft, 'instruction': 'shorter'})
    assert response.status_code == 502, response.text
    assert RAW not in response.text
    assert len(captured) == 1
    error, raw_event, event = captured[0]
    assert RAW not in raw_event  # the raw reply is not even in the chain the SDK walks
    assert len(json.loads(raw_event)['exception']['values']) == 1
    assert classify_failure(error).kind is FailureKind.MODEL
    assert sentry_setup.studio_error_code(error) == 'invalid_response'
    assert event['tags']['error_code'] == 'invalid_response' and event['tags']['phase'] == 'rewrite'
    assert RAW not in json.dumps(event, default=str)
