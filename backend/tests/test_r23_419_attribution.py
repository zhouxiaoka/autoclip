"""R23 #228/#229 for #419.

#228 (PM rule): a multi-goal failure is a product failure as soon as one cause is a product cause; it
leaves a denominator only when every cause is a user cause for it. The primary cause is the first failure
of the most product-like tier, the rest go along as secondary causes. Checked end to end: real
_produce_selected -> analysis record -> the real success_rate.sql. Fails on 1a518570 (order decided).
#229: one SQL adapter for every success-rate test."""
from pathlib import Path

import pytest

from backend.services.studio import jobs, intelligence
from backend.tests.test_r18_cloud_asr_failure import _asr_401, _on_disk, _real_store_jobs

pytest.importorskip('duckdb')
from backend.tests.success_rate_sql import figure, run_sql  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WINDOW = {'date_from': "'2026-10-01 00:00:00'", 'date_to': "'2026-11-01 00:00:00'", 'internal_cohort_id': '641509'}


def _produce(monkeypatch, tmp_path, goals, visual_error):
    store = _real_store_jobs(monkeypatch, {'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-m'}}, tmp_path)
    def asr_fails(*a, **k):
        raise _asr_401()                       # content goal: speech key rejected -> authentication / invalid_key
    def vision_fails(*a, **k):
        raise visual_error                     # highlight goal (visual)
    monkeypatch.setattr(jobs, 'run_content', asr_fails)
    monkeypatch.setattr(jobs, 'analyze', vision_fails)
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    jobs._produce_selected('p', {'selected_goals': goals, 'confirmed_preferences': {}, 'confirmed_analysis': 'visual'})
    return _on_disk(store)['analysis']


def _denominators(analysis):
    from datetime import datetime
    props = {'attempt_id': 't-aaaaaaaaaaaa', 'flow_id': 't-ffffffffffff', 'outcome': 'error',
             'error_code': analysis.get('error_code'), 'upstream_error_type': analysis.get('upstream_error_type'),
             'failure_stage': analysis.get('failure_stage'), 'app_version': '1.5.8',
             'analytics_environment': 'production', 'runtime': 'desktop'}
    [row] = run_sql(figure(1, params=WINDOW), [('u1', 'studio_production_finished', 'person-1', datetime(2026, 10, 10, 10), props)])
    return row['q_all'], row['q_prod']


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_228_auth_plus_visual_timeout_is_a_product_failure_whatever_the_goal_order(monkeypatch, tmp_path, goals):
    a = _produce(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    assert a['status'] == 'failed' and sorted(a['failed_goals']) == ['content', 'highlight']
    assert a['error_code'] == 'timeout' and a['failure_stage'] == 'vision', a
    assert a.get('upstream_error_type') != 'invalid_key'
    assert a['secondary_error_codes'] == ['authentication'] and a['secondary_upstream_error_types'] == ['invalid_key']
    assert _denominators(a) == (1, 1)          # counted in both denominators (was 0 with content first)


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_228_all_user_causes_leave_the_product_denominator_only(monkeypatch, tmp_path, goals):
    """auth (user_hard) + vision connection (user_x): every cause is a user cause for the product view;
    the full view still counts it because connection is not a hard user cause."""
    a = _produce(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('connection', '视觉模型连接失败'))
    assert a['error_code'] == 'connection' and a['secondary_error_codes'] == ['authentication'], a
    assert _denominators(a) == (1, 0)


def test_228_same_tier_keeps_the_first_failure_and_lists_the_rest():
    from backend.core.failure_attribution import rank_failures
    ranked = rank_failures([{'error_code': 'authentication'}, {'error_code': 'timeout'}, {'error_code': 'render'},
                            {'error_code': 'connection'}])
    assert [f['error_code'] for f in ranked] == ['timeout', 'render', 'connection', 'authentication']


def test_228_tiers_are_the_ones_the_sql_uses():
    """Same priority on both sides: the tiers come from the catalog the SQL is pinned to (test_llm_auth_invalid_e2e)."""
    import re
    from backend.core.failure_attribution import USER_HARD, USER_X, cause_tier
    sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    hard = set(re.findall(r"'(\w+)'", re.search(r"OR ec IN \(([^)]*)\)\s*OR ue IN", sql).group(1)))
    hard_ue = set(re.findall(r"'(\w+)'", re.search(r"OR ue IN \(([^)]*)\)\) AS user_hard", sql).group(1)))
    extra = set(re.findall(r"'(\w+)'", re.search(r"user_hard OR ec IN \(([^)]*)\)\) AS user_x", sql).group(1)))
    assert all(cause_tier({'error_code': c}) == USER_HARD for c in hard)
    assert all(cause_tier({'error_code': 'timeout', 'upstream_error_type': u}) == USER_HARD for u in hard_ue)
    assert all(cause_tier({'error_code': c}) == USER_X for c in extra)
    assert cause_tier({'error_code': 'timeout'}) == 0


def test_229_one_sql_adapter():
    tests = ROOT / 'backend' / 'tests'
    users = [p for p in tests.glob('test_*.py') if p.name != Path(__file__).name and 'success_rate.sql' in p.read_text(encoding='utf-8') and 'duckdb' in p.read_text(encoding='utf-8')]
    assert users, 'no SQL test found'
    for p in users + [tests / 'success_rate_sql.py']:
        text = p.read_text(encoding='utf-8')
        assert 'sqlglot' not in text, f'{p.name}: second SQL adapter'
        if p.name != 'success_rate_sql.py':
            assert 'backend.tests.success_rate_sql import' in text, f'{p.name} must use the shared adapter'
            assert 'def to_duckdb' not in text and 'CREATE MACRO' not in text, f'{p.name}: own adapter'


@pytest.mark.parametrize('goals', [['content', 'highlight'], ['highlight', 'content']])
def test_r24_page_gets_the_user_cause_stage_while_event_primary_stays_product(monkeypatch, tmp_path, goals):
    """R24 PM rule: page and stats are separate. The record keeps the product primary (timeout/vision) for the
    event, and carries each secondary cause's stage so the page can send 「去设置」 to the right row."""
    a = _produce(monkeypatch, tmp_path, goals, intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    assert a['error_code'] == 'timeout' and a['failure_stage'] == 'vision'
    assert a['secondary_error_codes'] == ['authentication'] and a['secondary_upstream_error_types'] == ['invalid_key']
    assert a['secondary_failure_stages'] == ['subtitle'], a


def test_267_history_row_keeps_the_secondary_causes(monkeypatch, tmp_path):
    """R24 #267: the analysis_history allow-list kept error_code but dropped the secondary causes."""
    _produce(monkeypatch, tmp_path, ['content', 'highlight'], intelligence.VisionRequestError('timeout', '视觉模型请求超时'))
    from backend.services.studio import store as s
    data = _on_disk(s)
    [row] = [r for r in data['analysis_history'] if r['run_id'] == 'run-m']
    assert row['analysis']['error_code'] == 'timeout'
    assert row['analysis']['secondary_error_codes'] == ['authentication'], row
    assert row['analysis']['secondary_upstream_error_types'] == ['invalid_key']
