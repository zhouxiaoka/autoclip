const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')

function loadWorkflow(MathImpl=Math){
 const source=fs.readFileSync(path.join(__dirname,'../src/analytics/workflow.ts'),'utf8')
 const exports={}
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,Date,Math:MathImpl,JSON,Number,Array,Object,Map,Set,String,URL})
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

test('generation summary counts templates, framing and fallbacks without any content',()=>{
 const summary=workflow.generationSummary(SNAPSHOT)
 assert.deepEqual({...summary},{variant_count:3,completed_variant_count:1,failed_variant_count:1,on_demand_variant_count:1,skipped_variant_count:1,platform_count:2,
  interview_count:1,podcast_count:1,landscape_count:0,editorial_count:0,street_count:0,classic_count:2,html_downgrade_count:0,speaker_framed_count:1,full_frame_count:1,framing_pending_count:0,framing_captions_count:0,
  portrait_style:undefined,brand_outro_enabled:undefined,outro_applied_count:0,outro_fallback_count:0,outro_unknown_count:1,packaging_fallback_count:1,trimmed_count:1,burned_captions:false,duration_ms:240000})
 const props=workflow.safeStudioProperties({...summary,title:'Private title',name:'Sam Altman',template:'interview_zh',packaging_style:'boxed',framing:'speaker'})
 assert.equal(JSON.stringify(props).includes('Private'),false)
 assert.equal(JSON.stringify(props).includes('Sam'),false)
 assert.equal(props.template,'interview_zh'); assert.equal(props.packaging_style,'boxed'); assert.equal(props.framing,'speaker')
})

test('outro metrics separate actual result, disabled setting, fallback and missing evidence',()=>{
 const state={generation:{portrait_style:'podcast',branding:{outro_enabled:true}},output_variants:[
  ...['applied','fallback','disabled','unknown'].map(id=>({id,draft_id:id,render_job_id:id,strategy_id:'douyin',status:'completed',branding:{outro_enabled:true}})),
  {id:'failed',draft_id:'failed',render_job_id:'failed',strategy_id:'douyin',status:'failed'},
 ],jobs:[
  {job_id:'applied',status:'completed',brand_outro:true,result:{outro_applied:true}},
  {job_id:'fallback',status:'completed',brand_outro:true,result:{outro_applied:false,warnings:['private error']}},
  {job_id:'disabled',status:'completed',brand_outro:false,result:{outro_applied:false}},
  {job_id:'failed',status:'failed',brand_outro:true,result:{outro_applied:false}},
 ]}
 const props=workflow.safeStudioProperties(workflow.generationSummary(state))
 assert.equal(props.portrait_style,'podcast')
 assert.equal(props.outro_applied_count,1);assert.equal(props.outro_fallback_count,1);assert.equal(props.outro_unknown_count,1)
 assert.equal(JSON.stringify(props).includes('private'),false)
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
 const finished=events.filter(e=>e.name==='studio_generation_finished')
 assert.equal(finished.length,1)
 assert.equal(finished[0].props.outcome,'partial'); assert.equal(finished[0].props.speaker_framed_count,1)
})

test('automatic production failures report a safe code once without sending private errors',()=>{
 const {t,events}=tracker()
 t.watch('studio-generation','p1')
 const watch=t.list().find(w=>w.kind==='studio-generation')
 const state={...SNAPSHOT,generation:{status:'failed',error_code:'whisper_not_installed',error:'private transcript'},
  analysis:{status:'failed',phase:'production',error_code:'whisper_not_installed',error:'private path'}}
 t.observeStudio(watch,state); t.observeStudio(watch,state)
 const finished=events.filter(e=>e.name==='studio_generation_finished')
 assert.equal(finished.length,1)
 assert.equal(finished[0].props.error_code,'whisper_not_installed')
 assert.equal(JSON.stringify(finished).includes('private'),false)
})

test('automatic failures report the failed stage, HTTP status and route, rejecting unknown values',()=>{
 const {t,events}=tracker();t.watch('studio-generation','p1')
 const state={generation:{status:'failed',error_code:'provider_error',failure_stage:'screening',http_status:400,error:'private body'},
  analysis:{status:'failed',phase:'screening',error_code:'provider_error'},plan:{id:'p',mode:'ai',recommended_analysis:'visual'}}
 t.observeStudio(t.list()[0],state)
 const props=events.find(e=>e.name==='studio_generation_finished').props
 assert.equal(props.failure_stage,'screening');assert.equal(props.http_status,400)
 assert.equal(props.route,'visual');assert.equal(props.recommendation_mode,'ai')
 assert.equal(JSON.stringify(props).includes('private'),false)
 const bad=workflow.safeStudioProperties({failure_stage:'private-stage',http_status:200,route:'private-route'})
 assert.equal(bad.failure_stage,undefined);assert.equal(bad.http_status,undefined);assert.equal(bad.route,undefined)
 const {t:t2,events:e2}=tracker();t2.watch('studio-generation','p1')
  t2.observeStudio(t2.list()[0],{...SNAPSHOT,generation:{...SNAPSHOT.generation,status:'completed',failure_stage:'render',http_status:500}})
  const done=e2.find(e=>e.name==='studio_generation_finished').props
  assert.equal(done.failure_stage,undefined);assert.equal(done.http_status,undefined);assert.equal(done.route,'subtitle')
  const {t:t3,events:e3}=tracker();t3.watch('studio-generation','p1')
  t3.observeStudio(t3.list()[0],{generation:{status:'failed',error_code:'timeout',failure_stage:'render',route:'subtitle'},analysis:{status:'failed'}})
  assert.equal(e3.find(e=>e.name==='studio_generation_finished').props.route,'subtitle')
})

test('automatic auth failures retain their code and pass catalog validation without private content',()=>{
 const {loadTs}=require('./load-ts.cjs')
 const catalogApi=loadTs(path.resolve(__dirname,'../src/analytics/eventCatalog.ts'))
 const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../../docs/analytics/event_catalog.json'),'utf8'))
 for(const status of [401,403]){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:'llm_auth_invalid',http_status:status,failure_stage:'analyze',error:'private content'}})
  const finished=events.find(e=>e.name==='studio_generation_finished')
  assert.equal(finished.props.error_code,'llm_auth_invalid')
  assert.equal(catalogApi.validateEvent(finished.name,finished.props,catalog).join(';'),'')
  assert.equal(JSON.stringify(finished).includes('private'),false)
 }
})

// R25: receipts come from the real backend, which always persists the generation's own code (_inspect writes it;
// store._ensure_failure_identity normalizes anything outside STUDIO_ERROR_CODES to 'unexpected').
test('automatic failures report the persisted code and never an unrecognized one',()=>{
 for(const code of ['subtitle_setup','private arbitrary message']){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{generation:{status:'failed',error_code:code},analysis:{status:'failed',phase:'production',error_code:code}})
  const finished=events.find(e=>e.name==='studio_generation_finished')
  assert.equal(finished.props.error_code,code==='subtitle_setup'?'subtitle_setup':'unexpected')
  assert.equal(JSON.stringify(finished).includes('private'),false)
 }
})

test('partial output reports its failed variant code and completed output clears stale failures',()=>{
 for(const status of ['partial','completed']){
  const {t,events}=tracker();t.watch('studio-generation','p1')
  t.observeStudio(t.list()[0],{...SNAPSHOT,generation:{...SNAPSHOT.generation,status,error_code:'timeout',error:'private path'}})
  const finished=events.find(e=>e.name==='studio_generation_finished')
  assert.equal(finished.props.error_code,status==='partial'?'timeout':undefined)
  assert.equal(JSON.stringify(finished).includes('private'),false)
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
  assert.equal(finished.length,1)
  assert.equal(finished[0].props.error_code,'timeout')
  assert.equal(finished[0].props.outcome,outcome)
  assert.equal(JSON.stringify(finished).includes('private'),false)
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
  const finished=events.find(e=>e.name==='studio_generation_finished')
  assert.ok(finished,'event emitted')
  assert.equal(catalogApi.validateEvent(finished.name,finished.props,catalog).join(';'),'')
  const id=wf.telemetryId()
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
 const finished=events.find(e=>e.name==='studio_generation_finished')
 assert.equal(catalogApi.validateEvent(finished.name,finished.props,catalog).join(';'),'','baseline event is fully valid')
 const tainted={...finished.props,flow_id:'t-abc-sk-123'}
 assert.equal(catalogApi.validateEvent(finished.name,tainted,catalog).join(';'),'studio_generation_finished.flow_id looks like a secret','a real sk- value must still be flagged')
 // #93: shape is t-<seg>-<seg>-<seg>, three non-empty base36 segments.
 const SHAPE=/^t-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/
 for(let i=0;i<20000;i++){const id=workflow.telemetryId();assert.match(id,SHAPE);for(const m of workflow.ID_FORBIDDEN_MARKERS) assert.ok(!id.includes(m),id)}
})
