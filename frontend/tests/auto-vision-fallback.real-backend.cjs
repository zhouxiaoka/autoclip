const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server')

const CODE='vision_unavailable_subtitle_fallback'
const MESSAGE='视觉服务暂不可用，已切换为字幕分析继续制作。'
const langs=['zh','en','ja','ko','es','pt','ru','fr']
const catalogs=Object.fromEntries(langs.map(lang=>[lang,require('../src/i18n/locales/'+lang+'.json')]))

function load(file,mocks={}){
 const exports={}
 runInSandbox(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src',file),'utf8'),{
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX},
 }).outputText,{exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL,require:id=>{
  assert.ok(id in mocks,id);return mocks[id]
 }})
 return exports
}

test('S5 AUTO fallback message renders from the plan in all eight locales',()=>{
 const missing=langs.filter(lang=>!catalogs[lang][MESSAGE]||(lang!=='zh'&&catalogs[lang][MESSAGE]===MESSAGE))
 assert.deepEqual(missing,[],'Every locale needs a translated vision-unavailable/subtitle-switch message')
 for(const lang of langs){
  const t=text=>catalogs[lang][text]||text
  const passthrough=props=>React.createElement('div',null,props.children)
  const Plan=load('features/studio/PlanSummary.tsx',{
   react:React,'react/jsx-runtime':require('react/jsx-runtime'),
   'react-i18next':{useTranslation:()=>({t})},'../../i18n':{t},
   '../../ui':{Btn:passthrough,Dialog:()=>null,Row:passthrough,Segmented:()=>null,fmtDuration:String},
   './types':{defaultImportOptions:{},goalLabels:{content:'content'},languages:[]},
   './ImportPreferences':{default:()=>null},'./api':{studioApi:{},errorText:String},
   'react-router-dom':{useNavigate:()=>()=>{}},'../../services/api':{speechApi:{}},
   './TranscriptionGatePrompt':{default:'transcription-gate'},'./transcriptionRecovery':{isRecoveryCode:c=>['whisper_not_installed','whisper_install_failed','whisper_model_missing','whisper_model_failed','whisper_installing','whisper_model_downloading'].includes(c)},'./useTranscriptionRecovery':{useTranscriptionRecovery:()=>[{phase:'idle',percent:null},{open:(c)=>{(globalThis.__recoveryOpened||(globalThis.__recoveryOpened=[])).push(c)},close(){},install:async()=>{},retry:async()=>{}}]},
  }).default
  const html=renderToStaticMarkup(React.createElement(Plan,{
   projectId:'fixture',status:'awaiting_confirmation',onChanged(){},plan:{
    id:'plan',mode:'fallback',reason:MESSAGE,degrade_reason:CODE,recommended_analysis:'subtitle',
    suggested_goals:['content'],preferences:{goal:'content',aspect:'original',language:'source'},overrides:{},
   },
  }))
  assert.ok(html.includes(catalogs[lang][MESSAGE]),lang+' must show the localized fallback message')
 }
})

const workflow=require('./helpers/real-backend.cjs').withRealBackend(require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/workflow.ts')))
for(const kind of ['studio-screen','studio-generation']){
 test('S5 '+kind+' records the fixed AUTO degrade reason once without content',()=>{
  const events=[],storage=new Map()
  const tracker=new workflow.WorkflowTracker({
   getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key),
  },()=>true,(name,props)=>{events.push({name,props});return true})
  tracker.watch(kind,'fixture',undefined,undefined,{},false,'run')
  const watch=tracker.list().find(item=>item.kind===kind)
  const snapshot={
   plan:{id:'plan',mode:'fallback',recommended_analysis:'subtitle',degrade_reason:CODE,
    reason:MESSAGE,local_evidence:{subtitle_status:'available'}},
   analysis:{status:'completed',phase:'production',run_id:'run'},
   generation:{auto_start:true,status:'completed',route:'subtitle',degrade_reason:CODE},
  }
  tracker.observeStudio(watch,snapshot)
  tracker.observeStudio(watch,snapshot)
  const finished=events.filter(event=>event.name===kind.replaceAll('-','_')+'_finished')
  if(kind==='studio-generation'){assert.equal(finished.length,0);return}
  assert.equal(finished.length,1)
  assert.equal(finished[0].props.degrade_reason,CODE)
  assert.equal(JSON.stringify(finished).includes(MESSAGE),false)
 })
}

test('S5 telemetry accepts only the fixed degrade reason code',()=>{
 assert.equal(workflow.safeStudioProperties({degrade_reason:CODE}).degrade_reason,CODE)
 assert.equal(workflow.safeStudioProperties({degrade_reason:'synthetic-unrecognized-reason'}).degrade_reason,undefined)
 assert.equal(workflow.safeStudioProperties({degrade_reason:MESSAGE}).degrade_reason,undefined)
})

// the new reasons reach the terminal event on both auto and manual-confirm entries.
for(const reason of ['frame_extract_subtitle_fallback','source_too_long_subtitle_route']){
 for(const entry of ['auto','manual']){
  test(`R12 ${entry} entry: terminal event carries ${reason} once`,()=>{
   const events=[],storage=new Map()
   const tracker=new workflow.WorkflowTracker({
    getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key),
   },()=>true,(name,props)=>{events.push({name,props});return true})
   const kind=entry==='auto'?'studio-generation':'studio-production'
   tracker.watch(kind,entry==='auto'?'fixture':'plan',undefined,undefined,{},false,'run')
   const watch=tracker.list().find(item=>item.kind===kind)
   const snapshot={
    plan:{id:'plan',mode:'local',recommended_analysis:'subtitle',confirmed_analysis:'subtitle',degrade_reason:reason},
    analysis:{status:'completed',outcome:'completed',phase:'production',run_id:'run'},
    generation:{auto_start:entry==='auto',status:'completed',route:'subtitle'},
   }
   tracker.observeStudio(watch,snapshot)
   tracker.observeStudio(watch,snapshot)
   const finished=events.filter(event=>event.name===kind.replaceAll('-','_')+'_finished')
   assert.equal(finished.length,0)
  })
 }
}
