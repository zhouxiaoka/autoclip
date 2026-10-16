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
PLAN_KEYS = ('recommendation_mode', 'analysis_mode', 'route')  # frozen from the attempt's own plan
OUTPUT_FREE = ('platform_count', 'portrait_style', 'brand_outro_enabled', 'recommended_template', 'accepted_recommendation', 'burned_captions')
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
    return next((a for a in receipts(data) if key and (a.get('idempotency_key') == key or key in (a.get('joined_keys') or ()))), None)


def check_join(data, receipt, parent_attempt_id, key=None):
    """R25 #343/#344: a request joining the open attempt passes the same parent check as the first one (the parent
    must exist, be a v4 attempt, and be the one the open attempt retries) and registers its own idempotency key,
    so replaying it after the attempt settled returns this receipt instead of creating another attempt."""
    if parent_attempt_id:
        parent = find(data, parent_attempt_id)
        if not parent or parent.get('kind') not in KINDS:
            raise RetryRejected('要重试的那次制作不存在')
        if parent_attempt_id != receipt.get('retry_of'):
            raise RetryRejected('这次制作已经重试过了')
    if key and key != receipt.get('idempotency_key') and key not in (receipt.get('joined_keys') or []):
        receipt.setdefault('joined_keys', []).append(key)
    return receipt


def bind_run(receipt, run_id):
    receipt['run_id'] = run_id


def inherit_plan(receipt, parent):
    """R26 #364: a variant retry re-renders outputs of the parent attempt, so it belongs to the plan that produced
    them (the parent's), not whatever plan the workspace holds now. The parent's frozen enums go along in case that
    plan has been replaced by a re-screen since."""
    if receipt is None or not parent:
        return
    if parent.get('plan_id'):
        receipt['plan_id'] = parent['plan_id']
    summary = parent.get('summary') or {}
    inherited = {k: v for k, v in (('degrade_reason', parent.get('degrade_reason') or (parent.get('inherited') or {}).get('degrade_reason')),
                                   *((k, summary.get(k)) for k in PLAN_KEYS)) if isinstance(v, str) and v}
    if inherited:
        receipt['inherited'] = inherited


def bind_plan(receipt, plan):
    """R25 #348: the plan this attempt actually runs (auto: written when screening starts production; manual: the
    confirmed one). Only a bound plan's degrade_reason is frozen at settle - an attempt that fails before its own
    plan exists must not inherit the previous plan's reason."""
    if receipt is not None and isinstance(plan, dict) and plan.get('id'):
        receipt['plan_id'] = plan['id']


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


DEGRADE_REASONS = ('vision_unavailable_subtitle_fallback', 'vision_invalid_subtitle_fallback',
                   'frame_extract_subtitle_fallback', 'source_too_long_subtitle_route')  # catalog enums.degrade_reason


def settle(receipt, state, record, now=None, plan=None, base=None):
    """Write the terminal once. Primary cause = failure_attribution over the structured causes. The degrade
    reason is frozen from this attempt's own plan (enum only), so a later re-screen cannot change it."""
    from backend.core.failure_attribution import rank_failures
    causes = causes_of(record) if state in ('failed', 'partial') else []
    ranked = rank_failures([{'error_code': c['code'], 'upstream_error_type': c['upstream'], 'failure_stage': c['stage'], '_c': c} for c in causes])
    receipt.update(state=state, finished_at=now, causes=[r['_c'] for r in ranked])
    own = plan if isinstance(plan, dict) and plan.get('id') and plan.get('id') == receipt.get('plan_id') else {}
    # R25 #345/#347: everything the terminal event projects is frozen here - the frontend never mixes in the live
    # workspace or plan for a receipt (a historical receipt must not borrow the current state's numbers).
    receipt['summary'] = {**(base or {}), **{k: record[k] for k in SUMMARY_KEYS if k in record and record[k] is not None}}
    for key, value in (('recommendation_mode', own.get('mode')), ('analysis_mode', own.get('confirmed_analysis'))):
        if isinstance(value, str) and value:
            receipt['summary'][key] = value
    if receipt.get('kind') == 'generation' and not receipt['summary'].get('route') and isinstance(own.get('recommended_analysis'), str):
        receipt['summary']['route'] = own['recommended_analysis']
    for key, value in (receipt.get('inherited') or {}).items():  # R26 #364: the source plan, when it is not current
        if key in PLAN_KEYS and not own:
            receipt['summary'].setdefault(key, value)
    reason = own.get('degrade_reason') if own else (receipt.get('inherited') or {}).get('degrade_reason')
    if reason in DEGRADE_REASONS:
        receipt['degrade_reason'] = reason
    if ranked:
        primary, others = ranked[0], ranked[1:]
        receipt.update(error_code=primary['error_code'], failure_stage=primary['failure_stage'] or None,
                       upstream_error_type=primary['upstream_error_type'] or None)
        if others:
            receipt['secondary_error_codes'] = [o['error_code'] for o in others]
            receipt['secondary_upstream_error_types'] = [o['upstream_error_type'] or '' for o in others]
            receipt['secondary_failure_stages'] = [o['failure_stage'] or '' for o in others]


def _millis(value):
    from datetime import datetime, timezone
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return round((parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp() * 1000)


def generation_summary(data) -> dict:
    """R25 #347: the generation terminal's counts, frozen in the receipt at settle from THIS attempt's workspace
    (same rules as frontend generationSummary, which it replaces for the terminal). Counts and enums only."""
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else {}
    all_variants = [v for v in data.get('output_variants') or [] if isinstance(v, dict)]
    variants = [v for v in all_variants if v.get('status') != 'on_demand']
    templates = {d.get('id'): d.get('packaging') for d in data.get('drafts') or [] if isinstance(d, dict)}
    packaged = [templates.get(v.get('draft_id')) for v in variants if templates.get(v.get('draft_id'))]
    jobs = {j.get('job_id'): j for j in data.get('jobs') or [] if isinstance(j, dict)}
    def report(v):
        return ((jobs.get(v.get('render_job_id') or '') or {}).get('result') or {}).get('template_render')
    def classic(v):
        r = report(v)
        if r:
            return r.get('downgraded') is True or r.get('template') == 'classic'
        return (templates.get(v.get('draft_id')) or {}).get('template') in ('interview_zh', 'podcast_en')
    completed = [(v, jobs.get(v.get('render_job_id') or '')) for v in variants if v.get('status') == 'completed']
    count = lambda test: sum(1 for v in variants if test(v))
    created, finished = _millis(generation.get('created_at')), _millis(generation.get('finished_at'))
    branding = generation.get('branding') if isinstance(generation.get('branding'), dict) else {}
    out = {
        'variant_count': len(all_variants),
        'completed_variant_count': count(lambda v: v.get('status') == 'completed'),
        'failed_variant_count': count(lambda v: v.get('status') == 'failed'),
        'on_demand_variant_count': len(all_variants) - len(variants),
        'skipped_variant_count': len(generation['skipped']) if isinstance(generation.get('skipped'), list) else 0,
        'platform_count': len(generation.get('requested_platforms') or []),
        'interview_count': sum(1 for p in packaged if p.get('template') == 'interview_zh'),
        'podcast_count': sum(1 for p in packaged if p.get('template') == 'podcast_en'),
        'landscape_count': len(variants) - len(packaged),
        'editorial_count': count(lambda v: (report(v) or {}).get('template') == 'editorial' and (report(v) or {}).get('downgraded') is not True),
        'street_count': count(lambda v: (report(v) or {}).get('template') == 'street' and (report(v) or {}).get('downgraded') is not True),
        'classic_count': count(classic),
        'html_downgrade_count': count(lambda v: (report(v) or {}).get('downgraded') is True),
        'speaker_framed_count': count(lambda v: v.get('framing') == 'speaker'),
        'full_frame_count': count(lambda v: v.get('framing') == 'full_frame'),
        'framing_pending_count': count(lambda v: v.get('framing') == 'full_frame_pending'),
        'framing_captions_count': count(lambda v: v.get('framing') == 'full_frame_captions'),
        'portrait_style': generation.get('portrait_style'),
        'brand_outro_enabled': branding.get('outro_enabled'),
        'outro_applied_count': sum(1 for _v, j in completed if ((j or {}).get('result') or {}).get('outro_applied') is True),
        'outro_fallback_count': sum(1 for v, j in completed if ((j or {}).get('brand_outro') if (j or {}).get('brand_outro') is not None else (v.get('branding') or {}).get('outro_enabled')) is True
                                    and ((j or {}).get('result') or {}).get('outro_applied') is False),
        'outro_unknown_count': sum(1 for _v, j in completed if not isinstance(((j or {}).get('result') or {}).get('outro_applied'), bool)),
        'packaging_fallback_count': sum(1 for p in packaged if p.get('fallback')),
        'trimmed_count': count(lambda v: bool(v.get('trimmed_to_sec'))),
        'burned_captions': bool(generation.get('source_has_burned_subtitles')),
        'duration_ms': max(0, finished - created) if created is not None and finished is not None else None,
    }
    if generation.get('recommended_template'):
        out['recommended_template'] = generation['recommended_template']
    if isinstance(generation.get('accepted_recommendation'), bool):
        out['accepted_recommendation'] = generation['accepted_recommendation']
    return {k: v for k, v in out.items() if v is not None}


def _owned_summary(receipt, data):
    """R26 #363: output counts belong to this attempt only once it has its own (or inherited) plan, i.e. it reached
    production; an attempt that failed before that keeps the request fields but not the previous run's outputs."""
    summary = generation_summary(data)
    return summary if receipt.get('plan_id') else {k: v for k, v in summary.items() if k in OUTPUT_FREE}


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
        settle(receipt, generation['status'], record, now, data.get('plan') if isinstance(data.get('plan'), dict) else None,
               base=_owned_summary(receipt, data))
    elif receipt['kind'] == 'production':
        if not receipt.get('run_id') or analysis.get('run_id') != receipt['run_id'] or analysis.get('phase') != 'production' \
                or analysis.get('status') not in ('completed', 'failed'):
            return
        settle(receipt, analysis.get('outcome') if analysis.get('outcome') in TERMINAL else analysis['status'], analysis, now,
               data.get('plan') if isinstance(data.get('plan'), dict) else None)


def public(receipt) -> dict:
    """What the API returns: the receipt without the idempotency key."""
    return {k: v for k, v in receipt.items() if k not in ('idempotency_key', 'joined_keys', 'plan_id', 'inherited')}
