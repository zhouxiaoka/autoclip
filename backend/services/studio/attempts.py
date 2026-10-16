"""Business attempts are owned by the backend (1.5.8 #419 rewrite, design-retro "Attempt 回执模型").

One AttemptReceipt per v4 success-rate attempt, persisted in the project's studio.json in the same atomic
write as the business state it describes:

    attempt_id, flow_id, sequence (strictly increasing per project), retry_of, kind, trigger, state,
    run_id, causes[{goal, stage, code, upstream, identity}], primary cause fields, summary, created_at, finished_at

Rules (invariants):
- Only this module creates attempts. Initial starts (auto import, manual confirm) and the single retry
  command (``begin_retry``) call ``open_attempt``; the frontend observer only projects receipts.
- Order is ``sequence``, never a wall-clock timestamp; it lives in the project state, so a restart or a
  cleared browser storage cannot change lineage.
- A retry's parent must be a failed/partial v4 attempt of the same project; retry_of and flow_id are copied
  from it here. One open attempt per project (serial retries): another analysis retry is refused, a second
  「重试这条」 joins the open variant-retry attempt. An idempotency key returns the same receipt.
- A receipt settles once (``reconcile`` in store.write): its causes are a structured list and its primary
  cause is chosen by backend.core.failure_attribution (catalog tiers, product first) - never 'multiple'.
- No user content: ids are random tokens, causes carry enums only.
"""
import uuid

from backend.services.studio.store import ConflictError

KINDS = ('generation', 'production')  # the two v4 terminals: studio_generation_finished / studio_production_finished
TERMINAL = ('completed', 'partial', 'failed')
RETRYABLE_PARENT = ('failed', 'partial')
KEEP = 100
SUMMARY_KEYS = ('provider', 'model', 'base_url_host', 'billable_calls_before_failure', 'retry_count', 'degrade_count',
                'llm_calls', 'prompt_tokens', 'completion_tokens', 'route', 'http_status', 'duration_ms',
                'requested_goals', 'succeeded_goals', 'failed_goals', 'result_count', 'completed_variant_count')


class RetryRejected(ConflictError):
    """The retry command refused: bad parent or another attempt is open. Nothing was created (HTTP 409)."""


def token() -> str:
    return 't-' + uuid.uuid4().hex


def receipts(data) -> list:
    value = data.get('attempts')
    if not isinstance(value, list):
        value = data['attempts'] = []
    return value


def find(data, attempt_id):
    return next((a for a in receipts(data) if a.get('attempt_id') == attempt_id), None) if attempt_id else None


def current(data):
    """The open attempt, if any (at most one per project)."""
    return next((a for a in reversed(receipts(data)) if a.get('state') == 'open'), None)


def unbound(receipt) -> bool:
    """A manual retry's production attempt waiting for confirmation: nothing runs for it yet, so a new retry
    replaces it (it is closed as 'abandoned' by open_attempt) instead of being blocked by it."""
    return bool(receipt) and receipt.get('kind') == 'production' and not receipt.get('run_id')


def open_attempt(data, kind, *, trigger='initial', parent=None, run_id=None, key=None, now=None):
    """Create the next attempt inside the caller's locked state change. An earlier open attempt that never
    reached a terminal is closed as 'abandoned' (not a v4 terminal) - there is only ever one open attempt."""
    assert kind in KINDS
    for item in receipts(data):
        if item.get('state') == 'open':
            item.update(state='abandoned', finished_at=now)
    sequence = int(data.get('attempt_sequence') or 0) + 1
    data['attempt_sequence'] = sequence
    attempt_id = token()
    receipt = {'attempt_id': attempt_id, 'flow_id': (parent or {}).get('flow_id') or token(), 'sequence': sequence,
               'retry_of': (parent or {}).get('attempt_id'), 'kind': kind, 'trigger': trigger, 'state': 'open',
               'run_id': run_id, 'causes': [], 'created_at': now}
    if key:
        receipt['idempotency_key'] = key
    receipts(data).append(receipt)
    del receipts(data)[:-KEEP]
    return receipt


def check_parent(data, parent_attempt_id):
    """Validate the retry's parent. None means "no known v4 attempt" (legacy project): no retry_of."""
    if not parent_attempt_id:
        return None
    parent = find(data, parent_attempt_id)
    if not parent or parent.get('kind') not in KINDS:
        raise RetryRejected('要重试的那次制作不存在')
    if parent.get('state') not in RETRYABLE_PARENT:
        raise RetryRejected('只有失败或部分完成的制作可以重试')
    newer = [a for a in receipts(data) if a.get('sequence', 0) > parent.get('sequence', 0) and (a.get('state') in TERMINAL or (a.get('state') == 'open' and not unbound(a)))]
    if newer:
        raise RetryRejected('这次制作已经重试过了')
    return parent


def by_key(data, key):
    return next((a for a in receipts(data) if key and a.get('idempotency_key') == key), None)


def bind_run(receipt, run_id):
    receipt['run_id'] = run_id


def _cause(record, goal=None):
    return {'goal': goal, 'stage': record.get('failure_stage') or '', 'code': record.get('error_code') or 'unexpected',
            'upstream': record.get('upstream_error_type') or '', 'identity': record.get('provider') or ''}


def causes_of(record) -> list:
    """Structured causes of a terminal record: the primary first, then the recorded secondaries."""
    if record.get('status') not in ('failed', 'partial') and record.get('outcome') not in ('failed', 'partial'):
        return []
    out = [_cause(record)]
    codes = record.get('secondary_error_codes') or []
    upstreams = record.get('secondary_upstream_error_types') or []
    stages = record.get('secondary_failure_stages') or []
    for index, code in enumerate(codes):
        out.append({'goal': None, 'stage': stages[index] if index < len(stages) else '', 'code': code or 'unexpected',
                    'upstream': upstreams[index] if index < len(upstreams) else '', 'identity': ''})
    return out


def settle(receipt, state, record, now=None):
    """Write the terminal once. Primary cause = failure_attribution over the structured causes."""
    from backend.core.failure_attribution import rank_failures
    causes = causes_of(record) if state in ('failed', 'partial') else []
    ranked = rank_failures([{'error_code': c['code'], 'upstream_error_type': c['upstream'], 'failure_stage': c['stage'], '_c': c} for c in causes])
    receipt.update(state=state, finished_at=now, causes=[r['_c'] for r in ranked])
    receipt['summary'] = {k: record[k] for k in SUMMARY_KEYS if k in record and record[k] is not None}
    if ranked:
        primary, others = ranked[0], ranked[1:]
        receipt.update(error_code=primary['error_code'], failure_stage=primary['failure_stage'] or None,
                       upstream_error_type=primary['upstream_error_type'] or None)
        if others:
            receipt['secondary_error_codes'] = [o['error_code'] for o in others]
            receipt['secondary_upstream_error_types'] = [o['upstream_error_type'] or '' for o in others]
            receipt['secondary_failure_stages'] = [o['failure_stage'] or '' for o in others]


def reconcile(data, now=None):
    """Called by store.write for every state write: settle the open attempt when its run reached a terminal."""
    receipt = current(data)
    if not receipt:
        return
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else {}
    analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else {}
    if receipt['kind'] == 'generation':
        if generation.get('attempt_id') != receipt['attempt_id'] or generation.get('status') not in TERMINAL:
            return
        record = {**{k: v for k, v in analysis.items() if k in SUMMARY_KEYS}, **generation}
        settle(receipt, generation['status'], record, now)
    elif receipt['kind'] == 'production':
        if not receipt.get('run_id') or analysis.get('run_id') != receipt['run_id'] or analysis.get('phase') != 'production' \
                or analysis.get('status') not in ('completed', 'failed'):
            return
        settle(receipt, analysis.get('outcome') if analysis.get('outcome') in TERMINAL else analysis['status'], analysis, now)


def public(receipt) -> dict:
    """What the API returns: the receipt without the idempotency key."""
    return {k: v for k, v in receipt.items() if k != 'idempotency_key'}
