const {test}=require('node:test')
const assert=require('node:assert/strict')
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),ts=require('typescript')
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server'),{createInstance}=require('i18next')
const langs=['zh','en','ja','ko','es','pt','ru','fr']
const catalogs=Object.fromEntries(langs.map(l=>[l,require('../src/i18n/locales/'+l+'.json')]))
const root=path.resolve(__dirname,'../src/features/studio')
function history(i18n){
 const exports={}
 const mocks={
  'react/jsx-runtime':require('react/jsx-runtime'),
  'react-i18next':{useTranslation:()=>({t:s=>i18n.t(s)})},
  '../../i18n':{t:s=>i18n.t(s),getLocale:()=>i18n.language},
  '../../ui':{Dialog:p=>React.createElement('section',null,p.children),ProgressLine:()=>null},
  'react-router-dom':{Link:p=>React.createElement('a',null,p.children)},
  './StudioDownloadLink':{default:()=>null},
 }
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root,'ExportHistory.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:id=>{assert.ok(mocks[id],id);return mocks[id]}})
 return exports.default
}
test('export history renders localized server warnings/restart errors in all eight languages, retaining source titles and unknown errors',async()=>{
 const i=createInstance();await i.init({resources:Object.fromEntries(langs.map(l=>[l,{translation:catalogs[l]}])),lng:'en',fallbackLng:'en',keySeparator:false,nsSeparator:false,interpolation:{escapeValue:false}})
 const History=history(i),title='原素材没有音轨，本次导出无声',unknown='decoder failed at frame 42'
 const base={title,revision:2,created_at:'2026-09-25T00:00:00Z'}
 const jobs=[{...base,job_id:'ok',status:'completed',result:{warnings:[title]}},{...base,job_id:'restart',status:'failed',error:'服务已重启，请重新导出'},{...base,job_id:'unknown',status:'failed',error:unknown}]
 for(const lang of langs){
  await i.changeLanguage(lang)
  const html=renderToStaticMarkup(React.createElement(History,{open:true,onClose(){},projectId:'p',jobs}))
  assert.ok(html.includes('<b>'+title+'</b>'),lang+' source title preserved')
  assert.ok(html.includes(catalogs[lang][title]),lang+' warning')
  assert.ok(html.includes(catalogs[lang]['服务已重启，请重新导出']),lang+' restart')
  assert.ok(html.includes(unknown),lang+' diagnostics preserved')
 }
})
test('all backend processing stages have translations in eight catalogs',()=>{
 const stages=['下载素材','理解画面','准备素材','快速判断适合的制作类型','开始制作所选内容','制作内容切片','制作精彩高光','制作推广成片','扫描画面，寻找候选高光','复核首选高光的起止边界','组织推广开头与成片草稿','整理高光成片草稿']
 for(const lang of langs)for(const stage of stages){assert.ok(catalogs[lang][stage],lang+stage);if(lang!=='zh')assert.notEqual(catalogs[lang][stage],stage)}
})
