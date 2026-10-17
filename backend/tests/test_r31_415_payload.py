"""R31 #415 I565 (Dong): runtime payload tests replace the reader AST heuristic as the primary guard.

A dirty record / snapshot (extra keys, a string status, a bool status, an unknown source, a URL-ish prose
value in a non-whitelisted key) goes through every exit: the store read projection, the history summary,
llm_emit.attribution / run_snapshot / sentry_tags_for_error, sentry_setup.studio_failure_context and the
real Sentry envelope (fake transport, nothing is sent). Only whitelisted keys with valid values come out."""
import json

import pytest

from backend.core import failure_attribution, llm_emit, sentry_setup
from backend.core.failure_attribution import AttributedError, FailureAttribution, SNAPSHOT_FIELDS, export_attribution
from backend.services.studio import store
from backend.tests.test_r25_415 import isolated  # noqa: F401
from backend.tests.test_r30_415 import _envelope_events

SECRET = 'sk-r31-SECRET-0000 https://user:pw@private.example/v1?key=x /Users/someone/clip.mp4'
DIRTY = {'attribution_source': 'request', 'provider': 'kimi', 'config_source': 'custom', 'model': 'kimi-k2',
         'base_url_host': 'kimi.fixture.example', 'http_status': '503;drop', 'upstream_error_type': 'upstream_unavailable',
         'failure_stage': 'analyze', 'raw_message': SECRET, 'api_key': SECRET, 'url': SECRET}
WHITELIST = set(SNAPSHOT_FIELDS)


def _no_secret(payload):
    text = json.dumps(payload, ensure_ascii=False, default=str)
    assert 'SECRET' not in text and 'private.example' not in text and '/Users/' not in text, text
    assert '503;drop' not in text, text


class _Safe(AttributedError, RuntimeError):
    pass


def _dirty_error():
    error = _Safe('safe text')
    # bypass the factory on purpose: a snapshot that a future writer could build wrong
    error.attribution = FailureAttribution('request', provider='kimi', config_source='custom', model='kimi-k2',
                                           base_url_host='kimi.fixture.example', http_status='503;drop',
                                           upstream_error_type='upstream_unavailable', failure_stage='analyze')
    return error


@pytest.mark.parametrize('status', ['503;drop', '503', True, 302, 600, 503.0])
def test_i565_the_serializer_copies_only_whitelisted_valid_fields(status):
    out = export_attribution({**DIRTY, 'status': 'failed', 'http_status': status})
    assert set(out) <= WHITELIST
    assert 'http_status' not in out
    assert out['provider'] == 'kimi' and out['attribution_source'] == 'request'
    assert export_attribution({**DIRTY, 'status': 'failed', 'http_status': 503})['http_status'] == 503


def test_i565_the_serializer_drops_an_unknown_source_and_a_half_identity():
    out = export_attribution({'status': 'failed', 'attribution_source': 'guess', 'provider': 'kimi', 'model': 'm'})
    assert out == {}


def test_i565_store_read_projection_and_history_summary_carry_only_whitelisted_fields():
    pid = 'p565'
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {'status': 'running', 'run_id': 'r1', 'phase': 'screening'}}, _recover_previous=False)
    path = store.directory(pid) / 'metadata' / 'studio.json'
    raw = json.loads(path.read_text())
    raw['analysis'] = {**raw['analysis'], **DIRTY, 'status': 'failed', 'error_code': 'provider_error'}
    path.write_text(json.dumps(raw))
    read = store.read(pid)['analysis']
    assert read.get('http_status') is None and read.get('provider') == 'kimi'
    store.write(pid, {**store.read(pid), 'analysis': {'status': 'running', 'run_id': 'r2', 'phase': 'screening'}}, _recover_previous=False)
    row = next(r for r in store.read(pid).get('analysis_history', []) if r['run_id'] == 'r1')['analysis']
    assert set(row) & set(DIRTY) <= WHITELIST
    _no_secret(row)
    assert row.get('provider') == 'kimi' and 'http_status' not in row


def test_i565_llm_emit_exits_carry_only_whitelisted_valid_fields():
    error = _dirty_error()
    fields = llm_emit.attribution(error)
    assert set(fields) <= WHITELIST and 'http_status' not in fields
    with llm_emit.track_run():
        snap = llm_emit.run_snapshot(error=error)
    assert snap.get('http_status') is None
    _no_secret(snap)
    tags = llm_emit.sentry_tags_for_error(error, 'analyze')
    assert 'http_status' not in tags and tags.get('provider') == 'kimi'
    _no_secret(tags)


def test_i565_sentry_failure_context_and_envelope_carry_only_whitelisted_valid_fields():
    error = _dirty_error()
    context = sentry_setup.studio_failure_context(error, 'analyze')
    assert set(context) <= {'failure_stage', 'http_status', 'upstream_error_type'}
    assert 'http_status' not in context
    events = _envelope_events(error, with_product_filter=True)
    for event in events:
        _no_secret({k: event.get(k) for k in ('tags', 'contexts', 'extra')})


def test_i565_write_attribution_stores_only_whitelisted_valid_fields():
    record = {'status': 'failed', 'raw_message': 'kept, not an attribution field'}
    failure_attribution.write_attribution(record, _dirty_error().attribution)
    assert 'http_status' not in record
    assert set(record) - {'status', 'raw_message'} <= WHITELIST


def test_i565_sentry_tags_take_no_identity_from_a_snapshot_whose_pair_is_invalid():
    """THE serializer's pair rule: provider/config_source that are not strings -> no identity at all, so
    model and host (valid on their own) do not go out as somebody's identity."""
    error = _Safe('safe text')
    error.attribution = FailureAttribution('request', provider=8, config_source=7, model='kimi-k2',
                                           base_url_host='kimi.fixture.example', http_status=503, failure_stage='analyze')
    tags = llm_emit.sentry_tags_for_error(error, 'analyze')
    assert not {'provider', 'model', 'base_url_host'} & set(tags), tags
    assert tags.get('http_status') == '503'


def test_i565_history_summary_of_a_dirty_terminal_the_writer_hands_in():
    """A writer hands a dirty failed terminal to store.write (no error in hand: the group it carries stays);
    its history row is built through THE serializer, not copied."""
    pid = 'p565w'
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    store.write(pid, {'id': pid, 'analysis': {**DIRTY, 'status': 'failed', 'run_id': 'r1', 'phase': 'screening',
                                              'error_code': 'provider_error'}}, _recover_previous=False)
    stored = json.loads((store.directory(pid) / 'metadata' / 'studio.json').read_text())  # what is on disk
    for row in (next(r for r in store.read(pid).get('analysis_history', []) if r['run_id'] == 'r1')['analysis'],
                next(r for r in stored.get('analysis_history', []) if r['run_id'] == 'r1')['analysis']):
        _no_secret(row)
        assert set(row) & set(DIRTY) <= WHITELIST and 'http_status' not in row
