const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),ts=require('typescript')
const file=path.resolve(__dirname,'../src/features/studio/draftExportState.ts'),m=new Module(file,module)
m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,file)
const state=m.exports.draftExportState
const draft={id:'d1',revision:2}
const job=(id,status,revision=2,time=1)=>({job_id:id,draft_id:'d1',revision,status,created_at:`2026-09-23T00:00:0${time}Z`})
test('unrendered and older revision exports never count as current video',()=>{
 assert.equal(state(draft,[]).status,'draft')
 const s=state(draft,[job('old','completed',1)])
 assert.equal(s.status,'updated');assert.equal(s.completed,undefined);assert.equal(s.previous.job_id,'old')
 assert.equal(state(draft,[{...job('other','completed'),draft_id:'d2'},job('future','completed',3)]).status,'draft')
})
test('queued and running current exports have distinct progress states',()=>{
 assert.equal(state(draft,[job('q','queued')]).status,'queued')
 assert.equal(state(draft,[job('r','running')]).status,'rendering')
 assert.equal(state(draft,[job('old','running',1)]).status,'draft')
})
test('failed re-export does not hide a valid completed file for the same revision',()=>{
 const s=state(draft,[job('failed','failed',2,2),job('ready','completed')])
 assert.equal(s.status,'ready');assert.equal(s.completed.job_id,'ready');assert.equal(s.failure.job_id,'failed')
 assert.equal(state(draft,[job('failed','failed')]).status,'failed')
})
test('active re-export retains current download, and unordered histories are sorted without mutation',()=>{
 const jobs=[job('older','completed',2,1),job('newest','completed',2,3),job('running','running',2,4)]
 const snapshot=JSON.stringify(jobs),s=state(draft,jobs)
 assert.equal(s.status,'rendering');assert.equal(s.active.job_id,'running');assert.equal(s.completed.job_id,'newest')
 assert.equal(JSON.stringify(jobs),snapshot)
})
