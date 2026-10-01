"""Token usage is recorded per project and stage, including worker threads (no model calls)."""
from concurrent.futures import ThreadPoolExecutor

from backend.core import llm_usage


def test_usage_is_recorded_per_stage_and_summarised(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_usage, 'usage_path', lambda project_id: tmp_path / project_id / 'metadata' / llm_usage.FILE)
    llm_usage.record('qwen-plus', {'input_tokens': 10}, prompt_chars=30, completion_chars=3)  # no sink: ignored
    with llm_usage.tracking('p1'):
        with llm_usage.stage('packaging'):
            llm_usage.record('qwen-plus', {'input_tokens': 1200, 'output_tokens': 300}, prompt_chars=2000, completion_chars=500)
        llm_usage.set_stage('outline')
        llm_usage.record('qwen-plus', None, prompt_chars=1500, completion_chars=150)  # provider without usage
        with ThreadPoolExecutor(max_workers=2) as pool:
            with llm_usage.stage('boundaries'):
                record = llm_usage.run_in_context(lambda: llm_usage.record('qwen-plus', {'prompt_tokens': 50, 'completion_tokens': 5},
                                                                           prompt_chars=80, completion_chars=8))
            list(pool.map(lambda _: record(), range(2)))
    result = llm_usage.summary('p1')
    assert result['stages']['packaging'] == {'calls': 1, 'prompt_tokens': 1200, 'completion_tokens': 300, 'estimated_calls': 0}
    assert result['stages']['outline'] == {'calls': 1, 'prompt_tokens': 1000, 'completion_tokens': 100, 'estimated_calls': 1}
    assert result['stages']['boundaries']['calls'] == 2
    assert result['total']['calls'] == 4


def test_manager_calls_record_provider_usage(monkeypatch, tmp_path):
    from backend.core import llm_manager
    from backend.core.llm_providers import LLMResponse

    class Provider:
        model_name = 'qwen-plus'

        def _build_full_input(self, prompt, data):
            return prompt + str(data)

        def call(self, prompt, data, **_):
            return LLMResponse(content='{"ok": true}', usage={'input_tokens': 42, 'output_tokens': 7}, model='qwen-plus')

    manager = llm_manager.LLMManager.__new__(llm_manager.LLMManager)
    manager.current_provider = Provider()
    monkeypatch.setattr(manager, '_reload_if_settings_changed', lambda: None, raising=False)
    monkeypatch.setattr(llm_manager, '_llm_cache_path', lambda *_: None)
    monkeypatch.setattr(llm_usage, 'usage_path', lambda project_id: tmp_path / llm_usage.FILE)
    with llm_usage.tracking('p1'), llm_usage.stage('scoring'):
        assert manager.call('score', {'x': 1}) == '{"ok": true}'
    assert llm_usage.summary('p1')['stages']['scoring']['prompt_tokens'] == 42


def test_stage_timings_add_up_and_do_not_count_as_model_calls(monkeypatch, tmp_path):
    clock = iter([10.0, 12.5, 20.0, 21.0])
    monkeypatch.setattr(llm_usage.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(llm_usage, 'usage_path', lambda _p: tmp_path / llm_usage.FILE)
    with llm_usage.tracking('p1'):
        for _ in range(2):
            with llm_usage.timed('render'):
                pass
    assert llm_usage.timings('p1') == {'render': 3.5}
    assert llm_usage.summary('p1')['total']['calls'] == 0
