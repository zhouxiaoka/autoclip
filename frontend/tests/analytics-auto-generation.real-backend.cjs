const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

function loadWorkflow(MathImpl=Math){
 const source=fs.readFileSync(path.join(__dirname,'../src/analytics/workflow.ts'),'utf8')
 const exports={}
 runInSandbox(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,Date,Math:MathImpl,JSON,Number,Array,Object,Map,Set,String,URL,require:id=>{
  if(id==='./failureCodes') return loadTs(path.join(__dirname,'../src/analytics/failureCodes.ts'))
  throw new Error('Unexpected dependency: '+id)
 }})
 return exports
}
const {withRealBackend: withBackendReceipts}=require('./helpers/real-backend.cjs')
const workflow=withBackendReceipts(loadWorkflow())

function tracker(){
 const events=[],store=new Map()
 const storage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)}
 const t=new workflow.WorkflowTracker(storage,()=>true,(name,props)=>{events.push({name,props});return true})
 return {t,events}
}

const SNAPSHOT={
 generation:{auto_start:true,status:'partial',requested_platforms:['douyin','tiktok'],skipped:[{strategy_id:'youtube_long',reason:'x'}],
  source_has_burned_subtitles:false,created_at:'2026-09-30T10:00:00Z',finished_at:'2026-09-30T10:04:00Z'},
 analysis:{status:'completed',phase:'rendering',run_id:'run-1'},
 plan:{id:'plan-1',mode:'local',recommended_analysis:'subtitle'},
 output_variants:[
  {draft_id:'a',strategy_id:'douyin',status:'completed',framing:'speaker'},
  {draft_id:'b',strategy_id:'tiktok',status:'failed',framing:'full_frame',trimmed_to_sec:180},
  {draft_id:'c',strategy_id:'douyin',status:'on_demand'},
 ],
 drafts:[{id:'a',title:'Private title',packaging:{template:'interview_zh',fallback:false}},{id:'b',packaging:{template:'podcast_en',fallback:true}}],
}

test('receipt summary fields keep enums and drop content',()=>{
 // the counting rules are asserted on backend attempts.generation_summary; here only the sanitizer.
 const props=workflow.safeStudioProperties({variant_count:3,outro_unknown_count:1,portrait_style:'podcast',title:'Private title',name:'Sam Altman',template:'interview_zh',packaging_style:'boxed',framing:'speaker',warnings:['private error']})
 assert.equal(JSON.stringify(props).includes('Private'),false)
 assert.equal(JSON.stringify(props).includes('private'),false)
 assert.equal(JSON.stringify(props).includes('Sam'),false)
 assert.equal(props.template,'interview_zh'); assert.equal(props.packaging_style,'boxed'); assert.equal(props.framing,'speaker')
 assert.equal(props.portrait_style,'podcast'); assert.equal(props.outro_unknown_count,1)
})

test('automatic output ends screening as auto_started, even if rendering later failed',()=>{
 const {t,events}=tracker()
 t.watch('studio-screen','p1',undefined,undefined,{},false,'run-1')
 t.observeStudio(t.list().find(w=>w.kind==='studio-screen'),{...SNAPSHOT,analysis:{status:'failed',phase:'rendering',run_id:'run-1'}})
 const screen=events.find(e=>e.name==='studio_screen_finished')
 assert.ok(screen); assert.equal(screen.props.outcome,'auto_started')
})

test('generation watch reports one terminal event with the aggregate summary',()=>{
 const {t,events}=tracker()
 t.watch('studio-generation','p1')
 const watch=t.list().find(w=>w.kind==='studio-generation')
 t.observeStudio(watch,{...SNAPSHOT,generation:{...SNAPSHOT.generation,status:'rendering'}})
 assert.equal(events.filter(e=>e.name==='studio_generation_finished').length,0)
 t.observeStudio(watch,SNAPSHOT)
 t.observeStudio(watch,SNAPSHOT)
 assert.equal(events.filter(e=>e.name==='studio_generation_finished').length,0)
})

test('automatic production failures report a safe code once without sending private errors',()=>{
 const {t,events}=tracker()
 t.watch('studio-generation','p1')
 const watch=t.list().find(w=>w.kind==='studio-generation')
 const state={...SNAPSHOT,generation:{status:'failed',error_code:'whisper_not_installed',error:'private transcript'},
  analysis:{status:'failed',phase:'production',error_code:'whisper_not_installed',error:'private path'}}
 t.observeStudio(watch,state); t.observeStudio(watch,state)
 assert.equal(events.filter(e=>e.name==='studio_generation_finished').length,0)
})

test('automatic failures report the failed stage, HTTP status and route, rejecting unknown values',()=>{
 const {t,events}=tracker();t.watch('studio-generation','p1')
 const state={generation:{status:'failed',error_code:'provider_error',failure_stage:'screening',http_status:400,error:'private body'},
  analysis:{status:'failed',phase:'screening',error_code:'provider_error'},plan:{id:'p',mode:'ai',recommended_analysis:'visual'}}
 t.observeStudio(t.list()[0],state)
 assert.equal(events.filter(e=>e.name==='studio_generation_finished').length,0)
 const bad=workflow.safeStudioProperties({failure_stage:'private-stage',http_status:200,route:'private-route'})
 assert.equal(bad.failure_stage,undefined);assert.equal(bad.http_status,undefined);assert.equal(bad.route,undefined)
})

test('automatic auth failures retain their code and pass catalog validation without private content',()=>{
 const {loadTs}=require('./load-ts.cjs')
 const catalogApi=loadTs(path.resolve(__dirname,'../src/analytics/eventCatalog.ts'))
 const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../../docs/analytics/event_catalog.json'),'utf8'))
 for(const status of [401,403]){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:'llm_auth_invalid',http_status:status,failure_stage:'analyze',error:'private content'}})
  assert.equal(events.find(e=>e.name==='studio_generation_finished'),undefined)
  const props={outcome:'error',error_code:'llm_auth_invalid',failure_stage:'analyze',http_status:status,studio_schema_version:2}
  assert.equal(catalogApi.validateEvent('studio_generation_finished',props,catalog).join(';'),'')
 }
})

// receipts come from the real backend, which always persists the generation's own code (_inspect writes it;
// store._ensure_failure_identity normalizes anything outside STUDIO_ERROR_CODES to 'unexpected').
test('automatic failures report the persisted code and never an unrecognized one',()=>{
 for(const code of ['subtitle_setup','private arbitrary message']){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:code},analysis:{status:'failed',phase:'production',error_code:code}})
  assert.equal(events.find(e=>e.name==='studio_generation_finished'),undefined)
 }
})

test('partial output reports its failed variant code and completed output clears stale failures',()=>{
 for(const status of ['partial','completed']){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{...SNAPSHOT,generation:{...SNAPSHOT.generation,status,error_code:'timeout',error:'private path'}})
  assert.equal(events.find(e=>e.name==='studio_generation_finished'),undefined)
 }
})


test('local render timeout retains a safe code for export and automatic partial output once',()=>{
 const snapshot={
  jobs:[{job_id:'private-render-job',status:'failed',error_code:'timeout',error:'private-command'}],
  generation:{auto_start:true,status:'partial',error_code:'timeout'},
  analysis:{status:'completed',phase:'rendering'},
  output_variants:[
   {draft_id:'kept',strategy_id:'douyin',status:'completed'},
   {draft_id:'failed',strategy_id:'douyin',status:'failed',render_job_id:'private-render-job'},
  ],
 }
 for(const [kind,id,event,outcome] of [
  ['studio-export','private-render-job','studio_export_finished','error'],
  ['studio-generation','private-project','studio_generation_finished','partial'],
 ]){
  const {t,events}=tracker();t.watch(kind,id,'private-project')
  const watch=t.list()[0]
  t.observeStudio(watch,snapshot);t.observeStudio(watch,snapshot)
  const finished=events.filter(e=>e.name===event)
  if(kind==='studio-generation'){assert.equal(finished.length,0);continue}
  assert.equal(finished.length,1)
  assert.equal(finished[0].props.error_code,'timeout')
  assert.equal(finished[0].props.outcome,outcome)
  assert.equal(JSON.stringify(finished).includes('private'),false)
 }
})

test('R22 #220: auto screen_finished names the screening connection, not the production re-freeze',()=>{
 const live={...SNAPSHOT,generation:{...SNAPSHOT.generation,status:'production',screening_identity:{provider:'kimi',config_source:'customized'},provider:'deepseek',config_source:'preset'},
  analysis:{status:'running',phase:'production',run_id:'run-1',provider:'deepseek',config_source:'preset',screening_identity:{provider:'kimi',config_source:'customized'}}}
 for(const snapshot of [live,{...live,analysis:{status:'running',phase:'rendering',run_id:'run-1',provider:'deepseek',config_source:'preset'}}]){
  const {t,events}=tracker()
  t.watch('studio-screen','p1',undefined,undefined,{},false,'run-1')
  t.observeStudio(t.list().find(w=>w.kind==='studio-screen'),snapshot)
  const screen=events.find(e=>e.name==='studio_screen_finished')
  assert.equal(screen.props.outcome,'auto_started')
  assert.equal(screen.props.provider,'kimi'); assert.equal(screen.props.config_source,'customized')
 }
})

// Flake root cause: telemetryId() joined random base36 segments with '-', so a segment ending in
// "sk" produced "sk-", which the catalog privacy check flags as a secret. Seeded reproduction:
function seededMath(values){let i=0;return Object.assign(Object.create(Math),{random:()=>values[i++%values.length]})}
const SK=(28*36+20)/1296   // (SK).toString(36) === '0.sk'

test('seeded ids that would spell a secret marker are regenerated and pass catalog validation',{timeout:5000},()=>{
 const {loadTs}=require('./load-ts.cjs')
 const catalogApi=loadTs(path.resolve(__dirname,'../src/analytics/eventCatalog.ts'))
 const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../../docs/analytics/event_catalog.json'),'utf8'))
 assert.equal(SK.toString(36),'0.sk')
 for(const values of [[SK,0.25,0.5,0.75],[SK]]){   // second: RNG stuck on the bad value
  const wf=withBackendReceipts(loadWorkflow(seededMath(values)))
  const events=[],store=new Map()
  const t=new wf.WorkflowTracker({getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},()=>true,(name,props)=>{events.push({name,props});return true})
  t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:'llm_auth_invalid',http_status:401,failure_stage:'analyze'}})
  assert.equal(events.find(e=>e.name==='studio_generation_finished'),undefined)
  const id=wf.telemetryId()
  assert.equal(catalogApi.validateEvent('studio_generation_finished',{outcome:'error',error_code:'llm_auth_invalid',failure_stage:'analyze',flow_id:id,studio_schema_version:2},catalog).join(';'),'')
  assert.match(id,/^t-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/,'three segments after t-')
  for(const marker of wf.ID_FORBIDDEN_MARKERS) assert.ok(!id.includes(marker),id)
 }
})

test('id markers cover the catalog forbidden substrings (detector not weakened)',()=>{
 const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../../docs/analytics/event_catalog.json'),'utf8'))
 for(const marker of catalog.privacy.forbidden_substrings) assert.ok(workflow.ID_FORBIDDEN_MARKERS.includes(marker.toLowerCase()),marker)
 const {loadTs}=require('./load-ts.cjs')
 const catalogApi=loadTs(path.resolve(__dirname,'../src/analytics/eventCatalog.ts'))
 // #92: start from a complete, otherwise-valid event so the only possible error is the privacy check.
 const events=[],store=new Map()
 const t=new workflow.WorkflowTracker({getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},()=>true,(name,props)=>{events.push({name,props});return true})
 t.watch('studio-generation','p1')
 t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:'llm_auth_invalid',http_status:401,failure_stage:'analyze'}})
 assert.equal(events.find(e=>e.name==='studio_generation_finished'),undefined)
 const baseline={outcome:'error',error_code:'llm_auth_invalid',failure_stage:'analyze',http_status:401,flow_id:'t-abc-def-ghij',studio_schema_version:2}
 assert.equal(catalogApi.validateEvent('studio_generation_finished',baseline,catalog).join(';'),'','baseline event is fully valid')
 const tainted={...baseline,flow_id:'t-abc-sk-123'}
 assert.equal(catalogApi.validateEvent('studio_generation_finished',tainted,catalog).join(';'),'studio_generation_finished.flow_id looks like a secret','a real sk- value must still be flagged')
 // #93: shape is t-<seg>-<seg>-<seg>, three non-empty base36 segments.
 const SHAPE=/^t-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/
 for(let i=0;i<20000;i++){const id=workflow.telemetryId();assert.match(id,SHAPE);for(const m of workflow.ID_FORBIDDEN_MARKERS) assert.ok(!id.includes(m),id)}
})

test('R24 #292: a replayed run reads its own receipt, never the current round\'s screening identity',()=>{
 const current={...SNAPSHOT,generation:{...SNAPSHOT.generation,status:'production',screening_identity:{provider:'glm',config_source:'customized'}},
  analysis:{status:'running',phase:'production',run_id:'run-2',provider:'glm',config_source:'customized',screening_identity:{provider:'glm',config_source:'customized'}},
  analysis_history:[{run_id:'run-1',analysis:{status:'failed',phase:'screening',run_id:'run-1',error_code:'unexpected',failure_stage:'screening',provider:'kimi',config_source:'customized'}}]}
 const {t,events}=tracker()
 t.watch('studio-screen','p1',undefined,undefined,{},false,'run-1')
 t.observeStudio(t.list().find(w=>w.kind==='studio-screen'),current)
 const screen=events.find(e=>e.name==='studio_screen_finished')
 assert.ok(screen)
 assert.equal(screen.props.provider,'kimi'); assert.equal(screen.props.config_source,'customized')
})
