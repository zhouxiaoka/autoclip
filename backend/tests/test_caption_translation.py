"""Translation recovery across provider, budget, cache and packaging boundaries."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import job_budget
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.services.studio import caption_translation as captions


def rows(count=10):
    return [{'start': float(i), 'end': float(i + 1), 'text': f'There are {i} useful ideas.'} for i in range(count)]


def response(_prompt, data):
    return {'lines': [{'id': r['id'], 'text': f"这里有{r['id']}个有用的想法。"} for r in data['lines']]}


def test_partial_cache_survives_a_batch_deadline_and_resumes_only_missing_rows(tmp_path, monkeypatch):
    now, calls = [100.], []
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    def timed(prompt, data):
        calls.append([r['id'] for r in data['lines']])
        if len(calls) == 2:
            now[0] += captions.BATCH_SECONDS + 1
            raise job_budget.JobDurationExceeded()
        return response(prompt, data)
    with job_budget.bound_clip_job(seconds=500):
        first = captions.translate(rows(), 'zh', call=timed, cache_dir=tmp_path, model_key='model-a')
        job_budget.ensure_clip_job_budget()
    assert set(first) == {0}
    assert len(list(tmp_path.glob('*.json'))) == 1
    assert captions.translate(rows(), 'zh', cache_dir=tmp_path, model_key='model-a', allow_model=False) == first
    def resumed(prompt, data):
        assert [r['id'] for r in data['lines']] == [len(resume_calls) + 1]
        resume_calls.append(data)
        return response(prompt, data)
    resume_calls = []
    final = captions.translate(rows(), 'zh', call=resumed, cache_dir=tmp_path, model_key='model-a')
    assert len(final) == 10 and all(final[i] == first[i] for i in first)
    cache = next(tmp_path.glob('*.json'))
    assert cache.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize('changed', ['model', 'audience', 'text', 'time', 'terms', 'policy'])
def test_cache_does_not_cross_translation_inputs(tmp_path, monkeypatch, changed):
    original = rows(1)
    assert captions.translate(original, 'zh', call=response, cache_dir=tmp_path, model_key='a')
    source, audience, terms, model = rows(1), 'zh', (), 'a'
    if changed == 'model': model = 'b'
    if changed == 'audience': audience = 'en'
    if changed == 'text': source[0]['text'] += ' Additional context.'
    if changed == 'time': source[0]['end'] += .2
    if changed == 'terms': terms = ('OpenAI',)
    if changed == 'policy': monkeypatch.setattr(captions, 'POLICY_VERSION', 999)
    assert captions.translate(source, audience, terms=terms, cache_dir=tmp_path, model_key=model, allow_model=False) == {}


def test_cached_content_is_revalidated_and_corruption_is_recoverable(tmp_path):
    source = rows(2)
    captions.translate(source, 'zh', call=response, cache_dir=tmp_path, model_key='a')
    cache = next(tmp_path.glob('*.json'))
    cache.write_text(json.dumps({'0': 'Untranslated original', '1': '这里有1个有用的想法。', '999': '无效行'}))
    assert captions.translate(source, 'zh', cache_dir=tmp_path, model_key='a', allow_model=False) == {1: '这里有1个有用的想法。'}
    cache.write_text('{broken')
    assert len(captions.translate(source, 'zh', call=response, cache_dir=tmp_path, model_key='a')) == 2


def test_cache_write_failure_keeps_valid_translation(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError('test only')
    monkeypatch.setattr(Path, 'mkdir', denied)
    assert captions.translate(rows(1), 'zh', call=response, cache_dir=tmp_path, model_key='a') == {0: '这里有0个有用的想法。'}


@pytest.mark.parametrize('error', [JobStopped, ProjectDeleted, ServiceRestarted, job_budget.JobDurationExceeded])
def test_control_signals_stop_new_calls_and_keep_earlier_batches(tmp_path, error):
    calls = []
    def call(prompt, data):
        calls.append(data)
        if len(calls) == 2:
            raise error()
        return response(prompt, data)
    with pytest.raises(error):
        captions.translate(rows(), 'zh', call=call, cache_dir=tmp_path, model_key='a')
    assert len(calls) == 2
    assert len(captions.translate(rows(), 'zh', cache_dir=tmp_path, model_key='a', allow_model=False)) == 1


def test_expired_parent_is_never_treated_as_optional_batch_timeout(monkeypatch):
    now = [100.]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    def slow(*args):
        now[0] += 6
        return {}
    with job_budget.bound_clip_job(seconds=5), pytest.raises(job_budget.JobDurationExceeded):
        captions.translate(rows(), 'zh', call=slow)


def test_transport_errors_do_not_trigger_format_retry():
    calls = []
    def unavailable(*args):
        calls.append(True)
        raise OSError('offline')
    assert captions.translate(rows(), 'zh', call=unavailable) == {}
    assert len(calls) == 1


def test_validation_preserves_names_figures_and_ids_but_accepts_independent_good_rows():
    source = [{'text': 'Fiji joined OpenAI in 2024.'}, {'text': 'A complete sentence.'}]
    for text in ['斐济在2024年加入OpenAI。', 'Fiji在2025年加入OpenAI。', 'Fiji joined OpenAI in 2024.']:
        raw = {'lines': [{'id': 0, 'text': text}, {'id': 1, 'text': '完整的一句话。'}]}
        assert captions._accepted(raw, {0, 1}, source, 'zh', ('Fiji', 'OpenAI')) == {1: '完整的一句话。'}
    raw = {'lines': [{'id': False, 'text': '错误行。'}, {'id': 0, 'text': 'Fiji在2024年加入OpenAI。'},
                     {'id': 1, 'text': '完整的一句话。'}, {'id': 1, 'text': '重复。'}]}
    assert captions._accepted(raw, {0, 1}, source, 'zh', ('Fiji', 'OpenAI')) == {0: 'Fiji在2024年加入OpenAI。'}


def test_token_limit_reaches_manager_through_real_text_json_and_client(monkeypatch):
    from backend.services.studio.intelligence import text_json
    from backend.utils import llm_client
    seen = []
    manager = SimpleNamespace(get_current_provider_info=lambda: {'available': True},
                              call=lambda *args, **kwargs: seen.append(kwargs) or '{"lines":[]}')
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: manager)
    assert text_json('prompt', {'lines': []}, max_tokens=1600) == {'lines': []}
    assert seen == [{'max_tokens': 1600}]


def test_real_request_adapter_binds_plain_translation_to_exactly_one_source_row(monkeypatch):
    from backend.utils import llm_client
    seen = []
    def call(prompt, data, **kwargs):
        seen.append((data, kwargs))
        return '这是第0个有用的想法。'
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=call))
    assert captions.translate(rows(1), 'zh') == {0: '这是第0个有用的想法。'}
    assert seen[0][0]['text'] == rows(1)[0]['text'] and 'lines' not in seen[0][0]
    assert 'context_before' not in seen[0][0] and 'context_after' not in seen[0][0]
    assert seen[0][1] == {'max_tokens': 600}


def test_neighbouring_facts_never_enter_the_translation_request(monkeypatch):
    from backend.utils import llm_client
    seen = []
    def call(prompt, data, **kwargs):
        seen.append(data)
        return '这家公司很有吸引力。' if len(seen) == 1 else '但创建它很困难。'
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=call))
    source = [{'text': 'This company is appealing.'}, {'text': 'But building it is difficult.'}]
    translated = captions.translate(source, 'zh')
    assert len(translated) == 2
    assert [p['text'] for p in seen] == [r['text'] for r in source]
    assert all(set(p) == {'text', 'protected_terms'} for p in seen)


def test_long_sentence_cannot_be_accepted_as_one_character_from_another_row():
    source = "Soon we are going to take over the world and become the next important company."
    assert captions._valid(source, '那', 'zh', ()) is None
    assert captions._valid('Our company is for everyone.', '我们的公司是为了 all', 'zh', ()) is None


@pytest.mark.parametrize('source,translation', [
    ('Building companies is cool fun', '创办公司既酷又有趣的.fun'),
    ('You can do amazing things', '你能做 amazing 的事情'),
    ('They want', '他们想要更长远的满足感，我认为这样会很好。'),
])
def test_foreign_words_and_context_expansion_do_not_count_as_translated_rows(source, translation):
    assert captions._valid(source, translation, 'zh', ()) is None


def test_source_acronyms_and_names_remain_readable_in_chinese():
    assert captions._valid('Sam builds AI tools for YC.', 'Sam为YC构建AI工具。', 'zh', ())


def test_repair_instruction_echo_is_rejected_instead_of_cached_as_translation(monkeypatch):
    from backend.utils import llm_client
    echo = '只补齐本批未通过校验的 ID；勿复述已成功译文，保留数字和专名。'
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=lambda *args, **kwargs: echo))
    source = [{'start': 0., 'end': 2., 'text': 'And maybe my highest advice'}]
    assert captions.translate(source, 'zh') == {}


def test_oversized_source_row_does_not_exhaust_a_request_or_truncate_a_translation():
    source = [{'start': 0., 'end': 10., 'text': 'words ' * 1000}]
    assert captions.translate(source, 'zh', call=lambda *_: pytest.fail('oversized source sent')) == {}


def test_model_cache_identity_uses_endpoint_and_controls_but_not_credentials(monkeypatch):
    from backend.core import llm_manager
    info = {'provider': 'test', 'backend_provider': 'openai', 'model': 'local', 'base_url': 'http://a/v1'}
    manager = SimpleNamespace(get_current_provider_info=lambda: info, settings={'temperature': .1, 'api_key': 'private'})
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)
    first = captions.model_fingerprint()
    manager.settings['api_key'] = 'rotated'
    assert captions.model_fingerprint() == first
    manager.settings['temperature'] = .5
    assert captions.model_fingerprint() != first
    manager.settings['temperature'] = .1
    info['base_url'] = 'http://b/v1'
    assert captions.model_fingerprint() != first
