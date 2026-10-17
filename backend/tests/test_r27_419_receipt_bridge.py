"""R27 #378: the test bridge (receipt_bridge.py) must not manufacture a premise the real entry never has. The real
entry binds the plan only when screening hands over to production (jobs._inspect.start_automatic) and stamps outputs
only when production creates them, so a snapshot that failed in screening carries neither the stored plan's
mode/route/degrade_reason nor the workspace's output counts - whatever plan and outputs are lying around."""
import os

import pytest

from backend.tests import receipt_bridge

PLAN = {'id': 'p-old', 'mode': 'ai', 'recommended_analysis': 'visual', 'confirmed_analysis': 'visual',
        'degrade_reason': 'vision_unavailable_subtitle_fallback'}
OUTPUTS = [{'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'completed'},
           {'id': 'v2', 'draft_id': 'd2', 'strategy_id': 'douyin', 'status': 'failed'}]


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    from backend.services.studio import attempts, store
    monkeypatch.setattr(store, '_read_failures', {})
    monkeypatch.setattr(store, '_pending_links', {})
    monkeypatch.setattr(store, '_io_failures', {})
    def run(snapshot):
        out = receipt_bridge.materialize({'kind': 'generation', 'run_id': 'r1', 'seed': 's', 'snapshot': snapshot}, attempts, store)
        return next(a for a in out['attempts'] if a['attempt_id'] == out['attempt_id'])
    return run


def test_378_screening_failure_snapshot_gets_no_plan_or_outputs_from_the_bridge(bridge):
    receipt = bridge({'plan': PLAN, 'output_variants': OUTPUTS, 'drafts': [],
                      'generation': {'status': 'failed', 'error_code': 'provider_error', 'failure_stage': 'screening'},
                      'analysis': {'status': 'failed', 'phase': 'screening', 'error_code': 'provider_error'}})
    assert receipt['state'] == 'failed'
    for key in ('recommendation_mode', 'analysis_mode', 'route', 'variant_count', 'completed_variant_count'):
        assert key not in receipt['summary'], key
    assert 'degrade_reason' not in receipt


def test_378_production_snapshot_is_bound_and_owns_its_outputs_like_the_real_entry(bridge):
    receipt = bridge({'plan': PLAN, 'output_variants': OUTPUTS, 'drafts': [],
                      'generation': {'status': 'partial'}, 'analysis': {'status': 'completed', 'phase': 'production'}})
    assert receipt['state'] == 'partial' and receipt['degrade_reason'] == PLAN['degrade_reason']
    assert (receipt['summary']['recommendation_mode'], receipt['summary']['variant_count'], receipt['summary']['completed_variant_count']) == ('ai', 2, 1)
