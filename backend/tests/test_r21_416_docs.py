"""R21 #204/#205 for #416: the tracking plan must not claim the live dashboard already shows NULL as
empty, and must state the retry_of dependency on #419. Both fail on 9d58ff1f."""
from pathlib import Path

PLAN = (Path(__file__).resolve().parents[2] / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')


def test_204_dashboard_null_claim_waits_for_the_post_merge_sync():
    assert '看板显示为空' not in PLAN
    assert '合入后同步' in PLAN


def test_205_retry_of_dependency_on_419_is_documented():
    assert '#419' in PLAN and '同批合入' in PLAN
