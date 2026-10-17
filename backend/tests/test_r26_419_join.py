"""R25 #343/#344: a second 「重试这条」 joining the open variant-retry attempt goes through the same parent check and
idempotency registration as the first request."""
import pytest

from backend.services.studio import attempts, jobs
from backend.tests import attempt_flow as flow


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    return flow.setup_env(tmp_path, monkeypatch)


def _partial(pid):
    flow.auto_import(pid)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('failed', 'timeout', None), 'bad2': ('failed', 'timeout', None)})
    return flow.receipts(pid)[0]


def test_343_joined_request_replayed_after_failure_creates_no_new_attempt(env):
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1')
    flow.retry_variant(pid, 'bad2', 'c2')  # joins
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('failed', 'timeout', None), 'bad2': ('failed', 'timeout', None)})
    dispatched = env.count('_dispatch_pending_variants')
    replay = flow.retry_variant(pid, 'bad2', 'c2')  # the joined click re-sent (network retry) after the attempt failed
    assert len(flow.receipts(pid)) == 2 and replay['attempt']['attempt_id'] == flow.receipts(pid)[1]['attempt_id']
    assert env.count('_dispatch_pending_variants') == dispatched  # not dispatched again


def test_344_join_with_unknown_parent_is_rejected():
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1')
    with pytest.raises(attempts.RetryRejected):
        jobs.retry_variant(pid, 'bad2', {'key': 'c2', 'parent_attempt_id': 't-doesnotexist00'})
    assert attempts.by_key(flow.store.read(pid), 'c2') is None


def test_344_join_naming_another_parent_is_rejected_but_the_right_one_joins():
    pid = flow.new_project(); parent = _partial(pid)
    first = flow.retry_variant(pid, 'bad1', 'c1')['attempt']
    with pytest.raises(attempts.RetryRejected):  # the open attempt itself is not a retryable parent
        jobs.retry_variant(pid, 'bad2', {'key': 'c2', 'parent_attempt_id': first['attempt_id']})
    jobs.retry_variant(pid, 'bad2', {'key': 'c3', 'parent_attempt_id': parent['attempt_id']})
    assert len(flow.receipts(pid)) == 2


def test_joined_key_is_not_in_the_public_receipt():
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1'); flow.retry_variant(pid, 'bad2', 'c2')
    assert all('joined_keys' not in r for r in flow.workspace(pid)['attempts'])
