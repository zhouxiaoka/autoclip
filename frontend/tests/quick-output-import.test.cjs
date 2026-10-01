const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
class FormDataMock { constructor(){this.rows=[]} append(key,value){this.rows.push([key,String(value)])} get(key){const row=this.rows.find(item=>item[0]===key);return row&&row[1]} entries(){return this.rows.values()} }

function load(mocks){
 const exports={}
 const source=fs.readFileSync(path.join(__dirname,'../src/features/studio/CreativeImport.tsx'),'utf8')
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText,{FormData:FormDataMock,exports,require:id=>{assert.ok(id in mocks,id);return mocks[id]}})
 return exports.default
}
function nodes(value){return !value||typeof value!=='object'?[]:Array.isArray(value)?value.flatMap(nodes):[value,...nodes(value.props?.children)]}

test('quick import submits platform targets, branding and auto-starts to results',async()=>{
 const calls=[],navigations=[];let index=0
 const states=[['link',()=>{}],['https://youtube.com/watch?v=video',()=>{}],[null,()=>{}],[null,()=>{}],[{goal:'auto',language:'source',aspect:null,duration:null,instruction:''},()=>{}],['',()=>{}],[['douyin'],()=>{}],[false,()=>{}],[false,()=>{}],['',()=>{}]]
 const component=load({
  'react-i18next':{useTranslation:()=>{}},'../../i18n':{t:x=>x},
  react:{useState:()=>states[index++],useEffect:()=>{}},antd:{Select:'select'},'react-router-dom':{useNavigate:()=>path=>navigations.push(path)},
  'react/jsx-runtime':{jsx:(type,props)=>({type,props}),jsxs:(type,props)=>({type,props}),Fragment:'fragment'},
  '../../ui':{Btn:'button',Segmented:'segmented',Dialog:'dialog'},'./PlatformPicker':{default:'platform-picker'},
  './api':{studioApi:{import:async body=>{calls.push(body);return {project_id:'project-1'}}},errorText:String},'../../analytics/studio':{trackQuickOutputPlatforms(){}},'../../analytics/experience':{trackExperience(){}},
  './types':{defaultImportOptions:{goal:'auto',language:'source',aspect:null,duration:null,instruction:''}},
  './ImportPreferences':{default:'preferences'},'./studio.css':{},'./quick-output.css':{},
 })
 const tree=nodes(component({onImported:async()=>{}}))
 await tree.find(node=>node.type==='button'&&node.props?.variant==='cta').props.onClick()
 assert.equal(calls.length,1)
 assert.deepEqual([...calls[0].entries()].filter(([key])=>key==='platforms'),[['platforms','douyin']])
 assert.equal(calls[0].get('auto_start'),'true')
 assert.equal(calls[0].get('portrait_style'),'auto')
 assert.equal(calls[0].get('brand_outro_enabled'),undefined, 'the backend uses the saved application setting')
 assert.deepEqual(navigations,['/project/project-1'])
})

test('quick import source no longer tells users to confirm a plan',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../src/features/studio/CreativeImport.tsx'),'utf8')
 assert.match(source,/直接生成可发布成片/)
 assert.match(source,/PlatformPicker/)
 assert.doesNotMatch(source,/navigate\(`\/import\/\$\{result\.project_id\}`\)/)
})
