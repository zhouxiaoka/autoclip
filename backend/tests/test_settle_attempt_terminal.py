"""Success-rate terminals are posted by settle_attempt, once, even if the frontend is gone."""
import json
import threading
import time

from backend.core import project_cancellation
from backend.services.studio import attempts, jobs, store
from backend.services.studio.terminal_outbox import pending_ids, replay_unsent, wait_until_idle


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
    assert wait_until_idle()
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
        data['output_variants'] = [{'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'running',
                                    'produced_by_attempt': receipt['attempt_id']}]
        data.setdefault('drafts', [])
        data.setdefault('jobs', [])
    store.change('q', open_quiet)

    def finish_quiet(data):
        data['output_variants'][0]['status'] = 'completed'
        return store.settle_attempt(data, kind='finish')

    (tmp_path / 'terminal-outbox.json').write_text(
        '{"pending":[{"insert_id":"studio-v1:old:finished","event":"studio_generation_finished","properties":{"outcome":"success","$insert_id":"studio-v1:old:finished"},"envelope":{}}]}',
        encoding='utf-8')
    assert store.change('q', finish_quiet) is True
    assert posted == []  # 有 key，但遥测关闭，新的终态也不发
    assert pending_ids() == []  # 关闭遥测时把还没发出去的一并清掉


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


def test_stuck_post_does_not_hold_the_studio_lock(tmp_path, monkeypatch):
    """发送卡住时，别的线程不用等 PostHog 就能拿到工作室锁。外层 with lock 也一样。"""
    _project(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    posted = []
    entered, release_send = threading.Event(), threading.Event()

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        entered.set()
        assert release_send.wait(5)
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    _open()
    acquired, errors = {}, []

    def finish(data):
        data['output_variants'][0]['status'] = 'completed'
        return store.settle_attempt(data, kind='finish')

    def writer():
        try:
            with store.lock:
                assert store.change('p', finish) is True
        except Exception as error:  # noqa: BLE001 - surface the writer failure on the main thread
            errors.append(error)
            release_send.set()

    def other():
        if not entered.wait(3):
            acquired['error'] = 'send did not start'
            return
        started = time.monotonic()
        try:
            store.lock.acquire()
        except Exception as error:  # noqa: BLE001
            acquired['error'] = type(error).__name__
            release_send.set()
            return
        acquired['elapsed'] = time.monotonic() - started
        store.lock.release()
        release_send.set()

    worker, waiter = threading.Thread(target=writer), threading.Thread(target=other)
    worker.start()
    waiter.start()
    worker.join(8)
    waiter.join(8)
    release_send.set()
    assert wait_until_idle()
    assert not errors, errors
    assert acquired.get('error') is None
    assert acquired['elapsed'] < 1.0
    assert len(posted) == 1 and posted[0]['properties']['$insert_id'].endswith(':finished')
    assert store.change('p', finish) is False
    assert len(posted) == 1
    assert store.read('p')['generation']['status'] == 'completed'


def test_shutdown_does_not_wait_for_a_stuck_post(tmp_path, monkeypatch):
    started, release, done = threading.Event(), threading.Event(), threading.Event()

    def slow():
        started.set()
        release.wait(3)
        done.set()

    _project(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.setattr('backend.services.studio.terminal_outbox._send_pending', slow)
    project_cancellation._shutting_down = True
    store._deferred_terminals.events = [{
        'event': 'studio_generation_finished',
        'properties': {'outcome': 'success', '$insert_id': 'studio-v1:t-shutdown:finished'},
    }]
    try:
        began = time.monotonic()
        store._deliver_deferred_terminals()
        elapsed = time.monotonic() - began
        assert elapsed < 0.5
        assert started.wait(2)
    finally:
        project_cancellation._shutting_down = False
        release.set()
    assert done.wait(2)
    assert wait_until_idle()
    assert store._deferred_terminals.events is None


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b''


def test_offline_settle_replays_once_after_restart(tmp_path, monkeypatch):
    """结算时断网：调用方不等网络。重启后同一条 $insert_id 补发一次，再补发不再发。"""
    _project(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    seen = []

    def offline(req, timeout=0):
        seen.append(json.loads(req.data.decode()))
        time.sleep(1.2)
        raise OSError('offline')

    monkeypatch.setattr('urllib.request.urlopen', offline)
    _open()

    def finish(data):
        data['output_variants'][0]['status'] = 'completed'
        return store.settle_attempt(data, kind='finish')

    began = time.monotonic()
    assert store.change('p', finish) is True
    assert time.monotonic() - began < 0.8
    assert wait_until_idle(4)
    assert len(seen) == 1
    insert_id = seen[0]['properties']['$insert_id']
    assert insert_id.endswith(':finished')
    assert pending_ids() == [insert_id]
    assert 'phc_' not in (tmp_path / 'terminal-outbox.json').read_text(encoding='utf-8')

    posted = []

    def online(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        return _Response()

    monkeypatch.setattr('urllib.request.urlopen', online)
    replay_unsent()
    assert wait_until_idle()
    assert len(posted) == 1
    assert posted[0]['properties']['$insert_id'] == insert_id
    assert pending_ids() == []
    replay_unsent()
    assert wait_until_idle()
    assert len(posted) == 1
