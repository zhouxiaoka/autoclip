"""Success-rate terminals are posted by settle_attempt, once, even if the frontend is gone."""
import json

from backend.services.studio import attempts, jobs, store


def _project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.delenv('AUTOCLIP_POSTHOG_KEY', raising=False)
    monkeypatch.delenv('VITE_PUBLIC_POSTHOG_KEY', raising=False)
    store.directory('p').mkdir(parents=True)
    (tmp_path / 'analytics.json').write_text('{"distinct_id":"018f6b2a-7c3d-7b2a-8c11-111111111111"}', encoding='utf-8')


def _capture(monkeypatch):
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    return posted


def _open(pid='p'):
    def mutate(data):
        receipt = attempts.open_attempt(data, 'generation', now=store.now())
        data['generation'] = {'status': 'rendering', 'attempt_id': receipt['attempt_id'], 'auto_start': True,
                              'requested_platforms': ['douyin'], 'created_at': store.now()}
        data['analysis'] = {'status': 'running', 'phase': 'rendering', 'run_id': 'run-1'}
        data['output_variants'] = [{'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'running',
                                    'produced_by_attempt': receipt['attempt_id']}]
        data.setdefault('drafts', [])
        data.setdefault('jobs', [])
    store.change(pid, mutate)


def test_frontend_disconnect_still_emits_one_terminal(tmp_path, monkeypatch):
    """制作已开始、前端不再连接：任务跑完后终态事件仍只发一次，再结算一次也不加一条。"""
    _project(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    posted = _capture(monkeypatch)
    _open()
    assert posted == []  # 还在跑，没有终态

    def finish(data):
        data['output_variants'][0]['status'] = 'completed'
        return store.settle_attempt(data, kind='finish')

    assert store.change('p', finish) is True
    assert store.change('p', finish) is False  # 终态已写入，第二次幂等
    store.change('p', lambda data: jobs._finish_generation(data))  # 渲染/取消走同一个函数
    assert len(posted) == 1
    body = posted[0]
    assert body['event'] == 'studio_generation_finished'
    assert body['distinct_id'] == '018f6b2a-7c3d-7b2a-8c11-111111111111'
    props = body['properties']
    assert props['runtime'] == 'desktop' and props['analytics_environment'] == 'production'
    assert props['outcome'] == 'success'
    assert props['$insert_id'].endswith(':finished')
    assert 'error' not in props and 'sk-' not in json.dumps(props)


def test_failure_terminal_is_idempotent_and_off_when_telemetry_is_off(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    posted = _capture(monkeypatch)
    _open()

    def fail(data):
        return store.settle_attempt(data, kind='fail', error='服务商原始报错 sk-secret', error_code='timeout',
                                    context={'failure_stage': 'production'})

    assert store.change('p', fail) is True
    assert store.change('p', fail) is False
    assert posted == []  # 没有 key，不发
    assert store.read('p')['generation']['error'] == '服务商原始报错 sk-secret'
    assert store.read('p')['generation']['error_code'] == 'timeout'
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    (tmp_path / 'privacy.json').write_text('{"analytics": false}', encoding='utf-8')
    store.directory('q').mkdir(parents=True)

    def open_quiet(data):
        receipt = attempts.open_attempt(data, 'generation', now=store.now())
        data['generation'] = {'status': 'rendering', 'attempt_id': receipt['attempt_id'], 'auto_start': True,
                              'requested_platforms': ['douyin'], 'created_at': store.now()}
        data['output_variants'] = [{'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'completed',
                                    'produced_by_attempt': receipt['attempt_id']}]
        data.setdefault('drafts', [])
        data.setdefault('jobs', [])
    store.change('q', open_quiet)
    assert store.change('q', lambda data: store.settle_attempt(data, kind='finish')) is True
    assert posted == []  # 有 key，但遥测关闭，新的终态也不发


def test_read_does_not_persist_an_interrupted_run(tmp_path, monkeypatch):
    _project(tmp_path, monkeypatch)
    path = store.directory('p') / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'generation': {'status': 'production', 'auto_start': True},
                                'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'r', 'instance': 'previous-process'},
                                'drafts': [], 'jobs': [], 'output_variants': []}), encoding='utf-8')
    seen = store.read('p')
    assert json.loads(path.read_text(encoding='utf-8'))['generation']['status'] == 'production'
    assert seen['generation']['status'] == 'production'
    healed = store.recover('p')
    assert healed['generation']['status'] == 'failed'
    assert json.loads(path.read_text(encoding='utf-8'))['generation']['status'] == 'failed'
