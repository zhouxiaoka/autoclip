"""#419: drive the real backend attempt ownership (store + jobs, executor stubbed) - shared by the receipt tests
and the store -> observer -> SQL chain test. Content-free: random ids and enums only."""
import json
from copy import deepcopy

from backend.services.studio import attempts, jobs, readiness, store
from backend.services.studio.models import ImportOptions


def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    monkeypatch.setattr(store, '_read_failures', {})
    monkeypatch.setattr(store, '_pending_links', {})
    monkeypatch.setattr(store, '_io_failures', {})
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: submitted.append(fn.__name__))
    monkeypatch.setattr(jobs, '_prepare_speaker_framing', lambda *a: None)
    monkeypatch.setattr(jobs, '_project_has_subtitle', lambda *a: False)
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda pid: submitted.append('_dispatch_pending_variants'))
    return submitted


def new_project(pid='p1'):
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    return pid


AUTO = ImportOptions.model_validate({'auto_start': True, 'platforms': ['douyin', 'xiaohongshu']})


def auto_import(pid):
    return jobs.inspect_project(pid, AUTO)


def render_outcome(pid, statuses):
    """The generation's variants reach these statuses ({id: (status, error_code|None, upstream|None)}) - settles."""
    def mutate(data):
        data.setdefault('drafts', [])
        data['analysis'] = {**(data.get('analysis') or {}), 'status': 'running', 'phase': 'rendering'}
        data['generation'].update(status='rendering')
        # an output that already exists keeps the attempt that produced it (a variant retry re-renders
        # it); a new one is produced by the open attempt and stamped by the same product call jobs.py persists with.
        existing = {v.get('id'): v for v in data.get('output_variants') or []}
        variants, created = [], []
        for vid, (status, code, upstream) in statuses.items():
            if not any(d['id'] == 'd-' + vid for d in data['drafts']):
                data['drafts'].append({'id': 'd-' + vid, 'title': '', 'scenes': []})
            item = existing.get(vid)
            if item is None:
                item = {'id': vid, 'draft_id': 'd-' + vid, 'strategy_id': 'douyin'}
                created.append(item)
            for key in ('error_code', 'upstream_error_type'):
                item.pop(key, None)
            item.update(status=status, **({'error_code': code} if code else {}), **({'upstream_error_type': upstream} if upstream else {}))
            variants.append(item)
        attempts.own_outputs(data, created)
        data['output_variants'] = [v for v in data.get('output_variants') or [] if v.get('id') not in statuses] + variants
        store.settle_generation(data)
    store.change(pid, mutate)


def production_failed_before_outputs(pid, code='timeout'):
    """The automatic run wrote its plan and started production, then failed before any output was created
    (_auto_generate / _content_drafts failure path)."""
    def mutate(data):
        data['analysis'] = {'status': 'failed', 'phase': 'production', 'run_id': data['analysis'].get('run_id'), 'error_code': code, 'failure_stage': 'analyze'}
        data['generation'].update(status='failed', error_code=code, failure_stage='analyze')
    store.change(pid, mutate)


def screening_failed(pid, code='timeout'):
    """Automatic run failed before rendering (the _inspect failure path writes the generation failed)."""
    def mutate(data):
        data['analysis'] = {'status': 'failed', 'phase': 'screening', 'run_id': data['analysis'].get('run_id'), 'error_code': code, 'failure_stage': 'analyze'}
        data['generation'].update(status='failed', error_code=code, failure_stage='analyze')
    store.change(pid, mutate)


def receipts(pid):
    return attempts.receipts(store.read(pid))


def workspace(pid):
    """What GET /studio/{pid} returns for receipts (api/v1/studio.py workspace)."""
    data = store.read(pid)
    return json.loads(json.dumps({**data, 'material_origin': 'user', 'attempts': [attempts.public(a) for a in attempts.receipts(data)]}))


def retry_variant(pid, vid, key):
    variant = jobs.retry_variant(pid, vid, {'key': key, 'parent_attempt_id': None})
    data = store.read(pid)
    receipt = attempts.by_key(data, key) or attempts.current(data)
    return json.loads(json.dumps({'attempt': attempts.public(receipt), 'variant': deepcopy(variant)}))


MANUAL = ImportOptions.model_validate({'auto_start': False})


def awaiting_confirmation(pid):
    """Manual screening finished: a plan waits for confirmation (what _inspect writes)."""
    def mutate(data):
        data['plan'] = {'id': 'plan-' + data['analysis']['run_id'][:8], 'preferences': {'goal': 'content'}, 'recommended_analysis': 'subtitle'}
        data['analysis'] = {'status': 'awaiting_confirmation', 'created_at': store.now()}
    store.change(pid, mutate)
    return store.read(pid)['plan']['id']


def confirm(pid, plan_id, monkeypatch):
    from backend.services.studio import preflight
    from backend.services.studio.models import ConfirmPlan
    video = store.directory(pid) / 'input.mp4'
    video.write_bytes(b'')
    (store.directory(pid) / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nx\n')
    monkeypatch.setattr(jobs, 'source', lambda _pid: video)
    # #418 confirm refuses an unreadable fixture through preflight.check (subtitle_route_failure is gone).
    # This helper only opens the production attempt.
    monkeypatch.setattr(preflight, 'check', lambda *a, **k: None)
    return jobs.confirm_project(pid, ConfirmPlan(plan_id=plan_id, goals=['content']))


def production_finished(pid, status='failed', code='timeout', outcome=None):
    def mutate(data):
        data['analysis'] = {'status': status, 'phase': 'production', 'run_id': data['analysis']['run_id'],
                            **({'error_code': code, 'failure_stage': 'analyze'} if status == 'failed' else {}), **({'outcome': outcome} if outcome else {})}
    store.change(pid, mutate)
