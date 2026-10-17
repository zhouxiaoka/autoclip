"""R16 #39: run identity survives analysis_history and reaches the terminal event on the real
path: store.write -> later run replaces live analysis -> store.read -> frontend WorkflowTracker."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services.studio import store

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
PRESETS = Path(__file__).resolve().parents[1] / 'presets' / 'provider_presets.json'

SCRIPT = r"""
const fs=require('fs'),path=require('path'),vm=require('vm'),ts=require('typescript')
const [kind,id,run,presets]=process.argv.slice(1)
const snapshot=JSON.parse(fs.readFileSync(0,'utf8'))
const exports={}
const deps={'@provider-presets':{__esModule:true,default:JSON.parse(fs.readFileSync(presets,'utf8'))}}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join('src','analytics','workflow.ts'),'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,
 {exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL,require:(d)=>{if(d in deps)return deps[d];throw new Error('dep '+d)}})
const events=[],storage=new Map()
const tracker=new exports.WorkflowTracker({getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 ()=>true,(name,props)=>{events.push({name,props});return true})
tracker.watch(kind,id,undefined,undefined,{},false,run)
const watch=tracker.list().find(item=>item.kind===kind)
tracker.observeStudio(watch,snapshot)
process.stdout.write(JSON.stringify(events.filter(e=>e.name.endsWith('_finished'))))
"""

IDENTITY = {'provider': 'gemini', 'config_source': 'customized', 'upstream_error_type': 'rate_limited',
            'failure_stage': 'screening', 'shutdown_kind': 'crash'}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p').mkdir(parents=True)
    return 'p'


def _capture(kind, watch_id, snapshot):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        # R19 #102: never skip (quality_gate treats an unexpected skip as BLOCKED). The frontend toolchain
        # is a required test dependency: `cd frontend && npm ci` (docs/TESTING_ACCEPTANCE.md).
        pytest.fail('frontend toolchain missing: run `cd frontend && npm ci` (node + frontend/node_modules/typescript are required)')
    done = subprocess.run(['node', '-e', SCRIPT, kind, watch_id, 'run', str(PRESETS)], input=json.dumps(snapshot),
                          cwd=FRONTEND, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


@pytest.mark.parametrize('phase,kind,watch_id', [('screening', 'studio-screen', 'p'), ('production', 'studio-production', 'plan')])
def test_identity_survives_history_to_terminal(project, phase, kind, watch_id):
    identity = {**IDENTITY, 'failure_stage': phase}
    state = {'plan': {'id': 'plan', 'mode': 'local'},
             'analysis': {'status': 'failed', 'phase': phase, 'run_id': 'run', 'error_code': 'service_restarted', **identity}}
    if phase == 'production':
        # v4 production terminals are the settled receipt (#419). The history row still keeps the identity.
        state['attempts'] = [{'attempt_id': 't-aaaaaaaaaaaaaaaa', 'flow_id': 't-ffffffffffffffff', 'sequence': 1,
                              'kind': 'production', 'state': 'open', 'run_id': 'run', 'trigger': 'initial', 'causes': []}]
        state['attempt_sequence'] = 1
    store.write(project, state)
    kept = store.read(project).get('attempts') if phase == 'production' else None
    later = {'plan': {'id': 'plan2', 'mode': 'local'},
             'analysis': {'status': 'running', 'phase': 'screening', 'run_id': 'run2', 'instance': store.INSTANCE}}
    if kept:
        later['attempts'] = kept
    store.write(project, later)
    snapshot = store.read(project)
    receipt = next(row for row in snapshot['analysis_history'] if row['run_id'] == 'run')
    for key, value in identity.items():
        assert receipt['analysis'][key] == value, key
    finished = _capture(kind, watch_id, snapshot)
    assert len(finished) == 1, finished
    props = finished[0]['props']
    for key, value in identity.items():
        assert props.get(key) == value, (key, props)
