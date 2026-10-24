"""Test bridge (replaces frontend/tests/helpers/backend-receipts.cjs): the REAL backend materializes the
attempt receipt for a workspace snapshot a frontend telemetry test observes. No receipt rule lives here: the
attempt is opened, bound and settled by backend.services.studio.attempts through store.write, exactly as jobs.py
does (open with the run -> running state written -> terminal state written -> attempts.reconcile settles it).
plan binding and output ownership happen only when the snapshot got past screening, as in the real entry.
Only the attempt tokens are deterministic (seeded) so repeated observations see the same attempt_id.
stdin {"kind": "generation"|"production", "run_id": str, "seed": str, "retry": bool, "snapshot": {...}}
stdout {"attempts": [...public receipts], "attempt_id": str, "run_id": str}"""
import hashlib
import json
import os
import sys
import tempfile
from copy import deepcopy


def main():
    payload = json.loads(sys.stdin.read())
    with tempfile.TemporaryDirectory() as root:
        os.environ['AUTOCLIP_DATA_DIR'] = root
        os.environ['AUTOCLIP_APP_DIR'] = root
        with open(os.path.join(root, 'privacy.json'), 'w') as f:
            f.write('{"crash_reports":false}')
        from backend.services.studio import attempts, store
        counter = iter(range(1000))
        attempts.token = lambda: 't-' + hashlib.sha256(f"{payload['seed']}:{next(counter)}".encode()).hexdigest()[:24]
        print(json.dumps(materialize(payload, attempts, store)))


def _running(snapshot, run, kind, store):
    state = {k: deepcopy(v) for k, v in snapshot.items() if k not in ('attempts', 'analysis_history')}
    state['analysis'] = {'status': 'running', 'phase': 'production', 'run_id': run, 'instance': store.INSTANCE, 'created_at': store.now()}
    if isinstance(state.get('generation'), dict):
        state['generation'] = {**state['generation'], 'status': 'production'}
        state['generation'].pop('finished_at', None)
    return state


def materialize(payload, attempts, store):
    pid, kind, run, snapshot = 'p', payload['kind'], payload['run_id'], payload['snapshot']
    store.directory(pid).mkdir(parents=True, exist_ok=True)
    plan = snapshot.get('plan') if isinstance(snapshot.get('plan'), dict) else None
    parent = None
    if payload.get('retry'):  # the failed attempt this one retries, settled by the backend first
        state = _running(snapshot, run + '-parent', kind, store)
        first = attempts.open_attempt(state, kind, run_id=run + '-parent', now=store.now())
        if kind == 'generation':
            state['generation']['attempt_id'] = first['attempt_id']
        store.write(pid, state)
        failed = store.read(pid)
        failed['analysis'] = {'status': 'failed', 'phase': 'production', 'run_id': run + '-parent', 'error_code': 'timeout', 'failure_stage': 'analyze'}
        if kind == 'generation':
            failed['generation'].update(status='failed', error_code='timeout', failure_stage='analyze')
        store.write(pid, failed)
        parent = attempts.find(store.read(pid), first['attempt_id'])
    state = {**_running(snapshot, run, kind, store), 'attempts': attempts.receipts(store.read(pid)) if parent else []}
    if parent:
        state['attempt_sequence'] = store.read(pid).get('attempt_sequence')
    receipt = attempts.open_attempt(state, kind, trigger='retry' if parent else 'initial', parent=parent, run_id=run, now=store.now())
    # like the real entry, the plan is bound only once screening handed over to production
    # (jobs._inspect.start_automatic / confirm_project); a snapshot that failed in screening never had its plan.
    reached_production = (snapshot.get('analysis') or {}).get('phase') != 'screening'
    if reached_production:
        attempts.bind_plan(receipt, plan)
    if kind == 'generation' and isinstance(state.get('generation'), dict):
        state['generation']['attempt_id'] = receipt['attempt_id']
    store.write(pid, state)
    terminal = store.read(pid)
    for key, value in snapshot.items():
        if key not in ('attempts', 'analysis_history', 'attempt_sequence'):
            terminal[key] = deepcopy(value)
    analysis = terminal.get('analysis') if isinstance(terminal.get('analysis'), dict) else {}
    terminal['analysis'] = {**analysis, 'run_id': analysis.get('run_id') or run, **({'phase': analysis.get('phase') or 'production'} if kind == 'production' else {})}
    if kind == 'generation' and isinstance(terminal.get('generation'), dict):
        terminal['generation'] = {**terminal['generation'], 'attempt_id': receipt['attempt_id']}
    if reached_production:  # unstamped snapshot outputs are this attempt's; stamped ones keep theirs
        attempts.own_outputs(terminal, [v for v in terminal.get('output_variants') or [] if isinstance(v, dict)])
    store.write(pid, terminal)
    data = store.read(pid)
    return {'attempts': [attempts.public(a) for a in attempts.receipts(data)], 'attempt_id': receipt['attempt_id'], 'run_id': run}


if __name__ == '__main__':
    main()
