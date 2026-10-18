"""R13 #25 (#406): degrade_reason survives the terminal record (analysis_history allowlist) and
reaches the frontend terminal event on the real path: store -> frontend read -> capture.
#419: the terminal is a projection of the backend attempt receipt; the reason is frozen in the receipt at settle
from that attempt's own plan, so a later re-screen (plan2, no reason) cannot drop or change it."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services.studio import attempts, store

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
REASONS = ['frame_extract_subtitle_fallback', 'source_too_long_subtitle_route']

SCRIPT = r"""
const fs=require('fs'),path=require('path'),vm=require('vm'),ts=require('typescript')
const {loadTs}=require('./tests/load-ts.cjs')
const [kind,id,run]=process.argv.slice(1)
const snapshot=JSON.parse(fs.readFileSync(0,'utf8'))
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join('src','analytics','workflow.ts'),'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,
 {exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL,require:(id)=>{
  if(id==='./failureCodes') return loadTs(path.resolve('src/analytics/failureCodes.ts'))
  throw new Error('dep '+id)
 }})
const events=[],storage=new Map()
const tracker=new exports.WorkflowTracker({getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 ()=>true,(name,props)=>{events.push({name,props});return true})
tracker.watch(kind,id,undefined,undefined,{},false,run)
const watch=tracker.list().find(item=>item.kind===kind)
tracker.observeStudio(watch,snapshot)
tracker.observeStudio(watch,JSON.parse(JSON.stringify(snapshot)))
process.stdout.write(JSON.stringify(events.filter(e=>e.name.endsWith('_finished'))))
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p').mkdir(parents=True)
    return 'p'


def _capture(kind, watch_id, snapshot):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        pytest.skip('frontend toolchain not installed')
    done = subprocess.run(['node', '-e', SCRIPT, kind, watch_id, 'run'], input=json.dumps(snapshot),
                          cwd=FRONTEND, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def _terminal(reason, auto):
    plan = {'id': 'plan', 'mode': 'local', 'recommended_analysis': 'subtitle',
            'confirmed_analysis': 'subtitle', 'degrade_reason': reason}
    return {
        'plan': plan,
        'analysis': {'status': 'completed', 'outcome': 'completed', 'phase': 'production', 'run_id': 'run'},
        'generation': {'auto_start': auto, 'status': 'completed', 'route': 'subtitle'},
    }


@pytest.mark.parametrize('reason', REASONS)
@pytest.mark.parametrize('entry', ['auto', 'manual'])
def test_degrade_reason_reaches_terminal_event_from_stored_record(project, reason, entry):
    auto = entry == 'auto'
    opened = {}
    receipt_kind = 'generation' if auto else 'production'
    seed = _terminal(reason, auto)
    seed['generation']['status'] = 'production'
    seed['analysis'] = {'status': 'running', 'phase': 'production', 'run_id': 'run', 'instance': store.INSTANCE}

    def start(data):
        data.update(seed)
        receipt = attempts.open_attempt(data, receipt_kind, run_id='run')
        attempts.bind_plan(receipt, data['plan'])  # R25 #348: what _inspect / confirm_project do for the attempt's own plan
        opened.update(receipt)
        if auto:
            data['generation']['attempt_id'] = opened['attempt_id']
        return data
    store.write(project, start(store.read(project)))
    done = store.read(project)
    done.update({k: v for k, v in _terminal(reason, auto).items() if k != 'generation'})
    done['generation'] = {**_terminal(reason, auto)['generation'], **({'attempt_id': opened['attempt_id']} if auto else {})}
    store.write(project, done)
    # The live run moves on (re-screen / plan rewrite); only the persisted terminal record
    # still describes run 'run', so the frontend reads it from analysis_history.
    later = store.read(project)
    later['plan'] = {'id': 'plan2', 'mode': 'local', 'recommended_analysis': 'vision'}
    later['analysis'] = {'status': 'running', 'phase': 'analysis', 'run_id': 'run2', 'instance': store.INSTANCE}
    store.write(project, later)
    snapshot = store.read(project)
    settled = attempts.find(snapshot, opened['attempt_id'])
    assert settled['state'] == 'completed' and settled['degrade_reason'] == reason
    receipt = next(row for row in snapshot['analysis_history'] if row['run_id'] == 'run')
    assert receipt['plan']['degrade_reason'] == reason
    kind = 'studio-generation' if auto else 'studio-production'
    finished = _capture(kind, 'p' if auto else 'plan', snapshot)
    assert len(finished) == 1, finished  # duplicate observation counted once
    assert finished[0]['props']['degrade_reason'] == reason
