"""R21 #204/#205 for #416: the tracking plan must not claim the live dashboard already shows NULL as
empty, and must state the retry_of dependency on #419. Both fail on 9d58ff1f."""
from pathlib import Path

PLAN = (Path(__file__).resolve().parents[2] / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')


def test_204_dashboard_null_claim_waits_for_the_post_merge_sync():
    assert '看板显示为空' not in PLAN
    assert '合入后同步' in PLAN


def test_205_416_can_merge_without_419_producer():
    """#416's SQL is valid when retry_of is absent. #419 is what emits it; they do not have to merge together."""
    assert '#419' in PLAN and '#416' in PLAN
    assert '可以单独合入' in PLAN
    assert '同批合入' not in PLAN


def test_225_sql_header_does_not_claim_live_dashboard_is_aligned():
    """R22 #225: the live insights are synced only after #416/#419 merge, so line 1 must not say they
    already match. Fails on 101deaf4."""
    sql = (Path(__file__).resolve().parents[2] / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    header = sql.splitlines()[0]
    assert '对齐' not in header
    assert '合入后同步' in header
