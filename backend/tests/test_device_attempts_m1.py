"""M1: device attempt ledger + generation terminal dimensions."""
import json

from backend.services.studio import attempts, device_attempts, store
from backend.services.studio.terminal_outbox import wait_until_idle


def _project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.delenv('AUTOCLIP_POSTHOG_KEY', raising=False)
    store.directory('p').mkdir(parents=True)
    (tmp_path / 'analytics.json').write_text(
        '{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding='utf-8')


def test_ledger_is_idempotent_and_tracks_first_success(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    first = device_attempts.record('t-aaaaaaaaaa', 'error')
    assert first == {'attempt_index_on_device': 1, 'is_first_success_device': True}
    again = device_attempts.record('t-aaaaaaaaaa', 'error')
    assert again == first  # same attempt_id does not bump the index
    second = device_attempts.record('t-bbbbbbbbbb', 'success')
    assert second == {'attempt_index_on_device': 2, 'is_first_success_device': True}
    third = device_attempts.record('t-cccccccccc', 'failed')
    assert third == {'attempt_index_on_device': 3, 'is_first_success_device': False}
    disk = json.loads((tmp_path / 'generation-device-attempts.json').read_text(encoding='utf-8'))
    assert set(disk['attempts']) == {'t-aaaaaaaaaa', 't-bbbbbbbbbb', 't-cccccccccc'}


def _reset_device_ledger():
    from backend.services.studio.qa import telemetry
    telemetry.set_runtime_analytics_off(False)
    device_attempts._memory.clear()
    device_attempts._memory.update({'attempts': {}})


def test_ledger_opt_out_stays_in_memory_only(tmp_path, monkeypatch):
    """privacy.json analytics:false → record must not create generation-device-attempts.json."""
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    _reset_device_ledger()
    (tmp_path / 'privacy.json').write_text(
        '{"analytics":false,"crash_reports":false}', encoding='utf-8')
    first = device_attempts.record('t-privacy-off1', 'success')
    assert first == {'attempt_index_on_device': 1, 'is_first_success_device': True}
    again = device_attempts.record('t-privacy-off1', 'success')
    assert again == first
    second = device_attempts.record('t-privacy-off2', 'error')
    assert second == {'attempt_index_on_device': 2, 'is_first_success_device': False}
    assert not (tmp_path / 'generation-device-attempts.json').exists()
    assert set(device_attempts._memory['attempts']) == {'t-privacy-off1', 't-privacy-off2'}


def test_ledger_opt_in_persists_to_disk(tmp_path, monkeypatch):
    """privacy.json analytics:true (or missing) keeps the on-disk ledger."""
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    _reset_device_ledger()
    (tmp_path / 'privacy.json').write_text(
        '{"analytics":true,"crash_reports":false}', encoding='utf-8')
    first = device_attempts.record('t-privacy-on1', 'partial')
    assert first == {'attempt_index_on_device': 1, 'is_first_success_device': True}
    disk = json.loads((tmp_path / 'generation-device-attempts.json').read_text(encoding='utf-8'))
    assert set(disk['attempts']) == {'t-privacy-on1'}
    assert disk['attempts']['t-privacy-on1']['outcome'] == 'partial'



def test_generation_summary_includes_source_duration_sec():
    state = {
        'generation': {'requested_platforms': ['douyin'], 'created_at': '2026-10-01T00:00:00Z',
                       'finished_at': '2026-10-01T00:01:00Z'},
        'plan': {'source_duration': 125.6},
        'output_variants': [], 'jobs': [], 'drafts': [],
    }
    summary = attempts.generation_summary(state)
    assert summary['source_duration_sec'] == 126
    assert summary['platform_count'] == 1


def test_terminal_event_emits_m1_dims(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    receipt = {
        'attempt_id': 't-dddddddddd', 'flow_id': 'f-1', 'sequence': 1, 'kind': 'generation',
        'state': 'completed', 'trigger': 'initial',
        'summary': {'platform_count': 2, 'source_duration_sec': 90, 'provider': 'deepseek'},
    }
    event = attempts._terminal_event(receipt)
    assert event['event'] == 'studio_generation_finished'
    props = event['properties']
    assert props['platform_count'] == 2
    assert props['source_duration_sec'] == 90
    assert props['attempt_index_on_device'] == 1
    assert props['is_first_success_device'] is True
    # failure still emits the boolean
    fail = attempts._terminal_event({
        **receipt, 'attempt_id': 't-eeeeeeeeee', 'state': 'failed',
        'error_code': 'timeout', 'failure_stage': 'production',
        'summary': {'platform_count': 1, 'source_duration_sec': 10},
    })
    assert fail['properties']['outcome'] == 'error'
    assert fail['properties']['is_first_success_device'] is False
    assert fail['properties']['attempt_index_on_device'] == 2


def test_settle_writes_m1_dims_onto_queued_terminal(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    monkeypatch.setattr('backend.services.studio.terminal_outbox._RETRY_DELAYS', ())

    def open_run(data):
        receipt = attempts.open_attempt(data, 'generation', now=store.now())
        data['plan'] = {'id': 'pl', 'source_duration': 44.2}
        data['generation'] = {
            'status': 'rendering', 'attempt_id': receipt['attempt_id'], 'auto_start': True,
            'requested_platforms': ['douyin', 'tiktok'], 'created_at': store.now(),
        }
        data['analysis'] = {'status': 'running', 'phase': 'rendering', 'run_id': 'run-1'}
        data['output_variants'] = [{
            'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'running',
            'produced_by_attempt': receipt['attempt_id'],
        }]
        data.setdefault('drafts', [])
        data.setdefault('jobs', [])

    store.change('p', open_run)

    def finish(data):
        data['output_variants'][0]['status'] = 'completed'
        return store.settle_attempt(data, kind='finish')

    assert store.change('p', finish) is True
    assert wait_until_idle()
    assert len(posted) == 1
    props = posted[0]['properties']
    assert props['outcome'] == 'success'
    assert props['platform_count'] == 2
    assert props['source_duration_sec'] == 44
    assert props['attempt_index_on_device'] == 1
    assert props['is_first_success_device'] is True


def test_catalog_registers_m1_and_deferred_fields():
    from backend.core import event_catalog
    event_catalog.reload_catalog()
    spec = event_catalog.load_catalog()['events']['studio_generation_finished']['optional_properties']
    for key in ('source_duration_sec', 'platform_count', 'is_first_success_device',
                'attempt_index_on_device', 'eta_initial_min', 'resumed_from', 'retry_kind'):
        assert key in spec, key
    payload = {
        'outcome': 'success', 'platform_count': 1, 'source_duration_sec': 10,
        'is_first_success_device': True, 'attempt_index_on_device': 1,
        'app_version': '1.5.8', 'os': 'macos', 'analytics_environment': 'production',
        'runtime': 'desktop', 'schema_version': 2,
    }
    assert event_catalog.validate_event('studio_generation_finished', payload, envelope=True) == []
