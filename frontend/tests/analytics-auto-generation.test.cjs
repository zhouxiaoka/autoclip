const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')

function loadWorkflow(){
 const source=fs.readFileSync(path.join(__dirname,'../src/analytics/workflow.ts'),'utf8')
 const exports={}
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,{exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL})
 return exports
}
const workflow=loadWorkflow()

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
  interview_count:1,podcast_count:1,landscape_count:0,speaker_framed_count:1,packaging_fallback_count:1,trimmed_count:1,burned_captions:false,duration_ms:240000})
 const props=workflow.safeStudioProperties({...summary,title:'Private title',name:'Sam Altman',template:'interview_zh',packaging_style:'boxed',framing:'speaker'})
 assert.equal(JSON.stringify(props).includes('Private'),false)
 assert.equal(JSON.stringify(props).includes('Sam'),false)
 assert.equal(props.template,'interview_zh'); assert.equal(props.packaging_style,'boxed'); assert.equal(props.framing,'speaker')
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
