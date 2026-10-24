"""Business attempts are owned by the backend (1.5.7 #419 rewrite, design-retro "Attempt 回执模型").

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
SUMMARY_KEYS = ('provider', 'config_source', 'attribution_source', 'model', 'base_url_host', 'shutdown_kind',
                'billable_calls_before_failure', 'retry_count', 'degrade_count',
                'llm_calls', 'prompt_tokens', 'completion_tokens', 'route', 'http_status', 'duration_ms',
                'requested_goals', 'succeeded_goals', 'failed_goals', 'result_count', 'completed_variant_count')


class RetryRejected(ConflictError):
    """The retry command refused: bad parent or another attempt is open. Nothing was created (HTTP 409)."""


class AppendRejected(RetryRejected):
    """1.5.7 does not append platforms. The refusal carries an error_code the API returns as HTTP 409.
    Nothing is created."""

    def __init__(self, message, error_code, status=409):
        super().__init__(message)
        self.error_code, self.status = error_code, status


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
    """/#344: a request joining the open attempt passes the same parent check as the first one (the parent
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


def own_outputs(data, variants):
    """/#377: output ownership is stored, not inferred. Each output is stamped, when it is created, with the
    open attempt that produced it and that attempt's bound plan. Receipts count and inherit from these stamps only.
    Without an open attempt nothing is stamped. Already stamped outputs are never re-stamped."""
    receipt = current(data)
    if not receipt:
        return
    for variant in variants:
        if variant.get('produced_by_attempt'):
            continue
        variant['produced_by_attempt'] = receipt['attempt_id']
        if receipt.get('plan_id'):
            variant['produced_by_plan'] = receipt['plan_id']


def own_drafts(data, drafts):
    """drafts a manual confirmation creates are owned by the open (production) attempt, stored when they
    are written - same rule as own_outputs. The stamp lives in the attempt record (draft_ids): the Draft schema is
    closed (extra='forbid') and drafts are copied into derived drafts, which must not inherit another run's stamp."""
    receipt = current(data)
    if not receipt:
        return
    ids = receipt.setdefault('draft_ids', [])
    ids.extend(d['id'] for d in drafts if isinstance(d, dict) and d.get('id') and d['id'] not in ids)


def inherit_plan(receipt, data, variant):
    """/ a variant retry re-renders an output, so it belongs to the plan that produced that
    output (the variant's own stamp) and reports the outputs of the attempt that produced it - not the retry
    parent, which is just the latest failure (a re-screen may have failed in between). The source attempt's frozen
    enums go along in case its plan has been replaced since. A joined retry adds its variant's producer."""
    if receipt is None or not isinstance(variant, dict) or not variant.get('produced_by_attempt'):
        return
    sources = receipt.setdefault('sources', [])
    if variant['produced_by_attempt'] in sources:
        return
    sources.append(variant['produced_by_attempt'])
    if len(sources) > 1:
        return  # the first retried output decides the plan of this aggregate attempt
    _inherit_source(receipt, data, variant)


def _inherit_source(receipt, data, variant):
    """The source output's plan and its attempt's frozen enums (degrade_reason, PLAN_KEYS incl. route)."""
    if variant.get('produced_by_plan'):
        receipt['plan_id'] = variant['produced_by_plan']
    source = find(data, variant['produced_by_attempt']) or {}
    summary = source.get('summary') or {}
    inherited = {k: v for k, v in (('degrade_reason', source.get('degrade_reason') or (source.get('inherited') or {}).get('degrade_reason')),
                                   *((k, summary.get(k)) for k in PLAN_KEYS)) if isinstance(v, str) and v}
    if inherited:
        receipt['inherited'] = inherited


def bind_plan(receipt, plan):
    """the plan this attempt actually runs (auto: written when screening starts production; manual: the
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
    receipt.pop('input', None)  # an append's frozen input is only needed while it runs
    own = plan if isinstance(plan, dict) and plan.get('id') and plan.get('id') == receipt.get('plan_id') else {}
    # /#347: everything the terminal event projects is frozen here - the frontend never mixes in the live
    # workspace or plan for a receipt (a historical receipt must not borrow the current state's numbers).
    receipt['summary'] = {**(base or {}), **{k: record[k] for k in SUMMARY_KEYS if k in record and record[k] is not None}}
    for key, value in (('recommendation_mode', own.get('mode')), ('analysis_mode', own.get('confirmed_analysis'))):
        if isinstance(value, str) and value:
            receipt['summary'][key] = value
    if receipt.get('kind') == 'generation' and not receipt['summary'].get('route') and isinstance(own.get('recommended_analysis'), str):
        receipt['summary']['route'] = own['recommended_analysis']
    for key, value in (receipt.get('inherited') or {}).items():  # the source plan, when it is not current
        if key in PLAN_KEYS and not own:
            receipt['summary'][key] = value  # the source output's plan wins over the live workspace route
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


def generation_summary(data, variants=None, started=None) -> dict:
    """the generation terminal's counts, frozen in the receipt at settle from THIS attempt's workspace
    (same rules as frontend generationSummary, which it replaces for the terminal). Counts and enums only."""
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else {}
    all_variants = [v for v in (data.get('output_variants') or [] if variants is None else variants) if isinstance(v, dict)]
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
    # duration_ms runs from THIS attempt's start (an appended round never includes earlier rounds)
    created, finished = _millis(started) or _millis(generation.get('created_at')), _millis(generation.get('finished_at'))
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
        'news_count': count(lambda v: (report(v) or {}).get('template') == 'news' and (report(v) or {}).get('downgraded') is not True),
        'cinema_count': count(lambda v: (report(v) or {}).get('template') == 'cinema' and (report(v) or {}).get('downgraded') is not True),
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


def round_outputs(data):
    """THE one scope rule, shared by store.settle_generation and the receipt summary. Only outputs stamped by THIS
    attempt - produced by it, or redone by it (「重试这条」 stamps redone_by_attempt). Returns:
    - those stamped outputs (on_demand included), which may be empty;
    - [] when the attempt record exists but stamped nothing: settle must not borrow other rounds (a shared
      generation.status of rendering/screening is not evidence this attempt succeeded);
    - None (whole workspace) only when there is no attempt record (trimmed / lost / pre-receipt data)."""
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else {}
    attempt_id = generation.get('attempt_id')
    receipt = find(data, attempt_id)
    if receipt is None:
        return None
    return [v for v in data.get('output_variants') or [] if isinstance(v, dict)
            and attempt_id in (v.get('produced_by_attempt'), v.get('redone_by_attempt'))]


def _owned_summary(data):
    """/ / output counts are those of round_outputs (the same scope settle_generation
    judges the status on). With no stamped output in scope the receipt keeps the request fields but no counts -
    unstamped outputs are not attributed by inference."""
    owned = round_outputs(data)
    started = (find(data, data['generation'].get('attempt_id')) or {}).get('created_at')
    if not owned:  # no counts by inference, but the duration never depends on the output scope
        return {k: v for k, v in generation_summary(data, started=started).items() if k in OUTPUT_FREE + ('duration_ms',)}
    return generation_summary(data, variants=owned, started=started)


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
        # settle_generation and the receipt share round_outputs; the counts are taken from _owned_summary
        # (round_outputs again), so generation's completed_variant_count is not copied twice.
        record = {**{k: v for k, v in analysis.items() if k in SUMMARY_KEYS},
                  **{k: v for k, v in generation.items() if k != 'completed_variant_count'}}
        settle(receipt, generation['status'], record, now, data.get('plan') if isinstance(data.get('plan'), dict) else None,
               base=_owned_summary(data))
    elif receipt['kind'] == 'production':
        if not receipt.get('run_id') or analysis.get('run_id') != receipt['run_id'] or analysis.get('phase') != 'production' \
                or analysis.get('status') not in ('completed', 'failed'):
            return
        settle(receipt, analysis.get('outcome') if analysis.get('outcome') in TERMINAL else analysis['status'], analysis, now,
               data.get('plan') if isinstance(data.get('plan'), dict) else None)


def public(receipt) -> dict:
    """What the API returns: the receipt without the idempotency key."""
    return {k: v for k, v in receipt.items() if k not in ('idempotency_key', 'joined_keys', 'plan_id', 'inherited', 'sources', 'input', 'draft_ids')}


def _terminal_event(receipt):
    summary = receipt.get('summary') if isinstance(receipt.get('summary'), dict) else {}
    failed, local, generation = receipt.get('state') != 'completed', summary.get('attribution_source') == 'local', receipt.get('kind') == 'generation'
    props = {k: v for k, v in summary.items() if isinstance(v, bool) or (isinstance(v, str) and v) or (isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0)}
    for key in (*(() if failed else ('shutdown_kind', 'billable_calls_before_failure', 'error_code', 'upstream_error_type', 'http_status')), *(('upstream_error_type', 'http_status') if local else ())):
        props.pop(key, None)
    props.pop('analysis_mode' if generation else 'recommendation_mode', None)
    props.pop('route', None) if not generation else props.update(trigger=receipt['trigger']) if receipt.get('trigger') else None
    props.update(outcome={'completed': 'success', 'failed': 'error'}.get(receipt.get('state'), receipt.get('state')), attempt_id=receipt.get('attempt_id'), flow_id=receipt.get('flow_id'), studio_schema_version=2, **({'attempt_sequence': receipt['sequence']} if isinstance(receipt.get('sequence'), int) else {}), **({'retry_of': receipt['retry_of']} if receipt.get('retry_of') else {}), **({'degrade_reason': receipt['degrade_reason']} if receipt.get('degrade_reason') else {}), **({'error_code': receipt['error_code']} if failed and receipt.get('error_code') else {}), **({'failure_stage': receipt['failure_stage']} if failed and receipt.get('failure_stage') else {}), **({'upstream_error_type': receipt['upstream_error_type']} if failed and not local and receipt.get('upstream_error_type') else {}), **{key: ','.join(str(item) for item in list(receipt[key])[:3]) for key in ('secondary_error_codes', 'secondary_upstream_error_types') if failed and receipt.get(key)})
    props['$insert_id'] = f"studio-v1:{receipt.get('attempt_id')}:finished"
    return {'event': 'studio_generation_finished' if generation else 'studio_production_finished', 'properties': {k: v for k, v in props.items() if v is not None and v != ''}}

def note_settled_terminals(data, previous):
    prior = {a.get('attempt_id'): a.get('state') for a in ((previous or {}).get('attempts') or []) if isinstance(a, dict)}
    return [_terminal_event(r) for r in (data.get('attempts') or []) if isinstance(r, dict) and r.get('state') in TERMINAL and prior.get(r.get('attempt_id')) == 'open']
