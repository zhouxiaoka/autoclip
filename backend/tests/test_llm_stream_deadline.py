"""A deadline must wake an SDK read, not merely close its handle in another thread."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.core import job_budget, llm_stream
from backend.core.llm_providers import OpenAIProvider


def test_abort_never_shuts_down_a_shared_http2_connection():
    calls = []
    class Network:
        def get_extra_info(self, name):
            calls.append('shared connection touched')
            return None
    class Response:
        extensions = {'http_version': b'HTTP/2', 'network_stream': Network()}
        def close(self):
            calls.append('close')
    llm_stream._abort_stream(Response())
    assert calls == ['close']


def test_deadline_eof_does_not_accept_partial_sse():
    def lines():
        yield 'data: {"choices":[{"delta":{"content":"partial"}}]}'
        yield ''
        job_budget._current.get().seconds = 0
        yield 'data: [DONE]'
        yield ''
    with job_budget.bound_clip_job(10), pytest.raises(job_budget.JobDurationExceeded):
        llm_stream.collect_sse(lines())


def test_deadline_interrupts_a_blocked_real_httpx_sdk_read(monkeypatch, caplog):
    consumed = threading.Event()
    release = threading.Event()
    original_note = llm_stream._note
    def note(state, **kwargs):
        original_note(state, **kwargs)
        if kwargs.get('chars'):
            consumed.set()
    monkeypatch.setattr(llm_stream, '_note', note)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            chunk = {'choices': [{'index': 0, 'delta': {'content': 'partial'}, 'finish_reason': None}]}
            try:
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
                self.wfile.flush()
                release.wait(8)
                self.wfile.write(b'data: [DONE]\n\n')
                self.wfile.flush()
            except OSError:
                pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = OpenAIProvider(api_key='local-fixture', model_name='fixture', base_url=f'http://127.0.0.1:{server.server_port}/v1')
    budgets = []
    def request():
        with job_budget.bound_clip_job(30), job_budget.clip_step_budget(10):
            budgets.append(job_budget._current.get())
            return provider.call('fixture')
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(request)
            try:
                assert consumed.wait(3)
                time.sleep(.05)  # SDK has consumed a chunk and is waiting for the next one.
                budgets[0].seconds = 0
                try:
                    pending.result(timeout=1.5)
                except FutureTimeout:
                    pytest.fail('expired stream stayed blocked on the old socket read timeout')
                except job_budget.JobDurationExceeded:
                    assert 'phase=response_body http_status=200' in caplog.text
                    assert 'abort=socket_shutdown' in caplog.text
                else:
                    pytest.fail('deadline returned an incomplete response as success')
            finally:
                release.set()
    finally:
        server.shutdown()
        server.server_close()
        provider.client.close()
        thread.join(timeout=2)


def test_packaging_wait_for_headers_spends_only_one_sdk_attempt(caplog):
    from backend.core import llm_usage
    seen = []
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            seen.append(True)
            release.wait(5)

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        provider = OpenAIProvider(api_key='local-fixture', model_name='fixture',
                                  base_url=f'http://127.0.0.1:{server.server_port}/v1')
        try:
            with llm_usage.stage('packaging'), job_budget.bound_clip_job(.4), pytest.raises(job_budget.JobDurationExceeded):
                provider.call('private fixture words')
            assert seen == [True]
            assert 'phase=open_stream' in caplog.text
            assert 'private fixture words' not in caplog.text
        finally:
            release.set()
            server.shutdown()
            provider.client.close()
            thread.join(timeout=2)
