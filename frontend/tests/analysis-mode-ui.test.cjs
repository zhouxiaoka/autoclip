const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
function load(file,mocks){const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/features/studio',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:id=>{assert.ok(id in mocks,id);return mocks[id]}});return exports}
function view(mode,goals,available=true){
 const states=[mode,{visual_analysis:available,visual_model:'test-model'},false,{},goals,false,''];let index=0
 const calls=[]
 const element=(type,props)=>({type,props})
 const component=load('PlanSummary.tsx',{
 'react-i18next':{useTranslation:()=>{}},'../../i18n':{t:x=>x},
 react:{useState:()=>{const n=index++;return [states[n],v=>{states[n]=v}]},useEffect:()=>{}},
 'react/jsx-runtime':{jsx:element,jsxs:element,Fragment:'fragment'},
 '../../ui':{Btn:'button',Dialog:'dialog',fmtDuration:String},
 './types':{defaultImportOptions:{},goalLabels:{content:'content',highlight:'highlight',promo:'promo'},languages:[]},
 './ImportPreferences':{default:'preferences'},
 './api':{studioApi:{confirmPlan:async(...args)=>calls.push(args)},errorText:String}
 }).default
 const render=()=>{index=0;return component({projectId:'p',plan:{id:'plan',suggested_goals:goals,preferences:{goal:'content',aspect:'original',language:'source'},overrides:{}},status:'awaiting_confirmation',onChanged:()=>{}})}
 const nodes=n=>!n||typeof n!=='object'?[]:Array.isArray(n)?n.flatMap(nodes):[n,...nodes(n.props?.children)]
 return {states,calls,render:()=>nodes(render())}
}
test('visual selection blocks content-only output without silently changing choices',()=>{
 const x=view('visual',['content']);let nodes=x.render()
 assert.equal(nodes.find(n=>n.props?.children==='确认并开始制作').props.disabled,true)
 nodes.find(n=>n.type==='select').props.onChange({target:{value:'subtitle'}})
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
