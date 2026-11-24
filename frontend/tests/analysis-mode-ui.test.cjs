const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),ts=require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
function load(file,mocks){const exports={};runInSandbox(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/features/studio',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:id=>{assert.ok(id in mocks,id);return mocks[id]}});return exports}
function view(mode,goals,available=true){
 const states=[mode,{visual_analysis:available,visual_model:'test-model'},false,{},goals,false,''];let index=0
 const calls=[]
 const element=(type,props)=>({type,props})
 const component=load('PlanSummary.tsx',{
 'react-i18next':{useTranslation:()=>{}},'../../i18n':{t:x=>x},
 react:{useState:()=>{const n=index++;return [states[n],v=>{states[n]=v}]},useEffect:()=>{},useRef:v=>({current:v})},
 'react/jsx-runtime':{jsx:element,jsxs:element,Fragment:'fragment'},
 '../../ui':{Btn:'button',Dialog:'dialog',Row:'row',Segmented:'segmented',fmtDuration:String},
 './types':{defaultImportOptions:{},goalLabels:{content:'content',highlight:'highlight',promo:'promo'},languages:[]},
 './PlanEditDialog':{default:()=>null},'./ImportPreferences':{default:'preferences'},
 './api':{studioApi:{confirmPlan:async(...args)=>calls.push(args)},errorText:String,errorCode:()=>undefined},
 'react-router-dom':{useNavigate:()=>()=>{}},'../../services/api':{speechApi:{}},
 './TranscriptionGatePrompt':{default:'transcription-gate'},'./transcriptionRecovery':{isRecoveryCode:c=>['whisper_not_installed','whisper_install_failed','whisper_model_missing','whisper_model_failed','whisper_installing','whisper_model_downloading'].includes(c)},'./useTranscriptionRecovery':{useTranscriptionRecovery:()=>[{phase:'idle',percent:null},{open:(c)=>{(globalThis.__recoveryOpened||(globalThis.__recoveryOpened=[])).push(c)},close(){},install:async()=>{},retry:async()=>{}}]}
 }).default
 const render=()=>{index=0;return component({projectId:'p',plan:{id:'plan',suggested_goals:goals,preferences:{goal:'content',aspect:'original',language:'source'},overrides:{}},status:'awaiting_confirmation',onChanged:()=>{}})}
 const nodes=n=>!n||typeof n!=='object'?[]:Array.isArray(n)?n.flatMap(nodes):[n,...nodes(n.props?.children)]
 return {states,calls,render:()=>nodes(render())}
}
test('visual selection blocks content-only output without silently changing choices',()=>{
 const x=view('visual',['content']);let nodes=x.render()
 assert.equal(nodes.find(n=>n.props?.children==='确认并开始制作').props.disabled,true)
 nodes.find(n=>n.type==='segmented').props.onChange('subtitle')
 assert.deepEqual(x.states[4],['content'])
 assert.equal(x.render().find(n=>n.props?.children==='确认并开始制作').props.disabled,false)
})
test('missing capability blocks visual confirmation but subtitle content remains available',()=>{
 for(const [mode,goals,disabled] of [['visual',['highlight'],true],['subtitle',['content'],false]]){
 const x=view(mode,goals,false);assert.equal(x.render().find(n=>n.props?.children==='确认并开始制作').props.disabled,disabled)
 }
})
test('confirm sends explicit route with selected outputs',async()=>{
 const x=view('visual',['highlight']);await x.render().find(n=>n.props?.children==='确认并开始制作').props.onClick()
 assert.equal(x.calls[0][4],'visual');assert.deepEqual(x.calls[0][2],['highlight'])
})

test('unified redo dialog submits platform auto-start in-place while manual plan edit keeps confirmation flow', async () => {
  const React = require('react')
  const { renderToStaticMarkup } = require('react-dom/server')
  const calls = []
  let pickedPlatforms, submit, cancel, cancelled = 0, submitted = 0
  const Dialog = ({ children, footer }) => React.createElement('div', null, children, footer)
  const Btn = ({ children, onClick }) => {
    if (children === '开始重做' || children === '生成新方案') submit = onClick
    if (children === '取消') cancel = onClick
    return null
  }
  const component = load('PlanEditDialog.tsx', {
    react: React, 'react/jsx-runtime': require('react/jsx-runtime'),
    'react-i18next': { useTranslation: () => ({ t: s => s }) },
    '../../ui': { Dialog, Btn },
    './ImportPreferences': { default: () => null },
    './PlatformPicker': { default: ({ value }) => { pickedPlatforms = value; return null } },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' }, languages: [{ value: 'source', label: '原语言' }, { value: 'en', label: 'English' }] },
    './api': { studioApi: { correctPlan: async (id, body) => calls.push({ id, body }) }, errorText: String },
  }).default
  const plan = {
    selected_goals: ['highlight'],
    overrides: { auto_start: true, goal: 'auto', source_window: { start: 0, end: 90 } },
    confirmed_preferences: { goal: 'highlight', duration: 18, aspect: 'original', language: 'en' },
    goal_preferences: { highlight: { aspect: 'portrait' } },
  }
  renderToStaticMarkup(React.createElement(component, {
    projectId: 'p', plan, remake: true, initialPlatforms: ['xiaohongshu'], existingPlatforms: ['douyin'],
    onClose: () => cancelled++, onSubmitted: () => submitted++,
  }))
  cancel()
  assert.equal(cancelled, 1)
  assert.equal(calls.length, 0)
  assert.deepEqual(JSON.parse(JSON.stringify(pickedPlatforms)), ['xiaohongshu'])
  await submit()
  assert.equal(submitted, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [{ id: 'p', body: {
    goal: 'auto', instruction: '', auto_start: true, platforms: ['xiaohongshu'], source_window: { start: 0, end: 90 },
    duration: 18, aspect: null, language: 'en',
  } }])
})
