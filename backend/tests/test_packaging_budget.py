"""Optional packaging must leave prepared clips able to enter rendering."""
from types import SimpleNamespace

import pytest

from backend.core import job_budget
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.services.studio import intelligence, jobs, packaging


@pytest.fixture
def packaging_run(monkeypatch):
    from backend.pipeline import concurrency
    now = [100.0]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(concurrency, 'workers', lambda: 1)
    monkeypatch.setattr(jobs, '_packaging_inputs', lambda *args: None)
    strategy = SimpleNamespace(template='interview_zh', audience_language='zh')
    monkeypatch.setattr(jobs, '_project_strategy', lambda *args: strategy)
    items = [('douyin', {'title': 'Useful clip', 'scenes': [{'start': 0, 'end': 5}]}),
             ('douyin', {'title': 'Another clip', 'scenes': [{'start': 5, 'end': 10}]})]
    cache = {'entries': [{'start_time': '00:00:00,000', 'end_time': '00:00:10,000', 'text': 'Useful source words'}], 'names': ''}
    return now, items, cache, strategy


def test_packaging_deadline_keeps_source_captions_and_parent_budget(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    calls = []
    def slow(*args):
        calls.append(args[0] == packaging.PROMPT)
        while not job_budget.budget_expired():
            now[0] += 30
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(seconds=1200):
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
        for platform, value in items:
            packed = jobs._apply_packaging('isolated-project', value, platform, False, cache)['packaging']
            assert packed['fallback'] is True
            assert packed['cues'][0]['text'] == 'Useful source words'
    assert calls == [True, True, False]  # two bounded full requests, then the reserved translation
    assert now[0] == 100 + packaging.PACKAGING_BUDGET_SEC


def test_packaging_timeout_preserves_completed_cache(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    key = (((0, 5),), 'interview_zh', 'zh')
    completed = {'title_lines': ['已完成'], 'fallback': False}
    cache[key] = completed
    def slow(*args):
        now[0] += 301
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job():
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
    assert cache[key] is completed
    assert jobs._apply_packaging('isolated-project', items[1][1], 'douyin', False, cache)['packaging']['fallback']


def test_packaging_cannot_restore_expired_parent(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    def slow(*args):
        now[0] += 1200
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(), pytest.raises(job_budget.JobDurationExceeded):
        jobs._prefetch_packaging('isolated-project', items, False, cache)


def test_packaging_reserves_short_remaining_budget_without_calling_model(packaging_run, monkeypatch):
    _, items, cache, _ = packaging_run
    calls = []
    monkeypatch.setattr(intelligence, 'text_json', lambda *args: calls.append(True) or {})
    with job_budget.bound_clip_job(seconds=20):
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
    assert calls == []


@pytest.mark.parametrize('error', [JobStopped, ProjectDeleted, ServiceRestarted, job_budget.JobDurationExceeded])
@pytest.mark.parametrize('translation', [False, True])
def test_packaging_propagates_control_signals_without_another_model_call(packaging_run, error, translation):
    _, _, _, strategy = packaging_run
    calls = []
    def call(*args):
        calls.append(True)
        if translation and len(calls) <= 2:
            raise ValueError('invalid packaging')
        raise error()
    with pytest.raises(error):
        packaging.build_packaging({'title': 'Title'}, [{'start': 0, 'end': 5, 'text': 'Source words'}], strategy, call=call)
    assert len(calls) == (3 if translation else 1)


def test_packaging_transport_failure_does_not_retry_as_translation(packaging_run):
    _, _, _, strategy = packaging_run
    calls = []
    def call(*args):
        calls.append(True)
        raise RuntimeError('transport unavailable')
    result = packaging.build_packaging({'title': 'Title'}, [{'start': 0, 'end': 5, 'text': 'Source words'}], strategy, call=call)
    assert result['fallback'] and result['cues'][0]['text'] == 'Source words'
    assert len(calls) == 1


def test_stalled_style_leaves_time_for_one_caption_translation(packaging_run, monkeypatch, caplog):
    now, items, cache, _ = packaging_run
    cache['entries'][0]['text'] = 'These are the source subtitles for the interview.'
    prompts = []

    def model(prompt, payload):
        prompts.append(prompt)
        if prompt == packaging.PROMPT:
            now[0] += job_budget.clip_job_read_timeout(1000) + .01
            job_budget.ensure_clip_job_budget()
        assert 0 < job_budget.clip_job_read_timeout(1000) <= 60
        return {'lines': [{'id': row['id'], 'text': '这是访谈字幕。'} for row in payload['lines']]}

    monkeypatch.setattr(intelligence, 'text_json', model)
    with job_budget.bound_clip_job(1200):
        jobs._prefetch_packaging('isolated-project', items[:1], False, cache)
        pack = jobs._apply_packaging('isolated-project', items[0][1], 'douyin', False, cache)['packaging']
        job_budget.ensure_clip_job_budget()
    assert len(prompts) == 3 and prompts[:2] == [packaging.PROMPT] * 2
    assert pack['fallback'] and pack['fallback_captions'] == 'translated'
    assert pack['cues'][0]['text'] == '这是访谈字幕。'
    assert 'phase=structured' in caplog.text and 'elapsed_ms=' in caplog.text


def test_200_stalled_stream_recovers_a_full_package_on_same_endpoint(monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from backend.core import llm_usage
    from backend.core.llm_providers import OpenAIProvider

    requests = []
    stop = threading.Event()
    class Gateway(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((body['stream'], body['model']))
            self.send_response(200)
            if body['stream']:
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(b': ready\n\n')
                self.wfile.flush()
                stop.wait(4)
                return
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            result = {'title_lines': ['谈谈成长'], 'segments': [{'from': 0, 'to': 0, 'text': '我们从错误中学习。'}],
                      'tags': [{'line': 0, 'text': '从错误中学习'}], 'mood': 'serious'}
            data = {'id': 'test', 'object': 'chat.completion', 'created': 1, 'model': body['model'],
                    'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(result)}, 'finish_reason': 'stop'}]}
            self.wfile.write(json.dumps(data).encode())

    monkeypatch.setattr(packaging, 'FIRST_STRUCTURED_LIMIT_SEC', .7, raising=False)
    with ThreadingHTTPServer(('127.0.0.1', 0), Gateway) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        model = OpenAIProvider(api_key='fixture', model_name='qwen3.8-flash', base_url=f'http://127.0.0.1:{server.server_port}/v1')
        def ask(prompt, payload):
            return json.loads(model.call(prompt, payload).content)
        try:
            with llm_usage.stage('packaging'), job_budget.bound_clip_job(300):
                result = packaging.build_packaging({'title': 'A conversation'}, [{'start': .2, 'end': 20, 'text': 'We learn from mistakes.'}],
                    SimpleNamespace(template='interview_zh', audience_language='zh'), call=ask)
            assert result['fallback'] is False and result['title_lines'] == ['谈谈成长']
            assert result['cues'][0]['text'] == '我们从错误中学习。'
            assert result['mood'] == 'serious'
            assert requests == [(True, 'qwen3.8-flash'), (False, 'qwen3.8-flash')]
        finally:
            stop.set()
            server.shutdown()
            model.client.close()
            thread.join(timeout=2)
