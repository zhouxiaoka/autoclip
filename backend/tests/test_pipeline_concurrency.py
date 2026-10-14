"""Per-chunk model calls run side by side, keep chunk order, and stay sequential for local models."""
import threading
import time

import pytest

from backend.core import llm_usage
from backend.pipeline import concurrency


def test_chunks_run_in_parallel_and_keep_their_order(monkeypatch):
    concurrency.reset_limiter()
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    active, peak, lock = [0], [0], threading.Lock()

    def call(n):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return n * 10

    assert concurrency.map_chunks(call, range(8)) == [n * 10 for n in range(8)]
    assert peak[0] > 1


def test_usage_tracking_follows_each_chunk_call(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '3')
    monkeypatch.setattr(llm_usage, 'usage_path', lambda _p: tmp_path / llm_usage.FILE)
    with llm_usage.tracking('p1'):
        llm_usage.set_stage('outline')
        concurrency.map_chunks(lambda _n: llm_usage.record('qwen-plus', {'input_tokens': 5, 'output_tokens': 1},
                                                           prompt_chars=8, completion_chars=2), range(6))
    assert llm_usage.summary('p1')['stages']['outline']['calls'] == 6


def test_local_models_stay_sequential(monkeypatch):
    from backend.core import llm_manager

    class Manager:
        settings = {'llm_provider_preset': 'ollama', 'openai_base_url': 'http://localhost:11434/v1'}

    monkeypatch.delenv('AUTOCLIP_LLM_CONCURRENCY', raising=False)
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: Manager())
    assert concurrency.workers() == 1
    Manager.settings = {'llm_provider_preset': None, 'openai_base_url': ''}
    assert concurrency.workers() == concurrency.CLOUD_WORKERS


def test_rate_limit_halves_concurrency_down_to_one(monkeypatch):
    concurrency.reset_limiter()
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    assert concurrency.effective_workers() == 4
    concurrency.note_rate_limited()
    assert concurrency.effective_workers() == 2
    concurrency.note_rate_limited()
    assert concurrency.effective_workers() == 1
    concurrency.note_rate_limited()
    assert concurrency.effective_workers() == 1
    concurrency.reset_limiter()
    assert concurrency.effective_workers() == 4


def test_one_chunk_raising_does_not_cancel_siblings(monkeypatch):
    concurrency.reset_limiter()
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    started, finished, lock = [], [], threading.Lock()

    def call(n):
        with lock:
            started.append(n)
        time.sleep(0.05)
        if n == 1:
            raise RuntimeError('chunk 1')
        with lock:
            finished.append(n)
        return n

    with pytest.raises(RuntimeError, match='chunk 1'):
        concurrency.map_chunks(call, range(4))
    assert sorted(started) == [0, 1, 2, 3]
    assert sorted(finished) == [0, 2, 3]


def test_map_chunks_respects_halved_limit(monkeypatch):
    concurrency.reset_limiter()
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    concurrency.note_rate_limited()
    concurrency.note_rate_limited()
    active, peak, lock = [0], [0], threading.Lock()

    def call(n):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        time.sleep(0.03)
        with lock:
            active[0] -= 1
        return n

    assert concurrency.map_chunks(call, range(4)) == list(range(4))
    assert peak[0] == 1
    concurrency.reset_limiter()
